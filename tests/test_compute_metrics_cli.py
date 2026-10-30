"""Exercita o comando de métricas com relatórios reproduzíveis."""

import json
import subprocess
import sys
from pathlib import Path

import pandas as pd

from src.evaluation.metrics import CLASSES
from src.run_metadata import file_sha256

FIRST = "a" * 64
SECOND = "b" * 64


def _write_run(runs_dir: Path, run_id: str, model: str) -> Path:
    """Prepara predições OOF pequenas para dois modelos com entradas iguais."""
    directory = runs_dir / run_id
    directory.mkdir(parents=True)
    predictions = directory / "predictions.parquet"
    pd.DataFrame({
        "repeat": [0, 0, 0], "fold": [0, 1, 1],
        "firmware_id": ["a", "b", "c"],
        "y_true": list(CLASSES), "y_pred": [CLASSES[0], CLASSES[0], CLASSES[2]],
    }).to_parquet(predictions, index=False)
    (directory / "run.meta.json").write_text(json.dumps({
        "run_id": run_id, "model": model, "experiment": "principal",
        "scheme": "grouped", "purpose": "baseline",
        "inputs": {key: {"sha256": "same"}
                   for key in ("table", "provenance", "folds")},
    }), encoding="utf-8")
    return predictions


def test_cli_reports_are_byte_identical_across_directories(tmp_path: Path) -> None:
    """Preserva linhas CSV e rastreia folds incompletos e hashes de origem."""
    runs_dir = tmp_path / "runs"
    first = _write_run(runs_dir, FIRST, "extra_trees")
    second = _write_run(runs_dir, SECOND, "random_forest")
    reports = []
    for index in (0, 1):
        command = [sys.executable, "scripts/compute_metrics.py", "--runs-dir",
                   str(runs_dir), "--output-dir", str(tmp_path / f"report-{index}"),
                   "--run-id", SECOND, "--run-id", FIRST]
        process = subprocess.run(command, capture_output=True, text=True, check=False)
        assert process.returncode == 0, process.stderr
        reports.append(Path(process.stdout.strip()))
    for name in ("metrics.csv", "metrics_per_class.csv", "confusion.csv"):
        assert file_sha256(reports[0] / name) == file_sha256(reports[1] / name)
    summary = pd.read_csv(reports[0] / "metrics.csv")
    assert summary["run_id"].tolist() == [FIRST, SECOND]
    manifest = json.loads((reports[0] / "report.meta.json").read_text())
    assert manifest["runs"][FIRST]["predictions_sha256"] == file_sha256(first)
    assert manifest["runs"][SECOND]["predictions_sha256"] == file_sha256(second)
    missing = manifest["folds_missing_class"][FIRST]["0"][0]["missing"]
    assert missing == list(CLASSES[1:])
