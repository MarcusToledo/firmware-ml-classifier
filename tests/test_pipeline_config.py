"""Confere limites explícitos da configuração de extração."""

from pathlib import Path

import pytest

from pipeline.feature_extraction import DEFAULT_MAX_BYTES, load_pipeline_config


def test_config_without_yaml_uses_bounded_defaults() -> None:
    """Mantém limites também quando o chamador omite o YAML."""
    config = load_pipeline_config(None, {})
    assert config.max_bytes == DEFAULT_MAX_BYTES
    assert config.unpack.max_total_bytes == 2_147_483_648
    assert config.unpack.max_files == 100_000
    assert config.unpack.timeout_seconds == 300


def test_config_missing_path_is_not_silent(tmp_path: Path) -> None:
    """Rejeita configuração declarada mas ausente."""
    path = tmp_path / "missing.yaml"
    with pytest.raises(FileNotFoundError, match="--config não encontrado"):
        load_pipeline_config(path, {})


@pytest.mark.parametrize("value", [None, "null", "0", "-5", "1.5", "hello", True])
def test_invalid_max_bytes_rejected(value: object, tmp_path: Path) -> None:
    """Não aceita leitura ilimitada nem conversões que truncam valores."""
    path = tmp_path / "config.yaml"
    path.write_text("feature: {}\n")
    with pytest.raises(
        ValueError, match="max_bytes inválido.*DEVE ser inteiro positivo"
    ):
        load_pipeline_config(path, {"max_bytes": value})


def test_config_overrides_and_unpack_limits(tmp_path: Path) -> None:
    """Mantém configurações específicas sem alterar os padrões de outros campos."""
    path = tmp_path / "config.yaml"
    path.write_text("doc2vec:\n  vector_size: 50\n  model_path: null\n")
    config = load_pipeline_config(
        path,
        {
            "max_bytes": "1024",
            "feature.max_single_string_len": "64",
            "unpack.max_files": "10",
        },
    )
    assert config.max_bytes == 1024
    assert config.feature.max_string_len == 64
    assert config.doc2vec.vector_size == 50
    assert config.doc2vec_model_path is None
    assert config.unpack.max_files == 10


@pytest.mark.parametrize("key", ["max_total_bytes", "max_files", "timeout_seconds"])
def test_unpack_limits_must_be_positive(key: str) -> None:
    """Recusa cada limite desativado antes do processamento."""
    with pytest.raises(ValueError, match=f"unpack.{key}"):
        load_pipeline_config(None, {f"unpack.{key}": 0})
