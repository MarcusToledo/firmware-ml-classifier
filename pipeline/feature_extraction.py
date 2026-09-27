"""Extrai features estatísticas, strings e estrutura de firmware em lote."""

from __future__ import annotations

import hashlib
import logging
import os
import re
import subprocess
from collections.abc import Iterable
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Any, NamedTuple, cast

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
from src.features.statistics import StreamingStats
from src.features.strings import DocumentBuilder, iter_ascii_strings
from src.features.unpack import (
    STATUS_NOT_RUN,
    STATUS_OK,
    STATUS_TIME,
    Toolchain,
    UnpackLimits,
    iter_extracted_files,
    unpack_firmware,
)
from src.io_utils import iter_file_chunks

FeatureValue = float | int | bool | str | None
DEFAULT_MAX_BYTES = 268_435_456
VERSION_SOURCE_DIRECTORY = "directory"
VERSION_SOURCE_FILENAME = "filename"
THIRD_PARTY_DDWRT = "dd-wrt"
STRINGS_FILESYSTEM = "filesystem"
STRINGS_BLOB = "blob"
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
    if len(relative_path.parts) != 3 or relative_path.is_absolute():
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
        if parsed <= 0 or (integer and str(value) != str(parsed)):
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


def _load_unpack(raw: dict[str, Any], path: Path | None) -> UnpackLimits:
    """Carrega limites de desempacotamento com padrões explícitos."""
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
    return FeatureConfig(
        min_string_len=int(raw.get("min_string_len", 4)),
        max_string_len=int(raw.get("max_single_string_len", 1024)),
        max_strings=int(raw.get("max_strings", 2000)),
        max_doc_chars=int(raw.get("max_doc_chars", 200000)),
        doc2vec=Doc2VecConfig(
            vector_size=int(doc.get("vector_size", 100)),
            window=int(doc.get("window", 5)),
            epochs=int(doc.get("epochs", 20)),
            min_count=int(doc.get("min_count", 2)),
            seed=int(doc.get("seed", 42)),
            workers=int(doc.get("workers", 1)),
            dm=int(doc.get("dm", 1)),
            alpha=float(doc.get("alpha", 0.025)),
            min_alpha=float(doc.get("min_alpha", 0.0001)),
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


def _scan_binwalk(path: Path, toolchain: Toolchain) -> tuple[list[str], str]:
    """Varre assinaturas e expõe erro ou timeout sem achados espúrios."""
    try:
        result = subprocess.run(
            [toolchain.binwalk, str(path)],
            capture_output=True,
            text=True,
            timeout=60,
            env=toolchain.env,
            check=False,
        )
    except subprocess.TimeoutExpired:
        LOGGER.warning("binwalk timeout para %s", path)
        return [], "timeout"
    except OSError as exc:
        LOGGER.warning("binwalk erro para %s: código indisponível: %s", path, exc)
        return [], "erro"
    if result.returncode != 0:
        LOGGER.warning("binwalk erro para %s: código %d", path, result.returncode)
        return [], "erro"
    descriptions = []
    for line in result.stdout.splitlines():
        parts = line.split(None, 2)
        if len(parts) == 3 and parts[0].isdigit():
            descriptions.append(parts[2].strip())
    return descriptions, "ok"


def _scan_string_stream(
    strings: Iterable[str], document: DocumentBuilder, batch_size: int = 10_000
) -> tuple[list[SecurityFinding], bool]:
    """Varre todas as strings em lotes sem limitar detectores pelo documento."""
    findings: list[SecurityFinding] = []
    batch: list[str] = []
    ddwrt = False
    for value in strings:
        document.add(value)
        ddwrt |= "DD-WRT" in value
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


def _read_stats(path: Path, limit: int) -> tuple[str, Any, int]:
    """Calcula SHA256 e estatísticas em uma passada sem armazenar o arquivo."""
    digest = hashlib.sha256()
    streaming = StreamingStats()
    size = 0
    for chunk in iter_file_chunks(path, limit):
        digest.update(chunk)
        streaming.update(chunk)
        size += len(chunk)
    return digest.hexdigest(), streaming.result(), size


def _string_features(
    path: Path, config: PipelineConfig, toolchain: Toolchain, document: DocumentBuilder
) -> tuple[list[SecurityFinding], bool, str, str, int]:
    """Prefere filesystem; faz fallback bruto exceto após limite de tempo."""
    with unpack_firmware(path, config.unpack, toolchain) as unpack:
        if unpack.status == STATUS_OK:
            assert unpack.root is not None
            findings, banner, cut = _scan_extracted(unpack.root, config, document)
            return findings, banner, unpack.status, STRINGS_FILESYSTEM, cut
        if unpack.status == STATUS_TIME:
            return [], False, unpack.status, STATUS_NOT_RUN, 0
        strings = iter_ascii_strings(
            iter_file_chunks(path, config.max_bytes),
            config.feature.min_string_len,
            config.feature.max_string_len,
        )
        findings, banner = _scan_string_stream(strings, document)
        return findings, banner, unpack.status, STRINGS_BLOB, 0


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
    """Extrai um firmware em streaming e preserva estado de cada etapa."""
    if (version is None) != (version_source is None):
        raise ValueError(
            f"version and version_source must be both set or both None for {path}"
        )
    relative = relative_to_root(path, dataset_root)
    meta_path = relative.as_posix() if relative is not None else str(path)
    try:
        file_size = path.stat().st_size
        firmware_id, stats, size = _read_stats(path, config.max_bytes)
    except OSError as exc:
        return _build_error_result(
            path,
            config,
            brand,
            model_name,
            label,
            version,
            version_source,
            exc,
            meta_path,
        )
    if not size:
        return _build_error_result(
            path,
            config,
            brand,
            model_name,
            label,
            version,
            version_source,
            ValueError("empty firmware"),
            meta_path,
            file_size,
        )
    descriptions, binwalk_status = _scan_binwalk(path, toolchain)
    document = DocumentBuilder(config.feature.max_strings, config.feature.max_doc_chars)
    try:
        findings, banner, unpack_status, strings_source, cut = _string_features(
            path, config, toolchain, document
        )
    except OSError as exc:
        return _build_error_result(
            path,
            config,
            brand,
            model_name,
            label,
            version,
            version_source,
            exc,
            meta_path,
            file_size,
        )
    vector = extract_features(
        stats, document.document(), document.truncated, size, config.feature, model
    )
    features: dict[str, FeatureValue] = {
        **combine_features(vector),
        **_structural_features(descriptions, stats.entropy_variance_across_sections),
        **findings_to_counts(findings),
    }
    findings.extend(find_crypto_signatures(descriptions))
    findings.extend(find_encrypted_sections(descriptions))
    metadata = {
        "read_ok": True,
        "byte_len": size,
        "bytes_used": size,
        "file_size": file_size,
        "max_bytes": config.max_bytes,
        "truncated": vector.truncated,
        "max_bytes_applied": True,
        "doc2vec_used": model is not None,
        "error": None,
        "path": meta_path,
        "brand": brand,
        "model": model_name,
        "label": label,
        "version": version,
        "version_source": version_source,
        "binwalk_status": binwalk_status,
        "unpack_status": unpack_status,
        "strings_source": strings_source,
        "unpack_files_cut": cut,
        "third_party": (
            THIRD_PARTY_DDWRT if is_third_party_name(path.name) or banner else None
        ),
    }
    return PipelineResult(firmware_id, features, metadata, findings)


def _build_error_result(
    path: Path,
    config: PipelineConfig,
    brand: str | None,
    model_name: str | None,
    label: str | None,
    version: str | None,
    version_source: str | None,
    exc: Exception,
    meta_path: str | None = None,
    file_size: int | None = None,
) -> PipelineResult:
    """Mantém esquema dos metadados em falhas de leitura ou extração."""
    return PipelineResult(
        None,
        {},
        {
            "read_ok": False,
            "byte_len": 0,
            "bytes_used": 0,
            "file_size": file_size,
            "max_bytes": config.max_bytes,
            "truncated": False,
            "max_bytes_applied": True,
            "doc2vec_used": False,
            "error": str(exc),
            "path": meta_path or str(path),
            "brand": brand,
            "model": model_name,
            "label": label,
            "version": version,
            "version_source": version_source,
            "binwalk_status": STATUS_NOT_RUN,
            "unpack_status": STATUS_NOT_RUN,
            "strings_source": STATUS_NOT_RUN,
            "unpack_files_cut": 0,
            "third_party": (
                THIRD_PARTY_DDWRT if is_third_party_name(path.name) else None
            ),
        },
        [],
    )


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
        return _build_error_result(
            path,
            config,
            identity.brand,
            identity.model,
            identity.label,
            identity.version,
            identity.version_source,
            exc,
            relative.as_posix() if relative else None,
        )


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
        return [
            _process_path(path, config, model, toolchain, dataset_root)
            for path in path_list
        ]
    results: list[PipelineResult | None] = [None] * len(path_list)
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
            results[futures[future]] = future.result()
    return cast(list[PipelineResult], results)
