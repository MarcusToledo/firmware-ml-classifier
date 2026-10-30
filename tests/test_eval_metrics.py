"""Confere métricas OOF e casos indefinidos contra contagens conhecidas."""

import pandas as pd
import pytest

from src.evaluation.metrics import CLASSES, metrics_by_repeat


def _predictions() -> pd.DataFrame:
    """Monta matriz com suportes 2, 2 e 1 e um erro por classe."""
    return pd.DataFrame({
        "repeat": [0] * 5, "fold": [0, 0, 1, 1, 1],
        "firmware_id": [f"id-{i}" for i in range(5)],
        "y_true": [CLASSES[i] for i in (0, 0, 1, 1, 2)],
        "y_pred": [CLASSES[i] for i in (0, 1, 1, 2, 2)],
    })


def test_pooled_metrics_match_hand_counted_confusion() -> None:
    """Usa a matriz 1/1/0, 0/1/1, 0/0/1 para provar agregação pooled."""
    result = metrics_by_repeat(_predictions(), CLASSES)[0]
    assert result.confusion["count"].tolist() == [1, 1, 0, 0, 1, 1, 0, 0, 1]
    assert result.per_class["support"].tolist() == [2, 2, 1]
    assert result.per_class["precision"].tolist() == pytest.approx([1, .5, .5])
    assert result.per_class["recall"].tolist() == pytest.approx([.5, .5, 1])
    assert result.per_class["f1"].tolist() == pytest.approx([2 / 3, .5, 2 / 3])
    assert result.summary == pytest.approx({
        "macro_f1": 11 / 18, "balanced_accuracy": 2 / 3,
        "macro_precision": 2 / 3, "macro_recall": 2 / 3,
    })
    assert result.folds_missing_class == [
        {"repeat": 0, "fold": 0, "missing": [CLASSES[1], CLASSES[2]]},
        {"repeat": 0, "fold": 1, "missing": [CLASSES[0]]},
    ]


def test_never_predicted_and_missing_support_are_explicit() -> None:
    """Zera divisão indefinida e inclui classe sem suporte na média fixa."""
    rows = _predictions().iloc[:4].copy()
    rows["y_pred"] = CLASSES[0]
    result = metrics_by_repeat(rows, CLASSES)[0]
    assert result.per_class["precision"].tolist() == pytest.approx([.5, 0, 0])
    assert result.summary["balanced_accuracy"] == pytest.approx(1 / 3)
    assert result.undefined == [f"precision:{CLASSES[1]}",
                                f"precision:{CLASSES[2]}", f"recall:{CLASSES[2]}"]


@pytest.mark.parametrize("column", ["y_true", "y_pred"])
def test_unknown_label_is_rejected(column: str) -> None:
    """Recusa qualquer rótulo fora das classes pré-registradas."""
    rows = _predictions()
    rows.loc[0, column] = "indeterminado"
    with pytest.raises(ValueError, match="indeterminado"):
        metrics_by_repeat(rows, CLASSES)


def test_duplicate_firmware_in_repeat_is_rejected() -> None:
    """Um ID não pode receber duas predições OOF na mesma repetição."""
    rows = _predictions()
    rows.loc[4, "firmware_id"] = "id-0"
    with pytest.raises(ValueError, match="id-0"):
        metrics_by_repeat(rows, CLASSES)
