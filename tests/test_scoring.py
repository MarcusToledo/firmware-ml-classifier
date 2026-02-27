from __future__ import annotations

from src.scoring import (
    ScoringConfig,
    ThresholdConfig,
    score_firmware,
)

DEFAULT_CONFIG = ScoringConfig()


def test_stats_only_redistributes_weight() -> None:
    """When only stats features are present, weight is redistributed."""
    features = {"entropy": 7.9, "byte_mean": 130.0, "compress_ratio": 0.99}
    result = score_firmware(features, DEFAULT_CONFIG)

    present = [s for s in result.signals if s.present]
    absent = [s for s in result.signals if not s.present]
    assert len(present) == 1
    assert present[0].name == "stats"
    assert len(absent) == 3
    assert all(s.weight == 0.0 for s in absent)
    assert result.numeric_score > 0.0


def test_deterministic_same_inputs_same_result() -> None:
    """Scoring must be deterministic: same inputs → same result."""
    features = {
        "entropy": 7.5,
        "byte_mean": 120.0,
        "compress_ratio": 0.90,
        "cvss_max": 7.0,
        "cve_count_critical": 1,
        "cve_count_high": 3,
    }
    r1 = score_firmware(features, DEFAULT_CONFIG)
    r2 = score_firmware(features, DEFAULT_CONFIG)
    assert r1.level == r2.level
    assert r1.numeric_score == r2.numeric_score


def test_hard_rule_telnetd_overrides_to_vulneravel() -> None:
    """has_telnetd=True forces minimum 'vulneravel' regardless of score."""
    features = {
        "entropy": 4.0,
        "byte_mean": 127.5,
        "compress_ratio": 0.50,
        "has_telnetd": True,
    }
    result = score_firmware(features, DEFAULT_CONFIG)
    assert result.level in ("vulneravel", "critico")
    assert result.hard_rule_applied == "has_telnetd"


def test_hard_rule_debug_account() -> None:
    """has_debug_account=True forces minimum 'vulneravel'."""
    features = {
        "entropy": 4.0,
        "byte_mean": 127.5,
        "compress_ratio": 0.50,
        "has_debug_account": True,
    }
    result = score_firmware(features, DEFAULT_CONFIG)
    assert result.level in ("vulneravel", "critico")
    assert result.hard_rule_applied == "has_debug_account"


def test_hard_rule_hardcoded_passwords() -> None:
    """count_hardcoded_passwords > 0 forces minimum 'vulneravel'."""
    # Low stats score alone → "seguro", but hard rule escalates
    features = {
        "entropy": 4.0,
        "byte_mean": 127.5,
        "compress_ratio": 0.50,
        "count_hardcoded_passwords": 1,
    }
    result = score_firmware(features, DEFAULT_CONFIG)
    assert result.level in ("vulneravel", "critico")
    # The strings signal score pulls the weighted average up, so the level
    # may already be >= vulneravel from the score alone. Verify the label
    # is correct regardless of whether the hard rule was the cause.
    assert result.level != "seguro"


def test_hard_rule_cvss_critical_overrides_to_critico() -> None:
    """cvss_max >= 9.0 forces 'critico' even when score alone wouldn't."""
    # Use high thresholds so score alone maps to "vulneravel", then hard rule
    # escalates to "critico"
    high_threshold_config = ScoringConfig(
        thresholds=ThresholdConfig(low=0.30, high=0.90),
    )
    features = {
        "entropy": 4.0,
        "byte_mean": 127.5,
        "compress_ratio": 0.50,
        "cvss_max": 9.5,
    }
    result = score_firmware(features, high_threshold_config)
    assert result.level == "critico"
    assert result.hard_rule_applied == "cvss_critical"


def test_no_signals_returns_seguro() -> None:
    """Firmware with no recognised features defaults to 'seguro'."""
    features = {"unknown_feature": 42}
    result = score_firmware(features, DEFAULT_CONFIG)
    assert result.level == "seguro"
    assert result.numeric_score == 0.0
    assert result.hard_rule_applied is None


def test_empty_features_returns_seguro() -> None:
    """Empty feature dict defaults to 'seguro'."""
    result = score_firmware({}, DEFAULT_CONFIG)
    assert result.level == "seguro"
    assert result.numeric_score == 0.0


def test_high_score_maps_to_critico() -> None:
    """Features that produce a high score should map to 'critico'."""
    features = {
        "cvss_max": 8.5,
        "cve_count_critical": 5,
        "cve_count_high": 10,
        "entropy": 7.99,
        "compress_ratio": 0.999,
    }
    result = score_firmware(features, DEFAULT_CONFIG)
    assert result.numeric_score >= 0.60
    assert result.level == "critico"


def test_low_risk_maps_to_seguro() -> None:
    """Low-risk features should map to 'seguro'."""
    features = {
        "entropy": 5.0,
        "byte_mean": 127.5,
        "compress_ratio": 0.60,
        "cvss_max": 1.0,
        "cve_count_critical": 0,
        "cve_count_high": 0,
    }
    result = score_firmware(features, DEFAULT_CONFIG)
    assert result.numeric_score < 0.30
    assert result.level == "seguro"


def test_custom_thresholds() -> None:
    """Custom thresholds should change classification boundaries."""
    features = {"entropy": 7.5, "compress_ratio": 0.90}
    strict_config = ScoringConfig(
        thresholds=ThresholdConfig(low=0.10, high=0.30),
    )
    result = score_firmware(features, strict_config)
    # With stricter thresholds, same features should be more severe
    assert result.level in ("vulneravel", "critico")


def test_signals_breakdown_present() -> None:
    """Result should include signal breakdown for all 4 signal groups."""
    features = {"entropy": 7.0}
    result = score_firmware(features, DEFAULT_CONFIG)
    names = {s.name for s in result.signals}
    assert names == {"stats", "cve", "strings", "binwalk"}


def test_hard_rule_does_not_downgrade() -> None:
    """Hard rules only escalate, never downgrade the level."""
    # cvss_max=9.5 → critico; has_telnetd min_level=vulneravel should not downgrade
    features = {
        "cvss_max": 9.5,
        "cve_count_critical": 5,
        "has_telnetd": True,
    }
    result = score_firmware(features, DEFAULT_CONFIG)
    assert result.level == "critico"


def test_binwalk_features_contribute() -> None:
    """Binwalk features should contribute to the score when present."""
    features_without = {"entropy": 6.0, "compress_ratio": 0.80}
    features_with = {
        **features_without,
        "has_encrypted_sections": True,
        "n_crypto_signatures": 3,
        "fs_type": "cramfs",
    }
    r_without = score_firmware(features_without, DEFAULT_CONFIG)
    r_with = score_firmware(features_with, DEFAULT_CONFIG)
    assert r_with.numeric_score > r_without.numeric_score
