from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

LOGGER = logging.getLogger(__name__)


def parse_overrides(values: list[str]) -> dict[str, Any]:
    """Converte lista de strings key=value em dicionario.

    Levanta ValueError se algum item nao tiver o formato esperado.
    """
    overrides: dict[str, Any] = {}
    for entry in values:
        if "=" not in entry:
            raise ValueError(f"Invalid override: {entry}")
        key, value = entry.split("=", 1)
        overrides[key] = value
    return overrides


def gather_paths(input_path: Path, allowed_extensions: set[str]) -> list[Path]:
    """Coleta paths de firmware a partir de dir, lista .txt ou path unico.

    Filtra por extensoes permitidas e ignora arquivos ocultos.
    """

    def is_allowed(path: Path) -> bool:
        return path.suffix.lower() in allowed_extensions and not path.name.startswith(
            "."
        )

    if input_path.is_dir():
        paths = [path for path in input_path.rglob("*") if path.is_file()]
        allowed = [path for path in paths if is_allowed(path)]
        LOGGER.info(
            "Filtered %s files to %s firmware candidates", len(paths), len(allowed)
        )
        return allowed
    if input_path.is_file() and input_path.suffix == ".txt":
        entries = [
            Path(line.strip())
            for line in input_path.read_text().splitlines()
            if line.strip()
        ]
        allowed = [path for path in entries if is_allowed(path)]
        LOGGER.info(
            "Filtered %s files to %s firmware candidates", len(entries), len(allowed)
        )
        return allowed
    if input_path.is_file() and not is_allowed(input_path):
        LOGGER.warning("Skipping non-firmware file: %s", input_path)
        return []
    return [input_path]
