"""Comparação numérica de versões de firmware com limites de CPE."""

from __future__ import annotations

import re
from dataclasses import dataclass

_LEADING_VERSION_RE = re.compile(r"^\d+(?:\.\d+)*")


def parse_version(raw: str) -> tuple[int, ...] | None:
    """Extrai os segmentos numéricos iniciais; retorna None se ausentes."""
    match = _LEADING_VERSION_RE.match(raw.strip())
    if match is None:
        return None
    return tuple(int(segment) for segment in match.group().split("."))


@dataclass(frozen=True)
class VersionRange:
    """Limites inclusivos e exclusivos de um critério CPE."""

    start_including: tuple[int, ...] | None = None
    start_excluding: tuple[int, ...] | None = None
    end_including: tuple[int, ...] | None = None
    end_excluding: tuple[int, ...] | None = None


def _compare(left: tuple[int, ...], right: tuple[int, ...]) -> int:
    length = max(len(left), len(right))
    padded_left = left + (0,) * (length - len(left))
    padded_right = right + (0,) * (length - len(right))
    return (padded_left > padded_right) - (padded_left < padded_right)


def versions_equal(left: tuple[int, ...], right: tuple[int, ...]) -> bool:
    """Compara versoes tratando segmentos finais ausentes como zero."""
    return _compare(left, right) == 0


def version_in_range(version: tuple[int, ...], bounds: VersionRange) -> bool:
    """Verifica os quatro limites, tratando segmentos finais ausentes como zero."""
    if bounds.start_including is not None:
        if _compare(version, bounds.start_including) < 0:
            return False
    if bounds.start_excluding is not None:
        if _compare(version, bounds.start_excluding) <= 0:
            return False
    if bounds.end_including is not None:
        if _compare(version, bounds.end_including) > 0:
            return False
    if bounds.end_excluding is not None:
        if _compare(version, bounds.end_excluding) >= 0:
            return False
    return True
