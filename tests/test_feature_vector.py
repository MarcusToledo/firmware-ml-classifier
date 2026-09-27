"""Confere composição de features sem retenção das strings brutas."""

from src.feature_extraction import FeatureConfig, combine_features, extract_features
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
    assert features["doc2vec_0"] == 0
    assert not hasattr(result, "strings")
