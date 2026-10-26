"""Verifica a CLI da tabela de treino e os artefatos produzidos."""

from __future__ import annotations

import json
import logging
import shutil
import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest

from scripts.build_dataset import main
from src.dataset.contract import (
    EXCLUSIONS_FILENAME,
    META_FILENAME,
    PROVENANCE_FILENAME,
    TABLE_FILENAME,
    TARGET_CLASSES,
)
from src.run_metadata import file_sha256
from tests.dataset_fixtures import feature_row, write_config, write_inputs

ROOT = Path(__file__).resolve().parents[1]
ARTIFACT_NAMES = (
    TABLE_FILENAME,
    EXCLUSIONS_FILENAME,
    PROVENANCE_FILENAME,
    META_FILENAME,
)


def _inputs(tmp_path: Path) -> tuple[Path, Path, Path]:
    """Monta três classes, uma exclusão e um caso indeterminado."""
    rows = [
        feature_row("id-a", "alpha/model-a/a.bin"),
        feature_row("id-b", "beta/model-b/b.bin"),
        feature_row("id-c", "gamma/model-c/c.bin"),
        feature_row("id-d", "delta/model-d/d.bin", meta_third_party="dd-wrt"),
        feature_row("id-e", "epsilon/model-e/e.bin"),
    ]
    levels = dict(zip(("id-a", "id-b", "id-c"), TARGET_CLASSES))
    levels.update({"id-d": TARGET_CLASSES[0], "id-e": "indeterminado"})
    features, labels = write_inputs(tmp_path / "inputs", rows, levels)
    output = tmp_path / "output"
    config = write_config(tmp_path, features, labels, output)
    return config, features, output


def _run(config: Path, *args: str) -> subprocess.CompletedProcess[str]:
    """Executa a CLI em processo novo com o diretório do projeto."""
    return subprocess.run(
        [sys.executable, "scripts/build_dataset.py", "--config", str(config), *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def test_repeated_runs_produce_identical_table_exclusions_and_metadata(
    tmp_path: Path,
) -> None:
    """Mantém conteúdo e hashes determinísticos entre duas execuções iguais."""
    config, _, output = _inputs(tmp_path)
    first = _run(config)
    assert first.returncode == 0, first.stderr
    table_before = (output / TABLE_FILENAME).read_bytes()
    exclusions_before = (output / EXCLUSIONS_FILENAME).read_bytes()
    meta_before = json.loads((output / META_FILENAME).read_text())

    second = _run(config)
    assert second.returncode == 0, second.stderr
    meta_after = json.loads((output / META_FILENAME).read_text())
    assert (output / TABLE_FILENAME).read_bytes() == table_before
    assert (output / EXCLUSIONS_FILENAME).read_bytes() == exclusions_before
    assert (
        meta_after["outputs"]["table"]["sha256"]
        == meta_before["outputs"]["table"]["sha256"]
    )
    meta_before.pop("created_at")
    meta_after.pop("created_at")
    assert meta_after == meta_before


def test_transient_failure_leaves_no_artifacts(tmp_path: Path) -> None:
    """Interrompe a preparação antes de criar arquivos em extração incompleta."""
    config, features, output = _inputs(tmp_path)
    frame = pd.read_parquet(features)
    frame.loc[0, "meta_binwalk_status"] = "nao_executado"
    frame.to_parquet(features, index=False)
    labels_meta = features.with_name("labels_v2.meta.json")
    labels_meta.write_text(
        json.dumps({"features_sha256": file_sha256(features)}) + "\n"
    )
    result = _run(config)
    assert result.returncode == 1
    assert "Preparação interrompida" in result.stderr
    assert "nao_executado" in result.stderr
    assert all(not (output / filename).exists() for filename in ARTIFACT_NAMES)


def test_explicit_features_flag_wins_and_is_recorded(tmp_path: Path) -> None:
    """Prioriza a flag sobre o YAML e o override na configuração gravada."""
    config, features, output = _inputs(tmp_path)
    alternative = tmp_path / "alternative.parquet"
    shutil.copyfile(features, alternative)
    result = _run(
        config, "--override", "features=missing.parquet", "--features", str(alternative)
    )
    assert result.returncode == 0, result.stderr
    metadata = json.loads((output / META_FILENAME).read_text())
    assert metadata["config"]["features"] == alternative.as_posix()


def test_main_logs_fr017_summary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Expõe no log distribuição, exclusões, fabricantes e proporções."""
    config, _, output = _inputs(tmp_path)
    monkeypatch.setattr(sys, "argv", ["build-dataset", "--config", str(config)])
    with caplog.at_level(logging.INFO):
        assert main() == 0
    messages = "\n".join(record.getMessage() for record in caplog.records)
    assert "5" in messages
    assert "3" in messages
    assert "falha_extracao" in messages or "terceiros" in messages
    assert "delta" in messages
    assert "epsilon" in messages
    assert all(label in messages for label in TARGET_CLASSES)
    assert f"Tabela de treino salva em {output / TABLE_FILENAME}" in messages
