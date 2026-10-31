"""Avalia os braços da spec 010 e grava o relatório final da spec 011."""

from __future__ import annotations

import argparse
import json
import logging
import shlex
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

import pandas as pd  # noqa: E402

from src.cli_utils import parse_overrides  # noqa: E402
from src.dataset import contract as c  # noqa: E402
from src.evaluation.ablation import resolve_arms  # noqa: E402
from src.evaluation.comparison import (  # noqa: E402
    Resampling,
    ablation_table,
    comparison_table,
    draw_resampling,
)
from src.evaluation.config import EvaluationConfig, load_evaluation_config  # noqa: E402
from src.evaluation.importance import permutation_by_fold  # noqa: E402
from src.evaluation.metrics import CLASSES, RunMetrics, metrics_by_repeat  # noqa: E402
from src.evaluation.report import (  # noqa: E402
    ReportBundle,
    arm_metric_tables,
    exclusion_table,
    report_meta,
    write_report,
)
from src.evaluation.runs import (  # noqa: E402
    ArmRun,
    check_current_inputs,
    check_same_inputs,
    ensure_run,
    oof_frame,
)
from src.evaluation.sensitivity import scenario_table, vendor_table  # noqa: E402
from src.models.training import (  # noqa: E402
    TrainingConfig,
    TrainingData,
    load_inputs,
    load_training_config,
)

LOGGER = logging.getLogger(__name__)
SCRIPT = "python scripts/evaluate.py"


def _parse_args() -> argparse.Namespace:
    """Obtém a configuração da avaliação e os overrides registrados."""
    parser = argparse.ArgumentParser(description="Avaliação final da spec 011")
    parser.add_argument("--config", type=Path,
                        default=Path("configs/evaluation.yaml"))
    parser.add_argument("--override", action="append", default=[])
    return parser.parse_args()


def _command() -> str:
    """Reconstrói o comando executado, sem caminho absoluto do interpretador."""
    arguments = shlex.join(sys.argv[1:])
    return f"{SCRIPT} {arguments}" if arguments else SCRIPT


def _column_changes(training: TrainingConfig) -> dict[str, str]:
    """Lê as colunas retiradas do vetor pela 008 e seus motivos."""
    path = training.processed_dir / c.META_FILENAME
    return dict(json.loads(path.read_text(encoding="utf-8"))["column_changes"])


def _ensure_runs(
    config: EvaluationConfig, training: TrainingConfig, data: TrainingData
) -> list[ArmRun]:
    """Garante a execução de cada braço e confere as entradas compartilhadas."""
    arms = resolve_arms(config, data.columns_vector, _column_changes(training))
    arm_runs = []
    for spec in arms:
        item = ensure_run(spec, config.experiment, config.scheme, training)
        LOGGER.info(
            "braço %s run_id %s modelo %s purpose %s reaproveitado %s predições %s",
            spec.arm, item.run.run_id, spec.model, item.run.meta["purpose"],
            item.reused, len(item.run.predictions),
        )
        arm_runs.append(item)
    runs = [item.run for item in arm_runs]
    check_same_inputs(runs)
    check_current_inputs(runs, data, training.processed_dir)
    return arm_runs


def _metrics(arm_runs: list[ArmRun]) -> dict[str, dict[int, RunMetrics]]:
    """Calcula as métricas OOF de cada execução e registra o macro-F1."""
    results = {}
    for item in arm_runs:
        results[item.run.run_id] = metrics_by_repeat(item.run.predictions, CLASSES)
        for repeat, metrics in results[item.run.run_id].items():
            LOGGER.info("braço %s repetição %s macro-F1 %.6f", item.spec.arm,
                        repeat, metrics.summary["macro_f1"])
    return results


def _resampling(
    config: EvaluationConfig, data: TrainingData
) -> tuple[pd.DataFrame, Resampling]:
    """Monta o quadro OOF e sorteia uma vez as reamostragens por componente."""
    oof = oof_frame(data, config.exclude_alias_vendor)
    resampling = draw_resampling(oof["group"], config.n_resamples,
                                 config.bootstrap_seed)
    LOGGER.info("bootstrap: n_firmware_id %s n_groups %s n_resamples %s seed %s "
                "ci %s", len(oof), len(resampling.groups), config.n_resamples,
                config.bootstrap_seed, config.ci)
    return oof, resampling


def _bundle(
    config: EvaluationConfig, training: TrainingConfig, data: TrainingData,
    arm_runs: list[ArmRun], results: dict[str, dict[int, RunMetrics]],
) -> ReportBundle:
    """Calcula comparações, ablações, secundárias e importância do relatório."""
    oof, resampling = _resampling(config, data)
    by_arm = {item.spec.arm: item.run for item in arm_runs}
    metrics, per_class, confusion = arm_metric_tables(arm_runs, results)
    importance = permutation_by_fold(
        by_arm["B2"], training.output_dir, data.fold_set.table, CLASSES,
        config.n_repeats, config.permutation_seed, config.ci,
    )
    return ReportBundle(
        metrics, per_class, confusion,
        comparison_table(arm_runs, oof, resampling, config),
        ablation_table(arm_runs, oof, resampling, config),
        exclusion_table(data.freeze), importance,
        vendor_table(oof, by_arm["B2"], by_arm["B1"], CLASSES),
        scenario_table(oof, by_arm["B2"], by_arm["B1"], resampling, config),
        arm_runs,
        report_meta(config, training, data, arm_runs, results, resampling),
        _command(),
    )


def main() -> int:
    """Garante as execuções, calcula a avaliação e informa o relatório criado."""
    args = _parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    try:
        config = load_evaluation_config(args.config, parse_overrides(args.override))
        training = load_training_config(config.training_config, {})
        data = load_inputs(training)
        arm_runs = _ensure_runs(config, training, data)
        results = _metrics(arm_runs)
        bundle = _bundle(config, training, data, arm_runs, results)
        print(write_report(config.output_dir, bundle))
    except (ValueError, FileNotFoundError, FileExistsError, RuntimeError) as exc:
        LOGGER.error("Avaliação interrompida: %s", exc)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
