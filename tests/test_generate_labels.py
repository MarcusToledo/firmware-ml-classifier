from __future__ import annotations

import hashlib
import json
import logging
import re
import sys
from pathlib import Path

import pandas as pd
import pytest

from scripts.generate_labels import _aggregate_firmware_label, _lookup_cve_entry, main
from src.labeling.cve_labels import (
    LABEL_CRITICAL_CVE,
    LABEL_INDETERMINATE,
    LABEL_KNOWN_CVE,
    LABEL_NO_KNOWN_CVE,
    CveLabelThresholds,
)


def _cve(cve_id: str, score: float = 7.5) -> dict:
    return {"id": cve_id, "cvss_max": score, "severity": "HIGH", "configurations": []}


def _cache_entry(cves: list[dict]) -> dict:
    return {
        "source": "keyword",
        "schema_version": 3,
        "fetched_at": "2026-09-26T00:00:00+00:00",
        "cves": cves,
    }


def _write_inputs(
    tmp_path: Path, rows: list[dict], cache: dict, suffix: str = ".csv"
) -> tuple[Path, Path]:
    features = tmp_path / f"features{suffix}"
    cache_path = tmp_path / "cves.json"
    if suffix == ".parquet":
        pd.DataFrame(rows).to_parquet(features, index=False)
    else:
        pd.DataFrame(rows).to_csv(features, index=False)
    cache_path.write_text(json.dumps(cache), encoding="utf-8")
    return features, cache_path


def _invoke(monkeypatch: pytest.MonkeyPatch, *args: str) -> None:
    monkeypatch.setattr(sys, "argv", ["generate-labels", *args])
    main()


def _run_cli(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    rows: list[dict],
    cache: dict,
) -> pd.DataFrame:
    features, cache_path = _write_inputs(tmp_path, rows, cache)
    output = tmp_path / "labels.csv"
    _invoke(
        monkeypatch,
        "--features",
        str(features),
        "--cves",
        str(cache_path),
        "--output",
        str(output),
    )
    return pd.read_csv(output)


def test_lookup_normalizes_identity_and_rejects_old_cache() -> None:
    entry = _cache_entry([_cve("CVE-1")])
    row = {"meta_brand": " DLink ", "meta_model": " DIR300 "}
    assert _lookup_cve_entry(row, {"dlink/dir300": entry}) == entry
    with pytest.raises(ValueError, match="dlink/dir300"):
        _lookup_cve_entry(row, {"dlink/dir300": {"cve_total": 1}})
    with pytest.raises(ValueError, match="schema"):
        _lookup_cve_entry(row, {"dlink/dir300": {**entry, "schema_version": 1}})
    with pytest.raises(ValueError, match="schema"):
        _lookup_cve_entry(row, {"dlink/dir300": {**entry, "schema_version": 2}})
    with pytest.raises(ValueError, match="fetched_at.*dlink/dir300"):
        _lookup_cve_entry(
            row,
            {
                "dlink/dir300": {
                    key: value for key, value in entry.items() if key != "fetched_at"
                }
            },
        )
    with pytest.raises(ValueError, match="schema"):
        # Entrada com "cves" mas sem schema_version deve falhar igual a
        # fetch_cves.py, nao ser aceita silenciosamente como schema 2.
        _lookup_cve_entry(row, {"dlink/dir300": {"cves": []}})


def test_lookup_missing_pair_fails_instead_of_becoming_negative() -> None:
    with pytest.raises(ValueError, match="unknown/x1"):
        _lookup_cve_entry({"meta_brand": "unknown", "meta_model": "x1"}, {})


def test_aggregate_all_aliases_with_only_indeterminate_cves() -> None:
    label, stats = _aggregate_firmware_label(
        [
            ([], [_cve("CVE-1")]),
            ([], [_cve("CVE-2", 9.8)]),
        ],
        CveLabelThresholds(),
    )
    assert label == LABEL_INDETERMINATE
    assert stats["cve_total"] == 0
    assert stats["cvss_max"] == 0.0


def test_aggregate_critical_applicable_with_indeterminate_cve() -> None:
    label, stats = _aggregate_firmware_label(
        [
            (
                [_cve("CVE-APPLICABLE", 9.8)],
                [_cve("CVE-INDETERMINATE", 7.5)],
            )
        ],
        CveLabelThresholds(),
    )
    assert label == LABEL_CRITICAL_CVE
    assert stats["cve_total"] == 1
    assert stats["cvss_max"] == 9.8


def test_aggregate_known_applicable_with_critical_indeterminate_cve() -> None:
    label, stats = _aggregate_firmware_label(
        [
            (
                [_cve("CVE-APPLICABLE")],
                [_cve("CVE-INDETERMINATE", 9.8)],
            )
        ],
        CveLabelThresholds(),
    )
    assert label == LABEL_INDETERMINATE
    assert stats["cve_total"] == 1
    assert stats["cvss_max"] == 7.5


def test_aggregate_known_applicable_with_only_known_indeterminate_cves() -> None:
    label, stats = _aggregate_firmware_label(
        [
            (
                [_cve("CVE-APPLICABLE")],
                [_cve("CVE-INDETERMINATE", 8.9)],
            )
        ],
        CveLabelThresholds(),
    )
    assert label == LABEL_KNOWN_CVE
    assert stats["cve_total"] == 1
    assert stats["cvss_max"] == 7.5


def test_aggregate_empty_evidence_is_valid_negative() -> None:
    label, stats = _aggregate_firmware_label([([], [])], CveLabelThresholds())
    assert label == LABEL_NO_KNOWN_CVE
    assert stats["cve_total"] == 0


def test_aggregate_keeps_indeterminate_cve_when_an_alias_has_no_evidence() -> None:
    label, stats = _aggregate_firmware_label(
        [
            ([], [_cve("CVE-INDETERMINATE", 9.8)]),
            ([], []),
        ],
        CveLabelThresholds(),
    )
    assert label == LABEL_INDETERMINATE
    assert stats["cve_total"] == 0


def test_aggregate_applicable_cve_overrides_same_indeterminate_cve() -> None:
    label, stats = _aggregate_firmware_label(
        [
            ([_cve("CVE-SAME")], []),
            ([], [_cve("CVE-SAME", 9.8)]),
        ],
        CveLabelThresholds(),
    )
    assert label == LABEL_KNOWN_CVE
    assert stats["cve_total"] == 1
    assert stats["cvss_max"] == 7.5


def test_aggregate_deduplicates_applicable_cve_between_aliases() -> None:
    cve = _cve("CVE-SAME")
    label, stats = _aggregate_firmware_label(
        [([cve], []), ([cve], [])],
        CveLabelThresholds(),
    )

    assert label == LABEL_KNOWN_CVE
    assert stats["cve_total"] == 1


def test_cli_filters_version_before_aggregating_aliases(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    rows = [
        {
            "firmware_id": "shared",
            "meta_path": "/dataset/raw/dlink/dir300/fw_2.0.bin",
            "meta_brand": "dlink",
            "meta_model": "dir300",
            "meta_version": "2.0",
            "meta_version_source": "filename",
            "entropy": 7.9,
        },
        {
            "firmware_id": "shared",
            "meta_path": "/dataset/raw/dlink/dir300b_1.0/fw.bin",
            "meta_brand": "dlink",
            "meta_model": "dir300b",
            "meta_version": "1.0",
            "meta_version_source": "directory",
            "entropy": 0.1,
        },
    ]
    labels = _run_cli(
        tmp_path,
        monkeypatch,
        rows,
        {
            "dlink/dir300": _cache_entry(
                [
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
                ]
            ),
            "dlink/dir300b": _cache_entry([_cve("CVE-CURRENT")]),
        },
    )
    assert labels["security_level"].tolist() == ["cve_conhecida", "cve_conhecida"]
    assert labels["cve_total"].tolist() == [1, 1]
    assert "entropy" not in labels.columns
    assert labels["version_source"].tolist() == ["filename", "directory"]


def test_cli_missing_version_writes_indeterminate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    labels = _run_cli(
        tmp_path,
        monkeypatch,
        [
            {
                "firmware_id": "fw",
                "meta_path": "/dataset/raw/dlink/dir300/fw.bin",
                "meta_brand": "dlink",
                "meta_model": "dir300",
                "meta_version": None,
                "meta_version_source": None,
            }
        ],
        {"dlink/dir300": _cache_entry([_cve("CVE-1", 9.8)])},
    )
    assert labels["security_level"].tolist() == [LABEL_INDETERMINATE]
    assert labels["version_source"].isna().tolist() == [True]


def test_cli_rejects_version_divergent_from_meta_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with pytest.raises(ValueError) as exc_info:
        _run_cli(
            tmp_path,
            monkeypatch,
            [
                {
                    "firmware_id": "fw-divergent",
                    "meta_path": "/dataset/raw/dlink/dir300_2.0/fw.bin",
                    "meta_brand": "dlink",
                    "meta_model": "dir300",
                    "meta_version": "1.0",
                    "meta_version_source": "directory",
                }
            ],
            {"dlink/dir300": _cache_entry([])},
        )

    message = str(exc_info.value)
    assert "firmware_id=fw-divergent" in message
    assert "meta_version='1.0'" in message
    assert "versao inferida='2.0'" in message
    assert "reextraia as features com --label-from-path" in message


def test_cli_rejects_missing_version_when_meta_path_has_version(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with pytest.raises(ValueError) as exc_info:
        _run_cli(
            tmp_path,
            monkeypatch,
            [
                {
                    "firmware_id": "fw-missing-version",
                    "meta_path": "/dataset/raw/dlink/dir300_2.0/fw.bin",
                    "meta_brand": "dlink",
                    "meta_model": "dir300",
                    "meta_version": None,
                    "meta_version_source": "directory",
                }
            ],
            {"dlink/dir300": _cache_entry([])},
        )

    message = str(exc_info.value)
    assert "firmware_id=fw-missing-version" in message
    assert "versao inferida='2.0'" in message
    assert "meta_version=None" in message


def test_cli_reports_missing_identity_before_version_divergence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with pytest.raises(ValueError, match="meta_brand/meta_model ausentes"):
        _run_cli(
            tmp_path,
            monkeypatch,
            [
                {
                    "firmware_id": "fw-without-label",
                    "meta_path": "/dataset/raw/dlink/dir300_2.0/fw.bin",
                    "meta_brand": None,
                    "meta_model": None,
                    "meta_version": "1.0",
                    "meta_version_source": "directory",
                }
            ],
            {},
        )


def test_cli_rejects_missing_meta_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with pytest.raises(ValueError, match="meta_path ausente"):
        _run_cli(
            tmp_path,
            monkeypatch,
            [
                {
                    "firmware_id": "fw-missing-path",
                    "meta_path": None,
                    "meta_brand": "dlink",
                    "meta_model": "dir300",
                    "meta_version": None,
                    "meta_version_source": None,
                }
            ],
            {},
        )


def test_cli_rejects_duplicate_rows(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    row = {
        "firmware_id": "fw",
        "meta_path": "/dataset/raw/dlink/dir300_1.0/fw.bin",
        "meta_brand": "dlink",
        "meta_model": "dir300",
        "meta_version": "1.0",
        "meta_version_source": "directory",
    }
    with pytest.raises(ValueError, match="duplicad"):
        _run_cli(
            tmp_path,
            monkeypatch,
            [row, row],
            {"dlink/dir300": _cache_entry([])},
        )


def test_cli_rejects_version_source_divergent_from_meta_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    row = {
        "firmware_id": "fw-divergent",
        "meta_path": "/dataset/raw/dlink/dir300/fw_2.0.bin",
        "meta_brand": "dlink",
        "meta_model": "dir300",
        "meta_version": "2.0",
        "meta_version_source": "directory",
    }
    with pytest.raises(ValueError) as exc_info:
        _run_cli(tmp_path, monkeypatch, [row], {"dlink/dir300": _cache_entry([])})
    message = str(exc_info.value)
    assert "firmware_id=fw-divergent" in message
    assert "origem inferida='filename'" in message
    assert "meta_version_source='directory'" in message
    assert "reextraia as features com --label-from-path" in message


def test_cli_rejects_missing_version_source_when_path_has_one(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    row = {
        "firmware_id": "fw-missing-source",
        "meta_path": "/dataset/raw/dlink/dir300/fw_2.0.bin",
        "meta_brand": "dlink",
        "meta_model": "dir300",
        "meta_version": "2.0",
        "meta_version_source": None,
    }
    with pytest.raises(ValueError, match="meta_version_source=None"):
        _run_cli(tmp_path, monkeypatch, [row], {"dlink/dir300": _cache_entry([])})


@pytest.mark.parametrize("suffix", [".csv", ".parquet"], ids=["csv", "parquet"])
def test_cli_rejects_features_without_version_source_column(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, suffix: str
) -> None:
    rows = [
        {
            "firmware_id": "fw",
            "meta_path": "/dataset/raw/dlink/dir300/fw_2.0.bin",
            "meta_brand": "dlink",
            "meta_model": "dir300",
            "meta_version": "2.0",
        }
    ]
    features, cache_path = _write_inputs(
        tmp_path, rows, {"dlink/dir300": _cache_entry([])}, suffix
    )
    with pytest.raises(ValueError) as exc_info:
        _invoke(
            monkeypatch,
            "--features",
            str(features),
            "--cves",
            str(cache_path),
            "--dry-run",
        )
    assert "meta_version_source" in str(exc_info.value)
    assert "reextraia as features com --label-from-path" in str(exc_info.value)


def _audit_inputs() -> tuple[list[dict], dict]:
    rows = [
        {
            "firmware_id": "shared",
            "meta_path": "/dataset/raw/dlink/dir300/fw_2.0.bin",
            "meta_brand": "dlink",
            "meta_model": "dir300",
            "meta_version": "2.0",
            "meta_version_source": "filename",
        },
        {
            "firmware_id": "shared",
            "meta_path": "/dataset/raw/dlink/dir300b_1.0/fw.bin",
            "meta_brand": "dlink",
            "meta_model": "dir300b",
            "meta_version": "1.0",
            "meta_version_source": "directory",
        },
        {
            "firmware_id": "solo",
            "meta_path": "/dataset/raw/dlink/dir600/fw.bin",
            "meta_brand": "dlink",
            "meta_model": "dir600",
            "meta_version": None,
            "meta_version_source": None,
        },
    ]
    old = {
        **_cve("CVE-OLD", 9.8),
        "configurations": [
            {
                "nodes": [
                    {"cpeMatch": [{"vulnerable": True, "versionEndExcluding": "2.0"}]}
                ]
            }
        ],
    }
    cache = {
        "dlink/dir300": _cache_entry([old]),
        "dlink/dir300b": _cache_entry([_cve("CVE-CURRENT")]),
        "dlink/dir600": _cache_entry([_cve("CVE-B"), _cve("CVE-A")]),
    }
    return rows, cache


def test_cli_records_aliases_strategy_and_per_alias_cves(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO, logger="scripts.generate_labels")
    rows, cache = _audit_inputs()
    labels = _run_cli(tmp_path, monkeypatch, rows, cache)
    assert labels.columns.tolist() == [
        "firmware_id",
        "meta_path",
        "vendor",
        "model",
        "version",
        "version_source",
        "security_level",
        "cve_total",
        "cvss_max",
        "label_strategy",
        "alias_count",
    ]
    assert labels["label_strategy"].tolist() == [
        "agregacao_conservadora",
        "agregacao_conservadora",
        "alias_unico",
    ]
    assert labels["alias_count"].tolist() == [2, 2, 1]
    audit = [
        json.loads(line)
        for line in (tmp_path / "labels_aliases.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    assert [record["firmware_id"] for record in audit] == ["shared", "solo"]
    assert audit[0]["versions_differ"] is True
    assert audit[0]["aliases"][0]["applicable_cves"] == []
    assert audit[0]["aliases"][0]["indeterminate_cves"] == []
    assert audit[0]["aliases"][1]["applicable_cves"] == ["CVE-CURRENT"]
    assert audit[1]["aliases"][0]["indeterminate_cves"] == ["CVE-A", "CVE-B"]
    assert audit[1]["aliases"][0]["version"] is None
    assert audit[1]["versions_differ"] is False
    assert (
        "1 firmware_id com mais de um alias; 1 com aliases de mais de um "
        "modelo; 1 com aliases de versões diferentes"
    ) in caplog.text


def test_cli_marks_versions_differ_for_null_against_value(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    rows = [
        {
            "firmware_id": "shared",
            "meta_path": "/dataset/raw/dlink/dir300_1.0/fw.bin",
            "meta_brand": "dlink",
            "meta_model": "dir300",
            "meta_version": "1.0",
            "meta_version_source": "directory",
        },
        {
            "firmware_id": "shared",
            "meta_path": "/dataset/raw/dlink/dir300/fw.bin",
            "meta_brand": "dlink",
            "meta_model": "dir300",
            "meta_version": None,
            "meta_version_source": None,
        },
    ]
    _run_cli(tmp_path, monkeypatch, rows, {"dlink/dir300": _cache_entry([])})
    audit = json.loads(
        (tmp_path / "labels_aliases.jsonl").read_text(encoding="utf-8").splitlines()[0]
    )
    assert audit["versions_differ"] is True


def test_cli_default_output_writes_table_and_auxiliaries(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    rows, cache = _audit_inputs()
    features, cache_path = _write_inputs(tmp_path, rows, cache)
    monkeypatch.chdir(tmp_path)
    _invoke(monkeypatch, "--features", str(features), "--cves", str(cache_path))
    output_dir = tmp_path / "dataset/processed"
    assert (output_dir / "labels_v2.csv").exists()
    assert (output_dir / "labels_v2_aliases.jsonl").exists()
    meta = json.loads((output_dir / "labels_v2.meta.json").read_text("utf-8"))
    assert list(meta) == [
        "critical_cvss",
        "features_path",
        "features_sha256",
        "cves_path",
        "cves_sha256",
        "code_commit",
        "generated_at",
    ]
    assert meta["features_sha256"] == hashlib.sha256(features.read_bytes()).hexdigest()
    assert meta["cves_sha256"] == hashlib.sha256(cache_path.read_bytes()).hexdigest()
    assert meta["critical_cvss"] == 9.0
    assert re.fullmatch(r"[0-9a-f]{40}(-dirty)?", meta["code_commit"])


def test_cli_explicit_output_places_auxiliaries_beside_table(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    rows, cache = _audit_inputs()
    features, cache_path = _write_inputs(tmp_path, rows, cache)
    output = tmp_path / "out/custom.csv"
    _invoke(
        monkeypatch,
        "--features",
        str(features),
        "--cves",
        str(cache_path),
        "--output",
        str(output),
    )
    assert (tmp_path / "out/custom.meta.json").exists()
    assert (tmp_path / "out/custom_aliases.jsonl").exists()


def test_cli_dry_run_writes_nothing_but_logs_alias_counts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO, logger="scripts.generate_labels")
    rows, cache = _audit_inputs()
    features, cache_path = _write_inputs(tmp_path, rows, cache)
    output = tmp_path / "out/labels.csv"
    _invoke(
        monkeypatch,
        "--features",
        str(features),
        "--cves",
        str(cache_path),
        "--output",
        str(output),
        "--dry-run",
    )
    assert not output.parent.exists()
    assert "Aliases: 1 firmware_id com mais de um alias" in caplog.text


def test_cli_rerun_reproduces_outputs_except_generated_at(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    rows, cache = _audit_inputs()
    features, cache_path = _write_inputs(tmp_path, rows, cache)
    for name in ("run1", "run2"):
        _invoke(
            monkeypatch,
            "--features",
            str(features),
            "--cves",
            str(cache_path),
            "--output",
            str(tmp_path / name / "labels.csv"),
        )
    for name in ("labels.csv", "labels_aliases.jsonl"):
        assert (tmp_path / "run1" / name).read_bytes() == (
            tmp_path / "run2" / name
        ).read_bytes()
    metadata = [
        json.loads((tmp_path / name / "labels.meta.json").read_text("utf-8"))
        for name in ("run1", "run2")
    ]
    for item in metadata:
        item.pop("generated_at")
    assert metadata[0] == metadata[1]
