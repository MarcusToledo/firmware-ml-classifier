from __future__ import annotations

from pathlib import Path

from src.labeling.cve_labels import (
    LABEL_CRITICAL_CVE,
    LABEL_KNOWN_CVE,
    LABEL_NO_KNOWN_CVE,
)
from src.scoring import (
    ScoringConfig,
    ThresholdConfig,
    _score_strings,
    load_scoring_config,
    score_firmware,
)

DEFAULT_CONFIG = ScoringConfig()


def test_baseline_has_no_cve_signal() -> None:
    result = score_firmware({"entropy": 7.5}, DEFAULT_CONFIG)
    assert {signal.name for signal in result.signals} == {"stats", "strings", "binwalk"}


def test_baseline_ignores_cve_fields() -> None:
    features = {"entropy": 7.5, "compress_ratio": 0.9}
    baseline = score_firmware(features, DEFAULT_CONFIG)
    with_cve = score_firmware(
        {**features, "cvss_max": 10.0, "cve_count_critical": 10}, DEFAULT_CONFIG
    )
    assert with_cve.level == baseline.level
    assert with_cve.numeric_score == baseline.numeric_score
    assert with_cve.hard_rule_applied == baseline.hard_rule_applied


def test_baseline_uses_shared_class_names() -> None:
    assert score_firmware({}, DEFAULT_CONFIG).level == LABEL_NO_KNOWN_CVE
    high = {
        "entropy": 7.99,
        "compress_ratio": 0.999,
        "count_hardcoded_passwords": 5,
        "has_outdated_libssl": True,
        "has_encrypted_sections": True,
    }
    assert score_firmware(high, DEFAULT_CONFIG).level == LABEL_CRITICAL_CVE


def test_scoring_config_loads_without_cve_weight() -> None:
    path = Path(__file__).resolve().parents[1] / "configs/scoring.yaml"
    config = load_scoring_config(path)
    assert len(score_firmware({}, config).signals) == 3


def test_stats_only_redistributes_weight() -> None:
    """When only stats features are present, weight is redistributed."""
    features = {"entropy": 7.9, "byte_mean": 130.0, "compress_ratio": 0.99}
    result = score_firmware(features, DEFAULT_CONFIG)

    present = [s for s in result.signals if s.present]
    absent = [s for s in result.signals if not s.present]
    assert len(present) == 1
    assert present[0].name == "stats"
    assert len(absent) == 2
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


def test_hard_rule_telnetd_overrides_to_known_cve() -> None:
    """has_telnetd=True forces minimum LABEL_KNOWN_CVE regardless of score."""
    features = {
        "entropy": 4.0,
        "byte_mean": 127.5,
        "compress_ratio": 0.50,
        "has_telnetd": True,
    }
    result = score_firmware(features, DEFAULT_CONFIG)
    assert result.level in (LABEL_KNOWN_CVE, LABEL_CRITICAL_CVE)
    assert result.hard_rule_applied == "has_telnetd"


def test_hard_rule_debug_account() -> None:
    """has_debug_account=True forces minimum LABEL_KNOWN_CVE."""
    features = {
        "entropy": 4.0,
        "byte_mean": 127.5,
        "compress_ratio": 0.50,
        "has_debug_account": True,
    }
    result = score_firmware(features, DEFAULT_CONFIG)
    assert result.level in (LABEL_KNOWN_CVE, LABEL_CRITICAL_CVE)
    assert result.hard_rule_applied == "has_debug_account"


def test_hard_rule_hardcoded_passwords() -> None:
    """count_hardcoded_passwords > 0 forces minimum LABEL_KNOWN_CVE."""
    # Low stats score alone → LABEL_NO_KNOWN_CVE, but hard rule escalates
    features = {
        "entropy": 4.0,
        "byte_mean": 127.5,
        "compress_ratio": 0.50,
        "count_hardcoded_passwords": 1,
    }
    result = score_firmware(features, DEFAULT_CONFIG)
    assert result.level in (LABEL_KNOWN_CVE, LABEL_CRITICAL_CVE)
    # The strings signal score pulls the weighted average up, so the level
    # may already be >= LABEL_KNOWN_CVE from the score alone. Verify the
    # label is correct regardless of whether the hard rule was the cause.
    assert result.level != LABEL_NO_KNOWN_CVE


def test_no_signals_returns_no_known_cve() -> None:
    """Firmware with no recognised features defaults to LABEL_NO_KNOWN_CVE."""
    features = {"unknown_feature": 42}
    result = score_firmware(features, DEFAULT_CONFIG)
    assert result.level == LABEL_NO_KNOWN_CVE
    assert result.numeric_score == 0.0
    assert result.hard_rule_applied is None


def test_empty_features_returns_no_known_cve() -> None:
    """Empty feature dict defaults to LABEL_NO_KNOWN_CVE."""
    result = score_firmware({}, DEFAULT_CONFIG)
    assert result.level == LABEL_NO_KNOWN_CVE
    assert result.numeric_score == 0.0


def test_no_signals_ignore_zero_threshold_before_hard_rules() -> None:
    """Mantém a classe sem CVE sem sinais e aplica a regra de telnet."""
    config = ScoringConfig(thresholds=ThresholdConfig(0.0, 0.5))
    assert score_firmware({}, config).level == LABEL_NO_KNOWN_CVE
    with_telnet = score_firmware({"has_telnetd": True}, config)
    assert with_telnet.level == LABEL_KNOWN_CVE
    assert with_telnet.hard_rule_applied == "has_telnetd"


def test_high_score_maps_to_critical_cve() -> None:
    """Features that produce a high score should map to LABEL_CRITICAL_CVE."""
    features = {
        "entropy": 7.99,
        "compress_ratio": 0.999,
        "count_hardcoded_passwords": 5,
        "has_outdated_libssl": True,
        "has_encrypted_sections": True,
    }
    result = score_firmware(features, DEFAULT_CONFIG)
    assert result.numeric_score >= 0.60
    assert result.level == LABEL_CRITICAL_CVE


def test_low_risk_maps_to_no_known_cve() -> None:
    """Low-risk features should map to LABEL_NO_KNOWN_CVE."""
    features = {
        "entropy": 5.0,
        "byte_mean": 127.5,
        "compress_ratio": 0.60,
    }
    result = score_firmware(features, DEFAULT_CONFIG)
    assert result.numeric_score < 0.20
    assert result.level == LABEL_NO_KNOWN_CVE


def test_custom_thresholds() -> None:
    """Custom thresholds should change classification boundaries."""
    features = {"entropy": 7.5, "compress_ratio": 0.90}
    strict_config = ScoringConfig(
        thresholds=ThresholdConfig(low=0.10, high=0.30),
    )
    result = score_firmware(features, strict_config)
    # With stricter thresholds, same features should be more severe
    assert result.level in (LABEL_KNOWN_CVE, LABEL_CRITICAL_CVE)


def test_signals_breakdown_present() -> None:
    """Result includes only the three firmware-derived signal groups."""
    features = {"entropy": 7.0}
    result = score_firmware(features, DEFAULT_CONFIG)
    names = {s.name for s in result.signals}
    assert names == {"stats", "strings", "binwalk"}


def test_hard_rule_does_not_downgrade() -> None:
    """Hard rules only escalate, never downgrade the level."""
    features = {
        "entropy": 7.99,
        "compress_ratio": 0.999,
        "count_hardcoded_passwords": 5,
        "has_outdated_libssl": True,
        "has_encrypted_sections": True,
        "has_telnetd": True,
    }
    result = score_firmware(features, DEFAULT_CONFIG)
    assert result.level == LABEL_CRITICAL_CVE


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
    result = _score_strings({}, DEFAULT_CONFIG.sub_scores.strings)
    assert result.present is False
    assert result.score == 0.0


def test_score_strings_outdated_libssl_raises_score() -> None:
    """has_outdated_libssl=True should produce a non-zero score."""
    result = _score_strings(
        {"has_outdated_libssl": True}, DEFAULT_CONFIG.sub_scores.strings
    )
    assert result.present is True
    assert result.score > 0.0


def test_score_strings_no_outdated_lib_zero() -> None:
    """All outdated flags False with no other features → score 0."""
    result = _score_strings(
        {
            "has_outdated_libssl": False,
            "has_outdated_busybox": False,
            "has_outdated_dropbear": False,
        },
        DEFAULT_CONFIG.sub_scores.strings,
    )
    assert result.present is True
    assert result.score == 0.0


def test_score_strings_outdated_busybox_contributes() -> None:
    """has_outdated_busybox=True should be reflected in score."""
    r_false = _score_strings(
        {"has_outdated_busybox": False}, DEFAULT_CONFIG.sub_scores.strings
    )
    r_true = _score_strings(
        {"has_outdated_busybox": True}, DEFAULT_CONFIG.sub_scores.strings
    )
    assert r_true.score > r_false.score


def test_score_strings_outdated_dropbear_contributes() -> None:
    """has_outdated_dropbear=True should be reflected in score."""
    r_false = _score_strings(
        {"has_outdated_dropbear": False}, DEFAULT_CONFIG.sub_scores.strings
    )
    r_true = _score_strings(
        {"has_outdated_dropbear": True}, DEFAULT_CONFIG.sub_scores.strings
    )
    assert r_true.score > r_false.score


def test_score_strings_passwords_contributes() -> None:
    """count_hardcoded_passwords should contribute to score."""
    r_none = _score_strings({}, DEFAULT_CONFIG.sub_scores.strings)
    r_some = _score_strings(
        {"count_hardcoded_passwords": 3}, DEFAULT_CONFIG.sub_scores.strings
    )
    assert r_some.score > r_none.score


def test_score_strings_combined_features() -> None:
    """Multiple string features produce higher score than single feature."""
    r_single = _score_strings(
        {"has_outdated_libssl": True}, DEFAULT_CONFIG.sub_scores.strings
    )
    r_combined = _score_strings(
        {
            "has_outdated_libssl": True,
            "has_outdated_busybox": True,
            "count_hardcoded_passwords": 2,
        },
        DEFAULT_CONFIG.sub_scores.strings,
    )
    assert r_combined.score >= r_single.score


def test_score_strings_cred_pairs_contributes() -> None:
    """count_credential_pairs > 0 should raise the strings sub-score."""
    r_none = _score_strings({}, DEFAULT_CONFIG.sub_scores.strings)
    r_some = _score_strings(
        {"count_credential_pairs": 1}, DEFAULT_CONFIG.sub_scores.strings
    )
    assert r_some.score > r_none.score


def test_score_strings_public_ips_contributes() -> None:
    """count_public_ips > 0 should raise the strings sub-score."""
    r_none = _score_strings({}, DEFAULT_CONFIG.sub_scores.strings)
    r_some = _score_strings({"count_public_ips": 1}, DEFAULT_CONFIG.sub_scores.strings)
    assert r_some.score > r_none.score


def test_score_strings_zero_new_counts_no_dilution() -> None:
    """New count features at zero must not dilute the existing score."""
    r_without = _score_strings(
        {"has_outdated_libssl": True}, DEFAULT_CONFIG.sub_scores.strings
    )
    r_with_zeros = _score_strings(
        {
            "has_outdated_libssl": True,
            "count_credential_pairs": 0,
            "count_public_ips": 0,
        },
        DEFAULT_CONFIG.sub_scores.strings,
    )
    assert r_with_zeros.score == r_without.score


def test_invalid_config_reports_path_and_key(tmp_path):
    """Rejeita categorias inválidas com contexto da configuração."""
    import pytest

    cases = [
        ("", "scoring"),
        ("[]", "scoring"),
        ("weights: {}", "scoring"),
        ("scoring: {unknown: 1}", "scoring.unknown"),
        ("unknown: 1\nscoring: {}", "unknown"),
        ("scoring: {thresholds: {unknown: 1}}", "scoring.thresholds.unknown"),
        ("scoring: {thresholds: {low: 0.8, high: 0.2}}", "scoring.thresholds"),
        ("scoring: {thresholds: {low: true}}", "scoring.thresholds.low"),
        ("scoring: {weights: {stats: -1}}", "scoring.weights.stats"),
        ("scoring: {weights: {stats: 0, strings: 0, binwalk: 0}}", "scoring.weights"),
        (
            "scoring: {hard_rules: {has_telnetd_min_level: invalid}}",
            "scoring.hard_rules.has_telnetd_min_level",
        ),
        (
            "scoring: {hard_rules: {has_telnetd_min_level: [x]}}",
            "scoring.hard_rules.has_telnetd_min_level",
        ),
        ("scoring: {weights: {strings: null}}", "scoring.weights.strings"),
        ("scoring: {weights: false}", "scoring.weights"),
        (
            "scoring: {sub_scores: {stats: {entropy_high: false}}}",
            "scoring.sub_scores.stats.entropy_high",
        ),
    ]
    path = tmp_path / "invalid.yaml"
    for text, key in cases:
        path.write_text(text)
        with pytest.raises(ValueError) as exc:
            load_scoring_config(path)
        assert str(path) in str(exc.value)
        assert key in str(exc.value)


def test_yaml_sub_scores_reproduce_defaults_and_override(tmp_path):
    """Reproduz padrões e altera o cálculo ao mudar o YAML."""

    yaml_path = Path(__file__).resolve().parents[1] / "configs/scoring.yaml"
    loaded = load_scoring_config(yaml_path)
    assert loaded.sub_scores == DEFAULT_CONFIG.sub_scores
    features = {"entropy": 7.0}
    assert (
        score_firmware(features, loaded).numeric_score
        == score_firmware(features, DEFAULT_CONFIG).numeric_score
    )
    text = yaml_path.read_text().replace("entropy_low: 6.0", "entropy_low: 7.5")
    path = tmp_path / "changed.yaml"
    path.write_text(text)
    changed = load_scoring_config(path)
    assert (
        score_firmware(features, changed).numeric_score
        != score_firmware(features, loaded).numeric_score
    )


def test_invalid_sub_scores_report_key(tmp_path):
    """Rejeita faixas, fatores, saturações e tipos inválidos."""
    import pytest

    cases = [
        ("stats: {entropy_low: 8, entropy_high: 7}", "stats.entropy"),
        ("stats: {byte_mean_center: 0}", "stats.byte_mean_center"),
        ("strings: {hardcoded_ips_steepness: 0}", "strings.hardcoded_ips_steepness"),
        ("strings: {public_ips_midpoint: -1}", "strings.public_ips_midpoint"),
        ("binwalk: {encrypted_score: 2}", "binwalk.encrypted_score"),
        ("binwalk: {legacy_fs_types: [cramfs, '']}", "binwalk.legacy_fs_types"),
        ("binwalk: {mystery: 3}", "binwalk.mystery"),
    ]
    path = tmp_path / "invalid.yaml"
    for value, key in cases:
        path.write_text(f"scoring:\n  sub_scores:\n    {value}\n")
        with pytest.raises(ValueError, match=key):
            load_scoring_config(path)


def test_missing_values_are_ignored_by_group():
    """Ignora None, NaN e pd.NA sem transformar ausência em risco."""
    import numpy as np
    import pandas as pd

    features = {
        "entropy": float("nan"),
        "compress_ratio": np.nan,
        "byte_mean": pd.NA,
        "count_hardcoded_passwords": pd.NA,
        "count_credential_pairs": np.nan,
        "has_outdated_libssl": None,
        "has_outdated_busybox": pd.NA,
        "has_outdated_dropbear": float("nan"),
        "count_hardcoded_ips": None,
        "count_public_ips": pd.NA,
        "has_encrypted_sections": pd.NA,
        "n_crypto_signatures": np.nan,
        "entropy_variance_across_sections": None,
        "fs_type": pd.NA,
        "compression_type": np.nan,
        "n_filesystems": pd.NA,
        "has_telnetd": pd.NA,
        "has_debug_account": np.nan,
    }
    result = score_firmware(features, DEFAULT_CONFIG)
    assert result.level == LABEL_NO_KNOWN_CVE
    assert result.numeric_score == 0
    assert result.hard_rules_triggered == []
    assert [(s.present, s.missing_ignored) for s in result.signals] == [
        (False, 3),
        (False, 7),
        (False, 6),
    ]
    assert all("missing_ignored=" in s.detail for s in result.signals)


def test_hard_rules_apply_with_no_signal_and_track_all():
    """Aplica mínimos sem peso e registra todas as regras acionadas."""
    from src.scoring import HardRuleConfig, WeightConfig

    single = score_firmware({"has_telnetd": True}, DEFAULT_CONFIG)
    assert single.numeric_score == 0
    assert single.level == LABEL_KNOWN_CVE
    assert single.hard_rules_triggered == ["has_telnetd"]
    config = ScoringConfig(
        weights=WeightConfig(stats=0, strings=0, binwalk=0),
        hard_rules=HardRuleConfig(has_debug_account_min_level=LABEL_CRITICAL_CVE),
    )
    result = score_firmware(
        {
            "entropy": 7,
            "has_telnetd": True,
            "has_debug_account": True,
            "count_hardcoded_passwords": 1,
        },
        config,
    )
    assert result.numeric_score == 0
    assert result.level == LABEL_CRITICAL_CVE
    assert result.hard_rule_applied == "has_debug_account"
    assert result.hard_rules_triggered == [
        "has_telnetd",
        "has_debug_account",
        "hardcoded_passwords",
    ]
