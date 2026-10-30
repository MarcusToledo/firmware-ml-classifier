"""Valida leitura de execuções e consistência dos artefatos comparados."""

import json
from pathlib import Path

import pandas as pd
import pytest

from src.evaluation.runs import check_same_inputs, load_run


def _run(runs_dir: Path, run_id: str, fold_hash: str) -> None:
    """Grava uma execução mínima com hashes de entrada explícitos."""
    directory = runs_dir / run_id
    directory.mkdir(parents=True)
    (directory / "run.meta.json").write_text(json.dumps({
        "run_id": run_id, "inputs": {
            key: {"sha256": fold_hash if key == "folds" else "same"}
            for key in ("table", "provenance", "folds")
        },
    }), encoding="utf-8")
    pd.DataFrame({"repeat": [0]}).to_parquet(directory / "predictions.parquet")


def test_different_folds_cannot_be_mixed(tmp_path: Path) -> None:
    """Nomeia ambos os run_ids de folds incompatíveis."""
    _run(tmp_path, "first", "hash-a")
    _run(tmp_path, "second", "hash-b")
    with pytest.raises(ValueError, match="first.*second"):
        check_same_inputs([load_run(tmp_path, name) for name in ("first", "second")])


def test_missing_predictions_are_rejected(tmp_path: Path) -> None:
    """Falha ao ler uma execução sem parquet de predições."""
    directory = tmp_path / "first"
    directory.mkdir()
    (directory / "run.meta.json").write_text('{"run_id":"first"}', encoding="utf-8")
    with pytest.raises(FileNotFoundError, match="predictions.parquet"):
        load_run(tmp_path, "first")
