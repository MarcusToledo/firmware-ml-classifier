"""Exercita limites, limpeza, ferramentas e symlinks do desempacotamento."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from src.features.unpack import (
    Toolchain,
    ToolchainError,
    UnpackLimits,
    iter_extracted_files,
    resolve_toolchain,
    unpack_firmware,
)


def _script_toolchain(tmp_path: Path, body: str) -> Toolchain:
    """Cria extrator shell controlado para exercitar o monitor de limites."""
    path = tmp_path / "unpacker"
    path.write_text("#!/bin/sh\n" + body)
    path.chmod(0o755)
    return Toolchain(str(path), dict(os.environ), {"binwalk": "fake"})


@pytest.mark.parametrize(
    "body,limits,status",
    [
        (
            'while [ "$1" != "-C" ]; do shift; done; shift; '
            'mkdir -p "$1/squashfs-root"; '
            'printf "%020d" 0 > "$1/squashfs-root/file"\n',
            UnpackLimits(10, 1, 5),
            "limite_tamanho",
        ),
        (
            'while [ "$1" != "-C" ]; do shift; done; shift; '
            'mkdir -p "$1/squashfs-root"; '
            'touch "$1/squashfs-root/a" "$1/squashfs-root/b"\n',
            UnpackLimits(100, 1, 5),
            "limite_arquivos",
        ),
        (
            'while [ "$1" != "-C" ]; do shift; done; shift; '
            'mkdir -p "$1/squashfs-root"; '
            'printf "%020d" 0 > "$1/squashfs-root/a"; '
            'printf "%020d" 0 > "$1/squashfs-root/b"\n',
            UnpackLimits(10, 1, 5),
            "limite_tamanho",
        ),
        ("sleep 3\n", UnpackLimits(100, 10, 0.1), "limite_tempo"),
        ("exit 3\n", UnpackLimits(100, 10, 5), "falha"),
        (
            'while [ "$1" != "-C" ]; do shift; done; shift; echo hello > "$1/raw"\n',
            UnpackLimits(100, 10, 5),
            "sem_filesystem",
        ),
    ],
)
def test_unpack_status_and_cleanup(
    tmp_path: Path, body: str, limits: UnpackLimits, status: str
) -> None:
    """Registra cada estado e remove o diretório temporário após consumo."""
    toolchain = _script_toolchain(tmp_path, body)
    with unpack_firmware(tmp_path / "firmware.bin", limits, toolchain) as result:
        assert result.status == status
        assert result.root is None
    assert not any(Path("/tmp").glob("fmc-unpack-*"))


def test_isolated_environment_and_symlinks(tmp_path: Path) -> None:
    """Confina HOME/TMPDIR e não percorre links para fora do diretório."""
    body = (
        'while [ "$1" != "-C" ]; do shift; done; shift; '
        'mkdir -p "$1/squashfs-root"; printf marker > "$1/squashfs-root/valid"; '
        'ln -s /etc/passwd "$1/squashfs-root/escape"; '
        'ln -s /etc "$1/squashfs-root/outside"; '
        'echo "$HOME:$TMPDIR" > "$1/squashfs-root/environment"\n'
    )
    with unpack_firmware(
        tmp_path / "firmware.bin",
        UnpackLimits(1000, 10, 5),
        _script_toolchain(tmp_path, body),
    ) as result:
        assert result.status == "ok" and result.root is not None
        paths = iter_extracted_files(result.root)
        assert {path.name for path in paths} == {"valid", "environment"}
        home, tmp = (
            next(path for path in paths if path.name == "environment")
            .read_text()
            .strip()
            .split(":")
        )
        assert Path(home).parent == result.root.parent
        assert Path(tmp).parent == result.root.parent
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
        assert result.status == "ok" and result.root is not None
        content = b"".join(
            path.read_bytes() for path in iter_extracted_files(result.root)
        )
        assert b"FMC_MARKER" in content
        assert b"root:x:0:0" not in content
