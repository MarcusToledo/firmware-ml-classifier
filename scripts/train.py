"""Executa treino reprodutível da spec 010 nos folds congelados."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from src.cli_utils import parse_overrides  # noqa: E402
from src.models.training import (  # noqa: E402
    MODELS,
    load_training_config,
    train_run,
)

LOGGER = logging.getLogger(__name__)


def _parse_args() -> argparse.Namespace:
    """Obtém modelo, configuração e subconjunto opcional de colunas."""
    parser = argparse.ArgumentParser(description="Treina modelos nos folds congelados")
    parser.add_argument("--model", required=True, choices=(*MODELS, "all"))
    parser.add_argument("--experiment", default="principal", choices=("principal",))
    parser.add_argument("--scheme", default="grouped", choices=("grouped",))
    parser.add_argument("--columns-file", type=Path)
    parser.add_argument("--config", type=Path, default=Path("configs/training.yaml"))
    parser.add_argument("--override", action="append", default=[])
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def _read_columns_file(path: Path | None) -> list[str] | None:
    """Lê uma coluna por linha, ignorando linhas vazias."""
    if path is None:
        return None
    lines = path.read_text(encoding="utf-8").splitlines()
    return [line.strip() for line in lines if line.strip()]


def main() -> int:
    """Executa modelos em ordem fixa e informa cada identidade calculada."""
    args = _parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    try:
        if args.model == "all" and args.columns_file is not None:
            raise ValueError("--columns-file não se aplica a --model all")
        config = load_training_config(args.config, parse_overrides(args.override))
        columns = _read_columns_file(args.columns_file)
        for model in MODELS if args.model == "all" else (args.model,):
            path = train_run(
                model, args.experiment, args.scheme, columns, config, args.force
            )
            print(f"{model}\t{path.name}")
    except (ValueError, FileNotFoundError, FileExistsError, RuntimeError) as exc:
        LOGGER.error("Treino interrompido: %s", exc)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
