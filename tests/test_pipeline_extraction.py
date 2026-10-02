"""Exercita leitura, fallback, estado e identidade em lote."""

from __future__ import annotations

import hashlib
import logging
import os
import time
import tracemalloc
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import pytest

from pipeline.feature_extraction import (
    STRINGS_BLOB,
    STRINGS_FILESYSTEM,
    THIRD_PARTY_DDWRT,
    VERSION_SOURCE_DIRECTORY,
    VERSION_SOURCE_FILENAME,
    extract_features_batch,
    extract_features_from_path,
    load_pipeline_config,
)
from src.features.filesystem import UNPACKED_COLUMNS
from src.features.unpack import (
    STATUS_ENCRYPTED,
    STATUS_FAILURE,
    STATUS_FILES,
    STATUS_NO_FILESYSTEM,
    STATUS_NOT_RUN,
    STATUS_OK,
    STATUS_SIZE,
    STATUS_TIME,
    Toolchain,
    UnpackResult,
)


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
    assert result.metadata["binwalk_status"] == STATUS_OK
    assert result.metadata["unpack_status"] == STATUS_OK
    assert result.metadata["unpack_error"] is None
    assert result.metadata["strings_source"] == STRINGS_FILESYSTEM
    assert result.metadata["third_party"] is None
    assert result.features["count_hardcoded_passwords"] >= 1
    assert result.features["n_filesystems"] == 1
    assert "hardcoded_passwords" in {finding.detector for finding in result.findings}
    assert set(UNPACKED_COLUMNS) <= result.features.keys()
    assert result.features["unpacked_n_files"] == 1
    assert result.features["unpacked_n_elf"] == 0
    assert result.features["unpacked_prop_nx"] is None
    assert result.metadata["fs_status"] == "ok"
    assert result.metadata["fs_elf_malformed"] == 0
    assert result.metadata["fs_arch"] is None


def test_filesystem_error_keeps_row(
    tmp_path: Path, fake_toolchain: Toolchain, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Mantém strings e linha do firmware quando a leitura do fs falha."""
    import src.features.filesystem as filesystem

    def fail(_root: Path) -> Iterator[Path]:
        """Simula falha de E/S durante o percurso da árvore extraída."""
        raise OSError("boom")
        yield from ()

    monkeypatch.setattr(filesystem, "iter_extracted_files", fail)
    path = tmp_path / "firmware.bin"
    path.write_bytes(b"firmware-data\x00")
    result = extract_features_from_path(
        path, load_pipeline_config(None, {}), None, fake_toolchain
    )
    assert result.metadata["fs_status"] == "erro"
    assert "boom" in result.metadata["fs_error"]
    assert all(result.features[column] is None for column in UNPACKED_COLUMNS)
    assert result.features["count_hardcoded_passwords"] >= 1


def test_batch_logs_filesystem_summary(
    tmp_path: Path, fake_toolchain: Toolchain, caplog: pytest.LogCaptureFixture
) -> None:
    """Registra os totais do lote após processar o filesystem extraído."""

    path = tmp_path / "firmware.bin"
    path.write_bytes(b"firmware-data\x00")
    with caplog.at_level(logging.INFO, logger="pipeline.feature_extraction"):
        extract_features_batch(
            [path], load_pipeline_config(None, {}), fake_toolchain, max_workers=1
        )
    assert "1/1 firmwares com fs_status=ok" in caplog.text
    assert "malformados=0" in caplog.text
    assert "Status do unpack: {'ok': 1}" in caplog.text


def test_batch_logs_sorted_unpack_counts(
    tmp_path: Path, fake_toolchain: Toolchain, caplog: pytest.LogCaptureFixture
) -> None:
    """Contabiliza por status inclusive a linha de erro em ordem alfabética."""
    path = tmp_path / "firmware.bin"
    path.write_bytes(b"firmware-data\x00")
    with caplog.at_level(logging.INFO, logger="pipeline.feature_extraction"):
        extract_features_batch(
            [path, tmp_path / "missing.bin"],
            load_pipeline_config(None, {}),
            fake_toolchain,
            max_workers=1,
        )
    assert "Status do unpack: {'nao_executado': 1, 'ok': 1}" in caplog.text


def test_scan_timeout_kills_child_process(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Encerra também o filho da varredura quando excede o prazo."""
    import pipeline.feature_extraction as pipeline

    path = tmp_path / "firmware.bin"
    path.write_bytes(b"firmware\x00")
    marker = tmp_path / "orphan-marker"
    script = tmp_path / "binwalk"
    script.write_text(
        "#!/bin/sh\n"
        'case "$1" in\n'
        "  -e) exit 0;;\n"
        f'  *) (sleep 2; touch "{marker}") & sleep 10;;\n'
        "esac\n"
    )
    script.chmod(0o755)
    toolchain = Toolchain(str(script), dict(os.environ), {"binwalk": "fake"})
    monkeypatch.setattr(pipeline, "_BINWALK_SCAN_TIMEOUT_SECONDS", 1)
    result = extract_features_from_path(
        path, load_pipeline_config(None, {}), None, toolchain
    )
    assert result.metadata["binwalk_status"] == "timeout"
    time.sleep(2.5)
    assert not marker.exists()


def test_read_rejects_file_changed_during_stream(
    tmp_path: Path, fake_toolchain: Toolchain, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Registra erro quando a leitura termina antes do tamanho medido."""
    import pipeline.feature_extraction as pipeline

    path = tmp_path / "firmware.bin"
    path.write_bytes(b"0123456789")
    monkeypatch.setattr(
        pipeline, "iter_file_chunks", lambda path, limit, **kw: iter([b"abc"])
    )
    result = extract_features_from_path(
        path, load_pipeline_config(None, {}), None, fake_toolchain
    )
    assert result.metadata["read_ok"] is False
    assert "alterado durante a leitura" in result.metadata["error"]


def test_empty_and_unreadable_skip_tools(
    tmp_path: Path, fake_toolchain: Toolchain
) -> None:
    """Mantém linha de falha e status não executado em leitura impossível."""
    empty = tmp_path / "empty.bin"
    empty.touch()
    missing = tmp_path / "missing.bin"
    empty_result, missing_result = extract_features_batch(
        [empty, missing], load_pipeline_config(None, {}), fake_toolchain, max_workers=1
    )
    assert empty_result.metadata["error"] == "empty firmware"
    assert empty_result.metadata["file_size"] == 0
    assert missing_result.metadata["error"].startswith("[Errno 2]")
    assert missing_result.metadata["file_size"] is None
    for result in (empty_result, missing_result):
        assert result.metadata["read_ok"] is False
        assert result.firmware_id is None
        assert result.metadata["binwalk_status"] == STATUS_NOT_RUN
        assert result.metadata["unpack_status"] == STATUS_NOT_RUN
        assert result.metadata["unpack_error"] is None
        assert result.metadata["strings_source"] == STATUS_NOT_RUN
        assert result.metadata["fs_status"] == "nao_executado"
        assert result.metadata["fs_error"] is None
        assert result.metadata["fs_elf_malformed"] is None
        assert result.metadata["fs_arch"] is None


def test_error_row_keeps_identity_and_batch_continues(
    tmp_path: Path, fake_toolchain: Toolchain
) -> None:
    """Arquivo ilegível vira linha de erro com a identidade do path relativo."""
    root = tmp_path / "raw"
    good = root / "zyxel" / "NWA110AX_7.10(ABTG.4)C0" / "firmware.bin"
    good.parent.mkdir(parents=True)
    good.write_bytes(b"firmware-data\x00")
    missing = root / "dlink" / "dsr1000n_1.2" / "firmware.bin"
    good_result, missing_result = extract_features_batch(
        [good, missing],
        load_pipeline_config(None, {}),
        fake_toolchain,
        max_workers=1,
        dataset_root=root,
    )
    assert good_result.metadata["read_ok"] is True
    assert missing_result.metadata["read_ok"] is False
    assert missing_result.metadata["path"] == "dlink/dsr1000n_1.2/firmware.bin"
    assert (
        missing_result.metadata["brand"],
        missing_result.metadata["model"],
        missing_result.metadata["version"],
        missing_result.metadata["version_source"],
    ) == ("dlink", "dsr1000n", "1.2", VERSION_SOURCE_DIRECTORY)


def test_classifier_features_exclude_cve_and_identity_fields(
    tmp_path: Path, fake_toolchain: Toolchain
) -> None:
    """Identidade e campos de CVE ficam só nos metadados (constituição III)."""
    root = tmp_path / "raw"
    path = root / "zyxel" / "NWA110AX_7.10(ABTG.4)C0" / "firmware.bin"
    path.parent.mkdir(parents=True)
    path.write_bytes(b"firmware-data\x00")
    result = extract_features_batch(
        [path],
        load_pipeline_config(None, {}),
        fake_toolchain,
        max_workers=1,
        dataset_root=root,
    )[0]
    assert result.metadata["brand"] == "zyxel"
    assert result.metadata["version"] == "7.10(ABTG.4)C0"
    forbidden = {
        "cvss_max",
        "cve_total",
        "cve_count_critical",
        "cve_count_high",
        "cve_count_medium",
        "cve_count_low",
        "brand",
        "model",
        "label",
        "version",
        "version_source",
        "third_party",
        "path",
    }
    assert forbidden.isdisjoint(result.features)
    assert not any(key.startswith("meta_") for key in result.features)
    assert {key for key in result.features if key.startswith("unpacked_")} == set(
        UNPACKED_COLUMNS
    )
    assert "fs_arch" not in result.features


@pytest.mark.parametrize(
    "version,source", [("1.0", None), (None, VERSION_SOURCE_FILENAME)]
)
def test_inconsistent_version_metadata_is_rejected(
    tmp_path: Path,
    fake_toolchain: Toolchain,
    version: str | None,
    source: str | None,
) -> None:
    """Exige versão e origem juntas, citando o arquivo."""
    path = tmp_path / "firmware.bin"
    with pytest.raises(ValueError, match=str(path)):
        extract_features_from_path(
            path,
            load_pipeline_config(None, {}),
            None,
            fake_toolchain,
            version=version,
            version_source=source,
        )


def test_detected_filesystem_not_extracted_is_failure(
    tmp_path: Path, fake_toolchain: Toolchain, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Filesystem visto na varredura sem raiz extraída é falha, não ausência."""
    import pipeline.feature_extraction as pipeline

    path = tmp_path / "firmware.bin"
    path.write_bytes(b"password=secret\x00")

    @contextmanager
    def unpack(
        _path: Path, _limits: object, _toolchain: Toolchain
    ) -> Iterator[UnpackResult]:
        """Simula recorte cramfs mantido sem ``cramfsck``."""
        yield UnpackResult(STATUS_NO_FILESYSTEM, None)

    monkeypatch.setattr(pipeline, "unpack_firmware", unpack)
    monkeypatch.setattr(
        pipeline, "_scan_binwalk", lambda path, tool: (["CramFS filesystem"], STATUS_OK)
    )
    result = extract_features_from_path(
        path, load_pipeline_config(None, {}), None, fake_toolchain
    )
    assert result.features["fs_type"] == "cramfs"
    assert result.metadata["unpack_status"] == STATUS_FAILURE
    assert result.metadata["unpack_error"] == (
        "filesystem cramfs detectado e não extraído"
    )
    assert result.metadata["strings_source"] == STRINGS_BLOB


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
        (STATUS_NO_FILESYSTEM, STRINGS_BLOB),
        (STATUS_FAILURE, STRINGS_BLOB),
        (STATUS_ENCRYPTED, STRINGS_BLOB),
        (STATUS_SIZE, STRINGS_BLOB),
        (STATUS_FILES, STRINGS_BLOB),
        (STATUS_TIME, STATUS_NOT_RUN),
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
        error = "marcador de criptografia b'Salted__' no offset 116"
        yield UnpackResult(status, None, error if status == STATUS_ENCRYPTED else None)

    monkeypatch.setattr(pipeline, "unpack_firmware", unpack)
    monkeypatch.setattr(pipeline, "_scan_binwalk", lambda path, tool: ([], STATUS_OK))
    result = extract_features_from_path(
        path, load_pipeline_config(None, {}), None, fake_toolchain
    )
    assert result.metadata["unpack_status"] == status
    if status == STATUS_ENCRYPTED:
        assert result.metadata["unpack_error"] == (
            "marcador de criptografia b'Salted__' no offset 116"
        )
    elif status == STATUS_FAILURE:
        assert result.metadata["unpack_error"]
    else:
        assert result.metadata["unpack_error"] is None
    assert result.metadata["strings_source"] == source
    assert result.metadata["third_party"] == (
        THIRD_PARTY_DDWRT if source == STRINGS_BLOB else None
    )
    if source == STRINGS_BLOB:
        assert result.features["count_hardcoded_passwords"] >= 1
    else:
        assert result.features["count_hardcoded_passwords"] == 0
    assert all(result.features[column] is None for column in UNPACKED_COLUMNS)
    assert result.metadata["fs_status"] == "nao_executado"


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
        yield UnpackResult(STATUS_NO_FILESYSTEM, None)

    monkeypatch.setattr(pipeline, "unpack_firmware", unpack)
    root = tmp_path / "raw"
    for name, content, expected_version, expected_third in [
        ("WNDR4300-V1.0.1.30.img", b"OpenWrt\x00", "1.0.1.30", None),
        ("WNDR4300-V1.0.1.31.img", b"DD-WRT\x00", "1.0.1.31", THIRD_PARTY_DDWRT),
        ("WNDR4300-webflash.img", b"firmware\x00", None, THIRD_PARTY_DDWRT),
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
        yield UnpackResult(STATUS_TIME, None)

    monkeypatch.setattr(pipeline, "unpack_firmware", unpack)
    monkeypatch.setattr(pipeline, "_scan_binwalk", lambda path, tool: ([], STATUS_OK))
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


def test_bounded_peak_for_many_unique_strings(
    tmp_path: Path, fake_toolchain: Toolchain, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Strings únicas além do limite do documento não acumulam na memória."""
    import pipeline.feature_extraction as pipeline

    @contextmanager
    def unpack(
        _path: Path, _limits: object, _toolchain: Toolchain
    ) -> Iterator[UnpackResult]:
        """Força a varredura do blob inteiro."""
        yield UnpackResult(STATUS_NO_FILESYSTEM, None)

    monkeypatch.setattr(pipeline, "unpack_firmware", unpack)
    monkeypatch.setattr(pipeline, "_scan_binwalk", lambda path, tool: ([], STATUS_OK))
    path = tmp_path / "strings.bin"
    count = 300_000
    path.write_bytes(b"".join(b"u%07d\x00" % index for index in range(count)))
    config = load_pipeline_config(
        None, {"feature.max_strings": "100", "feature.max_doc_chars": "100000"}
    )
    tracemalloc.start()
    result = extract_features_from_path(path, config, None, fake_toolchain)
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    assert result.metadata["truncated"] is True
    assert peak < 16 << 20
