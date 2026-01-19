from pathlib import Path

from pipeline.feature_extraction import (
    PipelineConfig,
    extract_features_batch,
    extract_features_from_path,
    load_pipeline_config,
)


def test_extract_features_from_path_valid_file(tmp_path: Path) -> None:
    firmware_path = tmp_path / "firmware.bin"
    firmware_path.write_bytes(b"firmware-data")

    config = load_pipeline_config(tmp_path / "missing.yaml", overrides={})

    result = extract_features_from_path(firmware_path, config, model=None)

    assert result.metadata["read_ok"] is True
    assert result.metadata["byte_len"] == len(b"firmware-data")
    assert result.firmware_id is not None
    assert result.metadata["doc2vec_used"] is False


def test_extract_features_from_path_empty_file(tmp_path: Path) -> None:
    firmware_path = tmp_path / "empty.bin"
    firmware_path.write_bytes(b"")

    config = load_pipeline_config(tmp_path / "missing.yaml", overrides={})

    result = extract_features_from_path(firmware_path, config, model=None)

    assert result.metadata["read_ok"] is False
    assert result.firmware_id is None
    assert result.metadata["error"] is not None


def test_extract_features_from_path_max_bytes_zero(tmp_path: Path) -> None:
    firmware_path = tmp_path / "firmware.bin"
    firmware_path.write_bytes(b"abc")

    config_path = tmp_path / "config.yaml"
    config_path.write_text("max_bytes: 0\n")

    config = load_pipeline_config(config_path, overrides={})

    result = extract_features_from_path(firmware_path, config, model=None)

    assert result.metadata["read_ok"] is False
    assert result.metadata["byte_len"] == 0


def test_extract_features_batch_continues_on_error(tmp_path: Path) -> None:
    good_path = tmp_path / "good.bin"
    good_path.write_bytes(b"good")
    missing_path = tmp_path / "missing.bin"

    config = load_pipeline_config(tmp_path / "missing.yaml", overrides={})

    results = extract_features_batch([good_path, missing_path], config)

    assert len(results) == 2
    assert results[0].metadata["read_ok"] is True
    assert results[1].metadata["read_ok"] is False
    assert results[1].firmware_id is None
