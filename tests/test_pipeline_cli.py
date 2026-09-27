"""Exercita validações anteriores ao lote e a gravação com raiz ancorada."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
import pytest

from pipeline.feature_extraction import BINWALK_STATUS_TIMEOUT, STRINGS_FILESYSTEM
from scripts import extract_features as cli
from src.features.unpack import Toolchain

_EXIT_USAGE = 2


def _invoke(
    monkeypatch: pytest.MonkeyPatch, input_path: Path, output: Path, *extra: str
) -> None:
    """Executa o mesmo main da CLI com argumentos explícitos."""
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "extract_features.py",
            "--input",
            str(input_path),
            "--output",
            str(output),
            *extra,
        ],
    )
    cli.main()


def test_cli_rejects_missing_root_before_toolchain(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Exige raiz para arquivo isolado, independentemente dos extratores."""
    firmware = tmp_path / "firmware.bin"
    firmware.write_bytes(b"firmware")
    with pytest.raises(SystemExit) as exc:
        _invoke(monkeypatch, firmware, tmp_path / "result.parquet", "--label-from-path")
    assert exc.value.code == _EXIT_USAGE


def test_cli_rejects_off_layout_before_toolchain(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Lista paths fora do layout mesmo que as ferramentas faltem."""
    root = tmp_path / "raw"
    root.mkdir()
    path = root / "dlink" / "loose.bin"
    path.parent.mkdir()
    path.write_bytes(b"firmware")
    with pytest.raises(SystemExit) as exc:
        _invoke(monkeypatch, root, tmp_path / "out.parquet", "--label-from-path")
    assert exc.value.code == _EXIT_USAGE
    assert str(path) in caplog.text


def test_cli_relative_paths_and_unlabelled_identity(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fake_toolchain: Toolchain
) -> None:
    """Mantém meta_path relativo com raiz, mas oculta identidade sem flag."""
    root = tmp_path / "raw"
    firmware = root / "netgear" / "r6250" / "R6250-V1.0.1.80_1.0.75.chk"
    firmware.parent.mkdir(parents=True)
    firmware.write_bytes(b"firmware\x00")
    monkeypatch.setattr(cli, "resolve_toolchain", lambda: fake_toolchain)
    output = tmp_path / "result.parquet"
    _invoke(monkeypatch, root, output)
    unlabelled = pd.read_parquet(output).iloc[0]
    assert unlabelled["meta_path"] == "netgear/r6250/R6250-V1.0.1.80_1.0.75.chk"
    assert pd.isna(unlabelled["meta_version"])
    _invoke(monkeypatch, root, output, "--label-from-path")
    labelled = pd.read_parquet(output).iloc[0]
    assert labelled["meta_version"] == "1.0.1.80"
    assert labelled["meta_brand"] == "netgear"
    assert labelled["meta_strings_source"] == STRINGS_FILESYSTEM


def test_cli_timeout_writes_output_before_nonzero_exit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fake_toolchain: Toolchain
) -> None:
    """Preserva tabela e status para retentativa após timeout binwalk."""
    import pipeline.feature_extraction as pipeline

    firmware = tmp_path / "firmware.bin"
    firmware.write_bytes(b"firmware\x00")
    monkeypatch.setattr(cli, "resolve_toolchain", lambda: fake_toolchain)
    monkeypatch.setattr(
        pipeline, "_scan_binwalk", lambda path, tool: ([], BINWALK_STATUS_TIMEOUT)
    )
    output = tmp_path / "out.parquet"
    with pytest.raises(SystemExit) as exc:
        _invoke(monkeypatch, firmware, output, "--workers", "1")
    assert exc.value.code == 1
    assert (
        pd.read_parquet(output).iloc[0]["meta_binwalk_status"] == BINWALK_STATUS_TIMEOUT
    )


def test_cli_csv_findings_and_override(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fake_toolchain: Toolchain
) -> None:
    """Grava CSV, JSONL ligado ao firmware_id e aplica override registrado."""
    firmware = tmp_path / "firmware.bin"
    firmware.write_bytes(b"firmware\x00")
    monkeypatch.setattr(cli, "resolve_toolchain", lambda: fake_toolchain)
    output = tmp_path / "out.csv"
    findings = tmp_path / "findings.jsonl"
    _invoke(
        monkeypatch,
        firmware,
        output,
        "--format",
        "csv",
        "--findings-output",
        str(findings),
        "--override",
        "max_bytes=4",
        "--workers",
        "1",
    )
    row = pd.read_csv(output).iloc[0]
    assert (row["meta_max_bytes"], row["meta_bytes_used"]) == (4, 4)
    assert row["meta_file_size"] == firmware.stat().st_size
    records = [json.loads(line) for line in findings.read_text().splitlines()]
    assert "hardcoded_passwords" in {record["detector"] for record in records}
    assert {record["firmware_id"] for record in records} == {row["firmware_id"]}


def test_cli_without_findings_output_writes_only_table(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fake_toolchain: Toolchain
) -> None:
    """Sem --findings-output, só a tabela é gravada."""
    firmware = tmp_path / "in" / "firmware.bin"
    firmware.parent.mkdir()
    firmware.write_bytes(b"firmware\x00")
    monkeypatch.setattr(cli, "resolve_toolchain", lambda: fake_toolchain)
    out_dir = tmp_path / "out"
    _invoke(monkeypatch, firmware, out_dir / "features.parquet", "--workers", "1")
    assert [path.name for path in out_dir.iterdir()] == ["features.parquet"]
