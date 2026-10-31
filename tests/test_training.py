"""Verifica treino por fold, rastreabilidade e rejeição de entradas alteradas."""

from __future__ import annotations

import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import pytest

from src.dataset import contract as c
from src.dataset.partition import PartitionConfig, build_partition, write_folds
from src.models.training import (
    compute_run_id,
    fixed_probabilities,
    load_inputs,
    load_training_config,
    train_run,
    write_run,
)
from tests.dataset_fixtures import build_frozen_corpus, feature_row


def corpus(tmp_path: Path) -> Path:
    """Constrói 30 firmwares independentes em três classes e fabricantes."""
    rows = [
        feature_row(
            f"id-{index:02}", f"{('acme', 'beta', 'gamma')[index % 3]}/m{index}/fw.bin",
            entropy=6.0 + index / 100,
            has_telnetd=index % 4 == 0,
        )
        for index in range(30)
    ]
    levels = {f"id-{index:02}": c.TARGET_CLASSES[index % 3] for index in range(30)}
    return build_frozen_corpus(tmp_path, rows, levels)


def config_for(tmp_path: Path, processed: Path):
    """Retorna configuração rápida, com saída isolada para cada teste."""
    return load_training_config(Path("configs/training.yaml"), {
        "processed_dir": str(processed),
        "output_dir": str(tmp_path / "runs"),
        "hyperparameters.n_estimators": "20",
    })


def test_config_rejects_invalid_parameters(tmp_path: Path) -> None:
    """Registra override e recusa paralelismo, pesos e alvo não propostos."""
    config = config_for(tmp_path, corpus(tmp_path))
    path = train_run("majoritario", "principal", "grouped", None, config)
    metadata = json.loads((path / "run.meta.json").read_text())
    assert metadata["config"]["hyperparameters"]["n_estimators"] == 20
    for key, value in (
        ("hyperparameters.n_jobs", "2"),
        ("class_weight", "balanced_subsample"),
    ):
        with pytest.raises(ValueError, match=key):
            load_training_config(Path("configs/training.yaml"), {key: value})
    with pytest.raises(ValueError, match="binário é Proposto"):
        train_run("majoritario", "binario", "grouped", None, config)


def test_refuses_rewritten_folds_even_when_009_is_consistent(tmp_path: Path) -> None:
    """Recusa folds coerentes com a 009 mas diferentes do congelamento."""
    processed = corpus(tmp_path)
    write_folds(build_partition(PartitionConfig(5, (1,), processed)), processed)
    with pytest.raises(
        ValueError, match="folds_grouped.parquet difere do congelamento"
    ):
        load_inputs(config_for(tmp_path, processed))


def test_et_predicts_each_test_id_and_persists_reproducible_pipelines(
    tmp_path: Path,
) -> None:
    """Confronta previsões únicas e cada modelo serializado com a tabela."""
    processed = corpus(tmp_path)
    config = config_for(tmp_path, processed)
    path = train_run("extra_trees", "principal", "grouped", None, config)
    predictions = pd.read_parquet(path / "predictions.parquet")
    metadata = json.loads((path / "run.meta.json").read_text())
    assert len(predictions) == predictions["firmware_id"].nunique() == 30
    assert len(metadata["folds"]) == 5
    assert predictions["purpose"].unique().tolist() == ["reportado"]
    table = pd.read_parquet(processed / c.TABLE_FILENAME).set_index(c.KEY_COLUMN)
    for fold in metadata["folds"]:
        mask = (
            (predictions["repeat"] == fold["repeat"])
            & (predictions["fold"] == fold["fold"])
        )
        selected = predictions.loc[mask]
        assert set(fold["train_ids"]).isdisjoint(selected["firmware_id"])
        pipeline = joblib.load(path / fold["model_file"])
        x_test = table.loc[selected["firmware_id"], metadata["columns"]]
        actual = pipeline.predict(x_test.astype("float64"))
        assert actual.tolist() == selected["y_pred"].tolist()


def test_filter_is_fit_only_on_training_partition(tmp_path: Path) -> None:
    """Exclui atributo variável só nos testes do fold 0, não nos demais."""
    preliminary = corpus(tmp_path / "preliminary")
    folds = pd.read_parquet(preliminary / "folds_grouped.parquet")
    first_test = set(
        folds.loc[
            (folds["fold"] == 0) & (folds["role"] == "test"), "firmware_id"
        ]
    )
    rows = [
        feature_row(
            f"id-{index:02}",
            f"{('acme', 'beta', 'gamma')[index % 3]}/m{index}/fw.bin",
            entropy=6.0 + index / 100,
            count_urls=5 if f"id-{index:02}" in first_test else 0,
        )
        for index in range(30)
    ]
    levels = {
        f"id-{index:02}": c.TARGET_CLASSES[index % 3] for index in range(30)
    }
    processed = build_frozen_corpus(tmp_path / "final", rows, levels)
    config = config_for(tmp_path / "final", processed)
    path = train_run("extra_trees", "principal", "grouped", None, config)
    records = json.loads((path / "run.meta.json").read_text())["folds"]
    assert "count_urls" not in records[0]["columns_used"]
    assert all("count_urls" in fold["columns_used"] for fold in records[1:])


def test_ablation_and_constant_only_selection(tmp_path: Path) -> None:
    """Interrompe filtro vazio e não salva estimador de ablação válida."""
    config = config_for(tmp_path, corpus(tmp_path))
    with pytest.raises(ValueError, match="repetição 0, fold"):
        train_run("extra_trees", "principal", "grouped", ["fs_type__cramfs"], config)
    with pytest.raises(ValueError, match="coluna pedida inexistente no vetor"):
        train_run("extra_trees", "principal", "grouped", ["inexistente"], config)
    path = train_run("extra_trees", "principal", "grouped", ["entropy"], config)
    assert json.loads((path / "run.meta.json").read_text())["purpose"] == "ablation"
    assert not list(path.glob("*.joblib"))


def test_run_id_and_force_distinguish_models_and_columns(tmp_path: Path) -> None:
    """Distingue configurações e proíbe substituir saída sem força explícita."""
    base = (
        "principal", "grouped", ["entropy"],
        {"target": c.TARGET_COLUMN}, {"table": "abc"},
    )
    et = compute_run_id("extra_trees", *base)
    assert et != compute_run_id("random_forest", *base)
    assert et != compute_run_id(
        "extra_trees", "principal", "grouped",
        ["entropy", "byte_mean"], base[3], base[4],
    )
    config = config_for(tmp_path, corpus(tmp_path))
    path = train_run("majoritario", "principal", "grouped", None, config)
    with pytest.raises(FileExistsError, match=path.name):
        train_run("majoritario", "principal", "grouped", None, config)
    replaced = train_run(
        "majoritario", "principal", "grouped", None, config, force=True
    )
    assert replaced == path


def test_concurrent_staging_and_late_publication_are_isolated(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Preserva staging alheio e recusa publicar sobre execução concorrente."""
    output = tmp_path / "runs"
    run_id = "a" * 64
    foreign = output / f".{run_id}.outro.tmp"
    foreign.mkdir(parents=True)
    (foreign / "predictions.parquet").write_text("em gravação")
    winner = output / run_id
    real_dump = joblib.dump

    def publish_during_write(value: object, path: Path) -> None:
        winner.mkdir()
        (winner / "run.meta.json").write_text("outra execução")
        real_dump(value, path)

    monkeypatch.setattr(joblib, "dump", publish_during_write)
    predictions = pd.DataFrame({"firmware_id": ["id-00"]})
    with pytest.raises(FileExistsError, match=f"run_id {run_id}.*durante a gravação"):
        write_run(output, run_id, predictions, {}, {"fold_0_0.joblib": {}}, False)
    assert (winner / "run.meta.json").read_text() == "outra execução"
    assert (foreign / "predictions.parquet").read_text() == "em gravação"
    assert sorted(path.name for path in output.iterdir()) == sorted(
        [run_id, foreign.name]
    )



def test_rf_uses_same_test_splits_as_et(tmp_path: Path) -> None:
    """Compara identidade de cada teste dos dois classificadores."""
    config = config_for(tmp_path, corpus(tmp_path))
    et = train_run("extra_trees", "principal", "grouped", None, config)
    rf = train_run("random_forest", "principal", "grouped", None, config)
    cols = ["repeat", "fold", "firmware_id"]
    et_folds = pd.read_parquet(et / "predictions.parquet")[cols]
    rf_folds = pd.read_parquet(rf / "predictions.parquet")[cols]
    assert et_folds.equals(rf_folds)
    assert set(pd.read_parquet(rf / "predictions.parquet")["purpose"]) == {"baseline"}


def test_absent_training_class_has_zero_probability() -> None:
    """Mantém três colunas fixas mesmo se o fold não contém uma classe."""
    values = fixed_probabilities(
        c.TARGET_CLASSES[:2], np.array([[0.2, 0.8]]), c.TARGET_CLASSES
    )
    np.testing.assert_array_equal(values, [[0.2, 0.8, 0.0]])
