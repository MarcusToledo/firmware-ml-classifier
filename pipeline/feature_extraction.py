"""Extrai features estatísticas, strings e estrutura de firmware em lote."""

from __future__ import annotations

import hashlib
import logging
import math
import os
import re
import subprocess
import tempfile
from collections.abc import Iterable
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Any, NamedTuple, Union, cast

import yaml
from gensim.models import Doc2Vec

from pipeline.firmware_version import infer_version_from_filename
from src.evidence.binwalk_findings import (
    count_crypto_signatures,
    find_crypto_signatures,
    find_encrypted_sections,
    has_encrypted_sections,
)
from src.evidence.findings import SecurityFinding
from src.evidence.patterns import findings_to_counts, scan_strings_findings
from src.feature_extraction import FeatureConfig, combine_features, extract_features
from src.features.binwalk import (
    count_filesystems,
    detect_compression_type,
    detect_fs_type,
)
from src.features.doc2vec import Doc2VecConfig, load_doc2vec
from src.features.filesystem import (
    FilesystemResult,
    filesystem_features,
    unavailable_filesystem,
)
from src.features.statistics import ByteStats, StreamingStats
from src.features.strings import DocumentBuilder, iter_ascii_strings
from src.features.unpack import (
    STATUS_FAILURE,
    STATUS_NO_FILESYSTEM,
    STATUS_NOT_RUN,
    STATUS_OK,
    STATUS_TIME,
    Toolchain,
    UnpackLimits,
    isolated_env,
    iter_extracted_files,
    stop_process_group,
    unpack_firmware,
)
from src.io_utils import iter_file_chunks

FeatureValue = Union[float, int, bool, str, None]
DEFAULT_MAX_BYTES = 268_435_456
VERSION_SOURCE_DIRECTORY = "directory"
VERSION_SOURCE_FILENAME = "filename"
THIRD_PARTY_DDWRT = "dd-wrt"
STRINGS_FILESYSTEM = "filesystem"
STRINGS_BLOB = "blob"
BINWALK_STATUS_ERROR = "erro"
BINWALK_STATUS_TIMEOUT = "timeout"
_BINWALK_SCAN_TIMEOUT_SECONDS = 60
_STRING_SCAN_BATCH_SIZE = 10_000
_DDWRT_BANNER = "DD-WRT"
_RELATIVE_IDENTITY_PARTS = 3
_BINWALK_FIELDS = 3
_BINWALK_DESCRIPTION_INDEX = _BINWALK_FIELDS - 1
LOGGER = logging.getLogger(__name__)
_VERSION_SUFFIX_RE = re.compile(
    r"^([a-z][a-z0-9-]*\d[a-z0-9-]*)_(\d+\.\d.*)$", re.IGNORECASE
)


class PathMetadata(NamedTuple):
    """Representa identidade e origem da versão inferidas do path relativo."""

    brand: str | None
    model: str | None
    label: str | None
    version: str | None
    version_source: str | None


def is_third_party_name(name: str) -> bool:
    """Identifica imagens webflash de terceiros pelo nome."""
    return "webflash" in name.lower()


def _split_model_version(model: str) -> tuple[str, str | None]:
    """Separa sufixo de versão decimal sem confundir revisão de hardware."""
    match = _VERSION_SUFFIX_RE.match(model)
    return (match.group(1).lower(), match.group(2)) if match else (model.lower(), None)


def infer_brand_model_label_from_path(relative_path: Path) -> PathMetadata:
    """Infere identidade apenas de fabricante/modelo/arquivo relativos à raiz."""
    if (
        len(relative_path.parts) != _RELATIVE_IDENTITY_PARTS
        or relative_path.is_absolute()
    ):
        return PathMetadata(None, None, None, None, None)
    brand = relative_path.parts[0].strip().lower()
    model, directory_version = _split_model_version(relative_path.parts[1].strip())
    if not brand or not model or not relative_path.name.strip():
        return PathMetadata(None, None, None, None, None)
    if is_third_party_name(relative_path.name):
        version, source = None, None
    elif directory_version is not None:
        version, source = directory_version, VERSION_SOURCE_DIRECTORY
    else:
        version = infer_version_from_filename(brand, relative_path.name)
        source = VERSION_SOURCE_FILENAME if version is not None else None
    return PathMetadata(brand, model, f"{brand}_{model}", version, source)


def relative_to_root(path: Path, root: Path | None) -> Path | None:
    """Obtém o path relativo à raiz canônica, sem aceitar saída da raiz."""
    if root is None:
        return None
    try:
        return path.resolve().relative_to(root.resolve())
    except ValueError:
        return None


def find_off_layout_paths(paths: Iterable[Path], root: Path | None) -> list[Path]:
    """Lista arquivos fora da raiz ou do layout de três componentes."""
    return [
        path
        for path in paths
        if (relative := relative_to_root(path, root)) is None
        or infer_brand_model_label_from_path(relative).brand is None
    ]


@dataclass(frozen=True)
class PipelineConfig:
    """Guarda limites de leitura, unpack e configuração das features."""

    max_bytes: int
    feature: FeatureConfig
    doc2vec: Doc2VecConfig
    doc2vec_model_path: Path | None
    unpack: UnpackLimits = UnpackLimits()


@dataclass(frozen=True)
class PipelineResult:
    """Agrega features, metadados e achados de um firmware."""

    firmware_id: str | None
    features: dict[str, FeatureValue]
    metadata: dict[str, Any]
    findings: list[SecurityFinding]


def apply_overrides(
    config: dict[str, Any], overrides: dict[str, Any]
) -> dict[str, Any]:
    """Aplica overrides em caminhos pontuados da configuração."""
    updated = dict(config)
    for key, value in overrides.items():
        cursor = updated
        parts = key.split(".")
        for part in parts[:-1]:
            cursor = cursor.setdefault(part, {})
        cursor[parts[-1]] = value
    return updated


def _positive(
    value: Any, name: str, path: Path | None, *, integer: bool = True
) -> int | float:
    """Valida limites positivos sem aceitar booleanos como números."""
    try:
        if isinstance(value, bool) or value in (None, "null"):
            raise ValueError
        parsed = int(value) if integer else float(value)
        if (
            not math.isfinite(parsed)
            or parsed <= 0
            or (integer and str(value) != str(parsed))
        ):
            raise ValueError
        return parsed
    except (ValueError, TypeError) as exc:
        if name == "max_bytes":
            raise ValueError(
                f"max_bytes inválido ({value!r}) em {path}: DEVE ser inteiro positivo"
            ) from exc
        raise ValueError(
            f"{name} inválido ({value!r}) em {path}: DEVE ser positivo"
        ) from exc


def _load_unpack(raw: Any, path: Path | None) -> UnpackLimits:
    """Carrega limites de desempacotamento com padrões explícitos."""
    if not isinstance(raw, dict):
        raise ValueError(f"unpack inválido ({raw!r}) em {path}: DEVE ser mapeamento")
    defaults = UnpackLimits()
    return UnpackLimits(
        max_total_bytes=cast(
            int,
            _positive(
                raw.get("max_total_bytes", defaults.max_total_bytes),
                "unpack.max_total_bytes",
                path,
            ),
        ),
        max_files=cast(
            int,
            _positive(
                raw.get("max_files", defaults.max_files), "unpack.max_files", path
            ),
        ),
        timeout_seconds=cast(
            float,
            _positive(
                raw.get("timeout_seconds", defaults.timeout_seconds),
                "unpack.timeout_seconds",
                path,
                integer=False,
            ),
        ),
    )


def _load_feature(raw: dict[str, Any], doc: dict[str, Any]) -> FeatureConfig:
    """Carrega os limites existentes de documento e Doc2Vec."""
    defaults = FeatureConfig()
    doc_defaults = defaults.doc2vec
    return FeatureConfig(
        min_string_len=int(raw.get("min_string_len", defaults.min_string_len)),
        max_string_len=int(raw.get("max_single_string_len", defaults.max_string_len)),
        max_strings=int(raw.get("max_strings", defaults.max_strings)),
        max_doc_chars=int(raw.get("max_doc_chars", defaults.max_doc_chars)),
        doc2vec=Doc2VecConfig(
            vector_size=int(doc.get("vector_size", doc_defaults.vector_size)),
            window=int(doc.get("window", doc_defaults.window)),
            epochs=int(doc.get("epochs", doc_defaults.epochs)),
            min_count=int(doc.get("min_count", doc_defaults.min_count)),
            seed=int(doc.get("seed", doc_defaults.seed)),
            workers=int(doc.get("workers", doc_defaults.workers)),
            dm=int(doc.get("dm", doc_defaults.dm)),
            alpha=float(doc.get("alpha", doc_defaults.alpha)),
            min_alpha=float(doc.get("min_alpha", doc_defaults.min_alpha)),
        ),
    )


def load_pipeline_config(
    path: Path | None, overrides: dict[str, Any]
) -> PipelineConfig:
    """Carrega YAML opcional e rejeita path inexistente ou limites inválidos."""
    raw: dict[str, Any] = {}
    if path is not None:
        if not path.exists():
            raise FileNotFoundError(f"--config não encontrado: {path}")
        raw = yaml.safe_load(path.read_text()) or {}
    merged = apply_overrides(raw, overrides)
    doc_raw = merged.get("doc2vec", {})
    feature = _load_feature(merged.get("feature", {}), doc_raw)
    model_path = doc_raw.get("model_path")
    return PipelineConfig(
        max_bytes=cast(
            int,
            _positive(merged.get("max_bytes", DEFAULT_MAX_BYTES), "max_bytes", path),
        ),
        feature=feature,
        doc2vec=feature.doc2vec,
        doc2vec_model_path=Path(model_path) if model_path else None,
        unpack=_load_unpack(merged.get("unpack", {}), path),
    )


def load_doc2vec_model(path: Path | None) -> Doc2Vec | None:
    """Carrega modelo opcional e avisa se não estiver disponível."""
    if path is None or not path.exists():
        LOGGER.warning("Doc2Vec model not found at %s; embeddings will be zero", path)
        return None
    return load_doc2vec(str(path))


def _run_binwalk_scan(path: Path, toolchain: Toolchain) -> tuple[int, str]:
    """Roda a varredura em grupo isolado e encerra seus processos órfãos."""
    with tempfile.TemporaryDirectory(prefix="fmc-scan-") as scratch:
        home = Path(scratch)
        process = subprocess.Popen(
            [toolchain.binwalk, str(path.absolute())],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            errors="replace",
            env=isolated_env(toolchain, home, home),
            start_new_session=True,
        )
        try:
            stdout, _ = process.communicate(timeout=_BINWALK_SCAN_TIMEOUT_SECONDS)
        except subprocess.TimeoutExpired:
            stop_process_group(process)
            raise
        stop_process_group(process)
        return process.returncode, stdout


def _scan_binwalk(path: Path, toolchain: Toolchain) -> tuple[list[str], str]:
    """Varre assinaturas e expõe erro ou timeout sem achados espúrios."""
    try:
        returncode, stdout = _run_binwalk_scan(path, toolchain)
    except subprocess.TimeoutExpired:
        LOGGER.warning("binwalk timeout para %s", path)
        return [], BINWALK_STATUS_TIMEOUT
    except OSError as exc:
        LOGGER.warning("binwalk erro para %s: código indisponível: %s", path, exc)
        return [], BINWALK_STATUS_ERROR
    if returncode != 0:
        LOGGER.warning("binwalk erro para %s: código %d", path, returncode)
        return [], BINWALK_STATUS_ERROR
    descriptions = []
    for line in stdout.splitlines():
        parts = line.split(None, _BINWALK_DESCRIPTION_INDEX)
        if len(parts) == _BINWALK_FIELDS and parts[0].isdigit():
            descriptions.append(parts[_BINWALK_DESCRIPTION_INDEX].strip())
    return descriptions, STATUS_OK


def _scan_string_stream(
    strings: Iterable[str],
    document: DocumentBuilder,
    batch_size: int = _STRING_SCAN_BATCH_SIZE,
) -> tuple[list[SecurityFinding], bool]:
    """Varre todas as strings em lotes sem limitar detectores pelo documento."""
    findings: list[SecurityFinding] = []
    batch: list[str] = []
    ddwrt = False
    for value in strings:
        document.add(value)
        ddwrt |= _DDWRT_BANNER in value
        batch.append(value)
        if len(batch) >= batch_size:
            findings.extend(scan_strings_findings(batch))
            batch.clear()
    if batch:
        findings.extend(scan_strings_findings(batch))
    return findings, ddwrt


def _scan_extracted(
    root: Path, config: PipelineConfig, document: DocumentBuilder
) -> tuple[list[SecurityFinding], bool, int]:
    """Lê só arquivos regulares até max_bytes e conta arquivos cortados."""
    findings: list[SecurityFinding] = []
    banner = False
    cut = 0
    for file in iter_extracted_files(root):
        try:
            cut += file.lstat().st_size > config.max_bytes
            strings = iter_ascii_strings(
                iter_file_chunks(file, config.max_bytes, nofollow=True),
                config.feature.min_string_len,
                config.feature.max_string_len,
            )
            file_findings, file_banner = _scan_string_stream(strings, document)
            findings.extend(file_findings)
            banner |= file_banner
        except OSError as exc:
            LOGGER.warning("Falha ao ler arquivo extraído %s: %s", file, exc)
    return findings, banner, cut


@dataclass(frozen=True)
class _FirmwareRead:
    """Agrupa a primeira passada sobre o arquivo bruto."""

    firmware_id: str
    stats: ByteStats
    size: int
    file_size: int


def _read_stats(path: Path, limit: int, file_size: int) -> _FirmwareRead:
    """Calcula SHA256 e estatísticas em uma passada sem armazenar o arquivo."""
    digest = hashlib.sha256()
    streaming = StreamingStats()
    size = 0
    for chunk in iter_file_chunks(path, limit):
        digest.update(chunk)
        streaming.update(chunk)
        size += len(chunk)
    if size != min(file_size, limit):
        raise ValueError(
            f"arquivo alterado durante a leitura: {path} "
            f"(stat {file_size} bytes, lidos {size})"
        )
    return _FirmwareRead(digest.hexdigest(), streaming.result(), size, file_size)


def _effective_unpack_status(status: str, fs_type: str | None) -> str:
    """Marca falha quando a varredura viu filesystem e nenhuma raiz foi extraída.

    O binwalk mantém o recorte quando o extrator do filesystem falha (ex.:
    cramfs sem ``cramfsck``); sem esta regra o caso se confundiria com imagem
    sem filesystem.
    """
    if status == STATUS_NO_FILESYSTEM and fs_type is not None:
        return STATUS_FAILURE
    return status


def _string_features(
    path: Path,
    config: PipelineConfig,
    toolchain: Toolchain,
    document: DocumentBuilder,
    fs_type: str | None,
) -> tuple[list[SecurityFinding], bool, str, str | None, str, int, FilesystemResult]:
    """Prefere filesystem e devolve o motivo de falha junto das strings."""
    with unpack_firmware(path, config.unpack, toolchain) as unpack:
        status = _effective_unpack_status(unpack.status, fs_type)
        error = unpack.error
        if status == STATUS_FAILURE and not error:
            error = "extrator falhou sem diagnóstico"
        if status != unpack.status:
            error = f"filesystem {fs_type} detectado e não extraído"
            LOGGER.warning("%s em %s: %s", error, path, unpack.error)
        if status == STATUS_OK:
            assert unpack.root is not None
            fs = filesystem_features(unpack.root, config.max_bytes)
            findings, banner, cut = _scan_extracted(unpack.root, config, document)
            return findings, banner, status, None, STRINGS_FILESYSTEM, cut, fs
        if status == STATUS_TIME:
            return [], False, status, error, STATUS_NOT_RUN, 0, unavailable_filesystem()
    strings = iter_ascii_strings(
        iter_file_chunks(path, config.max_bytes),
        config.feature.min_string_len,
        config.feature.max_string_len,
    )
    findings, banner = _scan_string_stream(strings, document)
    return findings, banner, status, error, STRINGS_BLOB, 0, unavailable_filesystem()


def _structural_features(
    descriptions: list[str], variance: float
) -> dict[str, FeatureValue]:
    """Converte descrições binwalk em features estruturais estáveis."""
    return {
        "n_filesystems": count_filesystems(descriptions),
        "n_crypto_signatures": count_crypto_signatures(descriptions),
        "has_encrypted_sections": has_encrypted_sections(descriptions),
        "fs_type": detect_fs_type(descriptions),
        "compression_type": detect_compression_type(descriptions),
        "entropy_variance_across_sections": variance,
    }


def _identity_metadata(
    path: Path, meta_path: str, identity: PathMetadata, third_party: bool
) -> dict[str, Any]:
    """Monta os metadados de identidade comuns a sucesso e erro."""
    return {
        "path": meta_path,
        "brand": identity.brand,
        "model": identity.model,
        "label": identity.label,
        "version": identity.version,
        "version_source": identity.version_source,
        "third_party": (
            THIRD_PARTY_DDWRT if is_third_party_name(path.name) or third_party else None
        ),
    }


@dataclass(frozen=True)
class _StringScan:
    """Agrupa o resultado da varredura de strings de um firmware."""

    findings: list[SecurityFinding]
    banner: bool
    unpack_status: str
    unpack_error: str | None
    strings_source: str
    files_cut: int
    filesystem: FilesystemResult


def _build_result(
    path: Path,
    config: PipelineConfig,
    model: Doc2Vec | None,
    read: _FirmwareRead,
    binwalk: tuple[list[str], str],
    scan: _StringScan,
    document: DocumentBuilder,
    meta_path: str,
    identity: PathMetadata,
) -> PipelineResult:
    """Combina features, achados e metadados de uma extração bem-sucedida."""
    descriptions, binwalk_status = binwalk
    vector = extract_features(
        read.stats,
        document.document(),
        document.truncated,
        read.size,
        config.feature,
        model,
    )
    features: dict[str, FeatureValue] = {
        **combine_features(vector),
        **_structural_features(
            descriptions, read.stats.entropy_variance_across_sections
        ),
        **findings_to_counts(scan.findings),
        **scan.filesystem.features,
    }
    findings = [
        *scan.findings,
        *find_crypto_signatures(descriptions),
        *find_encrypted_sections(descriptions),
    ]
    metadata = {
        "read_ok": True,
        "byte_len": read.size,
        "bytes_used": read.size,
        "file_size": read.file_size,
        "max_bytes": config.max_bytes,
        "truncated": vector.truncated,
        "max_bytes_applied": True,
        "doc2vec_used": model is not None,
        "error": None,
        "binwalk_status": binwalk_status,
        "unpack_status": scan.unpack_status,
        "unpack_error": scan.unpack_error,
        "strings_source": scan.strings_source,
        "unpack_files_cut": scan.files_cut,
        **_identity_metadata(path, meta_path, identity, scan.banner),
        **scan.filesystem.metadata,
    }
    return PipelineResult(read.firmware_id, features, metadata, findings)


def extract_features_from_path(
    path: Path,
    config: PipelineConfig,
    model: Doc2Vec | None,
    toolchain: Toolchain,
    brand: str | None = None,
    model_name: str | None = None,
    label: str | None = None,
    version: str | None = None,
    version_source: str | None = None,
    dataset_root: Path | None = None,
) -> PipelineResult:
    """Extrai um firmware em streaming e preserva estado de cada etapa.

    Levanta ``ValueError`` quando só um de ``version``/``version_source`` vem
    preenchido. Falha de leitura, arquivo vazio ou erro de E/S no
    desempacotamento viram linha com ``read_ok=False``.
    """
    if (version is None) != (version_source is None):
        raise ValueError(
            f"version and version_source must be both set or both None for {path}"
        )
    identity = PathMetadata(brand, model_name, label, version, version_source)
    relative = relative_to_root(path, dataset_root)
    meta_path = relative.as_posix() if relative is not None else str(path)
    file_size: int | None = None
    try:
        file_size = path.stat().st_size
        read = _read_stats(path, config.max_bytes, file_size)
        if not read.size:
            raise ValueError("empty firmware")
        binwalk = _scan_binwalk(path, toolchain)
        document = DocumentBuilder(
            config.feature.max_strings, config.feature.max_doc_chars
        )
        scan = _StringScan(
            *_string_features(
                path, config, toolchain, document, detect_fs_type(binwalk[0])
            )
        )
    except (OSError, ValueError) as exc:
        return _build_error_result(path, config, identity, exc, meta_path, file_size)
    return _build_result(
        path, config, model, read, binwalk, scan, document, meta_path, identity
    )


def _build_error_result(
    path: Path,
    config: PipelineConfig,
    identity: PathMetadata,
    exc: Exception,
    meta_path: str | None = None,
    file_size: int | None = None,
) -> PipelineResult:
    """Mantém esquema dos metadados em falhas de leitura ou extração."""
    metadata = {
        "read_ok": False,
        "byte_len": 0,
        "bytes_used": 0,
        "file_size": file_size,
        "max_bytes": config.max_bytes,
        "truncated": False,
        "max_bytes_applied": True,
        "doc2vec_used": False,
        "error": str(exc),
        "binwalk_status": STATUS_NOT_RUN,
        "unpack_status": STATUS_NOT_RUN,
        "unpack_error": None,
        "strings_source": STATUS_NOT_RUN,
        "unpack_files_cut": 0,
        **_identity_metadata(path, meta_path or str(path), identity, False),
        **unavailable_filesystem().metadata,
    }
    return PipelineResult(None, {}, metadata, [])


def _process_path(
    path: Path,
    config: PipelineConfig,
    model: Doc2Vec | None,
    toolchain: Toolchain,
    dataset_root: Path | None,
) -> PipelineResult:
    """Processa um arquivo e preserva identidade mesmo em erro inesperado."""
    relative = relative_to_root(path, dataset_root)
    identity = (
        infer_brand_model_label_from_path(relative)
        if relative
        else PathMetadata(None, None, None, None, None)
    )
    try:
        return extract_features_from_path(
            path,
            config,
            model,
            toolchain,
            identity.brand,
            identity.model,
            identity.label,
            identity.version,
            identity.version_source,
            dataset_root,
        )
    except Exception as exc:
        LOGGER.warning("Failed to extract features for %s: %s", path, exc)
        meta_path = relative.as_posix() if relative else None
        return _build_error_result(path, config, identity, exc, meta_path)


_WORKER_CONFIG: PipelineConfig | None = None
_WORKER_MODEL: Doc2Vec | None = None
_WORKER_TOOLCHAIN: Toolchain | None = None
_WORKER_ROOT: Path | None = None


def _init_worker(
    config: PipelineConfig, toolchain: Toolchain, dataset_root: Path | None
) -> None:
    """Carrega modelo uma vez por worker e disponibiliza ferramentas."""
    global _WORKER_CONFIG, _WORKER_MODEL, _WORKER_TOOLCHAIN, _WORKER_ROOT
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    _WORKER_CONFIG, _WORKER_TOOLCHAIN, _WORKER_ROOT = config, toolchain, dataset_root
    _WORKER_MODEL = load_doc2vec_model(config.doc2vec_model_path)


def _process_path_in_worker(path: Path) -> PipelineResult:
    """Processa arquivo com recursos inicializados no worker."""
    assert _WORKER_CONFIG is not None and _WORKER_TOOLCHAIN is not None
    return _process_path(
        path, _WORKER_CONFIG, _WORKER_MODEL, _WORKER_TOOLCHAIN, _WORKER_ROOT
    )


def _log_filesystem_summary(results: list[PipelineResult]) -> None:
    """Registra os totais de filesystems válidos e ELF processados no lote."""
    valid = [row for row in results if row.metadata["fs_status"] == STATUS_OK]
    unique = sum(cast(int, row.features["unpacked_n_elf"]) for row in valid)
    malformed = sum(row.metadata["fs_elf_malformed"] for row in valid)
    LOGGER.info(
        "Features do filesystem: %d/%d firmwares com fs_status=ok; "
        "ELF únicos=%d, lidos=%d, malformados=%d",
        len(valid),
        len(results),
        unique,
        unique - malformed,
        malformed,
    )


def extract_features_batch(
    paths: Iterable[Path],
    config: PipelineConfig,
    toolchain: Toolchain,
    max_workers: int | None = None,
    dataset_root: Path | None = None,
) -> list[PipelineResult]:
    """Distribui extração em processos mantendo a ordem de entrada."""
    path_list = list(paths)
    if not path_list:
        return []
    workers = max(
        1,
        (
            max_workers
            if max_workers is not None
            else min(len(path_list), os.cpu_count() or 1)
        ),
    )
    if workers == 1:
        model = load_doc2vec_model(config.doc2vec_model_path)
        results = [
            _process_path(path, config, model, toolchain, dataset_root)
            for path in path_list
        ]
    else:
        pending: list[PipelineResult | None] = [None] * len(path_list)
        with ProcessPoolExecutor(
            max_workers=workers,
            initializer=_init_worker,
            initargs=(config, toolchain, dataset_root),
        ) as executor:
            futures = {
                executor.submit(_process_path_in_worker, path): index
                for index, path in enumerate(path_list)
            }
            for future in as_completed(futures):
                pending[futures[future]] = future.result()
        results = cast(list[PipelineResult], pending)
    _log_filesystem_summary(results)
    counts: dict[str, int] = {}
    for result in results:
        status = result.metadata["unpack_status"]
        counts[status] = counts.get(status, 0) + 1
    LOGGER.info("Status do unpack: %s", dict(sorted(counts.items())))
    return results
