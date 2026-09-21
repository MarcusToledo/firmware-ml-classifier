"""Gera rótulos de vulnerabilidade conhecida a partir do cache CVE."""

from __future__ import annotations

import argparse
import json
import logging
from collections import Counter
from pathlib import Path
from typing import Any

import pandas as pd

from scripts.fetch_cves import _aggregate_scores
from src.labeling.cve_labels import (
    LABEL_CRITICAL_CVE,
    LABEL_INDETERMINATE,
    LABEL_KNOWN_CVE,
    LABEL_NO_KNOWN_CVE,
    CveLabelThresholds,
    applicable_cves_for_version,
    label_from_cve_stats,
)

LOGGER = logging.getLogger(__name__)
ID_COLUMNS = ("firmware_id", "meta_path", "meta_brand", "meta_model", "meta_version")


def _lookup_cve_entry(row: dict[str, Any], cache: dict[str, Any]) -> dict[str, Any]:
    """Busca consulta CVE válida para o fabricante e modelo da imagem."""
    brand = row.get("meta_brand")
    model = row.get("meta_model")
    if not isinstance(brand, str) or not brand.strip():
        raise ValueError("meta_brand/meta_model ausentes na tabela de features")
    if not isinstance(model, str) or not model.strip():
        raise ValueError("meta_brand/meta_model ausentes na tabela de features")

    key = f"{brand.strip().lower()}/{model.strip().lower()}"
    if key not in cache:
        raise ValueError(f"Consulta CVE ausente no cache para {key}")
    entry = cache[key]
    if not isinstance(entry, dict) or not isinstance(entry.get("cves"), list):
        raise ValueError(f"Resultado CVE inválido no cache para {key}")
    if entry.get("schema_version") != 2:
        raise ValueError(f"Versão de schema inválida no cache para {key}")
    return entry


def _aggregate_firmware_label(
    alias_results: list[tuple[list[dict[str, Any]], bool]],
    thresholds: CveLabelThresholds,
) -> tuple[str, dict[str, Any]]:
    """Une CVEs aplicáveis por ID antes de decidir o rótulo uma única vez."""
    merged: dict[str, dict[str, Any]] = {}
    any_determinate = False
    for applicable, determinate in alias_results:
        if not determinate:
            continue
        any_determinate = True
        for cve in applicable:
            cve_id = cve.get("id")
            if not isinstance(cve_id, str) or not cve_id:
                raise ValueError("CVE sem identificador válido no cache")
            merged[cve_id] = cve

    if not any_determinate:
        return LABEL_INDETERMINATE, {"cve_total": 0, "cvss_max": 0.0}

    stats = _aggregate_scores(
        [(cve["cvss_max"], cve["severity"]) for cve in merged.values()]
    )
    return label_from_cve_stats(stats, thresholds), stats


def _result_to_record(
    row: dict[str, Any], cve_stats: dict[str, Any], label: str
) -> dict[str, Any]:
    """Monta registro auditável sem features estatísticas ou semânticas."""
    return {
        "firmware_id": row["firmware_id"],
        "meta_path": row["meta_path"],
        "vendor": row["meta_brand"],
        "model": row["meta_model"],
        "version": row["meta_version"],
        "security_level": label,
        "cve_total": cve_stats["cve_total"],
        "cvss_max": cve_stats.get("cvss_max", 0.0),
    }


def _load_features(path: Path) -> pd.DataFrame:
    if path.suffix.lower() == ".parquet":
        frame = pd.read_parquet(path, columns=list(ID_COLUMNS))
    else:
        frame = pd.read_csv(
            path, usecols=list(ID_COLUMNS), dtype={"meta_version": "string"}
        )
    if frame.empty:
        raise ValueError(f"Tabela de features vazia: {path}")
    if frame["firmware_id"].isna().any():
        raise ValueError(f"firmware_id ausente: {path}")
    if frame.duplicated(subset=["firmware_id", "meta_path"]).any():
        raise ValueError(f"linha duplicada (firmware_id + meta_path): {path}")
    return frame


def _label_rows(
    rows: list[dict[str, Any]],
    cache: dict[str, Any],
    thresholds: CveLabelThresholds,
) -> list[dict[str, Any]]:
    by_firmware: dict[str, list[tuple[list[dict[str, Any]], bool]]] = {}
    for row in rows:
        try:
            entry = _lookup_cve_entry(row, cache)
        except ValueError as exc:
            raise ValueError(f"firmware_id={row['firmware_id']}: {exc}") from exc
        result = applicable_cves_for_version(row.get("meta_version"), entry)
        by_firmware.setdefault(row["firmware_id"], []).append(result)

    aggregated = {
        firmware_id: _aggregate_firmware_label(results, thresholds)
        for firmware_id, results in by_firmware.items()
    }
    records = []
    for row in rows:
        label, stats = aggregated[row["firmware_id"]]
        records.append(_result_to_record(row, stats, label))
    return records


def main() -> None:
    """Executa a rotulagem CVE com filtragem de versão por alias."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--features", type=Path, required=True)
    parser.add_argument("--cves", type=Path, required=True)
    parser.add_argument("--critical-cvss", type=float, default=9.0)
    parser.add_argument("--output", type=Path, default=Path("dataset/labels.csv"))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    frame = _load_features(args.features)
    with args.cves.open(encoding="utf-8") as source:
        cache = json.load(source)
    if not isinstance(cache, dict):
        raise ValueError(f"Cache CVE deve ser um objeto JSON: {args.cves}")
    LOGGER.info("Firmwares: %d; entradas CVE: %d", len(frame), len(cache))

    records = _label_rows(
        frame.to_dict(orient="records"), cache, CveLabelThresholds(args.critical_cvss)
    )
    output = pd.DataFrame.from_records(records)
    distribution = Counter(output["security_level"])
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
    if args.dry_run:
        return
    args.output.parent.mkdir(parents=True, exist_ok=True)
    output.to_csv(args.output, index=False)
    LOGGER.info("Rótulos salvos em %s", args.output)


if __name__ == "__main__":
    main()
