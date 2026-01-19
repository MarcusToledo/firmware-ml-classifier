from pathlib import Path

import pytest

from src.io_utils import normalize_binary, read_binary


def test_read_binary_valid_path_reads_bytes(tmp_path: Path) -> None:
    payload = b"firmware"
    path = tmp_path / "firmware.bin"
    path.write_bytes(payload)

    assert read_binary(path) == payload


def test_read_binary_missing_file_returns_empty_and_logs_warning(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    missing = tmp_path / "missing.bin"

    with caplog.at_level("WARNING"):
        result = read_binary(missing)

    assert result == b""
    assert any("Failed to read binary" in record.message for record in caplog.records)


def test_read_binary_max_bytes_zero_returns_empty(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    path = tmp_path / "firmware.bin"
    path.write_bytes(b"abc")

    with caplog.at_level("WARNING"):
        result = read_binary(path, max_bytes=0)

    assert result == b""
    assert any("max_bytes" in record.message for record in caplog.records)


def test_normalize_binary_bytes_passthrough() -> None:
    payload = b"firmware"

    assert normalize_binary(payload) == payload


def test_normalize_binary_invalid_returns_empty(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level("WARNING"):
        result = normalize_binary("invalid")  # type: ignore[arg-type]

    assert result == b""
    assert any(
        "normalize_binary received non-bytes input" in record.message
        for record in caplog.records
    )
