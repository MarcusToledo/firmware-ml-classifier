"""Security findings derived from Binwalk signature descriptions.

Consumes the ``list[str]`` of description lines Binwalk already produced
(see ``pipeline/feature_extraction.py``'s ``_extract_binwalk_descriptions``)
— it never runs Binwalk itself, only interprets its output for security
evidence. Structural (non-security) Binwalk signals — filesystem type,
compression type, filesystem count — stay in ``src/features/binwalk.py``.
"""
from __future__ import annotations

import re

from src.evidence.findings import SecurityFinding

_DETECTOR_VERSION = "1.0"

_CRYPTO_RE = re.compile(
    r"\bAES\b|\bDES\b|\bRSA\b|certificate|private\skey",
    re.IGNORECASE,
)

_ENCRYPTED_RE = re.compile(
    r"encrypt|\bAES\b|cipher",
    re.IGNORECASE,
)


def find_crypto_signatures(descriptions: list[str]) -> list[SecurityFinding]:
    """Find Binwalk descriptions mentioning cryptographic constructs."""
    findings: list[SecurityFinding] = []
    for d in descriptions:
        m = _CRYPTO_RE.search(d)
        if m:
            findings.append(
                SecurityFinding(
                    type="crypto_signature",
                    source=d,
                    context=f"cryptographic construct: {m.group(0)!r}",
                    confidence="medium",
                    detector="crypto_signatures",
                    detector_version=_DETECTOR_VERSION,
                )
            )
    return findings


def count_crypto_signatures(descriptions: list[str]) -> int:
    """Count descriptions that mention cryptographic constructs."""
    return len(find_crypto_signatures(descriptions))


def find_encrypted_sections(descriptions: list[str]) -> list[SecurityFinding]:
    """Find Binwalk descriptions suggesting encrypted content."""
    findings: list[SecurityFinding] = []
    for d in descriptions:
        m = _ENCRYPTED_RE.search(d)
        if m:
            findings.append(
                SecurityFinding(
                    type="encrypted_section",
                    source=d,
                    context=f"encryption indicator: {m.group(0)!r}",
                    confidence="medium",
                    detector="encrypted_sections",
                    detector_version=_DETECTOR_VERSION,
                )
            )
    return findings


def has_encrypted_sections(descriptions: list[str]) -> bool:
    """Return True if any description suggests encrypted content."""
    return bool(find_encrypted_sections(descriptions))
