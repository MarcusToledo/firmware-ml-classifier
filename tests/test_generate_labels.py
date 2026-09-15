from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
import pytest

from scripts.generate_labels import _lookup_cve_stats, _max_severity, main


def test_lookup_uses_normalized_vendor_model_key() -> None:
    cache = {"dlink/dir300": {"cve_total": 1, "cvss_max": 7.5}}
    row = {"meta_brand": " DLink ", "meta_model": " DIR300 "}
    assert _lookup_cve_stats(row, cache) == cache["dlink/dir300"]


def test_missing_lookup_is_not_a_negative_label() -> None:
    with pytest.raises(ValueError, match="unknown/x1"):
        _lookup_cve_stats({"meta_brand": "unknown", "meta_model": "x1"}, {})


def test_missing_identity_is_rejected() -> None:
    with pytest.raises(ValueError, match="meta_brand/meta_model"):
        _lookup_cve_stats({"meta_brand": None, "meta_model": "x1"}, {})


# ---------------------------------------------------------------------------
# _max_severity
# ---------------------------------------------------------------------------


def test_max_severity_picks_highest_cvss_and_total() -> None:
    """Firmwares byte-identicos reaproveitados sob varios nomes de modelo
    (rebadge) devem herdar a maior severidade encontrada entre os alias,
    nao a do alias que por acaso foi consultado."""
    stats_list = [
        {"cve_total": 0, "cvss_max": 0.0},
        {"cve_total": 19, "cvss_max": 9.8},
        {"cve_total": 4, "cvss_max": 9.8},
    ]
    assert _max_severity(stats_list) == {"cve_total": 19, "cvss_max": 9.8}


def test_max_severity_single_entry_is_unchanged() -> None:
    assert _max_severity([{"cve_total": 3, "cvss_max": 6.5}]) == {
        "cve_total": 3,
        "cvss_max": 6.5,
    }


def test_max_severity_empty_list_defaults_to_zero() -> None:
    assert _max_severity([]) == {"cve_total": 0, "cvss_max": 0.0}


def test_cli_writes_only_cve_based_labels(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    features = tmp_path / "features.csv"
    cache = tmp_path / "cves.json"
    output = tmp_path / "labels.csv"
    pd.DataFrame(
        [
            {
                "firmware_id": "fw1",
                "meta_path": "fw1.bin",
                "meta_brand": "dlink",
                "meta_model": "dir300",
                "entropy": 7.9,
            },
            {
                "firmware_id": "fw2",
                "meta_path": "fw2.bin",
                "meta_brand": "netgear",
                "meta_model": "r7000",
                "entropy": 0.1,
            },
        ]
    ).to_csv(features, index=False)
    cache.write_text(
        json.dumps(
            {
                "dlink/dir300": {"cve_total": 0, "cvss_max": 0.0},
                "netgear/r7000": {"cve_total": 1, "cvss_max": 9.8},
            }
        )
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "generate-labels",
            "--features",
            str(features),
            "--cves",
            str(cache),
            "--output",
            str(output),
        ],
    )

    main()

    labels = pd.read_csv(output)
    assert labels["security_level"].tolist() == ["sem_cve_conhecida", "cve_critica"]
    assert "entropy" not in labels.columns
    assert labels["cve_total"].tolist() == [0, 1]


def test_cli_aggregates_identical_firmware_across_aliases(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """O mesmo binario (mesmo firmware_id) reaproveitado sob dois nomes de
    modelo deve receber o MESMO rotulo, usando a maior severidade entre os
    alias, nao o rotulo do alias que por acaso tem/nao tem CVE pesquisada.
    """
    features = tmp_path / "features.csv"
    cache = tmp_path / "cves.json"
    output = tmp_path / "labels.csv"
    pd.DataFrame(
        [
            {
                "firmware_id": "shared-fw",
                "meta_path": "modelA.bin",
                "meta_brand": "asus",
                "meta_model": "modela",
            },
            {
                "firmware_id": "shared-fw",
                "meta_path": "modelB.bin",
                "meta_brand": "asus",
                "meta_model": "modelb",
            },
        ]
    ).to_csv(features, index=False)
    cache.write_text(
        json.dumps(
            {
                "asus/modela": {"cve_total": 0, "cvss_max": 0.0},
                "asus/modelb": {"cve_total": 19, "cvss_max": 9.8},
            }
        )
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "generate-labels",
            "--features",
            str(features),
            "--cves",
            str(cache),
            "--output",
            str(output),
        ],
    )

    main()

    labels = pd.read_csv(output)
    assert labels["security_level"].tolist() == ["cve_critica", "cve_critica"]
    assert labels["cve_total"].tolist() == [19, 19]
    assert labels["cvss_max"].tolist() == [9.8, 9.8]


def test_cli_rejects_true_duplicate_rows(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Mesmo firmware_id E mesmo meta_path repetidos indicam bug no pipeline
    de extracao (arquivo processado duas vezes), nao um alias legitimo."""
    features = tmp_path / "features.csv"
    cache = tmp_path / "cves.json"
    pd.DataFrame(
        [
            {
                "firmware_id": "fw",
                "meta_path": "same.bin",
                "meta_brand": "b",
                "meta_model": "m",
            },
            {
                "firmware_id": "fw",
                "meta_path": "same.bin",
                "meta_brand": "b",
                "meta_model": "m",
            },
        ]
    ).to_csv(features, index=False)
    cache.write_text(json.dumps({"b/m": {"cve_total": 0, "cvss_max": 0.0}}))
    monkeypatch.setattr(
        sys,
        "argv",
        ["generate-labels", "--features", str(features), "--cves", str(cache)],
    )
    with pytest.raises(ValueError, match="duplicad"):
        main()


def test_cli_rejects_missing_cache(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    features = tmp_path / "features.csv"
    pd.DataFrame(
        [{"firmware_id": "fw", "meta_path": "fw", "meta_brand": "b", "meta_model": "m"}]
    ).to_csv(features, index=False)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "generate-labels",
            "--features",
            str(features),
            "--cves",
            str(tmp_path / "absent.json"),
        ],
    )
    with pytest.raises(FileNotFoundError, match="absent.json"):
        main()
