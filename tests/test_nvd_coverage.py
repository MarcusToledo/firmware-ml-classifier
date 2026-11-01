"""Exercita a cobertura NVD pré-registrada em entradas sintéticas."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest

from src.dataset.nvd_coverage import describe_coverage
from src.run_metadata import file_sha256
from tests.dataset_fixtures import feature_row, write_config, write_inputs

COLUMNS = (
    "unpacked_prop_nx",
    "unpacked_prop_pie",
    "unpacked_prop_relro_full",
    "unpacked_prop_relro_partial",
    "unpacked_prop_canary",
)


def _inputs(tmp_path: Path) -> tuple[pd.DataFrame, pd.DataFrame, Path, Path, Path]:
    """Monta dois grupos, aliases, valores ausentes e exclusões por ID."""
    rows = []
    levels = {}
    for index in range(13):
        firmware_id = f"id-{index:02}"
        vendor = "acme" if index < 10 else "beta"
        level = "indeterminado" if index < 7 else "sem_cve_conhecida"
        levels[firmware_id] = level
        value = float(index % 5) / 4
        overrides = {column: value for column in COLUMNS}
        if index == 2:
            overrides[COLUMNS[0]] = float("nan")
        if index == 11:
            overrides["meta_unpack_status"] = "falha"
        if index == 12:
            overrides["meta_third_party"] = "terceiros"
        rows.append(feature_row(firmware_id, f"{vendor}/m/fw{index}.bin", **overrides))
    rows.append(feature_row("id-00", "acme/m/fw0-alias.bin", **{
        column: 0.0 for column in COLUMNS
    }))
    features_path, labels_path = write_inputs(tmp_path, rows, levels)
    labels = pd.read_csv(labels_path)
    labels["evidence_reason"] = labels["security_level"].map(
        {
            "indeterminado": "nao_encontrado",
            "sem_cve_conhecida": "produto_encontrado_sem_cve",
        }
    )
    labels.loc[labels["firmware_id"] == "id-06", "evidence_reason"] = "outro"
    labels.to_csv(labels_path, index=False)
    config_path = write_config(tmp_path, features_path, labels_path, tmp_path)
    return (
        pd.read_parquet(features_path), labels, features_path, labels_path,
        config_path,
    )


def _row(table: pd.DataFrame, group: str, vendor: str, column: str) -> pd.Series:
    """Seleciona única linha por grupo, fabricante e variável."""
    selected = table.loc[
        (table["grupo"] == group)
        & (table["fabricante"] == vendor)
        & (table["variavel"] == column)
    ]
    assert len(selected) == 1
    return selected.iloc[0]


def test_groups_exclusions_statistics_and_missing(tmp_path: Path) -> None:
    """Conta IDs, exclui falhas/terceiros e calcula quartis só dos presentes."""
    features, labels, *_ = _inputs(tmp_path)
    table = describe_coverage(features, labels)
    a = _row(table, "nao_encontrado", "todos", COLUMNS[0])
    assert (a["n"], a["n_ausente"]) == (6, 1)
    assert (a["mediana"], a["q1"], a["q3"], a["media"]) == pytest.approx(
        (0.25, 0.0, 0.75, 0.4)
    )
    assert _row(table, "sem_cve_confirmado", "todos", COLUMNS[0])["n"] == 4
    assert (
        _row(table, "sem_cve_confirmado", "acme", COLUMNS[0])["situacao"]
        == "n insuficiente"
    )
    assert _row(table, "sem_cve_confirmado", "beta", COLUMNS[0])["n"] == 1
    assert _row(table, "nao_encontrado", "acme", COLUMNS[0])["situacao"] == ""
    assert len(table) == 25


def test_all_values_missing_still_counts_ids(tmp_path: Path) -> None:
    """Mantém denominador e deixa quartis/média indefinidos sem presentes."""
    features, labels, *_ = _inputs(tmp_path)
    ids_a = labels.loc[
        labels["evidence_reason"].eq("nao_encontrado"), "firmware_id"
    ]
    features.loc[features["firmware_id"].isin(ids_a), COLUMNS[1]] = float("nan")
    row = _row(
        describe_coverage(features, labels), "nao_encontrado", "todos", COLUMNS[1]
    )
    assert (row["n"], row["n_ausente"]) == (6, 6)
    assert all(pd.isna(row[column]) for column in ("mediana", "q1", "q3", "media"))


def test_rejects_divergent_alias_features(tmp_path: Path) -> None:
    """Não escolhe arbitrariamente entre medidas divergentes de aliases."""
    features, labels, *_ = _inputs(tmp_path)
    features.loc[features["meta_path"].str.contains("alias"), COLUMNS[0]] = 1.0
    with pytest.raises(ValueError, match="Aliases com features divergentes"):
        describe_coverage(features, labels)


def test_writes_report_and_input_hashes(tmp_path: Path) -> None:
    """Persiste tabela, relatório e proveniência dos arquivos de entrada."""
    _, _, features_path, labels_path, config_path = _inputs(tmp_path)
    result = subprocess.run(
        [
            sys.executable,
            "scripts/describe_nvd_coverage.py",
            "--config",
            str(config_path),
            "--reports-dir",
            str(tmp_path / "reports"),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    directories = list((tmp_path / "reports").glob("cobertura_nvd_*"))
    assert len(directories) == 1, result.stderr
    directory = directories[0]
    meta = json.loads((directory / "cobertura_nvd.meta.json").read_text())
    assert meta["inputs"]["features"]["sha256"] == file_sha256(features_path)
    assert meta["inputs"]["labels"]["sha256"] == file_sha256(labels_path)
    assert meta["inputs"]["config"]["sha256"] == file_sha256(config_path)
    assert meta["inputs"]["preregistro"]["sha256"] == (
        "8b4693da40d1ab2d23c6887e38bce6b872c2572a8cabbf9407a75f8b82f0a138"
    )
    assert "| nao_encontrado |" in (directory / "report.md").read_text()
    table = pd.read_csv(directory / "cobertura_nvd.csv")
    assert len(table) == 25
    assert _row(table, "nao_encontrado", "todos", COLUMNS[0])["n_ausente"] == 1
