"""Fetch CVE data from NVD API v2.0 for firmware vendor/model pairs.

Reads a features parquet to extract unique (meta_brand, meta_model) pairs,
queries the NVD for known vulnerabilities, and saves aggregated CVE
statistics to a JSON cache file.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any
from urllib.parse import quote as url_quote

import pandas as pd

LOGGER = logging.getLogger(__name__)

NVD_API_URL = "https://services.nvd.nist.gov/rest/json/cves/2.0"
RESULTS_PER_PAGE = 2000
DEFAULT_DELAY_NO_KEY = 6
DEFAULT_DELAY_WITH_KEY = 1

# Maps internal brand names to the vendor name NVD uses in CVE descriptions.
VENDOR_ALIASES: dict[str, str] = {
    "dlink": "d-link",
    "tplink": "tp-link",
}

# Regex pattern for models that should have a hyphen before the numeric part.
# e.g. "dir300" -> "DIR-300", "dsr1000n" -> "DSR-1000N"

_MODEL_HYPHEN_RE = re.compile(
    r"^([a-z]{2,5})(\d.*)$",  # letters then digits (with optional suffix)
    re.IGNORECASE,
)

# Models with underscore-separated trailing number: "f5d7230_4" -> "F5D7230-4"
_MODEL_UNDERSCORE_RE = re.compile(
    r"^(.+)_(\d+)$",
)


# ---------------------------------------------------------------------------
# Name normalization
# ---------------------------------------------------------------------------


def normalize_vendor(vendor: str) -> str:
    """Map internal brand name to NVD-compatible vendor name."""
    return VENDOR_ALIASES.get(vendor, vendor)


def normalize_model(model: str) -> str:
    """Normalize model string for NVD keyword search.

    - Missing hyphen: ``dir300`` -> ``DIR-300``
    - Underscore suffix: ``f5d7230_4`` -> ``F5D7230-4``
    """
    # Already has a hyphen (e.g. "dir-300") — just uppercase
    if "-" in model:
        return model.upper()

    # Underscore suffix: "f5d7230_4" -> "F5D7230-4"
    m = _MODEL_UNDERSCORE_RE.match(model)
    if m:
        base = normalize_model(m.group(1))  # recurse on base part
        return f"{base}-{m.group(2)}"

    # Missing hyphen: "dir300" -> "DIR-300"
    m = _MODEL_HYPHEN_RE.match(model)
    if m:
        return f"{m.group(1).upper()}-{m.group(2).upper()}"

    return model.upper()


# ---------------------------------------------------------------------------
# CVSS extraction
# ---------------------------------------------------------------------------


def extract_cvss(cve: dict[str, Any]) -> tuple[float, str]:
    """Return (baseScore, severity) preferring v3.1 > v3.0 > v2."""
    metrics = cve.get("metrics", {})

    for key in ("cvssMetricV31", "cvssMetricV30"):
        entries = metrics.get(key, [])
        if entries:
            data = entries[0]["cvssData"]
            return data["baseScore"], data["baseSeverity"]

    v2 = metrics.get("cvssMetricV2", [])
    if v2:
        data = v2[0]["cvssData"]
        severity = v2[0].get("baseSeverity", "MEDIUM")
        return data["baseScore"], severity

    return 0.0, "NONE"


def severity_bucket(severity: str) -> str:
    """Normalize severity string to lowercase bucket name."""
    return severity.upper() if severity else "NONE"


# ---------------------------------------------------------------------------
# NVD API client
# ---------------------------------------------------------------------------


def _build_headers() -> dict[str, str]:
    """Build request headers, including API key if available."""
    headers = {"Accept": "application/json"}
    api_key = os.environ.get("NVD_API_KEY", "")
    if api_key:
        headers["apiKey"] = api_key
    return headers


def _fetch_page(
    keyword: str,
    start_index: int,
    headers: dict[str, str],
) -> dict[str, Any]:
    """Fetch a single page of CVE results from NVD."""
    params = (
        f"keywordSearch={url_quote(keyword)}"
        f"&resultsPerPage={RESULTS_PER_PAGE}"
        f"&startIndex={start_index}"
    )
    url = f"{NVD_API_URL}?{params}"
    req = urllib.request.Request(url, headers=headers)

    with urllib.request.urlopen(req, timeout=30) as resp:
        result: dict[str, Any] = json.loads(resp.read().decode())
        return result


def fetch_cves_for_pair(
    vendor: str,
    model: str,
    headers: dict[str, str],
    delay: float,
) -> dict[str, Any]:
    """Fetch all CVEs for a vendor/model pair and return aggregated stats.

    Applies vendor/model normalization before querying NVD.
    """
    nvd_vendor = normalize_vendor(vendor)
    nvd_model = normalize_model(model)
    keyword = f"{nvd_vendor} {nvd_model}"
    LOGGER.debug("  NVD query: %s", keyword)

    start_index = 0
    all_scores: list[tuple[float, str]] = []

    while True:
        data = _fetch_page(keyword, start_index, headers)
        total_results = data.get("totalResults", 0)
        vulnerabilities = data.get("vulnerabilities", [])

        for item in vulnerabilities:
            cve = item.get("cve", {})
            score, sev = extract_cvss(cve)
            all_scores.append((score, sev))

        start_index += len(vulnerabilities)
        if start_index >= total_results or not vulnerabilities:
            break

        time.sleep(delay)

    return _aggregate_scores(all_scores)


def _aggregate_scores(scores: list[tuple[float, str]]) -> dict[str, Any]:
    """Aggregate a list of (score, severity) tuples into summary stats."""
    if not scores:
        return {
            "cvss_max": 0.0,
            "cve_count_critical": 0,
            "cve_count_high": 0,
            "cve_count_medium": 0,
            "cve_count_low": 0,
            "cve_total": 0,
        }

    counts = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0}
    max_score = 0.0

    for score, sev in scores:
        max_score = max(max_score, score)
        bucket = severity_bucket(sev)
        if bucket in counts:
            counts[bucket] += 1

    return {
        "cvss_max": max_score,
        "cve_count_critical": counts["CRITICAL"],
        "cve_count_high": counts["HIGH"],
        "cve_count_medium": counts["MEDIUM"],
        "cve_count_low": counts["LOW"],
        "cve_total": len(scores),
    }


# ---------------------------------------------------------------------------
# Cache I/O
# ---------------------------------------------------------------------------


def load_cache(path: Path) -> dict[str, Any]:
    """Load existing cache from disk, or return empty dict."""
    if path.exists():
        data: dict[str, Any] = json.loads(path.read_text())
        return data
    return {}


def save_cache(cache: dict[str, Any], path: Path) -> None:
    """Persist cache to disk."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cache, indent=2) + "\n")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def extract_pairs(df: pd.DataFrame) -> list[tuple[str, str]]:
    """Extract unique (brand, model) pairs from features dataframe."""
    pairs: set[tuple[str, str]] = set()
    for _, row in df.iterrows():
        brand = str(row.get("meta_brand", "")).strip().lower()
        model = str(row.get("meta_model", "")).strip().lower()
        if brand and model and brand != "nan" and model != "nan":
            pairs.add((brand, model))
    return sorted(pairs)


def main() -> None:
    """CLI para buscar dados de CVE da NVD API v2.0."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--features",
        required=True,
        help="Path to features parquet with meta_brand/meta_model columns",
    )
    parser.add_argument(
        "--output",
        default="dataset/cve_cache.json",
        help="Path to CVE cache JSON (default: dataset/cve_cache.json)",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=None,
        help="Seconds between requests (default: 6 without key, 1 with key)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List vendor/model pairs without making requests",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-fetch even if pair is already cached",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    # Determine delay
    has_key = bool(os.environ.get("NVD_API_KEY", ""))
    delay = (
        args.delay
        if args.delay is not None
        else (DEFAULT_DELAY_WITH_KEY if has_key else DEFAULT_DELAY_NO_KEY)
    )

    # Read features
    features_path = Path(args.features)
    df = pd.read_parquet(features_path)
    LOGGER.info("Loaded %d records from %s", len(df), features_path)

    pairs = extract_pairs(df)
    LOGGER.info("Found %d unique vendor/model pairs", len(pairs))

    if args.dry_run:
        for vendor, model in pairs:
            nv = normalize_vendor(vendor)
            nm = normalize_model(model)
            suffix = f" -> {nv} {nm}" if (nv != vendor or nm != model) else ""
            print(f"  {vendor}/{model}{suffix}")
        LOGGER.info("Dry run — no requests made")
        return

    # Load existing cache
    output_path = Path(args.output)
    cache = load_cache(output_path)
    LOGGER.info("[CACHE] Loaded %d existing entries", len(cache))

    headers = _build_headers()
    stats = {"fetched": 0, "cached": 0, "failed": 0, "total_cves": 0}

    for i, (vendor, model) in enumerate(pairs, 1):
        key = f"{vendor}/{model}"

        if key in cache and not args.force:
            LOGGER.info("[SKIP] %d/%d %s (cached)", i, len(pairs), key)
            stats["cached"] += 1
            stats["total_cves"] += cache[key].get("cve_total", 0)
            continue

        try:
            LOGGER.info("[FETCH] %d/%d %s", i, len(pairs), key)
            result = fetch_cves_for_pair(vendor, model, headers, delay)
            cache[key] = result
            save_cache(cache, output_path)
            stats["fetched"] += 1
            stats["total_cves"] += result["cve_total"]
            LOGGER.info(
                "  -> %d CVEs (max CVSS: %.1f)",
                result["cve_total"],
                result["cvss_max"],
            )
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as exc:
            LOGGER.error("[FAIL] %s: %s", key, exc)
            stats["failed"] += 1

        if i < len(pairs):
            time.sleep(delay)

    LOGGER.info("--- Summary ---")
    LOGGER.info("  Fetched: %d", stats["fetched"])
    LOGGER.info("  Cached:  %d", stats["cached"])
    LOGGER.info("  Failed:  %d", stats["failed"])
    LOGGER.info("  Total CVEs: %d", stats["total_cves"])


if __name__ == "__main__":
    main()
