from pathlib import Path
from unittest.mock import patch

from pipeline.feature_extraction import (
    extract_features_batch,
    extract_features_from_path,
    load_pipeline_config,
)


def test_extract_features_from_path_valid_file(tmp_path: Path) -> None:
    firmware_path = tmp_path / "firmware.bin"
    firmware_path.write_bytes(b"firmware-data")

    config = load_pipeline_config(tmp_path / "missing.yaml", overrides={})

    result = extract_features_from_path(
        firmware_path,
        config,
        model=None,
    )

    assert result.metadata["read_ok"] is True
    assert result.metadata["byte_len"] == len(b"firmware-data")
    assert result.metadata["bytes_used"] == len(b"firmware-data")
    assert result.metadata["max_bytes"] is None
    assert result.firmware_id is not None
    assert result.metadata["doc2vec_used"] is False
    assert result.metadata["brand"] is None
    assert result.metadata["model"] is None
    assert result.metadata["label"] is None


def test_extract_features_from_path_empty_file(tmp_path: Path) -> None:
    firmware_path = tmp_path / "empty.bin"
    firmware_path.write_bytes(b"")

    config = load_pipeline_config(tmp_path / "missing.yaml", overrides={})

    result = extract_features_from_path(
        firmware_path,
        config,
        model=None,
    )

    assert result.metadata["read_ok"] is False
    assert result.firmware_id is None
    assert result.metadata["error"] is not None
    assert result.metadata["brand"] is None
    assert result.metadata["model"] is None
    assert result.metadata["label"] is None


def test_extract_features_from_path_max_bytes_zero(tmp_path: Path) -> None:
    firmware_path = tmp_path / "firmware.bin"
    firmware_path.write_bytes(b"abc")

    config_path = tmp_path / "config.yaml"
    config_path.write_text("max_bytes: 0\n")

    config = load_pipeline_config(config_path, overrides={})

    result = extract_features_from_path(
        firmware_path,
        config,
        model=None,
    )

    assert result.metadata["read_ok"] is False
    assert result.metadata["byte_len"] == 0
    assert result.metadata["bytes_used"] == 0
    assert result.metadata["max_bytes"] == 0
    assert result.metadata["brand"] is None
    assert result.metadata["model"] is None
    assert result.metadata["label"] is None


def test_extract_features_batch_continues_on_error(tmp_path: Path) -> None:
    good_path = tmp_path / "good.bin"
    good_path.write_bytes(b"good")
    missing_path = tmp_path / "missing.bin"

    config = load_pipeline_config(tmp_path / "missing.yaml", overrides={})

    results = extract_features_batch([good_path, missing_path], config)

    assert len(results) == 2
    assert results[0].metadata["read_ok"] is True
    assert results[0].metadata["brand"] is None
    assert results[0].metadata["model"] is None
    assert results[0].metadata["label"] is None
    assert results[1].metadata["read_ok"] is False
    assert results[1].metadata["brand"] is None
    assert results[1].metadata["model"] is None
    assert results[1].metadata["label"] is None
    assert results[1].firmware_id is None


def test_extract_features_includes_binwalk_keys(tmp_path: Path) -> None:
    """Binwalk feature keys are always present even without binwalk3."""
    firmware_path = tmp_path / "firmware.bin"
    firmware_path.write_bytes(b"firmware-data")

    config = load_pipeline_config(tmp_path / "missing.yaml", overrides={})
    result = extract_features_from_path(firmware_path, config, model=None)

    expected_keys = {
        "n_filesystems",
        "n_crypto_signatures",
        "has_encrypted_sections",
        "fs_type",
        "compression_type",
        "entropy_variance_across_sections",
    }
    assert expected_keys.issubset(result.features.keys())


def test_extract_features_includes_string_pattern_keys(tmp_path: Path) -> None:
    """String pattern feature keys are always present after extraction."""
    firmware_path = tmp_path / "firmware.bin"
    firmware_path.write_bytes(b"firmware-data")

    config = load_pipeline_config(tmp_path / "missing.yaml", overrides={})
    result = extract_features_from_path(firmware_path, config, model=None)

    expected_keys = {
        "count_hardcoded_passwords",
        "count_hardcoded_ips",
        "has_telnetd",
        "has_debug_account",
        "has_outdated_libssl",
        "has_outdated_busybox",
        "has_outdated_dropbear",
        "count_urls",
        "count_api_tokens",
    }
    assert expected_keys.issubset(result.features.keys())


def test_extract_features_from_path_calls_extract_ascii_strings_once(
    tmp_path: Path, monkeypatch
) -> None:
    """Regressao: extract_ascii_strings deve rodar 1x por arquivo, nao 2x.

    Antes da correcao, o doc2vec (via extract_features) e o scan_strings
    (string_patterns) chamavam extract_ascii_strings separadamente sobre os
    mesmos bytes, dobrando o custo dessa etapa em firmwares grandes.
    """
    import src.feature_extraction as fe

    firmware_path = tmp_path / "firmware.bin"
    firmware_path.write_bytes(b"firmware-data-with-strings")

    config = load_pipeline_config(tmp_path / "missing.yaml", overrides={})

    call_count = 0
    original = fe.extract_ascii_strings

    def counting_wrapper(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(fe, "extract_ascii_strings", counting_wrapper)

    extract_features_from_path(firmware_path, config, model=None)

    assert call_count == 1


def test_extract_features_batch_empty_list_returns_empty(tmp_path: Path) -> None:
    config = load_pipeline_config(tmp_path / "missing.yaml", overrides={})

    assert extract_features_batch([], config) == []


def test_extract_features_batch_sequential_mode(tmp_path: Path) -> None:
    """max_workers=1 forca o caminho sequencial (sem process pool)."""
    good_path = tmp_path / "good.bin"
    good_path.write_bytes(b"good")

    config = load_pipeline_config(tmp_path / "missing.yaml", overrides={})

    results = extract_features_batch([good_path], config, max_workers=1)

    assert len(results) == 1
    assert results[0].metadata["read_ok"] is True


def test_extract_features_batch_preserves_order_with_multiple_workers(
    tmp_path: Path,
) -> None:
    """Com workers>1, a ordem dos resultados deve seguir a ordem de entrada,
    independente da ordem em que os processos terminam."""
    paths = []
    for i in range(4):
        firmware_path = tmp_path / f"firmware_{i}.bin"
        firmware_path.write_bytes(f"firmware-{i}".encode())
        paths.append(firmware_path)

    config = load_pipeline_config(tmp_path / "missing.yaml", overrides={})

    results = extract_features_batch(paths, config, max_workers=2)

    assert len(results) == 4
    for path, result in zip(paths, results):
        assert result.metadata["path"] == str(path)
        assert result.metadata["read_ok"] is True


def test_extract_features_with_mocked_binwalk(tmp_path: Path) -> None:
    """Binwalk features are populated when binwalk CLI returns results."""
    import subprocess

    firmware_path = tmp_path / "firmware.bin"
    firmware_path.write_bytes(b"firmware-data")

    fake_stdout = (
        "DECIMAL       HEXADECIMAL     DESCRIPTION\n"
        "--------------------------------------------------------------------------------\n"
        "0             0x0             Squashfs filesystem, little endian\n"
        "64            0x40            gzip compressed data, from Unix\n"
        "128           0x80            AES encrypted block\n"
    )
    fake_completed = subprocess.CompletedProcess(
        args=[], returncode=0, stdout=fake_stdout, stderr=""
    )

    config = load_pipeline_config(tmp_path / "missing.yaml", overrides={})

    with patch("shutil.which", return_value="/usr/bin/binwalk"), patch(
        "subprocess.run", return_value=fake_completed
    ):
        result = extract_features_from_path(firmware_path, config, model=None)

    assert result.features["n_filesystems"] == 1
    assert result.features["n_crypto_signatures"] == 1
    assert result.features["has_encrypted_sections"] is True
    assert result.features["fs_type"] == "squashfs"
    assert result.features["compression_type"] == "gzip"
