"""Prepara a tabela de treino e grava seus artefatos."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from src.cli_utils import parse_overrides  # noqa: E402
from src.dataset.training_table import (  # noqa: E402
    build_training_table,
    load_dataset_config,
    log_summary,
    write_artifacts,
)

LOGGER = logging.getLogger(__name__)


def _parse_args() -> argparse.Namespace:
    """Obtém caminhos e substituições da configuração da preparação."""
    parser = argparse.ArgumentParser(description="Prepara a tabela de treino")
    parser.add_argument("--config", default="configs/dataset.yaml")
    parser.add_argument("--features")
    parser.add_argument("--labels")
    parser.add_argument("--output-dir")
    parser.add_argument("--override", action="append", default=[])
    return parser.parse_args()


def _config_overrides(args: argparse.Namespace) -> dict[str, Any]:
    """Aplica flags explícitas depois dos overrides pontuados da CLI."""
    overrides = parse_overrides(args.override)
    for flag, key in (
        (args.features, "features"),
        (args.labels, "labels"),
        (args.output_dir, "output_dir"),
    ):
        if flag is not None:
            overrides[key] = flag
    return overrides


def main() -> int:
    """Orquestra preparação, resumo e gravação dos artefatos."""
    args = _parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    try:
        config = load_dataset_config(Path(args.config), _config_overrides(args))
        prepared = build_training_table(config)
        log_summary(prepared)
        paths = write_artifacts(prepared, config.output_dir)
    except (ValueError, FileNotFoundError) as exc:
        LOGGER.error("Preparação interrompida: %s", exc)
        return 1
    LOGGER.info("Tabela de treino salva em %s", paths["table"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
