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
    cve = _cve([])
    entry = {"source": "keyword", "cves": [cve]}
    assert applicable_cves_for_version(None, entry) == ([], [cve])
    assert applicable_cves_for_version("  ", entry) == ([], [cve])
    assert applicable_cves_for_version("ABTG", entry) == ([], [cve])


def test_missing_version_with_empty_cache_has_negative_evidence() -> None:
    assert applicable_cves_for_version(None, {"cves": []}) == ([], [])


def test_applicable_and_indeterminate_cves_are_both_returned() -> None:
    indeterminate = _cve([{"versionEndExcluding": "ABTG"}])
    indeterminate["id"] = "CVE-INDETERMINATE"
    applicable = _cve([])
    applicable["id"] = "CVE-APPLICABLE"
    entry = {"cves": [indeterminate, applicable]}

    assert applicable_cves_for_version("1.0", entry) == (
        [applicable],
        [indeterminate],
    )


def test_comparable_version_filters_fixed_release() -> None:
    vulnerable = _cve([{"versionEndExcluding": "2.0"}])
    entry = {"source": "keyword", "cves": [vulnerable]}
    assert applicable_cves_for_version("1.9", entry) == ([vulnerable], [])
    assert applicable_cves_for_version("2.0", entry) == ([], [])


def test_cve_without_cpe_information_applies_conservatively() -> None:
    cve = _cve([])
    assert applicable_cves_for_version("1.0", {"cves": [cve]}) == ([cve], [])


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
    assert applicable_cves_for_version("1.0", entry) == ([], [])


def test_exact_cpe_version_is_respected() -> None:
    cve = _cve([{"criteria": "cpe:2.3:o:dlink:dir-300_firmware:1.2:*:*:*:*:*:*:*"}])
    entry = {"vendor": "d-link", "model": "DIR-300", "cves": [cve]}
    assert applicable_cves_for_version("1.2", entry) == ([cve], [])
    assert applicable_cves_for_version("1.3", entry) == ([], [])


def test_exact_cpe_version_matches_with_different_granularity() -> None:
    """'1.2' (CPE) e '1.2.0' (firmware) sao a mesma versao; o padding de
    zeros ja usado em version_match.py deve valer aqui tambem."""
    cve = _cve([{"criteria": "cpe:2.3:o:dlink:dir-300_firmware:1.2:*:*:*:*:*:*:*"}])
    entry = {"vendor": "d-link", "model": "DIR-300", "cves": [cve]}
    assert applicable_cves_for_version("1.2.0", entry) == ([cve], [])


def test_exact_cpe_prerelease_is_indeterminate_at_matching_base() -> None:
    criteria = "cpe:2.3:o:dlink:dir-300_firmware:1.2beta:*:*:*:*:*:*:*"
    cve = _cve([{"criteria": criteria}])
    entry = {"vendor": "d-link", "model": "DIR-300", "cves": [cve]}
    assert applicable_cves_for_version("1.2", entry) == ([], [cve])


def test_exact_cpe_build_suffix_is_indeterminate_at_base() -> None:
    criteria = "cpe:2.3:o:dlink:dir-300_firmware:2.14b01:*:*:*:*:*:*:*"
    cve = _cve([{"criteria": criteria}])
    entry = {"vendor": "d-link", "model": "DIR-300", "cves": [cve]}

    assert applicable_cves_for_version("2.14", entry) == ([], [cve])


def test_exact_cpe_build_suffix_is_indeterminate_at_padded_base() -> None:
    criteria = "cpe:2.3:o:dlink:dir-300_firmware:2.14b01:*:*:*:*:*:*:*"
    cve = _cve([{"criteria": criteria}])
    entry = {"vendor": "d-link", "model": "DIR-300", "cves": [cve]}

    assert applicable_cves_for_version("2.14.0", entry) == ([], [cve])


def test_exact_cpe_build_suffix_does_not_match_extra_numeric_segment() -> None:
    criteria = "cpe:2.3:o:dlink:dir-300_firmware:2.14b01:*:*:*:*:*:*:*"
    cve = _cve([{"criteria": criteria}])
    entry = {"vendor": "d-link", "model": "DIR-300", "cves": [cve]}

    assert applicable_cves_for_version("2.14.1", entry) == ([], [])


def test_exact_numeric_cpe_does_not_match_firmware_suffix() -> None:
    criteria = "cpe:2.3:o:dlink:dir-300_firmware:1.2:*:*:*:*:*:*:*"
    cve = _cve([{"criteria": criteria}])
    entry = {"vendor": "d-link", "model": "DIR-300", "cves": [cve]}

    assert applicable_cves_for_version("1.2rc1", entry) == ([], [])


def test_exact_cpe_build_suffix_does_not_apply_to_different_base() -> None:
    criteria = "cpe:2.3:o:dlink:dir-300_firmware:2.14b01:*:*:*:*:*:*:*"
    cve = _cve([{"criteria": criteria}])
    entry = {"vendor": "d-link", "model": "DIR-300", "cves": [cve]}

    assert applicable_cves_for_version("2.15", entry) == ([], [])


def test_exact_cpe_build_suffix_matches_case_insensitively() -> None:
    criteria = "cpe:2.3:o:dlink:dir-300_firmware:2.14b01:*:*:*:*:*:*:*"
    cve = _cve([{"criteria": criteria}])
    entry = {"vendor": "d-link", "model": "DIR-300", "cves": [cve]}

    assert applicable_cves_for_version("2.14B01", entry) == ([cve], [])


def test_exact_cpe_build_suffix_does_not_match_different_known_build() -> None:
    criteria = "cpe:2.3:o:dlink:dir-300_firmware:2.14b01:*:*:*:*:*:*:*"
    cve = _cve([{"criteria": criteria}])
    entry = {"vendor": "d-link", "model": "DIR-300", "cves": [cve]}

    assert applicable_cves_for_version("2.14B02", entry) == ([], [])


def test_exact_cpe_build_suffix_requires_separator_after_firmware_build() -> None:
    criteria = "cpe:2.3:o:dlink:dir-300_firmware:2.14b01:*:*:*:*:*:*:*"
    cve = _cve([{"criteria": criteria}])
    entry = {"vendor": "d-link", "model": "DIR-300", "cves": [cve]}

    assert applicable_cves_for_version("2.14B0", entry) == ([], [])


def test_exact_cpe_without_parseable_base_keeps_known_limitation() -> None:
    """Protege CPE sem base parseavel e registra a limitacao conhecida.

    O prefixo `firmware_` impede comparar versoes; o resultado nao afirma que
    a CVE nao se aplica.
    """
    criteria = "cpe:2.3:o:dlink:dir-300_firmware:firmware_4.05.03:*:*:*:*:*:*:*"
    cve = _cve([{"criteria": criteria}])
    entry = {"vendor": "d-link", "model": "DIR-300", "cves": [cve]}

    assert applicable_cves_for_version("4.05.03", entry) == ([], [])


def test_exact_cpe_build_and_region_suffix_is_indeterminate() -> None:
    criteria = "cpe:2.3:o:dlink:dir-300_firmware:1.06b05_ww:*:*:*:*:*:*:*"
    cve = _cve([{"criteria": criteria}])
    entry = {"vendor": "d-link", "model": "DIR-300", "cves": [cve]}

    assert applicable_cves_for_version("1.06", entry) == ([], [cve])


def test_exact_cpe_region_variant_is_indeterminate_for_matching_build() -> None:
    criteria = "cpe:2.3:o:dlink:dir-300_firmware:1.06b05_ww:*:*:*:*:*:*:*"
    cve = _cve([{"criteria": criteria}])
    entry = {"vendor": "d-link", "model": "DIR-300", "cves": [cve]}

    assert applicable_cves_for_version("1.06B05", entry) == ([], [cve])


def test_exact_cpe_with_specific_update_is_indeterminate_when_version_matches() -> None:
    """Caso real TL-SG2008: a CPE fixa o build 2018 e o arquivo e de 2014."""
    update = "build_20180529_rel.40524"
    criteria = f"cpe:2.3:o:tp-link:tl-sg2008_firmware:1.0.0:{update}:*:*:*:*:*:*"
    cve = _cve([{"criteria": criteria}])
    entry = {"vendor": "tp-link", "model": "tl-sg2008", "cves": [cve]}

    assert applicable_cves_for_version("1.0.0", entry) == ([], [cve])
    assert applicable_cves_for_version("1.0.1", entry) == ([], [])


def test_range_with_specific_update_is_indeterminate_inside_range() -> None:
    criteria = "cpe:2.3:o:dlink:dir-300_firmware:*:hotfix_04:*:*:*:*:*:*"
    cve = _cve([{"criteria": criteria, "versionEndExcluding": "2.0"}])
    entry = {"vendor": "d-link", "model": "DIR-300", "cves": [cve]}

    assert applicable_cves_for_version("1.5", entry) == ([], [cve])
    assert applicable_cves_for_version("2.0", entry) == ([], [])


def test_not_applicable_update_marker_keeps_match() -> None:
    """`-` e NA na CPE 2.3: nao restringe a um build especifico."""
    criteria = "cpe:2.3:o:dlink:dir-300_firmware:1.2:-:*:*:*:*:*:*"
    cve = _cve([{"criteria": criteria}])
    entry = {"vendor": "d-link", "model": "DIR-300", "cves": [cve]}

    assert applicable_cves_for_version("1.2", entry) == ([cve], [])


def test_unparseable_cpe_bound_is_indeterminate() -> None:
    cve = _cve([{"versionEndExcluding": "ABTG"}])
    assert applicable_cves_for_version("1.0", {"cves": [cve]}) == ([], [cve])


def test_asus_exact_cpe_version_normalizes_underscores() -> None:
    version = "3.0.0.4.374_4561"
    criteria = f"cpe:2.3:o:asus:rt-ac68u_firmware:{version}:*:*:*:*:*:*:*"
    cve = _cve([{"criteria": criteria}])
    entry = {"vendor": "asus", "model": "rt-ac68u", "cves": [cve]}

    assert applicable_cves_for_version("3.0.0.4.374.4561", entry) == ([cve], [])
    assert applicable_cves_for_version("3.0.0.4.374.4562", entry) == ([], [])


def test_asus_exclusive_bound_normalizes_underscores() -> None:
    cve = _cve([{"versionEndExcluding": "1.1.2.3_1010"}])
    entry = {"vendor": "asus", "model": "rt-ac68u", "cves": [cve]}

    assert applicable_cves_for_version("1.1.2.3.1009", entry) == ([cve], [])
    assert applicable_cves_for_version("1.1.2.3.1010", entry) == ([], [])


def test_non_asus_bound_preserves_underscore() -> None:
    cve = _cve([{"versionEndExcluding": "1.0_5"}])
    entry = {"vendor": "d-link", "model": "DIR-300", "cves": [cve]}

    assert applicable_cves_for_version("1.0", entry) == ([], [cve])


def test_leading_v_is_removed_for_any_vendor() -> None:
    cve = _cve([{"versionEndExcluding": "v1.2"}])
    entry = {"vendor": "d-link", "model": "DIR-300", "cves": [cve]}

    assert applicable_cves_for_version("1.1", entry) == ([cve], [])
    assert applicable_cves_for_version("1.2", entry) == ([], [])


def test_netgear_exact_cpe_with_package_is_indeterminate_at_base() -> None:
    package_version = "1.0.2.60_1.0.38"
    criteria = f"cpe:2.3:o:netgear:r6400_firmware:{package_version}:*:*:*:*:*:*:*"
    cve = _cve([{"criteria": criteria}])
    entry = {"vendor": "netgear", "model": "r6400", "cves": [cve]}

    assert applicable_cves_for_version("1.0.2.60", entry) == ([], [cve])
    assert applicable_cves_for_version("1.0.2.60.0", entry) == ([], [cve])
    assert applicable_cves_for_version("1.0.2.61", entry) == ([], [])


def test_netgear_range_removes_language_package() -> None:
    cve = _cve(
        [
            {
                "versionStartIncluding": "v1.0.9.6_1.2.19",
                "versionEndIncluding": "v1.0.11.100_10.2.100",
            }
        ]
    )
    entry = {"vendor": "netgear", "model": "r6250", "cves": [cve]}

    assert applicable_cves_for_version("1.0.10.0", entry) == ([cve], [])
    assert applicable_cves_for_version("1.0.12.0", entry) == ([], [])
    assert applicable_cves_for_version("1.0.9.6", entry) == ([], [cve])


def test_netgear_packaged_bound_is_indeterminate_at_padded_base() -> None:
    cve = _cve([{"versionEndExcluding": "1.0.2.0_1.0.1"}])
    entry = {"vendor": "netgear", "model": "r6400", "cves": [cve]}

    assert applicable_cves_for_version("1.0.2", entry) == ([], [cve])


def test_build_suffix_in_bound_stays_indeterminate() -> None:
    cve = _cve([{"versionEndIncluding": "1.04B58"}])
    entry = {"vendor": "d-link", "model": "dir-300", "cves": [cve]}

    assert applicable_cves_for_version("1.04", entry) == ([], [cve])


def _and_config(*matches: dict) -> dict:
    return {"nodes": [{"operator": "AND", "cpeMatch": list(matches)}]}


def test_target_hardware_platform_without_revision_is_satisfied() -> None:
    """O cache e por vendor/model, entao o hardware do proprio modelo-alvo,
    sem revisao (`-` ou `*`), e satisfeito por construcao."""
    fw = "cpe:2.3:o:dlink:dir-300_firmware:*:*:*:*:*:*:*:*"
    entry = {"vendor": "d-link", "model": "DIR-300"}
    for revision in ("-", "*"):
        cve = _cve([])
        cve["configurations"] = [
            _and_config(
                {"vulnerable": True, "criteria": fw, "versionEndExcluding": "2.0"},
                {
                    "vulnerable": False,
                    "criteria": f"cpe:2.3:h:dlink:dir-300:{revision}:*:*:*:*:*:*:*",
                },
            )
        ]
        entry["cves"] = [cve]
        assert applicable_cves_for_version("1.0", entry) == ([cve], [])
        assert applicable_cves_for_version("2.0", entry) == ([], [])


def test_target_hardware_platform_with_revision_is_indeterminate() -> None:
    """Sem a revisao do hardware nao da para afirmar que a CPE se aplica."""
    fw = "cpe:2.3:o:dlink:dir-300_firmware:*:*:*:*:*:*:*:*"
    cve = _cve([])
    cve["configurations"] = [
        _and_config(
            {"vulnerable": True, "criteria": fw},
            {
                "vulnerable": False,
                "criteria": "cpe:2.3:h:dlink:dir-300:b1:*:*:*:*:*:*:*",
            },
        )
    ]
    entry = {"vendor": "d-link", "model": "DIR-300", "cves": [cve]}
    assert applicable_cves_for_version("1.0", entry) == ([], [cve])


def test_non_vulnerable_platform_of_other_product_is_indeterminate() -> None:
    fw = "cpe:2.3:o:dlink:dir-300_firmware:*:*:*:*:*:*:*:*"
    cve = _cve([])
    cve["configurations"] = [
        _and_config(
            {"vulnerable": True, "criteria": fw},
            {
                "vulnerable": False,
                "criteria": "cpe:2.3:h:dlink:dir-600:-:*:*:*:*:*:*:*",
            },
        )
    ]
    entry = {"vendor": "d-link", "model": "DIR-300", "cves": [cve]}
    assert applicable_cves_for_version("1.0", entry) == ([], [cve])


def test_configuration_that_never_mentions_target_does_not_apply() -> None:
    """Uma CVE listada para varios modelos traz uma config por modelo. As dos
    outros modelos nao se aplicam; nao podem deixar o resultado indeterminado."""
    other_fw = "cpe:2.3:o:dlink:dir-600_firmware:*:*:*:*:*:*:*:*"
    other_hw = "cpe:2.3:h:dlink:dir-600:-:*:*:*:*:*:*:*"
    target_fw = "cpe:2.3:o:dlink:dir-300_firmware:*:*:*:*:*:*:*:*"
    cve = _cve([])
    cve["configurations"] = [
        _and_config(
            {"vulnerable": True, "criteria": other_fw},
            {"vulnerable": False, "criteria": other_hw},
        ),
        {
            "nodes": [
                {
                    "cpeMatch": [
                        {
                            "vulnerable": True,
                            "criteria": target_fw,
                            "versionEndExcluding": "2.0",
                        }
                    ]
                }
            ]
        },
    ]
    entry = {"vendor": "d-link", "model": "DIR-300", "cves": [cve]}
    assert applicable_cves_for_version("1.0", entry) == ([cve], [])
    assert applicable_cves_for_version("2.0", entry) == ([], [])


def test_cve_with_only_other_products_does_not_apply() -> None:
    cve = _cve([])
    cve["configurations"] = [
        _and_config(
            {
                "vulnerable": True,
                "criteria": "cpe:2.3:o:dlink:dir-600_firmware:*:*:*:*:*:*:*:*",
            },
        )
    ]
    entry = {"vendor": "d-link", "model": "DIR-300", "cves": [cve]}
    assert applicable_cves_for_version("1.0", entry) == ([], [])


def test_configuration_with_unparseable_criteria_stays_indeterminate() -> None:
    """Sem conseguir ler a CPE nao ha como afirmar que a config e de outro
    produto."""
    cve = _cve([])
    cve["configurations"] = [
        _and_config({"vulnerable": True, "criteria": "cpe:2.3:o:broken"})
    ]
    entry = {"vendor": "d-link", "model": "DIR-300", "cves": [cve]}
    assert applicable_cves_for_version("1.0", entry) == ([], [cve])


def test_and_with_other_vulnerable_product_is_indeterminate() -> None:
    target_fw = "cpe:2.3:o:dlink:dir-300_firmware:*:*:*:*:*:*:*:*"
    cve = _cve([])
    cve["configurations"] = [
        {
            "nodes": [
                {
                    "operator": "AND",
                    "cpeMatch": [
                        {
                            "vulnerable": True,
                            "criteria": target_fw,
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
    assert applicable_cves_for_version("1.0", entry) == ([], [cve])


def test_vendor_suffix_is_not_silently_discarded_for_numeric_range() -> None:
    cve = _cve([{"versionEndExcluding": "7.11"}])
    assert applicable_cves_for_version("7.10(ABTG.4)C0", {"cves": [cve]}) == ([], [cve])


def test_indeterminate_is_a_label_quality_state() -> None:
    assert LABEL_INDETERMINATE not in {
        LABEL_NO_KNOWN_CVE,
        LABEL_KNOWN_CVE,
        LABEL_CRITICAL_CVE,
    }
