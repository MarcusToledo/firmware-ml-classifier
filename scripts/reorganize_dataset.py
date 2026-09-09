"""Move flat firmware files into vendor/model/ subdirectories.

The pipeline expects dataset/raw/{vendor}/{model}/{firmware_file}.
Files placed directly at dataset/raw/{vendor}/{file} break automatic
metadata inference (infer_brand_model_label_from_path).

By default runs in --dry-run mode and only prints what it would do.
Pass --execute to actually move files.

Usage:
    python3 scripts/reorganize_dataset.py --dry-run      (default, safe)
    python3 scripts/reorganize_dataset.py --execute
    python3 scripts/reorganize_dataset.py --execute --vendor asus
"""

from __future__ import annotations

import argparse
import re
import sys
from collections.abc import Callable
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "dataset" / "raw"

# ---------------------------------------------------------------------------
# ASUS model extraction
# ---------------------------------------------------------------------------

# Router firmware filename prefixes — everything else is non-router
_ASUS_ROUTER_MODEL_PREFIXES = (
    "RT-",
    "RT_",
    "DSL-",
    "DSL_",
    "GT-",
    "GT_",
    "BRT_",
    "BLUECAVE",
    "6338",
    "ZENWIFI",
    "ZEN_WIFI",
    "ZEN-WIFI",
    "WL-",
    "WL_",  # older ASUS WL-series wireless routers/APs
)

# FW_<MODEL>_<numeric-build>.ext  or  FW_<MODEL>_<version>_<build>.ext
_ASUS_FW = re.compile(r"^FW_([A-Z0-9][A-Z0-9_\-]+?)_[\d.]", re.IGNORECASE)
# Rescue_<MODEL>_<build>.ext  or  Rescue_<MODEL>-<suffix>_<build>.ext
_ASUS_RESCUE = re.compile(
    r"^Rescue_([A-Z0-9][A-Z0-9_\-]+?)(?:_[\d]|-[A-Z0-9]+_[\d])", re.IGNORECASE
)
# Asus-<MODEL>-webflash.ext
_ASUS_WEBFLASH = re.compile(r"^Asus-([A-Za-z0-9]+)-webflash", re.IGNORECASE)


def _asus_model(fname: str) -> str | None:
    m = _ASUS_FW.match(fname)
    if m:
        raw = m.group(1).upper()
        if any(raw.startswith(p.upper()) for p in _ASUS_ROUTER_MODEL_PREFIXES):
            return raw.lower().replace("_", "-")
        return None  # non-router

    m = _ASUS_RESCUE.match(fname)
    if m:
        raw = m.group(1)
        return raw.lower().replace("_", "-")

    m = _ASUS_WEBFLASH.match(fname)
    if m:
        raw = m.group(1)
        return raw.lower()

    return None  # unrecognised → non-router


# ---------------------------------------------------------------------------
# TP-Link model extraction
# ---------------------------------------------------------------------------

# "Archer C7(EU)_V2_..." → archer-c7
# "Archer C1200(EU)_V1_..." → archer-c1200
# "Archer VR2100(EU)_V1_..." → archer-vr2100
# "ArcherD7b_V1_..." → archer-d7b
# "Archer_C50_v1_..." → archer-c50
_TPLINK_ARCHER = re.compile(
    r"^Archer[_ ]?([A-Za-z0-9]+(?:[ \-][A-Za-z0-9]+)?)[\s(_]", re.IGNORECASE
)
# "TL-WR841N_V10..." → tl-wr841n
# "TD-W8151N_v1_..." → td-w8151n
# "TL-ER604W(EU)_V2_..." → tl-er604w
_TPLINK_TL = re.compile(r"^((?:TL|TD)-[A-Z0-9]+)", re.IGNORECASE)
# "archer-c9v4-webflash.bin" → archer-c9
# "tl-wdr3500-webflash.bin" → tl-wdr3500
# "tl-wr703v1-webflash.bin" → tl-wr703
_TPLINK_WEBFLASH = re.compile(r"^([a-z]+-[a-z0-9]+?)(?:v\d+)?-webflash", re.IGNORECASE)


def _tplink_model(fname: str) -> str | None:
    m = _TPLINK_ARCHER.match(fname)
    if m:
        raw = "Archer " + m.group(1).strip()
        return raw.lower().replace(" ", "-")

    m = _TPLINK_TL.match(fname)
    if m:
        return m.group(1).lower()

    m = _TPLINK_WEBFLASH.match(fname)
    if m:
        return m.group(1).lower()

    return None


# ---------------------------------------------------------------------------
# Netgear model extraction
# ---------------------------------------------------------------------------

# "D6000_V1.0.0.72_1.0.1.zip" → d6000
# "R6220_V1.1.0.50_1.0.1.zip" → r6220
# "D7800_FW_V1.0.1.60.zip"    → d7800
# "D6300-Firmware_-V1.0.0.16_1.0.16.zip" → d6300
# "D6400-FW_V1.0.0.74_1.0.74.zip" → d6400
# "D6400-V1.0.0.68_1.0.68_FW.zip" → d6400
_NETGEAR_MODEL = re.compile(
    r"^([A-Z][A-Z0-9]+?)(?:[-_](?:FW|Firmware|V\d)|_V\d|-V\d)", re.IGNORECASE
)


def _netgear_model(fname: str) -> str | None:
    m = _NETGEAR_MODEL.match(fname)
    if m:
        return m.group(1).lower()
    return None


# ---------------------------------------------------------------------------
# Per-vendor dispatch
# ---------------------------------------------------------------------------

_EXTRACTORS: dict[str, Callable[[str], str | None]] = {
    "asus": _asus_model,
    "tp_link": _tplink_model,
    "netgear": _netgear_model,
}


def extract_model(vendor: str, fname: str) -> str | None:
    extractor = _EXTRACTORS.get(vendor)
    if extractor is None:
        return None
    return extractor(fname)


# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------


def collect_flat_files(vendor: str) -> list[Path]:
    vendor_dir = RAW / vendor
    if not vendor_dir.is_dir():
        return []
    return [p for p in vendor_dir.iterdir() if p.is_file() and p.name != ".DS_Store"]


def plan_moves(vendor: str) -> tuple[list[tuple[Path, Path]], list[tuple[Path, str]]]:
    moves: list[tuple[Path, Path]] = []
    skips: list[tuple[Path, str]] = []

    for src in collect_flat_files(vendor):
        model = extract_model(vendor, src.name)
        if model is None:
            skips.append((src, "no model pattern matched → _non_router"))
            dest = RAW / vendor / "_non_router" / src.name
            moves.append((src, dest))
        else:
            dest = RAW / vendor / model / src.name
            moves.append((src, dest))

    return moves, skips


def execute_moves(moves: list[tuple[Path, Path]], dry_run: bool) -> None:
    for src, dest in moves:
        verb = "MOVE" if not dry_run else "WOULD MOVE"
        rel_src = src.relative_to(ROOT)
        rel_dest = dest.relative_to(ROOT)
        print(f"  {verb}  {rel_src}  →  {rel_dest}")
        if not dry_run:
            dest.parent.mkdir(parents=True, exist_ok=True)
            src.rename(dest)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Reorganise flat firmware files into vendor/model/ dirs."
    )
    parser.add_argument(
        "--execute", action="store_true", help="Actually move files (default: dry-run)"
    )
    parser.add_argument(
        "--vendor", nargs="+", help="Limit to specific vendors (default: all)"
    )
    args = parser.parse_args()

    dry_run = not args.execute
    vendors = args.vendor or list(_EXTRACTORS.keys())

    if dry_run:
        print("=== reorganize_dataset.py [DRY RUN — pass --execute to apply] ===")
    else:
        print("=== reorganize_dataset.py [EXECUTE] ===")
    print()

    total_moves = 0
    total_skips = 0

    for vendor in vendors:
        flat = collect_flat_files(vendor)
        if not flat:
            print(f"[{vendor}] No flat files found, skipping.")
            continue

        moves, skips = plan_moves(vendor)
        total_moves += len(moves)
        total_skips += len(skips)

        print(
            f"[{vendor}] {len(flat)} flat files → "
            f"{len(moves) - len(skips)} with model, {len(skips)} → _non_router"
        )
        execute_moves(moves, dry_run)
        print()

    print(
        f"Summary: {total_moves} files planned "
        f"({total_moves - total_skips} to model dirs, {total_skips} to _non_router)"
    )
    if dry_run:
        print("Re-run with --execute to apply.")
    else:
        print("Done. Run validate_dataset.py to confirm dataset is clean.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
