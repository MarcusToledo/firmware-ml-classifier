from __future__ import annotations

from src.feature_extraction import FeatureConfig, extract_features


def test_extract_features_exposes_limited_strings() -> None:
    """FeatureVector.strings expoe a lista ja limitada a max_strings.

    Isso permite que o pipeline reutilize essa lista (scan_strings) em vez
    de rodar extract_ascii_strings de novo sobre os mesmos bytes.
    """
    data = b"HELLO\x00WORLD\x00AB"
    config = FeatureConfig(
        min_string_len=4, max_string_len=1024, max_strings=1, max_doc_chars=1000
    )

    result = extract_features(data, config, model=None)

    assert result.strings == ["HELLO"]


def test_extract_features_strings_empty_for_empty_data() -> None:
    config = FeatureConfig()

    result = extract_features(b"", config, model=None)

    assert result.strings == []
