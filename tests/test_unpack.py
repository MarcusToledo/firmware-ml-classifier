"""Exercita limites, limpeza, ferramentas e symlinks do desempacotamento."""

from __future__ import annotations

import os
import stat
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any

import pytest

import src.features.unpack as unpack_module
from src.features.unpack import (
    STATUS_FAILURE,
    STATUS_FILES,
    STATUS_NO_FILESYSTEM,
    STATUS_OK,
    STATUS_SIZE,
    STATUS_TIME,
    Toolchain,
    ToolchainError,
    UnpackLimits,
    iter_extracted_files,
    resolve_toolchain,
    unpack_firmware,
)

_EXTRACT_DIR = 'while [ "$1" != "-C" ]; do shift; done; shift; '


def _script_toolchain(tmp_path: Path, body: str) -> Toolchain:
    """Cria extrator shell controlado para exercitar o monitor de limites."""
    path = tmp_path / "unpacker"
    path.write_text("#!/bin/sh\n" + body)
    path.chmod(0o755)
    return Toolchain(str(path), dict(os.environ), {"binwalk": "fake"})


@pytest.fixture
def sandboxes(monkeypatch: pytest.MonkeyPatch) -> list[Path]:
    """Registra cada diretório temporário criado por ``unpack_firmware``."""
    created: list[Path] = []
    original = tempfile.mkdtemp

    def mkdtemp(*args: Any, **kwargs: Any) -> str:
        """Cria o diretório e guarda o path para conferir a limpeza."""
        path = original(*args, **kwargs)
        created.append(Path(path))
        return path

    monkeypatch.setattr(unpack_module.tempfile, "mkdtemp", mkdtemp)
    return created


@pytest.mark.parametrize(
    "body,limits,status",
    [
        (
            'while [ "$1" != "-C" ]; do shift; done; shift; '
            'mkdir -p "$1/squashfs-root"; '
            'printf "%020d" 0 > "$1/squashfs-root/file"\n',
            UnpackLimits(10, 1, 5),
            STATUS_SIZE,
        ),
        (
            'while [ "$1" != "-C" ]; do shift; done; shift; '
            'mkdir -p "$1/squashfs-root"; '
            'touch "$1/squashfs-root/a" "$1/squashfs-root/b"\n',
            UnpackLimits(100, 1, 5),
            STATUS_FILES,
        ),
        (
            'while [ "$1" != "-C" ]; do shift; done; shift; '
            'mkdir -p "$1/squashfs-root"; '
            'printf "%020d" 0 > "$1/squashfs-root/a"; '
            'printf "%020d" 0 > "$1/squashfs-root/b"\n',
            UnpackLimits(10, 1, 5),
            STATUS_SIZE,
        ),
        ("sleep 3\n", UnpackLimits(100, 10, 0.1), STATUS_TIME),
        (
            _EXTRACT_DIR
            + 'sleep 0.2; mkdir -p "$1/squashfs-root"; '
            + 'echo x > "$1/squashfs-root/f"\n',
            UnpackLimits(1000, 10, 0.4),
            STATUS_OK,
        ),
        ("exit 3\n", UnpackLimits(100, 10, 5), STATUS_FAILURE),
        (
            'while [ "$1" != "-C" ]; do shift; done; shift; echo hello > "$1/raw"\n',
            UnpackLimits(100, 10, 5),
            STATUS_NO_FILESYSTEM,
        ),
    ],
)
def test_unpack_status_and_cleanup(
    tmp_path: Path,
    sandboxes: list[Path],
    body: str,
    limits: UnpackLimits,
    status: str,
) -> None:
    """Registra cada estado e remove o diretório temporário após consumo."""
    toolchain = _script_toolchain(tmp_path, body)
    with unpack_firmware(tmp_path / "firmware.bin", limits, toolchain) as result:
        assert result.status == status
        assert (result.root is None) == (status != STATUS_OK)
    assert len(sandboxes) == 1
    assert not sandboxes[0].exists()


def test_restricted_dirs_are_read_and_removed_without_touching_link_targets(
    tmp_path: Path, sandboxes: list[Path]
) -> None:
    """Lê diretórios 000 e 400, remove diretório 555 e não muda o alvo de symlink."""
    victim = tmp_path / "victim"
    victim.write_text("outside")
    victim.chmod(0o644)
    body = (
        _EXTRACT_DIR + 'r="$1/squashfs-root"; mkdir -p "$r/ro" "$r/zz"; '
        f'ln -s {victim} "$r/ro/l"; echo inner > "$r/ro/f"; '
        'echo hidden > "$r/zz/secret"; chmod 555 "$r/ro"; chmod 000 "$r/zz"; '
        'mkdir "$r/zr"; echo g > "$r/zr/g"; chmod 400 "$r/zr"\n'
    )
    with unpack_firmware(
        tmp_path / "firmware.bin",
        UnpackLimits(1000, 10, 5),
        _script_toolchain(tmp_path, body),
    ) as result:
        assert result.status == STATUS_OK and result.root is not None
        names = {path.name for path in iter_extracted_files(result.root)}
        assert names == {"f", "secret", "g"}
    assert stat.S_IMODE(victim.stat().st_mode) == 0o644
    assert not sandboxes[0].exists()


def test_replaced_output_symlink_does_not_change_victim(
    tmp_path: Path, sandboxes: list[Path]
) -> None:
    """Rejeita raiz substituída sem modificar diretório externo."""
    victim = tmp_path / "victim"
    victim.mkdir()
    file = victim / "keep"
    file.write_text("outside")
    victim.chmod(0o555)
    body = _EXTRACT_DIR + f'rmdir "$1"; ln -s "{victim}" "$1"\n'
    with unpack_firmware(
        tmp_path / "firmware.bin",
        UnpackLimits(1000, 10, 5),
        _script_toolchain(tmp_path, body),
    ) as result:
        assert result.status == STATUS_FAILURE
        assert result.root is None
    assert stat.S_IMODE(victim.stat().st_mode) == 0o555
    assert file.exists()
    assert not sandboxes[0].exists()


def test_files_vanishing_during_extraction_do_not_fail(tmp_path: Path) -> None:
    """Tolera entradas apagadas pelo extrator enquanto o monitor varre."""
    body = (
        _EXTRACT_DIR + "i=0; while [ $i -lt 400 ]; do "
        'mkdir -p "$1/t/a/b"; touch "$1/t/a/b/x"; rm -rf "$1/t"; i=$((i+1)); done; '
        'mkdir -p "$1/squashfs-root"; echo ok > "$1/squashfs-root/f"\n'
    )
    toolchain = _script_toolchain(tmp_path, body)
    for _ in range(3):
        with unpack_firmware(
            tmp_path / "firmware.bin", UnpackLimits(1000, 10, 30), toolchain
        ) as result:
            assert result.status == STATUS_OK


def test_orphans_are_killed_and_body_exception_still_cleans(
    tmp_path: Path, sandboxes: list[Path]
) -> None:
    """Mata filhos de um líder já encerrado e limpa mesmo com erro no corpo."""
    body = (
        _EXTRACT_DIR + 'mkdir -p "$1/squashfs-root"; echo x > "$1/squashfs-root/f"; '
        '(sleep 1; mkdir "$1/late") & exit 0\n'
    )
    with pytest.raises(RuntimeError, match="consumidor"):
        with unpack_firmware(
            tmp_path / "firmware.bin",
            UnpackLimits(1000, 10, 5),
            _script_toolchain(tmp_path, body),
        ):
            raise RuntimeError("consumidor")
    time.sleep(1.5)
    assert not sandboxes[0].exists()


def test_isolated_environment_and_symlinks(tmp_path: Path) -> None:
    """Confina HOME/TMPDIR e não percorre links para fora do diretório."""
    body = (
        'while [ "$1" != "-C" ]; do shift; done; shift; '
        'mkdir -p "$1/squashfs-root"; printf marker > "$1/squashfs-root/valid"; '
        'ln -s /etc/passwd "$1/squashfs-root/escape"; '
        'ln -s /etc "$1/squashfs-root/outside"; '
        'echo "$HOME:$TMPDIR:$XDG_CONFIG_HOME" > "$1/squashfs-root/environment"\n'
    )
    with unpack_firmware(
        tmp_path / "firmware.bin",
        UnpackLimits(1000, 10, 5),
        _script_toolchain(tmp_path, body),
    ) as result:
        assert result.status == STATUS_OK and result.root is not None
        paths = iter_extracted_files(result.root)
        assert {path.name for path in paths} == {"valid", "environment"}
        home, tmp, xdg = (
            next(path for path in paths if path.name == "environment")
            .read_text()
            .strip()
            .split(":")
        )
        assert Path(home).parent == result.root.parent
        assert Path(tmp).parent == result.root.parent
        assert Path(xdg).parent == Path(home)
    assert not Path(home).exists()


def test_binwalk_tag_commit_is_accepted_but_other_old_versions_fail(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Aceita apenas o commit oficial da tag que reporta 2.3.3 erroneamente."""
    import src.features.unpack as unpack

    monkeypatch.setattr(unpack.os, "geteuid", lambda: 1000)
    monkeypatch.setattr(unpack.shutil, "which", lambda name, path: "/usr/bin/" + name)
    versions = {
        "binwalk": "2.3.4",
        "unsquashfs": "4.5",
        "sasquatch": "desconhecida",
        "jefferson": "0.4.8",
        "ubireader_extract_files": "0.8.16",
        "7z": "16.02",
    }
    monkeypatch.setattr(
        unpack,
        "_tool_version",
        lambda binary, pattern, args, package, env: versions[Path(binary).name],
    )
    assert resolve_toolchain().versions["binwalk"] == "2.3.4"
    versions["binwalk"] = "2.3.3+cddfede"
    assert resolve_toolchain().versions["binwalk"] == "2.3.3+cddfede"
    for old in ("2.3.3", "2.3.3+abc1234"):
        versions["binwalk"] = old
        with pytest.raises(ToolchainError, match="binwalk: versão"):
            resolve_toolchain()


@pytest.mark.requires_unpack_tools
def test_real_squashfs_symlinks_are_not_read(
    tmp_path: Path, require_unpack_tools: Toolchain
) -> None:
    """Desempacota squashfs real sem seguir links para passwd ou /etc."""
    source = tmp_path / "source"
    source.mkdir()
    (source / "marker").write_text("FMC_MARKER")
    (source / "p").symlink_to("/etc/passwd")
    (source / "up").symlink_to("../../../../etc")
    image = tmp_path / "firmware.squashfs"
    subprocess.run(
        ["mksquashfs", str(source), str(image), "-noappend"],
        check=True,
        capture_output=True,
    )
    with unpack_firmware(image, UnpackLimits(), require_unpack_tools) as result:
        assert result.status == STATUS_OK and result.root is not None
        content = b"".join(
            path.read_bytes() for path in iter_extracted_files(result.root)
        )
        assert b"FMC_MARKER" in content
        assert b"root:x:0:0" not in content
