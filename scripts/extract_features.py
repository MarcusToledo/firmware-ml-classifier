"""Executa extração em lote e grava tabela e achados estruturados."""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from pipeline.feature_extraction import (  # noqa: E402
    BINWALK_STATUS_TIMEOUT,
    PipelineConfig,
    PipelineResult,
    extract_features_batch,
    find_off_layout_paths,
    load_pipeline_config,
)
from src.cli_utils import parse_overrides  # noqa: E402
from src.features.unpack import (  # noqa: E402
    STATUS_TIME,
    Toolchain,
    ToolchainError,
    resolve_toolchain,
)

EXCLUDED_EXTENSIONS = {
    ".html",
    ".pdf",
    ".conf",
    ".txt",
    ".md",
    ".csv",
    ".json",
    ".zip",
    ".exe",
    ".msi",
    ".mib",
    ".xml",
}
OUTPUT_FORMATS = {"parquet", "csv"}
LOGGER = logging.getLogger(__name__)
_EXIT_INCOMPLETE = 1
_EXIT_USAGE = 2


def gather_paths(input_path: Path) -> list[Path]:
    """Coleta firmwares, ignorando extensões não binárias e arquivos ocultos."""
    if input_path.is_dir():
        paths = [path for path in input_path.rglob("*") if path.is_file()]
    elif input_path.is_file() and input_path.suffix == ".txt":
        paths = [
            Path(line.strip())
            for line in input_path.read_text().splitlines()
            if line.strip()
        ]
    elif input_path.is_file():
        paths = [input_path]
    else:
        return []
    allowed = [
        path
        for path in paths
        if path.suffix.lower() not in EXCLUDED_EXTENSIONS
        and not path.name.startswith(".")
    ]
    LOGGER.info("Filtered %d files to %d firmware candidates", len(paths), len(allowed))
    return allowed


def _parse_args() -> argparse.Namespace:
    """Obtém caminhos, opções de identidade e limites de paralelismo."""
    parser = argparse.ArgumentParser(description="Extract firmware features")
    parser.add_argument(
        "--config",
        default="configs/feature_extraction.yaml",
        help="Path to YAML config file",
    )
    parser.add_argument("--input", required=True, help="Firmware file, dir, or list")
    parser.add_argument(
        "--dataset-root", help="Raiz do dataset para paths relativos e identidade"
    )
    parser.add_argument(
        "--override",
        action="append",
        default=[],
        help="Override config values (key=value)",
    )
    parser.add_argument(
        "--output", required=True, help="Output path for extracted features"
    )
    parser.add_argument(
        "--format",
        default="parquet",
        choices=sorted(OUTPUT_FORMATS),
        help="Output format (parquet or csv)",
    )
    parser.add_argument(
        "--label-from-path",
        action="store_true",
        help="Inferir identidade a partir do path relativo à raiz",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=None,
        help="Número de processos paralelos; 1 força execução sequencial",
    )
    parser.add_argument(
        "--findings-output", help="Path opcional para achados estruturados em JSONL"
    )
    return parser.parse_args()


def _resolve_dataset_root(args: argparse.Namespace) -> Path | None:
    """Prioriza raiz explícita e só usa entrada quando for diretório."""
    if args.dataset_root:
        return Path(args.dataset_root)
    input_path = Path(args.input)
    return input_path if input_path.is_dir() else None


def _check_layout(paths: list[Path], root: Path | None, labelled: bool) -> None:
    """Rejeita paths rotulados fora da raiz ou do layout esperado."""
    if not labelled:
        return
    if root is None:
        LOGGER.error(
            "--dataset-root é obrigatório com --label-from-path quando "
            "--input é arquivo único ou lista .txt"
        )
        raise SystemExit(_EXIT_USAGE)
    invalid = find_off_layout_paths(paths, root)
    if invalid:
        for path in invalid:
            LOGGER.error("Arquivo fora do layout: %s", path)
        raise SystemExit(_EXIT_USAGE)


def _resolve_toolchain() -> Toolchain:
    """Valida versões dos extratores e interrompe lote sem ferramentas."""
    try:
        toolchain = resolve_toolchain()
    except ToolchainError as exc:
        LOGGER.error("%s", exc)
        raise SystemExit(_EXIT_USAGE) from exc
    LOGGER.info("Ferramentas: %s", toolchain.versions)
    return toolchain


def _build_records(
    results: list[PipelineResult], labelled: bool
) -> list[dict[str, Any]]:
    """Converte resultados em linhas e oculta identidade no modo inferência."""
    records: list[dict[str, Any]] = []
    for result in results:
        metadata = dict(result.metadata)
        if not labelled:
            for key in ("brand", "model", "label", "version", "version_source"):
                metadata[key] = None
        LOGGER.info(
            "path=%s read_ok=%s byte_len=%s doc2vec_used=%s error=%s",
            metadata.get("path"),
            metadata.get("read_ok"),
            metadata.get("byte_len"),
            metadata.get("doc2vec_used"),
            metadata.get("error"),
        )
        records.append(
            {
                "firmware_id": result.firmware_id,
                **result.features,
                **{f"meta_{key}": value for key, value in metadata.items()},
            }
        )
    return records


def _write_table(
    records: list[dict[str, Any]], args: argparse.Namespace, elapsed: float
) -> None:
    """Grava linhas em parquet ou CSV e registra cardinalidade e duração."""
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    table = pd.DataFrame.from_records(records)
    if args.format == "parquet":
        table.to_parquet(output, index=False)
    else:
        table.to_csv(output, index=False)
    LOGGER.info(
        "Extraction succeeded: %d record(s) written to %s in %.2fs",
        len(records),
        output,
        elapsed,
    )


def _write_findings(results: list[PipelineResult], output: str | None) -> None:
    """Grava JSONL de achados associados ao ID do firmware."""
    if output is None:
        return
    path = Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with path.open("w", encoding="utf-8") as handle:
        for result in results:
            for finding in result.findings:
                record = {
                    "firmware_id": result.firmware_id,
                    "path": result.metadata.get("path"),
                    **asdict(finding),
                }
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")
                count += 1
    LOGGER.info("Findings salvos: %d achado(s) em %s", count, path)


def _exit_if_incomplete(results: list[PipelineResult]) -> None:
    """Falha após gravar saída quando um timeout invalidou a execução."""
    timed_out = [
        str(result.metadata["path"])
        for result in results
        if result.metadata["binwalk_status"] == BINWALK_STATUS_TIMEOUT
        or result.metadata["unpack_status"] == STATUS_TIME
    ]
    if timed_out:
        LOGGER.error(
            "Execução incompleta: %d arquivo(s) com timeout/limite_tempo; "
            "rode de novo: %s",
            len(timed_out),
            timed_out,
        )
        raise SystemExit(_EXIT_INCOMPLETE)


def _load_config(args: argparse.Namespace) -> PipelineConfig:
    """Recusa configuração inválida com código de saída de uso da CLI."""
    try:
        return load_pipeline_config(Path(args.config), parse_overrides(args.override))
    except (ValueError, FileNotFoundError) as exc:
        LOGGER.error("%s", exc)
        raise SystemExit(_EXIT_USAGE) from exc


def main() -> None:
    """Orquestra validação, extração, gravação e estado de saída."""
    args = _parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    config = _load_config(args)
    paths = gather_paths(Path(args.input))
    dataset_root = _resolve_dataset_root(args)
    _check_layout(paths, dataset_root, args.label_from_path)
    toolchain = _resolve_toolchain()
    started = time.perf_counter()
    results = extract_features_batch(
        paths, config, toolchain, max_workers=args.workers, dataset_root=dataset_root
    )
    elapsed = time.perf_counter() - started
    LOGGER.info(
        "Extraction of %d file(s) completed in %.2fs (avg %.3fs/file)",
        len(results),
        elapsed,
        elapsed / len(results) if results else 0.0,
    )
    records = _build_records(results, args.label_from_path)
    _write_table(records, args, elapsed)
    _write_findings(results, args.findings_output)
    _exit_if_incomplete(results)


if __name__ == "__main__":
    main()
