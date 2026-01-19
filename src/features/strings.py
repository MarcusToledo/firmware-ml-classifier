from __future__ import annotations

from typing import Iterable, List

ASCII_MIN = 32
ASCII_MAX = 126


def extract_ascii_strings(
    data: bytes,
    min_len: int = 4,
    max_string_len: int = 1024,
) -> List[str]:
    """Extract printable ASCII strings from byte data.

    Only characters in ASCII range 32-126 are considered.
    """
    if not data:
        return []
    min_len = max(1, min_len)
    max_string_len = max(1, max_string_len)
    current: List[int] = []
    strings: List[str] = []
    for value in data:
        if ASCII_MIN <= value <= ASCII_MAX:
            current.append(value)
            continue
        if len(current) >= min_len:
            decoded = bytes(current).decode("ascii", errors="ignore")
            strings.append(decoded[:max_string_len])
        current = []
    if len(current) >= min_len:
        decoded = bytes(current).decode("ascii", errors="ignore")
        strings.append(decoded[:max_string_len])
    return strings


def limit_strings(strings: Iterable[str], max_strings: int) -> List[str]:
    """Limit the number of strings for stability."""
    if max_strings <= 0:
        return []
    limited: List[str] = []
    for value in strings:
        limited.append(value)
        if len(limited) >= max_strings:
            break
    return limited


def strings_to_document(strings: Iterable[str], max_doc_chars: int) -> str:
    """Join strings into a single document, truncated by length."""
    if max_doc_chars <= 0:
        return ""
    doc = "\n".join(strings)
    return doc[:max_doc_chars]


def tokenize_document(doc: str) -> List[str]:
    """Tokenize a document with minimal semantics."""
    return [token for token in doc.split() if token]
