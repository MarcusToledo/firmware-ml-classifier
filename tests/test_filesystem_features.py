"""Exercita inventário, proteções e falhas em ELF desempacotados."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

import pytest

import src.features.filesystem as filesystem_module
from src.features.filesystem import (
    UNPACKED_COLUMNS,
    FilesystemResult,
    bind_now,
    filesystem_features,
    read_elf,
    unavailable_filesystem,
)
from src.features.unpack import find_filesystem_roots

FIXTURES = Path(__file__).parent / "fixtures/elf"
MAX_BYTES = 268_435_456


def _root(tmp_path: Path, name: str = "squashfs-root") -> Path:
    """Cria uma raiz extraída em um diretório temporário."""
    root = tmp_path / "out/_fw.extracted" / name
    root.mkdir(parents=True)
    return root


def _copy(root: Path, fixture: str, target: str | None = None) -> Path:
    """Copia um ELF de teste para uma raiz extraída."""
    path = root / (target or fixture)
    path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(FIXTURES / fixture, path)
    return path


def _extract(root: Path, max_bytes: int = MAX_BYTES) -> FilesystemResult:
    """Extrai as features da saída que contém a raiz de teste."""
    return filesystem_features(root.parent.parent, max_bytes)


def _manifest() -> list[dict[str, Any]]:
    """Lê o oráculo registrado pelo gerador de fixtures."""
    return json.loads((FIXTURES / "manifest.json").read_text())["fixtures"]


def test_inventory_counts_files_and_elf_without_extension(tmp_path: Path) -> None:
    """Conta arquivos sem depender de extensão ou localização bin/lib."""
    root = _root(tmp_path)
    for name in ("config", "etc/passwd", "var/state"):
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("text")
    _copy(root, "exec_hardened", "bin/app")
    _copy(root, "lib_hardened.so", "lib/library.so")
    result = _extract(root)
    assert result.metadata["fs_status"] == "ok"
    assert [result.features[key] for key in UNPACKED_COLUMNS[:5]] == [5, 2, 1, 1, 0]


def test_roots_ignore_carved_symlinks_and_duplicate_elf(tmp_path: Path) -> None:
    """Ignora ELF fora de raízes, symlinks e duplicatas entre raízes."""
    root = _root(tmp_path)
    _copy(root, "exec_hardened", "bin/app")
    (root / "shortcut").symlink_to("bin/app")
    _copy(root.parent, "exec_partial", "1A0.elf")
    second = _root(tmp_path, "squashfs-root-0")
    _copy(second, "exec_hardened", "copy")
    nested = root / "sub/cpio-root"
    nested.mkdir(parents=True)
    (nested / "x").write_text("text")
    (root.parent / "link-root").symlink_to(root, target_is_directory=True)
    assert [path.name for path in find_filesystem_roots(root.parent.parent)] == [
        "squashfs-root",
        "squashfs-root-0",
    ]
    result = _extract(root)
    assert result.features["unpacked_n_files"] == 3
    assert result.features["unpacked_n_elf"] == 1
    assert result.features["unpacked_n_elf_exec"] == 1


@pytest.mark.parametrize(
    "fixture",
    [
        row["file"]
        for row in _manifest()
        if row["expected"].get("kind") in ("exec", "lib")
    ],
)
def test_fixture_protections_match_manifest(tmp_path: Path, fixture: str) -> None:
    """Confere cada proteção com o oráculo do manifest por árvore isolada."""
    expected = next(row["expected"] for row in _manifest() if row["file"] == fixture)
    root = _root(tmp_path)
    path = _copy(root, fixture)
    info = read_elf(path, MAX_BYTES)
    for key in ("kind", "machine", "static", "nx", "pie", "relro", "canary"):
        assert getattr(info, key) == expected[key]
    result = _extract(root)
    features = result.features
    assert features["unpacked_n_elf"] == 1
    assert features["unpacked_n_elf_exec"] == int(expected["kind"] == "exec")
    assert features["unpacked_n_elf_lib"] == int(expected["kind"] == "lib")
    assert features["unpacked_n_elf_static"] == int(expected["static"])
    assert features["unpacked_prop_nx"] == float(expected["nx"])
    assert features["unpacked_prop_pie"] == (
        float(expected["pie"]) if expected["kind"] == "exec" else None
    )
    for relro in ("full", "partial"):
        assert features[f"unpacked_prop_relro_{relro}"] == float(
            expected["relro"] == relro
        )
    assert features["unpacked_prop_canary"] == (
        None if expected["static"] else float(expected["canary"])
    )


def test_pie_proportion_uses_only_executables(tmp_path: Path) -> None:
    """Divide o número de executáveis PIE pelos executáveis lidos."""
    root = _root(tmp_path)
    _copy(root, "exec_hardened")
    _copy(root, "exec_partial")
    assert _extract(root).features["unpacked_prop_pie"] == 0.5


@pytest.mark.parametrize(
    "tags,expected",
    [
        ([("DT_BIND_NOW", 0)], True),
        ([("DT_FLAGS", 0x8)], True),
        ([("DT_FLAGS_1", 0x1)], True),
        ([("DT_FLAGS", 0x2)], False),
        ([], False),
    ],
)
def test_bind_now_tags(tags: list[tuple[str, int]], expected: bool) -> None:
    """Reconhece as três formas de resolução imediata das tags."""
    assert bind_now(tags) is expected


def test_malformed_elf_does_not_stop_batch(tmp_path: Path) -> None:
    """Mantém contagem de ELF único e exclui o malformado das proporções."""
    root = _root(tmp_path)
    _copy(root, "truncated_elf")
    _copy(root, "exec_hardened")
    result = _extract(root)
    assert result.metadata["fs_status"] == "ok"
    assert result.metadata["fs_elf_malformed"] == 1
    assert result.features["unpacked_n_elf"] == 2
    assert result.features["unpacked_n_elf_exec"] == 1
    assert result.features["unpacked_prop_pie"] == 1.0
    assert result.features["unpacked_prop_nx"] == 1.0


def test_max_bytes_rejects_oversized_elf(tmp_path: Path) -> None:
    """Classifica ELF acima do limite como malformado sem tentar parsear."""
    root = _root(tmp_path)
    _copy(root, "exec_hardened")
    result = _extract(root, 4)
    assert result.features["unpacked_n_elf"] == 1
    assert result.features["unpacked_n_elf_exec"] == 0
    assert result.metadata["fs_elf_malformed"] == 1


def test_object_is_other_and_not_in_proportions(tmp_path: Path) -> None:
    """Inclui objeto relocável no inventário, não nas proporções."""
    root = _root(tmp_path)
    _copy(root, "obj_rel.o", "mod.ko")
    result = _extract(root)
    assert [result.features[key] for key in UNPACKED_COLUMNS[1:5]] == [1, 0, 0, 0]
    assert all(result.features[key] is None for key in UNPACKED_COLUMNS[5:])
    assert result.metadata["fs_arch"] == "EM_X86_64"


def test_no_elf_has_zero_counts_and_null_proportions(tmp_path: Path) -> None:
    """Mantém contagens zero e proporções ausentes quando só há texto."""
    root = _root(tmp_path)
    (root / "config").write_text("text")
    result = _extract(root)
    assert result.metadata["fs_status"] == "ok"
    assert result.metadata["fs_arch"] is None
    assert [result.features[key] for key in UNPACKED_COLUMNS[:5]] == [1, 0, 0, 0, 0]
    assert all(result.features[key] is None for key in UNPACKED_COLUMNS[5:])


def test_only_library_has_no_pie_denominator(tmp_path: Path) -> None:
    """Não atribui PIE sem executável, mesmo havendo biblioteca."""
    root = _root(tmp_path)
    _copy(root, "lib_hardened.so")
    result = _extract(root)
    assert result.features["unpacked_prop_pie"] is None
    assert result.features["unpacked_prop_nx"] == 1.0


def test_library_with_dt_debug_is_not_executable(tmp_path: Path) -> None:
    """Mantém DT_DEBUG de biblioteca fora do denominador de PIE."""
    root = _root(tmp_path)
    _copy(root, "lib_dtdebug.so")
    result = _extract(root)
    assert result.features["unpacked_n_elf_lib"] == 1
    assert result.features["unpacked_n_elf_exec"] == 0
    assert result.features["unpacked_prop_pie"] is None


@pytest.mark.parametrize(
    "fixtures,arch",
    [
        (["mips_be_static", "exec_hardened", "exec_partial"], "EM_X86_64"),
        (["mips_be_static", "exec_hardened"], "EM_MIPS"),
    ],
)
def test_architecture_frequency_and_lexical_tie(
    tmp_path: Path, fixtures: list[str], arch: str
) -> None:
    """Escolhe arquitetura modal, desempata pela menor string."""
    root = _root(tmp_path)
    for fixture in fixtures:
        _copy(root, fixture)
    assert _extract(root).metadata["fs_arch"] == arch


def test_walk_error_marks_all_columns_unavailable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Preserva erro de leitura do percurso e não publica zeros falsos."""
    root = _root(tmp_path)

    def fail(_root: Path) -> list[Path]:
        """Simula falha na enumeração de arquivos extraídos."""
        raise OSError("boom")

    monkeypatch.setattr(filesystem_module, "iter_extracted_files", fail)
    result = _extract(root)
    assert result.metadata["fs_status"] == "erro"
    assert "boom" in result.metadata["fs_error"]
    assert result.metadata["fs_elf_malformed"] is None
    assert result.metadata["fs_arch"] is None
    assert all(result.features[key] is None for key in UNPACKED_COLUMNS)


def test_unavailable_has_null_columns_and_metadata() -> None:
    """Marca filesystem não executado sem alegar observação de ELF."""
    result = unavailable_filesystem()
    assert result.metadata == {
        "fs_status": "nao_executado",
        "fs_error": None,
        "fs_elf_malformed": None,
        "fs_arch": None,
    }
    assert all(result.features[key] is None for key in UNPACKED_COLUMNS)
