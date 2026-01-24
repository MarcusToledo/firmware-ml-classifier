from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from pipeline.feature_extraction import extract_features_batch, load_pipeline_config

ALLOWED_EXTENSIONS = {".bin", ".img", ".trx", ".chk", ".fw", ".rom"}

LOGGER = logging.getLogger(__name__)


def parse_overrides(values: List[str]) -> Dict[str, Any]:
    overrides: Dict[str, Any] = {}
    for entry in values:
        if "=" not in entry:
            raise ValueError(f"Invalid override: {entry}")
        key, value = entry.split("=", 1)
        overrides[key] = value
    return overrides


def gather_paths(input_path: Path) -> List[Path]:
    def is_allowed(path: Path) -> bool:
        return path.suffix.lower() in ALLOWED_EXTENSIONS and not path.name.startswith(".")

    if input_path.is_dir():
        paths = [path for path in input_path.rglob("*") if path.is_file()]
        allowed = [path for path in paths if is_allowed(path)]
        LOGGER.info("Filtered %s files to %s firmware candidates", len(paths), len(allowed))
        return allowed
    if input_path.is_file() and input_path.suffix == ".txt":
        entries = [
            Path(line.strip())
            for line in input_path.read_text().splitlines()
            if line.strip()
        ]
        allowed = [path for path in entries if is_allowed(path)]
        LOGGER.info("Filtered %s files to %s firmware candidates", len(entries), len(allowed))
        return allowed
    if input_path.is_file() and not is_allowed(input_path):
        LOGGER.warning("Skipping non-firmware file: %s", input_path)
        return []
    return [input_path]


def main() -> None:
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
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    config = load_pipeline_config(Path(args.config), parse_overrides(args.override))
    paths = gather_paths(Path(args.input))

    results = extract_features_batch(paths, config)
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


if __name__ == "__main__":
    main()
