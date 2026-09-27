"""Exercita leitura, fallback, estado e identidade em lote."""

from __future__ import annotations

import hashlib
import tracemalloc
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import pytest

from pipeline.feature_extraction import (
    extract_features_batch,
    extract_features_from_path,
    load_pipeline_config,
)
from src.features.unpack import Toolchain, UnpackResult


def test_full_read_and_filesystem_strings(
    tmp_path: Path, fake_toolchain: Toolchain
) -> None:
    """Lê arquivo inteiro para hash/estatísticas e varre strings do rootfs."""
    path = tmp_path / "firmware.bin"
    path.write_bytes(b"header\x00OpenWrt\x00")
    result = extract_features_from_path(
        path, load_pipeline_config(None, {}), None, fake_toolchain
    )
    assert result.firmware_id == hashlib.sha256(path.read_bytes()).hexdigest()
    assert (
        result.metadata["file_size"]
        == result.metadata["bytes_used"]
        == path.stat().st_size
    )
    assert result.metadata["binwalk_status"] == "ok"
    assert result.metadata["unpack_status"] == "ok"
    assert result.metadata["strings_source"] == "filesystem"
    assert result.metadata["third_party"] is None
    assert result.features["count_hardcoded_passwords"] >= 1
    assert result.features["n_filesystems"] == 1


def test_empty_and_unreadable_skip_tools(
    tmp_path: Path, fake_toolchain: Toolchain
) -> None:
    """Mantém linha de falha e status não executado em leitura impossível."""
    empty = tmp_path / "empty.bin"
    empty.touch()
    missing = tmp_path / "missing.bin"
    results = extract_features_batch(
        [empty, missing], load_pipeline_config(None, {}), fake_toolchain, max_workers=1
    )
    assert [result.metadata["error"] for result in results] == [
        "empty firmware",
        str(FileNotFoundError(2, "No such file or directory", str(missing))),
    ] or results[1].metadata["error"].startswith("[Errno 2]")
    assert all(
        result.metadata["binwalk_status"] == "nao_executado" for result in results
    )
    assert all(
        result.metadata["strings_source"] == "nao_executado" for result in results
    )
    assert all(
        result.metadata["file_size"] is None or result.metadata["file_size"] == 0
        for result in results
    )


def test_batch_preserves_relative_identity_and_order(
    tmp_path: Path, fake_toolchain: Toolchain
) -> None:
    """Mantém ordem e versão inferida relativa à raiz também com workers."""
    root = tmp_path / "dataset" / "raw"
    paths = [
        root / "netgear" / "r6250" / "R6250-V1.0.1.80_1.0.75.chk",
        root / "dlink" / "dir-300" / "fw.bin",
    ]
    for path in paths:
        path.parent.mkdir(parents=True)
        path.write_bytes(b"firmware\x00")
    results = extract_features_batch(
        paths,
        load_pipeline_config(None, {}),
        fake_toolchain,
        max_workers=2,
        dataset_root=root,
    )
    assert [result.metadata["path"] for result in results] == [
        "netgear/r6250/R6250-V1.0.1.80_1.0.75.chk",
        "dlink/dir-300/fw.bin",
    ]
    assert results[0].metadata["version"] == "1.0.1.80"
    assert results[1].metadata["brand"] == "dlink"


@pytest.mark.parametrize(
    "status,source",
    [
        ("sem_filesystem", "blob"),
        ("falha", "blob"),
        ("limite_tamanho", "blob"),
        ("limite_arquivos", "blob"),
        ("limite_tempo", "nao_executado"),
    ],
)
def test_unpack_fallback_or_timeout(
    tmp_path: Path,
    fake_toolchain: Toolchain,
    monkeypatch: pytest.MonkeyPatch,
    status: str,
    source: str,
) -> None:
    """Só faz fallback sobre blob quando não houve limite de tempo."""
    import pipeline.feature_extraction as pipeline

    path = tmp_path / "firmware.bin"
    path.write_bytes(b"password=secret\x00DD-WRT\x00")

    @contextmanager
    def unpack(
        _path: Path, _limits: object, _toolchain: Toolchain
    ) -> Iterator[UnpackResult]:
        """Reproduz o status reportado pelo monitor real."""
        yield UnpackResult(status, None)

    monkeypatch.setattr(pipeline, "unpack_firmware", unpack)
    result = extract_features_from_path(
        path, load_pipeline_config(None, {}), None, fake_toolchain
    )
    assert result.metadata["unpack_status"] == status
    assert result.metadata["strings_source"] == source
    assert result.metadata["third_party"] == ("dd-wrt" if source == "blob" else None)
    if source == "blob":
        assert result.features["count_hardcoded_passwords"] >= 1
    else:
        assert result.features["count_hardcoded_passwords"] == 0


def test_webflash_name_removes_version_but_banner_does_not(
    tmp_path: Path, fake_toolchain: Toolchain, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Marca terceiros sem apagar versão inferida quando só o banner aparece."""
    import pipeline.feature_extraction as pipeline

    @contextmanager
    def unpack(
        _path: Path, _limits: object, _toolchain: Toolchain
    ) -> Iterator[UnpackResult]:
        """Indica que a imagem exige fallback às strings brutas."""
        yield UnpackResult("sem_filesystem", None)

    monkeypatch.setattr(pipeline, "unpack_firmware", unpack)
    root = tmp_path / "raw"
    for name, content, expected_version, expected_third in [
        ("WNDR4300-V1.0.1.30.img", b"OpenWrt\x00", "1.0.1.30", None),
        ("WNDR4300-V1.0.1.31.img", b"DD-WRT\x00", "1.0.1.31", "dd-wrt"),
        ("WNDR4300-webflash.img", b"firmware\x00", None, "dd-wrt"),
    ]:
        path = root / "netgear" / "wndr4300" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        result = extract_features_batch(
            [path],
            load_pipeline_config(None, {}),
            fake_toolchain,
            max_workers=1,
            dataset_root=root,
        )[0]
        assert result.metadata["version"] == expected_version
        assert result.metadata["third_party"] == expected_third


def test_bounded_peak_for_large_file(
    tmp_path: Path, fake_toolchain: Toolchain, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Lê 64 MiB sem reter os bytes da imagem em memória."""
    import pipeline.feature_extraction as pipeline

    @contextmanager
    def unpack(
        _path: Path, _limits: object, _toolchain: Toolchain
    ) -> Iterator[UnpackResult]:
        """Evita strings do blob para medir apenas a leitura incremental."""
        yield UnpackResult("limite_tempo", None)

    monkeypatch.setattr(pipeline, "unpack_firmware", unpack)
    monkeypatch.setattr(pipeline, "_scan_binwalk", lambda path, tool: ([], "ok"))
    path = tmp_path / "large.bin"
    with path.open("wb") as handle:
        for _ in range(64):
            handle.write(b"\x00" * (1 << 20))
    tracemalloc.start()
    result = extract_features_from_path(
        path, load_pipeline_config(None, {}), None, fake_toolchain
    )
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    assert result.metadata["bytes_used"] == 64 << 20
    assert peak < 32 << 20
