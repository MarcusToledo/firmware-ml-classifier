from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import yaml
from gensim.models import Doc2Vec

from src.feature_extraction import FeatureConfig, combine_features, extract_features
from src.features.doc2vec import Doc2VecConfig, load_doc2vec
from src.io_utils import normalize_binary, read_binary

LOGGER = logging.getLogger(__name__)


def infer_brand_model_label_from_path(
    path: Path,
) -> tuple[Optional[str], Optional[str], Optional[str]]:
    """Infer brand/model/label from a dataset/raw/<brand>/<model> path."""
    raw_index = None
    for idx, part in enumerate(path.parts):
        if part.lower() == "raw":
            raw_index = idx
            break
    if raw_index is None:
        return None, None, None
    if len(path.parts) <= raw_index + 2:
        return None, None, None
    brand = path.parts[raw_index + 1].strip()
    model = path.parts[raw_index + 2].strip()
    if not brand or not model:
        return None, None, None
    label = f"{brand}_{model}"
    return brand, model, label


@dataclass(frozen=True)
class PipelineConfig:
    max_bytes: Optional[int]
    feature: FeatureConfig
    doc2vec: Doc2VecConfig
    doc2vec_model_path: Optional[Path]


@dataclass(frozen=True)
class PipelineResult:
    firmware_id: Optional[str]
    features: Dict[str, float]
    metadata: Dict[str, Any]


def apply_overrides(config: Dict[str, Any], overrides: Dict[str, Any]) -> Dict[str, Any]:
    """Apply dot-path overrides to a config dict."""
    updated = dict(config)
    for key, value in overrides.items():
        cursor = updated
        parts = key.split(".")
        for part in parts[:-1]:
            cursor = cursor.setdefault(part, {})
        cursor[parts[-1]] = value
    return updated


def load_pipeline_config(path: Path, overrides: Dict[str, Any]) -> PipelineConfig:
    """Load pipeline configuration from YAML and apply overrides."""
    raw: Dict[str, Any] = {}
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
    max_bytes = merged.get("max_bytes")

    return PipelineConfig(
        max_bytes=None if max_bytes in (None, "null") else int(max_bytes),
        feature=feature,
        doc2vec=feature.doc2vec,
        doc2vec_model_path=Path(model_path) if model_path else None,
    )


def load_doc2vec_model(path: Optional[Path]) -> Optional[Doc2Vec]:
    """Load a Doc2Vec model if available."""
    if path is None:
        LOGGER.warning("Doc2Vec model path not provided; embeddings will be zero")
        return None
    if not path.exists():
        LOGGER.warning("Doc2Vec model not found at %s; embeddings will be zero", path)
        return None
    return load_doc2vec(str(path))


def extract_features_from_path(
    path: Path,
    config: PipelineConfig,
    model: Optional[Doc2Vec],
    vendor: Optional[str] = None,
) -> PipelineResult:
    """Extract features for a single firmware path."""
    error: Optional[str] = None
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
    features = combine_features(feature_vector)

    metadata = {
        "read_ok": read_ok,
        "byte_len": len(data),
        "truncated": feature_vector.truncated,
        "max_bytes_applied": config.max_bytes is not None,
        "doc2vec_used": model is not None and read_ok,
        "error": error,
        "path": str(path),
        "vendor": vendor,
    }

    return PipelineResult(
        firmware_id=firmware_id,
        features=features,
        metadata=metadata,
    )


def extract_features_batch(
    paths: Iterable[Path],
    config: PipelineConfig,
) -> List[PipelineResult]:
    """Extract features for a batch of firmware paths."""
    results: List[PipelineResult] = []
    model = load_doc2vec_model(config.doc2vec_model_path)
    for path in paths:
        try:
            vendor = infer_vendor_from_path(path)
            result = extract_features_from_path(path, config, model, vendor=vendor)
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
                        "truncated": False,
                        "max_bytes_applied": config.max_bytes is not None,
                        "doc2vec_used": False,
                        "error": str(exc),
                        "path": str(path),
                        "vendor": infer_vendor_from_path(path),
                    },
                )
            )
    return results
