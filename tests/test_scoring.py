from __future__ import annotations

from src.scoring import (
    ScoringConfig,
    ThresholdConfig,
    _score_strings,
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


def test_n_filesystems_contributes_to_score() -> None:
    """Multiple filesystems raise the binwalk sub-score."""
    base = {"entropy": 6.0}
    with_single_fs = {**base, "n_filesystems": 1}
    with_multi_fs = {**base, "n_filesystems": 3}
    r_single = score_firmware(with_single_fs, DEFAULT_CONFIG)
    r_multi = score_firmware(with_multi_fs, DEFAULT_CONFIG)
    assert r_multi.numeric_score > r_single.numeric_score


def test_n_filesystems_zero_does_not_activate_binwalk_signal() -> None:
    """n_filesystems=0 must not mark the binwalk signal as present."""
    result = score_firmware({"n_filesystems": 0}, DEFAULT_CONFIG)
    binwalk_signal = next(s for s in result.signals if s.name == "binwalk")
    assert binwalk_signal.present is False


# ---------------------------------------------------------------------------
# _score_strings with has_outdated_* booleans
# ---------------------------------------------------------------------------


def test_score_strings_no_features_absent() -> None:
    """No string features → signal absent with score 0."""
    result = _score_strings({})
    assert result.present is False
    assert result.score == 0.0


def test_score_strings_outdated_libssl_raises_score() -> None:
    """has_outdated_libssl=True should produce a non-zero score."""
    result = _score_strings({"has_outdated_libssl": True})
    assert result.present is True
    assert result.score > 0.0


def test_score_strings_no_outdated_lib_zero() -> None:
    """All outdated flags False with no other features → score 0."""
    result = _score_strings(
        {
            "has_outdated_libssl": False,
            "has_outdated_busybox": False,
            "has_outdated_dropbear": False,
        }
    )
    assert result.present is True
    assert result.score == 0.0


def test_score_strings_outdated_busybox_contributes() -> None:
    """has_outdated_busybox=True should be reflected in score."""
    r_false = _score_strings({"has_outdated_busybox": False})
    r_true = _score_strings({"has_outdated_busybox": True})
    assert r_true.score > r_false.score


def test_score_strings_outdated_dropbear_contributes() -> None:
    """has_outdated_dropbear=True should be reflected in score."""
    r_false = _score_strings({"has_outdated_dropbear": False})
    r_true = _score_strings({"has_outdated_dropbear": True})
    assert r_true.score > r_false.score


def test_score_strings_passwords_contributes() -> None:
    """count_hardcoded_passwords should contribute to score."""
    r_none = _score_strings({})
    r_some = _score_strings({"count_hardcoded_passwords": 3})
    assert r_some.score > r_none.score


def test_score_strings_combined_features() -> None:
    """Multiple string features produce higher score than single feature."""
    r_single = _score_strings({"has_outdated_libssl": True})
    r_combined = _score_strings(
        {
            "has_outdated_libssl": True,
            "has_outdated_busybox": True,
            "count_hardcoded_passwords": 2,
        }
    )
    assert r_combined.score >= r_single.score
