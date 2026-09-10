from __future__ import annotations

import re
from collections.abc import Iterable

ASCII_MIN = 32
ASCII_MAX = 126

# Regex sobre bytes (executado em C via re) casando runs de ASCII imprimivel.
# Substitui o loop byte-a-byte em Python puro, que dominava o tempo de
# extracao em firmwares grandes (ver perfil em pipeline/feature_extraction.py).
_PRINTABLE_RUN_RE = re.compile(
    b"[" + bytes([ASCII_MIN]) + b"-" + bytes([ASCII_MAX]) + b"]+"
)


def extract_ascii_strings(
    data: bytes,
    min_len: int = 4,
    max_string_len: int = 1024,
) -> list[str]:
    """Extrai strings ASCII imprimiveis (32-126) de bytes.

    Ignora strings menores que min_len e trunca cada string em
    max_string_len. Retorna lista vazia para entrada vazia.
    """
    if not data:
        return []
    min_len = max(1, min_len)
    max_string_len = max(1, max_string_len)
    strings: list[str] = []
    for match in _PRINTABLE_RUN_RE.finditer(data):
        run = match.group()
        if len(run) >= min_len:
            strings.append(run[:max_string_len].decode("ascii"))
    return strings


def limit_strings(strings: Iterable[str], max_strings: int) -> list[str]:
    """Limita a lista de strings a max_strings elementos.

    Retorna lista vazia se max_strings <= 0.
    """
    if max_strings <= 0:
        return []
    limited: list[str] = []
    for value in strings:
        limited.append(value)
        if len(limited) >= max_strings:
            break
    return limited


def strings_to_document(strings: Iterable[str], max_doc_chars: int) -> str:
    """Concatena strings com \n e trunca em max_doc_chars.

    Retorna string vazia se max_doc_chars <= 0.
    """
    if max_doc_chars <= 0:
        return ""
    doc = "\n".join(strings)
    return doc[:max_doc_chars]


def tokenize_document(doc: str) -> list[str]:
    """Divide documento por whitespace e remove tokens vazios."""
    return [token for token in doc.split() if token]
