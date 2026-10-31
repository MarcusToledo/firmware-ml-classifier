"""Carrega e valida a configuração versionada da avaliação (spec 011)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from src.cli_utils import apply_overrides
from src.models.training import MODELS

REQUIRED_ARMS = (("B2", "extra_trees"), ("B1", "identidade"), ("B0", "majoritario"))


@dataclass(frozen=True)
class EvaluationConfig:
    """Contém braços, ablações e parâmetros efetivos da avaliação."""

    config_path: Path
    training_config: Path
    output_dir: Path
    experiment: str
    scheme: str
    matrix: tuple[dict[str, str], ...]
    ablations: tuple[dict[str, Any], ...]
    n_resamples: int
    bootstrap_seed: int
    ci: float
    n_repeats: int
    permutation_seed: int
    exclude_alias_vendor: str
    effective: dict[str, Any]


def _invalid(path: Path, key: str) -> ValueError:
    """Retorna o erro padronizado de configuração inválida."""
    return ValueError(f"Configuração inválida em {path}: {key}")


def _is_int(value: Any) -> bool:
    """Indica se o valor é inteiro e não booleano."""
    return isinstance(value, int) and not isinstance(value, bool)


def _is_text(value: Any) -> bool:
    """Indica se o valor é texto não vazio."""
    return isinstance(value, str) and bool(value.strip())


def _validate_matrix(matrix: Any, path: Path) -> None:
    """Exige braços com modelo da 010 e os comparadores obrigatórios B2, B1 e B0."""
    if not isinstance(matrix, list) or not matrix:
        raise _invalid(path, "matrix")
    for item in matrix:
        if not isinstance(item, dict) or not all(
            _is_text(item.get(key)) for key in ("arm", "label", "model")
        ):
            raise _invalid(path, "matrix")
        if item["model"] not in MODELS:
            raise _invalid(path, f"matrix.{item['arm']}.model")
    pairs = {(item["arm"], item["model"]) for item in matrix}
    if not all(required in pairs for required in REQUIRED_ARMS):
        raise _invalid(path, "matrix")


def _validate_ablations(ablations: Any, path: Path) -> None:
    """Exige ablações com nome, rótulo e lista não vazia de colunas a remover."""
    if not isinstance(ablations, list):
        raise _invalid(path, "ablations")
    for item in ablations:
        if not isinstance(item, dict) or not (
            _is_text(item.get("arm")) and _is_text(item.get("label"))
        ):
            raise _invalid(path, "ablations")
        remove = item.get("remove")
        if not isinstance(remove, list) or not remove or not all(
            _is_text(name) for name in remove
        ):
            raise _invalid(path, f"ablations.{item['arm']}.remove")


def _validate_parameters(raw: dict[str, Any], path: Path) -> None:
    """Exige bootstrap, permutação e fabricante de sensibilidade bem tipados."""
    bootstrap = raw.get("bootstrap")
    if not isinstance(bootstrap, dict):
        raise _invalid(path, "bootstrap")
    if not _is_int(bootstrap.get("n_resamples")) or bootstrap["n_resamples"] < 1:
        raise _invalid(path, "bootstrap.n_resamples")
    if not _is_int(bootstrap.get("seed")):
        raise _invalid(path, "bootstrap.seed")
    ci = bootstrap.get("ci")
    if not isinstance(ci, float) or not 0 < ci < 1:
        raise _invalid(path, "bootstrap.ci")
    permutation = raw.get("permutation")
    if not isinstance(permutation, dict):
        raise _invalid(path, "permutation")
    if not _is_int(permutation.get("n_repeats")) or permutation["n_repeats"] < 1:
        raise _invalid(path, "permutation.n_repeats")
    if not _is_int(permutation.get("seed")):
        raise _invalid(path, "permutation.seed")
    sensitivity = raw.get("sensitivity")
    if not isinstance(sensitivity, dict) or not _is_text(
        sensitivity.get("exclude_alias_vendor")
    ):
        raise _invalid(path, "sensitivity.exclude_alias_vendor")


def _validate_evaluation(raw: Any, path: Path) -> None:
    """Valida caminhos, experiência, braços e parâmetros da avaliação.

    Levanta ValueError citando a primeira chave inválida.
    """
    if not isinstance(raw, dict):
        raise _invalid(path, "raiz")
    for key in ("training_config", "output_dir"):
        if not _is_text(raw.get(key)):
            raise _invalid(path, key)
    if raw.get("experiment") != "principal":
        raise _invalid(path, "experiment")
    if raw.get("scheme") != "grouped":
        raise _invalid(path, "scheme")
    _validate_matrix(raw.get("matrix"), path)
    _validate_ablations(raw.get("ablations"), path)
    arms = [item["arm"] for item in [*raw["matrix"], *raw["ablations"]]]
    if len(arms) != len(set(arms)):
        raise _invalid(path, "arm duplicado")
    _validate_parameters(raw, path)


def load_evaluation_config(path: Path, overrides: dict[str, str]) -> EvaluationConfig:
    """Carrega o YAML, aplica overrides tipados e valida a configuração.

    Levanta FileNotFoundError se o arquivo não existe e ValueError se inválido.
    """
    if not path.is_file():
        raise FileNotFoundError(f"--config não encontrado: {path}")
    parsed: dict[str, Any] = {}
    for key, value in overrides.items():
        try:
            parsed[key] = yaml.safe_load(value)
        except yaml.YAMLError as exc:
            raise _invalid(path, key) from exc
    raw = apply_overrides(yaml.safe_load(path.read_text(encoding="utf-8")), parsed)
    _validate_evaluation(raw, path)
    return EvaluationConfig(
        path, Path(raw["training_config"]), Path(raw["output_dir"]),
        raw["experiment"], raw["scheme"], tuple(raw["matrix"]),
        tuple(raw["ablations"]), raw["bootstrap"]["n_resamples"],
        raw["bootstrap"]["seed"], raw["bootstrap"]["ci"],
        raw["permutation"]["n_repeats"], raw["permutation"]["seed"],
        raw["sensitivity"]["exclude_alias_vendor"], raw,
    )
