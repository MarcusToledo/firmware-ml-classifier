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
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

LOGGER = logging.getLogger(__name__)
STATUS_OK = "ok"
STATUS_NO_FILESYSTEM = "sem_filesystem"
STATUS_FAILURE = "falha"
STATUS_SIZE = "limite_tamanho"
STATUS_FILES = "limite_arquivos"
STATUS_TIME = "limite_tempo"
STATUS_NOT_RUN = "nao_executado"
_ROOT_RE = re.compile(r"^[a-z0-9]+-root(-\d+)?$")
# A tag upstream v2.3.4 aponta para cddfede, mas setup.py mantém 2.3.3.
_BINWALK_V234_COMMIT = "cddfede"
_REQUIRED_TOOLS = (
    (
        "binwalk",
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

    max_total_bytes: int = 2_147_483_648
    max_files: int = 100_000
    timeout_seconds: float = 300


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
            timeout=15,
            env=env,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ToolchainError(
            f"{binary}: versão desconhecida; mínimo exigido: ferramenta funcional"
        ) from exc
    match = re.search(pattern, result.stdout + result.stderr, re.IGNORECASE | re.DOTALL)
    if match is None:
        return "desconhecida"
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
    env["PATH"] = f"{Path(sys.executable).parent}{os.pathsep}{os.environ['PATH']}"
    versions: dict[str, str] = {}
    paths: dict[str, str] = {}
    for name, pattern, minimum, args, package in _REQUIRED_TOOLS:
        binary = shutil.which(name, path=env["PATH"])
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
            name == "binwalk"
            and version == "2.3.3"
            and commit.startswith(_BINWALK_V234_COMMIT)
        )
        if (
            minimum
            and not tagged
            and (
                found == "desconhecida"
                or tuple(map(int, version.split(".")))
                < tuple(map(int, minimum.split(".")))
            )
        ):
            raise ToolchainError(f"{name}: versão {found}; mínimo exigido: {minimum}")
        paths[name] = binary
        versions[name] = found
    return Toolchain(paths["binwalk"], env, versions)


def _inventory(root: Path) -> tuple[int, int, bool, bool]:
    """Conta entradas sem seguir links e identifica raízes extraídas válidas."""
    total = count = 0
    regular = filesystem = False
    stack = [(root, False)]
    while stack:
        directory, in_root = stack.pop()
        with os.scandir(directory) as entries:
            for entry in entries:
                info = entry.stat(follow_symlinks=False)
                if stat.S_ISDIR(info.st_mode):
                    stack.append(
                        (
                            Path(entry.path),
                            in_root or bool(_ROOT_RE.fullmatch(entry.name)),
                        )
                    )
                else:
                    count += 1
                    if stat.S_ISREG(info.st_mode):
                        total += info.st_size
                        regular = True
                        filesystem |= in_root
    return total, count, regular, filesystem


def _stop_process(process: subprocess.Popen[bytes]) -> None:
    """Mata o grupo inteiro do extrator, inclusive subprocessos remanescentes."""
    if process.poll() is None:
        os.killpg(process.pid, signal.SIGKILL)
    process.wait()


def _monitor(
    process: subprocess.Popen[bytes], root: Path, limits: UnpackLimits, started: float
) -> str:
    """Verifica limites periodicamente e novamente após a saída do extrator."""
    while True:
        total, count, _, _ = _inventory(root)
        status = (
            STATUS_SIZE
            if total > limits.max_total_bytes
            else (
                STATUS_FILES
                if count > limits.max_files
                else (
                    STATUS_TIME
                    if time.monotonic() - started > limits.timeout_seconds
                    else None
                )
            )
        )
        if status:
            _stop_process(process)
            return status
        if process.poll() is not None:
            return STATUS_OK
        time.sleep(0.5)


def _cleanup_error(func: object, name: str, exc: object) -> None:
    """Tenta novamente a remoção de diretórios tornados somente leitura."""
    os.chmod(name, stat.S_IRWXU)
    func(name)


@contextmanager
def unpack_firmware(
    path: Path, limits: UnpackLimits, toolchain: Toolchain
) -> Iterator[UnpackResult]:
    """Executa binwalk isolado e remove todo o diretório após o consumo."""
    base = Path(tempfile.mkdtemp(prefix="fmc-unpack-"))
    home, tmp, out = (base / part for part in ("home", "tmp", "out"))
    for directory in (home, tmp, out):
        directory.mkdir()
    stderr_path = base / "binwalk.stderr"
    process: subprocess.Popen[bytes] | None = None
    try:
        with stderr_path.open("wb") as stderr:
            try:
                started = time.monotonic()
                process = subprocess.Popen(
                    [toolchain.binwalk, "-e", "-q", "-C", str(out), str(path)],
                    cwd=base,
                    env={**toolchain.env, "HOME": str(home), "TMPDIR": str(tmp)},
                    stdout=subprocess.DEVNULL,
                    stderr=stderr,
                    start_new_session=True,
                )
                status = _monitor(process, out, limits, started)
                _, _, regular, filesystem = _inventory(out)
                if status == STATUS_OK:
                    status = (
                        STATUS_FAILURE
                        if process.returncode != 0 or not regular
                        else STATUS_OK if filesystem else STATUS_NO_FILESYSTEM
                    )
                error = (
                    stderr_path.read_bytes()[-2048:].decode("utf-8", errors="replace")
                    if status == STATUS_FAILURE
                    else None
                )
            except OSError as exc:
                status, error = STATUS_FAILURE, str(exc)
            finally:
                if process is not None and process.poll() is None:
                    _stop_process(process)
        yield UnpackResult(status, out if status == STATUS_OK else None, error)
    finally:
        try:
            shutil.rmtree(base, onerror=_cleanup_error)
        except OSError as exc:
            LOGGER.error("Falha ao limpar extração de %s em %s: %s", path, base, exc)


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
