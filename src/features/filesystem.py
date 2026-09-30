"""Extrai inventário e proteções ELF das raízes do filesystem desempacotado."""

from __future__ import annotations

import hashlib
import logging
import os
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from elftools.elf.constants import P_FLAGS
from elftools.elf.dynamic import DynamicSegment
from elftools.elf.elffile import ELFFile

from src.features.unpack import (
    STATUS_NOT_RUN,
    STATUS_OK,
    find_filesystem_roots,
    iter_extracted_files,
)
from src.io_utils import iter_file_chunks

LOGGER = logging.getLogger(__name__)
FS_STATUS_ERROR = "erro"
KIND_EXEC, KIND_LIB, KIND_OTHER = "exec", "lib", "outro"
RELRO_FULL, RELRO_PARTIAL, RELRO_NONE = "full", "partial", "none"
DF_BIND_NOW = 0x8
DF_1_NOW = 0x1
_CANARY_SYMBOLS = {"__stack_chk_fail", "__stack_chk_guard", "__intel_security_cookie"}
UNPACKED_COLUMNS: tuple[str, ...] = (
    "unpacked_n_files",
    "unpacked_n_elf",
    "unpacked_n_elf_exec",
    "unpacked_n_elf_lib",
    "unpacked_n_elf_static",
    "unpacked_prop_nx",
    "unpacked_prop_pie",
    "unpacked_prop_relro_full",
    "unpacked_prop_relro_partial",
    "unpacked_prop_canary",
)


class MalformedElfError(ValueError):
    """Indica ELF ilegível ou maior que o limite de leitura."""


@dataclass(frozen=True)
class ElfInfo:
    """Guarda tipo, arquitetura e proteções observadas em um ELF."""

    kind: str
    machine: str
    static: bool
    nx: bool
    pie: bool
    relro: str
    canary: bool


@dataclass(frozen=True)
class FilesystemResult:
    """Agrupa colunas de features e metadados do filesystem."""

    features: dict[str, int | float | None]
    metadata: dict[str, Any]


def bind_now(tags: Iterable[tuple[str, int]]) -> bool:
    """Identifica resolução imediata de símbolos pelas tags dinâmicas."""
    return any(
        tag == "DT_BIND_NOW"
        or (tag == "DT_FLAGS" and value & DF_BIND_NOW != 0)
        or (tag == "DT_FLAGS_1" and value & DF_1_NOW != 0)
        for tag, value in tags
    )


def _classify_kind(elf_type: str, has_interp: bool, has_soname: bool) -> str:
    """Distingue executável de biblioteca sem confiar na tag DT_DEBUG."""
    if elf_type == "ET_EXEC":
        return KIND_EXEC
    if elf_type != "ET_DYN":
        return KIND_OTHER
    # Desvio do checksec 2.7.1: libs MIPS/uClibc reais têm DT_DEBUG;
    # ET_DYN sem PT_INTERP (inclusive static-pie) é contado como biblioteca.
    return KIND_EXEC if has_interp and not has_soname else KIND_LIB


def _elf_info(elf: ELFFile) -> ElfInfo:
    """Calcula as proteções enquanto o descritor do ELF permanece aberto."""
    segments = list(elf.iter_segments())
    dynamic = next((seg for seg in segments if isinstance(seg, DynamicSegment)), None)
    tags = (
        [(tag.entry.d_tag, tag["d_val"]) for tag in dynamic.iter_tags()]
        if dynamic is not None
        else []
    )
    elf_type = elf["e_type"]
    kind = _classify_kind(
        elf_type,
        any(seg["p_type"] == "PT_INTERP" for seg in segments),
        any(tag == "DT_SONAME" for tag, _ in tags),
    )
    static = kind in (KIND_EXEC, KIND_LIB) and dynamic is None
    nx = any(
        seg["p_type"] == "PT_GNU_STACK" and not seg["p_flags"] & P_FLAGS.PF_X
        for seg in segments
    )
    relro = RELRO_NONE
    if any(seg["p_type"] == "PT_GNU_RELRO" for seg in segments):
        # checksec classifica como full também quando .got.plt não existe.
        relro = (
            RELRO_FULL
            if bind_now(tags) or elf.get_section_by_name(".got.plt") is None
            else RELRO_PARTIAL
        )
    canary = dynamic is not None and any(
        symbol["st_shndx"] == "SHN_UNDEF" and symbol.name in _CANARY_SYMBOLS
        for symbol in dynamic.iter_symbols()
    )
    return ElfInfo(
        kind,
        elf["e_machine"],
        static,
        nx,
        kind == KIND_EXEC and elf_type == "ET_DYN",
        relro,
        canary,
    )


def read_elf(path: Path, max_bytes: int) -> ElfInfo:
    """Lê ELF limitado e rejeita arquivos malformados sem seguir symlink.

    Propaga erros de abertura e de consulta do tamanho do arquivo.
    """
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd, "rb") as handle:
        size = os.fstat(fd).st_size
        if size > max_bytes:
            raise MalformedElfError(f"{path}: {size} bytes > max_bytes {max_bytes}")
        try:
            return _elf_info(ELFFile(handle))
        except Exception as exc:
            raise MalformedElfError(f"{path}: {type(exc).__name__}: {exc}") from exc


def _unique_elfs(out: Path, max_bytes: int) -> tuple[int, list[Path]]:
    """Conta arquivos regulares e retém a primeira ocorrência de cada ELF."""
    n_files = 0
    paths: list[Path] = []
    seen: set[tuple[int, bytes]] = set()
    for root in find_filesystem_roots(out):
        for path in iter_extracted_files(root):
            n_files += 1
            fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
            with os.fdopen(fd, "rb") as handle:
                size = os.fstat(fd).st_size
                magic = handle.read(min(4, max_bytes))
            if magic != b"\x7fELF":
                continue
            digest = hashlib.sha256()
            for chunk in iter_file_chunks(path, max_bytes, nofollow=True):
                digest.update(chunk)
            key = size, digest.digest()
            if key not in seen:
                seen.add(key)
                paths.append(path)
    return n_files, paths


def _ratio(numerator: int, denominator: int) -> float | None:
    """Devolve a proporção ou None quando não há população elegível."""
    return numerator / denominator if denominator else None


def _aggregate(
    n_files: int, n_elf: int, infos: list[ElfInfo], malformed: int
) -> FilesystemResult:
    """Soma inventário e calcula proporções apenas sobre ELF elegíveis."""
    execs = [info for info in infos if info.kind == KIND_EXEC]
    libs = [info for info in infos if info.kind == KIND_LIB]
    eligible = execs + libs
    dynamic = [info for info in eligible if not info.static]
    architectures = Counter(info.machine for info in infos)
    top_count = max(architectures.values(), default=0)
    arch = min(
        (machine for machine, count in architectures.items() if count == top_count),
        default=None,
    )
    values: tuple[int | float | None, ...] = (
        n_files,
        n_elf,
        len(execs),
        len(libs),
        sum(info.static for info in eligible),
        _ratio(sum(info.nx for info in eligible), len(eligible)),
        _ratio(sum(info.pie for info in execs), len(execs)),
        _ratio(sum(info.relro == RELRO_FULL for info in eligible), len(eligible)),
        _ratio(sum(info.relro == RELRO_PARTIAL for info in eligible), len(eligible)),
        _ratio(sum(info.canary for info in dynamic), len(dynamic)),
    )
    features = dict(zip(UNPACKED_COLUMNS, values))
    return FilesystemResult(
        features,
        {
            "fs_status": STATUS_OK,
            "fs_error": None,
            "fs_elf_malformed": malformed,
            "fs_arch": arch,
        },
    )


def _unavailable(status: str, error: str | None = None) -> FilesystemResult:
    """Marca como ausentes todas as colunas quando o filesystem não é utilizável."""
    return FilesystemResult(
        dict.fromkeys(UNPACKED_COLUMNS),
        {
            "fs_status": status,
            "fs_error": error,
            "fs_elf_malformed": None,
            "fs_arch": None,
        },
    )


def filesystem_features(out: Path, max_bytes: int) -> FilesystemResult:
    """Extrai features das raízes encontradas sob a saída do unpack."""
    try:
        n_files, paths = _unique_elfs(out, max_bytes)
        infos: list[ElfInfo] = []
        malformed = 0
        for path in paths:
            try:
                infos.append(read_elf(path, max_bytes))
            except MalformedElfError as exc:
                malformed += 1
                LOGGER.warning("ELF malformado: %s", exc)
        return _aggregate(n_files, len(paths), infos, malformed)
    except Exception as exc:
        LOGGER.error("Falha nas features do filesystem em %s: %s", out, exc)
        return _unavailable(FS_STATUS_ERROR, f"{type(exc).__name__}: {exc}")


def unavailable_filesystem() -> FilesystemResult:
    """Devolve features ausentes quando o unpack não produziu filesystem."""
    return _unavailable(STATUS_NOT_RUN)
