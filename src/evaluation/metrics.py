"""Calcula métricas de classificação por repetição sobre predições OOF."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd
from sklearn.metrics import confusion_matrix, precision_recall_fscore_support

from src.dataset import contract as c

CLASSES = c.TARGET_CLASSES
REQUIRED_COLUMNS = ("repeat", "fold", "firmware_id", "y_true", "y_pred")


@dataclass(frozen=True)
class RunMetrics:
    """Agrupa métricas, matriz de confusão e indefinições de uma repetição."""

    summary: dict[str, float]
    per_class: pd.DataFrame
    confusion: pd.DataFrame
    undefined: list[str]
    folds_missing_class: list[dict]


def _validate_predictions(predictions: pd.DataFrame, classes: tuple[str, ...]) -> None:
    """Rejeita colunas ausentes, IDs repetidos e rótulos desconhecidos."""
    missing = set(REQUIRED_COLUMNS) - set(predictions.columns)
    if missing:
        raise ValueError(f"colunas ausentes nas predições: {sorted(missing)}")
    duplicated = predictions.duplicated(["repeat", "firmware_id"])
    if duplicated.any():
        raise ValueError("firmware_id duplicado na repetição: "
                         f"{predictions.loc[duplicated, 'firmware_id'].tolist()}")
    for column in ("y_true", "y_pred"):
        unknown = set(predictions[column]) - set(classes)
        if unknown:
            raise ValueError(f"rótulos fora das classes em {column}: {sorted(unknown)}")


def _missing_in_folds(frame: pd.DataFrame, classes: tuple[str, ...]) -> list[dict]:
    """Lista folds cujo teste não contém todas as classes registradas."""
    missing_folds = []
    for (repeat, fold), rows in frame.groupby(["repeat", "fold"], sort=True):
        missing = [label for label in classes if label not in set(rows["y_true"])]
        if missing:
            missing_folds.append({"repeat": int(repeat), "fold": int(fold),
                                  "missing": missing})
    return missing_folds


def frame_metrics(frame: pd.DataFrame, classes: tuple[str, ...]) -> RunMetrics:
    """Computa indicadores com classes fixas e divisão por zero igual a zero."""
    labels = list(classes)
    precision, recall, f1, support = precision_recall_fscore_support(
        frame["y_true"], frame["y_pred"], labels=labels, zero_division=0
    )
    matrix = confusion_matrix(frame["y_true"], frame["y_pred"], labels=labels)
    undefined = []
    for index, label in enumerate(classes):
        if matrix[:, index].sum() == 0:
            undefined.append(f"precision:{label}")
        if support[index] == 0:
            undefined.append(f"recall:{label}")
    per_class = pd.DataFrame({"class": labels, "precision": precision,
                              "recall": recall, "f1": f1, "support": support})
    confusion = pd.DataFrame(
        [(true, predicted, int(matrix[i, j]))
         for i, true in enumerate(classes) for j, predicted in enumerate(classes)],
        columns=["true_class", "predicted_class", "count"],
    )
    summary = {"macro_f1": float(f1.mean()),
               "balanced_accuracy": float(recall.mean()),
               "macro_precision": float(precision.mean()),
               "macro_recall": float(recall.mean())}
    return RunMetrics(summary, per_class, confusion, undefined,
                      _missing_in_folds(frame, classes))


def metrics_by_repeat(
    predictions: pd.DataFrame, classes: tuple[str, ...]
) -> dict[int, RunMetrics]:
    """Agrupa todos os folds OOF por repetição antes de calcular as métricas."""
    _validate_predictions(predictions, classes)
    return {int(repeat): frame_metrics(frame, classes)
            for repeat, frame in predictions.groupby("repeat", sort=True)}
