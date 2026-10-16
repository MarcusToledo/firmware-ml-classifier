"""Organiza firmwares soltos e unifica modelos TP-Link quando solicitado.

O modo de mesclagem planeja e verifica todos os conflitos antes de mover.
Sem --execute, nenhum arquivo ou diretório é alterado.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import logging
import re
import sys
from collections.abc import Callable
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "dataset" / "raw"
LOGGER = logging.getLogger(__name__)

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


def plan_vendor_merge(raw: Path) -> tuple[list[tuple[Path, Path]], list[Path]]:
    """Lista firmwares e diretórios vazios sem alterar a árvore de origem."""
    origin = raw / "tplink"
    if not origin.is_dir():
        raise FileNotFoundError(f"Fabricante de origem ausente: {origin}")
    moves: list[tuple[Path, Path]] = []
    empty_dirs: list[Path] = []
    for model_dir in sorted(origin.iterdir()):
        if not model_dir.is_dir() or model_dir.is_symlink():
            raise ValueError(f"Modelo inválido em {origin}: {model_dir}")
        files = sorted(model_dir.iterdir())
        if any(not path.is_file() or path.is_symlink() for path in files):
            raise ValueError(
                f"Conteúdo inesperado no modelo {model_dir.name}: {model_dir}"
            )
        if not files:
            empty_dirs.append(model_dir)
        for source in files:
            target = raw / "tp_link" / model_dir.name.replace("_", "-") / source.name
            moves.append((source, target))
    return moves, empty_dirs


def validate_vendor_merge(moves: list[tuple[Path, Path]]) -> None:
    """Recusa modelos ocupados ou duas origens para o mesmo destino."""
    targets: dict[Path, str] = {}
    for source, target in moves:
        previous = targets.setdefault(target.parent, source.parent.name)
        if previous != source.parent.name:
            raise ValueError(
                f"Modelo {source.parent.name}: {previous} também aponta "
                f"para {target.parent}"
            )
        if target.parent.is_dir():
            if any(path.is_file() for path in target.parent.rglob("*")):
                raise ValueError(
                    f"Modelo {source.parent.name}: destino {target.parent} "
                    "já tem arquivo"
                )
        elif target.parent.exists():
            raise ValueError(
                f"Modelo {source.parent.name}: destino inválido {target.parent}"
            )


def sha256_file(path: Path) -> str:
    """Calcula SHA256 em blocos sem carregar o firmware inteiro na memória."""
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def run_vendor_merge(raw: Path, root: Path, execute: bool) -> int:
    """Valida o plano completo e só então move e registra os firmwares."""
    moves, empty_dirs = plan_vendor_merge(raw)
    print(f"Summary: {len(moves)} files planned, {len(empty_dirs)} empty directories")
    try:
        validate_vendor_merge(moves)
    except ValueError as exc:
        LOGGER.error("%s", exc)
        return 1
    for source, target in moves:
        print(f"  {'MOVE' if execute else 'WOULD MOVE'}  "
              f"{source.relative_to(raw)}  →  {target.relative_to(raw)}")
    if not execute:
        print("Re-run with --execute to apply.")
        return 0
    rows = [
        (source.relative_to(raw).as_posix(), target.relative_to(raw).as_posix(),
         sha256_file(source)) for source, target in moves
    ]
    for source, target in moves:
        target.parent.mkdir(parents=True, exist_ok=True)
        source.rename(target)
    for model_dir in sorted((raw / "tplink").iterdir()):
        model_dir.rmdir()
    (raw / "tplink").rmdir()
    map_path = root / "configs" / "tplink_merge_map.csv"
    map_path.parent.mkdir(parents=True, exist_ok=True)
    with map_path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(("old_path", "new_path", "sha256"))
        writer.writerows(rows)
    LOGGER.info("Mesclados %d arquivos, removidos %d modelos vazios; mapa %s",
                len(moves), len(empty_dirs), map_path)
    return 0


def run_flat_reorganization(vendors: list[str], dry_run: bool) -> int:
    """Executa o modo legado de organização dos firmwares soltos."""
    print("=== reorganize_dataset.py "
          f"[{'DRY RUN — pass --execute to apply' if dry_run else 'EXECUTE'}] ===\n")
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
        print(f"[{vendor}] {len(flat)} flat files → "
              f"{len(moves) - len(skips)} with model, {len(skips)} → _non_router")
        execute_moves(moves, dry_run)
        print()
    print(f"Summary: {total_moves} files planned "
          f"({total_moves - total_skips} to model dirs, {total_skips} to _non_router)")
    if dry_run:
        print("Re-run with --execute to apply.")
    else:
        print("Done. Run validate_dataset.py to confirm dataset is clean.")
    return 0


def main() -> int:
    """Interpreta os argumentos e executa o modo de organização selecionado."""
    parser = argparse.ArgumentParser(
        description="Reorganise flat firmware files or merge TP-Link vendors."
    )
    parser.add_argument("--execute", action="store_true",
                        help="Actually move files (default: dry-run)")
    parser.add_argument("--vendor", nargs="+",
                        help="Limit flat-file reorganisation to specific vendors")
    parser.add_argument("--merge-vendor", metavar="SOURCE:DESTINATION",
                        help="Merge tplink:tp_link models and write a SHA256 map")
    parser.add_argument(
        "--raw", type=Path, default=RAW,
        help="Dataset raw a mesclar (padrão: dataset/raw do projeto)",
    )
    args = parser.parse_args()
    if args.merge_vendor:
        if args.merge_vendor != "tplink:tp_link" or args.vendor:
            parser.error("--merge-vendor aceita apenas tplink:tp_link, sem --vendor")
        try:
            return run_vendor_merge(args.raw, ROOT, args.execute)
        except (OSError, ValueError) as exc:
            LOGGER.error("Falha na mesclagem tplink:tp_link: %s", exc)
            return 1
    return run_flat_reorganization(args.vendor or list(_EXTRACTORS), not args.execute)


if __name__ == "__main__":
    sys.exit(main())
