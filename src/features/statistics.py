"""Calcula estatísticas de bytes em memória limitada."""

from __future__ import annotations

import zlib
from dataclasses import dataclass
from typing import cast

import numpy as np

BLOCK_SIZE = 65536
_BYTE_VALUES = 256
_COMPRESSION_LEVEL = 9
_MIN_VARIANCE_SECTIONS = 2


def _byte_histogram(data: bytes | bytearray) -> np.ndarray:
    """Conta a frequência de cada byte sem copiar os dados."""
    counts = np.bincount(np.frombuffer(data, dtype=np.uint8), minlength=_BYTE_VALUES)
    return cast(np.ndarray, counts)


def shannon_entropy(data: bytes) -> float:
    """Calcula a entropia de Shannon dos bytes, inclusive entrada vazia."""
    if not data:
        return 0.0
    counts = _byte_histogram(data)
    return _entropy_counts(counts, len(data))


def _entropy_counts(counts: np.ndarray, size: int) -> float:
    """Calcula a entropia a partir de um histograma acumulado."""
    probabilities = counts[counts > 0].astype(np.float64) / size
    return float(-(probabilities * np.log2(probabilities)).sum())


@dataclass(frozen=True)
class ByteStats:
    """Guarda estatísticas calculadas do prefixo lido do firmware."""

    entropy: float
    byte_mean: float
    compress_ratio: float
    entropy_variance_across_sections: float


class StreamingStats:
    """Acumula histograma, compressão e entropias por bloco alinhado."""

    def __init__(self) -> None:
        """Inicializa acumuladores de tamanho limitado."""
        self._counts = np.zeros(_BYTE_VALUES, dtype=np.int64)
        self._size = 0
        self._compressed = 0
        self._compressor = zlib.compressobj(level=_COMPRESSION_LEVEL)
        self._section = bytearray()
        self._entropies: list[float] = []

    def update(self, chunk: bytes) -> None:
        """Inclui um bloco arbitrário sem reter todos os bytes lidos."""
        if not chunk:
            return
        self._counts += _byte_histogram(chunk)
        self._size += len(chunk)
        self._compressed += len(self._compressor.compress(chunk))
        view = memoryview(chunk)
        while view:
            length = min(BLOCK_SIZE - len(self._section), len(view))
            self._section.extend(view[:length])
            view = view[length:]
            if len(self._section) == BLOCK_SIZE:
                self._entropies.append(shannon_entropy(self._section))
                self._section.clear()

    def result(self) -> ByteStats:
        """Finaliza a compressão e devolve estatísticas do prefixo lido."""
        self._compressed += len(self._compressor.flush())
        variance = (
            float(np.var(self._entropies))
            if len(self._entropies) >= _MIN_VARIANCE_SECTIONS
            else 0.0
        )
        return ByteStats(
            entropy=_entropy_counts(self._counts, self._size) if self._size else 0.0,
            byte_mean=(
                float(np.dot(np.arange(_BYTE_VALUES), self._counts) / self._size)
                if self._size
                else 0.0
            ),
            compress_ratio=self._compressed / self._size if self._size else 1.0,
            entropy_variance_across_sections=variance,
        )
