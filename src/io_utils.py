from __future__ import annotations

import logging
import os
from collections.abc import Iterator
from pathlib import Path

LOGGER = logging.getLogger(__name__)


def iter_file_chunks(
    path: Path, max_bytes: int, chunk_size: int = 1 << 20, nofollow: bool = False
) -> Iterator[bytes]:
    """Lê blocos limitados e impede symlinks quando solicitado."""
    flags = os.O_RDONLY | (os.O_NOFOLLOW if nofollow else 0)
    fd = os.open(path, flags)
    with os.fdopen(fd, "rb") as handle:
        remaining = max_bytes
        while remaining > 0:
            chunk = handle.read(min(remaining, chunk_size))
            if not chunk:
                break
            remaining -= len(chunk)
            yield chunk


def read_binary(path: Path, max_bytes: int | None = None) -> bytes:
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
    """Garante que a entrada seja bytes.

    Retorna b"" se receber um tipo invalido.
    """
    if isinstance(data, (bytes, bytearray)):
        return bytes(data)
    LOGGER.warning("normalize_binary received non-bytes input")
    return b""
