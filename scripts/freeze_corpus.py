"""Congela o corpus elegível em ``corpus.freeze.json`` (008/FR-018)."""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from src.dataset.corpus import (  # noqa: E402
    freeze_corpus,
    load_freeze_config,
    write_freeze,
)

LOGGER = logging.getLogger(__name__)


def _parse_args() -> argparse.Namespace:
    """Obtém configuração, diretório processado e diretório dos firmwares."""
    parser = argparse.ArgumentParser(description="Congela o corpus elegível")
    parser.add_argument("--config", default="configs/dataset.yaml")
    parser.add_argument("--processed-dir", default=None)
    parser.add_argument("--raw", default="dataset/raw")
    return parser.parse_args()


def _log_summary(manifest: dict) -> None:
    """Informa data efetiva, desvio, suporte por classe e componentes."""
    deviation = manifest["deviation"]
    LOGGER.info(
        "Congelado em %s; marco %s (%s dias)",
        deviation["effective_date"],
        deviation["milestone"],
        deviation["days_after_milestone"],
    )
    support = manifest["support"]
    LOGGER.info(
        "Corpus: %s firmware_id, %s componentes; classes %s",
        support["n_firmware_id"],
        support["n_groups"],
        support["by_class"],
    )
    LOGGER.info("Componentes com cada classe: %s", support["groups_with_class"])
    LOGGER.info(
        "Exclusões por motivo: %s", manifest["exclusions"]["excluded_by_reason"]
    )


def main() -> int:
    """Orquestra leitura, validação, montagem e gravação do congelamento."""
    args = _parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    try:
        config = load_freeze_config(
            Path(args.config),
            Path(args.processed_dir) if args.processed_dir is not None else None,
            Path(args.raw),
        )
        manifest = freeze_corpus(config, datetime.now().astimezone())
        _log_summary(manifest)
        path = write_freeze(manifest, config.processed_dir)
    except (ValueError, FileNotFoundError, FileExistsError, RuntimeError) as exc:
        LOGGER.error("Congelamento interrompido: %s", exc)
        return 1
    LOGGER.info("Congelamento salvo em %s", path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
