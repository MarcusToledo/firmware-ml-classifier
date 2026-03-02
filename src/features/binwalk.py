"""Pure parsing helpers for Binwalk signature descriptions.

All functions receive a ``list[str]`` of description lines (as returned by
``binwalk.scan``) and perform regex-based matching — no dependency on binwalk3
itself.
"""
from __future__ import annotations

import re
from collections import Counter

_FS_RE = re.compile(
    r"squashfs|cramfs|jffs2|romfs|ext[234]|ubifs|yaffs",
    re.IGNORECASE,
)

_CRYPTO_RE = re.compile(
    r"\bAES\b|\bDES\b|\bRSA\b|certificate|private\skey",
    re.IGNORECASE,
)

_ENCRYPTED_RE = re.compile(
    r"encrypt|\bAES\b|cipher",
    re.IGNORECASE,
)

_COMPRESSION_RE = re.compile(
    r"\blzma\b|\bgzip\b|\bxz\b|\bzstd\b|\blzo\b|\bbzip2\b",
    re.IGNORECASE,
)


def count_filesystems(descriptions: list[str]) -> int:
    """Count descriptions that mention a known filesystem type."""
    return sum(1 for d in descriptions if _FS_RE.search(d))


def count_crypto_signatures(descriptions: list[str]) -> int:
    """Count descriptions that mention cryptographic constructs."""
    return sum(1 for d in descriptions if _CRYPTO_RE.search(d))


def has_encrypted_sections(descriptions: list[str]) -> bool:
    """Return True if any description suggests encrypted content."""
    return any(_ENCRYPTED_RE.search(d) for d in descriptions)


def detect_fs_type(descriptions: list[str]) -> str | None:
    """Return the most frequently mentioned filesystem, or None."""
    matches: list[str] = []
    for d in descriptions:
        m = _FS_RE.search(d)
        if m:
            matches.append(m.group(0).lower())
    if not matches:
        return None
    counter = Counter(matches)
    return counter.most_common(1)[0][0]


def detect_compression_type(descriptions: list[str]) -> str | None:
    """Return the first compression algorithm mentioned, or None."""
    for d in descriptions:
        m = _COMPRESSION_RE.search(d)
        if m:
            return m.group(0).lower()
    return None
