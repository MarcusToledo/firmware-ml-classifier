import subprocess
import sys
from pathlib import Path


def test_cli_basic_file(tmp_path: Path) -> None:
    firmware_path = tmp_path / "firmware.bin"
    firmware_path.write_bytes(b"firmware")
    config_path = tmp_path / "config.yaml"
    config_path.write_text("")

    result = subprocess.run(
        [
            sys.executable,
            "scripts/extract_features.py",
            "--config",
            str(config_path),
            "--input",
            str(firmware_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "read_ok" in result.stdout + result.stderr


def test_cli_with_override(tmp_path: Path) -> None:
    firmware_path = tmp_path / "firmware.bin"
    firmware_path.write_bytes(b"firmware")
    config_path = tmp_path / "config.yaml"
    config_path.write_text("")

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
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "read_ok" in result.stdout + result.stderr


def test_cli_directory_input(tmp_path: Path) -> None:
    firmware_dir = tmp_path / "firmwares"
    firmware_dir.mkdir()
    (firmware_dir / "one.bin").write_bytes(b"one")
    (firmware_dir / "two.bin").write_bytes(b"two")
    config_path = tmp_path / "config.yaml"
    config_path.write_text("")

    result = subprocess.run(
        [
            sys.executable,
            "scripts/extract_features.py",
            "--config",
            str(config_path),
            "--input",
            str(firmware_dir),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "read_ok" in result.stdout + result.stderr
