"""Monta e grava o relatório final da avaliação: CSV, PNG e report.md (011)."""

from __future__ import annotations

import json
import platform
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import joblib
import matplotlib
import numpy as np
import pandas as pd
import sklearn
import yaml

from src.dataset import contract as c
from src.evaluation.comparison import Resampling
from src.evaluation.config import EvaluationConfig
from src.evaluation.figures import plot_confusion, plot_deltas, plot_importance
from src.evaluation.metrics import CLASSES, RunMetrics
from src.evaluation.report_tables import metric_rows
from src.evaluation.runs import ArmRun
from src.models.training import TrainingConfig, TrainingData
from src.run_metadata import code_commit, file_sha256

INTERPRETATIONS = {
    "supera_b1": (
        "Δ positivo com IC 95% acima de zero: B2 supera B1 neste corpus e "
        "protocolo; não demonstra independência de identidade indireta."
    ),
    "inconclusivo": (
        "Δ positivo com IC 95% tocando ou cruzando zero: resultado inconclusivo."
    ),
    "nulo_ou_negativo": (
        "Δ nulo ou negativo: resultado válido; não demonstra ausência de sinal "
        "nem equivalência quando o IC cruza zero."
    ),
    "queda": (
        "B2′ perde desempenho (IC 95% de B2′−B2 abaixo de zero): count_urls "
        "contribui para as predições, compatível com identidade embutida nas "
        "strings, sem comprová-la."
    ),
    "sem_queda_conclusiva": (
        "IC 95% de B2′−B2 inclui zero ou está acima: sem queda conclusiva "
        "atribuível a count_urls."
    ),
}
IMPORTANCE_NOTE = (
    "A importância por permutação mede a contribuição de cada feature às "
    "predições deste modelo nos folds de teste; não tem interpretação causal. "
    "Features correlacionadas dividem ou mascaram a queda."
)
SECONDARY_NOTE = (
    "Análises pré-registradas em 29/10/2026, condicionais, sobre as mesmas "
    "predições OOF, sem novo treino nem novos folds; não substituem o "
    "contraste-âncora. O cenário sem alias TP-Link não equivale a treinar sem "
    "TP-Link nem a generalizar para fabricante novo (FR-014 Proposto)."
)
REDACTION_NOTE = (
    "O pacote não copia predições por firmware, strings, achados nem "
    "credenciais; as predições ficam em models/runs/<run_id>/predictions.parquet, "
    "verificáveis pelo SHA256."
)
OVERLAP_NOTE = (
    "Os motivos se sobrepõem: um firmware_id pode ser contado em mais de um "
    "motivo, e a soma das colunas pode exceder o número de IDs excluídos."
)
PROPOSTO_NOT_EXECUTED = [
    "FR-013", "FR-014", "FR-015 B3/B4", "FR-016 B6", "FR-017 binário",
    "FR-018 RF/MDI",
]
METRIC_COLUMNS = (
    "run_id", "arm", "model", "experiment", "scheme", "purpose", "repeat",
    "macro_f1", "balanced_accuracy", "macro_precision", "macro_recall",
    "n_predictions", "n_undefined",
)
PER_CLASS_COLUMNS = (
    "run_id", "arm", "purpose", "repeat", "class", "precision", "recall", "f1",
    "support",
)
CONFUSION_COLUMNS = (
    "run_id", "arm", "purpose", "repeat", "true_class", "predicted_class", "count",
)
RESULT_ARMS = ("B2", "RF")
BASELINE_ARMS = ("B0", "BR")
CSV_OPTIONS: dict[str, Any] = {
    "index": False, "float_format": "%.6f", "lineterminator": "\n"
}


@dataclass(frozen=True)
class ReportBundle:
    """Reúne tabelas, execuções, manifesto e comando do relatório."""

    metrics: pd.DataFrame
    per_class: pd.DataFrame
    confusion: pd.DataFrame
    comparison: pd.DataFrame
    ablation: pd.DataFrame
    exclusions: pd.DataFrame
    importance: pd.DataFrame
    sensitivity_by_vendor: pd.DataFrame
    sensitivity_comparison: pd.DataFrame
    arm_runs: list[ArmRun]
    meta: dict[str, Any]
    command: str


def exclusion_table(freeze: dict[str, Any]) -> pd.DataFrame:
    """Retorna exclusões por motivo e proporção de indeterminado por fabricante."""
    exclusions = freeze["exclusions"]
    by_reason = exclusions["excluded_by_vendor_reason"]
    totals = exclusions["indeterminate_by_vendor"]
    rows = []
    for vendor in sorted(totals):
        indeterminate, total = totals[vendor]["indeterminado"], totals[vendor]["total"]
        reasons = by_reason.get(vendor, {})
        rows.append({
            "vendor": vendor,
            "falha_extracao": int(reasons.get("falha_extracao", 0)),
            "terceiros": int(reasons.get("terceiros", 0)),
            "indeterminado": int(indeterminate), "total_ids": int(total),
            "proporcao_indeterminado": indeterminate / total if total else 0.0,
        })
    return pd.DataFrame(rows)


def arm_metric_tables(
    arm_runs: list[ArmRun], results: dict[str, dict[int, RunMetrics]]
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Retorna métricas, métricas por classe e confusão na ordem dos braços.

    Reaproveita as linhas da T05 e acrescenta a coluna arm.
    """
    tables: tuple[list[dict], list[dict], list[dict]] = ([], [], [])
    for item in arm_runs:
        run_id = item.run.run_id
        parts = metric_rows([item.run], {run_id: results[run_id]})
        for target, rows in zip(tables, parts):
            target.extend({**row, "arm": item.spec.arm} for row in rows)
    return (
        pd.DataFrame(tables[0], columns=METRIC_COLUMNS),
        pd.DataFrame(tables[1], columns=PER_CLASS_COLUMNS),
        pd.DataFrame(tables[2], columns=CONFUSION_COLUMNS),
    )


def _input_hashes(
    config: EvaluationConfig, training: TrainingConfig, data: TrainingData
) -> dict[str, str]:
    """Retorna os SHA256 das entradas congeladas e das configurações."""
    hashes = {
        key: data.inputs[key]["sha256"]
        for key in ("table", "provenance", "folds", "corpus_freeze")
    }
    hashes.update(
        training_table_meta=file_sha256(training.processed_dir / c.META_FILENAME),
        evaluation_config=file_sha256(config.config_path),
        training_config=file_sha256(training.config_path),
    )
    return hashes


def _versions() -> dict[str, str]:
    """Retorna as versões do Python e das bibliotecas usadas."""
    return {
        "python": platform.python_version(), "numpy": np.__version__,
        "pandas": pd.__version__, "scikit-learn": sklearn.__version__,
        "matplotlib": matplotlib.__version__, "pyyaml": yaml.__version__,
        "joblib": joblib.__version__,
    }


def report_meta(
    config: EvaluationConfig, training: TrainingConfig, data: TrainingData,
    arm_runs: list[ArmRun], results: dict[str, dict[int, RunMetrics]],
    resampling: Resampling,
) -> dict[str, Any]:
    """Monta o manifesto do relatório, sem created_at nem reaproveitamento."""
    runs = {item.run.run_id: {
        "arm": item.spec.arm, "model": item.run.meta["model"],
        "purpose": item.run.meta["purpose"], "commit": item.run.meta["commit"],
        "predictions_path": str(
            training.output_dir / item.run.run_id / "predictions.parquet"
        ),
        "predictions_sha256": item.run.predictions_sha256,
        "n_predictions": len(item.run.predictions),
    } for item in arm_runs}
    per_run = {item.run.run_id: sorted(results[item.run.run_id].items())
               for item in arm_runs}
    return {
        "commit": code_commit(),
        "arms": {item.spec.arm: item.run.run_id for item in arm_runs},
        "runs": runs, "inputs": _input_hashes(config, training, data),
        "config": config.effective, "training_config": training.effective,
        "versions": _versions(), "classes": list(CLASSES), "zero_division": 0,
        "undefined": {run_id: {repeat: m.undefined for repeat, m in items}
                      for run_id, items in per_run.items()},
        "folds_missing_class": {
            run_id: {repeat: m.folds_missing_class for repeat, m in items}
            for run_id, items in per_run.items()
        },
        "arms_not_executed": [], "proposto_not_executed": PROPOSTO_NOT_EXECUTED,
        "resampling": {
            "n_resamples": config.n_resamples, "seed": config.bootstrap_seed,
            "ci": config.ci, "n_groups": len(resampling.groups),
        },
    }


def _cell(value: Any) -> str:
    """Formata um valor de tabela Markdown com três casas para números reais."""
    if isinstance(value, (bool, np.bool_)):
        return str(bool(value))
    if isinstance(value, (float, np.floating)):
        return "" if np.isnan(value) else f"{value:.3f}"
    return str(value)


def _md_table(frame: pd.DataFrame, columns: list[str]) -> list[str]:
    """Retorna as linhas de uma tabela Markdown com as colunas pedidas."""
    lines = ["| " + " | ".join(columns) + " |", "|" + "---|" * len(columns)]
    for row in frame[columns].itertuples(index=False, name=None):
        lines.append("| " + " | ".join(_cell(value) for value in row) + " |")
    return [*lines, ""]


def command_rows(bundle: ReportBundle, artifacts: list[str]) -> pd.DataFrame:
    """Retorna o comando que reconstrói cada artefato do relatório e das execuções.

    O arquivo de colunas das ablações fica no diretório do relatório.
    """
    rows = [{"artifact": name, "command": bundle.command} for name in artifacts]
    training_config = bundle.meta["config"]["training_config"]
    for item in bundle.arm_runs:
        command = (
            f"python scripts/train.py --model {item.spec.model} --experiment "
            f"principal --scheme grouped --config {training_config}"
        )
        if item.spec.kind == "ablation":
            command += f" --columns-file <relatório>/columns_{item.spec.arm}.txt"
        rows.append({
            "artifact": bundle.meta["runs"][item.run.run_id]["predictions_path"],
            "command": command,
        })
    return pd.DataFrame(rows, columns=["artifact", "command"])


def _section_runs(bundle: ReportBundle) -> list[str]:
    """Lista braços, execuções e hashes das predições avaliadas."""
    frame = pd.DataFrame([{
        "braço": item.spec.arm, "rótulo": item.spec.label,
        "modelo": item.spec.model, "purpose": item.run.meta["purpose"],
        "run_id": item.run.run_id, "sha256 predições": item.run.predictions_sha256,
    } for item in bundle.arm_runs])
    return ["## Execuções avaliadas", "", *_md_table(frame, list(frame.columns))]


def _metric_section(
    bundle: ReportBundle, title: str, arms: tuple[str, ...]
) -> list[str]:
    """Retorna uma seção com as métricas OOF dos braços pedidos."""
    frame = bundle.metrics.loc[bundle.metrics["arm"].isin(arms)]
    columns = ["arm", "model", "purpose", "macro_f1", "balanced_accuracy",
               "macro_precision", "macro_recall", "n_predictions"]
    return [f"## {title}", "", *_md_table(frame, columns)]


def _section_results(bundle: ReportBundle) -> list[str]:
    """Retorna o resultado reportado de B2 e RF, com a matriz de confusão de B2."""
    return [
        *_metric_section(bundle, "Resultado: B2 e Random Forest", RESULT_ARMS),
        "![Matriz de confusão B2](confusion_B2.png)", "",
    ]


def _section_anchor(bundle: ReportBundle) -> list[str]:
    """Retorna B1 como diagnóstico, o contraste-âncora e as demais comparações."""
    anchor = bundle.comparison.loc[bundle.comparison["anchor"]].iloc[0]
    others = bundle.comparison.loc[~bundle.comparison["anchor"]]
    columns = ["arm", "reference_arm", "macro_f1", "reference_macro_f1", "delta",
               "delta_ci_low", "delta_ci_high"]
    return [
        *_metric_section(
            bundle, "Comparador obrigatório B1 e contraste-âncora", ("B1",)
        ),
        f"Δ = macro-F1(B2) − macro-F1(B1) = {anchor['delta']:.3f} "
        f"(IC 95% {anchor['delta_ci_low']:.3f} a {anchor['delta_ci_high']:.3f}).",
        "", INTERPRETATIONS[anchor["interpretation"]], "",
        "![Matriz de confusão B1](confusion_B1.png)", "",
        "Demais comparações (IC 95% por bootstrap pareado por componente):", "",
        *_md_table(others, columns),
        "![Δ e IC 95%](deltas.png)", "",
    ]


def _section_ablations(bundle: ReportBundle) -> list[str]:
    """Retorna as ablações comparadas com B2 e a interpretação de B2′."""
    columns = ["arm", "removed_columns", "already_excluded", "n_columns",
               "macro_f1", "delta", "delta_ci_low", "delta_ci_high"]
    lines = ["## Ablações", "", *_md_table(bundle.ablation, columns)]
    for text in bundle.ablation["interpretation"]:
        if text:
            lines.extend([INTERPRETATIONS[text], ""])
    return lines


def _missing_classes(by_vendor: pd.DataFrame) -> list[str]:
    """Lista fabricantes sem alguma das três classes verdadeiras."""
    rows = by_vendor.loc[(by_vendor["arm"] == "B2") & (by_vendor["support"] == 0)]
    lines = [
        f"- {vendor}: sem {', '.join(group['true_class'])}"
        for vendor, group in rows.groupby("vendor", sort=True)
    ]
    return lines or ["- todos os fabricantes têm as três classes"]


def _section_secondary(bundle: ReportBundle) -> list[str]:
    """Retorna os cenários secundários com a ressalva pré-registrada."""
    columns = ["scenario", "n_firmware_id", "n_components", "macro_f1_b2",
               "macro_f1_b1", "delta", "delta_ci_low", "delta_ci_high"]
    return [
        "## Análises secundárias pré-registradas (FR-019)", "", SECONDARY_NOTE, "",
        *_md_table(bundle.sensitivity_comparison, columns),
        "Fabricantes sem as três classes (métricas por fabricante em "
        "sensitivity_by_vendor.csv):", "",
        *_missing_classes(bundle.sensitivity_by_vendor), "",
    ]


def _section_exclusions(bundle: ReportBundle) -> list[str]:
    """Retorna exclusões e proporção de indeterminado por fabricante."""
    return [
        "## Exclusões e indeterminado por fabricante", "", OVERLAP_NOTE, "",
        *_md_table(bundle.exclusions, list(bundle.exclusions.columns)),
    ]


def _section_importance(bundle: ReportBundle) -> list[str]:
    """Retorna a importância por permutação do Extra Trees B2."""
    columns = ["feature", "mean_drop", "std_drop", "ci_low", "ci_high"]
    return [
        "## Importância por permutação (Extra Trees B2)", "", IMPORTANCE_NOTE, "",
        *_md_table(bundle.importance, columns),
        "![Importância por permutação](importance.png)", "",
    ]


def _section_reconstruction(commands: pd.DataFrame) -> list[str]:
    """Retorna os comandos de reconstrução e a nota de redação."""
    return [
        "## Reconstrução", "", *_md_table(commands, ["artifact", "command"]),
        REDACTION_NOTE, "",
    ]


def render_markdown(bundle: ReportBundle, commands: pd.DataFrame) -> str:
    """Monta o report.md com resultados antes de B1 e das ablações (FR-008)."""
    lines = [
        "# Avaliação final (spec 011)", "",
        *_section_runs(bundle), *_section_results(bundle),
        *_metric_section(bundle, "Baselines", BASELINE_ARMS),
        *_section_anchor(bundle), *_section_ablations(bundle),
        *_section_secondary(bundle), *_section_exclusions(bundle),
        *_section_importance(bundle), *_section_reconstruction(commands),
    ]
    return "\n".join(lines).rstrip("\n") + "\n"


def delta_rows(bundle: ReportBundle) -> pd.DataFrame:
    """Retorna Δ e IC das comparações contra B1, ablações e cenários."""
    labels = {item.spec.arm: item.spec.label for item in bundle.arm_runs}
    columns = ["delta", "delta_ci_low", "delta_ci_high"]
    versus_b1 = bundle.comparison.loc[bundle.comparison["reference_arm"] == "B1"]
    parts = [
        versus_b1.assign(label=[f"{labels[a]} − B1" for a in versus_b1["arm"]]),
        bundle.ablation.assign(
            label=[f"{labels[a]} − B2" for a in bundle.ablation["arm"]]
        ),
        bundle.sensitivity_comparison.assign(label=[
            f"B2 − B1 ({s})" for s in bundle.sensitivity_comparison["scenario"]
        ]),
    ]
    return pd.concat([part[["label", *columns]] for part in parts], ignore_index=True)


def _tables(bundle: ReportBundle) -> dict[str, pd.DataFrame]:
    """Associa cada CSV do relatório à sua tabela."""
    return {
        "metrics.csv": bundle.metrics, "metrics_per_class.csv": bundle.per_class,
        "confusion.csv": bundle.confusion, "comparison.csv": bundle.comparison,
        "ablation.csv": bundle.ablation, "exclusions.csv": bundle.exclusions,
        "importance.csv": bundle.importance,
        "sensitivity_by_vendor.csv": bundle.sensitivity_by_vendor,
        "sensitivity_comparison.csv": bundle.sensitivity_comparison,
    }


def _write_figures(destination: Path, bundle: ReportBundle) -> list[str]:
    """Grava as figuras do relatório e retorna seus nomes."""
    for arm in ("B2", "B1"):
        run_id = bundle.meta["arms"][arm]
        rows = bundle.confusion.loc[bundle.confusion["run_id"] == run_id]
        plot_confusion(rows, CLASSES, f"Matriz de confusão {arm}",
                       destination / f"confusion_{arm}.png")
    plot_deltas(delta_rows(bundle), destination / "deltas.png")
    plot_importance(bundle.importance, destination / "importance.png")
    return ["confusion_B2.png", "confusion_B1.png", "deltas.png", "importance.png"]


def write_report(output_root: Path, bundle: ReportBundle) -> Path:
    """Grava o relatório em diretório UTC novo, sem sobrescrever outro.

    Levanta FileExistsError se o diretório do instante já existe.
    """
    created_at = datetime.now(timezone.utc)
    destination = output_root / created_at.strftime("%Y%m%dT%H%M%SZ")
    destination.mkdir(parents=True, exist_ok=False)
    tables = _tables(bundle)
    for name, frame in tables.items():
        frame.to_csv(destination / name, **CSV_OPTIONS)
    for item in bundle.arm_runs:
        if item.spec.kind == "ablation":
            (destination / f"columns_{item.spec.arm}.txt").write_text(
                "".join(f"{name}\n" for name in item.spec.columns or []),
                encoding="utf-8",
            )
    figures = _write_figures(destination, bundle)
    artifacts = [*tables, "commands.csv", *figures, "report.md"]
    commands = command_rows(bundle, artifacts)
    commands.to_csv(destination / "commands.csv", **CSV_OPTIONS)
    (destination / "report.md").write_text(
        render_markdown(bundle, commands), encoding="utf-8"
    )
    manifest = {**bundle.meta, "created_at": created_at.isoformat(timespec="seconds")}
    (destination / "report.meta.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return destination
