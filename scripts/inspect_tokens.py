from __future__ import annotations

import argparse
import hashlib
import logging
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from pipeline.feature_extraction import load_pipeline_config  # noqa: E402
from src.cli_utils import gather_paths as gather_cli_paths  # noqa: E402
from src.cli_utils import parse_overrides  # noqa: E402
from src.features.strings import (  # noqa: E402
    extract_ascii_strings,
    limit_strings,
    strings_to_document,
    tokenize_document,
)
from src.io_utils import normalize_binary, read_binary  # noqa: E402

LOGGER = logging.getLogger(__name__)
ALLOWED_EXTENSIONS = {".bin", ".img", ".trx", ".chk", ".fw", ".rom"}


def gather_paths(input_path: Path) -> list[Path]:
    """Wrapper que filtra paths com extensoes permitidas."""
    return gather_cli_paths(input_path, ALLOWED_EXTENSIONS)


def extract_tokens(data: bytes, config: Any) -> list[str]:
    """Extrai tokens aplicando limites de strings e documento."""
    raw_strings = extract_ascii_strings(
        data,
        min_len=config.feature.min_string_len,
        max_string_len=config.feature.max_string_len,
    )
    strings = limit_strings(raw_strings, max_strings=config.feature.max_strings)
    doc = strings_to_document(strings, max_doc_chars=config.feature.max_doc_chars)
    return tokenize_document(doc)


def main() -> None:
    """CLI para inspecionar tokens com limites configuraveis."""
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
