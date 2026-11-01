"""Resolve os braços do núcleo e das ablações sobre o vetor congelado (011)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from src.evaluation.config import EvaluationConfig

ABLATION_MODEL = "extra_trees"


@dataclass(frozen=True)
class ArmSpec:
    """Descreve um braço avaliado: modelo, colunas e colunas removidas."""

    arm: str
    label: str
    model: str
    columns: list[str] | None
    removed: tuple[str, ...]
    already_excluded: tuple[str, ...]
    kind: str


def _ablation_arm(
    item: dict[str, Any], columns_vector: list[str], column_changes: dict[str, str]
) -> ArmSpec:
    """Separa colunas a remover das já retiradas na 008 e monta o braço.

    Levanta ValueError para coluna desconhecida, braço sem coluna presente no
    vetor (bloqueado) ou braço sem colunas restantes.
    """
    arm, requested = item["arm"], set(item["remove"])
    unknown = sorted(requested - set(columns_vector) - set(column_changes))
    if unknown:
        raise ValueError(
            f"braço {arm}: coluna inexistente no vetor e em column_changes: {unknown}"
        )
    removed = tuple(name for name in columns_vector if name in requested)
    if not removed:
        raise ValueError(
            f"braço {arm} bloqueado: nenhuma coluna de remove está no vetor "
            "congelado; não declarar execução (011/FR-005, aguarda 001/T050)"
        )
    excluded = tuple(sorted(requested - set(columns_vector)))
    columns = [name for name in columns_vector if name not in requested]
    if not columns:
        raise ValueError(f"braço {arm} sem colunas após remoção")
    return ArmSpec(
        arm, item["label"], ABLATION_MODEL, columns, removed, excluded, "ablation"
    )


def resolve_arms(
    config: EvaluationConfig, columns_vector: list[str], column_changes: dict[str, str]
) -> list[ArmSpec]:
    """Retorna os braços da matriz seguidos das ablações, na ordem do YAML.

    Levanta ValueError se o vetor contém doc2vec_* (011/FR-006) ou se alguma
    ablação é inválida.
    """
    if any(name.startswith("doc2vec_") for name in columns_vector):
        raise ValueError("coluna doc2vec_* no vetor; T06 é Proposto (011/FR-006)")
    arms = [
        ArmSpec(item["arm"], item["label"], item["model"], None, (), (), "nucleo")
        for item in config.matrix
    ]
    arms.extend(
        _ablation_arm(item, columns_vector, column_changes)
        for item in config.ablations
    )
    return arms
