"""Valida a resolução dos braços de ablação sobre o vetor congelado (011)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.evaluation.ablation import resolve_arms
from src.evaluation.config import EvaluationConfig, load_evaluation_config

VECTOR = ["entropy", "count_urls", "has_telnetd", "unpacked_n_files"]
CHANGES = {"count_non_public_ips": "t13a_reformular",
           "count_public_ips": "t13a_reformular"}


def _config(ablations: list[dict]) -> EvaluationConfig:
    """Carrega a configuração versionada com as ablações pedidas."""
    return load_evaluation_config(
        Path("configs/evaluation.yaml"), {"ablations": json.dumps(ablations)}
    )


def _ablation(*remove: str) -> dict:
    """Retorna uma ablação B2′ com as colunas a remover."""
    return {"arm": "B2_linha", "label": "B2′", "remove": list(remove)}


def test_b2_linha_records_columns_already_excluded_by_008() -> None:
    """Remove count_urls e registra as colunas de IP retiradas pela 008."""
    arms = resolve_arms(
        _config([_ablation("count_public_ips", "count_urls", "count_non_public_ips")]),
        VECTOR, CHANGES,
    )
    assert [arm.kind for arm in arms[:-1]] == ["nucleo"] * 5
    linha = arms[-1]
    assert (linha.model, linha.kind) == ("extra_trees", "ablation")
    assert linha.removed == ("count_urls",)
    assert linha.already_excluded == ("count_non_public_ips", "count_public_ips")
    assert linha.columns == ["entropy", "has_telnetd", "unpacked_n_files"]


def test_removed_columns_follow_vector_order() -> None:
    """Ordena colunas removidas e restantes pela ordem imutável do vetor."""
    arms = resolve_arms(
        _config([_ablation("unpacked_n_files", "entropy")]), VECTOR, CHANGES
    )
    assert arms[-1].removed == ("entropy", "unpacked_n_files")
    assert arms[-1].columns == ["count_urls", "has_telnetd"]


@pytest.mark.parametrize(("remove", "message"), [
    (("count_urls", "coluna_x"), "inexistente"),
    (("count_public_ips", "count_non_public_ips"), "bloqueado"),
    (tuple(VECTOR), "sem colunas"),
])
def test_invalid_ablation_is_rejected(remove: tuple[str, ...], message: str) -> None:
    """Recusa coluna desconhecida, braço bloqueado e braço sem colunas."""
    with pytest.raises(ValueError, match=message):
        resolve_arms(_config([_ablation(*remove)]), VECTOR, CHANGES)


def test_doc2vec_column_in_vector_is_rejected() -> None:
    """Recusa avaliar vetor com doc2vec_*, Proposto pela T06."""
    with pytest.raises(ValueError, match="FR-006"):
        resolve_arms(_config([]), [*VECTOR, "doc2vec_0"], CHANGES)
