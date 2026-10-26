"""Valida a tabela de treino e a cobertura dos firmwares em disco."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from src.dataset.validation import validate_artifacts  # noqa: E402

LOGGER = logging.getLogger(__name__)


def _parse_args() -> argparse.Namespace:
    """Obtém os diretórios dos artefatos e dos firmwares originais."""
    parser = argparse.ArgumentParser(description="Valida os artefatos de treino.")
    parser.add_argument("--processed-dir", type=Path, default=Path("dataset/processed"))
    parser.add_argument("--raw", type=Path, default=Path("dataset/raw"))
    return parser.parse_args()


def main() -> int:
    """Registra os problemas da tabela de treino e retorna código de saída."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    args = _parse_args()
    issues = validate_artifacts(args.processed_dir, args.raw)
    for issue in issues:
        LOGGER.error("%s", issue)
    if issues:
        return 1
    LOGGER.info("Artefato íntegro e sem órfãos: %s", args.processed_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
