import pytest

from src.labeling.cve_labels import (
    LABEL_CRITICAL_CVE,
    LABEL_KNOWN_CVE,
    LABEL_NO_KNOWN_CVE,
    CveLabelThresholds,
    label_from_cve_stats,
)


def test_no_cve_data_returns_no_known_cve() -> None:
    assert label_from_cve_stats({}) == LABEL_NO_KNOWN_CVE


def test_cve_total_zero_returns_no_known_cve() -> None:
    stats = {"cve_total": 0, "cvss_max": 0.0}
    assert label_from_cve_stats(stats) == LABEL_NO_KNOWN_CVE


def test_known_cve_below_critical_threshold() -> None:
    stats = {"cve_total": 3, "cvss_max": 5.5}
    assert label_from_cve_stats(stats) == LABEL_KNOWN_CVE


def test_known_cve_at_critical_threshold() -> None:
    stats = {"cve_total": 1, "cvss_max": 9.0}
    assert label_from_cve_stats(stats) == LABEL_CRITICAL_CVE


def test_known_cve_above_critical_threshold() -> None:
    stats = {"cve_total": 5, "cvss_max": 9.8}
    assert label_from_cve_stats(stats) == LABEL_CRITICAL_CVE


def test_custom_critical_threshold() -> None:
    stats = {"cve_total": 1, "cvss_max": 7.0}
    thresholds = CveLabelThresholds(critical_cvss=7.0)
    assert label_from_cve_stats(stats, thresholds) == LABEL_CRITICAL_CVE


def test_label_depends_only_on_cve_fields() -> None:
    """O rotulo nao pode depender de nenhum campo de stats/strings/binwalk —
    so cve_total/cvss_max entram na decisao (protecao contra vazamento)."""
    stats_with_extra_fields = {
        "cve_total": 0,
        "cvss_max": 0.0,
        "entropy": 7.9,
        "count_hardcoded_passwords": 10,
        "has_telnetd": True,
    }
    assert label_from_cve_stats(stats_with_extra_fields) == LABEL_NO_KNOWN_CVE


@pytest.mark.parametrize("value", [-1, 1.5, "3", True])
def test_invalid_cve_count_fails(value: object) -> None:
    with pytest.raises(ValueError, match="cve_total"):
        label_from_cve_stats({"cve_total": value})


@pytest.mark.parametrize("value", [-0.1, 10.1, "9.0", float("nan")])
def test_invalid_cvss_fails(value: object) -> None:
    with pytest.raises(ValueError, match="cvss_max"):
        label_from_cve_stats({"cve_total": 1, "cvss_max": value})


def test_invalid_threshold_fails() -> None:
    with pytest.raises(ValueError, match="critical_cvss"):
        CveLabelThresholds(critical_cvss=11.0)
