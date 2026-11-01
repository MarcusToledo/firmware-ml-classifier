"""Valida leitura de execuções e consistência dos artefatos comparados."""

import json
from pathlib import Path

import pandas as pd
import pytest

from src.evaluation.ablation import ArmSpec
from src.evaluation.runs import (
    check_current_inputs,
    check_same_inputs,
    ensure_run,
    load_run,
)
from src.models.training import load_inputs, prepare_run
from tests.eval_fixtures import evaluation_configs

B2 = ArmSpec("B2", "B2", "extra_trees", None, (), (), "nucleo")

FIRST = "a" * 64
SECOND = "b" * 64


def _run(runs_dir: Path, run_id: str, fold_hash: str) -> None:
    """Grava uma execução mínima com hashes de entrada explícitos."""
    directory = runs_dir / run_id
    directory.mkdir(parents=True)
    (directory / "run.meta.json").write_text(json.dumps({
        "run_id": run_id, "inputs": {
            key: {"sha256": fold_hash if key == "folds" else "same"}
            for key in ("table", "provenance", "folds")
        },
    }), encoding="utf-8")
    pd.DataFrame({"repeat": [0]}).to_parquet(directory / "predictions.parquet")


def test_different_folds_cannot_be_mixed(tmp_path: Path) -> None:
    """Nomeia ambos os run_ids de folds incompatíveis."""
    _run(tmp_path, FIRST, "hash-a")
    _run(tmp_path, SECOND, "hash-b")
    with pytest.raises(ValueError, match=f"{FIRST}.*{SECOND}"):
        check_same_inputs([load_run(tmp_path, name) for name in (FIRST, SECOND)])


def test_missing_predictions_are_rejected(tmp_path: Path) -> None:
    """Falha ao ler uma execução sem parquet de predições."""
    directory = tmp_path / FIRST
    directory.mkdir()
    (directory / "run.meta.json").write_text(
        json.dumps({"run_id": FIRST}), encoding="utf-8"
    )
    with pytest.raises(FileNotFoundError, match="predictions.parquet"):
        load_run(tmp_path, FIRST)


@pytest.mark.parametrize("run_id", ["../" + FIRST, "/tmp/" + FIRST, "", FIRST.upper()])
def test_run_id_outside_sha256_format_is_rejected(tmp_path: Path, run_id: str) -> None:
    """Recusa run_id que não é SHA256, mesmo apontando para execução existente."""
    _run(tmp_path, FIRST, "hash-a")
    with pytest.raises(ValueError, match="run_id inválido"):
        load_run(tmp_path / "runs", run_id)


def test_ensure_run_trains_once_then_reuses(tmp_path: Path) -> None:
    """Treina na primeira chamada e reaproveita o mesmo run_id sem regravar."""
    config, training = evaluation_configs(tmp_path)
    first = ensure_run(B2, config.experiment, config.scheme, training)
    predictions = training.output_dir / first.run.run_id / "predictions.parquet"
    mtime = predictions.stat().st_mtime_ns
    second = ensure_run(B2, config.experiment, config.scheme, training)
    assert (first.reused, second.reused) == (False, True)
    assert second.run.run_id == first.run.run_id
    assert predictions.stat().st_mtime_ns == mtime


def test_ensure_run_rejects_incomplete_directory(tmp_path: Path) -> None:
    """Recusa diretório do run_id sem predições e orienta reexecutar com --force."""
    config, training = evaluation_configs(tmp_path)
    run_id = prepare_run("extra_trees", "principal", "grouped", None, training).run_id
    directory = training.output_dir / run_id
    directory.mkdir(parents=True)
    (directory / "run.meta.json").write_text(json.dumps({"run_id": run_id}))
    with pytest.raises(ValueError, match="incompleta.*--force"):
        ensure_run(B2, config.experiment, config.scheme, training)


def test_ensure_run_rejects_tampered_parameters(tmp_path: Path) -> None:
    """Recusa reaproveitar execução cujo manifesto não reproduz o run_id."""
    config, training = evaluation_configs(tmp_path)
    run_id = ensure_run(B2, config.experiment, config.scheme, training).run.run_id
    meta_path = training.output_dir / run_id / "run.meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta["hyperparameters"]["n_estimators"] = 999
    meta_path.write_text(json.dumps(meta), encoding="utf-8")
    with pytest.raises(ValueError, match="divergem do run_id"):
        ensure_run(B2, config.experiment, config.scheme, training)


def test_check_current_inputs_names_stale_table(tmp_path: Path) -> None:
    """Cita o run_id cuja tabela difere da registrada pela 008."""
    config, training = evaluation_configs(tmp_path)
    run = ensure_run(B2, config.experiment, config.scheme, training).run
    data = load_inputs(training)
    check_current_inputs([run], data, training.processed_dir)
    run.meta["inputs"]["table"]["sha256"] = "0" * 64
    with pytest.raises(ValueError, match=f"tabela.*{run.run_id}"):
        check_current_inputs([run], data, training.processed_dir)
