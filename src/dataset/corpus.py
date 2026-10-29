"""Congela o corpus elegível a partir dos artefatos da 008 e da 009 (008/FR-018).

O registro só é montado depois da validação da tabela (008/FR-015) e da
conferência dos hashes dos folds agrupados (009). Toda contagem vem dos
artefatos verificados nesta execução; nada é copiado de registros históricos.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

from src.dataset import contract as c
from src.dataset.partition import (
    FOLDS_FILENAME,
    FOLDS_META_FILENAME,
    ROLE_TEST,
    load_folds,
)
from src.dataset.validation import validate_artifacts
from src.run_metadata import code_commit, file_sha256

FREEZE_FILENAME = "corpus.freeze.json"


@dataclass(frozen=True)
class FreezeConfig:
    """Contém caminhos, marco do cronograma e motivo do desvio."""

    config_path: Path
    processed_dir: Path
    raw_root: Path
    milestone: date
    deviation_reason: str


def load_freeze_config(
    path: Path, processed_dir: Path | None, raw_root: Path
) -> FreezeConfig:
    """Lê a seção ``freeze`` e o diretório processado da configuração.

    Levanta FileNotFoundError sem o arquivo e ValueError quando o marco não é
    data ISO ou o motivo do desvio não é texto.
    """
    if not path.is_file():
        raise FileNotFoundError(f"--config não encontrado: {path}")
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    section = raw.get("freeze") if isinstance(raw, dict) else None
    if not isinstance(section, dict):
        raise ValueError(f"Configuração inválida em {path}: freeze")
    milestone = section.get("milestone")
    if not isinstance(milestone, date) or isinstance(milestone, datetime):
        raise ValueError(f"Configuração inválida em {path}: freeze.milestone")
    reason = section.get("deviation_reason", "")
    if not isinstance(reason, str):
        raise ValueError(f"Configuração inválida em {path}: freeze.deviation_reason")
    directory = processed_dir or raw.get("output_dir")
    if not isinstance(directory, (str, Path)) or not str(directory).strip():
        raise ValueError(f"Configuração inválida em {path}: output_dir")
    return FreezeConfig(path, Path(directory), raw_root, milestone, reason.strip())


def deviation_record(milestone: date, frozen_at: datetime, reason: str) -> dict:
    """Registra marco, data efetiva e motivo; exige motivo quando há atraso.

    Levanta ValueError se a data efetiva passa do marco sem motivo registrado.
    """
    effective = frozen_at.date()
    days = (effective - milestone).days
    if days > 0 and not reason:
        raise ValueError(
            f"congelamento {days} dias após o marco {milestone.isoformat()} "
            "sem freeze.deviation_reason"
        )
    return {
        "milestone": milestone.isoformat(),
        "effective_date": effective.isoformat(),
        "days_after_milestone": days,
        "reason": reason or None,
    }


def eligibility_criteria() -> dict[str, Any]:
    """Descreve, a partir do contrato da 008, quem entra no corpus."""
    return {
        "target_classes": list(c.TARGET_CLASSES),
        "exclusion_reasons": list(c.REASON_ORDER),
        "extraction_failure_states": {
            "meta_binwalk_status": sorted(c.BINWALK_EXCLUDE),
            "meta_unpack_status": sorted(c.UNPACK_EXCLUDE),
            "meta_fs_status": sorted(c.FS_EXCLUDE),
        },
        "third_party": "meta_third_party não nulo em algum alias",
        "indeterminate": f"{c.TARGET_COLUMN} == {c.REASON_INDETERMINATE}",
        "subset": None,
    }


def support(table: pd.DataFrame, folds: pd.DataFrame) -> dict[str, Any]:
    """Conta IDs por classe e por componente conectado com suas classes.

    Levanta ValueError se algum ID da tabela não tiver componente nos folds.
    """
    groups = (
        folds.loc[folds["role"] == ROLE_TEST, [c.KEY_COLUMN, "group"]]
        .drop_duplicates()
        .set_index(c.KEY_COLUMN)["group"]
    )
    labelled = table[[c.KEY_COLUMN, c.TARGET_COLUMN]].assign(
        group=table[c.KEY_COLUMN].map(groups)
    )
    if labelled["group"].isna().any():
        missing = sorted(labelled.loc[labelled["group"].isna(), c.KEY_COLUMN])
        raise ValueError(f"firmware_id sem componente nos folds: {missing[:10]}")
    classes = labelled[c.TARGET_COLUMN].value_counts()
    per_group = [
        {
            "group": str(name),
            "n": len(rows),
            "classes": {
                label: int((rows[c.TARGET_COLUMN] == label).sum())
                for label in c.TARGET_CLASSES
            },
        }
        for name, rows in labelled.groupby("group", sort=True)
    ]
    return {
        "n_firmware_id": len(labelled),
        "by_class": {label: int(classes.get(label, 0)) for label in c.TARGET_CLASSES},
        "n_groups": len(per_group),
        "groups_with_class": {
            label: sum(entry["classes"][label] > 0 for entry in per_group)
            for label in c.TARGET_CLASSES
        },
        "by_group": per_group,
    }


def _artifact_hashes(config: FreezeConfig, table_meta: dict) -> dict[str, Any]:
    """Reúne caminho e SHA256 de configuração, entradas, tabela e folds."""
    directory = config.processed_dir
    produced = {
        "table": directory / c.TABLE_FILENAME,
        "exclusions": directory / c.EXCLUSIONS_FILENAME,
        "provenance": directory / c.PROVENANCE_FILENAME,
        "table_meta": directory / c.META_FILENAME,
        "folds": directory / FOLDS_FILENAME,
        "folds_meta": directory / FOLDS_META_FILENAME,
    }
    return {
        "config": {
            "path": config.config_path.as_posix(),
            "sha256": file_sha256(config.config_path),
        },
        "inputs": table_meta["inputs"],
        "artifacts": {
            name: {"path": path.as_posix(), "sha256": file_sha256(path)}
            for name, path in produced.items()
        },
    }


def freeze_corpus(config: FreezeConfig, frozen_at: datetime) -> dict[str, Any]:
    """Valida 008 e 009 e monta o registro de congelamento sem gravar.

    Levanta FileNotFoundError sem ``raw_root`` e ValueError com os problemas
    da validação da 008, hashes divergentes dos folds ou desvio sem motivo.
    """
    if not config.raw_root.is_dir():
        raise FileNotFoundError(f"diretório de firmwares ausente: {config.raw_root}")
    issues = validate_artifacts(config.processed_dir, config.raw_root)
    if issues:
        raise ValueError(f"validação da 008 falhou: {issues}")
    fold_set = load_folds(config.processed_dir)
    table_meta = json.loads(
        (config.processed_dir / c.META_FILENAME).read_text(encoding="utf-8")
    )
    return {
        "frozen_at": frozen_at.isoformat(timespec="seconds"),
        "deviation": deviation_record(
            config.milestone, frozen_at, config.deviation_reason
        ),
        "commit": code_commit(),
        "effective_config": {
            "dataset": table_meta["config"],
            "partition": fold_set.meta["config"],
            "group_rule": fold_set.meta["group_rule"],
        },
        "hashes": _artifact_hashes(config, table_meta),
        "columns_vector": table_meta["columns_vector"],
        "eligibility": eligibility_criteria(),
        "exclusions": {
            key: table_meta["counts"][key]
            for key in (
                "input_firmware_ids",
                "excluded_firmware_ids",
                "excluded_by_reason",
                "excluded_by_vendor_reason",
                "indeterminate_by_vendor",
            )
        },
        "support": support(fold_set.table, fold_set.folds),
    }


def write_freeze(manifest: dict[str, Any], processed_dir: Path) -> Path:
    """Grava o registro; recusa sobrescrever um congelamento existente.

    Levanta FileExistsError quando ``corpus.freeze.json`` já existe.
    """
    path = processed_dir / FREEZE_FILENAME
    if path.exists():
        raise FileExistsError(
            f"{path} já existe; congelamento não é sobrescrito. Remova-o "
            "explicitamente e registre o motivo antes de congelar de novo"
        )
    path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return path
