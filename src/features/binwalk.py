"""Helpers puros para parsear descrições de assinatura do Binwalk.

Todas as funções recebem uma ``list[str]`` de linhas de descrição (como as
retornadas por ``binwalk.scan``) e fazem matching baseado em regex, sem
dependência do binwalk3 em si. Sinais orientados a segurança (assinaturas
de cripto, seções criptografadas) ficam em
``src/evidence/binwalk_findings.py``; este módulo mantém só os sinais
estruturais (não relacionados a segurança).
"""
from __future__ import annotations

import re
from collections import Counter

_FS_RE = re.compile(
    r"squashfs|cramfs|jffs2|romfs|ext[234]|ubifs|yaffs",
    re.IGNORECASE,
)

_COMPRESSION_RE = re.compile(
    r"\blzma\b|\bgzip\b|\bxz\b|\bzstd\b|\blzo\b|\bbzip2\b",
    re.IGNORECASE,
)


def count_filesystems(descriptions: list[str]) -> int:
    """Conta descrições que mencionam um tipo de filesystem conhecido."""
    return sum(1 for d in descriptions if _FS_RE.search(d))


def detect_fs_type(descriptions: list[str]) -> str | None:
    """Retorna o filesystem mencionado com mais frequência, ou None."""
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
    """Retorna o primeiro algoritmo de compressão mencionado, ou None."""
    for d in descriptions:
        m = _COMPRESSION_RE.search(d)
        if m:
            return m.group(0).lower()
    return None
