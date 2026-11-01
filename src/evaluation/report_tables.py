"""Persiste tabelas CSV determinísticas e manifesto de avaliação."""

from __future__ import annotations

import json
import platform
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import sklearn

from src.evaluation.metrics import CLASSES, RunMetrics
from src.evaluation.runs import INPUT_KEYS, EvaluatedRun
from src.models.training import MODELS
from src.run_metadata import code_commit


def _ordered_runs(runs: list[EvaluatedRun]) -> list[EvaluatedRun]:
    """Ordena execuções pelo braço pré-registrado e pela identidade."""
    return sorted(runs, key=lambda run: (MODELS.index(run.meta["model"]), run.run_id))


def metric_rows(
    runs: list[EvaluatedRun], results: dict[str, dict[int, RunMetrics]]
) -> tuple[list[dict], list[dict], list[dict]]:
    """Agrupa linhas de resumo, classe e confusão em ordem fixa."""
    summaries, classes, confusions = [], [], []
    for run in _ordered_runs(runs):
        meta = run.meta
        for repeat, metrics in sorted(results[run.run_id].items()):
            common = {"run_id": run.run_id, "purpose": meta["purpose"],
                      "repeat": repeat}
            summaries.append({"run_id": run.run_id, "model": meta["model"],
                              "experiment": meta["experiment"],
                              "scheme": meta["scheme"], "purpose": meta["purpose"],
                              "repeat": repeat, **metrics.summary,
                              "n_predictions": int(
                                  (run.predictions["repeat"] == repeat).sum()),
                              "n_undefined": len(metrics.undefined)})
            classes.extend({**common, **row} for row in
                           metrics.per_class.to_dict("records"))
            confusions.extend({**common, **row} for row in
                              metrics.confusion.to_dict("records"))
    return summaries, classes, confusions


def _report_meta(
    runs: list[EvaluatedRun], results: dict[str, dict[int, RunMetrics]],
    config_meta: dict[str, Any], created_at: datetime,
) -> dict[str, Any]:
    """Registra entradas, indefinições e versões da avaliação."""
    ordered = _ordered_runs(runs)
    return {
        "run_ids": [run.run_id for run in ordered],
        "runs": {run.run_id: {
            "model": run.meta["model"], "purpose": run.meta["purpose"],
            "predictions_path": str(config_meta["runs_dir"] / run.run_id
                                    / "predictions.parquet"),
            "predictions_sha256": run.predictions_sha256,
            "n_predictions": len(run.predictions),
        } for run in ordered},
        "inputs": {key: ordered[0].meta["inputs"][key]["sha256"]
                   for key in INPUT_KEYS},
        "aggregation": "pooled_oof_por_repeticao", "classes": list(CLASSES),
        "zero_division": 0,
        "undefined": {run.run_id: {repeat: result.undefined for repeat, result
                      in sorted(results[run.run_id].items())} for run in ordered},
        "folds_missing_class": {
            run.run_id: {
                repeat: result.folds_missing_class
                for repeat, result in sorted(results[run.run_id].items())
            } for run in ordered
        },
        "commit": code_commit(),
        "versions": {"python": platform.python_version(), "numpy": np.__version__,
                     "pandas": pd.__version__, "scikit-learn": sklearn.__version__},
        "created_at": created_at.isoformat(timespec="seconds"),
    }


def write_metrics_report(
    output_root: Path, runs: list[EvaluatedRun],
    results: dict[str, dict[int, RunMetrics]], config_meta: dict[str, Any],
) -> Path:
    """Grava relatório em diretório UTC novo sem sobrescrever outro relatório."""
    if not runs:
        raise ValueError("nenhuma execução para avaliação")
    created_at = datetime.now(timezone.utc)
    destination = output_root / created_at.strftime("%Y%m%dT%H%M%SZ")
    destination.mkdir(parents=True, exist_ok=False)
    summaries, classes, confusions = metric_rows(runs, results)
    for name, rows, columns in (
        ("metrics.csv", summaries, ("run_id", "model", "experiment", "scheme",
                                   "purpose", "repeat", "macro_f1", "balanced_accuracy",
                                   "macro_precision", "macro_recall", "n_predictions",
                                   "n_undefined")),
        ("metrics_per_class.csv", classes, ("run_id", "purpose", "repeat", "class",
                                            "precision", "recall", "f1", "support")),
        ("confusion.csv", confusions, ("run_id", "purpose", "repeat", "true_class",
                                      "predicted_class", "count")),
    ):
        pd.DataFrame(rows, columns=columns).to_csv(
            destination / name, index=False, float_format="%.6f", lineterminator="\n"
        )
    manifest = _report_meta(runs, results, config_meta, created_at)
    (destination / "report.meta.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return destination
