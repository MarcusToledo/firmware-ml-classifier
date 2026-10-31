"""Valida as análises secundárias pré-registradas da 011/FR-019."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
import pytest

from src.evaluation.ablation import ArmSpec
from src.evaluation.comparison import comparison_table, draw_resampling
from src.evaluation.config import EvaluationConfig
from src.evaluation.metrics import CLASSES
from src.evaluation.runs import ArmRun, ensure_run, oof_frame
from src.evaluation.sensitivity import scenario_table, scenario_weights, vendor_table
from src.models.training import load_inputs
from tests.eval_fixtures import evaluation_configs

ARMS = (("B2", "extra_trees"), ("B0", "majoritario"), ("B1", "identidade"))


@dataclass(frozen=True)
class Evaluated:
    """Reúne configuração, quadro OOF e execuções de B2, B0 e B1."""

    config: EvaluationConfig
    oof: pd.DataFrame
    arm_runs: list[ArmRun]

    def run(self, arm: str):
        """Retorna a execução do braço pedido."""
        return next(item.run for item in self.arm_runs if item.spec.arm == arm)


@pytest.fixture(scope="module")
def evaluated(tmp_path_factory: pytest.TempPathFactory) -> Evaluated:
    """Treina B2, B0 e B1 uma vez no corpus sintético da avaliação."""
    config, training = evaluation_configs(
        tmp_path_factory.mktemp("sensibilidade"), {"bootstrap.n_resamples": "200"}
    )
    arm_runs = [
        ensure_run(ArmSpec(arm, arm, model, None, (), (), "nucleo"),
                   config.experiment, config.scheme, training)
        for arm, model in ARMS
    ]
    oof = oof_frame(load_inputs(training), config.exclude_alias_vendor)
    return Evaluated(config, oof, arm_runs)


def test_component_weights_sum_to_one_per_group(evaluated: Evaluated) -> None:
    """Dá peso total 1 a cada componente, inclusive ao de tamanho 2."""
    weights = scenario_weights(evaluated.oof, "tp_link")["peso_componente"]
    totals = pd.Series(weights).groupby(evaluated.oof["group"]).sum()
    assert evaluated.oof["n_group"].max() == 2
    np.testing.assert_allclose(totals.to_numpy(), 1.0)


def test_alias_scenario_zeroes_exactly_tp_link(evaluated: Evaluated) -> None:
    """Zera somente os IDs com alias do fabricante excluído."""
    weights = scenario_weights(evaluated.oof, "tp_link")["sem_alias_tp_link"]
    is_tp_link = (evaluated.oof["vendor"] == "tp_link").to_numpy()
    assert is_tp_link.any()
    np.testing.assert_array_equal(weights == 0, is_tp_link)


def test_vendor_without_class_reports_undefined_recall(evaluated: Evaluated) -> None:
    """Mostra suporte zero e recall indefinido nas classes ausentes do fabricante."""
    table = vendor_table(evaluated.oof, evaluated.run("B2"), evaluated.run("B1"),
                         CLASSES)
    assert len(table) == 3 * 2 * len(CLASSES)
    rows = table.loc[(table["vendor"] == "tp_link") & (table["arm"] == "B2")]
    absent = rows.loc[rows["true_class"].isin(CLASSES[1:])]
    assert absent["support"].tolist() == [0, 0]
    assert all("recall" in value.split(";") for value in absent["undefined"])


def test_all_vendors_scenario_reproduces_anchor(evaluated: Evaluated) -> None:
    """Reproduz Δ e IC do contraste-âncora com as mesmas reamostragens."""
    resampling = draw_resampling(evaluated.oof["group"], 200, 0)
    config = evaluated.config
    anchor = comparison_table(evaluated.arm_runs, evaluated.oof, resampling, config)
    anchor = anchor.loc[anchor["anchor"]].iloc[0]
    scenarios = scenario_table(evaluated.oof, evaluated.run("B2"),
                               evaluated.run("B1"), resampling, config)
    first = scenarios.iloc[0]
    assert first["scenario"] == "todos_fabricantes"
    for column in ("delta", "delta_ci_low", "delta_ci_high"):
        assert first[column] == anchor[column]
