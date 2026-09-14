from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
import pytest

from scripts.generate_labels import _lookup_cve_stats, main


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
