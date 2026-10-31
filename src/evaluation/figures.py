"""Gera figuras PNG determinísticas do relatório de avaliação (011).

Usa ``matplotlib.figure.Figure`` diretamente, sem pyplot: o PNG sai pelo
backend Agg sem estado global nem janela.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from matplotlib.figure import Figure

DPI = 100


def _save(fig: Figure, path: Path) -> None:
    """Salva a figura em PNG sem metadados variáveis."""
    fig.tight_layout()
    fig.savefig(path, format="png", dpi=DPI, metadata={"Software": None})


def _list_height(n_items: int) -> float:
    """Retorna a altura da figura proporcional ao número de itens."""
    return 0.35 * n_items + 1.5


def _asymmetric_errors(
    center: pd.Series, low: pd.Series, high: pd.Series
) -> np.ndarray:
    """Retorna barras de erro não negativas em torno da estimativa pontual."""
    return np.vstack([center - low, high - center]).clip(min=0)


def plot_confusion(
    confusion_rows: pd.DataFrame, classes: tuple[str, ...], title: str, path: Path
) -> None:
    """Desenha a matriz de confusão com as contagens anotadas."""
    counts = confusion_rows.set_index(["true_class", "predicted_class"])["count"]
    matrix = np.asarray(
        [[int(counts[(true, pred)]) for pred in classes] for true in classes]
    )
    fig = Figure(figsize=(6, 5))
    axis = fig.subplots()
    axis.imshow(matrix, cmap="Blues")
    for (row, column), value in np.ndenumerate(matrix):
        color = "white" if value > matrix.max() / 2 else "black"
        axis.text(column, row, str(value), ha="center", va="center", color=color)
    axis.set_xticks(range(len(classes)), classes, rotation=20)
    axis.set_yticks(range(len(classes)), classes)
    axis.set_xlabel("classe prevista")
    axis.set_ylabel("classe verdadeira")
    axis.set_title(title)
    _save(fig, path)


def plot_deltas(rows: pd.DataFrame, path: Path) -> None:
    """Desenha Δ e IC de cada comparação, com linha vertical em zero.

    ``rows`` tem as colunas label, delta, delta_ci_low e delta_ci_high.
    """
    ordered = rows.iloc[::-1].reset_index(drop=True)
    errors = _asymmetric_errors(
        ordered["delta"], ordered["delta_ci_low"], ordered["delta_ci_high"]
    )
    fig = Figure(figsize=(7, _list_height(len(ordered))))
    axis = fig.subplots()
    axis.errorbar(ordered["delta"], range(len(ordered)), xerr=errors, fmt="o",
                  color="black", capsize=3)
    axis.axvline(0.0, color="grey", linestyle="--", linewidth=1)
    axis.set_yticks(range(len(ordered)), ordered["label"])
    axis.set_xlabel("Δ macro-F1 (IC 95%, bootstrap por componente)")
    _save(fig, path)


def plot_importance(importance: pd.DataFrame, path: Path) -> None:
    """Desenha a queda média de macro-F1 por feature com IC assimétrico."""
    ordered = importance.iloc[::-1].reset_index(drop=True)
    errors = _asymmetric_errors(
        ordered["mean_drop"], ordered["ci_low"], ordered["ci_high"]
    )
    fig = Figure(figsize=(7, _list_height(len(ordered))))
    axis = fig.subplots()
    axis.barh(range(len(ordered)), ordered["mean_drop"], xerr=errors,
              color="steelblue", capsize=2)
    axis.axvline(0.0, color="grey", linewidth=1)
    axis.set_yticks(range(len(ordered)), ordered["feature"])
    axis.set_xlabel("queda de macro-F1 por permutação (média dos folds)")
    _save(fig, path)
