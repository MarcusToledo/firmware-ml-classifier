"""Confere composição de features sem retenção das strings brutas."""

from src.feature_extraction import FeatureConfig, combine_features, extract_features
from src.features.doc2vec import Doc2VecConfig
from src.features.statistics import StreamingStats


def test_vector_uses_precomputed_stats_and_document() -> None:
    """Preserva estatísticas, comprimento e truncamento já calculados."""
    collector = StreamingStats()
    collector.update(b"HELLO\x00WORLD")
    result = extract_features(
        collector.result(), "HELLO\nWORLD", True, 11, FeatureConfig(), None
    )
    features = combine_features(result)
    assert result.byte_len == 11
    assert result.truncated is True
    assert features["byte_mean"] > 0
    assert not any(key.startswith("doc2vec_") for key in features)
    assert not hasattr(result, "strings")


def test_vector_enabled_without_model_has_zero_embedding() -> None:
    """Ligado e sem modelo, emite exatamente ``vector_size`` colunas zeradas."""
    collector = StreamingStats()
    collector.update(b"HELLO\x00WORLD")
    config = FeatureConfig(doc2vec_enabled=True, doc2vec=Doc2VecConfig(vector_size=8))
    result = extract_features(collector.result(), "HELLO\nWORLD", True, 11, config)
    features = combine_features(result)
    columns = {key for key in features if key.startswith("doc2vec_")}
    assert columns == {f"doc2vec_{index}" for index in range(8)}
    assert all(features[column] == 0.0 for column in columns)
