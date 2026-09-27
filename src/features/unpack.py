"""Resolve ferramentas e isola o desempacotamento de firmwares não confiáveis."""

from __future__ import annotations

import importlib.metadata
import logging
import os
import re
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import time
from collections.abc import Iterator
from contextlib import contextmanager, suppress
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

LOGGER = logging.getLogger(__name__)
STATUS_OK = "ok"
STATUS_NO_FILESYSTEM = "sem_filesystem"
STATUS_FAILURE = "falha"
STATUS_SIZE = "limite_tamanho"
STATUS_FILES = "limite_arquivos"
STATUS_TIME = "limite_tempo"
STATUS_NOT_RUN = "nao_executado"
_DEFAULT_MAX_TOTAL_BYTES = 2_147_483_648
_DEFAULT_MAX_FILES = 100_000
_DEFAULT_TIMEOUT_SECONDS = 300
_TOOL_VERSION_TIMEOUT_SECONDS = 15
_MONITOR_INTERVAL_SECONDS = 0.5
_STDERR_TAIL_BYTES = 2048
_BINWALK_TOOL = "binwalk"
_UNKNOWN_VERSION = "desconhecida"
_ENV_PATH = "PATH"
_SANDBOX_HOME = "home"
_SANDBOX_TMP = "tmp"
_SANDBOX_OUT = "out"
_ROOT_RE = re.compile(r"^[a-z0-9]+-root(-\d+)?$")
# A tag upstream v2.3.4 aponta para cddfede, mas setup.py mantém 2.3.3.
_BINWALK_V234_COMMIT = "cddfede"
_REQUIRED_TOOLS = (
    (
        _BINWALK_TOOL,
        "Binwalk v(\\d+\\.\\d+\\.\\d+)(?:\\+([0-9a-f]+))?",
        "2.3.4",
        ("--help",),
        None,
    ),
    ("unsquashfs", "version (\\d+\\.\\d+)", "4.5", ("-version",), None),
    ("sasquatch", "version (\\d+\\.\\d+)", None, ("-version",), None),
    ("jefferson", None, "0.4.1", (), "jefferson"),
    ("ubireader_extract_files", None, "0.8.5", (), "ubi-reader"),
    ("7z", "7-Zip.*?(\\d+\\.\\d+)", "16.02", (), None),
)


class ToolchainError(RuntimeError):
    """Informa ferramenta ausente, inadequada ou execução privilegiada."""


@dataclass(frozen=True)
class Toolchain:
    """Guarda executável principal, ambiente isolado e versões conferidas."""

    binwalk: str
    env: dict[str, str]
    versions: dict[str, str]


@dataclass(frozen=True)
class UnpackLimits:
    """Limita bytes, quantidade de arquivos e tempo do extrator."""

    max_total_bytes: int = _DEFAULT_MAX_TOTAL_BYTES
    max_files: int = _DEFAULT_MAX_FILES
    timeout_seconds: float = _DEFAULT_TIMEOUT_SECONDS


@dataclass(frozen=True)
class UnpackResult:
    """Representa o status e a raiz temporária acessível dentro do contexto."""

    status: str
    root: Path | None
    error: str | None = None


def _tool_version(
    binary: str,
    pattern: str | None,
    args: tuple[str, ...],
    package: str | None,
    env: dict[str, str],
) -> str:
    """Consulta a versão instalada sem ocultar falhas de execução."""
    if package:
        return importlib.metadata.version(package)
    assert pattern is not None
    try:
        result = subprocess.run(
            [binary, *args],
            capture_output=True,
            text=True,
            timeout=_TOOL_VERSION_TIMEOUT_SECONDS,
            env=env,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ToolchainError(
            f"{binary}: versão desconhecida; mínimo exigido: ferramenta funcional"
        ) from exc
    match = re.search(pattern, result.stdout + result.stderr, re.IGNORECASE | re.DOTALL)
    if match is None:
        return _UNKNOWN_VERSION
    return match.group(1) + (
        f"+{match.group(2)}"
        if package is None and match.lastindex == 2 and match.group(2)
        else ""
    )


def resolve_toolchain() -> Toolchain:
    """Exige extratores instalados em versões seguras e usuário sem root."""
    if os.geteuid() == 0:
        raise ToolchainError(
            "root: versão atual privilegiada; mínimo exigido: usuário sem root"
        )
    env = dict(os.environ)
    env[_ENV_PATH] = f"{Path(sys.executable).parent}{os.pathsep}{os.environ[_ENV_PATH]}"
    versions: dict[str, str] = {}
    paths: dict[str, str] = {}
    for name, pattern, minimum, args, package in _REQUIRED_TOOLS:
        binary = shutil.which(name, path=env[_ENV_PATH])
        if binary is None:
            raise ToolchainError(
                f"{name}: versão ausente; mínimo exigido: {minimum or 'presença'}"
            )
        try:
            found = _tool_version(binary, pattern, args, package, env)
        except importlib.metadata.PackageNotFoundError as exc:
            raise ToolchainError(
                f"{name}: versão ausente; mínimo exigido: {minimum}"
            ) from exc
        version, _, commit = found.partition("+")
        tagged = (
            name == _BINWALK_TOOL
            and version == "2.3.3"
            and commit.startswith(_BINWALK_V234_COMMIT)
        )
        if (
            minimum
            and not tagged
            and (
                found == _UNKNOWN_VERSION
                or tuple(map(int, version.split(".")))
                < tuple(map(int, minimum.split(".")))
            )
        ):
            raise ToolchainError(f"{name}: versão {found}; mínimo exigido: {minimum}")
        paths[name] = binary
        versions[name] = found
    return Toolchain(paths[_BINWALK_TOOL], env, versions)


def _scan_entries(directory: Path, strict: bool) -> list[os.DirEntry[str]]:
    """Lista um diretório; fora do modo estrito tolera entrada sumida ou fechada.

    Durante a extração o binwalk cria, apaga e renomeia arquivos, então
    ``FileNotFoundError`` e ``PermissionError`` só são erro depois que o
    processo terminou e as permissões foram normalizadas.
    """
    try:
        with os.scandir(directory) as entries:
            return list(entries)
    except (FileNotFoundError, PermissionError):
        if strict:
            raise
        return []


def _inventory(root: Path, strict: bool) -> tuple[int, int, bool, bool]:
    """Conta entradas sem seguir links e identifica raízes extraídas válidas."""
    total = count = 0
    regular = filesystem = False
    stack = [(root, False)]
    while stack:
        directory, in_root = stack.pop()
        for entry in _scan_entries(directory, strict):
            try:
                info = entry.stat(follow_symlinks=False)
            except (FileNotFoundError, PermissionError):
                if strict:
                    raise
                continue
            if stat.S_ISDIR(info.st_mode):
                nested = in_root or bool(_ROOT_RE.fullmatch(entry.name))
                stack.append((Path(entry.path), nested))
                continue
            count += 1
            if stat.S_ISREG(info.st_mode):
                total += info.st_size
                regular = True
                filesystem |= in_root
    return total, count, regular, filesystem


def _grant_owner_access(root: Path) -> None:
    """Dá rwx ao dono em cada diretório real sob ``root``, de cima para baixo.

    Só roda com o grupo do extrator já morto: cada alvo foi conferido por
    ``lstat`` como diretório real e o caminho até ele só tem diretórios reais,
    então o ``chmod`` nunca atravessa symlink para fora da sandbox.
    """
    stack = [root]
    while stack:
        directory = stack.pop()
        os.chmod(directory, stat.S_IRWXU)
        with os.scandir(directory) as entries:
            stack.extend(
                Path(entry.path)
                for entry in entries
                if entry.is_dir(follow_symlinks=False)
            )


def _stop_process(process: subprocess.Popen[bytes]) -> None:
    """Mata o grupo inteiro do extrator, inclusive órfãos de um líder já morto."""
    with suppress(ProcessLookupError):
        os.killpg(process.pid, signal.SIGKILL)
    process.wait()


def _limit_status(
    total: int, count: int, elapsed: float, limits: UnpackLimits
) -> str | None:
    """Devolve o primeiro limite estourado: tamanho, arquivos e depois tempo."""
    if total > limits.max_total_bytes:
        return STATUS_SIZE
    if count > limits.max_files:
        return STATUS_FILES
    if elapsed > limits.timeout_seconds:
        return STATUS_TIME
    return None


def _monitor(
    process: subprocess.Popen[bytes], root: Path, limits: UnpackLimits, started: float
) -> str | None:
    """Confere limites periodicamente e uma última vez após o extrator."""
    while True:
        finished = process.poll() is not None
        total, count, _, _ = _inventory(root, strict=False)
        status = _limit_status(total, count, time.monotonic() - started, limits)
        if status or finished:
            return status
        time.sleep(_MONITOR_INTERVAL_SECONDS)


def _final_status(
    process: subprocess.Popen[bytes], out: Path, limits: UnpackLimits
) -> str:
    """Classifica a saída completa depois de normalizar as permissões."""
    _grant_owner_access(out)
    total, count, regular, filesystem = _inventory(out, strict=True)
    limit = _limit_status(total, count, 0.0, limits)
    if limit:
        return limit
    if process.returncode != 0 or not regular:
        return STATUS_FAILURE
    return STATUS_OK if filesystem else STATUS_NO_FILESYSTEM


def _stderr_tail(handle: BinaryIO) -> str:
    """Lê só a janela final do stderr pelo descritor já aberto."""
    size = handle.seek(0, os.SEEK_END)
    handle.seek(max(0, size - _STDERR_TAIL_BYTES))
    return handle.read().decode("utf-8", errors="replace")


def isolated_env(toolchain: Toolchain, home: Path, tmp: Path) -> dict[str, str]:
    """Monta o ambiente do binwalk sem configuração, plugins nem magic do usuário."""
    return {
        **toolchain.env,
        "HOME": str(home),
        "XDG_CONFIG_HOME": str(home / ".config"),
        "TMPDIR": str(tmp),
    }


def _run_extractor(
    path: Path, base: Path, limits: UnpackLimits, toolchain: Toolchain
) -> tuple[str, str | None]:
    """Roda ``binwalk -e`` confinado em ``base`` e devolve status e erro."""
    out = base / _SANDBOX_OUT
    with (base / "binwalk.stderr").open("w+b") as stderr:
        try:
            started = time.monotonic()
            process = subprocess.Popen(
                [toolchain.binwalk, "-e", "-q", "-C", str(out), str(path.absolute())],
                cwd=base,
                env=isolated_env(toolchain, base / _SANDBOX_HOME, base / _SANDBOX_TMP),
                stdout=subprocess.DEVNULL,
                stderr=stderr,
                start_new_session=True,
            )
        except OSError as exc:
            return STATUS_FAILURE, str(exc)
        try:
            status = _monitor(process, out, limits, started)
        finally:
            _stop_process(process)
        status = status or _final_status(process, out, limits)
        error = _stderr_tail(stderr) if status == STATUS_FAILURE else None
    return status, error


def _remove_sandbox(path: Path, base: Path) -> None:
    """Remove a sandbox inteira; falha de limpeza é registrada, não propagada."""
    try:
        _grant_owner_access(base)
        shutil.rmtree(base)
    except OSError as exc:
        LOGGER.error("Falha ao limpar extração de %s em %s: %s", path, base, exc)


@contextmanager
def unpack_firmware(
    path: Path, limits: UnpackLimits, toolchain: Toolchain
) -> Iterator[UnpackResult]:
    """Executa binwalk isolado e remove todo o diretório após o consumo.

    ``root`` só é válido dentro do ``with``; ao sair, o grupo do extrator já
    está morto e o diretório temporário é apagado.
    """
    base = Path(tempfile.mkdtemp(prefix="fmc-unpack-"))
    try:
        for part in (_SANDBOX_HOME, _SANDBOX_TMP, _SANDBOX_OUT):
            (base / part).mkdir()
        try:
            status, error = _run_extractor(path, base, limits, toolchain)
        except OSError as exc:
            status, error = STATUS_FAILURE, str(exc)
        root = base / _SANDBOX_OUT if status == STATUS_OK else None
        yield UnpackResult(status, root, error)
    finally:
        _remove_sandbox(path, base)


def iter_extracted_files(root: Path) -> list[Path]:
    """Ordena arquivos regulares extraídos sem seguir nenhum symlink."""
    files: list[Path] = []
    stack = [root]
    while stack:
        directory = stack.pop()
        with os.scandir(directory) as entries:
            for entry in entries:
                if entry.is_dir(follow_symlinks=False):
                    stack.append(Path(entry.path))
                elif entry.is_file(follow_symlinks=False):
                    files.append(Path(entry.path))
    return sorted(files, key=lambda path: path.relative_to(root).as_posix())
