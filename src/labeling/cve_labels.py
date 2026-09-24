"""Mapeia estatísticas de CVE para classes de vulnerabilidade conhecida.

Os campos de CVE definem somente o rótulo; nunca entram no vetor de features.
Ausência de CVE conhecida não significa que o firmware seja seguro.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

LABEL_NO_KNOWN_CVE = "sem_cve_conhecida"
LABEL_KNOWN_CVE = "cve_conhecida"
LABEL_CRITICAL_CVE = "cve_critica"


@dataclass(frozen=True)
class CveLabelThresholds:
    """Limiar CVSS para a classe de CVE crítica."""

    critical_cvss: float = 9.0

    def __post_init__(self) -> None:
        if not isinstance(self.critical_cvss, (int, float)) or isinstance(
            self.critical_cvss, bool
        ):
            raise ValueError("critical_cvss deve ser um número entre 0 e 10")
        if not math.isfinite(self.critical_cvss) or not 0 <= self.critical_cvss <= 10:
            raise ValueError("critical_cvss deve ser um número entre 0 e 10")


_DEFAULT_THRESHOLDS = CveLabelThresholds()


def label_from_cve_stats(
    cve_stats: dict[str, Any],
    thresholds: CveLabelThresholds = _DEFAULT_THRESHOLDS,
) -> str:
    """Rotula estatísticas agregadas de uma consulta CVE concluída.

    Um dicionário vazio representa uma consulta sem resultados nesta API.
    O chamador deve distinguir isso de uma consulta ausente ou com erro.
    """
    cve_total = cve_stats.get("cve_total", 0)
    if not isinstance(cve_total, int) or isinstance(cve_total, bool) or cve_total < 0:
        raise ValueError("cve_total deve ser um inteiro não negativo")

    cvss_max = cve_stats.get("cvss_max", 0.0)
    if not isinstance(cvss_max, (int, float)) or isinstance(cvss_max, bool):
        raise ValueError("cvss_max deve ser um número entre 0 e 10")
    if not math.isfinite(cvss_max) or not 0 <= cvss_max <= 10:
        raise ValueError("cvss_max deve ser um número entre 0 e 10")

    if cve_total == 0:
        return LABEL_NO_KNOWN_CVE
    if cvss_max >= thresholds.critical_cvss:
        return LABEL_CRITICAL_CVE
    return LABEL_KNOWN_CVE
