"""Evidência de segurança estruturada produzida pelos detectores em ``src/evidence/``.

Um ``SecurityFinding`` é a saída auditável de uma execução de detector sobre
um dado já extraído (uma string, uma linha de descrição do Binwalk). Nunca é
um veredito em si, só uma observação com contexto suficiente para revisão
manual. Os detectores também expõem contagens/flags achatadas derivadas
desses achados (ver ``findings_to_counts`` em ``src/evidence/patterns.py``)
para consumo como feature do classificador.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SecurityFinding:
    """Uma observação de segurança estruturada e auditável.

    Atributos:
        type: Categoria do achado (ex.: "credential_candidate").
        source: A string/descrição original que gerou o match.
        context: Explicação curta e legível do que casou e por quê.
        confidence: "low" | "medium" | "high" (confiabilidade do sinal).
        detector: Nome do detector que produziu este achado.
        detector_version: Versão do detector, para reprodutibilidade.
    """

    type: str
    source: str
    context: str
    confidence: str
    detector: str
    detector_version: str
