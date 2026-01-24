from __future__ import annotations

import argparse
import hashlib
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from pipeline.feature_extraction import load_pipeline_config
from src.features.doc2vec import build_corpus, train_doc2vec, save_doc2vec
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


def build_documents(paths: List[Path], config: Any) -> List[Tuple[str, List[str]]]:
    documents: List[Tuple[str, List[str]]] = []
    for path in paths:
        data = read_binary(path, max_bytes=config.max_bytes)
        data = normalize_binary(data)
        if not data:
            LOGGER.warning("Skipping empty firmware: %s", path)
            continue
        firmware_id = hashlib.sha256(data).hexdigest()
        raw_strings = extract_ascii_strings(
            data,
            min_len=config.feature.min_string_len,
            max_string_len=config.feature.max_string_len,
        )
        strings = limit_strings(raw_strings, max_strings=config.feature.max_strings)
        doc = strings_to_document(strings, max_doc_chars=config.feature.max_doc_chars)
        tokens = tokenize_document(doc)
        if not tokens:
            LOGGER.warning("Skipping firmware with no tokens: %s", path)
            continue
        documents.append((firmware_id, tokens))
    return documents


def main() -> None:
    parser = argparse.ArgumentParser(description="Train Doc2Vec on firmware strings")
    parser.add_argument(
        "--config",
        default="configs/feature_extraction.yaml",
        help="Path to YAML config file",
    )
    parser.add_argument("--input", required=True, help="Firmware directory or list")
    parser.add_argument(
        "--output",
        default=None,
        help="Output path for Doc2Vec model (overrides config)",
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
    documents = build_documents(paths, config)

    if not documents:
        raise RuntimeError("No valid documents found for Doc2Vec training")

    corpus = build_corpus(documents)
    model = train_doc2vec(corpus, config.doc2vec)

    output_path = Path(args.output) if args.output else config.doc2vec_model_path
    if output_path is None:
        output_path = Path("models/doc2vec.model")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    save_doc2vec(model, str(output_path))
    LOGGER.info("Saved Doc2Vec model to %s", output_path)


if __name__ == "__main__":
    main()
