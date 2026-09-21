from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
import pytest

from scripts.generate_labels import _aggregate_firmware_label, _lookup_cve_entry, main
from src.labeling.cve_labels import LABEL_INDETERMINATE, CveLabelThresholds


def _cve(cve_id: str, score: float = 7.5) -> dict:
    return {"id": cve_id, "cvss_max": score, "severity": "HIGH", "configurations": []}


def _run_cli(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    rows: list[dict],
    cache: dict,
) -> pd.DataFrame:
    features = tmp_path / "features.csv"
    cache_path = tmp_path / "cves.json"
    output = tmp_path / "labels.csv"
    pd.DataFrame(rows).to_csv(features, index=False)
    cache_path.write_text(json.dumps(cache), encoding="utf-8")
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "generate-labels",
            "--features",
            str(features),
            "--cves",
            str(cache_path),
            "--output",
            str(output),
        ],
    )
    main()
    return pd.read_csv(output)


def test_lookup_normalizes_identity_and_rejects_old_cache() -> None:
    entry = {"source": "keyword", "cves": [_cve("CVE-1")], "schema_version": 2}
    row = {"meta_brand": " DLink ", "meta_model": " DIR300 "}
    assert _lookup_cve_entry(row, {"dlink/dir300": entry}) == entry
    with pytest.raises(ValueError, match="dlink/dir300"):
        _lookup_cve_entry(row, {"dlink/dir300": {"cve_total": 1}})
    with pytest.raises(ValueError, match="schema"):
        _lookup_cve_entry(row, {"dlink/dir300": {**entry, "schema_version": 1}})
    with pytest.raises(ValueError, match="schema"):
        # Entrada com "cves" mas sem schema_version deve falhar igual a
        # fetch_cves.py, nao ser aceita silenciosamente como schema 2.
        _lookup_cve_entry(row, {"dlink/dir300": {"cves": []}})


def test_lookup_missing_pair_fails_instead_of_becoming_negative() -> None:
    with pytest.raises(ValueError, match="unknown/x1"):
        _lookup_cve_entry({"meta_brand": "unknown", "meta_model": "x1"}, {})


def test_aggregate_all_indeterminate() -> None:
    label, stats = _aggregate_firmware_label(
        [([], False), ([], False)], CveLabelThresholds()
    )
    assert label == LABEL_INDETERMINATE
    assert stats == {"cve_total": 0, "cvss_max": 0.0}


def test_aggregate_uses_determinate_alias_and_deduplicates_cves() -> None:
    label, stats = _aggregate_firmware_label(
        [
            ([], False),
            ([_cve("CVE-1"), _cve("CVE-2", 9.8)], True),
            ([_cve("CVE-1")], True),
        ],
        CveLabelThresholds(),
    )
    assert label == "cve_critica"
    assert stats["cve_total"] == 2
    assert stats["cvss_max"] == 9.8


def test_aggregate_valid_negative_result() -> None:
    label, stats = _aggregate_firmware_label([([], True)], CveLabelThresholds())
    assert label == "sem_cve_conhecida"
    assert stats["cve_total"] == 0


def test_cli_filters_version_before_aggregating_aliases(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    rows = [
        {
            "firmware_id": "shared",
            "meta_path": "one.bin",
            "meta_brand": "dlink",
            "meta_model": "dir300",
            "meta_version": "2.0",
            "entropy": 7.9,
        },
        {
            "firmware_id": "shared",
            "meta_path": "two.bin",
            "meta_brand": "dlink",
            "meta_model": "dir300b",
            "meta_version": "1.0",
            "entropy": 0.1,
        },
    ]
    labels = _run_cli(
        tmp_path,
        monkeypatch,
        rows,
        {
            "dlink/dir300": {
                "source": "keyword",
                "schema_version": 2,
                "cves": [
                    {
                        **_cve("CVE-OLD", 9.8),
                        "configurations": [
                            {
                                "nodes": [
                                    {
                                        "cpeMatch": [
                                            {
                                                "vulnerable": True,
                                                "versionEndExcluding": "2.0",
                                            }
                                        ]
                                    }
                                ]
                            }
                        ],
                    }
                ],
            },
            "dlink/dir300b": {
                "source": "keyword",
                "schema_version": 2,
                "cves": [_cve("CVE-CURRENT")],
            },
        },
    )
    assert labels["security_level"].tolist() == ["cve_conhecida", "cve_conhecida"]
    assert labels["cve_total"].tolist() == [1, 1]
    assert "entropy" not in labels.columns


def test_cli_missing_version_writes_indeterminate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    labels = _run_cli(
        tmp_path,
        monkeypatch,
        [
            {
                "firmware_id": "fw",
                "meta_path": "fw.bin",
                "meta_brand": "dlink",
                "meta_model": "dir300",
                "meta_version": None,
            }
        ],
        {
            "dlink/dir300": {
                "source": "keyword",
                "schema_version": 2,
                "cves": [_cve("CVE-1", 9.8)],
            }
        },
    )
    assert labels["security_level"].tolist() == [LABEL_INDETERMINATE]


def test_cli_rejects_duplicate_rows(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    row = {
        "firmware_id": "fw",
        "meta_path": "same.bin",
        "meta_brand": "dlink",
        "meta_model": "dir300",
        "meta_version": "1.0",
    }
    with pytest.raises(ValueError, match="duplicad"):
        _run_cli(
            tmp_path,
            monkeypatch,
            [row, row],
            {"dlink/dir300": {"source": "keyword", "cves": []}},
        )
