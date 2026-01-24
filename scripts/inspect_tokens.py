from __future__ import annotations

import argparse
import hashlib
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from pipeline.feature_extraction import load_pipeline_config
from src.features.strings import (
    extract_ascii_strings,
    limit_strings,
    strings_to_document,
    tokenize_document,
)
from src.io_utils import normalize_binary, read_binary

LOGGER = logging.getLogger(__name__)
ALLOWED_EXTENSIONS = {".bin", ".img", ".trx", ".chk", ".fw", ".rom"}


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


def extract_tokens(data: bytes, config: Any) -> List[str]:
    raw_strings = extract_ascii_strings(
        data,
        min_len=config.feature.min_string_len,
        max_string_len=config.feature.max_string_len,
    )
    strings = limit_strings(raw_strings, max_strings=config.feature.max_strings)
    doc = strings_to_document(strings, max_doc_chars=config.feature.max_doc_chars)
    return tokenize_document(doc)


def main() -> None:
    parser = argparse.ArgumentParser(description="Inspect firmware tokens")
    parser.add_argument(
        "--config",
        default="configs/feature_extraction.yaml",
        help="Path to YAML config file",
    )
    parser.add_argument("--input", required=True, help="Firmware file, dir, or list")
    parser.add_argument(
        "--limit",
        type=int,
        default=50,
        help="Max tokens per firmware",
    )
    parser.add_argument(
        "--max-docs",
        type=int,
        default=20,
        help="Max number of firmwares to print",
    )
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

    printed = 0
    for path in paths:
        if printed >= args.max_docs:
            break
        data = read_binary(path, max_bytes=config.max_bytes)
        data = normalize_binary(data)
        if not data:
            LOGGER.warning("Skipping empty firmware: %s", path)
            continue
        tokens = extract_tokens(data, config)
        firmware_id = hashlib.sha256(data).hexdigest()
        preview = tokens[: args.limit]
        LOGGER.info(
            "firmware_id=%s token_count=%s tokens=%s",
            firmware_id,
            len(tokens),
            preview,
        )
        printed += 1


if __name__ == "__main__":
    main()
