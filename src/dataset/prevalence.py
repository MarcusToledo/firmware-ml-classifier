"""Descreve a prevalência das colunas do vetor no corpus congelado.

A estatística é descritiva: fração de imagens com valor diferente de zero,
no total e por fabricante. O rótulo não é lido, para que a descrição não se
torne associação com a classe antes do treino.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from src.dataset import contract as c
from src.dataset.corpus import FREEZE_FILENAME
from src.dataset.partition import load_training_inputs
from src.run_metadata import code_commit, file_sha256

ALL_VENDORS = "todos"
PREVALENCE_COLUMNS = [
    "coluna",
    "fabricante",
    "n",
    "n_ausente",
    "n_presente",
    "prevalencia",
]


@dataclass(frozen=True)
class FrozenCorpus:
    """Contém vetor, fabricante por ID e o registro de congelamento."""

    features: pd.DataFrame
    vendors: pd.Series
    columns: list[str]
    freeze: dict[str, Any]


def _vendor_by_id(provenance: pd.DataFrame) -> pd.Series:
    """Retorna o fabricante único de cada ``firmware_id``.

    Levanta ValueError se algum ID tiver aliases de fabricantes distintos,
    porque a prevalência por fabricante contaria a imagem duas vezes.
    """
    vendors = provenance.groupby(c.KEY_COLUMN)["vendor"].unique()
    mixed = sorted(key for key, values in vendors.items() if len(values) > 1)
    if mixed:
        raise ValueError(f"firmware_id com mais de um fabricante: {mixed}")
    return vendors.map(lambda values: values[0]).rename("vendor")


def load_frozen_corpus(processed_dir: Path) -> FrozenCorpus:
    """Carrega a tabela da 008 e confere que é a registrada no congelamento.

    Levanta FileNotFoundError sem ``corpus.freeze.json`` e ValueError se o
    SHA256 da tabela ou as colunas do vetor divergirem do congelamento.
    """
    freeze_path = processed_dir / FREEZE_FILENAME
    if not freeze_path.is_file():
        raise FileNotFoundError(f"congelamento ausente: {freeze_path}")
    freeze = json.loads(freeze_path.read_text(encoding="utf-8"))
    inputs = load_training_inputs(processed_dir)
    frozen_hash = freeze["hashes"]["artifacts"]["table"]["sha256"]
    if inputs.table_sha256 != frozen_hash:
        raise ValueError(
            f"tabela {inputs.table_path} difere do congelamento: "
            f"congelado {frozen_hash}, atual {inputs.table_sha256}"
        )
    columns = list(freeze["columns_vector"])
    missing = sorted(set(columns) - set(inputs.table.columns))
    if missing:
        raise ValueError(f"colunas do congelamento ausentes na tabela: {missing}")
    features = inputs.table.set_index(c.KEY_COLUMN)[columns]
    vendors = _vendor_by_id(inputs.provenance).reindex(features.index)
    return FrozenCorpus(features, vendors, columns, freeze)


def _prevalence_rows(features: pd.DataFrame, vendor: str) -> list[dict[str, Any]]:
    """Conta valores ausentes e diferentes de zero de cada coluna."""
    rows = []
    for column in features.columns:
        values = features[column]
        valid = values.dropna()
        present = int((valid.astype(float) != 0).sum())
        rows.append(
            {
                "coluna": column,
                "fabricante": vendor,
                "n": len(values),
                "n_ausente": len(values) - len(valid),
                "n_presente": present,
                "prevalencia": present / len(valid) if len(valid) else float("nan"),
            }
        )
    return rows


def prevalence(corpus: FrozenCorpus) -> pd.DataFrame:
    """Calcula a prevalência de cada coluna no total e por fabricante.

    O denominador exclui valores ausentes, contados à parte em ``n_ausente``;
    ``prevalencia`` fica indefinida quando a coluna não tem valor no estrato.
    """
    rows = _prevalence_rows(corpus.features, ALL_VENDORS)
    for vendor, frame in corpus.features.groupby(corpus.vendors, sort=True):
        rows.extend(_prevalence_rows(frame, str(vendor)))
    return pd.DataFrame(rows, columns=PREVALENCE_COLUMNS)


def write_prevalence(
    table: pd.DataFrame,
    corpus: FrozenCorpus,
    processed_dir: Path,
    reports_dir: Path,
    generated_at: datetime,
) -> Path:
    """Grava ``prevalencia.csv`` e ``prevalencia.meta.json`` em diretório datado.

    O diretório ``<reports_dir>/prevalencia_<timestamp UTC>/`` nunca é
    reutilizado; o metadado liga a tabela ao congelamento e ao commit.
    """
    stamp = generated_at.strftime("%Y%m%dT%H%M%SZ")
    directory = reports_dir / f"prevalencia_{stamp}"
    directory.mkdir(parents=True, exist_ok=False)
    table.to_csv(directory / "prevalencia.csv", index=False, float_format="%.6f")
    freeze_path = processed_dir / FREEZE_FILENAME
    meta = {
        "generated_at": generated_at.isoformat(timespec="seconds"),
        "commit": code_commit(),
        "freeze": {"path": str(freeze_path), "sha256": file_sha256(freeze_path)},
        "frozen_at": corpus.freeze["frozen_at"],
        "table_sha256": corpus.freeze["hashes"]["artifacts"]["table"]["sha256"],
        "n_firmware_id": len(corpus.features),
        "columns": corpus.columns,
        "definition": (
            "prevalencia = n_presente / (n - n_ausente); presente = valor != 0; "
            "sem leitura do rótulo"
        ),
    }
    (directory / "prevalencia.meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return directory
