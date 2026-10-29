"""Testa sorteio, conferência da rubrica, decisão e redação da T13-A (013)."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest
import yaml

from src.evidence.validation import (
    CLASS_FALSE,
    CLASS_INDETERMINATE,
    CLASS_TRUE,
    DECISION_KEEP,
    DECISION_REFORMULATE,
    DECISION_REMOVE,
    DecisionRule,
    allocate,
    build_sample,
    decide,
    finding_key,
    load_annotations,
    load_validation_config,
    render_report,
    summarize,
    wilson_interval,
    write_sample,
)

RULE = DecisionRule(
    confidence=0.95, cut=0.5, min_determined=10, max_indeterminate_fraction=0.5
)


def _finding(detector: str, firmware_id: str, path: str, source: str) -> dict:
    """Monta um achado no formato do JSONL de 002/FR-016."""
    return {
        "firmware_id": firmware_id,
        "path": path,
        "type": "t",
        "source": source,
        "context": f"ctx:{source}",
        "confidence": "low",
        "detector": detector,
        "detector_version": "1.0",
    }


def _population() -> list[dict]:
    """Gera achados com alias, vários fabricantes e um detector pequeno.

    ``api_tokens``: 3 fabricantes, 10 firmwares cada, 3 achados por
    firmware; o firmware ``asus-0`` tem alias em ``asus/b/...``.
    ``crypto_signatures``: 2 firmwares, 4 achados cada.
    """
    records = []
    for vendor in ("asus", "dlink", "netgear"):
        for n in range(10):
            fid = f"{vendor}-{n}"
            paths = [f"{vendor}/m{n}/fw.bin"]
            if fid == "asus-0":
                paths.append("asus/b/alias.bin")
            for path in paths:
                for k in range(3):
                    records.append(_finding("api_tokens", fid, path, f"tok{fid}{k}"))
    for fid, vendor in (("c-1", "belkin"), ("c-2", "dlink")):
        for k in range(4):
            path = f"{vendor}/{fid}/fw.bin"
            records.append(_finding("crypto_signatures", fid, path, f"AES {fid} {k}"))
    return records


def _write_jsonl(path: Path, records: list[dict]) -> None:
    """Grava os achados como JSONL."""
    path.write_text("".join(json.dumps(r) + "\n" for r in records), encoding="utf-8")


def _config(tmp_path: Path, records: list[dict], exclusions: list[dict]) -> Path:
    """Grava JSONL e configuração congelada mínima; retorna o caminho do YAML."""
    findings = tmp_path / "findings.jsonl"
    _write_jsonl(findings, records)
    raw = {
        "findings": findings.as_posix(),
        "sample_dir": (tmp_path / "amostra").as_posix(),
        "reports_dir": (tmp_path / "reports").as_posix(),
        "sampling": {"seed": 7, "target_per_detector": 6},
        "decision": {
            "confidence": 0.95,
            "cut": 0.5,
            "min_determined": 10,
            "max_indeterminate_fraction": 0.5,
        },
        "pilot_exclusions": exclusions,
        "rubric": {
            "version": "1",
            "frozen_at": "2026-10-27",
            "indeterminate_reasons": ["sem_contexto", "truncada"],
            "general_false_positive": {
                "FP-ruido": {"exclude": ["api_tokens"]},
                "FP-assinatura": {"only": ["crypto_signatures"]},
            },
            "detectors": {
                "api_tokens": {
                    "target": "segredo",
                    "verdadeiro": ["AT-1"],
                    "falso": ["FP-hash"],
                    "refs": ["002/FR-011"],
                },
                "crypto_signatures": {
                    "target": "cripto",
                    "verdadeiro": ["CS-1"],
                    "falso": ["FP-palavra"],
                    "subtypes": ["algoritmo_tabela"],
                },
            },
        },
    }
    path = tmp_path / "detector_validation.yaml"
    path.write_text(yaml.safe_dump(raw, allow_unicode=True), encoding="utf-8")
    return path


def _pilot(records: list[dict], index: int) -> list[dict]:
    """Retorna a exclusão do piloto para o registro de posição ``index``."""
    return [{"line": index + 1, "key": finding_key(records[index])}]


# --------------------------------------------------------------------------
# Alocação e sorteio
# --------------------------------------------------------------------------


def test_allocation_redistributes_alphabetically_until_target_or_exhaustion():
    capacity = {"asus": 3, "belkin": 1, "dlink": 4, "netgear": 1, "tp_link": 12}
    allocation, received = allocate(capacity, 20)
    assert allocation == {
        "asus": 3,
        "belkin": 1,
        "dlink": 4,
        "netgear": 1,
        "tp_link": 11,
    }
    assert received == ["tp_link"] * 7

    allocation, _ = allocate({"a": 10, "b": 10, "c": 10}, 20)
    assert allocation == {"a": 7, "b": 7, "c": 6}

    allocation, _ = allocate({"belkin": 1, "dlink": 5, "netgear": 1}, 20)
    assert allocation == {"belkin": 1, "dlink": 5, "netgear": 1}


def test_sample_is_reproducible_one_per_firmware_and_takes_all_small_strata(
    tmp_path: Path,
):
    records = _population()
    config = load_validation_config(_config(tmp_path, records, []))

    first = build_sample(config)
    second = build_sample(config)

    assert first.rows == second.rows
    tokens = [r for r in first.rows if r["detector"] == "api_tokens"]
    crypto = [r for r in first.rows if r["detector"] == "crypto_signatures"]
    assert len(tokens) == 6
    assert len({r["firmware_id"] for r in tokens}) == 6
    assert first.manifest["allocation"]["api_tokens"] == {
        "asus": 2,
        "dlink": 2,
        "netgear": 2,
    }
    assert sorted(r["firmware_id"] for r in crypto) == ["c-1", "c-2"]
    assert first.manifest["population"]["crypto_signatures"]["belkin"] == {
        "firmwares": 1,
        "achados": 4,
    }


def test_alias_is_represented_by_smallest_path_and_pilot_copies_are_excluded(
    tmp_path: Path,
):
    records = _population()
    alias_index = next(
        i for i, r in enumerate(records) if r["path"] == "asus/b/alias.bin"
    )
    config = load_validation_config(
        _config(tmp_path, records, _pilot(records, alias_index))
    )

    result = build_sample(config)

    assert result.manifest["pilot_excluded_findings"] == 2
    assert result.manifest["population"]["api_tokens"]["asus"]["achados"] == 29
    excluded_source = records[alias_index]["source"]
    assert all(row["source"] != excluded_source for row in result.rows)
    assert all(
        row["path"] == "asus/b/alias.bin"
        for row in result.rows
        if row["firmware_id"] == "asus-0"
    )


def test_divergent_alias_or_wrong_pilot_key_fails_before_sampling(tmp_path: Path):
    records = _population()
    records.append(_finding("api_tokens", "asus-0", "asus/b/alias.bin", "extra"))
    config = load_validation_config(_config(tmp_path, records, []))
    with pytest.raises(ValueError, match="Aliases divergentes"):
        build_sample(config)

    records = _population()
    wrong = [{"line": 1, "key": finding_key(records[1])}]
    config = load_validation_config(_config(tmp_path, records, wrong))
    with pytest.raises(ValueError, match="piloto não conferem"):
        build_sample(config)


def test_write_sample_refuses_to_overwrite_existing_draw(tmp_path: Path):
    config = load_validation_config(_config(tmp_path, _population(), []))
    result = build_sample(config)
    write_sample(result, config.sample_dir)
    with pytest.raises(FileExistsError):
        write_sample(result, config.sample_dir)


# --------------------------------------------------------------------------
# Wilson e decisão
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("n_true", "n_false", "n_ind", "expected"),
    [
        (15, 5, 0, DECISION_KEEP),
        (14, 6, 0, DECISION_REFORMULATE),
        (5, 15, 0, DECISION_REMOVE),
        (6, 14, 0, DECISION_REFORMULATE),
        (7, 0, 0, DECISION_REFORMULATE),
        (10, 0, 11, DECISION_REFORMULATE),
        (0, 0, 0, DECISION_REFORMULATE),
    ],
)
def test_decision_rule_boundaries(n_true, n_false, n_ind, expected):
    decision, _, _ = decide(n_true, n_false, n_ind, RULE)
    assert decision == expected


def test_wilson_matches_reference_and_handles_zero_denominator():
    low, high = wilson_interval(15, 20, 0.95)
    assert low == pytest.approx(0.5313, abs=1e-4)
    assert high == pytest.approx(0.8881, abs=1e-4)
    assert wilson_interval(0, 0, 0.95) is None


# --------------------------------------------------------------------------
# Anotação e relatório
# --------------------------------------------------------------------------


def _annotate(config_path: Path, edit) -> None:
    """Sorteia, anota todos os itens como VC válidos e aplica ``edit``."""
    config = load_validation_config(config_path)
    write_sample(build_sample(config), config.sample_dir)
    sample = config.sample_dir / "amostra.csv"
    with sample.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    for row in rows:
        crypto = row["detector"] == "crypto_signatures"
        row.update(
            classe=CLASS_TRUE,
            criterio="CS-1" if crypto else "AT-1",
            subtipo="algoritmo_tabela" if crypto else "",
            justificativa="contexto de segredo",
            data="2026-10-28",
        )
    edit(rows)
    with sample.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"classe": CLASS_FALSE, "criterio": "AT-1"}, "critério 'AT-1'"),
        ({"classe": CLASS_FALSE, "criterio": "FP-ruido"}, "critério 'FP-ruido'"),
        ({"classe": CLASS_INDETERMINATE, "criterio": "IND"}, "motivo_ind"),
        ({"data": "2026-10-26"}, "anterior ao congelamento"),
        ({"justificativa": " "}, "justificativa vazia"),
        ({"rubrica_versao": "0"}, "diverge do manifesto"),
        ({"source": "editado"}, "diverge do manifesto"),
        ({"detector": "crypto_signatures"}, "diverge do manifesto"),
        ({"fabricante": "outro"}, "diverge do manifesto"),
        ({"firmware_id": "outro"}, "diverge do manifesto"),
        ({"context": "editado"}, "diverge do manifesto"),
    ],
)
def test_report_rejects_annotation_outside_frozen_rubric(
    tmp_path: Path, change, message
):
    config_path = _config(tmp_path, _population(), [])

    def edit(rows):
        target = next(r for r in rows if r["detector"] == "api_tokens")
        target.update(change)

    _annotate(config_path, edit)
    with pytest.raises(ValueError, match=message):
        load_annotations(load_validation_config(config_path))


def test_report_requires_subtype_for_crypto_true_and_accepts_signature_fp(
    tmp_path: Path,
):
    config_path = _config(tmp_path, _population(), [])

    def edit(rows):
        crypto = [r for r in rows if r["detector"] == "crypto_signatures"]
        crypto[0].update(subtipo="")
        crypto[1].update(classe=CLASS_FALSE, criterio="FP-assinatura", subtipo="")

    _annotate(config_path, edit)
    with pytest.raises(ValueError) as error:
        load_annotations(load_validation_config(config_path))
    assert "1 anotações inválidas" in str(error.value)
    assert "subtipo" in str(error.value)


def test_report_fails_if_config_changed_after_draw(tmp_path: Path):
    config_path = _config(tmp_path, _population(), [])
    _annotate(config_path, lambda rows: None)
    config_path.write_text(
        config_path.read_text(encoding="utf-8") + "# mudança\n", encoding="utf-8"
    )
    with pytest.raises(ValueError, match="mudou depois do sorteio"):
        load_annotations(load_validation_config(config_path))


def test_report_redacts_tokens_and_marks_absent_detectors(tmp_path: Path):
    config_path = _config(tmp_path, _population(), [])
    _annotate(config_path, lambda rows: None)
    config = load_validation_config(config_path)
    rows, manifest = load_annotations(config)

    results = summarize(rows, config.decision)
    report = render_report(results, rows, manifest, config, "2026-10-28T00:00:00")

    by_detector = {r.detector: r for r in results}
    assert by_detector["api_tokens"].n_true == 6
    assert by_detector["api_tokens"].decision == DECISION_REFORMULATE
    assert by_detector["telnetd"].decision is None
    assert by_detector["telnetd"].interval is None
    assert "ausente na população" in report
    token_sources = [r["source"] for r in rows if r["detector"] == "api_tokens"]
    assert all(source not in report for source in token_sources)
    assert "<redigido:len=" in report


def test_unknown_detector_in_rubric_is_rejected(tmp_path: Path):
    path = _config(tmp_path, _population(), [])
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    raw["rubric"]["detectors"]["inventado"] = raw["rubric"]["detectors"]["api_tokens"]
    path.write_text(yaml.safe_dump(raw), encoding="utf-8")
    with pytest.raises(ValueError, match="inventado"):
        load_validation_config(path)


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("min_determined", 0),
        ("min_determined", -1),
        ("max_indeterminate_fraction", -0.1),
        ("max_indeterminate_fraction", 1.5),
    ],
)
def test_decision_rule_out_of_bounds_is_rejected(tmp_path: Path, key, value):
    path = _config(tmp_path, _population(), [])
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    raw["decision"][key] = value
    path.write_text(yaml.safe_dump(raw), encoding="utf-8")
    with pytest.raises(ValueError, match=key):
        load_validation_config(path)


def test_frozen_project_config_applies_general_false_positive_scopes():
    config = load_validation_config(Path("configs/detector_validation.yaml"))
    assert "outdated_dropbear" not in config.rubric.detectors
    assert "FP-exemplo" in config.rubric.false_codes("api_tokens")
    assert "FP-ruido" not in config.rubric.false_codes("api_tokens")
    assert "FP-exemplo" not in config.rubric.false_codes("urls")
    assert "FP-assinatura" in config.rubric.false_codes("encrypted_sections")
    assert "FP-assinatura" not in config.rubric.false_codes("telnetd")
