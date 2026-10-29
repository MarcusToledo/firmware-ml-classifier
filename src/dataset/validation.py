"""Valida integridade e cobertura da tabela de treino (spec 008)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd
from pandas.api.types import is_object_dtype, is_string_dtype

from src.dataset.contract import (
    EXCLUSIONS_FILENAME,
    KEY_COLUMN,
    META_FILENAME,
    PROVENANCE_FILENAME,
    T13A_EXCLUDED_COLUMNS,
    TABLE_FILENAME,
    TARGET_CLASSES,
    TARGET_COLUMN,
    is_forbidden_column,
)
from src.io_utils import gather_firmware_paths
from src.run_metadata import file_sha256


def _table_issues(table: pd.DataFrame) -> list[str]:
    """Confere chave, tipos e classes da tabela gravada."""
    issues: list[str] = []
    duplicates = sorted(
        table.loc[table[KEY_COLUMN].duplicated(False), KEY_COLUMN].astype(str).unique()
    )
    if duplicates:
        issues.append(f"firmware_id duplicado: {', '.join(duplicates)}")
    vector = table.drop(columns=[KEY_COLUMN, TARGET_COLUMN])
    forbidden = [col for col in vector if is_forbidden_column(col)]
    if forbidden:
        issues.append(f"coluna proibida no vetor: {', '.join(forbidden)}")
    excluded = [col for col in vector if col in T13A_EXCLUDED_COLUMNS]
    if excluded:
        issues.append(f"coluna excluída pela T13-A no vetor: {', '.join(excluded)}")
    text = [
        col
        for col in vector
        if is_object_dtype(vector[col])
        or is_string_dtype(vector[col])
        or isinstance(vector[col].dtype, pd.CategoricalDtype)
    ]
    if text:
        issues.append(f"coluna de texto no vetor: {', '.join(text)}")
    invalid = table.loc[~table[TARGET_COLUMN].isin(TARGET_CLASSES), TARGET_COLUMN]
    if not invalid.empty:
        values = ", ".join(sorted(invalid.astype(str).unique()))
        issues.append(f"alvo fora das classes: {values}")
    return issues


def _hash_issues(meta: dict[str, Any], processed_dir: Path) -> list[str]:
    """Confere os hashes declarados de entradas e saídas.

    Entradas são resolvidas a partir do diretório de execução; saídas, pelo nome
    do arquivo dentro de `processed_dir`, para validar cópias do artefato.
    """
    issues: list[str] = []
    for group in ("inputs", "outputs"):
        for entry in meta[group].values():
            path = Path(entry["path"])
            if group == "outputs":
                path = processed_dir / path.name
            if not path.is_file():
                issues.append(f"artefato ausente: {path}")
                continue
            actual = file_sha256(path)
            if actual != entry["sha256"]:
                issues.append(
                    f"SHA256 divergente em {path}: "
                    f"registrado {entry['sha256']}, atual {actual}"
                )
    return issues


def _column_issues(table: pd.DataFrame, expected: list[str]) -> list[str]:
    """Confere conteúdo e ordem das colunas do vetor."""
    actual = [col for col in table if col not in (KEY_COLUMN, TARGET_COLUMN)]
    missing = sorted(set(expected) - set(actual))
    extra = sorted(set(actual) - set(expected))
    if missing or extra:
        return [f"colunas diferentes dos metadados: faltam {missing}; sobram {extra}"]
    if actual != expected:
        return ["ordem das colunas difere dos metadados"]
    return []


def _orphan_issues(features_path: Path, raw_root: Path) -> list[str]:
    """Compara firmwares no disco com caminhos das features de entrada."""
    if not features_path.is_file():
        return []
    features = (
        pd.read_csv(features_path, usecols=["meta_path"])
        if features_path.suffix == ".csv"
        else pd.read_parquet(features_path, columns=["meta_path"])
    )
    paths = features["meta_path"].dropna().astype(str)
    absolute = paths[paths.map(lambda value: Path(value).is_absolute())]
    if not absolute.empty:
        return [
            "meta_path absoluto na tabela de features "
            f"({len(absolute)} linhas, ex.: {absolute.iloc[0]}); "
            "extraia as features de novo com --dataset-root"
        ]
    seen = set(paths)
    orphans = sorted(
        path.relative_to(raw_root).as_posix()
        for path in gather_firmware_paths(raw_root)
        if path.relative_to(raw_root).as_posix() not in seen
    )
    return [f"órfão em {path.split('/')[0]}: {path}" for path in orphans]


def validate_artifacts(processed_dir: Path, raw_root: Path) -> list[str]:
    """Retorna problemas de integridade e arquivos órfãos; vazio se íntegro."""
    artifact_paths = [
        processed_dir / name
        for name in (
            TABLE_FILENAME,
            EXCLUSIONS_FILENAME,
            PROVENANCE_FILENAME,
            META_FILENAME,
        )
    ]
    missing = [
        f"artefato ausente: {path}" for path in artifact_paths if not path.is_file()
    ]
    if missing:
        return missing
    table = pd.read_parquet(artifact_paths[0])
    meta = json.loads(artifact_paths[3].read_text(encoding="utf-8"))
    issues = _table_issues(table)
    issues.extend(_hash_issues(meta, processed_dir))
    issues.extend(_column_issues(table, meta["columns_vector"]))
    issues.extend(_orphan_issues(Path(meta["inputs"]["features"]["path"]), raw_root))
    return issues
