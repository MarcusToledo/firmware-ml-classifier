from __future__ import annotations

import hashlib
import logging
import re
import shutil
import subprocess
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Union, cast

import yaml
from gensim.models import Doc2Vec

from src.feature_extraction import FeatureConfig, combine_features, extract_features
from src.features.binwalk import (
    count_crypto_signatures,
    count_filesystems,
    detect_compression_type,
    detect_fs_type,
    has_encrypted_sections,
)
from src.features.doc2vec import Doc2VecConfig, load_doc2vec
from src.features.statistics import entropy_variance_across_sections
from src.io_utils import normalize_binary, read_binary

FeatureValue = Union[float, int, bool, str, None]

LOGGER = logging.getLogger(__name__)

_VERSION_SUFFIX_RE = re.compile(r"^([a-z]+\d+[a-z]*)_\d+\.", re.IGNORECASE)


def _strip_version_suffix(model: str) -> str:
    """Strip firmware version suffix: 'NWA110AX_7.10(ABTG.4)C0' -> 'nwa110ax'."""
    m = _VERSION_SUFFIX_RE.match(model)
    return m.group(1).lower() if m else model.lower()


def infer_brand_model_label_from_path(
    path: Path,
) -> tuple[str | None, str | None, str | None]:
    """Extrai brand, model e label de */raw/<brand>/<model>/*.

    Retorna (None, None, None) quando o padrao nao casar.
    """
    raw_index = None
    for idx, part in enumerate(path.parts):
        if part.lower() == "raw":
            raw_index = idx
            break
    if raw_index is None:
        return None, None, None
    if len(path.parts) <= raw_index + 2:
        return None, None, None
    brand = path.parts[raw_index + 1].strip().lower()
    model = _strip_version_suffix(path.parts[raw_index + 2].strip())
    if not brand or not model:
        return None, None, None
    label = f"{brand}_{model}"
    return brand, model, label


@dataclass(frozen=True)
class PipelineConfig:
    max_bytes: int | None
    feature: FeatureConfig
    doc2vec: Doc2VecConfig
    doc2vec_model_path: Path | None


@dataclass(frozen=True)
class PipelineResult:
    firmware_id: str | None
    features: dict[str, FeatureValue]
    metadata: dict[str, Any]


def apply_overrides(
    config: dict[str, Any],
    overrides: dict[str, Any],
) -> dict[str, Any]:
    """Aplica overrides com dot-path em um dicionario de config."""
    updated = dict(config)
    for key, value in overrides.items():
        cursor = updated
        parts = key.split(".")
        for part in parts[:-1]:
            cursor = cursor.setdefault(part, {})
        cursor[parts[-1]] = value
    return updated


def load_pipeline_config(path: Path, overrides: dict[str, Any]) -> PipelineConfig:
    """Carrega YAML de configuracao e aplica overrides.

    Overrides usam dot-path (ex.: feature.max_strings=500).
    """
    raw: dict[str, Any] = {}
    if path.exists():
        raw = yaml.safe_load(path.read_text()) or {}
    merged = apply_overrides(raw, overrides)

    feature_raw = merged.get("feature", {})
    doc2vec_raw = merged.get("doc2vec", {})

    feature = FeatureConfig(
        min_string_len=int(feature_raw.get("min_string_len", 4)),
        max_string_len=int(feature_raw.get("max_single_string_len", 1024)),
        max_strings=int(feature_raw.get("max_strings", 2000)),
        max_doc_chars=int(feature_raw.get("max_doc_chars", 200000)),
        doc2vec=Doc2VecConfig(
            vector_size=int(doc2vec_raw.get("vector_size", 100)),
            window=int(doc2vec_raw.get("window", 5)),
            epochs=int(doc2vec_raw.get("epochs", 20)),
            min_count=int(doc2vec_raw.get("min_count", 2)),
            seed=int(doc2vec_raw.get("seed", 42)),
            workers=int(doc2vec_raw.get("workers", 1)),
            dm=int(doc2vec_raw.get("dm", 1)),
            alpha=float(doc2vec_raw.get("alpha", 0.025)),
            min_alpha=float(doc2vec_raw.get("min_alpha", 0.0001)),
        ),
    )

    model_path = doc2vec_raw.get("model_path")
    max_bytes_raw = merged.get("max_bytes")
    if max_bytes_raw in (None, "null"):
        max_bytes_value = None
    else:
        max_bytes_value = int(cast(Union[int, str], max_bytes_raw))

    return PipelineConfig(
        max_bytes=max_bytes_value,
        feature=feature,
        doc2vec=feature.doc2vec,
        doc2vec_model_path=Path(model_path) if model_path else None,
    )


def load_doc2vec_model(path: Path | None) -> Doc2Vec | None:
    """Carrega modelo Doc2Vec quando disponivel.

    Retorna None com warning se o path for None ou inexistente.
    """
    if path is None:
        LOGGER.warning("Doc2Vec model path not provided; embeddings will be zero")
        return None
    if not path.exists():
        LOGGER.warning("Doc2Vec model not found at %s; embeddings will be zero", path)
        return None
    return load_doc2vec(str(path))


def _extract_binwalk_descriptions(path: Path) -> list[str]:
    """Run binwalk signature scan and return description strings.

    Uses the binwalk CLI via subprocess. Returns an empty list when binwalk
    is not installed or the scan fails.
    """
    binwalk_bin = shutil.which("binwalk")
    if binwalk_bin is None:
        LOGGER.debug("binwalk not found in PATH; skipping structural analysis")
        return []
    try:
        result = subprocess.run(
            [binwalk_bin, str(path)],
            capture_output=True,
            text=True,
            timeout=60,
        )
        descriptions: list[str] = []
        for line in result.stdout.splitlines():
            parts = line.split(None, 2)
            if len(parts) == 3 and parts[0].isdigit():
                descriptions.append(parts[2].strip())
        return descriptions
    except Exception as exc:
        LOGGER.warning("binwalk scan failed for %s: %s", path, exc)
        return []


def extract_features_from_path(
    path: Path,
    config: PipelineConfig,
    model: Doc2Vec | None,
    brand: str | None = None,
    model_name: str | None = None,
    label: str | None = None,
) -> PipelineResult:
    """Extrai features e metadados de um firmware.

    Metadados incluem read_ok, error, truncated, doc2vec_used, brand,
    model e label. firmware_id e o SHA256 do conteudo lido.
    """
    error: str | None = None
    data = read_binary(path, max_bytes=config.max_bytes)
    data = normalize_binary(data)

    if config.max_bytes is not None and config.max_bytes <= 0:
        error = "max_bytes results in empty read"

    read_ok = error is None
    if read_ok and not data:
        error = "empty firmware"
        read_ok = False

    firmware_id = None
    if read_ok:
        firmware_id = hashlib.sha256(data).hexdigest()

    if not read_ok:
        LOGGER.warning("Failed to read firmware %s: %s", path, error)

    feature_vector = extract_features(data, config.feature, model)
    features: dict[str, FeatureValue] = {**combine_features(feature_vector)}

    # Binwalk structural features
    descriptions = _extract_binwalk_descriptions(path) if read_ok else []
    features["n_filesystems"] = count_filesystems(descriptions)
    features["n_crypto_signatures"] = count_crypto_signatures(descriptions)
    features["has_encrypted_sections"] = has_encrypted_sections(descriptions)
    features["fs_type"] = detect_fs_type(descriptions)
    features["compression_type"] = detect_compression_type(descriptions)
    features["entropy_variance_across_sections"] = (
        entropy_variance_across_sections(data) if read_ok else 0.0
    )

    metadata = {
        "read_ok": read_ok,
        "byte_len": len(data),
        "bytes_used": len(data),
        "max_bytes": config.max_bytes,
        "truncated": feature_vector.truncated,
        "max_bytes_applied": config.max_bytes is not None,
        "doc2vec_used": model is not None and read_ok,
        "error": error,
        "path": str(path),
        "brand": brand,
        "model": model_name,
        "label": label,
    }

    return PipelineResult(
        firmware_id=firmware_id,
        features=features,
        metadata=metadata,
    )


def extract_features_batch(
    paths: Iterable[Path],
    config: PipelineConfig,
) -> list[PipelineResult]:
    """Processa uma lista de paths com tolerancia a falhas.

    Retorna um resultado para cada path, inclusive em caso de erro.
    """
    results: list[PipelineResult] = []
    model = load_doc2vec_model(config.doc2vec_model_path)
    for path in paths:
        brand, model_name, label = infer_brand_model_label_from_path(path)
        try:
            result = extract_features_from_path(
                path,
                config,
                model,
                brand=brand,
                model_name=model_name,
                label=label,
            )
            results.append(result)
        except Exception as exc:  # pragma: no cover - defensive for batch safety
            LOGGER.warning("Failed to extract features for %s: %s", path, exc)
            results.append(
                PipelineResult(
                    firmware_id=None,
                    features={},
                    metadata={
                        "read_ok": False,
                        "byte_len": 0,
                        "bytes_used": 0,
                        "max_bytes": config.max_bytes,
                        "truncated": False,
                        "max_bytes_applied": config.max_bytes is not None,
                        "doc2vec_used": False,
                        "error": str(exc),
                        "path": str(path),
                        "brand": brand,
                        "model": model_name,
                        "label": label,
                    },
                )
            )
    return results
