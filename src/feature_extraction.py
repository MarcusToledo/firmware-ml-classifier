"""Combina estatísticas incrementais e embedding opcional do firmware."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from gensim.models import Doc2Vec

from .features.doc2vec import Doc2VecConfig, infer_embedding
from .features.statistics import ByteStats
from .features.strings import (
    DEFAULT_MAX_STRING_LEN,
    DEFAULT_MIN_STRING_LEN,
    tokenize_document,
)

_DEFAULT_MAX_STRINGS = 2000
_DEFAULT_MAX_DOC_CHARS = 200000


@dataclass(frozen=True)
class FeatureConfig:
    """Define os limites do documento e os parâmetros de embedding."""

    min_string_len: int = DEFAULT_MIN_STRING_LEN
    max_string_len: int = DEFAULT_MAX_STRING_LEN
    max_strings: int = _DEFAULT_MAX_STRINGS
    max_doc_chars: int = _DEFAULT_MAX_DOC_CHARS
    doc2vec: Doc2VecConfig = Doc2VecConfig()


@dataclass(frozen=True)
class FeatureVector:
    """Guarda estatísticas e embedding sem reter bytes ou strings brutas."""

    stats: ByteStats
    embedding: np.ndarray
    byte_len: int
    truncated: bool


def extract_features(
    stats: ByteStats,
    document: str,
    truncated: bool,
    byte_len: int,
    config: FeatureConfig,
    model: Doc2Vec | None = None,
) -> FeatureVector:
    """Converte estatísticas e documento em vetor de features."""
    if model is None:
        embedding = np.zeros(config.doc2vec.vector_size, dtype=np.float32)
    else:
        embedding = infer_embedding(model, tokenize_document(document), config.doc2vec)
    return FeatureVector(stats, embedding, byte_len, truncated)


def combine_features(feature_vector: FeatureVector) -> dict[str, float]:
    """Converte FeatureVector em dicionário plano para DataFrame."""
    features: dict[str, float] = {
        "entropy": feature_vector.stats.entropy,
        "byte_mean": feature_vector.stats.byte_mean,
        "compress_ratio": feature_vector.stats.compress_ratio,
    }
    for index, value in enumerate(feature_vector.embedding):
        features[f"doc2vec_{index}"] = float(value)
    return features
