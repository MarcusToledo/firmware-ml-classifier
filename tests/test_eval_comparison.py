"""Valida macro-F1 ponderado e bootstrap pareado por componente (011)."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from sklearn.metrics import f1_score

from src.evaluation.comparison import (
    Resampling,
    draw_resampling,
    interpret_anchor,
    interpret_b2_linha,
    paired_group_bootstrap,
    weighted_macro_f1,
)
from src.evaluation.metrics import CLASSES


def _sklearn_f1(y_true, y_pred, weights=None) -> float:
    """Retorna o macro-F1 de referência com as classes fixas."""
    return float(f1_score(y_true, y_pred, labels=list(CLASSES), average="macro",
                          zero_division=0, sample_weight=weights))


def test_unit_weights_match_sklearn_with_absent_class() -> None:
    """Coincide com o sklearn quando uma classe verdadeira está ausente."""
    rng = np.random.default_rng(3)
    truth = rng.integers(0, 2, size=200)
    predicted = rng.integers(0, 3, size=200)
    value = weighted_macro_f1(truth, predicted, np.ones(200), len(CLASSES))
    names = np.asarray(CLASSES)
    expected = _sklearn_f1(names[truth], names[predicted])
    assert value == pytest.approx(expected, abs=1e-12)


def test_identical_predictions_give_zero_delta() -> None:
    """Retorna Δ zero e IC degenerado em zero para braços iguais."""
    labels = pd.Series([CLASSES[i % 3] for i in range(12)])
    groups = pd.Series([f"g{i // 2}" for i in range(12)])
    resampling = draw_resampling(groups, 200, 0)
    index = np.asarray([i // 2 for i in range(12)])
    result = paired_group_bootstrap(labels, labels, labels.copy(), index,
                                    np.ones(12), resampling, CLASSES, 0.95)
    assert result.delta == 0.0
    assert result.ci_delta == (0.0, 0.0)


def test_resampled_delta_matches_weighted_sklearn() -> None:
    """Confere cada reamostragem com o macro-F1 ponderado do sklearn."""
    truth = pd.Series([CLASSES[0], CLASSES[1], CLASSES[2], CLASSES[2]])
    first = pd.Series([CLASSES[0], CLASSES[1], CLASSES[2], CLASSES[0]])
    second = pd.Series([CLASSES[0], CLASSES[0], CLASSES[2], CLASSES[2]])
    index = np.asarray([0, 0, 1, 1])
    counts = np.asarray([[2, 0], [0, 2], [1, 1]], dtype=np.int64)
    resampling = Resampling(("g0", "g1"), counts)
    result = paired_group_bootstrap(truth, first, second, index, np.ones(4),
                                    resampling, CLASSES, 0.5)
    deltas = [
        _sklearn_f1(truth, first, row[index]) - _sklearn_f1(truth, second, row[index])
        for row in counts
    ]
    assert result.delta == pytest.approx(_sklearn_f1(truth, first)
                                         - _sklearn_f1(truth, second))
    expected = np.percentile(deltas, [25, 75], method="linear")
    assert result.ci_delta == pytest.approx(tuple(expected))


def test_draw_resampling_is_seeded_and_keeps_group_count() -> None:
    """Repete os sorteios com a mesma semente e reamostra G componentes."""
    groups = pd.Series(["b", "a", "c", "a"])
    first, second = draw_resampling(groups, 30, 7), draw_resampling(groups, 30, 7)
    assert first.groups == ("a", "b", "c")
    np.testing.assert_array_equal(first.counts, second.counts)
    assert (first.counts.sum(axis=1) == 3).all()


@pytest.mark.parametrize(("delta", "low", "expected"), [
    (0.1, 0.01, "supera_b1"), (0.1, 0.0, "inconclusivo"),
    (0.0, -0.1, "nulo_ou_negativo"),
])
def test_interpret_anchor(delta: float, low: float, expected: str) -> None:
    """Exige limite inferior positivo para afirmar que B2 supera B1."""
    assert interpret_anchor(delta, low) == expected


@pytest.mark.parametrize(("high", "expected"), [
    (-0.01, "queda"), (0.0, "sem_queda_conclusiva"),
])
def test_interpret_b2_linha(high: float, expected: str) -> None:
    """Só declara queda quando o IC de B2′−B2 fica inteiro abaixo de zero."""
    assert interpret_b2_linha(high) == expected
