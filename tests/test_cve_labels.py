import pytest

from src.labeling.cve_labels import (
    LABEL_CRITICAL_CVE,
    LABEL_INDETERMINATE,
    LABEL_KNOWN_CVE,
    LABEL_NO_KNOWN_CVE,
    CveLabelThresholds,
    applicable_cves_for_version,
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
    """O rotulo nao pode depender de nenhum campo de stats/strings/binwalk,
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


def _cve(ranges: list[dict[str, str]]) -> dict:
    """Monta uma CVE de teste no formato real (`configurations`), a partir
    de uma lista simplificada de bounds/criteria -- mesmo formato que
    `scripts/fetch_cves.py` grava no cache de verdade."""
    cpe_matches = [{**bounds, "vulnerable": True} for bounds in ranges]
    return {
        "id": "CVE-1",
        "cvss_max": 9.8,
        "severity": "CRITICAL",
        "configurations": (
            [{"nodes": [{"cpeMatch": cpe_matches}]}] if cpe_matches else []
        ),
    }


def test_missing_version_is_indeterminate() -> None:
    entry = {"source": "keyword", "cves": [_cve([])]}
    assert applicable_cves_for_version(None, entry) == ([], False)
    assert applicable_cves_for_version("  ", entry) == ([], False)
    assert applicable_cves_for_version("ABTG", entry) == ([], False)


def test_comparable_version_filters_fixed_release() -> None:
    vulnerable = _cve([{"versionEndExcluding": "2.0"}])
    entry = {"source": "keyword", "cves": [vulnerable]}
    assert applicable_cves_for_version("1.9", entry) == ([vulnerable], True)
    assert applicable_cves_for_version("2.0", entry) == ([], True)


def test_cve_without_cpe_information_applies_conservatively() -> None:
    cve = _cve([])
    assert applicable_cves_for_version("1.0", {"cves": [cve]}) == ([cve], True)


def test_cpe_criteria_prevents_other_product_range_from_matching() -> None:
    cve = _cve(
        [
            {
                "criteria": "cpe:2.3:o:dlink:other_firmware:*:*:*:*:*:*:*:*",
                "versionEndExcluding": "9.0",
            }
        ]
    )
    entry = {"vendor": "d-link", "model": "DIR-300", "cves": [cve]}
    assert applicable_cves_for_version("1.0", entry) == ([], True)


def test_exact_cpe_version_is_respected() -> None:
    cve = _cve([{"criteria": "cpe:2.3:o:dlink:dir-300_firmware:1.2:*:*:*:*:*:*:*"}])
    entry = {"vendor": "d-link", "model": "DIR-300", "cves": [cve]}
    assert applicable_cves_for_version("1.2", entry) == ([cve], True)
    assert applicable_cves_for_version("1.3", entry) == ([], True)


def test_exact_cpe_version_matches_with_different_granularity() -> None:
    """'1.2' (CPE) e '1.2.0' (firmware) sao a mesma versao; o padding de
    zeros ja usado em version_match.py deve valer aqui tambem."""
    cve = _cve([{"criteria": "cpe:2.3:o:dlink:dir-300_firmware:1.2:*:*:*:*:*:*:*"}])
    entry = {"vendor": "d-link", "model": "DIR-300", "cves": [cve]}
    assert applicable_cves_for_version("1.2.0", entry) == ([cve], True)


def test_exact_cpe_prerelease_does_not_match_release() -> None:
    cve = _cve([{"criteria": "cpe:2.3:o:dlink:dir-300_firmware:1.2beta:*:*:*:*:*:*:*"}])
    entry = {"vendor": "d-link", "model": "DIR-300", "cves": [cve]}
    assert applicable_cves_for_version("1.2", entry) == ([], True)


def test_unparseable_cpe_bound_is_indeterminate() -> None:
    cve = _cve([{"versionEndExcluding": "ABTG"}])
    assert applicable_cves_for_version("1.0", {"cves": [cve]}) == ([], False)


def test_compound_cpe_condition_is_indeterminate_without_other_platform() -> None:
    target = "cpe:2.3:o:dlink:dir-300_firmware:*:*:*:*:*:*:*:*"
    platform = "cpe:2.3:h:dlink:dir-300:*:*:*:*:*:*:*:*"
    cve = _cve([])
    cve["configurations"] = [
        {
            "nodes": [
                {
                    "operator": "AND",
                    "cpeMatch": [
                        {"vulnerable": True, "criteria": target},
                        {"vulnerable": False, "criteria": platform},
                    ],
                }
            ]
        }
    ]
    entry = {"vendor": "d-link", "model": "DIR-300", "cves": [cve]}
    assert applicable_cves_for_version("1.0", entry) == ([], False)


def test_and_with_other_vulnerable_product_is_indeterminate() -> None:
    cve = _cve([])
    cve["configurations"] = [
        {
            "nodes": [
                {
                    "operator": "AND",
                    "cpeMatch": [
                        {
                            "vulnerable": True,
                            "criteria": (
                                "cpe:2.3:o:dlink:dir-300_firmware:"
                                "*:*:*:*:*:*:*:*"
                            ),
                        },
                        {
                            "vulnerable": True,
                            "criteria": "cpe:2.3:a:other:platform:*:*:*:*:*:*:*:*",
                        },
                    ],
                }
            ]
        }
    ]
    entry = {"vendor": "d-link", "model": "DIR-300", "cves": [cve]}
    assert applicable_cves_for_version("1.0", entry) == ([], False)


def test_vendor_suffix_is_not_silently_discarded_for_numeric_range() -> None:
    cve = _cve([{"versionEndExcluding": "7.11"}])
    assert applicable_cves_for_version("7.10(ABTG.4)C0", {"cves": [cve]}) == (
        [],
        False,
    )


def test_indeterminate_is_a_label_quality_state() -> None:
    assert LABEL_INDETERMINATE not in {
        LABEL_NO_KNOWN_CVE,
        LABEL_KNOWN_CVE,
        LABEL_CRITICAL_CVE,
    }
