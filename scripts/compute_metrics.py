"""Calcula métricas OOF das execuções da spec 010 sem alterar predições."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from src.evaluation.metrics import CLASSES, metrics_by_repeat  # noqa: E402
from src.evaluation.report_tables import write_metrics_report  # noqa: E402
from src.evaluation.runs import check_same_inputs, load_run  # noqa: E402

LOGGER = logging.getLogger(__name__)


def _parse_args() -> argparse.Namespace:
    """Obtém identidades de execução e diretórios de entrada e saída."""
    parser = argparse.ArgumentParser(description="Calcula métricas OOF por repetição")
    parser.add_argument("--run-id", action="append", required=True)
    parser.add_argument("--runs-dir", type=Path, default=Path("models/runs"))
    parser.add_argument("--output-dir", type=Path, default=Path("reports"))
    return parser.parse_args()


def main() -> int:
    """Confere as entradas, calcula indicadores e informa o relatório criado."""
    args = _parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    try:
        if len(args.run_id) != len(set(args.run_id)):
            raise ValueError("run_id repetido na avaliação")
        runs = [load_run(args.runs_dir, run_id) for run_id in args.run_id]
        check_same_inputs(runs)
        results = {run.run_id: metrics_by_repeat(run.predictions, CLASSES)
                   for run in runs}
        for run in runs:
            for repeat, metrics in results[run.run_id].items():
                LOGGER.info(
                    "run_id %s modelo %s purpose %s repetição %s predições %s "
                    "macro-F1 %.6f balanced accuracy %.6f",
                    run.run_id, run.meta["model"], run.meta["purpose"], repeat,
                    int((run.predictions["repeat"] == repeat).sum()),
                    metrics.summary["macro_f1"], metrics.summary["balanced_accuracy"],
                )
        path = write_metrics_report(args.output_dir, runs, results,
                                    {"runs_dir": args.runs_dir})
        print(path)
    except (ValueError, FileNotFoundError, FileExistsError) as exc:
        LOGGER.error("Avaliação interrompida: %s", exc)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
