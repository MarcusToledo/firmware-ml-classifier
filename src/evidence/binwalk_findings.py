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
from src.evidence.patterns import CONFIDENCE_MEDIUM

DETECTOR_CRYPTO_SIGNATURES = "crypto_signatures"
DETECTOR_ENCRYPTED_SECTIONS = "encrypted_sections"


DETECTOR_VERSIONS: dict[str, str] = {
    DETECTOR_CRYPTO_SIGNATURES: "1.0",
    DETECTOR_ENCRYPTED_SECTIONS: "2.0",
}

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
                    confidence=CONFIDENCE_MEDIUM,
                    detector=DETECTOR_CRYPTO_SIGNATURES,
                    detector_version=DETECTOR_VERSIONS[DETECTOR_CRYPTO_SIGNATURES],
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
        if "s-box" in d.lower():
            continue
        m = _ENCRYPTED_RE.search(d)
        if m:
            findings.append(
                SecurityFinding(
                    type="encrypted_section",
                    source=d,
                    context=f"encryption indicator: {m.group(0)!r}",
                    confidence=CONFIDENCE_MEDIUM,
                    detector=DETECTOR_ENCRYPTED_SECTIONS,
                    detector_version=DETECTOR_VERSIONS[DETECTOR_ENCRYPTED_SECTIONS],
                )
            )
    return findings


def has_encrypted_sections(descriptions: list[str]) -> bool:
    """Retorna True se alguma descrição sugerir conteúdo criptografado."""
    return bool(find_encrypted_sections(descriptions))
