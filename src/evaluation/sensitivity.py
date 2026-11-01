"""Análises secundárias pré-registradas sobre as mesmas predições OOF (011/FR-019).

Nenhuma função deste módulo treina modelo ou cria folds.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.dataset import contract as c
from src.evaluation.comparison import Resampling, compare_runs
from src.evaluation.config import EvaluationConfig
from src.evaluation.metrics import RunMetrics, frame_metrics
from src.evaluation.runs import EvaluatedRun, aligned_predictions

ANALYSIS_TYPE = "secundario"
UNDEFINED_KINDS = ("precision", "recall")


def _class_rows(
    vendor: str, arm: str, run_id: str, frame: pd.DataFrame,
    metrics: RunMetrics, classes: tuple[str, ...],
) -> list[dict[str, object]]:
    """Monta uma linha por classe verdadeira com métricas e linha da confusão."""
    rows = []
    per_class = metrics.per_class.set_index("class")
    confusion = metrics.confusion.set_index(["true_class", "predicted_class"])["count"]
    for label in classes:
        undefined = [kind for kind in UNDEFINED_KINDS
                     if f"{kind}:{label}" in metrics.undefined]
        rows.append({
            "vendor": vendor, "arm": arm, "run_id": run_id, "true_class": label,
            "support": int(per_class.at[label, "support"]),
            "n_components": int(frame.loc[frame["y_true"] == label, "group"].nunique()),
            "precision": per_class.at[label, "precision"],
            "recall": per_class.at[label, "recall"], "f1": per_class.at[label, "f1"],
            "undefined": ";".join(undefined),
            **{f"pred__{predicted}": int(confusion[(label, predicted)])
               for predicted in classes},
            "analysis_type": ANALYSIS_TYPE,
        })
    return rows


def vendor_table(
    oof: pd.DataFrame, b2: EvaluatedRun, b1: EvaluatedRun, classes: tuple[str, ...]
) -> pd.DataFrame:
    """Calcula métricas por fabricante e classe de B2 e B1 (sensitivity_by_vendor)."""
    rows: list[dict[str, object]] = []
    frames = {}
    for arm, run in (("B2", b2), ("B1", b1)):
        predictions = aligned_predictions(run, oof[c.KEY_COLUMN])
        frames[arm] = predictions.assign(
            group=oof["group"].to_numpy(), vendor=oof["vendor"].to_numpy()
        )
    for vendor in sorted(oof["vendor"].unique()):
        for arm, run in (("B2", b2), ("B1", b1)):
            frame = frames[arm].loc[frames[arm]["vendor"] == vendor]
            metrics = frame_metrics(frame, classes)
            rows.extend(_class_rows(vendor, arm, run.run_id, frame, metrics, classes))
    return pd.DataFrame(rows)


def scenario_weights(
    oof: pd.DataFrame, exclude_alias_vendor: str
) -> dict[str, np.ndarray]:
    """Retorna os pesos base dos três cenários pré-registrados, em ordem fixa.

    O peso por componente é 1/n_group: cada ocorrência reamostrada de um
    componente soma 1, qualquer que seja o seu tamanho.
    """
    ones = np.ones(len(oof), dtype=np.float64)
    return {
        "todos_fabricantes": ones,
        f"sem_alias_{exclude_alias_vendor}": np.where(
            oof["has_excluded_alias"].to_numpy(), 0.0, 1.0
        ),
        "peso_componente": 1.0 / oof["n_group"].to_numpy(dtype=np.float64),
    }


def scenario_table(
    oof: pd.DataFrame, b2: EvaluatedRun, b1: EvaluatedRun, resampling: Resampling,
    config: EvaluationConfig,
) -> pd.DataFrame:
    """Compara B2 e B1 em cada cenário com as mesmas reamostragens do âncora."""
    rows = []
    for scenario, weights in scenario_weights(oof, config.exclude_alias_vendor).items():
        result = compare_runs(b2, b1, oof, resampling, weights, config.ci)
        kept = weights > 0
        rows.append({
            "scenario": scenario, "analysis_type": ANALYSIS_TYPE,
            "n_firmware_id": int(kept.sum()),
            "n_components": int(oof.loc[kept, "group"].nunique()),
            "macro_f1_b2": result.metric_a, "macro_f1_b2_ci_low": result.ci_a[0],
            "macro_f1_b2_ci_high": result.ci_a[1], "macro_f1_b1": result.metric_b,
            "macro_f1_b1_ci_low": result.ci_b[0],
            "macro_f1_b1_ci_high": result.ci_b[1], "delta": result.delta,
            "delta_ci_low": result.ci_delta[0], "delta_ci_high": result.ci_delta[1],
        })
    return pd.DataFrame(rows)
