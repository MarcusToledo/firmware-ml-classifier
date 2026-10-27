"""Verifica geração reproduzível, rastreabilidade e falha segura da CLI."""

from __future__ import annotations

import json
import logging
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.make_folds import main
from src.dataset.contract import TABLE_FILENAME, TARGET_CLASSES
from src.dataset.partition import FOLDS_FILENAME, FOLDS_META_FILENAME
from tests.test_partition import make_inputs

ROOT = Path(__file__).resolve().parents[1]


def _run(config: Path) -> subprocess.CompletedProcess[str]:
    """Executa a CLI em outro processo com override de semente."""
    return subprocess.run(
        [
            sys.executable,
            "scripts/make_folds.py",
            "--config",
            str(config),
            "--override",
            "partition.seeds=[7]",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def _config(tmp_path: Path, rare: bool = False) -> Path:
    """Grava entradas e YAML locais para gerar os folds."""
    make_inputs(tmp_path / "processed", rare=rare)
    config = tmp_path / "config.yaml"
    config.write_text(
        f"output_dir: {tmp_path / 'processed'}\n"
        "partition:\n  n_splits: 5\n  seeds: [0]\n",
        encoding="utf-8",
    )
    return config


def test_cli_is_reproducible_and_records_distribution(tmp_path: Path) -> None:
    """Mantém bytes estáveis e registra override, aliases e classes raras."""
    config = _config(tmp_path, rare=True)
    output = tmp_path / "processed"
    first = _run(config)
    assert first.returncode == 0, first.stderr
    before = (output / FOLDS_FILENAME).read_bytes()
    meta_before = json.loads((output / FOLDS_META_FILENAME).read_text())
    second = _run(config)
    assert second.returncode == 0, second.stderr
    meta_after = json.loads((output / FOLDS_META_FILENAME).read_text())
    assert (output / FOLDS_FILENAME).read_bytes() == before
    assert meta_before.pop("created_at")
    assert meta_after.pop("created_at")
    assert meta_before == meta_after
    assert meta_after["scheme"] == "grouped"
    assert meta_after["purpose"] == "principal"
    assert meta_after["seeds"] == [7]
    assert meta_after["config"]["partition"]["seeds"] == [7]
    assert meta_after["n_groups"] == 40
    assert meta_after["test_folds_missing_class"]
    for fold in meta_after["per_fold"]:
        assert set(fold["test"]["classes"]) == set(TARGET_CLASSES)
    assert any(
        section["vendors"].get("other") == 1
        for fold in meta_after["per_fold"]
        for section in (fold["train"], fold["test"])
    )


def test_cli_rejects_changed_table_before_writing(tmp_path: Path) -> None:
    """Não cria folds quando o SHA da tabela de treino diverge."""
    config = _config(tmp_path)
    output = tmp_path / "processed"
    target = output / TABLE_FILENAME
    target.write_bytes(target.read_bytes() + b"x")
    result = _run(config)
    assert result.returncode != 0
    assert "SHA256 divergente" in result.stderr
    assert not (output / FOLDS_FILENAME).exists()
    assert not (output / FOLDS_META_FILENAME).exists()


def test_main_logs_group_sizes_and_per_fold_classes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Publica grupos, maior grupo e distribuição das classes nos logs."""
    config = _config(tmp_path)
    monkeypatch.setattr(sys, "argv", ["make-folds", "--config", str(config)])
    with caplog.at_level(logging.INFO):
        assert main() == 0
    messages = "\n".join(record.getMessage() for record in caplog.records)
    assert "40 grupos" in messages
    assert "maior grupo 1" in messages
    for index in range(5):
        assert f"Fold {index}: treino" in messages
    assert all(name in messages for name in TARGET_CLASSES)
