import subprocess
import sys
from pathlib import Path

import pandas as pd


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
    assert "meta_vendor" in df.columns
    assert df["meta_vendor"].isna().to_numpy().all()


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
    assert "meta_vendor" in df.columns
    assert df["meta_vendor"].isna().to_numpy().all()


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
    assert "meta_vendor" in df.columns
    assert df["meta_vendor"].isna().to_numpy().all()


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
    assert "meta_vendor" in df.columns
    assert df["meta_vendor"].isna().to_numpy().all()
