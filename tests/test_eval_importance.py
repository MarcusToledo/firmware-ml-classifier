"""Valida a importância por permutação do Extra Trees B2 (011/FR-010)."""

from __future__ import annotations

from pathlib import Path

import joblib
import pandas as pd
import pytest
from sklearn.dummy import DummyClassifier

from src.dataset import contract as c
from src.evaluation.importance import permutation_by_fold
from src.evaluation.metrics import CLASSES
from src.evaluation.runs import EvaluatedRun, load_run
from src.models.training import load_inputs, train_run
from tests.eval_fixtures import evaluation_configs


def _trained(
    tmp_path: Path, model: str = "extra_trees"
) -> tuple[EvaluatedRun, pd.DataFrame, Path]:
    """Treina o modelo pedido e retorna (execução, tabela, diretório dos runs)."""
    _, training = evaluation_configs(tmp_path)
    path = train_run(model, "principal", "grouped", None, training)
    table = load_inputs(training).fold_set.table
    return load_run(training.output_dir, path.name), table, training.output_dir


def test_informative_feature_drops_and_noise_interval_contains_zero(
    tmp_path: Path,
) -> None:
    """Atribui queda à feature que define a classe e não ao ruído aleatório."""
    run, table, runs_dir = _trained(tmp_path)
    result = permutation_by_fold(run, runs_dir, table, CLASSES, 3, 0, 0.95)
    by_feature = result.set_index("feature")
    assert set(by_feature.index) == set(run.meta["columns"])
    assert by_feature.at["entropy", "mean_drop"] > 0
    low, high = by_feature.loc["byte_mean", ["ci_low", "ci_high"]]
    assert low <= 0 <= high
    assert by_feature["n_folds"].unique().tolist() == [5]


def test_identity_run_is_rejected(tmp_path: Path) -> None:
    """Recusa calcular importância fora do Extra Trees reportado."""
    run, table, runs_dir = _trained(tmp_path, "identidade")
    with pytest.raises(ValueError, match="FR-010"):
        permutation_by_fold(run, runs_dir, table, CLASSES, 2, 0, 0.95)


def test_replaced_fold_model_is_detected(tmp_path: Path) -> None:
    """Recusa modelo de fold que não reproduz as predições gravadas."""
    run, table, runs_dir = _trained(tmp_path)
    columns = run.meta["columns"]
    constant = DummyClassifier(strategy="constant", constant=CLASSES[2])
    constant.fit(table[columns].astype("float64"), table[c.TARGET_COLUMN])
    joblib.dump(constant, runs_dir / run.run_id / "fold_0_0.joblib")
    with pytest.raises(ValueError, match="diverge das predições"):
        permutation_by_fold(run, runs_dir, table, CLASSES, 2, 0, 0.95)
