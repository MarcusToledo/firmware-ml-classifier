from __future__ import annotations

import argparse
import json
import logging
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from src.scoring import ScoringResult, load_scoring_config, score_firmware  # noqa: E402

LOGGER = logging.getLogger(__name__)


def _merge_cve_features(
    row: dict[str, Any],
    cve_cache: dict[str, Any],
) -> dict[str, Any]:
    """Merge CVE features from cache into a feature row.

    Looks up by ``{meta_brand}/{meta_model}`` (lowercase) to match
    the keys produced by ``fetch_cves.py``.
    """
    brand = str(row.get("meta_brand", "")).strip().lower()
    model = str(row.get("meta_model", "")).strip().lower()
    if not brand or not model or brand == "nan" or model == "nan":
        return row

    key = f"{brand}/{model}"
    cve_entry = cve_cache.get(key, {})
    if not cve_entry:
        return row

    merged = dict(row)
    for field in (
        "cvss_max",
        "cve_count_critical",
        "cve_count_high",
        "cve_count_medium",
        "cve_count_low",
    ):
        if field in cve_entry:
            merged[field] = cve_entry[field]
    return merged


def _result_to_record(
    row: dict[str, Any],
    result: ScoringResult,
) -> dict[str, Any]:
    """Build an output record from a scoring result."""
    signal_scores = {s.name: s.score for s in result.signals}
    return {
        "firmware_id": row.get("firmware_id", ""),
        "meta_path": row.get("meta_path", ""),
        "vendor": row.get("meta_brand", ""),
        "model": row.get("meta_model", ""),
        "security_level": result.level,
        "numeric_score": round(result.numeric_score, 4),
        "signal_stats": round(signal_scores.get("stats", 0.0), 4),
        "signal_cve": round(signal_scores.get("cve", 0.0), 4),
        "signal_strings": round(signal_scores.get("strings", 0.0), 4),
        "signal_binwalk": round(signal_scores.get("binwalk", 0.0), 4),
        "hard_rule_applied": result.hard_rule_applied or "",
    }


def main() -> None:
    """CLI para geração de labels de segurança a partir de features extraídas."""
    parser = argparse.ArgumentParser(
        description="Generate security labels from firmware features",
    )
    parser.add_argument(
        "--features",
        required=True,
        help="Path to features parquet file",
    )
    parser.add_argument(
        "--cves",
        default=None,
        help="Path to CVE cache JSON (optional)",
    )
    parser.add_argument(
        "--config",
        default="configs/scoring.yaml",
        help="Path to scoring config YAML",
    )
    parser.add_argument(
        "--output",
        default="dataset/labels.csv",
        help="Output path for labels CSV",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show class distribution without saving",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    config = load_scoring_config(Path(args.config))
    LOGGER.info("Loaded scoring config from %s", args.config)

    features_path = Path(args.features)
    if features_path.suffix == ".parquet":
        df = pd.read_parquet(features_path)
    else:
        df = pd.read_csv(features_path)
    LOGGER.info("Loaded %d firmware records from %s", len(df), args.features)

    cve_cache: dict[str, Any] = {}
    if args.cves:
        cve_path = Path(args.cves)
        if cve_path.exists():
            cve_cache = json.loads(cve_path.read_text())
            LOGGER.info("Loaded CVE cache with %d entries", len(cve_cache))
        else:
            LOGGER.warning("CVE cache not found: %s", args.cves)

    records: list[dict[str, Any]] = []
    for _, row in df.iterrows():
        row_dict = row.to_dict()
        merged = _merge_cve_features(row_dict, cve_cache)
        result = score_firmware(merged, config)
        records.append(_result_to_record(row_dict, result))

    output_df = pd.DataFrame.from_records(records)

    # Show distribution
    distribution = Counter(output_df["security_level"])
    LOGGER.info("Label distribution:")
    for level in ("seguro", "vulneravel", "critico"):
        count = distribution.get(level, 0)
        pct = count / len(output_df) * 100 if len(output_df) else 0
        LOGGER.info("  %s: %d (%.1f%%)", level, count, pct)

    if args.dry_run:
        LOGGER.info("Dry run — not saving output")
        return

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_df.to_csv(output_path, index=False)
    LOGGER.info("Saved labels to %s", output_path)


if __name__ == "__main__":
    main()
