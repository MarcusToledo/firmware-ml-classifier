from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from pipeline.feature_extraction import extract_features_batch, load_pipeline_config
from src.cli_utils import gather_paths as gather_cli_paths
from src.cli_utils import parse_overrides

ALLOWED_EXTENSIONS = {".bin", ".img", ".trx", ".chk", ".fw", ".rom"}
OUTPUT_FORMATS = {"parquet", "csv"}

LOGGER = logging.getLogger(__name__)


def gather_paths(input_path: Path) -> List[Path]:
    """Wrapper que filtra paths com extensoes permitidas."""
    return gather_cli_paths(input_path, ALLOWED_EXTENSIONS)


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
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    config = load_pipeline_config(Path(args.config), parse_overrides(args.override))
    paths = gather_paths(Path(args.input))

    results = extract_features_batch(paths, config)
    records: List[Dict[str, Any]] = []
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
        record: Dict[str, Any] = {
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


if __name__ == "__main__":
    main()
