"""Fetch CVE data from NVD API v2.0 for firmware vendor/model pairs.

Reads a features parquet to extract unique (meta_brand, meta_model) pairs,
queries the NVD for known vulnerabilities, and saves CVE and CPE evidence
to a JSON cache file.
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
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote as url_quote

import pandas as pd

from src.labeling.cve_labels import severity_bucket
from src.run_metadata import code_commit, file_sha256

LOGGER = logging.getLogger(__name__)

NVD_API_URL = "https://services.nvd.nist.gov/rest/json/cves/2.0"
NVD_CPE_API_URL = "https://services.nvd.nist.gov/rest/json/cpes/2.0"
RESULTS_PER_PAGE = 2000
DEFAULT_DELAY_NO_KEY = 6
DEFAULT_DELAY_WITH_KEY = 1
# Persist the cache to disk every N successful fetches instead of after
# every single one, since a full JSON rewrite grows with the cache size.
SAVE_INTERVAL = 10

CACHE_SCHEMA_VERSION = 3
_CACHE_SCHEMA_FIELD = "schema_version"
_FETCHED_AT_FIELD = "fetched_at"
_DEFAULT_CACHE_PATH = "dataset/processed/cve_cache_v2.json"
_EXIT_MISSING_PAIRS = 2
_EXIT_FETCH_FAILURE = 1
_CPE_FIELD_COUNT = 13
_CPE_WILDCARD_FIELD_COUNT = 8
_CPE_PART_INDEX = 2
_CPE_VENDOR_INDEX = 3
_CPE_MODEL_INDEX = 4
_CPE_WILDCARD_START = 5
_CPE_FORMAT_VERSION = "2.3"
_CPE_HARDWARE_PART = "h"
_CPE_SOFTWARE_PART = "o"
_NVD_REQUEST_TIMEOUT_SECONDS = 30
_BRAND_COLUMN = "meta_brand"
_MODEL_COLUMN = "meta_model"
_NVD_API_KEY_ENV = "NVD_API_KEY"
_NVD_TOTAL_RESULTS_FIELD = "totalResults"
_CVSS_V2_METRIC = "cvssMetricV2"
_CVSS_DATA_FIELD = "cvssData"
_CVSS_SCORE_FIELD = "baseScore"
_KEYWORD_SEARCH_PARAM = "keywordSearch"
_CVSS_SEVERITY_FIELD = "baseSeverity"
_NO_CVSS_SCORE = 0.0
_CVE_ITEMS_FIELD = "cves"
_CVE_MAX_SCORE_FIELD = "cvss_max"
_STATS_FETCHED = "fetched"
_STATS_CACHED = "cached"
_STATS_FAILED = "failed"
_STATS_TOTAL_CVES = "total_cves"
_TIMESTAMP_PRECISION = "seconds"


# Maps internal brand names to the vendor name NVD uses in CVE descriptions.
VENDOR_ALIASES: dict[str, str] = {
    "dlink": "d-link",
    "tplink": "tp-link",
    "tp_link": "tp-link",
}

# Regex pattern for models that should have a hyphen before the numeric part.
# e.g. "dir300" -> "DIR-300", "dsr1000n" -> "DSR-1000N"

_MODEL_HYPHEN_RE = re.compile(
    r"^([a-z]{2,5})(\d.*)$",  # letters then digits (with optional suffix)
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# Name normalization
# ---------------------------------------------------------------------------
# TODO: mover as regras de normalização (VENDOR_ALIASES, normalize_vendor e
# normalize_model) para um módulo/script separado, para centralizá-las e não
# poluir este módulo.


def normalize_vendor(vendor: str) -> str:
    """Map internal brand name to NVD-compatible vendor name."""
    return VENDOR_ALIASES.get(vendor, vendor)


def normalize_model(model: str) -> str:
    """Normalize model string for NVD keyword search.

    - Missing hyphen: ``dir300`` -> ``DIR-300``
    - Underscores: ``f5d7230_4`` -> ``F5D7230-4``, ``td_w8950n`` ->
      ``TD-W8950N`` (a NVD escreve com hifen, nunca com underscore)
    """
    model = model.replace("_", "-")

    # Already has a hyphen (e.g. "dir-300") — just uppercase
    if "-" in model:
        return model.upper()

    # Missing hyphen: "dir300" -> "DIR-300"
    m = _MODEL_HYPHEN_RE.match(model)
    if m:
        return f"{m.group(1).upper()}-{m.group(2).upper()}"

    return model.upper()


# ---------------------------------------------------------------------------
# CVSS extraction
# ---------------------------------------------------------------------------


def extract_cvss(cve: dict[str, Any]) -> tuple[float, str]:
    """Seleciona o maior score da primeira versão CVSS disponível."""
    metrics = cve.get("metrics", {})
    for key in ("cvssMetricV31", "cvssMetricV30", _CVSS_V2_METRIC):
        entries = metrics.get(key, [])
        if entries:
            entry = max(
                entries, key=lambda item: item[_CVSS_DATA_FIELD][_CVSS_SCORE_FIELD]
            )
            severity = (
                entry.get(_CVSS_SEVERITY_FIELD, "MEDIUM")
                if key == _CVSS_V2_METRIC
                else entry[_CVSS_DATA_FIELD][_CVSS_SEVERITY_FIELD]
            )
            return entry[_CVSS_DATA_FIELD][_CVSS_SCORE_FIELD], severity
    return _NO_CVSS_SCORE, "NONE"


# ---------------------------------------------------------------------------
# NVD API client
# ---------------------------------------------------------------------------


def _build_headers() -> dict[str, str]:
    """Build request headers, including API key if available."""
    headers = {"Accept": "application/json"}
    api_key = os.environ.get(_NVD_API_KEY_ENV, "")
    if api_key:
        headers["apiKey"] = api_key
    return headers


def _fetch_page(
    query_params: str,
    start_index: int,
    headers: dict[str, str],
) -> dict[str, Any]:
    """Fetch a single page of CVE results from NVD."""
    params = (
        f"{query_params}&resultsPerPage={RESULTS_PER_PAGE}&startIndex={start_index}"
    )
    url = f"{NVD_API_URL}?{params}"
    req = urllib.request.Request(url, headers=headers)

    with urllib.request.urlopen(req, timeout=_NVD_REQUEST_TIMEOUT_SECONDS) as resp:
        result: dict[str, Any] = json.loads(resp.read().decode())
        return result


def _fetch_cpe_page(
    keyword: str, start_index: int, headers: dict[str, str]
) -> dict[str, Any]:
    """Consulta uma página do dicionário oficial de nomes CPE da NVD."""
    params = (
        f"{_KEYWORD_SEARCH_PARAM}={url_quote(keyword)}"
        f"&resultsPerPage={RESULTS_PER_PAGE}"
        f"&startIndex={start_index}"
    )
    request = urllib.request.Request(f"{NVD_CPE_API_URL}?{params}", headers=headers)
    with urllib.request.urlopen(
        request, timeout=_NVD_REQUEST_TIMEOUT_SECONDS
    ) as response:
        result: dict[str, Any] = json.loads(response.read().decode())
        return result


def _canonical_cpe_token(value: str) -> str:
    """Normaliza um campo CPE para comparação sem caixa nem pontuação."""
    return re.sub(r"[^a-z0-9]", "", value.lower())


def _matching_cpe_name(
    product: dict[str, Any], vendor: str, model: str
) -> tuple[tuple[str, str, str], str] | None:
    """Retorna chave e CPE generalizado quando fornecedor e modelo coincidem."""
    name = product.get("cpe", {}).get("cpeName")
    if not isinstance(name, str):
        return None
    parts = name.split(":")
    if len(parts) != _CPE_FIELD_COUNT or parts[:_CPE_PART_INDEX] != [
        "cpe",
        _CPE_FORMAT_VERSION,
    ]:
        return None
    if parts[_CPE_PART_INDEX] not in (_CPE_SOFTWARE_PART, _CPE_HARDWARE_PART):
        return None
    cpe_vendor = _canonical_cpe_token(parts[_CPE_VENDOR_INDEX])
    cpe_model = _canonical_cpe_token(parts[_CPE_MODEL_INDEX]).removesuffix("firmware")
    if cpe_vendor != vendor or cpe_model != model:
        return None
    key = (
        parts[_CPE_PART_INDEX],
        parts[_CPE_VENDOR_INDEX],
        parts[_CPE_MODEL_INDEX],
    )
    return key, ":".join(
        parts[:_CPE_WILDCARD_START] + ["*"] * _CPE_WILDCARD_FIELD_COUNT
    )


def resolve_cpe_name(
    vendor: str, model: str, headers: dict[str, str], delay: float
) -> tuple[str | None, list[str]]:
    """Percorre o dicionário, prioriza software e expõe ambiguidades."""
    nvd_vendor = normalize_vendor(vendor)
    nvd_model = normalize_model(model)
    keyword = f"{nvd_vendor} {nvd_model}"
    expected_vendor = _canonical_cpe_token(nvd_vendor)
    expected_model = _canonical_cpe_token(nvd_model)
    accepted: dict[tuple[str, str, str], str] = {}
    start_index = 0
    while True:
        data = _fetch_cpe_page(keyword, start_index, headers)
        products = data.get("products", [])
        for product in products:
            match = _matching_cpe_name(product, expected_vendor, expected_model)
            if match is not None:
                key, name = match
                accepted[key] = name
        start_index += len(products)
        if not products or start_index >= data.get(_NVD_TOTAL_RESULTS_FIELD, 0):
            break
        time.sleep(delay)
    part = (
        _CPE_SOFTWARE_PART
        if any(key[0] == _CPE_SOFTWARE_PART for key in accepted)
        else _CPE_HARDWARE_PART
    )
    names = sorted(name for key, name in accepted.items() if key[0] == part)
    if len(names) == 1:
        return names[0], []
    return None, names


def _fetch_all_pages(
    query_params: str, headers: dict[str, str], delay: float
) -> list[dict[str, Any]]:
    """Busca páginas CVE completas e preserva dados brutos auditáveis."""
    start_index = 0
    cves: list[dict[str, Any]] = []
    while True:
        data = _fetch_page(query_params, start_index, headers)
        total_results = data.get(_NVD_TOTAL_RESULTS_FIELD, 0)
        vulnerabilities = data.get("vulnerabilities", [])
        for item in vulnerabilities:
            cve = item.get("cve", {})
            score, severity = extract_cvss(cve)
            cves.append(
                {
                    "id": cve.get("id", ""),
                    _CVE_MAX_SCORE_FIELD: score,
                    "severity": severity_bucket(severity),
                    "configurations": cve.get("configurations", []),
                }
            )
        start_index += len(vulnerabilities)
        if start_index >= total_results or not vulnerabilities:
            break
        time.sleep(delay)
    return cves


def fetch_cves_for_pair(
    vendor: str,
    model: str,
    headers: dict[str, str],
    delay: float,
) -> dict[str, Any]:
    """Busca CVEs por CPE oficial ou por texto e mantém evidência por CVE."""
    cpe_name, candidates = resolve_cpe_name(vendor, model, headers, delay)
    if cpe_name is not None:
        query_params = f"virtualMatchString={url_quote(cpe_name)}"
        source = "cpe"
    else:
        keyword = f"{normalize_vendor(vendor)} {normalize_model(model)}"
        query_params = f"{_KEYWORD_SEARCH_PARAM}={url_quote(keyword)}"
        source = "keyword"
    if delay > 0:
        time.sleep(delay)
    cves = _fetch_all_pages(query_params, headers, delay)
    return {
        _CACHE_SCHEMA_FIELD: CACHE_SCHEMA_VERSION,
        _FETCHED_AT_FIELD: datetime.now(timezone.utc).isoformat(
            timespec=_TIMESTAMP_PRECISION
        ),
        "cpe_candidates": candidates,
        "source": source,
        "vendor": normalize_vendor(vendor),
        "model": normalize_model(model),
        "cpe_name": cpe_name,
        _CVE_ITEMS_FIELD: cves,
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
    """Extrai pares únicos de fabricante/modelo ordenados das features."""
    # fillna before stringifying so missing values (None/NaN, regardless of
    # column dtype) normalize to "" instead of the literal string "nan".
    brand = df[_BRAND_COLUMN].fillna("").astype(str).str.strip().str.lower()
    model = df[_MODEL_COLUMN].fillna("").astype(str).str.strip().str.lower()
    valid = (brand != "") & (model != "")
    LOGGER.info(
        "Linhas descartadas por fabricante ou modelo nulo ou vazio: %d",
        int((~valid).sum()),
    )
    pairs = set(zip(brand[valid], model[valid]))
    return sorted(pairs)


def _should_save(fetched_count: int, interval: int = SAVE_INTERVAL) -> bool:
    """Return True when the cache should be flushed to disk.

    Saving after every fetch rewrites the whole (ever-growing) cache file,
    which is O(n^2) I/O over a full run. Flushing periodically instead keeps
    resumability (bounded loss on a crash) without that blowup.
    """
    return fetched_count % interval == 0


def _parse_args() -> argparse.Namespace:
    """Obtém os argumentos da busca de CVEs."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--features",
        required=True,
        help="Path to features parquet with meta_brand/meta_model columns",
    )
    parser.add_argument(
        "--output",
        default=_DEFAULT_CACHE_PATH,
        help=f"Path to CVE cache JSON (default: {_DEFAULT_CACHE_PATH})",
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
        "--force", action="store_true", help="Re-fetch even if pair is already cached"
    )
    return parser.parse_args()


def _resolve_delay(args: argparse.Namespace) -> float:
    """Escolhe o intervalo segundo a chave NVD e o argumento explícito."""
    if args.delay is not None:
        return float(args.delay)
    return (
        DEFAULT_DELAY_WITH_KEY
        if os.environ.get(_NVD_API_KEY_ENV)
        else DEFAULT_DELAY_NO_KEY
    )


def _load_pairs(path: Path) -> list[tuple[str, str]]:
    """Lê apenas as colunas de identidade e exige pares válidos."""
    df = pd.read_parquet(path, columns=[_BRAND_COLUMN, _MODEL_COLUMN])
    LOGGER.info("Loaded %d records from %s", len(df), path)
    pairs = extract_pairs(df)
    LOGGER.info("Found %d unique vendor/model pairs", len(pairs))
    if not pairs:
        LOGGER.error(
            "Nenhum par fabricante/modelo em %s; extraia as features com "
            "--label-from-path",
            path,
        )
        raise SystemExit(_EXIT_MISSING_PAIRS)
    return pairs


def _show_dry_run(pairs: list[tuple[str, str]]) -> None:
    """Lista os pares e suas formas NVD sem acessar rede nem cache."""
    for vendor, model in pairs:
        nv = normalize_vendor(vendor)
        nm = normalize_model(model)
        suffix = f" -> {nv} {nm}" if (nv != vendor or nm != model) else ""
        print(f"  {vendor}/{model}{suffix}")
    LOGGER.info("Dry run — no requests made")


def _fetch_one_pair(
    vendor: str,
    model: str,
    index: int,
    total: int,
    cache: dict[str, Any],
    headers: dict[str, str],
    delay: float,
    force: bool,
    stats: dict[str, int],
) -> None:
    """Reaproveita entrada válida ou consulta a NVD e registra a falha."""
    key = f"{vendor}/{model}"
    if key in cache and not force:
        entry = cache[key]
        version = entry.get(_CACHE_SCHEMA_FIELD) if isinstance(entry, dict) else None
        if version != CACHE_SCHEMA_VERSION:
            raise ValueError(
                f"Cache CVE em schema antigo para {key}: "
                f"schema_version={version}; rode com --force"
            )
        if not isinstance(entry.get(_CVE_ITEMS_FIELD), list):
            raise ValueError(f"Cache CVE inválido para {key}: cves não é uma lista")
        fetched_at = entry.get(_FETCHED_AT_FIELD)
        if not isinstance(fetched_at, str) or not fetched_at.strip():
            raise ValueError(
                f"Cache CVE inválido para {key}: fetched_at ausente; rode com --force"
            )
        LOGGER.info("[SKIP] %d/%d %s (cached)", index, total, key)
        stats[_STATS_CACHED] += 1
        stats[_STATS_TOTAL_CVES] += len(entry[_CVE_ITEMS_FIELD])
        return
    try:
        LOGGER.info("[FETCH] %d/%d %s", index, total, key)
        result = fetch_cves_for_pair(vendor, model, headers, delay)
        cache[key] = result
        stats[_STATS_FETCHED] += 1
        stats[_STATS_TOTAL_CVES] += len(result[_CVE_ITEMS_FIELD])
        LOGGER.info(
            "  -> %d CVEs (max CVSS: %.1f)",
            len(result[_CVE_ITEMS_FIELD]),
            max(
                (cve[_CVE_MAX_SCORE_FIELD] for cve in result[_CVE_ITEMS_FIELD]),
                default=_NO_CVSS_SCORE,
            ),
        )
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as exc:
        LOGGER.error("[FAIL] %s: %s", key, exc)
        stats[_STATS_FAILED] += 1
        if force:
            cache.pop(key, None)


def _fetch_all_pairs(
    pairs: list[tuple[str, str]],
    output: Path,
    delay: float,
    force: bool,
    stats: dict[str, int],
    args: argparse.Namespace,
    started_at: str,
) -> dict[str, int]:
    """Percorre pares e preserva o cache mesmo com exceção inesperada."""
    cache = load_cache(output)
    LOGGER.info("[CACHE] Loaded %d existing entries", len(cache))
    headers = _build_headers()
    try:
        for index, (vendor, model) in enumerate(pairs, 1):
            fetched_before = stats[_STATS_FETCHED]
            _fetch_one_pair(
                vendor,
                model,
                index,
                len(pairs),
                cache,
                headers,
                delay,
                force,
                stats,
            )
            if stats[_STATS_FETCHED] > fetched_before and _should_save(
                stats[_STATS_FETCHED]
            ):
                save_cache(cache, output)
                _write_run_metadata(args, output, started_at, stats)
            if index < len(pairs):
                time.sleep(delay)
    finally:
        save_cache(cache, output)
    return stats


def _log_summary(stats: dict[str, int]) -> None:
    """Registra a quantidade consultada, reaproveitada e falha."""
    LOGGER.info("--- Summary ---")
    LOGGER.info("  Fetched: %d", stats[_STATS_FETCHED])
    LOGGER.info("  Cached:  %d", stats[_STATS_CACHED])
    LOGGER.info("  Failed:  %d", stats[_STATS_FAILED])
    LOGGER.info("  Total CVEs: %d", stats[_STATS_TOTAL_CVES])


def _write_run_metadata(
    args: argparse.Namespace, output: Path, started_at: str, stats: dict[str, int]
) -> None:
    """Grava a proveniência de uma execução que escreveu o cache."""
    features = Path(args.features)
    metadata = {
        "cli_args": {
            key: str(value) if isinstance(value, Path) else value
            for key, value in vars(args).items()
        },
        "features_path": str(features),
        "features_sha256": file_sha256(features),
        "output_path": str(output),
        "code_commit": code_commit(),
        "started_at": started_at,
        "finished_at": datetime.now(timezone.utc).isoformat(
            timespec=_TIMESTAMP_PRECISION
        ),
        "pairs_fetched": stats[_STATS_FETCHED],
        "pairs_skipped": stats[_STATS_CACHED],
        "pairs_failed": stats[_STATS_FAILED],
    }
    path = output.with_name(f"{output.stem}.meta.json")
    path.write_text(json.dumps(metadata, indent=2, ensure_ascii=False) + "\n")


def main() -> None:
    """Orquestra a busca e sinaliza falhas depois de salvar os artefatos."""
    args = _parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    started_at = datetime.now(timezone.utc).isoformat(timespec=_TIMESTAMP_PRECISION)
    delay = _resolve_delay(args)
    pairs = _load_pairs(Path(args.features))
    if args.dry_run:
        _show_dry_run(pairs)
        return
    output = Path(args.output)
    stats = {
        _STATS_FETCHED: 0,
        _STATS_CACHED: 0,
        _STATS_FAILED: 0,
        _STATS_TOTAL_CVES: 0,
    }
    try:
        _fetch_all_pairs(pairs, output, delay, args.force, stats, args, started_at)
    except BaseException:
        if output.exists():
            _write_run_metadata(args, output, started_at, stats)
        raise
    _log_summary(stats)
    _write_run_metadata(args, output, started_at, stats)
    if stats[_STATS_FAILED]:
        raise SystemExit(_EXIT_FETCH_FAILURE)


if __name__ == "__main__":
    main()
