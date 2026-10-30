"""Baselines majoritário, de identidade e de score pré-registrado (010)."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from src.dataset import contract as c
from src.dataset.partition import normalize_key
from src.dataset.training_table import collapse_aliases, input_feature_columns
from src.run_metadata import file_sha256
from src.scoring import ScoringConfig, score_firmware


def majority_class(y_train: pd.Series, classes: tuple[str, ...]) -> str:
    """Retorna a classe mais frequente, desempatando pela ordem fixa."""
    counts = y_train.value_counts()
    return max(
        classes, key=lambda label: (int(counts.get(label, 0)), -classes.index(label))
    )


def identity_features(provenance: pd.DataFrame, ids: pd.Index) -> pd.DataFrame:
    """Codifica todos os fabricantes de aliases de cada ID em multi-hot."""
    aliases = provenance[[c.KEY_COLUMN, "vendor"]].drop_duplicates().copy()
    aliases["vendor"] = aliases["vendor"].map(normalize_key)
    names = sorted(aliases["vendor"].unique())
    encoded = pd.DataFrame(0.0, index=ids, columns=[f"fabricante__{v}" for v in names])
    for firmware_id, vendor in aliases.itertuples(index=False, name=None):
        if firmware_id in encoded.index:
            encoded.at[firmware_id, f"fabricante__{vendor}"] = 1.0
    return encoded


def load_scoring_features(
    processed_dir: Path, ids: list[str]
) -> tuple[pd.DataFrame, dict[str, str], list[str]]:
    """Lê features brutas verificadas e reúne os detectores T13-A lidos.

    Levanta ValueError quando a fonte diverge do SHA256 registrado pela 008.
    """
    meta_path = processed_dir / c.META_FILENAME
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    registered = meta["inputs"]["features"]
    path = Path(registered["path"])
    expected = registered["sha256"]
    actual = file_sha256(path)
    if actual != expected:
        raise ValueError(
            f"{path} difere de training_table.meta.json: "
            f"registrado {expected}, atual {actual}"
        )
    features = pd.read_parquet(path)
    columns = input_feature_columns(features)
    collapsed = collapse_aliases(features, set(ids), columns)
    t13a = sorted(
        name for name in columns
        if meta["column_changes"].get(name, "").startswith("t13a_")
    )
    source = {"path": str(path), "sha256": actual}
    return collapsed.set_index(c.KEY_COLUMN).reindex(ids), source, t13a


def score_firmware_levels(rows: pd.DataFrame, scoring: ScoringConfig) -> pd.Series:
    """Retorna o nível do score fixo para cada firmware, sem ajuste."""
    return rows.apply(lambda row: score_firmware(row.to_dict(), scoring).level, axis=1)
