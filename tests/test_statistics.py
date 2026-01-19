import math

from src.features.statistics import byte_mean, compress_ratio, shannon_entropy


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
