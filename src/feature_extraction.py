from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np
from gensim.models import Doc2Vec

from .features.doc2vec import Doc2VecConfig, infer_embedding
from .features.statistics import byte_mean, compress_ratio, shannon_entropy
from .features.strings import (
    extract_ascii_strings,
    limit_strings,
    strings_to_document,
    tokenize_document,
)


@dataclass(frozen=True)
class FeatureConfig:
    min_string_len: int = 4
    max_string_len: int = 1024
    max_strings: int = 2000
    max_doc_chars: int = 200000
    doc2vec: Doc2VecConfig = Doc2VecConfig()


@dataclass(frozen=True)
class Stats:
    entropy: float
    byte_mean: float
    compress_ratio: float


@dataclass(frozen=True)
class FeatureVector:
    stats: Stats
    embedding: np.ndarray
    byte_len: int
    truncated: bool


def extract_features(
    data: bytes,
    config: FeatureConfig,
    model: Optional[Doc2Vec] = None,
) -> FeatureVector:
    """Extract statistical and Doc2Vec features from firmware bytes."""
    byte_len = len(data)
    stats = Stats(
        entropy=shannon_entropy(data),
        byte_mean=byte_mean(data),
        compress_ratio=compress_ratio(data),
    )
    raw_strings = extract_ascii_strings(
        data,
        min_len=config.min_string_len,
        max_string_len=config.max_string_len,
    )
    truncated_strings = len(raw_strings) > config.max_strings if config.max_strings > 0 else False
    strings = limit_strings(raw_strings, max_strings=config.max_strings)
    doc_full = "\n".join(strings)
    truncated_doc = config.max_doc_chars > 0 and len(doc_full) > config.max_doc_chars
    doc = strings_to_document(strings, max_doc_chars=config.max_doc_chars)
    tokens = tokenize_document(doc)
    if model is None:
        embedding = np.zeros(config.doc2vec.vector_size, dtype=np.float32)
    else:
        embedding = infer_embedding(model, tokens, config.doc2vec)
    return FeatureVector(
        stats=stats,
        embedding=embedding,
        byte_len=byte_len,
        truncated=truncated_strings or truncated_doc,
    )


def combine_features(feature_vector: FeatureVector) -> dict[str, float]:
    """Combine stats and embedding into a flat feature mapping."""
    features: dict[str, float] = {
        "entropy": feature_vector.stats.entropy,
        "byte_mean": feature_vector.stats.byte_mean,
        "compress_ratio": feature_vector.stats.compress_ratio,
    }
    for idx, value in enumerate(feature_vector.embedding.tolist()):
        features[f"doc2vec_{idx}"] = float(value)
    return features
