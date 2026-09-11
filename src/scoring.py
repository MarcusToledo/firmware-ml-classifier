from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

# ---------------------------------------------------------------------------
# Binwalk scoring constants
# ---------------------------------------------------------------------------

_ENCRYPTED_SCORE: float = 0.8
_CRYPTO_SIGS_SATURATION: float = 5.0
_CRYPTO_SIGS_WEIGHT: float = 0.5
_ENTROPY_VAR_SATURATION: float = 3.0
_LEGACY_FS_SCORE: float = 0.4
_LEGACY_FS_TYPES: frozenset[str] = frozenset({"cramfs", "jffs2"})
_LEGACY_COMPRESSION_SCORE: float = 0.2
_LEGACY_COMPRESSION_TYPES: frozenset[str] = frozenset({"gzip"})
_N_FILESYSTEMS_SATURATION: float = 3.0
_N_FILESYSTEMS_WEIGHT: float = 0.3
_OUTDATED_LIB_SCORE: float = 0.6

# ---------------------------------------------------------------------------
# Configuration dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ThresholdConfig:
    low: float = 0.20
    high: float = 0.60


@dataclass(frozen=True)
class WeightConfig:
    stats: float = 0.10
    cve: float = 0.45
    strings: float = 0.30
    binwalk: float = 0.15


@dataclass(frozen=True)
class HardRuleConfig:
    has_telnetd_min_level: str = "vulneravel"
    has_debug_account_min_level: str = "vulneravel"
    hardcoded_passwords_min_level: str = "vulneravel"
    cvss_critical_threshold: float = 9.0
    cvss_critical_min_level: str = "vulneravel"


@dataclass(frozen=True)
class ScoringConfig:
    thresholds: ThresholdConfig = field(default_factory=ThresholdConfig)
    weights: WeightConfig = field(default_factory=WeightConfig)
    hard_rules: HardRuleConfig = field(default_factory=HardRuleConfig)


# ---------------------------------------------------------------------------
# Result dataclasses
# ---------------------------------------------------------------------------

LEVEL_ORDER = {"seguro": 0, "vulneravel": 1, "critico": 2}
LEVEL_FROM_INT = {v: k for k, v in LEVEL_ORDER.items()}


@dataclass
class SignalResult:
    name: str
    score: float
    weight: float
    present: bool
    detail: str


@dataclass
class ScoringResult:
    level: str
    numeric_score: float
    signals: list[SignalResult]
    hard_rule_applied: str | None


# ---------------------------------------------------------------------------
# Sub-score calculators
# ---------------------------------------------------------------------------


def _sigmoid(x: float, midpoint: float, steepness: float) -> float:
    """Sigmoid mapping: 0-1 output centred on *midpoint*."""
    return 1.0 / (1.0 + math.exp(-steepness * (x - midpoint)))


def _score_stats(features: dict[str, Any]) -> SignalResult:
    """Sub-score for static statistical features."""
    entropy = features.get("entropy")
    compress_ratio = features.get("compress_ratio")
    byte_mean = features.get("byte_mean")

    if entropy is None and compress_ratio is None and byte_mean is None:
        return SignalResult("stats", 0.0, 0.0, False, "no stats features")

    parts: list[float] = []
    details: list[str] = []

    if entropy is not None:
        # High entropy (>7.5) is suspicious (encrypted/compressed)
        s = max(0.0, min(1.0, (entropy - 6.0) / 2.0))
        parts.append(s)
        details.append(f"entropy={entropy:.2f}→{s:.2f}")

    if compress_ratio is not None:
        # High compress ratio (near 1.0) means already compressed/encrypted
        s = max(0.0, min(1.0, (compress_ratio - 0.80) / 0.20))
        parts.append(s)
        details.append(f"compress_ratio={compress_ratio:.3f}→{s:.2f}")

    if byte_mean is not None:
        # Deviation from 127.5 — weak signal
        deviation = abs(byte_mean - 127.5) / 127.5
        s = max(0.0, min(1.0, deviation))
        parts.append(s * 0.3)  # downweight
        details.append(f"byte_mean={byte_mean:.1f}→{s * 0.3:.2f}")

    score = sum(parts) / len(parts) if parts else 0.0
    return SignalResult("stats", score, 1.0, True, "; ".join(details))


def _score_cve(features: dict[str, Any]) -> SignalResult:
    """Sub-score for CVE-related features."""
    cvss_max = features.get("cvss_max")
    crit = features.get("cve_count_critical")
    high = features.get("cve_count_high")

    if cvss_max is None and crit is None and high is None:
        return SignalResult("cve", 0.0, 0.0, False, "no CVE features")

    parts: list[float] = []
    weights: list[float] = []
    details: list[str] = []

    if cvss_max is not None:
        s = max(0.0, min(1.0, cvss_max / 10.0))
        parts.append(s)
        weights.append(3.0)  # dominant weight
        details.append(f"cvss_max={cvss_max:.1f}→{s:.2f}")

    if crit is not None:
        s = _sigmoid(crit, 2.0, 1.5)
        parts.append(s)
        weights.append(1.5)
        details.append(f"cve_critical={crit}→{s:.2f}")

    if high is not None:
        s = _sigmoid(high, 3.0, 1.0)
        parts.append(s)
        weights.append(1.0)
        details.append(f"cve_high={high}→{s:.2f}")

    total_w = sum(weights)
    score = sum(p * w for p, w in zip(parts, weights)) / total_w if total_w else 0.0
    return SignalResult("cve", score, 1.0, True, "; ".join(details))


def _score_strings(features: dict[str, Any]) -> SignalResult:
    """Sub-score for suspicious string features."""
    passwords = features.get("count_hardcoded_passwords")
    cred_pairs = features.get("count_credential_pairs")
    ips = features.get("count_hardcoded_ips")
    public_ips = features.get("count_public_ips")
    outdated_libssl = features.get("has_outdated_libssl")
    outdated_busybox = features.get("has_outdated_busybox")
    outdated_dropbear = features.get("has_outdated_dropbear")

    available = [
        v
        for v in [
            passwords,
            cred_pairs,
            ips,
            public_ips,
            outdated_libssl,
            outdated_busybox,
            outdated_dropbear,
        ]
        if v is not None
    ]
    if not available:
        return SignalResult("strings", 0.0, 0.0, False, "no string features")

    parts: list[float] = []
    details: list[str] = []

    if passwords is not None and passwords > 0:
        s = _sigmoid(passwords, 1.0, 2.0)
        parts.append(s)
        details.append(f"passwords={passwords}→{s:.2f}")

    if cred_pairs is not None and cred_pairs > 0:
        s = _sigmoid(cred_pairs, 1.0, 3.0)
        parts.append(s)
        details.append(f"cred_pairs={cred_pairs}→{s:.2f}")

    if ips is not None and ips > 0:
        s = _sigmoid(ips, 2.0, 1.0)
        parts.append(s)
        details.append(f"ips={ips}→{s:.2f}")

    if public_ips is not None and public_ips > 0:
        s = _sigmoid(public_ips, 1.0, 2.5)
        parts.append(s)
        details.append(f"public_ips={public_ips}→{s:.2f}")

    for name, outdated in [
        ("libssl", outdated_libssl),
        ("busybox", outdated_busybox),
        ("dropbear", outdated_dropbear),
    ]:
        if outdated is not None:
            s = _OUTDATED_LIB_SCORE if outdated else 0.0
            parts.append(s)
            details.append(f"{name}_outdated={outdated}→{s:.2f}")

    score = sum(parts) / len(parts) if parts else 0.0
    return SignalResult("strings", score, 1.0, True, "; ".join(details))


def _score_binwalk(features: dict[str, Any]) -> SignalResult:
    """Sub-score for Binwalk structural analysis features."""
    encrypted = features.get("has_encrypted_sections")
    crypto_sigs = features.get("n_crypto_signatures")
    entropy_var = features.get("entropy_variance_across_sections")
    fs_type = features.get("fs_type")
    compression = features.get("compression_type")
    n_filesystems = features.get("n_filesystems")

    available = [
        v
        for v in [
            encrypted,
            crypto_sigs,
            entropy_var,
            fs_type,
            compression,
            n_filesystems
            if (n_filesystems is not None and n_filesystems > 0)
            else None,
        ]
        if v is not None
    ]
    if not available:
        return SignalResult("binwalk", 0.0, 0.0, False, "no binwalk features")

    parts: list[float] = []
    details: list[str] = []

    if encrypted is not None:
        s = _ENCRYPTED_SCORE if encrypted else 0.0
        parts.append(s)
        details.append(f"encrypted={encrypted}→{s:.2f}")

    if crypto_sigs is not None:
        s = min(1.0, crypto_sigs / _CRYPTO_SIGS_SATURATION) * _CRYPTO_SIGS_WEIGHT
        parts.append(s)
        details.append(f"crypto_sigs={crypto_sigs}→{s:.2f}")

    if entropy_var is not None:
        # High variance → mixed content → suspicious
        s = min(1.0, entropy_var / _ENTROPY_VAR_SATURATION)
        parts.append(s)
        details.append(f"entropy_var={entropy_var:.2f}→{s:.2f}")

    if fs_type is not None:
        s = _LEGACY_FS_SCORE if str(fs_type).lower() in _LEGACY_FS_TYPES else 0.0
        parts.append(s)
        details.append(f"fs_type={fs_type}→{s:.2f}")

    if compression is not None:
        s = (
            _LEGACY_COMPRESSION_SCORE
            if str(compression).lower() in _LEGACY_COMPRESSION_TYPES
            else 0.0
        )
        parts.append(s)
        details.append(f"compression={compression}→{s:.2f}")

    if n_filesystems is not None and n_filesystems > 0:
        # Multiple embedded filesystems suggest hidden partitions or overlays
        s = min(1.0, n_filesystems / _N_FILESYSTEMS_SATURATION) * _N_FILESYSTEMS_WEIGHT
        parts.append(s)
        details.append(f"n_filesystems={n_filesystems}→{s:.2f}")

    score = sum(parts) / len(parts) if parts else 0.0
    return SignalResult("binwalk", score, 1.0, True, "; ".join(details))


# ---------------------------------------------------------------------------
# Main scoring function
# ---------------------------------------------------------------------------

_SIGNAL_FUNCS = {
    "stats": _score_stats,
    "cve": _score_cve,
    "strings": _score_strings,
    "binwalk": _score_binwalk,
}


def score_firmware(
    features: dict[str, Any],
    config: ScoringConfig,
) -> ScoringResult:
    """Score a firmware based on its features and return a deterministic label.

    Absent signals are excluded and weights are redistributed among present
    signals. If no signals are present, the firmware is labelled "seguro"
    (safe fallback).
    """
    weights_map = {
        "stats": config.weights.stats,
        "cve": config.weights.cve,
        "strings": config.weights.strings,
        "binwalk": config.weights.binwalk,
    }

    signals: list[SignalResult] = []
    for name, func in _SIGNAL_FUNCS.items():
        result = func(features)
        result.weight = weights_map[name] if result.present else 0.0
        signals.append(result)

    total_weight = sum(s.weight for s in signals)
    if total_weight == 0.0:
        return ScoringResult(
            level="seguro",
            numeric_score=0.0,
            signals=signals,
            hard_rule_applied=None,
        )

    numeric_score = sum(s.score * s.weight for s in signals) / total_weight

    # Map score to level via thresholds
    if numeric_score < config.thresholds.low:
        level = "seguro"
    elif numeric_score < config.thresholds.high:
        level = "vulneravel"
    else:
        level = "critico"

    # Apply hard rules (can only escalate, never downgrade)
    hard_rule_applied: str | None = None

    if features.get("has_telnetd"):
        min_level = config.hard_rules.has_telnetd_min_level
        if LEVEL_ORDER.get(min_level, 0) > LEVEL_ORDER.get(level, 0):
            level = min_level
            hard_rule_applied = "has_telnetd"

    if features.get("has_debug_account"):
        min_level = config.hard_rules.has_debug_account_min_level
        if LEVEL_ORDER.get(min_level, 0) > LEVEL_ORDER.get(level, 0):
            level = min_level
            hard_rule_applied = "has_debug_account"

    passwords = features.get("count_hardcoded_passwords", 0)
    if passwords and passwords > 0:
        min_level = config.hard_rules.hardcoded_passwords_min_level
        if LEVEL_ORDER.get(min_level, 0) > LEVEL_ORDER.get(level, 0):
            level = min_level
            hard_rule_applied = "hardcoded_passwords"

    cvss_max = features.get("cvss_max")
    if cvss_max is not None and cvss_max >= config.hard_rules.cvss_critical_threshold:
        min_level = config.hard_rules.cvss_critical_min_level
        if LEVEL_ORDER.get(min_level, 0) > LEVEL_ORDER.get(level, 0):
            level = min_level
            hard_rule_applied = "cvss_critical"

    return ScoringResult(
        level=level,
        numeric_score=numeric_score,
        signals=signals,
        hard_rule_applied=hard_rule_applied,
    )


# ---------------------------------------------------------------------------
# Config loading
# ---------------------------------------------------------------------------


def load_scoring_config(path: Path) -> ScoringConfig:
    """Load scoring configuration from a YAML file."""
    data = yaml.safe_load(path.read_text())
    scoring = data.get("scoring", {})

    thresholds = ThresholdConfig(**scoring.get("thresholds", {}))
    weights = WeightConfig(**scoring.get("weights", {}))
    hard_rules = HardRuleConfig(**scoring.get("hard_rules", {}))

    return ScoringConfig(
        thresholds=thresholds,
        weights=weights,
        hard_rules=hard_rules,
    )
