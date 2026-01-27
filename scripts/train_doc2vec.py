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
from src.features.doc2vec import (  # noqa: E402
    build_corpus,
    save_doc2vec,
    train_doc2vec,
)
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


def build_documents(paths: list[Path], config: Any) -> list[tuple[str, list[str]]]:
    """Gera documentos tokenizados (firmware_id, tokens).

    Ignora arquivos vazios ou sem tokens.
    """
    documents: list[tuple[str, list[str]]] = []
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
    """CLI para treino de Doc2Vec com config e overrides."""
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
