"""Gera fixtures ELF e confere as proteções com checksec 2.7.1."""

from __future__ import annotations

import argparse
import json
import logging
import struct
import subprocess
from pathlib import Path
from typing import Any

from elftools.elf.elffile import ELFFile

LOGGER = logging.getLogger(__name__)
ROOT = Path(__file__).resolve().parent
PROG = "src/prog.c"
LIB = "src/lib.c"
FLAGS: tuple[tuple[str, list[str], dict[str, Any]], ...] = (
    (
        "exec_hardened",
        [
            "-O0",
            "-fPIE",
            "-pie",
            "-fstack-protector-all",
            "-Wl,-z,relro,-z,now",
            "-Wl,-z,noexecstack",
            PROG,
        ],
        {
            "kind": "exec",
            "static": False,
            "nx": True,
            "pie": True,
            "relro": "full",
            "canary": True,
        },
    ),
    (
        "exec_partial",
        [
            "-O0",
            "-fno-pie",
            "-no-pie",
            "-fno-stack-protector",
            "-Wl,-z,relro,-z,lazy",
            "-Wl,-z,noexecstack",
            PROG,
        ],
        {
            "kind": "exec",
            "static": False,
            "nx": True,
            "pie": False,
            "relro": "partial",
            "canary": False,
        },
    ),
    (
        "exec_weak",
        [
            "-O0",
            "-fno-pie",
            "-no-pie",
            "-fno-stack-protector",
            "-Wl,-z,norelro",
            "-Wl,-z,execstack",
            PROG,
        ],
        {
            "kind": "exec",
            "static": False,
            "nx": False,
            "pie": False,
            "relro": "none",
            "canary": False,
        },
    ),
    (
        "lib_hardened.so",
        [
            "-O0",
            "-shared",
            "-fPIC",
            "-fstack-protector-all",
            "-Wl,-z,relro,-z,now",
            "-Wl,-z,noexecstack",
            LIB,
        ],
        {
            "kind": "lib",
            "static": False,
            "nx": True,
            "pie": False,
            "relro": "full",
            "canary": True,
        },
    ),
    (
        "exec_static",
        [
            "-O0",
            "-static",
            "-fno-pie",
            "-no-pie",
            "-fstack-protector-all",
            "-Wl,-z,noexecstack",
            "-s",
            PROG,
        ],
        {"kind": "exec", "static": True, "nx": True, "pie": False},
    ),
    (
        "obj_rel.o",
        ["-O0", "-c", LIB],
        {
            "kind": "outro",
            "static": False,
            "nx": False,
            "pie": False,
            "relro": "none",
            "canary": False,
        },
    ),
)


def compile_fixtures() -> tuple[list[dict[str, Any]], bool]:
    """Compila as variantes de gcc e registra a ausência eventual de libc estática."""
    fixtures: list[dict[str, Any]] = []
    static_omitted = False
    for filename, flags, expected in FLAGS:
        command = ["gcc", *flags, "-o", filename]
        try:
            subprocess.run(
                command, cwd=ROOT, check=True, capture_output=True, text=True
            )
        except subprocess.CalledProcessError as exc:
            if filename != "exec_static":
                raise RuntimeError(f"{filename}: gcc falhou: {exc.stderr}") from exc
            LOGGER.warning("exec_static omitido: %s", exc.stderr.strip())
            static_omitted = True
            continue
        fixtures.append(
            {
                "file": filename,
                "command": command,
                "expected": {"malformed": False, "machine": "EM_X86_64", **expected},
            }
        )
    return fixtures, static_omitted


def make_mips() -> dict[str, Any]:
    """Monta um ELF32 MIPS big-endian executável sem dependência de compilador."""
    ident = b"\x7fELF" + bytes((1, 2, 1, 0)) + bytes(8)
    header = struct.pack(
        ">16sHHIIIIIHHHHHH", ident, 2, 8, 1, 0, 52, 0, 0, 52, 32, 2, 40, 0, 0
    )
    load = struct.pack(">IIIIIIII", 1, 0, 0, 0, 116, 116, 5, 0x1000)
    stack = struct.pack(">IIIIIIII", 0x6474E551, 0, 0, 0, 0, 0, 6, 16)
    (ROOT / "mips_be_static").write_bytes(header + load + stack)
    return {
        "file": "mips_be_static",
        "command": ["struct", "ELF32", "big-endian"],
        "expected": {
            "malformed": False,
            "kind": "exec",
            "machine": "EM_MIPS",
            "static": True,
            "nx": True,
            "pie": False,
            "relro": "none",
            "canary": False,
        },
    }


def make_truncated() -> dict[str, Any]:
    """Trunca um ELF até que pyelftools falhe ao examinar seus segmentos."""
    source = (ROOT / "exec_hardened").read_bytes()
    for size in (120, 70):
        path = ROOT / "truncated_elf"
        path.write_bytes(source[:size])
        try:
            with path.open("rb") as handle:
                elf = ELFFile(handle)
                _ = elf["e_type"]
                list(elf.iter_segments())
        except Exception:
            LOGGER.info("truncated_elf: pyelftools rejeitou %d bytes", size)
            return {
                "file": path.name,
                "command": ["truncate", "exec_hardened", str(size)],
                "expected": {"malformed": True},
                "checksec": None,
            }
    raise RuntimeError("truncated_elf: nem 70 bytes falharam no pyelftools")


def inspect_checksec(binary: str, executable: str) -> dict[str, str]:
    """Obtém o resultado JSON do checksec, aceitando ambas as flags de formato."""
    for option in ("--output=json", "--format=json"):
        result = subprocess.run(
            [executable, option, f"--file={binary}"],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            try:
                report = json.loads(result.stdout)
                return report[binary]
            except (KeyError, ValueError) as exc:
                raise RuntimeError(f"{binary}: checksec JSON inválido") from exc
        LOGGER.warning(
            "%s: checksec rejeitou %s: %s", binary, option, result.stderr.strip()
        )
    raise RuntimeError(f"{binary}: checksec rejeitou --output e --format")


def check_expected(fixture: dict[str, Any], oracle: dict[str, str]) -> None:
    """Compara campos inferidos das flags com a referência do checksec."""
    name = fixture["file"]
    expected = fixture["expected"]
    if name == "obj_rel.o":
        # Checksec reporta n/a para NX/RELRO e símbolo de canary em ET_REL.
        # Esses campos não representam proteções de um binário carregável.
        if oracle["pie"] != "rel":
            raise ValueError(f"{name}: pie: esperado 'rel', checksec {oracle['pie']!r}")
        fixture["checksec"] = {
            field: oracle[field] for field in ("relro", "canary", "nx", "pie")
        }
        return
    mapped = {
        "relro": {"full": "full", "partial": "partial", "no": "none"}.get(
            oracle["relro"]
        ),
        "canary": oracle["canary"] == "yes",
        "nx": oracle["nx"] == "yes",
        "pie": oracle["pie"] == "yes",
    }
    valid_values = {
        "relro": ("full", "partial", "no"),
        "canary": ("yes", "no"),
        "nx": ("yes", "no"),
        "pie": ("yes", "no", "dso", "rel"),
    }
    for field, value in mapped.items():
        if value is None or oracle[field] not in valid_values[field]:
            raise ValueError(f"{name}: checksec retornou {field}={oracle[field]!r}")
        if name == "exec_static" and field in ("relro", "canary"):
            expected[field] = value
        elif expected[field] != value:
            raise ValueError(
                f"{name}: {field}: esperado {expected[field]!r}, "
                f"checksec {oracle[field]!r}"
            )
    fixture["checksec"] = {field: oracle[field] for field in mapped}


def build(checksec: str | None) -> None:
    """Gera os binários e grava o manifesto rastreável das observações."""
    gcc = subprocess.run(
        ["gcc", "--version"], check=True, capture_output=True, text=True
    ).stdout.splitlines()[0]
    fixtures, static_omitted = compile_fixtures()
    fixtures.extend((make_mips(), make_truncated()))
    for fixture in fixtures:
        if fixture["expected"]["malformed"]:
            continue
        if checksec is None:
            fixture["checksec"] = None
            if fixture["file"] == "exec_static":
                fixture["expected"].update(relro="partial", canary=False)
        else:
            check_expected(fixture, inspect_checksec(fixture["file"], checksec))
    manifest = {
        "generator": "tests/fixtures/elf/build_fixtures.py",
        "gcc": gcc,
        "checksec": "2.7.1" if checksec else None,
        "fixtures": fixtures,
    }
    if static_omitted:
        manifest["exec_static_omitted"] = "gcc -static falhou"
    (ROOT / "manifest.json").write_text(
        json.dumps(manifest, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )
    LOGGER.info("Geradas %d fixtures ELF", len(fixtures))


def main() -> None:
    """Recebe o modo de conferência e inicia a geração determinística."""
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--checksec", help="Caminho do checksec 2.7.1")
    group.add_argument("--no-checksec", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    build(args.checksec)


if __name__ == "__main__":
    main()
