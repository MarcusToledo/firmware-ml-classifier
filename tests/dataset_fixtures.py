"""Monta entradas sintéticas da preparação da tabela de treino (spec 008)."""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

from src.dataset.corpus import freeze_corpus, load_freeze_config, write_freeze
from src.dataset.partition import PartitionConfig, build_partition, write_folds
from src.dataset.training_table import (
    build_training_table,
    load_dataset_config,
    write_artifacts,
)
from src.run_metadata import file_sha256

ONE_HOT_LISTS = {
    "fs_type": ["squashfs", "jffs2", "cramfs", "ubifs"],
    "compression_type": ["lzma", "gzip", "xz", "lzo"],
}


def feature_row(firmware_id: str, meta_path: str, **overrides: Any) -> dict[str, Any]:
    """Retorna linha válida de features; `overrides` substitui ou adiciona chaves."""
    parts = meta_path.split("/")
    row: dict[str, Any] = {
        "firmware_id": firmware_id,
        "entropy": 7.0,
        "byte_mean": 100.0,
        "n_filesystems": 1,
        "has_telnetd": False,
        "fs_type": "squashfs",
        "compression_type": "lzma",
        "unpacked_n_files": 10.0,
        "meta_path": meta_path,
        "meta_brand": parts[0],
        "meta_model": parts[1] if len(parts) > 1 else "",
        "meta_read_ok": True,
        "meta_binwalk_status": "ok",
        "meta_unpack_status": "ok",
        "meta_third_party": None,
        "meta_fs_status": "ok",
    }
    row.update(overrides)
    return row


def _label_rows(
    rows: list[dict[str, Any]],
    levels: dict[str, str],
    level_by_path: dict[str, str] | None,
) -> list[dict[str, Any]]:
    """Retorna uma linha de rótulo por linha de feature."""
    by_path = level_by_path or {}
    return [
        {
            "firmware_id": row["firmware_id"],
            "meta_path": row["meta_path"],
            "vendor": row["meta_brand"],
            "model": row["meta_model"],
            "version": "1.0",
            "version_source": "filename",
            "security_level": by_path.get(row["meta_path"], levels[row["firmware_id"]]),
            "cve_total": 0,
            "cvss_max": 0.0,
            "label_strategy": "test",
            "alias_count": 1,
        }
        for row in rows
    ]


def write_inputs(
    directory: Path,
    rows: list[dict[str, Any]],
    levels: dict[str, str],
    *,
    level_by_path: dict[str, str] | None = None,
    features_sha256: str | None = None,
) -> tuple[Path, Path]:
    """Grava features, rótulos e meta dos rótulos; retorna (features, labels).

    O `security_level` vem de `level_by_path[meta_path]` quando presente e de
    `levels[firmware_id]` nos demais casos. `features_sha256` força o valor
    registrado no meta; por padrão é o SHA256 real do parquet.
    """
    directory.mkdir(parents=True, exist_ok=True)
    features = directory / "features_v2.parquet"
    labels = directory / "labels_v2.csv"
    pd.DataFrame(rows).to_parquet(features, index=False)
    pd.DataFrame(_label_rows(rows, levels, level_by_path)).to_csv(labels, index=False)
    meta = {"features_sha256": features_sha256 or file_sha256(features)}
    (directory / "labels_v2.meta.json").write_text(json.dumps(meta) + "\n")
    return features, labels


def write_config(
    directory: Path, features: Path, labels: Path, output_dir: Path
) -> Path:
    """Grava `dataset.yaml` com as listas fixas do one-hot e retorna o caminho."""
    config = {
        "features": str(features),
        "labels": str(labels),
        "output_dir": str(output_dir),
        "one_hot": ONE_HOT_LISTS,
    }
    path = directory / "dataset.yaml"
    path.write_text(yaml.safe_dump(config, sort_keys=False))
    return path


def build_frozen_corpus(
    tmp_path: Path, rows: list[dict[str, Any]], levels: dict[str, str]
) -> Path:
    """Constrói entradas 008, folds 009 e congelamento de corpus sintético."""
    features, labels = write_inputs(tmp_path / "inputs", rows, levels)
    processed = tmp_path / "processed"
    config = write_config(tmp_path, features, labels, processed)
    write_artifacts(build_training_table(load_dataset_config(config, {})), processed)
    write_folds(build_partition(PartitionConfig(5, (0,), processed)), processed)
    raw = yaml.safe_load(config.read_text(encoding="utf-8"))
    raw["freeze"] = {"milestone": date(2026, 10, 11), "deviation_reason": "teste"}
    config.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")
    (tmp_path / "raw").mkdir()
    freeze_config = load_freeze_config(config, None, tmp_path / "raw")
    frozen_at = datetime(2026, 10, 30, 10, 0, tzinfo=timezone(timedelta(hours=-3)))
    write_freeze(freeze_corpus(freeze_config, frozen_at), processed)
    return processed
