"""Valida identidade apenas sobre paths relativos de três segmentos."""

from pathlib import Path

import pytest

from pipeline.feature_extraction import (
    THIRD_PARTY_DDWRT,
    VERSION_SOURCE_DIRECTORY,
    VERSION_SOURCE_FILENAME,
    find_off_layout_paths,
    infer_brand_model_label_from_path,
    is_third_party_name,
    relative_to_root,
)


@pytest.mark.parametrize(
    "path,brand,model,version,source",
    [
        (
            "zyxel/NWA110AX_7.10(ABTG.4)C0/file.bin",
            "zyxel",
            "nwa110ax",
            "7.10(ABTG.4)C0",
            VERSION_SOURCE_DIRECTORY,
        ),
        ("dlink/dir-300/file.bin", "dlink", "dir-300", None, None),
        (
            "belkin/f5d7234_4/f5d7234-4_ww_4.00.05.bin",
            "belkin",
            "f5d7234_4",
            "4.00.05",
            VERSION_SOURCE_FILENAME,
        ),
        (
            "asus/rt-ac68u/RT-AC68U_3.0.0.4_384_45717-gadd52a8.trx",
            "asus",
            "rt-ac68u",
            "3.0.0.4.384.45717",
            VERSION_SOURCE_FILENAME,
        ),
        (
            "dlink/dsr1000n_1.2/DSR-1000N_FW_9.99_WW",
            "dlink",
            "dsr1000n",
            "1.2",
            VERSION_SOURCE_DIRECTORY,
        ),
        ("dlink/dir-1760/DIR_1760_FW101B04.BIN", "dlink", "dir-1760", None, None),
    ],
)
def test_infer_relative_identity(
    path: str, brand: str, model: str, version: str | None, source: str | None
) -> None:
    """Preserva precedência de versão e rejeita inferências ambíguas."""
    identity = infer_brand_model_label_from_path(Path(path))
    assert (
        identity.brand,
        identity.model,
        identity.label,
        identity.version,
        identity.version_source,
    ) == (brand, model, f"{brand}_{model}", version, source)


@pytest.mark.parametrize(
    "path",
    [
        "dlink/file.bin",
        "dlink/model/folder/file.bin",
        "dataset/raw/dlink/model/file.bin",
        "/tmp/dlink/model/file.bin",
    ],
)
def test_invalid_relative_layout_has_no_identity(path: str) -> None:
    """Recusa componente ausente, pasta extra e path absoluto."""
    assert infer_brand_model_label_from_path(Path(path)) == (
        None,
        None,
        None,
        None,
        None,
    )


def test_relative_to_root_uses_actual_root_and_rejects_escape(tmp_path: Path) -> None:
    """Não utiliza o primeiro segmento raw de um path ancestral."""
    root = tmp_path / "raw" / "project" / "dataset" / "raw"
    root.mkdir(parents=True)
    inside = root / "dlink" / "dir300" / "fw.bin"
    outside = tmp_path / "raw" / "outside.bin"
    assert relative_to_root(inside, root) == Path("dlink/dir300/fw.bin")
    assert relative_to_root(outside, root) is None
    assert find_off_layout_paths(
        [inside, root / "dlink" / "loose.bin", outside], root
    ) == [root / "dlink" / "loose.bin", outside]


def test_webflash_only_removes_version_from_name() -> None:
    """Marca DD-WRT pelo nome sem descartar identidade do modelo."""
    identity = infer_brand_model_label_from_path(
        Path("tp_link/tl-wr710v1_1.2/tl-wr710v1-WEBFLASH.bin")
    )
    assert identity.label == "tp_link_tl-wr710v1"
    assert (identity.version, identity.version_source) == (None, None)
    assert is_third_party_name("TL-WR710V1-webflash.bin")
    assert THIRD_PARTY_DDWRT == "dd-wrt"
    assert not is_third_party_name("OpenWrt-official.bin")
