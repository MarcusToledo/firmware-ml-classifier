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
    assert "hardcoded_passwords" in {finding.detector for finding in result.findings}


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
        assert result.metadata["binwalk_status"] == "nao_executado"
        assert result.metadata["unpack_status"] == "nao_executado"
        assert result.metadata["strings_source"] == "nao_executado"


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
    ) == ("dlink", "dsr1000n", "1.2", "directory")


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


@pytest.mark.parametrize("version,source", [("1.0", None), (None, "filename")])
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
        yield UnpackResult("sem_filesystem", None)

    monkeypatch.setattr(pipeline, "unpack_firmware", unpack)
    monkeypatch.setattr(
        pipeline, "_scan_binwalk", lambda path, tool: (["CramFS filesystem"], "ok")
    )
    result = extract_features_from_path(
        path, load_pipeline_config(None, {}), None, fake_toolchain
    )
    assert result.features["fs_type"] == "cramfs"
    assert result.metadata["unpack_status"] == "falha"
    assert result.metadata["strings_source"] == "blob"


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
    monkeypatch.setattr(pipeline, "_scan_binwalk", lambda path, tool: ([], "ok"))
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
        yield UnpackResult("sem_filesystem", None)

    monkeypatch.setattr(pipeline, "unpack_firmware", unpack)
    monkeypatch.setattr(pipeline, "_scan_binwalk", lambda path, tool: ([], "ok"))
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
