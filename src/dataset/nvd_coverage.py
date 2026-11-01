"""Descreve as proteções ELF por cobertura NVD, conforme pré-registro da rodada v3.

O parquet traz uma linha por arquivo/alias. Como na tabela de treino 008,
``collapse_aliases`` exige medidas iguais e retém um único registro por firmware_id.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from src.dataset import contract as c
from src.dataset.training_table import (
    apply_exclusions,
    check_transient_failures,
    collapse_aliases,
)
from src.run_metadata import REPO_ROOT, code_commit, file_sha256

PREREGISTRATION = REPO_ROOT / "docs/preregistro_cobertura_nvd.md"
PREREGISTRATION_SHA256 = (
    "8b4693da40d1ab2d23c6887e38bce6b872c2572a8cabbf9407a75f8b82f0a138"
)
VARIABLES = (
    "unpacked_prop_nx",
    "unpacked_prop_pie",
    "unpacked_prop_relro_full",
    "unpacked_prop_relro_partial",
    "unpacked_prop_canary",
)
GROUPS = ("nao_encontrado", "sem_cve_confirmado")
COLUMNS = (
    "grupo", "fabricante", "variavel", "n", "n_ausente",
    "mediana", "q1", "q3", "media", "situacao",
)


def _check_columns(features: pd.DataFrame, labels: pd.DataFrame) -> None:
    """Exige colunas usadas pela seleção e pelas exclusões da 008."""
    feature_columns = (
        c.KEY_COLUMN, "meta_path", "meta_brand", *c.EXTRACTION_STATUS_COLUMNS,
        *VARIABLES,
    )
    for name, frame, columns in (
        ("features", features, feature_columns),
        ("labels", labels, (c.KEY_COLUMN, c.TARGET_COLUMN, "evidence_reason")),
    ):
        missing = sorted(set(columns) - set(frame.columns))
        if missing:
            raise ValueError(f"{name}: colunas ausentes: {missing}")
    if features[c.KEY_COLUMN].isna().any() or labels[c.KEY_COLUMN].isna().any():
        raise ValueError("firmware_id nulo nas entradas")
    if set(features[c.KEY_COLUMN]) != set(labels[c.KEY_COLUMN]):
        raise ValueError("firmware_id sem par entre features e labels")


def _grouped_labels(labels: pd.DataFrame) -> pd.DataFrame:
    """Define A/B por ID e rejeita divergência de rótulo ou motivo entre aliases."""
    inconsistent = labels.groupby(c.KEY_COLUMN)[
        [c.TARGET_COLUMN, "evidence_reason"]
    ].nunique(dropna=False).gt(1).any(axis=1)
    if inconsistent.any():
        divergent = sorted(inconsistent[inconsistent].index)
        raise ValueError(f"Rótulos divergentes entre aliases: {divergent}")
    distinct = labels.drop_duplicates(c.KEY_COLUMN).copy()
    is_a = distinct[c.TARGET_COLUMN].eq("indeterminado") & distinct[
        "evidence_reason"
    ].eq("nao_encontrado")
    is_b = distinct[c.TARGET_COLUMN].eq("sem_cve_conhecida")
    distinct["grupo"] = pd.NA
    distinct.loc[is_a, "grupo"] = GROUPS[0]
    distinct.loc[is_b, "grupo"] = GROUPS[1]
    return distinct[[c.KEY_COLUMN, "grupo"]].dropna()


def _vendor_by_id(features: pd.DataFrame, ids: set[str]) -> pd.DataFrame:
    """Obtém fabricante único por firmware_id, sem multiplicar aliases."""
    eligible = features.loc[features[c.KEY_COLUMN].isin(ids)]
    brands = eligible.groupby(c.KEY_COLUMN)["meta_brand"].nunique(dropna=False)
    ambiguous = brands[brands.ne(1)].index.tolist()
    null = eligible.loc[eligible["meta_brand"].isna(), c.KEY_COLUMN].tolist()
    if ambiguous or null:
        invalid_ids = sorted(set(ambiguous + null))
        raise ValueError(f"firmware_id sem fabricante único: {invalid_ids}")
    return eligible.drop_duplicates(c.KEY_COLUMN)[[c.KEY_COLUMN, "meta_brand"]]


def _rows(group: str, vendor: str, frame: pd.DataFrame) -> list[dict[str, Any]]:
    """Calcula estatísticas por variável, excluindo só valores ausentes."""
    rows = []
    for variable in VARIABLES:
        values = pd.to_numeric(frame[variable], errors="raise").dropna()
        rows.append({
            "grupo": group, "fabricante": vendor, "variavel": variable,
            "n": len(frame), "n_ausente": len(frame) - len(values),
            "mediana": values.median(), "q1": values.quantile(0.25),
            "q3": values.quantile(0.75), "media": values.mean(),
            "situacao": (
                "n insuficiente" if vendor != "todos" and len(frame) < 5 else ""
            ),
        })
    return rows


def describe_coverage(features: pd.DataFrame, labels: pd.DataFrame) -> pd.DataFrame:
    """Calcula os dois grupos pré-registrados no total e por fabricante.

    Aplica somente falha_extracao e terceiros de ``apply_exclusions``; a
    exclusão de indeterminados da 008 não vale para o grupo A.
    """
    _check_columns(features, labels)
    check_transient_failures(features)
    excluded = apply_exclusions(features, labels)
    blocked = {key for key, reasons in excluded.items() if set(reasons) & {
        c.REASON_EXTRACTION_FAILURE, c.REASON_THIRD_PARTY
    }}
    grouped = _grouped_labels(labels)
    grouped = grouped.loc[~grouped[c.KEY_COLUMN].isin(blocked)]
    ids = set(grouped[c.KEY_COLUMN])
    collapsed = collapse_aliases(features, ids, list(VARIABLES))
    vendors = _vendor_by_id(features, ids)
    selected = collapsed.merge(grouped, on=c.KEY_COLUMN, validate="one_to_one")
    selected = selected.merge(vendors, on=c.KEY_COLUMN, validate="one_to_one")
    rows = []
    for group in GROUPS:
        subset = selected.loc[selected["grupo"].eq(group)]
        rows.extend(_rows(group, "todos", subset))
        for vendor, frame in subset.groupby("meta_brand", sort=True):
            rows.extend(_rows(group, str(vendor), frame))
    return pd.DataFrame(rows, columns=COLUMNS)


def _markdown_table(table: pd.DataFrame) -> str:
    """Representa as linhas do CSV em tabela Markdown sem arredondamento adicional."""
    printable = table.copy()
    for column in ("mediana", "q1", "q3", "media"):
        printable[column] = printable[column].map(
            lambda value: "" if pd.isna(value) else f"{value:.6f}"
        )
    header = "| " + " | ".join(COLUMNS) + " |"
    separator = "|" + "|".join("---" for _ in COLUMNS) + "|"
    lines = [
        "# Cobertura NVD e proteções ELF",
        "",
        "Estatísticas descritivas por firmware_id. Valores ausentes não entram "
        "nas medidas; n inclui todos os IDs elegíveis do estrato.",
        "",
        header,
        separator,
    ]
    lines.extend(
        "| " + " | ".join(str(value) for value in row) + " |"
        for row in printable.itertuples(index=False, name=None)
    )
    lines.extend([
        "",
        "As diferenças descrevem associação neste corpus, não causalidade. "
        "A composição por fabricante é apresentada nos estratos acima; "
        "os rótulos e o protocolo de avaliação não são alterados.",
        "",
    ])
    return "\n".join(lines)


def write_coverage(
    table: pd.DataFrame, features_path: Path, labels_path: Path,
    config_path: Path, reports_dir: Path, generated_at: datetime,
) -> Path:
    """Grava CSV, parágrafo/tabela e metadados com hashes do pré-registro."""
    prereg_hash = file_sha256(PREREGISTRATION)
    if prereg_hash != PREREGISTRATION_SHA256:
        raise ValueError(f"Pré-registro alterado: {PREREGISTRATION}")
    stamp = generated_at.strftime("%Y%m%dT%H%M%SZ")
    directory = reports_dir / f"cobertura_nvd_{stamp}"
    directory.mkdir(parents=True, exist_ok=False)
    table.to_csv(directory / "cobertura_nvd.csv", index=False, float_format="%.6f")
    (directory / "report.md").write_text(_markdown_table(table), encoding="utf-8")
    inputs = {
        name: {"path": str(path), "sha256": file_sha256(path)}
        for name, path in (
            ("features", features_path), ("labels", labels_path),
            ("config", config_path), ("preregistro", PREREGISTRATION),
        )
    }
    meta = {"generated_at": generated_at.isoformat(timespec="seconds"),
            "commit": code_commit(), "inputs": inputs,
            "aggregation": "aliases de arquivo idênticos por firmware_id (008)"}
    (directory / "cobertura_nvd.meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return directory
