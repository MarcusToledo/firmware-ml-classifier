from __future__ import annotations

import math
from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import Any

import pandas as pd
import yaml  # type: ignore[import-untyped]

from src.labeling.cve_labels import (
    LABEL_CRITICAL_CVE,
    LABEL_KNOWN_CVE,
    LABEL_NO_KNOWN_CVE,
)

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
    strings: float = 0.30
    binwalk: float = 0.15


@dataclass(frozen=True)
class HardRuleConfig:
    has_telnetd_min_level: str = LABEL_KNOWN_CVE
    has_debug_account_min_level: str = LABEL_KNOWN_CVE
    hardcoded_passwords_min_level: str = LABEL_KNOWN_CVE


@dataclass(frozen=True)
class StatsSubScoreConfig:
    entropy_low: float = 6.0
    entropy_high: float = 8.0
    compress_ratio_low: float = 0.80
    compress_ratio_high: float = 1.0
    byte_mean_center: float = 127.5
    byte_mean_factor: float = 0.3


@dataclass(frozen=True)
class StringsSubScoreConfig:
    hardcoded_passwords_midpoint: float = 1.0
    hardcoded_passwords_steepness: float = 2.0
    credential_pairs_midpoint: float = 1.0
    credential_pairs_steepness: float = 3.0
    hardcoded_ips_midpoint: float = 2.0
    hardcoded_ips_steepness: float = 1.0
    public_ips_midpoint: float = 1.0
    public_ips_steepness: float = 2.5
    outdated_lib_score: float = 0.6


@dataclass(frozen=True)
class BinwalkSubScoreConfig:
    encrypted_score: float = 0.8
    crypto_signatures_saturation: float = 5.0
    crypto_signatures_factor: float = 0.5
    entropy_variance_saturation: float = 3.0
    legacy_fs_score: float = 0.4
    legacy_fs_types: tuple[str, ...] = ("cramfs", "jffs2")
    legacy_compression_score: float = 0.2
    legacy_compression_types: tuple[str, ...] = ("gzip",)
    n_filesystems_saturation: float = 3.0
    n_filesystems_factor: float = 0.3


@dataclass(frozen=True)
class SubScoreConfig:
    stats: StatsSubScoreConfig = field(default_factory=StatsSubScoreConfig)
    strings: StringsSubScoreConfig = field(default_factory=StringsSubScoreConfig)
    binwalk: BinwalkSubScoreConfig = field(default_factory=BinwalkSubScoreConfig)


@dataclass(frozen=True)
class ScoringConfig:
    thresholds: ThresholdConfig = field(default_factory=ThresholdConfig)
    weights: WeightConfig = field(default_factory=WeightConfig)
    hard_rules: HardRuleConfig = field(default_factory=HardRuleConfig)
    sub_scores: SubScoreConfig = field(default_factory=SubScoreConfig)


# ---------------------------------------------------------------------------
# Result dataclasses
# ---------------------------------------------------------------------------

LEVEL_ORDER = {
    LABEL_NO_KNOWN_CVE: 0,
    LABEL_KNOWN_CVE: 1,
    LABEL_CRITICAL_CVE: 2,
}
LEVEL_FROM_INT = {v: k for k, v in LEVEL_ORDER.items()}


@dataclass
class SignalResult:
    name: str
    score: float
    weight: float
    present: bool
    detail: str
    missing_ignored: int = 0


@dataclass
class ScoringResult:
    level: str
    numeric_score: float
    signals: list[SignalResult]
    hard_rule_applied: str | None
    hard_rules_triggered: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Sub-score calculators
# ---------------------------------------------------------------------------


def _sigmoid(x: float, midpoint: float, steepness: float) -> float:
    """Calcula a sigmoide centrada no ponto médio."""
    return 1.0 / (1.0 + math.exp(-steepness * (x - midpoint)))


def _is_missing(v: Any) -> bool:
    """Identifica valores escalares ausentes sem avaliar arrays como booleanos."""
    return v is None or (pd.api.types.is_scalar(v) and bool(pd.isna(v)))


def _values(
    features: dict[str, Any], keys: tuple[str, ...]
) -> tuple[dict[str, Any], int]:
    """Separa valores presentes e conta chaves existentes com valor ausente."""
    return (
        {
            key: features[key]
            for key in keys
            if key in features and not _is_missing(features[key])
        },
        sum(key in features and _is_missing(features[key]) for key in keys),
    )


def _signal(
    name: str, parts: list[float], details: list[str], present: bool, missing: int
) -> SignalResult:
    """Monta o sinal com a contagem auditável de valores ignorados."""
    if missing:
        details.append(f"missing_ignored={missing}")
    return SignalResult(
        name,
        sum(parts) / len(parts) if parts else 0.0,
        1.0 if present else 0.0,
        present,
        "; ".join(details),
        missing,
    )


def _score_stats(features: dict[str, Any], config: StatsSubScoreConfig) -> SignalResult:
    """Calcula o sinal estatístico ignorando valores ausentes."""
    values, missing = _values(features, ("entropy", "compress_ratio", "byte_mean"))
    if not values:
        return _signal("stats", [], ["no stats features"], False, missing)
    parts: list[float] = []
    details: list[str] = []
    if "entropy" in values:
        entropy = values["entropy"]
        s = max(
            0.0,
            min(
                1.0,
                (entropy - config.entropy_low)
                / (config.entropy_high - config.entropy_low),
            ),
        )
        parts.append(s)
        details.append(f"entropy={entropy:.2f}→{s:.2f}")
    if "compress_ratio" in values:
        ratio = values["compress_ratio"]
        s = max(
            0.0,
            min(
                1.0,
                (ratio - config.compress_ratio_low)
                / (config.compress_ratio_high - config.compress_ratio_low),
            ),
        )
        parts.append(s)
        details.append(f"compress_ratio={ratio:.3f}→{s:.2f}")
    if "byte_mean" in values:
        mean = values["byte_mean"]
        s = (
            max(
                0.0,
                min(1.0, abs(mean - config.byte_mean_center) / config.byte_mean_center),
            )
            * config.byte_mean_factor
        )
        parts.append(s)
        details.append(f"byte_mean={mean:.1f}→{s:.2f}")
    return _signal("stats", parts, details, True, missing)


def _string_count_settings(
    config: StringsSubScoreConfig,
) -> tuple[tuple[str, str, float, float], ...]:
    """Relaciona contagens às curvas configuradas."""
    return (
        (
            "count_hardcoded_passwords",
            "passwords",
            config.hardcoded_passwords_midpoint,
            config.hardcoded_passwords_steepness,
        ),
        (
            "count_credential_pairs",
            "cred_pairs",
            config.credential_pairs_midpoint,
            config.credential_pairs_steepness,
        ),
        (
            "count_hardcoded_ips",
            "ips",
            config.hardcoded_ips_midpoint,
            config.hardcoded_ips_steepness,
        ),
        (
            "count_public_ips",
            "public_ips",
            config.public_ips_midpoint,
            config.public_ips_steepness,
        ),
    )


def _score_strings(
    features: dict[str, Any], config: StringsSubScoreConfig
) -> SignalResult:
    """Calcula o sinal de strings ignorando valores ausentes."""
    counts = _string_count_settings(config)
    flags = (
        ("has_outdated_libssl", "libssl"),
        ("has_outdated_busybox", "busybox"),
        ("has_outdated_dropbear", "dropbear"),
    )
    values, missing = _values(
        features, tuple(row[0] for row in counts) + tuple(row[0] for row in flags)
    )
    if not values:
        return _signal("strings", [], ["no string features"], False, missing)
    parts: list[float] = []
    details: list[str] = []
    for key, name, midpoint, steepness in counts:
        value = values.get(key, 0)
        if value > 0:
            s = _sigmoid(value, midpoint, steepness)
            parts.append(s)
            details.append(f"{name}={value}→{s:.2f}")
    for key, name in flags:
        if key in values:
            value = values[key]
            s = config.outdated_lib_score if value else 0.0
            parts.append(s)
            details.append(f"{name}_outdated={value}→{s:.2f}")
    return _signal("strings", parts, details, True, missing)


def _binwalk_numeric_parts(
    values: dict[str, Any],
    config: BinwalkSubScoreConfig,
    parts: list[float],
    details: list[str],
) -> None:
    """Acumula sub-scores numéricos e o indicador de criptografia."""
    if "has_encrypted_sections" in values:
        value = values["has_encrypted_sections"]
        s = config.encrypted_score if value else 0.0
        parts.append(s)
        details.append(f"encrypted={value}→{s:.2f}")
    if "n_crypto_signatures" in values:
        value = values["n_crypto_signatures"]
        s = (
            min(1.0, value / config.crypto_signatures_saturation)
            * config.crypto_signatures_factor
        )
        parts.append(s)
        details.append(f"crypto_sigs={value}→{s:.2f}")
    if "entropy_variance_across_sections" in values:
        value = values["entropy_variance_across_sections"]
        s = min(1.0, value / config.entropy_variance_saturation)
        parts.append(s)
        details.append(f"entropy_var={value:.2f}→{s:.2f}")
    for key, label, types, score in (
        ("fs_type", "fs_type", config.legacy_fs_types, config.legacy_fs_score),
        (
            "compression_type",
            "compression",
            config.legacy_compression_types,
            config.legacy_compression_score,
        ),
    ):
        if key in values:
            value = values[key]
            s = score if str(value).lower() in types else 0.0
            parts.append(s)
            details.append(f"{label}={value}→{s:.2f}")


def _score_binwalk(
    features: dict[str, Any], config: BinwalkSubScoreConfig
) -> SignalResult:
    """Calcula o sinal estrutural ignorando valores ausentes."""
    values, missing = _values(
        features,
        (
            "has_encrypted_sections",
            "n_crypto_signatures",
            "entropy_variance_across_sections",
            "fs_type",
            "compression_type",
            "n_filesystems",
        ),
    )
    if not values or (
        set(values) == {"n_filesystems"} and values["n_filesystems"] <= 0
    ):
        return _signal("binwalk", [], ["no binwalk features"], False, missing)
    parts: list[float] = []
    details: list[str] = []
    _binwalk_numeric_parts(values, config, parts, details)
    if values.get("n_filesystems", 0) > 0:
        value = values["n_filesystems"]
        s = (
            min(1.0, value / config.n_filesystems_saturation)
            * config.n_filesystems_factor
        )
        parts.append(s)
        details.append(f"n_filesystems={value}→{s:.2f}")
    return _signal("binwalk", parts, details, True, missing)


# ---------------------------------------------------------------------------
# Main scoring function
# ---------------------------------------------------------------------------


def _apply_hard_rules(
    features: dict[str, Any], config: ScoringConfig, level: str
) -> tuple[str, str | None, list[str]]:
    """Eleva o nível e registra todas as condições acionadas em ordem."""
    triggered: list[str] = []
    applied: str | None = None
    for name, key, minimum in (
        ("has_telnetd", "has_telnetd", config.hard_rules.has_telnetd_min_level),
        (
            "has_debug_account",
            "has_debug_account",
            config.hard_rules.has_debug_account_min_level,
        ),
        (
            "hardcoded_passwords",
            "count_hardcoded_passwords",
            config.hard_rules.hardcoded_passwords_min_level,
        ),
    ):
        value = features.get(key)
        active = (
            value is not None
            and not _is_missing(value)
            and (value > 0 if name == "hardcoded_passwords" else bool(value))
        )
        if active:
            triggered.append(name)
            if LEVEL_ORDER[minimum] > LEVEL_ORDER[level]:
                level = minimum
                applied = name
    return level, applied, triggered


def score_firmware(
    features: dict[str, Any],
    config: ScoringConfig,
) -> ScoringResult:
    """Produz uma previsão determinística para comparação com o classificador.

    O resultado não é ground truth; nenhum campo CVE participa do cálculo.
    """
    weights_map = {
        "stats": config.weights.stats,
        "strings": config.weights.strings,
        "binwalk": config.weights.binwalk,
    }

    signals: list[SignalResult] = [
        _score_stats(features, config.sub_scores.stats),
        _score_strings(features, config.sub_scores.strings),
        _score_binwalk(features, config.sub_scores.binwalk),
    ]
    for result in signals:
        result.weight = weights_map[result.name] if result.present else 0.0

    total_weight = sum(s.weight for s in signals)
    numeric_score = (
        sum(s.score * s.weight for s in signals) / total_weight if total_weight else 0.0
    )
    if numeric_score < config.thresholds.low:
        level = LABEL_NO_KNOWN_CVE
    elif numeric_score < config.thresholds.high:
        level = LABEL_KNOWN_CVE
    else:
        level = LABEL_CRITICAL_CVE
    level, applied, triggered = _apply_hard_rules(features, config, level)
    return ScoringResult(level, numeric_score, signals, applied, triggered)


# ---------------------------------------------------------------------------
# Config loading
# ---------------------------------------------------------------------------


def _mapping(value: Any, path: Path, key: str, allowed: set[str]) -> dict[str, Any]:
    """Valida mapeamento e rejeita chaves desconhecidas com contexto."""
    if not isinstance(value, dict):
        raise ValueError(f"{path}: {key}: DEVE ser mapeamento")
    for name in value:
        if name not in allowed:
            raise ValueError(f"{path}: {key}.{name}: chave desconhecida")
    return value


def _section(
    value: dict[str, Any], path: Path, key: str, cls: type[Any]
) -> dict[str, Any]:
    """Valida as chaves de uma seção opcional."""
    return _mapping(
        value.get(key, {}), path, f"scoring.{key}", {f.name for f in fields(cls)}
    )


def _number(value: Any, path: Path, key: str) -> float:
    """Exige número finito sem aceitar booleanos."""
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
    ):
        raise ValueError(f"{path}: {key}: DEVE ser número finito")
    return float(value)


def _thresholds(scoring: dict[str, Any], path: Path) -> ThresholdConfig:
    """Valida limites crescentes dentro do intervalo unitário."""
    values = _section(scoring, path, "thresholds", ThresholdConfig)
    default = ThresholdConfig()
    low = _number(values.get("low", default.low), path, "scoring.thresholds.low")
    high = _number(values.get("high", default.high), path, "scoring.thresholds.high")
    if not 0 <= low < high <= 1:
        raise ValueError(f"{path}: scoring.thresholds: exige 0 ≤ low < high ≤ 1")
    return ThresholdConfig(low, high)


def _weights(scoring: dict[str, Any], path: Path) -> WeightConfig:
    """Valida pesos não negativos e soma positiva."""
    values = _section(scoring, path, "weights", WeightConfig)
    default = WeightConfig()
    numbers = {
        name: _number(
            values.get(name, getattr(default, name)), path, f"scoring.weights.{name}"
        )
        for name in ("stats", "strings", "binwalk")
    }
    for name, value in numbers.items():
        if value < 0:
            raise ValueError(f"{path}: scoring.weights.{name}: peso negativo")
    if sum(numbers.values()) <= 0:
        raise ValueError(f"{path}: scoring.weights: soma DEVE ser positiva")
    return WeightConfig(**numbers)


def _hard_rules(scoring: dict[str, Any], path: Path) -> HardRuleConfig:
    """Valida níveis mínimos de cada regra."""
    values = _section(scoring, path, "hard_rules", HardRuleConfig)
    for key, level in values.items():
        if not isinstance(level, str) or level not in LEVEL_ORDER:
            raise ValueError(f"{path}: scoring.hard_rules.{key}: nível inválido")
    return HardRuleConfig(**values)


def _sub_group(group: dict[str, Any], path: Path, key: str, cls: type[Any]) -> Any:
    """Valida faixas, constantes e listas de tipos de um sub-score."""
    values = _mapping(group, path, key, {f.name for f in fields(cls)})
    default = cls()
    parsed: dict[str, Any] = {}
    for name in (f.name for f in fields(cls)):
        value = values.get(name, getattr(default, name))
        full_key = f"{key}.{name}"
        if name.endswith("_types"):
            if name in values and (
                not isinstance(value, list)
                or any(not isinstance(x, str) or not x for x in value)
            ):
                raise ValueError(
                    f"{path}: {full_key}: exige lista de strings não vazias"
                )
            parsed[name] = tuple(value)
            continue
        value = _number(value, path, full_key)
        if (
            name.endswith(("_score", "_factor"))
            and not 0 <= value <= 1
            or name.endswith(("_saturation", "_steepness"))
            and value <= 0
            or name.endswith("_midpoint")
            and value < 0
            or name == "byte_mean_center"
            and value <= 0
        ):
            raise ValueError(f"{path}: {full_key}: valor fora da faixa")
        parsed[name] = value
    for prefix in ("entropy", "compress_ratio"):
        if (
            f"{prefix}_low" in parsed
            and not parsed[f"{prefix}_low"] < parsed[f"{prefix}_high"]
        ):
            raise ValueError(f"{path}: {key}.{prefix}: low DEVE ser menor que high")
    return cls(**parsed)


def _sub_scores(scoring: dict[str, Any], path: Path) -> SubScoreConfig:
    """Carrega e valida as três subseções de sub-scores."""
    values = _mapping(
        scoring.get("sub_scores", {}),
        path,
        "scoring.sub_scores",
        {"stats", "strings", "binwalk"},
    )
    return SubScoreConfig(
        stats=_sub_group(
            values.get("stats", {}),
            path,
            "scoring.sub_scores.stats",
            StatsSubScoreConfig,
        ),
        strings=_sub_group(
            values.get("strings", {}),
            path,
            "scoring.sub_scores.strings",
            StringsSubScoreConfig,
        ),
        binwalk=_sub_group(
            values.get("binwalk", {}),
            path,
            "scoring.sub_scores.binwalk",
            BinwalkSubScoreConfig,
        ),
    )


def load_scoring_config(path: Path) -> ScoringConfig:
    """Carrega configuração validada do baseline a partir do YAML."""
    data = _mapping(yaml.safe_load(path.read_text()), path, "scoring", {"scoring"})
    if "scoring" not in data:
        raise ValueError(f"{path}: scoring: seção obrigatória")
    scoring = _mapping(
        data["scoring"],
        path,
        "scoring",
        {"thresholds", "weights", "hard_rules", "sub_scores"},
    )
    return ScoringConfig(
        thresholds=_thresholds(scoring, path),
        weights=_weights(scoring, path),
        hard_rules=_hard_rules(scoring, path),
        sub_scores=_sub_scores(scoring, path),
    )
