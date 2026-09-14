"""Gera rótulos de vulnerabilidade conhecida a partir do cache CVE."""

from __future__ import annotations

import argparse
import json
import logging
from collections import Counter
from pathlib import Path
from typing import Any

import pandas as pd

from src.labeling.cve_labels import (
    LABEL_CRITICAL_CVE,
    LABEL_KNOWN_CVE,
    LABEL_NO_KNOWN_CVE,
    CveLabelThresholds,
    label_from_cve_stats,
)

LOGGER = logging.getLogger(__name__)
ID_COLUMNS = ("firmware_id", "meta_path", "meta_brand", "meta_model")


def _lookup_cve_stats(row: dict[str, Any], cache: dict[str, Any]) -> dict[str, Any]:
    """Busca o resultado de uma consulta concluída por fabricante/modelo."""
    brand = row.get("meta_brand")
    model = row.get("meta_model")
    if not isinstance(brand, str) or not brand.strip():
        raise ValueError("meta_brand/meta_model ausentes na tabela de features")
    if not isinstance(model, str) or not model.strip():
        raise ValueError("meta_brand/meta_model ausentes na tabela de features")

    key = f"{brand.strip().lower()}/{model.strip().lower()}"
    if key not in cache:
        raise ValueError(f"Consulta CVE ausente no cache para {key}")
    stats = cache[key]
    if not isinstance(stats, dict) or "cve_total" not in stats:
        raise ValueError(f"Resultado CVE inválido no cache para {key}")
    return stats


def _result_to_record(
    row: dict[str, Any], cve_stats: dict[str, Any], label: str
) -> dict[str, Any]:
    """Monta registro de rótulo com dados CVE para auditoria."""
    return {
        "firmware_id": row["firmware_id"],
        "meta_path": row["meta_path"],
        "vendor": row["meta_brand"],
        "model": row["meta_model"],
        "security_level": label,
        "cve_total": cve_stats["cve_total"],
        "cvss_max": cve_stats.get("cvss_max", 0.0),
    }


def main() -> None:
    """Executa a rotulagem CVE sem usar features do firmware no rótulo."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--features", type=Path, required=True)
    parser.add_argument("--cves", type=Path, required=True)
    parser.add_argument("--critical-cvss", type=float, default=9.0)
    parser.add_argument("--output", type=Path, default=Path("dataset/labels.csv"))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    thresholds = CveLabelThresholds(args.critical_cvss)

    if args.features.suffix.lower() == ".parquet":
        frame = pd.read_parquet(args.features, columns=list(ID_COLUMNS))
    else:
        frame = pd.read_csv(args.features, usecols=list(ID_COLUMNS))
    if frame.empty:
        raise ValueError(f"Tabela de features vazia: {args.features}")
    if frame["firmware_id"].isna().any() or frame["firmware_id"].duplicated().any():
        raise ValueError(f"firmware_id ausente ou duplicado: {args.features}")

    with args.cves.open(encoding="utf-8") as source:
        cache = json.load(source)
    if not isinstance(cache, dict):
        raise ValueError(f"Cache CVE deve ser um objeto JSON: {args.cves}")
    LOGGER.info("Firmwares: %d; entradas CVE: %d", len(frame), len(cache))

    records = []
    for row in frame.to_dict(orient="records"):
        try:
            stats = _lookup_cve_stats(row, cache)
            label = label_from_cve_stats(stats, thresholds)
        except ValueError as exc:
            raise ValueError(f"firmware_id={row['firmware_id']}: {exc}") from exc
        records.append(_result_to_record(row, stats, label))

    output = pd.DataFrame.from_records(records)
    distribution = Counter(output["security_level"])
    LOGGER.info(
        "Distribuição: %s",
        {
            label: distribution[label]
            for label in (LABEL_NO_KNOWN_CVE, LABEL_KNOWN_CVE, LABEL_CRITICAL_CVE)
        },
    )
    if args.dry_run:
        return
    args.output.parent.mkdir(parents=True, exist_ok=True)
    output.to_csv(args.output, index=False)
    LOGGER.info("Rótulos salvos em %s", args.output)


if __name__ == "__main__":
    main()
