"""Prepara tabela de treino auditável a partir de features e rótulos."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

from src.cli_utils import apply_overrides
from src.dataset import contract as c
from src.run_metadata import code_commit, file_sha256

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class DatasetConfig:
    """Representa a configuração efetiva da preparação."""

    features: Path
    labels: Path
    output_dir: Path
    one_hot: dict[str, tuple[str, ...]]

    def as_dict(self) -> dict[str, Any]:
        """Retorna caminhos POSIX e categorias como listas serializáveis."""
        return {
            "features": self.features.as_posix(),
            "labels": self.labels.as_posix(),
            "output_dir": self.output_dir.as_posix(),
            "one_hot": {key: list(values) for key, values in self.one_hot.items()},
        }


@dataclass(frozen=True)
class InputTables:
    """Agrupa as entradas verificadas e seus hashes."""

    features: pd.DataFrame
    labels: pd.DataFrame
    features_sha256: str
    labels_sha256: str
    labels_meta_path: Path
    labels_meta_sha256: str


@dataclass(frozen=True)
class ExclusionReport:
    """Agrupa exclusões e contagens por motivo e fabricante."""

    frame: pd.DataFrame
    by_reason: dict[str, int]
    by_vendor: dict[str, int]
    by_vendor_reason: dict[str, dict[str, int]]
    multi_vendor_ids: int


@dataclass(frozen=True)
class PreparedDataset:
    """Contém a tabela pronta e os artefatos ainda não gravados."""

    table: pd.DataFrame
    exclusions: pd.DataFrame
    provenance: list[dict[str, Any]]
    metadata: dict[str, Any]


def load_dataset_config(path: Path, overrides: dict[str, Any]) -> DatasetConfig:
    """Lê a configuração e exige categorias fixas sem ambiguidades."""
    if not path.is_file():
        raise FileNotFoundError(f"--config não encontrado: {path}")
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"Configuração inválida em {path}: esperado mapa")
    config = apply_overrides(raw, overrides)
    paths: dict[str, Path] = {}
    for key in ("features", "labels", "output_dir"):
        value = config.get(key)
        if not isinstance(value, (str, Path)) or not str(value).strip():
            raise ValueError(f"Configuração inválida em {path}: {key}")
        paths[key] = Path(value)
    hot = config.get("one_hot")
    if not isinstance(hot, dict):
        raise ValueError(f"Configuração inválida em {path}: one_hot")
    categories: dict[str, tuple[str, ...]] = {}
    for key in c.ONE_HOT_SOURCES:
        values = hot.get(key)
        if (
            not isinstance(values, list)
            or not values
            or any(not isinstance(v, str) or not v.strip() for v in values)
            or len(set(values)) != len(values)
            or bool({c.ONE_HOT_OTHER, c.ONE_HOT_MISSING} & set(values))
        ):
            raise ValueError(f"Configuração inválida em {path}: one_hot.{key}")
        categories[key] = tuple(values)
    return DatasetConfig(
        paths["features"], paths["labels"], paths["output_dir"], categories
    )


def _require_columns(frame: pd.DataFrame, path: Path, columns: tuple[str, ...]) -> None:
    """Exige colunas da entrada e orienta reextração para status ausente."""
    for column in columns:
        if column not in frame:
            advice = (
                "; extraia as features de novo com scripts/extract_features.py"
                if column in c.EXTRACTION_STATUS_COLUMNS
                else ""
            )
            raise ValueError(f"Coluna ausente em {path}: {column}{advice}")


def _read_features(path: Path) -> pd.DataFrame:
    """Lê a tabela de features em parquet ou CSV; rejeita outros formatos."""
    if path.suffix == ".parquet":
        return pd.read_parquet(path)
    if path.suffix == ".csv":
        return pd.read_csv(path)
    raise ValueError(f"Formato de features inválido: {path}")


def load_inputs(config: DatasetConfig) -> InputTables:
    """Lê entradas e confere vínculo criptográfico entre features e rótulos."""
    meta_path = config.labels.with_name(f"{config.labels.stem}.meta.json")
    for path in (config.features, config.labels, meta_path):
        if not path.is_file():
            raise FileNotFoundError(f"Entrada não encontrada: {path}")
    features = _read_features(config.features)
    labels = pd.read_csv(config.labels)
    _require_columns(
        features,
        config.features,
        (
            c.KEY_COLUMN,
            *c.IDENTITY_COLUMNS,
            *c.EXTRACTION_STATUS_COLUMNS,
            *c.ONE_HOT_SOURCES,
        ),
    )
    _require_columns(labels, config.labels, (c.KEY_COLUMN, c.TARGET_COLUMN))
    invalid = labels[c.TARGET_COLUMN].isna() | ~labels[c.TARGET_COLUMN].isin(
        c.LABEL_VALUES
    )
    if invalid.any():
        ids = sorted(labels.loc[invalid, c.KEY_COLUMN].astype(str).unique())
        raise ValueError(f"{config.labels}: security_level inválido para {ids}")
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    actual = file_sha256(config.features)
    expected = meta.get("features_sha256") if isinstance(meta, dict) else None
    if expected != actual:
        raise ValueError(
            f"{meta_path}: features_sha256 registrado {expected}, atual {actual}"
        )
    return InputTables(
        features,
        labels,
        actual,
        file_sha256(config.labels),
        meta_path,
        file_sha256(meta_path),
    )


def _check_ids(inputs: InputTables, config: DatasetConfig) -> None:
    """Rejeita IDs nulos ou sem par antes de filtrar qualquer alias."""
    features, labels = inputs.features, inputs.labels
    nulls = features[c.KEY_COLUMN].isna()
    if nulls.any():
        paths = sorted(features.loc[nulls, "meta_path"].astype(str).tolist())
        raise ValueError(
            f"{config.features}: firmware_id nulo em {paths}; "
            "extraia as features de novo"
        )
    feature_ids = set(features[c.KEY_COLUMN])
    label_ids = set(labels[c.KEY_COLUMN])
    if feature_ids != label_ids:
        raise ValueError(
            f"firmware_id sem par: {config.features}: "
            f"{sorted(feature_ids - label_ids)}; "
            f"{config.labels}: {sorted(label_ids - feature_ids)}"
        )


def check_transient_failures(features: pd.DataFrame) -> None:
    """Interrompe em estados transitórios ou desconhecidos de qualquer alias."""
    states = (
        ("meta_binwalk_status", c.BINWALK_KEEP, c.BINWALK_EXCLUDE, c.BINWALK_ABORT),
        ("meta_unpack_status", c.UNPACK_KEEP, c.UNPACK_EXCLUDE, c.UNPACK_ABORT),
        ("meta_fs_status", c.FS_KEEP, c.FS_EXCLUDE, frozenset()),
    )
    transient: list[str] = []
    unknown: list[str] = []
    for column, keep, exclude, abort in states:
        for path, value in zip(features["meta_path"], features[column]):
            detail = f"{path}: {column}={value}"
            if pd.isna(value) or value not in keep | exclude | abort:
                unknown.append(detail)
            elif value in abort:
                transient.append(detail)
    if transient:
        raise ValueError(
            f"Falha transitória em {sorted(transient)}; extraia as features de novo"
        )
    if unknown:
        raise ValueError(f"estado desconhecido em {sorted(unknown)}")


def apply_exclusions(
    features: pd.DataFrame, labels: pd.DataFrame
) -> dict[str, tuple[str, ...]]:
    """Reúne todos os motivos para cada ID excluído, na ordem contratada."""
    failure = (
        features["meta_binwalk_status"].isin(c.BINWALK_EXCLUDE)
        | features["meta_unpack_status"].isin(c.UNPACK_EXCLUDE)
        | features["meta_fs_status"].isin(c.FS_EXCLUDE)
    )
    by_reason = {
        c.REASON_EXTRACTION_FAILURE: set(features.loc[failure, c.KEY_COLUMN]),
        c.REASON_THIRD_PARTY: set(
            features.loc[features["meta_third_party"].notna(), c.KEY_COLUMN]
        ),
        c.REASON_INDETERMINATE: set(
            labels.loc[labels[c.TARGET_COLUMN] == c.REASON_INDETERMINATE, c.KEY_COLUMN]
        ),
    }
    return {
        firmware_id: tuple(
            reason for reason in c.REASON_ORDER if firmware_id in by_reason[reason]
        )
        for firmware_id in sorted(set().union(*by_reason.values()))
    }


def _vendors_by_id(features: pd.DataFrame) -> dict[str, tuple[str, ...]]:
    """Retorna fabricantes distintos de cada ID em ordem estável."""
    return {
        firmware_id: tuple(sorted(set(group["meta_brand"])))
        for firmware_id, group in features.groupby(c.KEY_COLUMN, sort=True)
    }


def build_exclusions(
    features: pd.DataFrame, reasons: dict[str, tuple[str, ...]]
) -> ExclusionReport:
    """Monta registro de exclusões e contagens sem duplicar aliases."""
    vendors = _vendors_by_id(features)
    rows = [
        (firmware_id, ";".join(reasons[firmware_id]), ";".join(vendors[firmware_id]))
        for firmware_id in sorted(reasons)
    ]
    frame = pd.DataFrame(rows, columns=[c.KEY_COLUMN, "reasons", "vendors"])
    by_reason = {reason: 0 for reason in c.REASON_ORDER}
    by_vendor = {
        vendor: 0 for firmware_id in sorted(reasons) for vendor in vendors[firmware_id]
    }
    by_vendor_reason = {
        vendor: {reason: 0 for reason in c.REASON_ORDER} for vendor in sorted(by_vendor)
    }
    for firmware_id, causes in sorted(reasons.items()):
        for reason in causes:
            by_reason[reason] += 1
        for vendor in vendors[firmware_id]:
            by_vendor[vendor] += 1
            for reason in causes:
                by_vendor_reason[vendor][reason] += 1
    return ExclusionReport(
        frame,
        by_reason,
        dict(sorted(by_vendor.items())),
        by_vendor_reason,
        sum(len(vendors[firmware_id]) > 1 for firmware_id in reasons),
    )


def _indeterminate_by_vendor(
    features: pd.DataFrame, labels: pd.DataFrame
) -> dict[str, dict[str, int | float]]:
    """Calcula proporção de IDs indeterminados por fabricante da entrada."""
    indeterminate = set(
        labels.loc[labels[c.TARGET_COLUMN] == c.REASON_INDETERMINATE, c.KEY_COLUMN]
    )
    counts: dict[str, dict[str, int | float]] = {}
    for firmware_id, vendors in _vendors_by_id(features).items():
        for vendor in vendors:
            entry = counts.setdefault(vendor, {"indeterminado": 0, "total": 0})
            entry["total"] += 1
            entry["indeterminado"] += firmware_id in indeterminate
    for entry in counts.values():
        entry["proporcao"] = round(entry["indeterminado"] / entry["total"], 4)
    return dict(sorted(counts.items()))


def input_feature_columns(features: pd.DataFrame) -> list[str]:
    """Lista as colunas de feature na ordem original da entrada."""
    return [
        name
        for name in features.columns
        if name != c.KEY_COLUMN and not name.startswith("meta_")
    ]


def select_feature_columns(columns: list[str]) -> tuple[list[str], dict[str, str]]:
    """Filtra Doc2Vec e textos categóricos, mas rejeita vazamento de CVE."""
    selected: list[str] = []
    changes: dict[str, str] = {}
    for column in columns:
        if column in c.FORBIDDEN_COLUMNS or column.startswith("cve_count_"):
            raise ValueError(f"Coluna de vazamento na tabela de features: {column}")
        if column.startswith("doc2vec_"):
            changes[column] = c.CHANGE_DOC2VEC
        elif column in c.ONE_HOT_SOURCES:
            changes[column] = c.CHANGE_ONE_HOT
        else:
            selected.append(column)
    return selected, changes


def collapse_aliases(
    features: pd.DataFrame, keep_ids: set[str], columns: list[str]
) -> pd.DataFrame:
    """Verifica igualdade das features entre aliases e conserva um por ID."""
    eligible = features.loc[features[c.KEY_COLUMN].isin(keep_ids)]
    differences: list[str] = []
    for firmware_id, group in eligible.groupby(c.KEY_COLUMN, sort=True):
        different = [col for col in columns if group[col].nunique(dropna=False) > 1]
        if different:
            differences.append(f"{firmware_id}: {', '.join(different)}")
    if differences:
        raise ValueError(f"Aliases com features divergentes: {'; '.join(differences)}")
    ordered = eligible.sort_values([c.KEY_COLUMN, "meta_path"], kind="stable")
    return ordered.drop_duplicates(c.KEY_COLUMN)[[c.KEY_COLUMN, *columns]].reset_index(
        drop=True
    )


def join_labels(collapsed: pd.DataFrame, labels: pd.DataFrame) -> pd.DataFrame:
    """Exige alvo idêntico entre aliases mantidos e anexa só o alvo."""
    kept = labels.loc[labels[c.KEY_COLUMN].isin(collapsed[c.KEY_COLUMN])]
    different = [
        firmware_id
        for firmware_id, group in kept.groupby(c.KEY_COLUMN, sort=True)
        if group[c.TARGET_COLUMN].nunique(dropna=False) > 1
    ]
    if different:
        raise ValueError(f"security_level divergente entre aliases: {different}")
    distinct = kept.drop_duplicates(c.KEY_COLUMN)[[c.KEY_COLUMN, c.TARGET_COLUMN]]
    return collapsed.merge(distinct, on=c.KEY_COLUMN, how="left", validate="one_to_one")


def one_hot_fixed(
    frame: pd.DataFrame, column: str, categories: tuple[str, ...]
) -> pd.DataFrame:
    """Codifica categoria fixa, desconhecida ou ausente em colunas int8."""
    source = frame[column]
    names = (*categories, c.ONE_HOT_OTHER, c.ONE_HOT_MISSING)
    result = pd.DataFrame(index=frame.index)
    for category in names:
        if category == c.ONE_HOT_MISSING:
            matches = source.isna()
        elif category == c.ONE_HOT_OTHER:
            matches = source.notna() & ~source.isin(categories)
        else:
            matches = source.eq(category).fillna(False)
        result[f"{column}{c.ONE_HOT_SEPARATOR}{category}"] = matches.astype("int8")
    return result


def constant_columns(table: pd.DataFrame, vector_columns: list[str]) -> list[str]:
    """Identifica constantes sem retirar colunas do vetor."""
    return [col for col in vector_columns if table[col].nunique(dropna=False) <= 1]


def column_report(
    columns: list[str], vector: list[str], changes: dict[str, str]
) -> dict[str, Any]:
    """Registra colunas de entrada, vetor e motivos de transformação."""
    return {
        "columns_input": columns,
        "columns_vector": vector,
        "column_changes": changes,
    }


def build_provenance(
    features: pd.DataFrame, table_ids: set[str], excluded_ids: set[str]
) -> list[dict[str, Any]]:
    """Registra todos os aliases, fora do vetor, ordenados por caminho."""
    provenance: list[dict[str, Any]] = []
    for firmware_id, group in features.groupby(c.KEY_COLUMN, sort=True):
        if firmware_id not in table_ids | excluded_ids:
            continue
        aliases = [
            {
                "meta_path": row.meta_path,
                "vendor": row.meta_brand,
                "model": row.meta_model,
            }
            for row in group.sort_values("meta_path", kind="stable").itertuples()
        ]
        provenance.append(
            {
                "firmware_id": firmware_id,
                "in_table": firmware_id in table_ids,
                "aliases": aliases,
            }
        )
    return provenance


def _make_table(
    joined: pd.DataFrame, columns: list[str], config: DatasetConfig
) -> pd.DataFrame:
    """Substitui textos pelos blocos one-hot preservando ordem e valores."""
    parts = [joined[[c.KEY_COLUMN]]]
    for column in columns:
        if column in c.ONE_HOT_SOURCES:
            parts.append(one_hot_fixed(joined, column, config.one_hot[column]))
        elif not column.startswith("doc2vec_"):
            parts.append(joined[[column]])
    parts.append(joined[[c.TARGET_COLUMN]])
    return (
        pd.concat(parts, axis=1)
        .sort_values(c.KEY_COLUMN, kind="stable")
        .reset_index(drop=True)
    )


def _input_hashes(inputs: InputTables, config: DatasetConfig) -> dict[str, Any]:
    """Registra caminhos e hashes das três entradas verificadas."""
    return {
        "features": {
            "path": config.features.as_posix(),
            "sha256": inputs.features_sha256,
        },
        "labels": {"path": config.labels.as_posix(), "sha256": inputs.labels_sha256},
        "labels_meta": {
            "path": inputs.labels_meta_path.as_posix(),
            "sha256": inputs.labels_meta_sha256,
        },
    }


def _counts(
    inputs: InputTables, table: pd.DataFrame, report: ExclusionReport
) -> dict[str, Any]:
    """Conta classes, exclusões e indeterminados na população de entrada."""
    classes = table[c.TARGET_COLUMN].value_counts()
    return {
        "input_rows": len(inputs.features),
        "input_firmware_ids": inputs.features[c.KEY_COLUMN].nunique(),
        "table_rows": len(table),
        "by_class": {name: int(classes.get(name, 0)) for name in c.TARGET_CLASSES},
        "excluded_firmware_ids": len(report.frame),
        "excluded_by_reason": report.by_reason,
        "excluded_by_vendor": report.by_vendor,
        "excluded_by_vendor_reason": report.by_vendor_reason,
        "multi_vendor_firmware_ids": report.multi_vendor_ids,
        "indeterminate_by_vendor": _indeterminate_by_vendor(
            inputs.features, inputs.labels
        ),
    }


def build_training_table(config: DatasetConfig) -> PreparedDataset:
    """Valida entradas e prepara todos os artefatos sem gravar nada."""
    inputs = load_inputs(config)
    _check_ids(inputs, config)
    check_transient_failures(inputs.features)
    reasons = apply_exclusions(inputs.features, inputs.labels)
    report = build_exclusions(inputs.features, reasons)
    columns = input_feature_columns(inputs.features)
    selected, changes = select_feature_columns(columns)
    keep_ids = set(inputs.features[c.KEY_COLUMN]) - set(reasons)
    sources = [column for column in columns if column in c.ONE_HOT_SOURCES]
    collapsed = collapse_aliases(inputs.features, keep_ids, selected + sources)
    joined = join_labels(collapsed, inputs.labels)
    table = _make_table(joined, columns, config)
    counts = _counts(inputs, table, report)
    if not len(table) or any(not count for count in counts["by_class"].values()):
        raise ValueError(f"Tabela vazia ou classe sem exemplo: {counts['by_class']}")
    vector = [col for col in table if col not in (c.KEY_COLUMN, c.TARGET_COLUMN)]
    non_numeric = [
        col for col in vector if not pd.api.types.is_numeric_dtype(table[col])
    ]
    if non_numeric:
        raise ValueError(f"{config.features}: coluna de texto no vetor: {non_numeric}")
    metadata = {
        "inputs": _input_hashes(inputs, config),
        "commit": code_commit(),
        "config": config.as_dict(),
        **column_report(columns, vector, changes),
        "constant_columns": constant_columns(table, vector),
        "counts": counts,
    }
    provenance = build_provenance(
        inputs.features, set(table[c.KEY_COLUMN]), set(reasons)
    )
    return PreparedDataset(table, report.frame, provenance, metadata)


def log_summary(prepared: PreparedDataset) -> None:
    """Informa dimensões, classes e exclusões por motivo e fabricante."""
    counts = prepared.metadata["counts"]
    LOGGER.info(
        "Entrada: %s linhas, %s firmware_id; tabela: %s linhas, %s colunas do vetor",
        counts["input_rows"],
        counts["input_firmware_ids"],
        counts["table_rows"],
        len(prepared.metadata["columns_vector"]),
    )
    LOGGER.info("Distribuição por classe: %s", counts["by_class"])
    LOGGER.info("Exclusões por motivo: %s", counts["excluded_by_reason"])
    LOGGER.info("Exclusões por fabricante: %s", counts["excluded_by_vendor"])
    LOGGER.info(
        "firmware_id com mais de um fabricante: %s",
        counts["multi_vendor_firmware_ids"],
    )
    LOGGER.info(
        "Proporção de indeterminado por fabricante: %s",
        counts["indeterminate_by_vendor"],
    )


def write_artifacts(prepared: PreparedDataset, output_dir: Path) -> dict[str, Path]:
    """Grava tabela, exclusões, proveniência e por último metadados com hashes."""
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "table": output_dir / c.TABLE_FILENAME,
        "exclusions": output_dir / c.EXCLUSIONS_FILENAME,
        "provenance": output_dir / c.PROVENANCE_FILENAME,
        "meta": output_dir / c.META_FILENAME,
    }
    prepared.table.to_parquet(paths["table"], index=False)
    prepared.exclusions.to_csv(paths["exclusions"], index=False)
    with paths["provenance"].open("w", encoding="utf-8") as destination:
        for entry in prepared.provenance:
            destination.write(json.dumps(entry, ensure_ascii=False) + "\n")
    outputs = {
        name: {"path": paths[name].as_posix(), "sha256": file_sha256(paths[name])}
        for name in ("table", "exclusions", "provenance")
    }
    metadata = {
        **prepared.metadata,
        "outputs": outputs,
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    paths["meta"].write_text(
        json.dumps(metadata, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return paths
