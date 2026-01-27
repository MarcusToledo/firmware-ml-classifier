from __future__ import annotations

import logging
import zlib

import numpy as np

LOGGER = logging.getLogger(__name__)


def shannon_entropy(data: bytes) -> float:
    """Calcula a entropia de Shannon (bits) da distribuicao de bytes.

    Retorna 0.0 para entrada vazia.
    """
    if not data:
        return 0.0
    arr = np.frombuffer(data, dtype=np.uint8)
    counts = np.bincount(arr, minlength=256)
    probs = counts[counts > 0].astype(np.float64) / arr.size
    entropy = -(probs * np.log2(probs)).sum()
    return float(entropy)


def byte_mean(data: bytes) -> float:
    """Calcula a media aritmetica dos valores de bytes (0-255).

    Retorna 0.0 para entrada vazia.
    """
    if not data:
        return 0.0
    arr = np.frombuffer(data, dtype=np.uint8)
    return float(arr.mean(dtype=np.float64))


def compress_ratio(data: bytes, level: int = 9) -> float:
    """Calcula a razao tamanho_comprimido/tamanho_original com zlib.

    Retorna 1.0 para entrada vazia. Normaliza level para 9 se fora do
    intervalo 0-9.
    """
    if not data:
        return 1.0
    if level < 0 or level > 9:
        LOGGER.warning("Invalid zlib level %s; defaulting to 9", level)
        level = 9
    compressed = zlib.compress(data, level=level)
    return float(len(compressed) / len(data))
