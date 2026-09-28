"""Compara acumulador em blocos com cálculos independentes em memória."""

import zlib

import numpy as np
import pytest

from src.features.statistics import BLOCK_SIZE, StreamingStats, shannon_entropy

_BYTE_VALUES = 256
_COMPRESSION_LEVEL = 9


def test_empty_stats_keep_defined_values() -> None:
    """Mantém resultado definido para arquivo vazio."""
    result = StreamingStats().result()
    assert (
        result.entropy,
        result.byte_mean,
        result.compress_ratio,
        result.entropy_variance_across_sections,
    ) == (0.0, 0.0, 1.0, 0.0)


@pytest.mark.parametrize("chunk_size", [1, 4093, BLOCK_SIZE, BLOCK_SIZE + 1])
def test_streamed_statistics_match_full_reference(chunk_size: int) -> None:
    """Independe do tamanho dos pedaços, inclusive sobre bordas de 64 KiB."""
    data = (
        np.random.default_rng(42)
        .integers(0, _BYTE_VALUES, size=BLOCK_SIZE * 2 + 113, dtype=np.uint8)
        .tobytes()
    )
    stats = StreamingStats()
    for index in range(0, len(data), chunk_size):
        stats.update(data[index : index + chunk_size])
    result = stats.result()
    counts = np.bincount(np.frombuffer(data, dtype=np.uint8), minlength=_BYTE_VALUES)
    probabilities = counts[counts > 0] / len(data)
    expected_entropy = float(-(probabilities * np.log2(probabilities)).sum())
    section_entropies = [
        shannon_entropy(data[index : index + BLOCK_SIZE]) for index in (0, BLOCK_SIZE)
    ]
    assert result.entropy == pytest.approx(expected_entropy, rel=1e-12)
    assert result.byte_mean == pytest.approx(
        float(np.frombuffer(data, dtype=np.uint8).mean()), rel=1e-12
    )
    assert result.compress_ratio == len(zlib.compress(data, _COMPRESSION_LEVEL)) / len(
        data
    )
    assert result.entropy_variance_across_sections == pytest.approx(
        float(np.var(section_entropies)), rel=1e-12
    )
