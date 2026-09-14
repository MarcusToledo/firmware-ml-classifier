"""Achados de segurança derivados das descrições de assinatura do Binwalk.

Recebe a ``list[str]`` de linhas de descrição que o Binwalk já produziu (ver
``_extract_binwalk_descriptions`` em ``pipeline/feature_extraction.py``).
Nunca roda o Binwalk em si, só interpreta a saída dele em busca de evidência
de segurança. Sinais estruturais (não relacionados a segurança) do Binwalk,
como tipo de filesystem, tipo de compressão e contagem de filesystems,
ficam em ``src/features/binwalk.py``.
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
    """Encontra descrições do Binwalk que mencionam construções criptográficas."""
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
    """Conta descrições que mencionam construções criptográficas."""
    return len(find_crypto_signatures(descriptions))


def find_encrypted_sections(descriptions: list[str]) -> list[SecurityFinding]:
    """Encontra descrições do Binwalk que sugerem conteúdo criptografado."""
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
    """Retorna True se alguma descrição sugerir conteúdo criptografado."""
    return bool(find_encrypted_sections(descriptions))
