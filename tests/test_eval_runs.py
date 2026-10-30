"""Valida leitura de execuções e consistência dos artefatos comparados."""

import json
from pathlib import Path

import pandas as pd
import pytest

from src.evaluation.runs import check_same_inputs, load_run

FIRST = "a" * 64
SECOND = "b" * 64


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
    _run(tmp_path, FIRST, "hash-a")
    _run(tmp_path, SECOND, "hash-b")
    with pytest.raises(ValueError, match=f"{FIRST}.*{SECOND}"):
        check_same_inputs([load_run(tmp_path, name) for name in (FIRST, SECOND)])


def test_missing_predictions_are_rejected(tmp_path: Path) -> None:
    """Falha ao ler uma execução sem parquet de predições."""
    directory = tmp_path / FIRST
    directory.mkdir()
    (directory / "run.meta.json").write_text(
        json.dumps({"run_id": FIRST}), encoding="utf-8"
    )
    with pytest.raises(FileNotFoundError, match="predictions.parquet"):
        load_run(tmp_path, FIRST)


@pytest.mark.parametrize("run_id", ["../" + FIRST, "/tmp/" + FIRST, "", FIRST.upper()])
def test_run_id_outside_sha256_format_is_rejected(tmp_path: Path, run_id: str) -> None:
    """Recusa run_id que não é SHA256, mesmo apontando para execução existente."""
    _run(tmp_path, FIRST, "hash-a")
    with pytest.raises(ValueError, match="run_id inválido"):
        load_run(tmp_path / "runs", run_id)
