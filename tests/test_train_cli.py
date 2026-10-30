"""Exercita CLI de treino, determinismo e logs por fold."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from scripts import train
from src.dataset import contract as c
from src.run_metadata import file_sha256
from tests.dataset_fixtures import build_frozen_corpus, feature_row


def _corpus(tmp_path: Path) -> Path:
    """Gera corpus independente para verificar previsões da CLI."""
    rows = [
        feature_row(
            f"id-{i:02}", f"{('acme', 'beta', 'gamma')[i % 3]}/m{i}/fw.bin",
            entropy=6.0 + i / 100,
        )
        for i in range(30)
    ]
    levels = {f"id-{i:02}": c.TARGET_CLASSES[i % 3] for i in range(30)}
    return build_frozen_corpus(tmp_path, rows, levels)


def test_cli_repeats_predictions_in_distinct_outputs(tmp_path: Path) -> None:
    """Compara bytes reproduzidos nos baselines ET e identidade."""
    processed = _corpus(tmp_path)
    for model in ("extra_trees", "identidade"):
        metas = []
        hashes = []
        for index in (0, 1):
            output = tmp_path / f"output-{model}-{index}"
            cmd = [sys.executable, "scripts/train.py", "--model", model,
                   "--override", f"processed_dir={processed}",
                   "--override", f"output_dir={output}",
                   "--override", "hyperparameters.n_estimators=20"]
            run = subprocess.run(cmd, capture_output=True, text=True, check=False)
            assert run.returncode == 0, run.stderr
            run_id = run.stdout.strip().split("\t")[1]
            path = output / run_id
            hashes.append(file_sha256(path / "predictions.parquet"))
            meta = json.loads((path / "run.meta.json").read_text())
            meta.pop("created_at")
            meta["config"].pop("output_dir")
            metas.append(meta)
            if index == 0:
                again = subprocess.run(cmd, capture_output=True, text=True, check=False)
                assert again.returncode == 1
                assert "execução já existe: run_id" in again.stderr
        assert hashes[0] == hashes[1]
        assert metas[0] == metas[1]


def test_cli_logs_fold_provenance(tmp_path: Path, caplog, monkeypatch, capsys) -> None:
    """Registra tamanhos, classes, semente e hiperparâmetros de cada fold."""
    processed = _corpus(tmp_path)
    monkeypatch.setattr(sys, "argv", ["train.py", "--model", "extra_trees",
                        "--override", f"processed_dir={processed}",
                        "--override", f"output_dir={tmp_path / 'runs'}",
                        "--override", "hyperparameters.n_estimators=20"])
    with caplog.at_level("INFO"):
        assert train.main() == 0
    assert capsys.readouterr().out.startswith("extra_trees\t")
    messages = [
        row.message for row in caplog.records if "repetição 0 fold" in row.message
    ]
    assert len(messages) == 5
    for message in messages:
        assert all(
            part in message for part in
            ("treino", "teste", "classes", "colunas", "seed 0", "n_estimators")
        )
