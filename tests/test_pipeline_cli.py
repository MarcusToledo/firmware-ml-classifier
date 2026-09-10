import re
import subprocess
import sys
from pathlib import Path

import pandas as pd


def test_cli_reports_elapsed_time(tmp_path: Path) -> None:
    firmware_path = tmp_path / "firmware.bin"
    firmware_path.write_bytes(b"firmware")
    config_path = tmp_path / "config.yaml"
    config_path.write_text("")
    output_path = tmp_path / "features.parquet"

    result = subprocess.run(
        [
            sys.executable,
            "scripts/extract_features.py",
            "--config",
            str(config_path),
            "--input",
            str(firmware_path),
            "--output",
            str(output_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    output = result.stdout + result.stderr
    match = re.search(
        r"Extraction of 1 file\(s\) completed in (\d+\.\d{2})s "
        r"\(avg (\d+\.\d{3})s/file\)",
        output,
    )
    assert match is not None, output
    assert float(match.group(1)) >= 0.0
    assert float(match.group(2)) >= 0.0

    success_match = re.search(
        r"Extraction succeeded: 1 record\(s\) written to .+ in (\d+\.\d{2})s",
        output,
    )
    assert success_match is not None, output
    assert float(success_match.group(1)) >= 0.0


def test_cli_basic_file(tmp_path: Path) -> None:
    firmware_path = tmp_path / "firmware.bin"
    firmware_path.write_bytes(b"firmware")
    config_path = tmp_path / "config.yaml"
    config_path.write_text("")
    output_path = tmp_path / "features.parquet"

    result = subprocess.run(
        [
            sys.executable,
            "scripts/extract_features.py",
            "--config",
            str(config_path),
            "--input",
            str(firmware_path),
            "--output",
            str(output_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "read_ok" in result.stdout + result.stderr
    assert output_path.exists()

    df = pd.read_parquet(output_path)
    assert not df.empty
    assert "meta_path" in df.columns
    assert "meta_brand" in df.columns
    assert "meta_model" in df.columns
    assert "meta_label" in df.columns
    assert "meta_bytes_used" in df.columns
    assert "meta_max_bytes" in df.columns
    assert df["meta_label"].isna().to_numpy().all()


def test_cli_with_override(tmp_path: Path) -> None:
    firmware_path = tmp_path / "firmware.bin"
    firmware_path.write_bytes(b"firmware")
    config_path = tmp_path / "config.yaml"
    config_path.write_text("")
    output_path = tmp_path / "features.parquet"

    result = subprocess.run(
        [
            sys.executable,
            "scripts/extract_features.py",
            "--config",
            str(config_path),
            "--input",
            str(firmware_path),
            "--override",
            "feature.max_single_string_len=8",
            "--output",
            str(output_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "read_ok" in result.stdout + result.stderr
    assert output_path.exists()

    df = pd.read_parquet(output_path)
    assert not df.empty
    assert "meta_path" in df.columns
    assert "meta_brand" in df.columns
    assert "meta_model" in df.columns
    assert "meta_label" in df.columns
    assert "meta_bytes_used" in df.columns
    assert "meta_max_bytes" in df.columns
    assert df["meta_label"].isna().to_numpy().all()


def test_cli_directory_input(tmp_path: Path) -> None:
    firmware_dir = tmp_path / "firmwares"
    firmware_dir.mkdir()
    (firmware_dir / "one.bin").write_bytes(b"one")
    (firmware_dir / "two.bin").write_bytes(b"two")
    config_path = tmp_path / "config.yaml"
    config_path.write_text("")
    output_path = tmp_path / "features.parquet"

    result = subprocess.run(
        [
            sys.executable,
            "scripts/extract_features.py",
            "--config",
            str(config_path),
            "--input",
            str(firmware_dir),
            "--output",
            str(output_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "read_ok" in result.stdout + result.stderr
    assert output_path.exists()

    df = pd.read_parquet(output_path)
    assert not df.empty
    assert "meta_path" in df.columns
    assert "meta_brand" in df.columns
    assert "meta_model" in df.columns
    assert "meta_label" in df.columns
    assert "meta_bytes_used" in df.columns
    assert "meta_max_bytes" in df.columns
    assert df["meta_label"].isna().to_numpy().all()


def test_cli_label_from_path(tmp_path: Path) -> None:
    base_dir = tmp_path / "dataset" / "raw" / "dlink" / "DIR300"
    base_dir.mkdir(parents=True)
    firmware_path = base_dir / "firmware.bin"
    firmware_path.write_bytes(b"firmware")
    config_path = tmp_path / "config.yaml"
    config_path.write_text("")
    output_path = tmp_path / "features.parquet"

    result = subprocess.run(
        [
            sys.executable,
            "scripts/extract_features.py",
            "--config",
            str(config_path),
            "--input",
            str(firmware_path),
            "--output",
            str(output_path),
            "--label-from-path",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "read_ok" in result.stdout + result.stderr
    assert output_path.exists()

    df = pd.read_parquet(output_path)
    assert not df.empty
    assert df["meta_brand"].iloc[0] == "dlink"
    assert df["meta_model"].iloc[0] == "dir300"
    assert df["meta_label"].iloc[0] == "dlink_dir300"


def test_cli_csv_output(tmp_path: Path) -> None:
    firmware_path = tmp_path / "firmware.bin"
    firmware_path.write_bytes(b"firmware")
    config_path = tmp_path / "config.yaml"
    config_path.write_text("")
    output_path = tmp_path / "features.csv"

    result = subprocess.run(
        [
            sys.executable,
            "scripts/extract_features.py",
            "--config",
            str(config_path),
            "--input",
            str(firmware_path),
            "--output",
            str(output_path),
            "--format",
            "csv",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "read_ok" in result.stdout + result.stderr
    assert output_path.exists()

    df = pd.read_csv(output_path)
    assert not df.empty
    assert "meta_path" in df.columns
    assert "meta_brand" in df.columns
    assert "meta_model" in df.columns
    assert "meta_label" in df.columns
    assert "meta_bytes_used" in df.columns
    assert "meta_max_bytes" in df.columns
    assert df["meta_label"].isna().to_numpy().all()
