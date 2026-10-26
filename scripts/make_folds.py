"""Gera folds agrupados a partir dos artefatos de treino da 008."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from src.cli_utils import parse_overrides  # noqa: E402
from src.dataset.partition import (  # noqa: E402
    build_partition,
    load_partition_config,
    log_summary,
    write_folds,
)

LOGGER = logging.getLogger(__name__)


def _parse_args() -> argparse.Namespace:
    """Obtém configuração, diretório processado e overrides da CLI."""
    parser = argparse.ArgumentParser(description="Gera folds agrupados")
    parser.add_argument("--config", default="configs/dataset.yaml")
    parser.add_argument("--processed-dir", default=None)
    parser.add_argument("--override", action="append", default=[])
    return parser.parse_args()


def main() -> int:
    """Orquestra leitura, validação, resumo e gravação dos folds."""
    args = _parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    try:
        config = load_partition_config(
            Path(args.config),
            parse_overrides(args.override),
            Path(args.processed_dir) if args.processed_dir is not None else None,
        )
        result = build_partition(config)
        log_summary(result)
        paths = write_folds(result, config.processed_dir)
    except (ValueError, FileNotFoundError, RuntimeError) as exc:
        LOGGER.error("Partição interrompida: %s", exc)
        return 1
    LOGGER.info("Folds salvos em %s", paths["folds"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
