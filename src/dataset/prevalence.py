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
import pyarrow.parquet as pq

from src.dataset import contract as c
from src.dataset.corpus import FREEZE_FILENAME
from src.dataset.partition import read_provenance
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


FROZEN_INPUTS = {
    "table": c.TABLE_FILENAME,
    "provenance": c.PROVENANCE_FILENAME,
    "table_meta": c.META_FILENAME,
}


def _check_frozen_hashes(processed_dir: Path, freeze: dict[str, Any]) -> None:
    """Confere tabela, proveniência e metadado contra os SHA256 congelados.

    Levanta FileNotFoundError sem algum artefato e ValueError com o arquivo e os
    dois hashes quando o conteúdo atual difere do registrado no congelamento.
    """
    artifacts = freeze["hashes"]["artifacts"]
    for key, name in FROZEN_INPUTS.items():
        path = processed_dir / name
        if not path.is_file():
            raise FileNotFoundError(f"artefato da 008 ausente: {path}")
        expected = artifacts[key]["sha256"]
        actual = file_sha256(path)
        if actual != expected:
            raise ValueError(
                f"{path} difere do congelamento: congelado {expected}, atual {actual}"
            )


def _vendor_by_id(provenance: pd.DataFrame, ids: pd.Index) -> pd.Series:
    """Retorna o fabricante único de cada ``firmware_id`` da tabela.

    Levanta ValueError se algum ID tiver aliases de fabricantes distintos,
    porque seria contado duas vezes, ou se faltar alias para algum ID.
    """
    vendors = provenance.groupby(c.KEY_COLUMN)["vendor"].unique()
    mixed = sorted(key for key, values in vendors.items() if len(values) > 1)
    if mixed:
        raise ValueError(f"firmware_id com mais de um fabricante: {mixed}")
    missing = sorted(set(ids) - set(vendors.index))
    if missing:
        raise ValueError(f"firmware_id sem alias na proveniência: {missing}")
    return vendors.map(lambda values: values[0]).rename("vendor").reindex(ids)


def load_frozen_corpus(processed_dir: Path) -> FrozenCorpus:
    """Carrega só o vetor e os fabricantes do corpus congelado, sem o rótulo.

    Levanta FileNotFoundError sem ``corpus.freeze.json`` ou artefato da 008 e
    ValueError se tabela, proveniência ou metadado divergirem do congelamento
    ou se faltar coluna do vetor na tabela.
    """
    freeze_path = processed_dir / FREEZE_FILENAME
    if not freeze_path.is_file():
        raise FileNotFoundError(f"congelamento ausente: {freeze_path}")
    freeze = json.loads(freeze_path.read_text(encoding="utf-8"))
    _check_frozen_hashes(processed_dir, freeze)
    table_path = processed_dir / c.TABLE_FILENAME
    columns = list(freeze["columns_vector"])
    missing = sorted(set(columns) - set(pq.read_schema(table_path).names))
    if missing:
        raise ValueError(f"colunas do congelamento ausentes em {table_path}: {missing}")
    features = (
        pd.read_parquet(table_path, columns=[c.KEY_COLUMN, *columns])
        .set_index(c.KEY_COLUMN)
        .sort_index()
    )
    provenance = read_provenance(processed_dir / c.PROVENANCE_FILENAME)
    vendors = _vendor_by_id(provenance, features.index)
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
