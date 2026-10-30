"""Exercita a prevalência descritiva sobre um corpus congelado real (008/FR-020)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.dataset import contract as c
from src.dataset.prevalence import ALL_VENDORS, load_frozen_corpus, prevalence
from src.run_metadata import file_sha256
from tests.dataset_fixtures import build_frozen_corpus, feature_row

TELNETD_IDS = {"id-00", "id-01", "id-10"}


def _frozen(tmp_path: Path) -> Path:
    """Gera tabela, folds e congelamento de dois fabricantes; retorna o diretório."""
    rows = []
    for index in range(15):
        firmware_id = f"id-{index:02}"
        vendor = "acme" if index < 10 else "beta"
        overrides = {"has_telnetd": firmware_id in TELNETD_IDS}
        if firmware_id == "id-02":
            overrides["unpacked_n_files"] = float("nan")
        rows.append(feature_row(firmware_id, f"{vendor}/m{index}/fw.bin", **overrides))
    levels = {f"id-{i:02}": c.TARGET_CLASSES[i % 3] for i in range(15)}
    return build_frozen_corpus(tmp_path, rows, levels)


def _row(table, column: str, vendor: str) -> dict:
    """Retorna a linha de uma coluna num estrato."""
    selected = table[(table["coluna"] == column) & (table["fabricante"] == vendor)]
    assert len(selected) == 1
    return selected.iloc[0].to_dict()


def test_prevalence_by_vendor_and_missing_values(tmp_path: Path) -> None:
    """Conta por fabricante, tira ausentes do denominador e não carrega rótulo."""
    corpus = load_frozen_corpus(_frozen(tmp_path))
    assert c.TARGET_COLUMN not in corpus.features.columns
    table = prevalence(corpus)

    total = _row(table, "has_telnetd", ALL_VENDORS)
    assert (total["n"], total["n_presente"]) == (15, 3)
    assert total["prevalencia"] == pytest.approx(3 / 15)
    assert _row(table, "has_telnetd", "acme")["prevalencia"] == pytest.approx(2 / 10)
    assert _row(table, "has_telnetd", "beta")["prevalencia"] == pytest.approx(1 / 5)

    files = _row(table, "unpacked_n_files", "acme")
    assert (files["n"], files["n_ausente"], files["n_presente"]) == (10, 1, 9)
    assert files["prevalencia"] == pytest.approx(1.0)


def test_table_differing_from_freeze_is_refused(tmp_path: Path) -> None:
    """Recusa descrever uma tabela que não é a registrada no congelamento."""
    processed = _frozen(tmp_path)
    table = processed / c.TABLE_FILENAME
    table.write_bytes(table.read_bytes() + b"x")

    with pytest.raises(ValueError, match="training_table.parquet difere"):
        load_frozen_corpus(processed)


def test_vendor_change_consistent_with_008_meta_is_refused(tmp_path: Path) -> None:
    """Recusa proveniência regravada com metadado da 008 atualizado após o congelamento.

    A tabela fica intacta e o metadado da 008 continua coerente com a nova
    proveniência; só o congelamento revela que os estratos mudaram.
    """
    processed = _frozen(tmp_path)
    provenance = processed / c.PROVENANCE_FILENAME
    provenance.write_text(
        provenance.read_text(encoding="utf-8").replace('"beta"', '"acme"'),
        encoding="utf-8",
    )
    meta_path = processed / c.META_FILENAME
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta["outputs"]["provenance"]["sha256"] = file_sha256(provenance)
    meta_path.write_text(json.dumps(meta), encoding="utf-8")

    with pytest.raises(ValueError, match="training_table_provenance.jsonl difere"):
        load_frozen_corpus(processed)
