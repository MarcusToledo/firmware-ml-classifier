"""Gera rótulos de vulnerabilidade conhecida a partir do cache CVE."""

from __future__ import annotations

import argparse
import json
import logging
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timezone
from itertools import chain
from pathlib import Path
from typing import Any

import pandas as pd
import pyarrow.parquet as pq

from pipeline.feature_extraction import (
    VERSION_SOURCE_DIRECTORY,
    VERSION_SOURCE_FILENAME,
    infer_brand_model_label_from_path,
)
from src.labeling.cve_labels import (
    LABEL_CRITICAL_CVE,
    LABEL_INDETERMINATE,
    LABEL_KNOWN_CVE,
    LABEL_NO_KNOWN_CVE,
    CveLabelThresholds,
    aggregate_cve_scores,
    applicable_cves_for_version,
    label_from_cve_stats,
)
from src.run_metadata import code_commit, file_sha256

LOGGER = logging.getLogger(__name__)
ID_COLUMNS = (
    "firmware_id",
    "meta_path",
    "meta_brand",
    "meta_model",
    "meta_version",
    "meta_version_source",
)
STRATEGY_SINGLE_ALIAS = "alias_unico"
STRATEGY_CONSERVATIVE = "agregacao_conservadora"

AliasEvidence = tuple[list[dict[str, Any]], list[dict[str, Any]]]


@dataclass(frozen=True)
class AliasEvaluation:
    """Resultado da rotulagem de uma linha (alias) da tabela de features."""

    row: dict[str, Any]
    applicable: list[dict[str, Any]]
    indeterminate: list[dict[str, Any]]
    version_source: str | None


def _cache_key(row: dict[str, Any]) -> str:
    """Monta a chave vendor/model do cache a partir de meta_brand e meta_model.

    Levanta ValueError se algum dos dois faltar.
    """
    brand = row.get("meta_brand")
    model = row.get("meta_model")
    if not isinstance(brand, str) or not brand.strip():
        raise ValueError("meta_brand/meta_model ausentes na tabela de features")
    if not isinstance(model, str) or not model.strip():
        raise ValueError("meta_brand/meta_model ausentes na tabela de features")
    return f"{brand.strip().lower()}/{model.strip().lower()}"


def _validate_cache_entry(key: str, entry: object) -> dict[str, Any]:
    """Exige lista de CVEs, schema_version 3 e fetched_at na entrada do cache."""
    if not isinstance(entry, dict) or not isinstance(entry.get("cves"), list):
        raise ValueError(f"Resultado CVE inválido no cache para {key}")
    if entry.get("schema_version") != 3:
        raise ValueError(f"Versão de schema inválida no cache para {key}")
    fetched_at = entry.get("fetched_at")
    if not isinstance(fetched_at, str) or not fetched_at.strip():
        raise ValueError(f"fetched_at ausente no cache para {key}")
    return entry


def _lookup_cve_entry(row: dict[str, Any], cache: dict[str, Any]) -> dict[str, Any]:
    """Busca consulta CVE válida para o fabricante e modelo da imagem."""
    key = _cache_key(row)
    if key not in cache:
        raise ValueError(f"Consulta CVE ausente no cache para {key}")
    return _validate_cache_entry(key, cache[key])


def _cve_id(cve: dict[str, Any]) -> str:
    """Retorna o identificador da CVE; ValueError se ausente."""
    cve_id = cve.get("id")
    if not isinstance(cve_id, str) or not cve_id:
        raise ValueError("CVE sem identificador válido no cache")
    return cve_id


def _merge_alias_evidence(
    alias_results: list[AliasEvidence],
) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    """Une CVEs de todos os aliases por id; CVE aplicável sai das indeterminadas."""
    applicable_by_id: dict[str, dict[str, Any]] = {}
    indeterminate_by_id: dict[str, dict[str, Any]] = {}
    for applicable, indeterminate in alias_results:
        for cve in applicable:
            applicable_by_id[_cve_id(cve)] = cve
        for cve in indeterminate:
            indeterminate_by_id[_cve_id(cve)] = cve
    for cve_id in applicable_by_id:
        indeterminate_by_id.pop(cve_id, None)
    return applicable_by_id, indeterminate_by_id


def _score_stats(cves: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """Agrega cvss_max e severidade de um conjunto de CVEs."""
    return aggregate_cve_scores([(c["cvss_max"], c["severity"]) for c in cves])


def _aggregate_firmware_label(
    alias_results: list[AliasEvidence],
    thresholds: CveLabelThresholds,
) -> tuple[str, dict[str, Any]]:
    """Une as evidencias de todos os aliases e decide o rotulo por limites.

    O rotulo so e atribuido quando toda resolucao possivel das CVEs
    indeterminadas leva a mesma classe. ``cve_total`` e ``cvss_max`` refletem
    apenas as CVEs aplicaveis e, portanto, formam um limite inferior.
    """
    applicable_by_id, indeterminate_by_id = _merge_alias_evidence(alias_results)
    stats = _score_stats(applicable_by_id.values())
    upper_bound_stats = _score_stats(
        chain(applicable_by_id.values(), indeterminate_by_id.values())
    )
    lower_bound_label = label_from_cve_stats(stats, thresholds)
    upper_bound_label = label_from_cve_stats(upper_bound_stats, thresholds)
    if lower_bound_label == upper_bound_label:
        return lower_bound_label, stats
    return LABEL_INDETERMINATE, stats


def _build_label_record(
    row: dict[str, Any],
    cve_stats: dict[str, Any],
    label: str,
    version_source: str | None,
    label_strategy: str,
    alias_count: int,
) -> dict[str, Any]:
    """Monta registro auditável sem features estatísticas ou semânticas."""
    return {
        "firmware_id": row["firmware_id"],
        "meta_path": row["meta_path"],
        "vendor": row["meta_brand"],
        "model": row["meta_model"],
        "version": row["meta_version"],
        "version_source": version_source,
        "security_level": label,
        "cve_total": cve_stats["cve_total"],
        "cvss_max": cve_stats.get("cvss_max", 0.0),
        "label_strategy": label_strategy,
        "alias_count": alias_count,
    }


def _require_id_columns(path: Path) -> None:
    """Exige as colunas de identificação.

    Levanta ValueError com instrução de reextração via --label-from-path.
    """
    if path.suffix.lower() == ".parquet":
        available = pq.read_schema(path).names
    else:
        available = pd.read_csv(path, nrows=0).columns
    missing = [column for column in ID_COLUMNS if column not in available]
    if missing:
        raise ValueError(
            f"Colunas ausentes na tabela de features {path}: "
            f"{', '.join(missing)}; reextraia as features com --label-from-path"
        )


def _read_id_columns(path: Path) -> pd.DataFrame:
    """Lê só as colunas de identificação, em Parquet ou CSV."""
    if path.suffix.lower() == ".parquet":
        return pd.read_parquet(path, columns=list(ID_COLUMNS))
    return pd.read_csv(
        path,
        usecols=list(ID_COLUMNS),
        dtype={"meta_version": "string", "meta_version_source": "string"},
    )


def _validate_feature_rows(frame: pd.DataFrame, path: Path) -> None:
    """Rejeita tabela vazia, firmware_id ou meta_path ausentes e linhas duplicadas."""
    if frame.empty:
        raise ValueError(f"Tabela de features vazia: {path}")
    if frame["firmware_id"].isna().any():
        raise ValueError(f"firmware_id ausente: {path}")
    if frame["meta_path"].isna().any():
        raise ValueError(f"meta_path ausente: {path}")
    if frame.duplicated(subset=["firmware_id", "meta_path"]).any():
        raise ValueError(f"linha duplicada (firmware_id + meta_path): {path}")


def _load_features(path: Path) -> pd.DataFrame:
    """Lê as colunas de identificação da tabela de features e valida as linhas."""
    _require_id_columns(path)
    frame = _read_id_columns(path)
    _validate_feature_rows(frame, path)
    return frame


def _none_if_missing(value: Any) -> str | None:
    """Normaliza valores ausentes vindos de CSV ou Parquet."""
    return None if pd.isna(value) else value


def _path_mismatch_error(
    row: dict[str, Any],
    kind: str,
    inferred: str | None,
    column: str,
    recorded: str | None,
) -> ValueError:
    """Monta o erro de divergência entre valor inferido do caminho e coluna."""
    return ValueError(
        f"firmware_id={row['firmware_id']}; meta_path={row['meta_path']!r}: "
        f"{kind} inferida={inferred!r} difere de {column}={recorded!r}; "
        "reextraia as features com --label-from-path"
    )


def _verify_path_version(row: dict[str, Any]) -> str | None:
    """Confere versão e origem inferidas de meta_path contra as colunas da tabela.

    Retorna a origem da versão; levanta ValueError pedindo reextração quando divergem.
    """
    meta = infer_brand_model_label_from_path(Path(row["meta_path"]))
    feature_version = _none_if_missing(row.get("meta_version"))
    if meta.version != feature_version:
        raise _path_mismatch_error(
            row, "versao", meta.version, "meta_version", feature_version
        )
    feature_source = _none_if_missing(row.get("meta_version_source"))
    if meta.version_source != feature_source:
        raise _path_mismatch_error(
            row, "origem", meta.version_source, "meta_version_source", feature_source
        )
    return meta.version_source


def _evaluate_alias(row: dict[str, Any], cache: dict[str, Any]) -> AliasEvaluation:
    """Avalia as CVEs de um alias após conferir o cache e a versão do caminho."""
    try:
        entry = _lookup_cve_entry(row, cache)
    except ValueError as exc:
        raise ValueError(f"firmware_id={row['firmware_id']}: {exc}") from exc
    version_source = _verify_path_version(row)
    applicable, indeterminate = applicable_cves_for_version(
        _none_if_missing(row.get("meta_version")), entry
    )
    return AliasEvaluation(row, applicable, indeterminate, version_source)


def _group_indexes_by_firmware(
    rows: list[dict[str, Any]],
) -> dict[str, list[int]]:
    """Agrupa os índices das linhas por firmware_id, na ordem de primeira aparição."""
    by_firmware: dict[str, list[int]] = {}
    for index, row in enumerate(rows):
        by_firmware.setdefault(row["firmware_id"], []).append(index)
    return by_firmware


def _alias_summary(alias: AliasEvaluation) -> dict[str, Any]:
    """Resume um alias para o JSONL: caminho, vendor, modelo, versão e CVEs por id."""
    return {
        "meta_path": alias.row["meta_path"],
        "vendor": alias.row["meta_brand"],
        "model": alias.row["meta_model"],
        "version": _none_if_missing(alias.row["meta_version"]),
        "applicable_cves": sorted({_cve_id(c) for c in alias.applicable}),
        "indeterminate_cves": sorted({_cve_id(c) for c in alias.indeterminate}),
    }


def _label_firmware(
    firmware_id: str,
    aliases: list[AliasEvaluation],
    thresholds: CveLabelThresholds,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Aplica o rótulo agregado a todos os aliases de um firmware_id.

    Retorna (registros do CSV, um por alias, registro do JSONL de aliases).
    """
    label, stats = _aggregate_firmware_label(
        [(alias.applicable, alias.indeterminate) for alias in aliases], thresholds
    )
    strategy = STRATEGY_SINGLE_ALIAS if len(aliases) == 1 else STRATEGY_CONSERVATIVE
    alias_summaries = [_alias_summary(alias) for alias in aliases]
    records = [
        _build_label_record(
            alias.row, stats, label, alias.version_source, strategy, len(aliases)
        )
        for alias in aliases
    ]
    alias_record = {
        "firmware_id": firmware_id,
        "label_strategy": strategy,
        "versions_differ": len({alias["version"] for alias in alias_summaries}) > 1,
        "aliases": alias_summaries,
    }
    return records, alias_record


def _label_rows(
    rows: list[dict[str, Any]],
    cache: dict[str, Any],
    thresholds: CveLabelThresholds,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Rotula cada linha e agrega aliases do mesmo firmware_id.

    Retorna (registros do CSV na ordem de entrada, registros do JSONL de aliases
    na ordem de primeira aparição do firmware_id).
    """
    evaluations = [_evaluate_alias(row, cache) for row in rows]
    records_by_index: dict[int, dict[str, Any]] = {}
    alias_records: list[dict[str, Any]] = []
    for firmware_id, indexes in _group_indexes_by_firmware(rows).items():
        records, alias_record = _label_firmware(
            firmware_id, [evaluations[i] for i in indexes], thresholds
        )
        records_by_index.update(zip(indexes, records))
        alias_records.append(alias_record)
    return [records_by_index[i] for i in range(len(rows))], alias_records


def _parse_args() -> argparse.Namespace:
    """Lê os argumentos da linha de comando."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--features", type=Path, required=True)
    parser.add_argument("--cves", type=Path, required=True)
    parser.add_argument("--critical-cvss", type=float, default=9.0)
    parser.add_argument(
        "--output", type=Path, default=Path("dataset/processed/labels_v2.csv")
    )
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def _load_cve_cache(path: Path) -> dict[str, Any]:
    """Carrega o cache CVE em JSON e exige um objeto no topo."""
    with path.open(encoding="utf-8") as source:
        cache = json.load(source)
    if not isinstance(cache, dict):
        raise ValueError(f"Cache CVE deve ser um objeto JSON: {path}")
    return cache


def _log_label_distribution(records: list[dict[str, Any]]) -> None:
    """Registra a contagem de cada classe de rótulo."""
    distribution = Counter(record["security_level"] for record in records)
    LOGGER.info(
        "Distribuição: %s",
        {
            label: distribution[label]
            for label in (
                LABEL_NO_KNOWN_CVE,
                LABEL_KNOWN_CVE,
                LABEL_CRITICAL_CVE,
                LABEL_INDETERMINATE,
            )
        },
    )


def _log_version_sources(records: list[dict[str, Any]]) -> None:
    """Registra a contagem por origem da versão, incluindo a origem ausente."""
    version_source_distribution = Counter(
        record["version_source"] for record in records
    )
    LOGGER.info(
        "Origem da versão: %s",
        {
            source: version_source_distribution[source]
            for source in (
                VERSION_SOURCE_DIRECTORY,
                VERSION_SOURCE_FILENAME,
                None,
            )
        },
    )


def _log_alias_counts(alias_records: list[dict[str, Any]]) -> None:
    """Registra as contagens de aliases, modelos e versões diferentes."""
    multi_alias = sum(len(record["aliases"]) > 1 for record in alias_records)
    multi_model = sum(
        len({alias["model"].strip().lower() for alias in record["aliases"]}) > 1
        for record in alias_records
    )
    versions_differ = sum(record["versions_differ"] for record in alias_records)
    LOGGER.info(
        "Aliases: %d firmware_id com mais de um alias; %d com aliases de "
        "mais de um modelo; %d com aliases de versões diferentes",
        multi_alias,
        multi_model,
        versions_differ,
    )


def _build_run_metadata(
    features: Path, cves: Path, critical_cvss: float
) -> dict[str, Any]:
    """Monta os metadados de proveniência antes de qualquer escrita (005/FR-018)."""
    return {
        "critical_cvss": float(critical_cvss),
        "features_path": features.as_posix(),
        "features_sha256": file_sha256(features),
        "cves_path": cves.as_posix(),
        "cves_sha256": file_sha256(cves),
        "code_commit": code_commit(),
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


def _write_label_artifacts(
    output: Path,
    records: list[dict[str, Any]],
    alias_records: list[dict[str, Any]],
    run_metadata: dict[str, Any],
) -> None:
    """Grava o CSV de rótulos, o JSONL de aliases e o .meta.json ao lado do CSV."""
    frame = pd.DataFrame.from_records(records)
    aliases_path = output.with_name(f"{output.stem}_aliases.jsonl")
    meta_path = output.with_name(f"{output.stem}.meta.json")
    output.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(output, index=False)
    LOGGER.info("Rótulos salvos em %s", output)
    with aliases_path.open("w", encoding="utf-8") as destination:
        for record in alias_records:
            destination.write(json.dumps(record, ensure_ascii=False) + "\n")
    LOGGER.info("Aliases salvos em %s", aliases_path)
    meta_path.write_text(
        json.dumps(run_metadata, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    LOGGER.info("Metadados salvos em %s", meta_path)


def main() -> None:
    """Executa a rotulagem CVE com filtragem de versão por alias."""
    args = _parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    frame = _load_features(args.features)
    cache = _load_cve_cache(args.cves)
    LOGGER.info("Firmwares: %d; entradas CVE: %d", len(frame), len(cache))
    records, alias_records = _label_rows(
        frame.to_dict(orient="records"), cache, CveLabelThresholds(args.critical_cvss)
    )
    _log_label_distribution(records)
    _log_version_sources(records)
    _log_alias_counts(alias_records)
    if args.dry_run:
        return
    run_metadata = _build_run_metadata(args.features, args.cves, args.critical_cvss)
    _write_label_artifacts(args.output, records, alias_records, run_metadata)


if __name__ == "__main__":
    main()
