"""Testa o modo de unificação de fabricantes do CLI."""

from __future__ import annotations

import csv
import hashlib
import sys
from pathlib import Path

import pytest

from scripts import reorganize_dataset as cli


def _invoke(monkeypatch: pytest.MonkeyPatch, root: Path, *args: str) -> int:
    """Executa a CLI sobre uma árvore temporária de firmware."""
    monkeypatch.setattr(cli, "ROOT", root)
    monkeypatch.setattr(cli, "RAW", root / "dataset" / "raw")
    monkeypatch.setattr(
        sys,
        "argv",
        ["reorganize_dataset.py", "--merge-vendor", "tplink:tp_link", *args],
    )
    return cli.main()


def _firmware(root: Path, relative: str, payload: bytes) -> Path:
    """Cria um arquivo de firmware no caminho relativo à raiz raw."""
    path = root / "dataset" / "raw" / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    return path


def test_merge_moves_files_preserves_hash_and_writes_map(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Move modelos normalizados e registra caminhos e hashes verificáveis."""
    first = _firmware(tmp_path, "tplink/tl_wr841n/a.bin", b"firmware A")
    second = _firmware(tmp_path, "tplink/archer_c7/b.bin", b"firmware B")
    old_hashes = {
        path.name: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in (first, second)
    }
    assert _invoke(monkeypatch, tmp_path, "--execute") == 0
    assert not first.exists() and not second.exists()
    with (tmp_path / "configs/tplink_merge_map.csv").open(newline="") as stream:
        rows = list(csv.DictReader(stream))
    assert rows == [
        {
            "old_path": "tplink/archer_c7/b.bin",
            "new_path": "tp_link/archer-c7/b.bin",
            "sha256": old_hashes["b.bin"],
        },
        {
            "old_path": "tplink/tl_wr841n/a.bin",
            "new_path": "tp_link/tl-wr841n/a.bin",
            "sha256": old_hashes["a.bin"],
        },
    ]
    for row in rows:
        new = tmp_path / "dataset/raw" / row["new_path"]
        assert hashlib.sha256(new.read_bytes()).hexdigest() == row["sha256"]
    assert not (tmp_path / "dataset/raw/tplink").exists()


def test_merge_dry_run_preserves_files_directories_and_map(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Mostra o plano sem criar mapa nem alterar arquivos ou diretórios."""
    source = _firmware(tmp_path, "tplink/tl_wr841n/a.bin", b"firmware")
    empty = tmp_path / "dataset/raw/tplink/archer_d7b"
    empty.mkdir()
    assert _invoke(monkeypatch, tmp_path) == 0
    output = capsys.readouterr().out
    assert "tp_link/tl-wr841n/a.bin" in output
    assert "1 files planned" in output
    assert "1 empty" in output
    assert source.read_bytes() == b"firmware"
    assert empty.is_dir()
    assert not (tmp_path / "dataset/raw/tp_link").exists()
    assert not (tmp_path / "configs/tplink_merge_map.csv").exists()


def test_merge_removes_empty_model_and_vendor(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Remove modelos vazios após movimentação sem contar esses modelos no mapa."""
    (tmp_path / "dataset/raw/tplink/archer_d7b").mkdir(parents=True)
    assert _invoke(monkeypatch, tmp_path, "--execute") == 0
    assert not (tmp_path / "dataset/raw/tplink").exists()
    with (tmp_path / "configs/tplink_merge_map.csv").open(newline="") as stream:
        assert list(csv.DictReader(stream)) == []


@pytest.mark.parametrize("same_content", [True, False])
def test_merge_conflict_fails_before_any_move(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    same_content: bool,
) -> None:
    """Recusa modelo ocupado mesmo se o arquivo de destino for idêntico."""
    free = _firmware(tmp_path, "tplink/aa_router/free.bin", b"free")
    conflict = _firmware(tmp_path, "tplink/tl_er604w/fw.bin", b"same")
    destination = _firmware(
        tmp_path, "tp_link/tl-er604w/fw.bin", b"same" if same_content else b"other"
    )
    assert _invoke(monkeypatch, tmp_path, "--execute") != 0
    assert "tl_er604w" in caplog.text
    assert free.read_bytes() == b"free"
    assert conflict.read_bytes() == b"same"
    assert destination.read_bytes() == (b"same" if same_content else b"other")
    assert not (tmp_path / "dataset/raw/tp_link/aa-router").exists()
    assert not (tmp_path / "configs/tplink_merge_map.csv").exists()
