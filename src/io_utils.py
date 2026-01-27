from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

LOGGER = logging.getLogger(__name__)


def read_binary(path: Path, max_bytes: Optional[int] = None) -> bytes:
    """Le bytes de um arquivo de firmware.

    Limita a leitura a max_bytes quando fornecido. Retorna b"" em falha
    de leitura ou quando max_bytes <= 0.
    """
    if max_bytes is not None and max_bytes <= 0:
        LOGGER.warning("max_bytes=%s results in empty read", max_bytes)
        return b""

    try:
        if max_bytes is None:
            return path.read_bytes()
        with path.open("rb") as handle:
            return handle.read(max_bytes)
    except (OSError, ValueError) as exc:
        LOGGER.warning("Failed to read binary: %s", exc)
        return b""


def normalize_binary(data: bytes) -> bytes:
    """Ensure data is bytes; return empty bytes on invalid input."""
    if isinstance(data, (bytes, bytearray)):
        return bytes(data)
    LOGGER.warning("normalize_binary received non-bytes input")
    return b""
