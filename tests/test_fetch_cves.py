from __future__ import annotations

from scripts.fetch_cves import (
    _aggregate_scores,
    extract_cvss,
    normalize_model,
    normalize_vendor,
)

# ---------------------------------------------------------------------------
# normalize_vendor / normalize_model
# ---------------------------------------------------------------------------


def test_normalize_vendor_dlink() -> None:
    assert normalize_vendor("dlink") == "d-link"


def test_normalize_vendor_tplink() -> None:
    assert normalize_vendor("tplink") == "tp-link"


def test_normalize_vendor_passthrough() -> None:
    assert normalize_vendor("netgear") == "netgear"
    assert normalize_vendor("belkin") == "belkin"


def test_normalize_model_with_hyphen() -> None:
    """Models already hyphenated should just uppercase."""
    assert normalize_model("dir-300") == "DIR-300"
    assert normalize_model("dsr-1000ac") == "DSR-1000AC"


def test_normalize_model_missing_hyphen() -> None:
    """Models like 'dir300' should get a hyphen inserted."""
    assert normalize_model("dir300") == "DIR-300"
    assert normalize_model("dir605l") == "DIR-605L"


def test_normalize_model_underscore_suffix() -> None:
    """Models like 'f5d7230_4' should become 'F5D7230-4'."""
    assert normalize_model("f5d7230_4") == "F5D7230-4"
    assert normalize_model("f5d6231_4") == "F5D6231-4"


def test_normalize_model_double_underscore() -> None:
    """Models like 'dgs_1210_48' -> 'DGS-1210-48'."""
    assert normalize_model("dgs_1210_48") == "DGS-1210-48"


def test_normalize_model_plain() -> None:
    """Models without hyphens or underscores just uppercase."""
    assert normalize_model("awgr54") == "AWGR-54"


# ---------------------------------------------------------------------------
# extract_cvss
# ---------------------------------------------------------------------------


def test_extract_cvss_v31() -> None:
    """Should prefer CVSS v3.1 when available."""
    cve = {
        "metrics": {
            "cvssMetricV31": [
                {"cvssData": {"baseScore": 9.8, "baseSeverity": "CRITICAL"}}
            ],
            "cvssMetricV2": [
                {
                    "cvssData": {"baseScore": 7.5},
                    "baseSeverity": "HIGH",
                }
            ],
        }
    }
    score, severity = extract_cvss(cve)
    assert score == 9.8
    assert severity == "CRITICAL"


def test_extract_cvss_v30_fallback() -> None:
    """Should fall back to v3.0 when v3.1 is missing."""
    cve = {
        "metrics": {
            "cvssMetricV30": [{"cvssData": {"baseScore": 7.5, "baseSeverity": "HIGH"}}],
        }
    }
    score, severity = extract_cvss(cve)
    assert score == 7.5
    assert severity == "HIGH"


def test_extract_cvss_v2_fallback() -> None:
    """Should fall back to v2 when v3.x is missing."""
    cve = {
        "metrics": {
            "cvssMetricV2": [
                {
                    "cvssData": {"baseScore": 5.0},
                    "baseSeverity": "MEDIUM",
                }
            ],
        }
    }
    score, severity = extract_cvss(cve)
    assert score == 5.0
    assert severity == "MEDIUM"


def test_extract_cvss_no_metrics() -> None:
    """Should return 0.0/NONE when no metrics are present."""
    score, severity = extract_cvss({"metrics": {}})
    assert score == 0.0
    assert severity == "NONE"


def test_extract_cvss_empty_cve() -> None:
    """Should handle completely empty CVE dict."""
    score, severity = extract_cvss({})
    assert score == 0.0
    assert severity == "NONE"


# ---------------------------------------------------------------------------
# _aggregate_scores
# ---------------------------------------------------------------------------


def test_aggregate_empty() -> None:
    """Empty input should return all zeros."""
    result = _aggregate_scores([])
    assert result["cvss_max"] == 0.0
    assert result["cve_total"] == 0
    assert result["cve_count_critical"] == 0


def test_aggregate_mixed_severities() -> None:
    """Should correctly count severities and find max score."""
    scores = [
        (9.8, "CRITICAL"),
        (7.5, "HIGH"),
        (7.1, "HIGH"),
        (4.3, "MEDIUM"),
        (2.1, "LOW"),
    ]
    result = _aggregate_scores(scores)
    assert result["cvss_max"] == 9.8
    assert result["cve_total"] == 5
    assert result["cve_count_critical"] == 1
    assert result["cve_count_high"] == 2
    assert result["cve_count_medium"] == 1
    assert result["cve_count_low"] == 1


def test_aggregate_none_severity_ignored() -> None:
    """Scores with NONE severity shouldn't count in any bucket."""
    scores = [(0.0, "NONE"), (0.0, "NONE")]
    result = _aggregate_scores(scores)
    assert result["cve_total"] == 2
    assert result["cve_count_critical"] == 0
    assert result["cve_count_high"] == 0
    assert result["cve_count_medium"] == 0
    assert result["cve_count_low"] == 0
