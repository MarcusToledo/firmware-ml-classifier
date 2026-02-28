from __future__ import annotations

from pathlib import Path

from pipeline.feature_extraction import infer_brand_model_label_from_path


def test_infer_path_strips_version_suffix() -> None:
    """Zyxel-style version suffixes should be stripped at extraction time."""
    path = Path("dataset/raw/zyxel/NWA110AX_7.10(ABTG.4)C0/file.bin")
    brand, model, label = infer_brand_model_label_from_path(path)
    assert brand == "zyxel"
    assert model == "nwa110ax"
    assert label == "zyxel_nwa110ax"


def test_infer_path_preserves_normal_model() -> None:
    """Normal model names without version suffix should be preserved."""
    path = Path("dataset/raw/dlink/dir-300/file.bin")
    brand, model, label = infer_brand_model_label_from_path(path)
    assert brand == "dlink"
    assert model == "dir-300"
    assert label == "dlink_dir-300"
