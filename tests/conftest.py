"""Disponibiliza ferramentas simuladas e marca verificações reais opcionais."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from src.features.unpack import Toolchain, ToolchainError, resolve_toolchain


def pytest_configure(config: pytest.Config) -> None:
    """Registra marcador para testes que exigem todos os extratores reais."""
    config.addinivalue_line(
        "markers", "requires_unpack_tools: exige binwalk, sasquatch e demais extratores"
    )


@pytest.fixture
def fake_toolchain(tmp_path: Path) -> Toolchain:
    """Executa shell que produz rootfs com marcador e saída de assinatura."""
    script = tmp_path / "binwalk"
    script.write_text(
        "#!/bin/sh\n"
        'case "$1" in\n'
        '  -e) while [ "$1" != "-C" ]; do shift; done; shift; '
        'mkdir -p "$1/_firmware.bin.extracted/squashfs-root"; '
        'printf "password=secret\\n" > '
        '"$1/_firmware.bin.extracted/squashfs-root/config";;\n'
        '  *) printf "0 0 Squashfs filesystem\\n";;\n'
        "esac\n"
    )
    script.chmod(0o755)
    return Toolchain(str(script), dict(os.environ), {"binwalk": "fake"})


@pytest.fixture
def require_unpack_tools() -> Toolchain:
    """Ignora o cenário real com justificativa quando faltar ferramenta."""
    try:
        return resolve_toolchain()
    except ToolchainError as exc:
        pytest.skip(str(exc))
