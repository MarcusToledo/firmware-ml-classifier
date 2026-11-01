"""Calcula importância por permutação do Extra Trees B2 por fold (011/FR-010)."""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.inspection import permutation_importance
from sklearn.metrics import f1_score, make_scorer

from src.dataset import contract as c
from src.evaluation.runs import EvaluatedRun

LOGGER = logging.getLogger(__name__)


def _fold_drops(
    run: EvaluatedRun, runs_dir: Path, table: pd.DataFrame, record: dict[str, Any],
    classes: tuple[str, ...], n_repeats: int, seed: int,
) -> np.ndarray:
    """Retorna a queda média de macro-F1 por coluna no teste de um fold.

    Levanta ValueError se o fold não tem modelo salvo ou se o modelo não
    reproduz as predições gravadas.
    """
    fold = int(record["fold"])
    if not record.get("model_file"):
        raise ValueError(f"fold {fold} sem modelo salvo: run_id {run.run_id}")
    pipeline = joblib.load(runs_dir / run.run_id / record["model_file"])
    predictions = run.predictions.loc[
        (run.predictions["repeat"] == record["repeat"])
        & (run.predictions["fold"] == fold)
    ].sort_values(c.KEY_COLUMN)
    ids = predictions[c.KEY_COLUMN].tolist()
    indexed = table.set_index(c.KEY_COLUMN)
    x_test = indexed.loc[ids, run.meta["columns"]].astype("float64")
    y_test = indexed.loc[ids, c.TARGET_COLUMN]
    if pipeline.predict(x_test).tolist() != predictions["y_pred"].tolist():
        raise ValueError(
            f"modelo do fold {fold} diverge das predições gravadas: run_id {run.run_id}"
        )
    # pos_label=None: sem ele o scorer valida o rótulo positivo padrão 1.
    scorer = make_scorer(
        f1_score, average="macro", labels=list(classes), zero_division=0,
        pos_label=None,
    )
    started = time.perf_counter()
    result = permutation_importance(
        pipeline, x_test, y_test, scoring=scorer, n_repeats=n_repeats,
        random_state=seed, n_jobs=1,
    )
    LOGGER.info("permutação fold %s: %.1f s", fold, time.perf_counter() - started)
    return np.asarray(result.importances_mean, dtype=np.float64)


def permutation_by_fold(
    run: EvaluatedRun, runs_dir: Path, table: pd.DataFrame,
    classes: tuple[str, ...], n_repeats: int, seed: int, ci: float,
) -> pd.DataFrame:
    """Agrega por feature a queda de macro-F1 dos folds (importance.csv).

    Levanta ValueError fora do Extra Trees reportado (B2).
    """
    if run.meta["model"] != "extra_trees" or run.meta["purpose"] != "reportado":
        raise ValueError("importância só no Extra Trees B2 (011/FR-010)")
    records = sorted(run.meta["folds"], key=lambda r: (r["repeat"], r["fold"]))
    drops = np.stack([
        _fold_drops(run, runs_dir, table, record, classes, n_repeats, seed)
        for record in records
    ], axis=1)
    low, high = np.percentile(
        drops, [100 * (1 - ci) / 2, 100 * (1 + ci) / 2], axis=1, method="linear"
    )
    frame = pd.DataFrame({
        "feature": run.meta["columns"], "mean_drop": drops.mean(axis=1),
        "std_drop": drops.std(axis=1, ddof=1), "ci_low": low, "ci_high": high,
        "n_folds": len(records),
    })
    for index, record in enumerate(records):
        frame[f"drop_fold_{record['fold']}"] = drops[:, index]
    return frame.sort_values(
        ["mean_drop", "feature"], ascending=[False, True]
    ).reset_index(drop=True)
