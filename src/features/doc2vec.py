from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Iterable, List, Sequence, Tuple

import numpy as np
from gensim.models import Doc2Vec
from gensim.models.doc2vec import TaggedDocument


@dataclass(frozen=True)
class Doc2VecConfig:
    vector_size: int = 100
    window: int = 5
    epochs: int = 20
    min_count: int = 2
    seed: int = 42
    workers: int = 1
    dm: int = 1
    alpha: float = 0.025
    min_alpha: float = 0.0001


def build_corpus(documents: Iterable[Tuple[str, Sequence[str]]]) -> List[TaggedDocument]:
    """Converte pares (doc_id, tokens) em TaggedDocument para treino."""
    return [
        TaggedDocument(words=list(doc_tokens), tags=[doc_id])
        for doc_id, doc_tokens in documents
    ]


def train_doc2vec(corpus: List[TaggedDocument], config: Doc2VecConfig) -> Doc2Vec:
    """Train a Doc2Vec model from a tokenized corpus."""
    if config.workers != 1:
        raise ValueError("workers must be 1 for reproducibility")
    model = Doc2Vec(
        vector_size=config.vector_size,
        window=config.window,
        min_count=config.min_count,
        epochs=config.epochs,
        seed=config.seed,
        workers=config.workers,
        dm=config.dm,
        alpha=config.alpha,
        min_alpha=config.min_alpha,
    )
    model.build_vocab(corpus)
    model.train(corpus, total_examples=model.corpus_count, epochs=model.epochs)
    return model


def infer_embedding(model: Doc2Vec, tokens: Sequence[str], config: Doc2VecConfig) -> np.ndarray:
    """Infer an embedding for a tokenized document."""
    if not tokens:
        return np.zeros(config.vector_size, dtype=np.float32)
    set_global_seed(config.seed)
    return model.infer_vector(
        list(tokens),
        epochs=config.epochs,
        alpha=config.alpha,
        min_alpha=config.min_alpha,
    )


def set_global_seed(seed: int) -> None:
    """Set random seeds for reproducibility."""
    random.seed(seed)
    np.random.seed(seed)


def save_doc2vec(model: Doc2Vec, path: str) -> None:
    """Serialize a Doc2Vec model."""
    model.save(path)


def load_doc2vec(path: str) -> Doc2Vec:
    """Load a serialized Doc2Vec model."""
    model = Doc2Vec.load(path)
    return model  # type: ignore[return-value, no-any-return, assignment]
