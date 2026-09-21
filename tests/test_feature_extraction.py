from __future__ import annotations

from pathlib import Path

from pipeline.feature_extraction import infer_brand_model_label_from_path


def test_infer_path_strips_version_suffix() -> None:
    """Zyxel-style version suffixes should be stripped at extraction time,
    but the raw version must be preserved, not discarded."""
    path = Path("dataset/raw/zyxel/NWA110AX_7.10(ABTG.4)C0/file.bin")
    brand, model, label, version = infer_brand_model_label_from_path(path)
    assert brand == "zyxel"
    assert model == "nwa110ax"
    assert label == "zyxel_nwa110ax"
    assert version == "7.10(ABTG.4)C0"


def test_infer_path_preserves_normal_model() -> None:
    """Normal model names without version suffix should be preserved, and
    have no extractable version."""
    path = Path("dataset/raw/dlink/dir-300/file.bin")
    brand, model, label, version = infer_brand_model_label_from_path(path)
    assert brand == "dlink"
    assert model == "dir-300"
    assert label == "dlink_dir-300"
    assert version is None


def test_infer_path_no_raw_segment_returns_all_none() -> None:
    path = Path("some/other/dir/file.bin")
    assert infer_brand_model_label_from_path(path) == (None, None, None, None)


def test_infer_path_version_suffix_with_simple_digits() -> None:
    """A simpler version suffix ('dsr1000n_1.2') should also split cleanly."""
    path = Path("dataset/raw/dlink/dsr1000n_1.2/file.bin")
    brand, model, label, version = infer_brand_model_label_from_path(path)
    assert brand == "dlink"
    assert model == "dsr1000n"
    assert version == "1.2"


def test_infer_path_falls_back_to_version_in_filename() -> None:
    """Diretorio sem versao: a versao vem do nome do arquivo."""
    path = Path("dataset/raw/asus/rt-ac68u/RT-AC68U_3.0.0.4_384_45717-gadd52a8.trx")
    brand, model, label, version = infer_brand_model_label_from_path(path)
    assert (brand, model, label) == ("asus", "rt-ac68u", "asus_rt-ac68u")
    assert version == "3.0.0.4.384.45717"


def test_infer_path_directory_version_wins_over_filename() -> None:
    """A versao do diretorio tem prioridade sobre a do nome do arquivo."""
    path = Path("dataset/raw/dlink/dsr1000n_1.2/DSR-1000N_FW_9.99_WW")
    _, model, _, version = infer_brand_model_label_from_path(path)
    assert model == "dsr1000n"
    assert version == "1.2"


def test_infer_path_ambiguous_filename_has_no_version() -> None:
    path = Path("dataset/raw/dlink/dir-1760/DIR_1760_FW101B04.BIN")
    assert infer_brand_model_label_from_path(path)[3] is None
