"""Audit the firmware dataset for structural issues.

Checks:
  1. Files at wrong nesting level (flat under vendor, should be vendor/model/)
  2. labels.csv consistency (meta_path on disk, no duplicate firmware_id)
  3. Orphan files on disk not referenced in labels.csv
  4. ASUS non-router detection (BIOS/motherboard files mixed in)
  5. Duplicate firmware content (same SHA256 at different paths)

Exit code 0 → dataset is clean. Exit code 1 → issues found.

Usage:
    python3 scripts/validate_dataset.py
    python3 scripts/validate_dataset.py --no-hashes   (skip slow SHA256 scan)
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "dataset" / "raw"
LABELS_CSV = ROOT / "dataset" / "labels.csv"

# ASUS router model prefixes (after stripping "FW_" / "Rescue_" / "Asus-")
ASUS_ROUTER_PREFIXES = (
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
    "WL_",
)


def is_asus_router_file(fname: str) -> bool:
    upper = fname.upper()
    if upper.startswith("FW_"):
        model = upper[3:]
        return any(model.startswith(p.upper()) for p in ASUS_ROUTER_PREFIXES)
    if upper.startswith("RESCUE_"):
        return True
    if upper.startswith("ASUS-RT"):
        return True
    return False


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def check_structure() -> list[str]:
    issues: list[str] = []
    flat_by_vendor: dict[str, list[Path]] = defaultdict(list)

    for vendor_dir in sorted(RAW.iterdir()):
        if not vendor_dir.is_dir():
            continue
        for item in vendor_dir.iterdir():
            if item.is_file() and item.name != ".DS_Store":
                flat_by_vendor[vendor_dir.name].append(item)

    if flat_by_vendor:
        issues.append(
            "FILES PLACED DIRECTLY IN VENDOR DIR (expected vendor/model/file):"
        )
        for vendor, files in sorted(flat_by_vendor.items()):
            non_router = []
            if vendor == "asus":
                non_router = [f for f in files if not is_asus_router_file(f.name)]
            issues.append(
                f"  {vendor}: {len(files)} flat files"
                + (f" ({len(non_router)} appear non-router)" if non_router else "")
            )
    return issues


def check_labels() -> list[str]:
    issues: list[str] = []

    if not LABELS_CSV.exists():
        return [f"labels.csv not found at {LABELS_CSV}"]

    seen_ids: dict[str, str] = {}
    missing_paths: list[str] = []

    with LABELS_CSV.open() as f:
        reader = csv.DictReader(f)
        for row in reader:
            fid = row["firmware_id"]
            meta = row["meta_path"]
            full = ROOT / meta if not meta.startswith("/") else Path(meta)

            if not full.exists():
                missing_paths.append(meta)

            if fid in seen_ids:
                issues.append(f"DUPLICATE firmware_id {fid}: {seen_ids[fid]} vs {meta}")
            else:
                seen_ids[fid] = meta

    if missing_paths:
        issues.append(f"MISSING FILES referenced in labels.csv ({len(missing_paths)}):")
        for p in missing_paths[:10]:
            issues.append(f"  {p}")
        if len(missing_paths) > 10:
            issues.append(f"  ... and {len(missing_paths) - 10} more")

    return issues


def check_orphans() -> list[str]:
    issues: list[str] = []

    if not LABELS_CSV.exists():
        return []

    labeled: set[str] = set()
    with LABELS_CSV.open() as f:
        for row in csv.DictReader(f):
            labeled.add(row["meta_path"])

    orphans_by_vendor: dict[str, int] = defaultdict(int)
    for fpath in RAW.rglob("*"):
        if not fpath.is_file() or fpath.name == ".DS_Store":
            continue
        rel = str(fpath.relative_to(ROOT))
        if rel not in labeled:
            vendor = (
                fpath.relative_to(RAW).parts[0]
                if fpath.is_relative_to(RAW)
                else "unknown"
            )
            orphans_by_vendor[vendor] += 1

    if orphans_by_vendor:
        total = sum(orphans_by_vendor.values())
        issues.append(f"ORPHAN FILES on disk not in labels.csv ({total} total):")
        for vendor, count in sorted(orphans_by_vendor.items()):
            issues.append(f"  {vendor}: {count}")
    if orphans_by_vendor:
        issues.append(
            "  → Run extract_features.py + generate_labels.py to label these files."
        )

    return issues


def check_asus_non_routers() -> list[str]:
    asus_dir = RAW / "asus"
    if not asus_dir.exists():
        return []

    non_routers = [
        f for f in asus_dir.iterdir() if f.is_file() and not is_asus_router_file(f.name)
    ]
    if not non_routers:
        return []

    issues = [f"ASUS NON-ROUTER FILES ({len(non_routers)}) mixed with router firmware:"]
    for f in sorted(non_routers)[:15]:
        issues.append(f"  {f.name}")
    if len(non_routers) > 15:
        issues.append(f"  ... and {len(non_routers) - 15} more")
    return issues


def check_duplicates() -> list[str]:
    issues: list[str] = []
    hash_to_paths: dict[str, list[Path]] = defaultdict(list)

    all_files = list(RAW.rglob("*"))
    all_files = [f for f in all_files if f.is_file()]

    print(f"  Computing SHA256 for {len(all_files)} files ...", flush=True)
    for fpath in all_files:
        try:
            h = sha256(fpath)
            hash_to_paths[h].append(fpath)
        except OSError:
            pass

    dupes = {h: paths for h, paths in hash_to_paths.items() if len(paths) > 1}
    if dupes:
        issues.append(f"DUPLICATE CONTENT ({len(dupes)} groups):")
        for h, paths in list(dupes.items())[:5]:
            issues.append(f"  SHA256 {h[:12]}...:")
            for p in paths:
                issues.append(f"    {p.relative_to(ROOT)}")
    return issues


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit the firmware dataset.")
    parser.add_argument(
        "--no-hashes", action="store_true", help="Skip SHA256 duplicate check"
    )
    args = parser.parse_args()

    all_issues: list[str] = []

    print("=== validate_dataset.py ===")
    print()

    print("[1/5] Checking directory structure ...")
    all_issues += check_structure()

    print("[2/5] Checking labels.csv consistency ...")
    all_issues += check_labels()

    print("[3/5] Checking for orphan files ...")
    all_issues += check_orphans()

    print("[4/5] Checking for ASUS non-router files ...")
    all_issues += check_asus_non_routers()

    if args.no_hashes:
        print("[5/5] Skipping SHA256 duplicate check (--no-hashes)")
    else:
        print("[5/5] Checking for duplicate content ...")
        all_issues += check_duplicates()

    print()
    if all_issues:
        print("ISSUES FOUND:")
        for line in all_issues:
            print(line)
        print()
        print(f"Total: {len(all_issues)} issue lines.")
        return 1

    print("OK — dataset looks clean.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
