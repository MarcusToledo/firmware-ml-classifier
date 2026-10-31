"""Compara braços por bootstrap pareado por componente conectado (011)."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from src.dataset import contract as c
from src.evaluation.config import EvaluationConfig
from src.evaluation.metrics import CLASSES
from src.evaluation.runs import ArmRun, EvaluatedRun, aligned_predictions

REFERENCES = ("B1", "B0")
ANCHOR = ("B2", "B1")
ABLATION_COLUMNS = (
    "arm", "run_id", "purpose", "removed_columns", "already_excluded", "n_columns",
    "macro_f1", "macro_f1_ci_low", "macro_f1_ci_high", "reference_arm",
    "reference_macro_f1", "delta", "delta_ci_low", "delta_ci_high", "interpretation",
)
B2_LINHA = "B2_linha"


@dataclass(frozen=True)
class Resampling:
    """Guarda os componentes e quantas vezes cada um entra em cada reamostragem."""

    groups: tuple[str, ...]
    counts: np.ndarray


@dataclass(frozen=True)
class PairedComparison:
    """Contém estimativas pontuais e IC de dois braços e da diferença entre eles."""

    metric_a: float
    metric_b: float
    delta: float
    ci_a: tuple[float, float]
    ci_b: tuple[float, float]
    ci_delta: tuple[float, float]


def draw_resampling(groups: pd.Series, n_resamples: int, seed: int) -> Resampling:
    """Sorteia uma vez as reamostragens de componentes, com reposição."""
    unique = tuple(sorted(set(groups)))
    size = len(unique)
    rng = np.random.default_rng(seed)
    draws = rng.integers(0, size, size=(n_resamples, size))
    counts = np.stack([np.bincount(row, minlength=size) for row in draws])
    return Resampling(unique, counts.astype(np.int64))


def group_positions(groups: pd.Series, resampling: Resampling) -> np.ndarray:
    """Retorna a posição de cada componente na reamostragem."""
    position = {group: index for index, group in enumerate(resampling.groups)}
    return np.asarray([position[group] for group in groups], dtype=np.int64)


def weighted_macro_f1(
    y_true_idx: np.ndarray, y_pred_idx: np.ndarray, weights: np.ndarray,
    n_classes: int,
) -> np.ndarray:
    """Calcula macro-F1 com matriz de confusão ponderada e divisão por zero igual a 0.

    Retorna escalar para pesos 1-D e vetor (B,) para pesos (B, n_ids).
    """
    cells = y_true_idx * n_classes + y_pred_idx
    indicator = np.zeros((len(cells), n_classes * n_classes), dtype=np.float64)
    indicator[np.arange(len(cells)), cells] = 1.0
    matrix = (np.atleast_2d(weights) @ indicator).reshape(-1, n_classes, n_classes)
    true_positive = np.diagonal(matrix, axis1=1, axis2=2)
    denominator = matrix.sum(axis=2) + matrix.sum(axis=1)
    f1 = np.divide(
        2 * true_positive, denominator,
        out=np.zeros_like(true_positive), where=denominator > 0,
    )
    result = f1.mean(axis=1)
    return result[0] if np.ndim(weights) == 1 else result


def _label_index(labels: pd.Series, classes: tuple[str, ...]) -> np.ndarray:
    """Converte rótulos em índices das classes fixas.

    Levanta ValueError para rótulo fora das classes.
    """
    unknown = sorted(set(labels) - set(classes))
    if unknown:
        raise ValueError(f"rótulos fora das classes: {unknown}")
    return np.asarray([classes.index(label) for label in labels], dtype=np.int64)


def _interval(values: np.ndarray, ci: float) -> tuple[float, float]:
    """Retorna o intervalo percentil das reamostragens."""
    low, high = np.percentile(
        values, [100 * (1 - ci) / 2, 100 * (1 + ci) / 2], method="linear"
    )
    return float(low), float(high)


def paired_group_bootstrap(
    y_true: pd.Series, pred_a: pd.Series, pred_b: pd.Series,
    group_index: np.ndarray, base_weights: np.ndarray, resampling: Resampling,
    classes: tuple[str, ...], ci: float,
) -> PairedComparison:
    """Compara macro-F1 de dois braços nas mesmas reamostragens de componentes."""
    truth = _label_index(y_true, classes)
    first, second = _label_index(pred_a, classes), _label_index(pred_b, classes)
    weights = resampling.counts[:, group_index] * base_weights
    point_a = float(weighted_macro_f1(truth, first, base_weights, len(classes)))
    point_b = float(weighted_macro_f1(truth, second, base_weights, len(classes)))
    sample_a = weighted_macro_f1(truth, first, weights, len(classes))
    sample_b = weighted_macro_f1(truth, second, weights, len(classes))
    return PairedComparison(
        point_a, point_b, point_a - point_b, _interval(sample_a, ci),
        _interval(sample_b, ci), _interval(sample_a - sample_b, ci),
    )


def compare_runs(
    run_a: EvaluatedRun, run_b: EvaluatedRun, oof: pd.DataFrame,
    resampling: Resampling, base_weights: np.ndarray, ci: float,
) -> PairedComparison:
    """Alinha as predições de dois braços aos IDs do OOF e os compara.

    Levanta ValueError se os rótulos verdadeiros das execuções divergem.
    """
    first = aligned_predictions(run_a, oof[c.KEY_COLUMN])
    second = aligned_predictions(run_b, oof[c.KEY_COLUMN])
    if first["y_true"].tolist() != second["y_true"].tolist():
        raise ValueError(
            f"y_true diverge entre run_id {run_a.run_id} e {run_b.run_id}"
        )
    return paired_group_bootstrap(
        first["y_true"], first["y_pred"], second["y_pred"],
        group_positions(oof["group"], resampling), base_weights, resampling,
        CLASSES, ci,
    )


def interpret_anchor(delta: float, ci_low: float) -> str:
    """Classifica o contraste B2−B1 segundo o sinal de Δ e o limite inferior."""
    if delta <= 0:
        return "nulo_ou_negativo"
    return "supera_b1" if ci_low > 0 else "inconclusivo"


def interpret_b2_linha(ci_high: float) -> str:
    """Classifica B2′−B2 como queda só quando o IC inteiro fica abaixo de zero."""
    return "queda" if ci_high < 0 else "sem_queda_conclusiva"


def _comparison_row(
    arm: ArmRun, reference: ArmRun, result: PairedComparison
) -> dict[str, object]:
    """Monta uma linha de comparison.csv a partir da comparação pareada."""
    anchor = (arm.spec.arm, reference.spec.arm) == ANCHOR
    return {
        "arm": arm.spec.arm, "model": arm.spec.model, "run_id": arm.run.run_id,
        "purpose": arm.run.meta["purpose"], "reference_arm": reference.spec.arm,
        "reference_run_id": reference.run.run_id, "macro_f1": result.metric_a,
        "macro_f1_ci_low": result.ci_a[0], "macro_f1_ci_high": result.ci_a[1],
        "reference_macro_f1": result.metric_b, "delta": result.delta,
        "delta_ci_low": result.ci_delta[0], "delta_ci_high": result.ci_delta[1],
        "anchor": anchor,
        "interpretation": (
            interpret_anchor(result.delta, result.ci_delta[0]) if anchor else ""
        ),
    }


def comparison_table(
    arm_runs: list[ArmRun], oof: pd.DataFrame, resampling: Resampling,
    config: EvaluationConfig,
) -> pd.DataFrame:
    """Compara cada braço do núcleo com B1 e com B0 (comparison.csv)."""
    by_arm = {item.spec.arm: item for item in arm_runs}
    nucleus = [item for item in arm_runs if item.spec.kind == "nucleo"]
    ones = np.ones(len(oof), dtype=np.float64)
    rows = []
    for reference_arm in REFERENCES:
        reference = by_arm[reference_arm]
        for arm in nucleus:
            if arm.spec.arm == reference_arm:
                continue
            result = compare_runs(
                arm.run, reference.run, oof, resampling, ones, config.ci
            )
            rows.append(_comparison_row(arm, reference, result))
    return pd.DataFrame(rows)


def ablation_table(
    arm_runs: list[ArmRun], oof: pd.DataFrame, resampling: Resampling,
    config: EvaluationConfig,
) -> pd.DataFrame:
    """Compara cada ablação com B2 nas mesmas reamostragens (ablation.csv)."""
    reference = next(item for item in arm_runs if item.spec.arm == ANCHOR[0])
    ones = np.ones(len(oof), dtype=np.float64)
    rows = []
    for arm in (item for item in arm_runs if item.spec.kind == "ablation"):
        result = compare_runs(arm.run, reference.run, oof, resampling, ones, config.ci)
        rows.append({
            "arm": arm.spec.arm, "run_id": arm.run.run_id,
            "purpose": arm.run.meta["purpose"],
            "removed_columns": ";".join(arm.spec.removed),
            "already_excluded": ";".join(arm.spec.already_excluded),
            "n_columns": len(arm.spec.columns or []),
            "macro_f1": result.metric_a, "macro_f1_ci_low": result.ci_a[0],
            "macro_f1_ci_high": result.ci_a[1], "reference_arm": reference.spec.arm,
            "reference_macro_f1": result.metric_b, "delta": result.delta,
            "delta_ci_low": result.ci_delta[0], "delta_ci_high": result.ci_delta[1],
            "interpretation": (
                interpret_b2_linha(result.ci_delta[1])
                if arm.spec.arm == B2_LINHA else ""
            ),
        })
    return pd.DataFrame(rows, columns=ABLATION_COLUMNS)
