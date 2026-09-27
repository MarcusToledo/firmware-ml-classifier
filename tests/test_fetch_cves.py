from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from unittest.mock import patch
from urllib.error import URLError

import pandas as pd
import pytest

from scripts.fetch_cves import (
    _parse_args,
    _should_save,
    extract_cvss,
    extract_pairs,
    fetch_cves_for_pair,
    main,
    normalize_model,
    normalize_vendor,
    resolve_cpe_name,
)

# ---------------------------------------------------------------------------
# normalize_vendor / normalize_model
# ---------------------------------------------------------------------------
# TODO: mover essas regras de normalização para um módulo/script separado, para
# centralizá-las e não poluir os módulos. Estes testes acompanham essa mudança.


def test_normalize_vendor_dlink() -> None:
    assert normalize_vendor("dlink") == "d-link"


def test_normalize_vendor_tplink() -> None:
    assert normalize_vendor("tplink") == "tp-link"


def test_normalize_vendor_tp_link_underscore() -> None:
    """dataset/raw/ tem tanto 'tplink/' quanto 'tp_link/' para o mesmo
    fabricante (lotes de ingestao diferentes). As duas grafias devem
    normalizar para o mesmo termo de busca na NVD."""
    assert normalize_vendor("tp_link") == "tp-link"


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


def test_normalize_model_underscore_separated_words() -> None:
    """Modelos da pasta tplink/ e belkin/ usam underscore entre as partes. A NVD
    escreve com hifen, entao a consulta nao pode mandar o underscore."""
    assert normalize_model("td_w8950n") == "TD-W8950N"
    assert normalize_model("tl_wr702n") == "TL-WR702N"
    assert normalize_model("archer_c20i") == "ARCHER-C20I"
    assert normalize_model("dx_wgrtr") == "DX-WGRTR"
    assert normalize_model("f6d4230_4_bc") == "F6D4230-4-BC"


def test_normalize_model_never_sends_underscore() -> None:
    for model in ("tl_pa4010p_tkit", "tl_sg2109web", "dgs_1210_48", "f5d7230_4"):
        assert "_" not in normalize_model(model)


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
# extract_pairs
# ---------------------------------------------------------------------------


def test_extract_pairs_dedupes_and_normalizes() -> None:
    """Should dedupe, lowercase, and strip whitespace from pairs."""
    df = pd.DataFrame(
        {
            "meta_brand": ["Netgear", "netgear", " TP-Link "],
            "meta_model": ["DIR-300", "dir-300", "AC1750"],
        }
    )
    assert extract_pairs(df) == [("netgear", "dir-300"), ("tp-link", "ac1750")]


def test_extract_pairs_skips_missing_values() -> None:
    """Rows with empty or NaN brand/model should be skipped."""
    df = pd.DataFrame(
        {
            "meta_brand": ["netgear", "", None, "dlink"],
            "meta_model": ["dir-300", "x1000", "y2000", None],
        }
    )
    assert extract_pairs(df) == [("netgear", "dir-300")]


def test_extract_pairs_empty_dataframe() -> None:
    """Empty dataframe should return an empty list."""
    df = pd.DataFrame({"meta_brand": [], "meta_model": []})
    assert extract_pairs(df) == []


def test_extract_pairs_sorted() -> None:
    """Result should be sorted for deterministic ordering."""
    df = pd.DataFrame(
        {
            "meta_brand": ["zyxel", "asus"],
            "meta_model": ["m1", "m2"],
        }
    )
    assert extract_pairs(df) == [("asus", "m2"), ("zyxel", "m1")]


# ---------------------------------------------------------------------------
# _should_save
# ---------------------------------------------------------------------------


def test_should_save_at_interval() -> None:
    """Should flush exactly on multiples of the interval."""
    assert _should_save(10, interval=10) is True
    assert _should_save(20, interval=10) is True


def test_should_save_between_intervals() -> None:
    """Should not flush between interval boundaries."""
    assert _should_save(1, interval=10) is False
    assert _should_save(9, interval=10) is False
    assert _should_save(11, interval=10) is False


def test_fetch_keyword_retains_cve_and_configurations() -> None:
    cve = {
        "id": "CVE-2020-1111",
        "metrics": {
            "cvssMetricV31": [
                {"cvssData": {"baseScore": 9.8, "baseSeverity": "CRITICAL"}}
            ]
        },
        "configurations": [
            {
                "nodes": [
                    {
                        "cpeMatch": [
                            {
                                "vulnerable": True,
                                "criteria": (
                                    "cpe:2.3:o:dlink:dir-300_firmware:"
                                    "*:*:*:*:*:*:*:*"
                                ),
                                "versionEndExcluding": "2.0",
                            }
                        ]
                    }
                ]
            }
        ],
    }
    with (
        patch("scripts.fetch_cves.resolve_cpe_name", return_value=(None, [])),
        patch(
            "scripts.fetch_cves._fetch_page",
            return_value={"totalResults": 1, "vulnerabilities": [{"cve": cve}]},
        ),
    ):
        entry = fetch_cves_for_pair("dlink", "dir300", headers={}, delay=0)

    assert entry["source"] == "keyword"
    assert entry["schema_version"] == 3
    assert datetime.fromisoformat(entry["fetched_at"]).utcoffset().total_seconds() == 0
    assert entry["cpe_candidates"] == []
    assert entry["cves"][0]["id"] == "CVE-2020-1111"
    assert entry["cves"][0]["cvss_max"] == 9.8
    assert entry["cves"][0]["configurations"] == cve["configurations"]


def test_resolve_cpe_selects_matching_firmware_and_wildcards_version() -> None:
    products = [
        {"cpe": {"cpeName": "cpe:2.3:o:dlink:other:1.0:*:*:*:*:*:*:*"}},
        {"cpe": {"cpeName": "cpe:2.3:o:dlink:dir-300_firmware:1.2:*:*:*:*:*:*:*"}},
    ]
    with patch(
        "scripts.fetch_cves._fetch_cpe_page", return_value={"products": products}
    ):
        name = resolve_cpe_name("dlink", "dir300", headers={}, delay=0)
    assert name == ("cpe:2.3:o:dlink:dir-300_firmware:*:*:*:*:*:*:*:*", [])


def test_resolve_cpe_generalizes_specific_update_and_edition() -> None:
    specific = "cpe:2.3:o:dlink:dir-300_firmware:1.2:rev1:home:*:*:*:*:*"
    with patch(
        "scripts.fetch_cves._fetch_cpe_page",
        return_value={"products": [{"cpe": {"cpeName": specific}}]},
    ):
        name = resolve_cpe_name("dlink", "dir300", headers={}, delay=0)
    assert name == ("cpe:2.3:o:dlink:dir-300_firmware:*:*:*:*:*:*:*:*", [])


def test_fetch_prefers_resolved_cpe_query() -> None:
    with (
        patch(
            "scripts.fetch_cves.resolve_cpe_name",
            return_value=("cpe:2.3:o:dlink:dir-300_firmware:*:*:*:*:*:*:*:*", []),
        ),
        patch(
            "scripts.fetch_cves._fetch_page",
            return_value={"totalResults": 0, "vulnerabilities": []},
        ) as fetch_page,
    ):
        entry = fetch_cves_for_pair("dlink", "dir300", headers={}, delay=0)
    assert entry["source"] == "cpe"
    assert entry["cves"] == []
    assert "virtualMatchString=" in fetch_page.call_args.args[0]


def test_cvss_uses_highest_score_in_preferred_version() -> None:
    """Escolhe a maior pontuação e sua severidade na versão preferida."""
    metrics = {
        "cvssMetricV31": [
            {"cvssData": {"baseScore": 7.5, "baseSeverity": "HIGH"}},
            {"cvssData": {"baseScore": 9.8, "baseSeverity": "CRITICAL"}},
        ],
        "cvssMetricV2": [{"cvssData": {"baseScore": 10.0}}],
    }
    assert extract_cvss({"metrics": metrics}) == (9.8, "CRITICAL")
    assert extract_cvss(
        {
            "metrics": {
                "cvssMetricV2": [
                    {"cvssData": {"baseScore": 3.0}},
                    {"cvssData": {"baseScore": 5.0}, "baseSeverity": "HIGH"},
                ]
            }
        }
    ) == (5.0, "HIGH")


def test_cpe_pagination_preference_and_ambiguity() -> None:
    """Percorre páginas, prioriza software e deduplica versões do mesmo produto."""

    def product(part: str, model: str, version: str) -> dict:
        """Cria uma entrada de dicionário CPE para teste."""
        return {
            "cpe": {"cpeName": f"cpe:2.3:{part}:dlink:{model}:{version}:*:*:*:*:*:*:*"}
        }

    pages = [
        {"totalResults": 4, "products": [product("h", "dir-300", "1.0")]},
        {
            "totalResults": 4,
            "products": [
                product("o", "dir-300_firmware", "1.0"),
                product("o", "dir-300_firmware", "2.0"),
                product("o", "dir300", "1.0"),
            ],
        },
    ]
    with patch("scripts.fetch_cves._fetch_cpe_page", side_effect=pages) as fetch:
        name, candidates = resolve_cpe_name("dlink", "dir300", {}, 0)
    assert name is None
    assert candidates == [
        "cpe:2.3:o:dlink:dir-300_firmware:*:*:*:*:*:*:*:*",
        "cpe:2.3:o:dlink:dir300:*:*:*:*:*:*:*:*",
    ]
    assert fetch.call_args_list[1].args[1] == 1
    with patch(
        "scripts.fetch_cves._fetch_cpe_page",
        return_value={"totalResults": 1, "products": [product("h", "dir-300", "1.0")]},
    ):
        assert resolve_cpe_name("dlink", "dir300", {}, 0) == (
            "cpe:2.3:h:dlink:dir-300:*:*:*:*:*:*:*:*",
            [],
        )
    with (
        patch("scripts.fetch_cves.resolve_cpe_name", return_value=(None, candidates)),
        patch(
            "scripts.fetch_cves._fetch_page",
            return_value={"totalResults": 0, "vulnerabilities": []},
        ) as fetch_page,
    ):
        entry = fetch_cves_for_pair("dlink", "dir300", {}, 0)
    assert entry["source"] == "keyword"
    assert entry["cpe_candidates"] == candidates
    assert "keywordSearch=" in fetch_page.call_args.args[0]


def test_cpe_finds_unique_software_on_second_page() -> None:
    """Escolhe produto de software após página inicial só com hardware."""
    first = {
        "totalResults": 3,
        "products": [{"cpe": {"cpeName": "cpe:2.3:h:dlink:dir-300:1:*:*:*:*:*:*:*"}}],
    }
    second = {
        "totalResults": 3,
        "products": [
            {"cpe": {"cpeName": "cpe:2.3:o:dlink:dir-300_firmware:1:*:*:*:*:*:*:*"}},
            {"cpe": {"cpeName": "cpe:2.3:o:dlink:dir-300_firmware:2:*:*:*:*:*:*:*"}},
        ],
    }
    with patch(
        "scripts.fetch_cves._fetch_cpe_page", side_effect=[first, second]
    ) as fetch:
        assert resolve_cpe_name("dlink", "dir-300", {}, 0) == (
            "cpe:2.3:o:dlink:dir-300_firmware:*:*:*:*:*:*:*:*",
            [],
        )
    assert [call.args[1] for call in fetch.call_args_list] == [0, 1]


def _invoke(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, rows: list[dict], *extra: str
) -> tuple[Path, Path]:
    """Executa o CLI com parquet temporário e devolve os caminhos dos artefatos."""
    features = tmp_path / "features.parquet"
    output = tmp_path / "cache.json"
    pd.DataFrame(rows).to_parquet(features)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "fetch_cves.py",
            "--features",
            str(features),
            "--output",
            str(output),
            "--delay",
            "0",
            *extra,
        ],
    )
    main()
    return features, output


def test_empty_pairs_fail_before_dry_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Recusa a busca sem identidade mesmo em simulação e informa descartes."""
    caplog.set_level("INFO")
    with pytest.raises(SystemExit, match="2"):
        _invoke(
            tmp_path,
            monkeypatch,
            [{"meta_brand": None, "meta_model": "dir300"}],
            "--dry-run",
        )
    assert "Linhas descartadas por fabricante ou modelo nulo ou vazio: 1" in caplog.text
    assert "--label-from-path" in caplog.text
    assert not (tmp_path / "cache.json").exists()


def test_schema_and_metadata_on_success(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Registra cache datado e proveniência completa após consulta."""
    with (
        patch("scripts.fetch_cves.resolve_cpe_name", return_value=(None, [])),
        patch(
            "scripts.fetch_cves._fetch_page",
            return_value={"totalResults": 0, "vulnerabilities": []},
        ),
    ):
        features, output = _invoke(
            tmp_path, monkeypatch, [{"meta_brand": "dlink", "meta_model": "dir300"}]
        )
    entry = json.loads(output.read_text())["dlink/dir300"]
    assert entry["schema_version"] == 3
    assert datetime.fromisoformat(entry["fetched_at"]).utcoffset().total_seconds() == 0
    metadata = json.loads(output.with_name("cache.meta.json").read_text())
    assert metadata["features_path"] == str(features)
    assert metadata["output_path"] == str(output)
    assert len(metadata["features_sha256"]) == 64
    assert metadata["code_commit"]
    assert (
        metadata["pairs_fetched"],
        metadata["pairs_skipped"],
        metadata["pairs_failed"],
    ) == (1, 0, 0)
    assert datetime.fromisoformat(metadata["started_at"]) <= datetime.fromisoformat(
        metadata["finished_at"]
    )


def test_old_schema_rejected_without_force(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Recusa entrada antiga antes de reutilizá-la."""
    output = tmp_path / "cache.json"
    output.write_text(json.dumps({"dlink/dir300": {"schema_version": 2, "cves": []}}))
    with pytest.raises(ValueError, match="schema_version=2; rode com --force"):
        _invoke(
            tmp_path, monkeypatch, [{"meta_brand": "dlink", "meta_model": "dir300"}]
        )


@pytest.mark.parametrize("force", [False, True])
def test_network_failure_persists_without_stale_entry(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    force: bool,
) -> None:
    """Retira evidência velha em consulta forçada e retorna falha nos dois modos."""
    output = tmp_path / "cache.json"
    if force:
        output.write_text(
            json.dumps({"dlink/dir300": {"schema_version": 3, "cves": []}})
        )
    with patch("scripts.fetch_cves.resolve_cpe_name", side_effect=URLError("offline")):
        with pytest.raises(SystemExit, match="1"):
            _invoke(
                tmp_path,
                monkeypatch,
                [{"meta_brand": "dlink", "meta_model": "dir300"}],
                *(["--force"] if force else []),
            )
    assert "dlink/dir300" not in json.loads(output.read_text())
    assert (
        json.loads(output.with_name("cache.meta.json").read_text())["pairs_failed"] == 1
    )


def test_default_output_path(monkeypatch: pytest.MonkeyPatch) -> None:
    """Expõe o caminho canônico no padrão e na ajuda."""

    monkeypatch.setattr(sys, "argv", ["fetch_cves.py", "--features", "x"])
    assert _parse_args().output == "dataset/processed/cve_cache_v2.json"


def test_dry_run_never_writes_metadata(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Lista pares sem criar cache ou metadados."""
    _invoke(
        tmp_path,
        monkeypatch,
        [{"meta_brand": "dlink", "meta_model": "dir300"}],
        "--dry-run",
    )
    assert not (tmp_path / "cache.json").exists()
    assert not (tmp_path / "cache.meta.json").exists()


def test_unexpected_failure_preserves_cache_and_run_metadata(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Registra proveniência e pares consultados antes de exceção inesperada."""
    rows = [
        {"meta_brand": "asus", "meta_model": "r1"},
        {"meta_brand": "dlink", "meta_model": "dir300"},
    ]
    with (
        patch(
            "scripts.fetch_cves.resolve_cpe_name",
            side_effect=[
                (None, []),
                ValueError("resposta inválida"),
            ],
        ),
        patch(
            "scripts.fetch_cves._fetch_page",
            return_value={"totalResults": 0, "vulnerabilities": []},
        ),
    ):
        with pytest.raises(ValueError, match="resposta inválida"):
            _invoke(tmp_path, monkeypatch, rows)
    assert list(json.loads((tmp_path / "cache.json").read_text())) == ["asus/r1"]
    metadata = json.loads((tmp_path / "cache.meta.json").read_text())
    assert metadata["pairs_fetched"] == 1
