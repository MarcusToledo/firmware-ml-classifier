from pathlib import Path

from pipeline.feature_extraction import load_pipeline_config


def test_load_pipeline_config_defaults(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text("")

    config = load_pipeline_config(config_path, overrides={})

    assert config.max_bytes is None
    assert config.feature.min_string_len == 4
    assert config.feature.max_string_len == 1024
    assert config.feature.max_strings == 2000
    assert config.feature.max_doc_chars == 200000
    assert config.doc2vec.vector_size == 100


def test_load_pipeline_config_with_overrides(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text("")

    overrides = {
        "max_bytes": "1024",
        "feature.max_single_string_len": "64",
        "doc2vec.seed": "123",
    }

    config = load_pipeline_config(config_path, overrides=overrides)

    assert config.max_bytes == 1024
    assert config.feature.max_string_len == 64
    assert config.doc2vec.seed == 123


def test_override_nested_doc2vec(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text("doc2vec:\n  vector_size: 50\n  window: 2\n  seed: 42\n")

    overrides = {"doc2vec.window": "7"}

    config = load_pipeline_config(config_path, overrides=overrides)

    assert config.doc2vec.vector_size == 50
    assert config.doc2vec.window == 7


def test_null_model_path(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text("doc2vec:\n  model_path: null\n")

    config = load_pipeline_config(config_path, overrides={})

    assert config.doc2vec_model_path is None
