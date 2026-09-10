from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from pipeline.feature_extraction import (  # noqa: E402
    extract_features_batch,
    load_pipeline_config,
)
from src.cli_utils import parse_overrides  # noqa: E402

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


def gather_paths(input_path: Path) -> list[Path]:
    """Coleta paths de firmware excluindo extensoes conhecidas de nao-firmware."""
    if input_path.is_dir():
        paths = [p for p in input_path.rglob("*") if p.is_file()]
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
        p
        for p in paths
        if p.suffix.lower() not in EXCLUDED_EXTENSIONS and not p.name.startswith(".")
    ]
    LOGGER.info("Filtered %d files to %d firmware candidates", len(paths), len(allowed))
    return allowed


def main() -> None:
    """CLI para extracao batch de features.

    Suporta config, input, output, format (parquet/csv), overrides e
    label-from-path.
    """
    parser = argparse.ArgumentParser(description="Extract firmware features")
    parser.add_argument(
        "--config",
        default="configs/feature_extraction.yaml",
        help="Path to YAML config file",
    )
    parser.add_argument("--input", required=True, help="Firmware file, dir, or list")
    parser.add_argument(
        "--override",
        action="append",
        default=[],
        help="Override config values (key=value)",
    )
    parser.add_argument(
        "--output",
        required=True,
        help="Output path for extracted features",
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
        help="Inferir brand/model/label a partir do path",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=None,
        help=(
            "Numero de processos paralelos (default: auto = "
            "min(num_arquivos, cpus)). Use 1 para forcar execucao sequencial."
        ),
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    config = load_pipeline_config(Path(args.config), parse_overrides(args.override))
    paths = gather_paths(Path(args.input))

    start_time = time.perf_counter()
    results = extract_features_batch(paths, config, max_workers=args.workers)
    elapsed_seconds = time.perf_counter() - start_time
    avg_seconds = elapsed_seconds / len(results) if results else 0.0
    LOGGER.info(
        "Extraction of %d file(s) completed in %.2fs (avg %.3fs/file)",
        len(results),
        elapsed_seconds,
        avg_seconds,
    )

    records: list[dict[str, Any]] = []
    if not args.label_from_path:
        for result in results:
            result.metadata["brand"] = None
            result.metadata["model"] = None
            result.metadata["label"] = None
    for result in results:
        metadata = result.metadata
        LOGGER.info(
            "path=%s read_ok=%s byte_len=%s doc2vec_used=%s error=%s",
            metadata.get("path"),
            metadata.get("read_ok"),
            metadata.get("byte_len"),
            metadata.get("doc2vec_used"),
            metadata.get("error"),
        )
        record: dict[str, Any] = {
            "firmware_id": result.firmware_id,
            **result.features,
        }
        for key, value in metadata.items():
            record[f"meta_{key}"] = value
        records.append(record)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame.from_records(records)
    if args.format == "parquet":
        df.to_parquet(output_path, index=False)
    else:
        df.to_csv(output_path, index=False)

    LOGGER.info(
        "Extraction succeeded: %d record(s) written to %s in %.2fs",
        len(records),
        output_path,
        elapsed_seconds,
    )


if __name__ == "__main__":
    main()
