"""Descreve a prevalência das colunas do vetor no corpus congelado (008/FR-020)."""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

import pandas as pd  # noqa: E402

from src.dataset.prevalence import (  # noqa: E402
    ALL_VENDORS,
    load_frozen_corpus,
    prevalence,
    write_prevalence,
)

LOGGER = logging.getLogger(__name__)


def _parse_args() -> argparse.Namespace:
    """Obtém o diretório processado e o diretório de relatórios."""
    parser = argparse.ArgumentParser(
        description="Prevalência das colunas do vetor no corpus congelado"
    )
    parser.add_argument("--processed-dir", default="dataset/processed")
    parser.add_argument("--reports-dir", default="reports")
    return parser.parse_args()


def _log_summary(table: pd.DataFrame) -> None:
    """Informa colunas constantes e prevalência total de cada coluna."""
    total = table[table["fabricante"] == ALL_VENDORS]
    constant = total[total["prevalencia"].isin([0.0, 1.0])]["coluna"].tolist()
    LOGGER.info("Colunas com prevalência 0 ou 1 no total: %s", constant)
    for row in total.itertuples(index=False):
        LOGGER.info(
            "%s: %s/%s (ausentes %s)",
            row.coluna,
            row.n_presente,
            row.n - row.n_ausente,
            row.n_ausente,
        )


def main() -> int:
    """Orquestra carga do corpus congelado, cálculo e gravação."""
    args = _parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    processed_dir = Path(args.processed_dir)
    try:
        corpus = load_frozen_corpus(processed_dir)
        table = prevalence(corpus)
        _log_summary(table)
        directory = write_prevalence(
            table,
            corpus,
            processed_dir,
            Path(args.reports_dir),
            datetime.now(timezone.utc),
        )
    except (ValueError, FileNotFoundError, FileExistsError, RuntimeError) as exc:
        LOGGER.error("Prevalência interrompida: %s", exc)
        return 1
    LOGGER.info("Prevalência salva em %s", directory)
    return 0


if __name__ == "__main__":
    sys.exit(main())
