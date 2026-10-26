"""Gera e valida folds agrupados a partir dos artefatos da tabela de treino."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml
from sklearn.model_selection import StratifiedGroupKFold

from src.cli_utils import apply_overrides
from src.dataset import contract as c
from src.run_metadata import code_commit, file_sha256

LOGGER = logging.getLogger(__name__)
FOLDS_FILENAME = "folds_grouped.parquet"
FOLDS_META_FILENAME = "folds_grouped.meta.json"
SCHEME_GROUPED = "grouped"
PURPOSE_PRINCIPAL = "principal"
GROUP_RULE = "componente_firmware_id_modelo"
GROUP_PREFIX = "g:"
ROLE_TRAIN = "train"
ROLE_TEST = "test"
FOLD_COLUMNS = ("repeat", "seed", "fold", "firmware_id", "role", "group")


@dataclass(frozen=True)
class PartitionConfig:
    """Contém parâmetros e destino da partição agrupada."""

    n_splits: int
    seeds: tuple[int, ...]
    processed_dir: Path

    def as_dict(self) -> dict[str, Any]:
        """Retorna a configuração serializável registrada no artefato."""
        return {
            "processed_dir": self.processed_dir.as_posix(),
            "partition": {"n_splits": self.n_splits, "seeds": list(self.seeds)},
        }


def load_partition_config(
    path: Path, overrides: dict[str, Any], processed_dir: Path | None
) -> PartitionConfig:
    """Lê e valida cinco ou mais grupos com uma única semente configurada."""
    if not path.is_file():
        raise FileNotFoundError(f"--config não encontrado: {path}")
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"Configuração inválida em {path}: partition")
    config = apply_overrides(raw, overrides)
    partition = config.get("partition")
    if not isinstance(partition, dict):
        raise ValueError(f"Configuração inválida em {path}: partition")
    splits = partition.get("n_splits")
    seeds = partition.get("seeds")
    if isinstance(splits, str):
        splits = yaml.safe_load(splits)
    if isinstance(seeds, str):
        seeds = yaml.safe_load(seeds)
    if type(splits) is not int or splits < 2:
        raise ValueError(f"Configuração inválida em {path}: partition.n_splits")
    if (
        not isinstance(seeds, list)
        or len(seeds) != 1
        or type(seeds[0]) is not int
        or seeds[0] < 0
    ):
        raise ValueError(
            f"Configuração inválida em {path}: partition.seeds: "
            "o núcleo usa uma semente (009/FR-011 é Proposto)"
        )
    directory = processed_dir if processed_dir is not None else config.get("output_dir")
    if not isinstance(directory, (str, Path)) or not str(directory).strip():
        raise ValueError(f"Configuração inválida em {path}: output_dir")
    return PartitionConfig(splits, tuple(seeds), Path(directory))


@dataclass(frozen=True)
class TrainingInputs:
    """Contém a tabela e a proveniência verificadas pelos hashes da 008."""

    table: pd.DataFrame
    provenance: pd.DataFrame
    table_sha256: str
    provenance_sha256: str
    table_path: Path
    provenance_path: Path


def _checked_hash(path: Path, expected: str) -> str:
    """Confere o SHA256 registrado e retorna o valor atual."""
    actual = file_sha256(path)
    if actual != expected:
        raise ValueError(
            f"SHA256 divergente em {path}: registrado {expected}, atual {actual}"
        )
    return actual


def _provenance_rows(path: Path) -> pd.DataFrame:
    """Expande somente os aliases incluídos na tabela de treino."""
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as source:
        for line in source:
            entry = json.loads(line)
            if not entry["in_table"]:
                continue
            for alias in entry["aliases"]:
                for key in ("vendor", "model"):
                    value = alias.get(key)
                    if not isinstance(value, str) or not value.strip():
                        raise ValueError(
                            f"alias sem {key}: firmware_id {entry['firmware_id']}, "
                            f"meta_path {alias.get('meta_path')}"
                        )
                rows.append(
                    {
                        "firmware_id": entry["firmware_id"],
                        **{key: alias[key] for key in ("meta_path", "vendor", "model")},
                    }
                )
    return pd.DataFrame(rows, columns=["firmware_id", "meta_path", "vendor", "model"])


def load_training_inputs(processed_dir: Path) -> TrainingInputs:
    """Carrega os artefatos 008, confere hashes e reconcilia aliases com IDs."""
    table_path = processed_dir / c.TABLE_FILENAME
    provenance_path = processed_dir / c.PROVENANCE_FILENAME
    meta_path = processed_dir / c.META_FILENAME
    for path in (table_path, provenance_path, meta_path):
        if not path.is_file():
            raise FileNotFoundError(f"artefato da 008 ausente: {path}")
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    table_hash = _checked_hash(table_path, meta["outputs"]["table"]["sha256"])
    provenance_hash = _checked_hash(
        provenance_path, meta["outputs"]["provenance"]["sha256"]
    )
    table = pd.read_parquet(table_path).sort_values(c.KEY_COLUMN).reset_index(drop=True)
    provenance = _provenance_rows(provenance_path)
    table_ids = set(table[c.KEY_COLUMN])
    alias_ids = set(provenance[c.KEY_COLUMN])
    missing = sorted(table_ids - alias_ids)
    extra = sorted(alias_ids - table_ids)
    if missing or extra:
        raise ValueError(
            f"aliases in_table: firmware_id sem alias {missing}; "
            f"fora da tabela {extra}"
        )
    provenance = provenance.sort_values([c.KEY_COLUMN, "meta_path"]).reset_index(
        drop=True
    )
    return TrainingInputs(
        table, provenance, table_hash, provenance_hash, table_path, provenance_path
    )


def model_key(vendor: str, model: str) -> str:
    """Normaliza fabricante e modelo sem remover sufixos de revisão."""

    def normalize(value: str) -> str:
        return "".join(char for char in value.lower() if char not in "-_ ")

    return f"{normalize(vendor)}/{normalize(model)}"


def build_groups(provenance: pd.DataFrame) -> dict[str, str]:
    """Une IDs ligados por modelos e nomeia cada componente pelo menor ID."""
    parent: dict[str, str] = {}

    def root(node: str) -> str:
        parent.setdefault(node, node)
        while parent[node] != node:
            parent[node] = parent[parent[node]]
            node = parent[node]
        return node

    for row in provenance.itertuples(index=False):
        firmware = f"id:{row.firmware_id}"
        model = f"model:{model_key(row.vendor, row.model)}"
        parent[root(model)] = root(firmware)
    members: dict[str, list[str]] = {}
    for firmware_id in provenance[c.KEY_COLUMN].unique():
        members.setdefault(root(f"id:{firmware_id}"), []).append(firmware_id)
    return {
        firmware_id: GROUP_PREFIX + min(ids)
        for ids in members.values()
        for firmware_id in ids
    }


def grouped_folds(
    table: pd.DataFrame, groups: dict[str, str], n_splits: int, seed: int
) -> pd.DataFrame:
    """Distribui grupos entre folds estratificados e inclui treino e teste."""
    ordered = table.sort_values(c.KEY_COLUMN).reset_index(drop=True)
    ids = ordered[c.KEY_COLUMN].tolist()
    group_values = [groups[firmware_id] for firmware_id in ids]
    splitter = StratifiedGroupKFold(n_splits=n_splits, shuffle=True, random_state=seed)
    rows: list[tuple[int, int, int, str, str, str]] = []
    for fold, (_, test_indices) in enumerate(
        splitter.split(np.zeros(len(ids)), ordered[c.TARGET_COLUMN], group_values)
    ):
        test = set(test_indices)
        rows.extend(
            (
                0,
                seed,
                fold,
                firmware_id,
                ROLE_TEST if index in test else ROLE_TRAIN,
                group_values[index],
            )
            for index, firmware_id in enumerate(ids)
        )
    return (
        pd.DataFrame(rows, columns=FOLD_COLUMNS)
        .astype({"repeat": "int64", "seed": "int64", "fold": "int64"})
        .sort_values(["repeat", "fold", c.KEY_COLUMN])
        .reset_index(drop=True)
    )


def _short_list(values: set[str]) -> str:
    """Exibe até dez chaves e o tamanho total da violação."""
    ordered = sorted(values)
    return f"{ordered[:10]} (total {len(ordered)})"


def check_no_crossing(folds: pd.DataFrame, provenance: pd.DataFrame) -> None:
    """Rejeita vazamento de ID/modelo e IDs sem teste único por repetição."""
    models = provenance.assign(
        model_key=[
            model_key(vendor, model)
            for vendor, model in zip(provenance["vendor"], provenance["model"])
        ]
    )[[c.KEY_COLUMN, "model_key"]]
    for (_, fold), frame in folds.groupby(["repeat", "fold"]):
        train = set(frame.loc[frame["role"] == ROLE_TRAIN, c.KEY_COLUMN])
        test = set(frame.loc[frame["role"] == ROLE_TEST, c.KEY_COLUMN])
        train_models = set(models.loc[models[c.KEY_COLUMN].isin(train), "model_key"])
        test_models = set(models.loc[models[c.KEY_COLUMN].isin(test), "model_key"])
        shared_ids = train & test
        shared_models = train_models & test_models
        if shared_ids or shared_models:
            raise ValueError(
                f"cruzamento treino/teste no fold {fold}: "
                f"firmware_id {_short_list(shared_ids)}; "
                f"modelo {_short_list(shared_models)}"
            )
    for repeat, frame in folds.groupby("repeat"):
        counts = frame.loc[frame["role"] == ROLE_TEST, c.KEY_COLUMN].value_counts()
        invalid = set(provenance[c.KEY_COLUMN]) - set(counts[counts == 1].index)
        if invalid:
            raise ValueError(
                f"firmware_id sem teste único na repetição {repeat}: "
                f"{_short_list(invalid)}"
            )


def _distribution(
    ids: pd.Series, table: pd.DataFrame, provenance: pd.DataFrame
) -> dict[str, Any]:
    """Conta classes por ID e fabricantes distintos por ID."""
    selected = table.loc[table[c.KEY_COLUMN].isin(ids)]
    counts = selected[c.TARGET_COLUMN].value_counts()
    vendors = provenance.loc[
        provenance[c.KEY_COLUMN].isin(ids), [c.KEY_COLUMN, "vendor"]
    ]
    vendors = vendors.drop_duplicates().groupby("vendor").size()
    return {
        "n": len(selected),
        "classes": {name: int(counts.get(name, 0)) for name in c.TARGET_CLASSES},
        "vendors": {name: int(count) for name, count in sorted(vendors.items())},
    }


def fold_summary(
    folds: pd.DataFrame, table: pd.DataFrame, provenance: pd.DataFrame
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Retorna (resumo por fold, folds de teste com classes ausentes).

    Cada fabricante distinto de um ID conta uma vez, mesmo com vários aliases.
    """
    summaries: list[dict[str, Any]] = []
    missing: list[dict[str, Any]] = []
    for (repeat, fold), frame in folds.groupby(["repeat", "fold"], sort=True):
        train = _distribution(
            frame.loc[frame["role"] == ROLE_TRAIN, c.KEY_COLUMN], table, provenance
        )
        test = _distribution(
            frame.loc[frame["role"] == ROLE_TEST, c.KEY_COLUMN], table, provenance
        )
        summaries.append(
            {"repeat": int(repeat), "fold": int(fold), "train": train, "test": test}
        )
        absent = sorted(name for name, count in test["classes"].items() if count == 0)
        if absent:
            missing.append(
                {"repeat": int(repeat), "fold": int(fold), "missing": absent}
            )
    return summaries, missing


@dataclass(frozen=True)
class PartitionResult:
    """Contém folds e metadados prontos para gravação."""

    folds: pd.DataFrame
    metadata: dict[str, Any]


def build_partition(config: PartitionConfig) -> PartitionResult:
    """Valida as entradas e constrói folds e metadados sem gravar arquivos."""
    inputs = load_training_inputs(config.processed_dir)
    groups = build_groups(inputs.provenance)
    folds = grouped_folds(inputs.table, groups, config.n_splits, config.seeds[0])
    check_no_crossing(folds, inputs.provenance)
    per_fold, missing = fold_summary(folds, inputs.table, inputs.provenance)
    sizes = pd.Series(groups).value_counts()
    metadata = {
        "scheme": SCHEME_GROUPED,
        "purpose": PURPOSE_PRINCIPAL,
        "config": config.as_dict(),
        "group_rule": GROUP_RULE,
        "n_splits": config.n_splits,
        "seeds": list(config.seeds),
        "inputs": {
            "table": {
                "path": inputs.table_path.as_posix(),
                "sha256": inputs.table_sha256,
            },
            "provenance": {
                "path": inputs.provenance_path.as_posix(),
                "sha256": inputs.provenance_sha256,
            },
        },
        "n_firmware_id": len(inputs.table),
        "n_groups": len(sizes),
        "max_group_size": int(sizes.max()),
        "per_fold": per_fold,
        "test_folds_missing_class": missing,
        "commit": code_commit(),
    }
    return PartitionResult(folds, metadata)


def log_summary(result: PartitionResult) -> None:
    """Informa dimensões, semente, classes por fold e classes ausentes."""
    meta = result.metadata
    LOGGER.info(
        "Partição: %s firmware_id, %s grupos, maior grupo %s, semente %s",
        meta["n_firmware_id"],
        meta["n_groups"],
        meta["max_group_size"],
        meta["seeds"][0],
    )
    for summary in meta["per_fold"]:
        LOGGER.info(
            "Fold %s: treino %s; teste %s",
            summary["fold"],
            summary["train"]["classes"],
            summary["test"]["classes"],
        )
    for missing in meta["test_folds_missing_class"]:
        LOGGER.warning(
            "Fold de teste %s sem classes %s", missing["fold"], missing["missing"]
        )


def write_folds(result: PartitionResult, processed_dir: Path) -> dict[str, Path]:
    """Grava parquet e, por último, metadados com SHA256 e instante UTC."""
    processed_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "folds": processed_dir / FOLDS_FILENAME,
        "meta": processed_dir / FOLDS_META_FILENAME,
    }
    result.folds.to_parquet(paths["folds"], index=False)
    metadata = {
        **result.metadata,
        "folds_sha256": file_sha256(paths["folds"]),
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    paths["meta"].write_text(
        json.dumps(metadata, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return paths


@dataclass(frozen=True)
class FoldSet:
    """Contém tabela, proveniência, folds e metadados íntegros."""

    table: pd.DataFrame
    provenance: pd.DataFrame
    folds: pd.DataFrame
    meta: dict[str, Any]


def load_folds(processed_dir: Path, scheme: str = SCHEME_GROUPED) -> FoldSet:
    """Carrega folds agrupados somente se os três hashes forem íntegros."""
    if scheme != SCHEME_GROUPED:
        raise ValueError(
            f"esquema não suportado: {scheme}; random é B6 Proposto (009/FR-007)"
        )
    meta_path = processed_dir / FOLDS_META_FILENAME
    if not meta_path.is_file():
        raise FileNotFoundError(f"artefato da 009 ausente: {meta_path}")
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    inputs = load_training_inputs(processed_dir)
    _checked_hash(inputs.table_path, meta["inputs"]["table"]["sha256"])
    _checked_hash(inputs.provenance_path, meta["inputs"]["provenance"]["sha256"])
    folds_path = processed_dir / FOLDS_FILENAME
    _checked_hash(folds_path, meta["folds_sha256"])
    return FoldSet(inputs.table, inputs.provenance, pd.read_parquet(folds_path), meta)
