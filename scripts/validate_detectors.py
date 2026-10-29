"""Sorteia a amostra da T13-A e gera o relatório de decisões (spec 013).

Uso:
    python scripts/validate_detectors.py sortear
    python scripts/validate_detectors.py relatorio

``sortear`` grava a planilha de anotação (texto original, acesso restrito)
e o manifesto em ``sample_dir``; recusa sobrescrever um sorteio existente.
``relatorio`` confere a planilha anotada contra o manifesto e a rubrica
congelada e grava o relatório redigido em ``reports/`` com timestamp.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from src.evidence.validation import (  # noqa: E402
    SampleResult,
    ValidationConfig,
    build_sample,
    load_annotations,
    load_validation_config,
    summarize,
    write_report,
    write_sample,
)

LOGGER = logging.getLogger(__name__)


def _parse_args() -> argparse.Namespace:
    """Obtém o subcomando e o caminho da configuração congelada."""
    parser = argparse.ArgumentParser(description="Validação dos detectores (T13-A)")
    parser.add_argument("command", choices=("sortear", "relatorio"))
    parser.add_argument("--config", default="configs/detector_validation.yaml")
    return parser.parse_args()


def _log_sample(result: SampleResult) -> None:
    """Informa semente, população e alocação por detector."""
    manifest = result.manifest
    LOGGER.info(
        "Semente %s; %d itens; %d achados do piloto excluídos",
        manifest["seed"],
        len(result.rows),
        manifest["pilot_excluded_findings"],
    )
    for detector, allocation in manifest["allocation"].items():
        LOGGER.info(
            "%s: alocação %s; redistribuição %s",
            detector,
            allocation,
            manifest["redistributed"][detector],
        )


def _run_sample(config: ValidationConfig) -> None:
    """Sorteia, registra e grava planilha e manifesto."""
    result = build_sample(config)
    _log_sample(result)
    paths = write_sample(result, config.sample_dir)
    LOGGER.info("Planilha (acesso restrito) em %s", paths["sample"])


def _run_report(config: ValidationConfig) -> None:
    """Confere anotações, decide por detector e grava o relatório."""
    rows, manifest = load_annotations(config)
    results = summarize(rows, config.decision)
    for result in results:
        LOGGER.info(
            "%s: VC %d, FP %d, IND %d → %s (%s)",
            result.detector,
            result.n_true,
            result.n_false,
            result.n_indeterminate,
            result.decision,
            result.reason,
        )
    directory = write_report(results, rows, manifest, config)
    LOGGER.info("Relatório em %s", directory)


def main() -> int:
    """Orquestra o subcomando escolhido."""
    args = _parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    try:
        config = load_validation_config(Path(args.config))
        if args.command == "sortear":
            _run_sample(config)
        else:
            _run_report(config)
    except (ValueError, FileNotFoundError, FileExistsError, RuntimeError) as exc:
        LOGGER.error("T13-A interrompida: %s", exc)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
