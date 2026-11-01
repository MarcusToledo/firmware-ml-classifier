"""Descreve cobertura NVD e proteções ELF segundo pré-registro da rodada v3."""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

LOGGER = logging.getLogger(__name__)


def _parse_args() -> argparse.Namespace:
    """Obtém configuração do dataset e diretório de relatórios."""
    parser = argparse.ArgumentParser(description="Cobertura NVD e proteções ELF")
    parser.add_argument("--config", type=Path, default=Path("configs/dataset.yaml"))
    parser.add_argument("--reports-dir", type=Path, default=Path("reports"))
    return parser.parse_args()


def main() -> int:
    """Orquestra leitura, análise descritiva e gravação do relatório."""
    root = Path(__file__).resolve().parents[1]
    if str(root) not in sys.path:
        sys.path.append(str(root))
    from src.dataset.nvd_coverage import describe_coverage, write_coverage
    from src.dataset.training_table import load_dataset_config, load_inputs

    args = _parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    try:
        config = load_dataset_config(args.config, {})
        inputs = load_inputs(config)
        table = describe_coverage(inputs.features, inputs.labels)
        LOGGER.info(
            "Grupos: %s; variáveis: %s",
            table["grupo"].nunique(),
            table["variavel"].nunique(),
        )
        directory = write_coverage(
            table, config.features, config.labels, args.config,
            args.reports_dir, datetime.now(timezone.utc),
        )
    except (ValueError, FileNotFoundError, FileExistsError, RuntimeError) as exc:
        LOGGER.error("Cobertura NVD interrompida: %s", exc)
        return 1
    LOGGER.info("Cobertura NVD salva em %s", directory)
    return 0


if __name__ == "__main__":
    sys.exit(main())
