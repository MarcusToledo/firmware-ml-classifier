"""Exercita validação dos artefatos e dos firmwares órfãos."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest

from src.dataset.validation import validate_artifacts
from src.run_metadata import file_sha256

ROOT = Path(__file__).resolve().parents[1]


def _artifacts(tmp_path: Path) -> tuple[Path, Path, dict]:
    """Grava entradas e artefatos mínimos, com hashes reais."""
    processed = tmp_path / "processed"
    raw = tmp_path / "raw"
    processed.mkdir()
    firmware = raw / "acme" / "router" / "firmware.bin"
    firmware.parent.mkdir(parents=True)
    firmware.write_bytes(b"firmware")
    features = processed / "features_v2.parquet"
    pd.DataFrame(
        {"firmware_id": ["fw1"], "meta_path": ["acme/router/firmware.bin"]}
    ).to_parquet(features, index=False)
    labels = processed / "labels_v2.csv"
    labels.write_text("firmware_id,security_level\nfw1,sem_cve_conhecida\n")
    labels_meta = processed / "labels_v2.meta.json"
    labels_meta.write_text("{}")
    table = processed / "training_table.parquet"
    pd.DataFrame(
        {
            "firmware_id": ["fw1"],
            "entropy": [7.0],
            "security_level": ["sem_cve_conhecida"],
        }
    ).to_parquet(table, index=False)
    exclusions = processed / "training_table_exclusions.csv"
    exclusions.write_text("firmware_id,reasons,vendors\n")
    provenance = processed / "training_table_provenance.jsonl"
    provenance.write_text(
        json.dumps(
            {
                "firmware_id": "fw1",
                "in_table": True,
                "aliases": [
                    {
                        "meta_path": "acme/router/firmware.bin",
                        "vendor": "acme",
                        "model": "router",
                    }
                ],
            }
        )
        + "\n"
    )
    meta = {
        "inputs": {
            name: {"path": path.as_posix(), "sha256": file_sha256(path)}
            for name, path in (
                ("features", features),
                ("labels", labels),
                ("labels_meta", labels_meta),
            )
        },
        "outputs": {
            name: {"path": path.as_posix(), "sha256": file_sha256(path)}
            for name, path in (
                ("table", table),
                ("exclusions", exclusions),
                ("provenance", provenance),
            )
        },
        "columns_vector": ["entropy"],
    }
    (processed / "training_table.meta.json").write_text(json.dumps(meta))
    return processed, raw, meta


def _save_meta(processed: Path, meta: dict) -> None:
    """Atualiza o arquivo de metadados após alteração do cenário."""
    (processed / "training_table.meta.json").write_text(json.dumps(meta))


def _save_table(processed: Path, meta: dict, frame: pd.DataFrame) -> None:
    """Grava uma tabela alterada e sincroniza o hash para isolar o defeito."""
    path = processed / "training_table.parquet"
    frame.to_parquet(path, index=False)
    meta["outputs"]["table"]["sha256"] = file_sha256(path)
    _save_meta(processed, meta)


def test_artifact_integrity_and_filtered_raw_files(tmp_path: Path) -> None:
    """Aceita artefatos íntegros e ignora documentos e arquivos ocultos."""
    processed, raw, _ = _artifacts(tmp_path)
    (raw / "acme" / "manual.pdf").write_bytes(b"manual")
    (raw / "acme" / ".hidden.bin").write_bytes(b"hidden")
    assert validate_artifacts(processed, raw) == []


@pytest.mark.parametrize(
    "name",
    [
        "training_table.parquet",
        "training_table_exclusions.csv",
        "training_table_provenance.jsonl",
        "training_table.meta.json",
    ],
)
def test_missing_artifact(tmp_path: Path, name: str) -> None:
    """Lista artefatos obrigatórios ausentes."""
    processed, raw, _ = _artifacts(tmp_path)
    (processed / name).unlink()
    assert any(
        issue.startswith("artefato ausente:")
        for issue in validate_artifacts(processed, raw)
    )


@pytest.mark.parametrize(
    "column", ["meta_brand", "doc2vec_0", "cve_count_high", "vendor", "fs_type"]
)
def test_forbidden_vector_columns(tmp_path: Path, column: str) -> None:
    """Recusa identidade e vazamento no vetor mesmo quando o hash confere."""
    processed, raw, meta = _artifacts(tmp_path)
    meta["columns_vector"].append(column)
    _save_table(
        processed,
        meta,
        pd.DataFrame(
            {
                "firmware_id": ["fw1"],
                "entropy": [7.0],
                column: [1],
                "security_level": ["sem_cve_conhecida"],
            }
        ),
    )
    assert any(
        issue.startswith("coluna proibida no vetor:")
        for issue in validate_artifacts(processed, raw)
    )


@pytest.mark.parametrize(
    "change,prefix",
    [
        ("duplicate", "firmware_id duplicado:"),
        ("text", "coluna de texto no vetor:"),
        ("target", "alvo fora das classes:"),
        ("order", "ordem das colunas difere dos metadados"),
        ("different", "colunas diferentes dos metadados:"),
    ],
)
def test_table_defects(tmp_path: Path, change: str, prefix: str) -> None:
    """Identifica alterações de valores, esquema, ordem e unicidade."""
    processed, raw, meta = _artifacts(tmp_path)
    frame = pd.read_parquet(processed / "training_table.parquet")
    if change == "duplicate":
        frame = pd.concat([frame, frame], ignore_index=True)
    elif change == "text":
        frame["entropy"] = ["alta"]
    elif change == "target":
        frame["security_level"] = ["indeterminado"]
    elif change == "order":
        frame.insert(2, "extra", [1])
        meta["columns_vector"] = ["extra", "entropy"]
    elif change == "different":
        frame["extra"] = [1]
    _save_table(processed, meta, frame)
    assert any(issue.startswith(prefix) for issue in validate_artifacts(processed, raw))


@pytest.mark.parametrize(
    "group,name",
    [
        ("inputs", "features"),
        ("inputs", "labels"),
        ("inputs", "labels_meta"),
        ("outputs", "table"),
        ("outputs", "exclusions"),
        ("outputs", "provenance"),
    ],
)
def test_hash_mismatch(tmp_path: Path, group: str, name: str) -> None:
    """Confere SHA256 real de cada entrada e saída declarada."""
    processed, raw, meta = _artifacts(tmp_path)
    meta[group][name]["sha256"] = "0" * 64
    _save_meta(processed, meta)
    issues = validate_artifacts(processed, raw)
    assert any(
        issue.startswith("SHA256 divergente em ") and meta[group][name]["path"] in issue
        for issue in issues
    )


def test_missing_declared_input(tmp_path: Path) -> None:
    """Informa caminho ausente referenciado no metadado."""
    processed, raw, meta = _artifacts(tmp_path)
    Path(meta["inputs"]["labels"]["path"]).unlink()
    assert any(
        issue.startswith("artefato ausente:")
        for issue in validate_artifacts(processed, raw)
    )


def test_absolute_meta_path(tmp_path: Path) -> None:
    """Interrompe órfãos se a extração registrou caminhos absolutos."""
    processed, raw, meta = _artifacts(tmp_path)
    features = Path(meta["inputs"]["features"]["path"])
    pd.DataFrame(
        {
            "firmware_id": ["fw1"],
            "meta_path": [str(raw / "acme/router/firmware.bin")],
        }
    ).to_parquet(features, index=False)
    meta["inputs"]["features"]["sha256"] = file_sha256(features)
    _save_meta(processed, meta)
    issues = validate_artifacts(processed, raw)
    assert any(
        issue.startswith("meta_path absoluto na tabela de features") for issue in issues
    )
    assert not any(issue.startswith("órfão em ") for issue in issues)


def test_orphan_reports_vendor_and_path(tmp_path: Path) -> None:
    """Aponta firmware do disco que não consta das features."""
    processed, raw, _ = _artifacts(tmp_path)
    (raw / "acme" / "router" / "extra.bin").write_bytes(b"extra")
    assert "órfão em acme: acme/router/extra.bin" in validate_artifacts(processed, raw)


@pytest.mark.parametrize("corrupt", [False, True])
def test_cli_exit_status(tmp_path: Path, corrupt: bool) -> None:
    """Propaga sucesso ou falha com código de saída observável."""
    processed, raw, meta = _artifacts(tmp_path)
    if corrupt:
        meta["outputs"]["table"]["sha256"] = "0" * 64
        _save_meta(processed, meta)
    result = subprocess.run(
        [
            sys.executable,
            "scripts/validate_dataset.py",
            "--processed-dir",
            str(processed),
            "--raw",
            str(raw),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == (1 if corrupt else 0)
    expected = "SHA256 divergente" if corrupt else "Artefato íntegro e sem órfãos"
    assert expected in result.stderr
