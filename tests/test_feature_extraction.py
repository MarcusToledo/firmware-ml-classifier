from __future__ import annotations

from pathlib import Path

from pipeline.feature_extraction import infer_brand_model_label_from_path


def test_infer_path_strips_version_suffix() -> None:
    """Zyxel-style version suffixes should be stripped at extraction time,
    but the raw version must be preserved, not discarded."""
    path = Path("dataset/raw/zyxel/NWA110AX_7.10(ABTG.4)C0/file.bin")
    metadata = infer_brand_model_label_from_path(path)
    assert metadata.brand == "zyxel"
    assert metadata.model == "nwa110ax"
    assert metadata.label == "zyxel_nwa110ax"
    assert metadata.version == "7.10(ABTG.4)C0"
    assert metadata.version_source == "directory"


def test_infer_path_preserves_normal_model() -> None:
    """Normal model names without version suffix should be preserved, and
    have no extractable version."""
    path = Path("dataset/raw/dlink/dir-300/file.bin")
    metadata = infer_brand_model_label_from_path(path)
    assert metadata.brand == "dlink"
    assert metadata.model == "dir-300"
    assert metadata.label == "dlink_dir-300"
    assert metadata.version is None
    assert metadata.version_source is None


def test_infer_path_no_raw_segment_returns_all_none() -> None:
    path = Path("some/other/dir/file.bin")
    assert infer_brand_model_label_from_path(path) == (
        None,
        None,
        None,
        None,
        None,
    )


def test_infer_path_version_suffix_with_simple_digits() -> None:
    """A simpler version suffix ('dsr1000n_1.2') should also split cleanly."""
    path = Path("dataset/raw/dlink/dsr1000n_1.2/file.bin")
    metadata = infer_brand_model_label_from_path(path)
    assert metadata.brand == "dlink"
    assert metadata.model == "dsr1000n"
    assert metadata.version == "1.2"
    assert metadata.version_source == "directory"


def test_infer_path_directory_version_with_hyphenated_model() -> None:
    path = Path("dataset/raw/asus/rt-ac68u_3.0.0.4/file.bin")
    metadata = infer_brand_model_label_from_path(path)
    assert metadata.model == "rt-ac68u"
    assert metadata.version == "3.0.0.4"
    assert metadata.version_source == "directory"


def test_infer_path_hardware_revision_suffix_is_part_of_model() -> None:
    """Belkin 'f5d7234_4' e o modelo F5D7234-4 (hardware v4), nao versao 4."""
    path = Path("dataset/raw/belkin/f5d7234_4/f5d7234-4_ww_4.00.05.bin")
    metadata = infer_brand_model_label_from_path(path)
    assert metadata.model == "f5d7234_4"
    assert metadata.version_source != "directory"


def test_infer_path_falls_back_to_version_in_filename() -> None:
    """Diretorio sem versao: a versao vem do nome do arquivo."""
    path = Path("dataset/raw/asus/rt-ac68u/RT-AC68U_3.0.0.4_384_45717-gadd52a8.trx")
    metadata = infer_brand_model_label_from_path(path)
    assert (metadata.brand, metadata.model, metadata.label) == (
        "asus",
        "rt-ac68u",
        "asus_rt-ac68u",
    )
    assert metadata.version == "3.0.0.4.384.45717"
    assert metadata.version_source == "filename"


def test_infer_path_directory_version_wins_over_filename() -> None:
    """A versao do diretorio tem prioridade sobre a do nome do arquivo."""
    path = Path("dataset/raw/dlink/dsr1000n_1.2/DSR-1000N_FW_9.99_WW")
    metadata = infer_brand_model_label_from_path(path)
    assert metadata.model == "dsr1000n"
    assert metadata.version == "1.2"
    assert metadata.version_source == "directory"


def test_infer_path_ambiguous_filename_has_no_version() -> None:
    path = Path("dataset/raw/dlink/dir-1760/DIR_1760_FW101B04.BIN")
    metadata = infer_brand_model_label_from_path(path)
    assert metadata.version is None
    assert metadata.version_source is None
