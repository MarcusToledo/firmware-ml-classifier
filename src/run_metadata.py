"""Funções de proveniência para artefatos de execução."""

from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def file_sha256(path: Path) -> str:
    """Calcula o SHA256 do arquivo lendo blocos de 64 KiB."""
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _git_output(repo: Path, *args: str) -> str:
    """Executa um comando git no repositório e retorna a saída padrão."""
    return subprocess.run(
        ["git", *args],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
    ).stdout


def code_commit(repo: Path = REPO_ROOT) -> str:
    """Retorna o SHA do HEAD, com sufixo -dirty se houver arquivo rastreado modificado.

    Levanta RuntimeError quando o git não responde.
    """
    try:
        sha = _git_output(repo, "rev-parse", "HEAD").strip()
        status = _git_output(repo, "status", "--porcelain", "--untracked-files=no")
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        raise RuntimeError(
            f"Não foi possível obter o commit do código em {repo}: {exc}"
        ) from exc
    return f"{sha}-dirty" if status else sha
