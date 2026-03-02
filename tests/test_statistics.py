import math
import os

from src.features.statistics import (
    BLOCK_SIZE,
    byte_mean,
    compress_ratio,
    entropy_variance_across_sections,
    shannon_entropy,
)


def test_entropy_empty_returns_zero() -> None:
    assert shannon_entropy(b"") == 0.0


def test_byte_mean_empty_returns_zero() -> None:
    assert byte_mean(b"") == 0.0


def test_compress_ratio_empty_returns_one() -> None:
    assert compress_ratio(b"") == 1.0


def test_compress_ratio_level_affects_output() -> None:
    payload = b"A" * 100
    ratio_default = compress_ratio(payload)
    ratio_fast = compress_ratio(payload, level=1)

    assert ratio_default <= ratio_fast


def test_entropy_known_distribution() -> None:
    payload = b"\x00\x01"
    assert math.isclose(shannon_entropy(payload), 1.0, rel_tol=1e-6)


# -- entropy_variance_across_sections ----------------------------------------


def test_entropy_variance_empty() -> None:
    assert entropy_variance_across_sections(b"") == 0.0


def test_entropy_variance_too_small() -> None:
    # Less than 2 blocks → 0.0
    assert entropy_variance_across_sections(b"\x00" * BLOCK_SIZE) == 0.0


def test_entropy_variance_uniform_blocks() -> None:
    # Two identical blocks → variance should be 0.0
    data = b"\x00" * (BLOCK_SIZE * 2)
    assert entropy_variance_across_sections(data) == 0.0


def test_entropy_variance_different_blocks() -> None:
    # One low-entropy block + one high-entropy block → positive variance
    low_entropy = b"\x00" * BLOCK_SIZE
    high_entropy = os.urandom(BLOCK_SIZE)
    data = low_entropy + high_entropy
    variance = entropy_variance_across_sections(data)
    assert variance > 0.0
