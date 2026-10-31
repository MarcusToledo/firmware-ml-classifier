"""Treina modelos e baselines nos folds imutáveis do corpus (spec 010)."""

from __future__ import annotations

import errno
import hashlib
import json
import logging
import shutil
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, cast

import joblib
import numpy as np
import pandas as pd
import yaml
from sklearn.ensemble import ExtraTreesClassifier, RandomForestClassifier
from sklearn.feature_selection import VarianceThreshold
from sklearn.pipeline import Pipeline

from src.cli_utils import apply_overrides
from src.dataset import contract as c
from src.dataset.corpus import FREEZE_FILENAME, check_frozen_artifacts
from src.dataset.partition import FoldSet, load_folds
from src.models.baselines import (
    identity_features,
    load_scoring_features,
    majority_class,
    score_firmware_levels,
)
from src.run_metadata import code_commit, file_sha256
from src.scoring import load_scoring_config

LOGGER = logging.getLogger(__name__)
MODELS = ("extra_trees", "random_forest", "majoritario", "identidade", "score_firmware")
TREE_MODELS = ("extra_trees", "random_forest")
TRAINING_FROZEN_KEYS = ("table", "provenance", "table_meta", "folds", "folds_meta")
PROBA_PREFIX = "proba__"
HYPERPARAMETER_KEYS = (
    "n_estimators", "max_features", "min_samples_leaf", "max_depth", "n_jobs"
)


@dataclass(frozen=True)
class TrainingConfig:
    """Contém caminhos e parâmetros efetivos do treino."""

    config_path: Path
    processed_dir: Path
    output_dir: Path
    scoring_config: Path
    hyperparameters: dict[str, Any]
    class_weight: str
    experiments: dict[str, dict[str, Any]]
    effective: dict[str, Any]


@dataclass(frozen=True)
class TrainingData:
    """Contém folds, congelamento e hashes de entrada verificados."""

    fold_set: FoldSet
    freeze: dict[str, Any]
    columns_vector: list[str]
    inputs: dict[str, dict[str, str]]


def _validate_config(raw: Any, path: Path) -> None:
    """Exige parâmetros fixos e caminhos explícitos da spec 010."""
    if not isinstance(raw, dict):
        raise ValueError(f"Configuração inválida em {path}: raiz")
    for key in ("processed_dir", "output_dir", "scoring_config"):
        if not isinstance(raw.get(key), str) or not raw[key].strip():
            raise ValueError(f"Configuração inválida em {path}: {key}")
    params = raw.get("hyperparameters")
    if not isinstance(params, dict) or set(params) != set(HYPERPARAMETER_KEYS):
        raise ValueError(f"Configuração inválida em {path}: hyperparameters")
    if type(params["n_jobs"]) is not int or params["n_jobs"] != 1:
        raise ValueError(
            f"Configuração inválida em {path}: hyperparameters.n_jobs; "
            "n_jobs DEVE ser 1 (010/FR-003, determinismo)"
        )
    if raw.get("class_weight") != "balanced":
        raise ValueError(f"Configuração inválida em {path}: class_weight")
    experiments = raw.get("experiments")
    if not isinstance(experiments, dict) or not isinstance(
        experiments.get("principal"), dict
    ):
        raise ValueError(f"Configuração inválida em {path}: experiments.principal")
    principal = experiments["principal"]
    if principal.get("target") != c.TARGET_COLUMN:
        raise ValueError(
            f"Configuração inválida em {path}: experiments.principal.target"
        )
    if principal.get("classes") != list(c.TARGET_CLASSES):
        raise ValueError(
            f"Configuração inválida em {path}: experiments.principal.classes"
        )


def load_training_config(path: Path, overrides: dict[str, str]) -> TrainingConfig:
    """Carrega YAML e aplica overrides tipados antes de validar parâmetros."""
    if not path.is_file():
        raise FileNotFoundError(f"--config não encontrado: {path}")
    parsed: dict[str, Any] = {}
    for key, value in overrides.items():
        try:
            parsed[key] = yaml.safe_load(value)
        except yaml.YAMLError as exc:
            raise ValueError(f"Configuração inválida em {path}: {key}") from exc
    raw = apply_overrides(yaml.safe_load(path.read_text(encoding="utf-8")), parsed)
    _validate_config(raw, path)
    return TrainingConfig(
        path, Path(raw["processed_dir"]), Path(raw["output_dir"]),
        Path(raw["scoring_config"]), raw["hyperparameters"],
        raw["class_weight"], raw["experiments"], raw,
    )


def target_for_experiment(
    experiment: str, config: TrainingConfig
) -> tuple[str, ...]:
    """Retorna as classes fixas da experiência principal registrada."""
    if experiment != "principal":
        raise ValueError(
            f"experimento não suportado: {experiment}; "
            "binário é Proposto (010/FR-015)"
        )
    return c.TARGET_CLASSES


def load_inputs(config: TrainingConfig) -> TrainingData:
    """Exige os cinco artefatos congelados e folds internamente íntegros."""
    directory = config.processed_dir
    freeze = check_frozen_artifacts(directory, TRAINING_FROZEN_KEYS)
    fold_set = load_folds(directory)
    columns = list(freeze["columns_vector"])
    expected = {c.KEY_COLUMN, c.TARGET_COLUMN, *columns}
    actual = set(fold_set.table.columns)
    if expected != actual:
        raise ValueError(
            "colunas da tabela diferem do congelamento: "
            f"faltantes {sorted(expected - actual)}, "
            f"sobrando {sorted(actual - expected)}"
        )
    if len(fold_set.meta["seeds"]) != 1:
        raise ValueError(f"folds exigem uma única semente: {fold_set.meta['seeds']}")
    artifacts = freeze["hashes"]["artifacts"]
    inputs = {
        key: {
            "path": str(directory / Path(artifacts[key]["path"]).name),
            "sha256": artifacts[key]["sha256"],
        }
        for key in ("table", "provenance", "folds")
    }
    path = directory / FREEZE_FILENAME
    inputs["corpus_freeze"] = {"path": str(path), "sha256": file_sha256(path)}
    return TrainingData(fold_set, freeze, columns, inputs)


def resolve_columns(
    requested: list[str] | None, columns_vector: list[str]
) -> list[str]:
    """Seleciona colunas pedidas na ordem imutável do vetor."""
    if requested is None:
        return list(columns_vector)
    if not requested:
        raise ValueError("lista de colunas pedidas vazia")
    if len(set(requested)) != len(requested):
        raise ValueError("colunas pedidas duplicadas")
    unknown = sorted(set(requested) - set(columns_vector))
    if unknown:
        raise ValueError(f"coluna pedida inexistente no vetor: {unknown}")
    chosen = set(requested)
    return [name for name in columns_vector if name in chosen]


def build_pipeline(
    model: str, hyperparameters: dict[str, Any], class_weight: str, seed: int
) -> Pipeline:
    """Constrói ET ou RF com filtro ajustado exclusivamente no treino."""
    if model not in (*TREE_MODELS, "identidade"):
        raise ValueError(f"modelo sem pipeline: {model}")
    estimator = (
        RandomForestClassifier if model == "random_forest" else ExtraTreesClassifier
    )
    return Pipeline([
        ("filtro", VarianceThreshold(0.0)),
        ("modelo", estimator(
            **hyperparameters, class_weight=class_weight, random_state=seed
        )),
    ])


def fit_fold(
    pipeline: Pipeline, x_train: pd.DataFrame, y_train: pd.Series,
    repeat: int, fold: int,
) -> list[str]:
    """Ajusta filtro e estimador e devolve colunas retidas pelo filtro."""
    if not (x_train.nunique(dropna=True) > 1).any():
        raise ValueError(
            f"nenhuma coluna resta após o filtro: repetição {repeat}, "
            f"fold {fold}, colunas {list(x_train.columns)}"
        )
    pipeline.fit(x_train, y_train)
    return list(x_train.columns[pipeline.named_steps["filtro"].get_support()])


def fixed_probabilities(
    model_classes: Sequence[str], proba: np.ndarray, classes: tuple[str, ...]
) -> np.ndarray:
    """Alinha as probabilidades às três classes, zerando classes ausentes."""
    output = np.zeros((len(proba), len(classes)), dtype=np.float64)
    for index, label in enumerate(model_classes):
        output[:, classes.index(label)] = proba[:, index]
    return cast(np.ndarray, output)


def one_hot_probabilities(
    predicted: Sequence[str], classes: tuple[str, ...]
) -> np.ndarray:
    """Converte previsão determinística em probabilidade one-hot."""
    return cast(
        np.ndarray,
        np.asarray(
            [[float(label == category) for category in classes] for label in predicted],
            dtype=np.float64,
        ),
    )


def purpose_for(model: str, full_columns: bool) -> str:
    """Classifica finalidade reportada, baseline, diagnóstico ou ablação."""
    if model == "identidade":
        return "diagnostico"
    if model in TREE_MODELS and not full_columns:
        return "ablation"
    if model == "extra_trees":
        return "reportado"
    return "baseline"


def compute_run_id(
    model: str, experiment: str, scheme: str, columns: list[str],
    config: dict[str, Any], inputs: dict[str, str],
) -> str:
    """Retorna SHA256 canônico dos parâmetros e conteúdos, sem caminhos."""
    payload = {
        "model": model, "experiment": experiment, "scheme": scheme,
        "columns": sorted(columns), "config": config, "inputs": inputs,
    }
    serialized = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _publish(temporary: Path, destination: Path, run_id: str, force: bool) -> None:
    """Renomeia o staging para o destino sem sobrescrever outra execução.

    Levanta FileExistsError se outra execução publicou o mesmo ``run_id``
    durante a gravação; o rename não substitui diretório com conteúdo.
    """
    if force and destination.exists():
        shutil.rmtree(destination)
    try:
        temporary.rename(destination)
    except OSError as exc:
        if exc.errno not in (errno.EEXIST, errno.ENOTEMPTY):
            raise
        raise FileExistsError(
            f"execução já existe: run_id {run_id} em {destination}, publicada "
            "por outra execução durante a gravação"
        ) from exc


def write_run(
    output_dir: Path, run_id: str, predictions: pd.DataFrame, meta: dict[str, Any],
    models: dict[str, Pipeline], force: bool,
) -> Path:
    """Grava predições, modelos e metadado em staging exclusivo e publica.

    Cada chamada usa um diretório temporário próprio, para que execuções
    concorrentes do mesmo ``run_id`` não apaguem nem misturem arquivos.
    Levanta FileExistsError se o destino já existe e ``force`` é falso.
    """
    destination = output_dir / run_id
    if destination.exists() and not force:
        raise FileExistsError(
            f"execução já existe: run_id {run_id} em {destination}; "
            "use --force para substituir"
        )
    output_dir.mkdir(parents=True, exist_ok=True)
    # Nome único com mkdir exclusivo; mkdtemp criaria o run com permissão 0700.
    temporary = output_dir / f".{run_id}.{uuid.uuid4().hex}.tmp"
    temporary.mkdir()
    try:
        predictions.to_parquet(temporary / "predictions.parquet", index=False)
        for name, pipeline in models.items():
            joblib.dump(pipeline, temporary / name)
        (temporary / "run.meta.json").write_text(
            json.dumps(meta, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        _publish(temporary, destination, run_id, force)
    except BaseException:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    return destination


def _predict_fold(
    model: str, params: dict[str, Any], classes: tuple[str, ...],
    features: pd.DataFrame | None, levels: pd.Series | None,
    train_ids: list[str], test_ids: list[str], y_train: pd.Series,
    repeat: int, fold: int, seed: int,
) -> tuple[
    Sequence[str], np.ndarray, list[str] | None,
    dict[str, Any] | None, Pipeline | None,
]:
    """Ajusta árvores no treino ou aplica baseline no teste do fold."""
    if model == "majoritario":
        predicted = [majority_class(y_train, classes)] * len(test_ids)
        return predicted, one_hot_probabilities(predicted, classes), None, None, None
    if model == "score_firmware":
        assert levels is not None
        predicted = levels.loc[test_ids].tolist()
        return predicted, one_hot_probabilities(predicted, classes), None, None, None
    assert features is not None
    pipeline = build_pipeline(
        model, params["hyperparameters"], params["class_weight"], seed
    )
    x_train, x_test = features.loc[train_ids], features.loc[test_ids]
    used = fit_fold(pipeline, x_train, y_train, repeat, fold)
    predicted = pipeline.predict(x_test)
    probabilities = fixed_probabilities(
        pipeline.named_steps["modelo"].classes_, pipeline.predict_proba(x_test),
        classes,
    )
    effective = {
        **params["hyperparameters"],
        "class_weight": params["class_weight"],
        "random_state": seed,
    }
    return predicted, probabilities, used, effective, pipeline


def _fold_rows(
    frame: pd.DataFrame, table: pd.DataFrame, classes: tuple[str, ...],
    model: str, columns: list[str], params: dict[str, Any],
    features: pd.DataFrame | None, levels: pd.Series | None, save_model: bool,
) -> tuple[pd.DataFrame, dict[str, Any], Pipeline | None]:
    """Treina ou aplica um baseline em um fold e registra suas entradas."""
    repeat, fold = int(frame["repeat"].iloc[0]), int(frame["fold"].iloc[0])
    seed = int(frame["seed"].iloc[0])
    train_ids = sorted(frame.loc[frame["role"] == "train", c.KEY_COLUMN].tolist())
    test_ids = sorted(frame.loc[frame["role"] == "test", c.KEY_COLUMN].tolist())
    y_train = table.loc[train_ids, c.TARGET_COLUMN]
    y_test = table.loc[test_ids, c.TARGET_COLUMN]
    predicted, probabilities, kept, effective, pipeline = _predict_fold(
        model, params, classes, features, levels, train_ids, test_ids,
        y_train, repeat, fold, seed,
    )
    used = kept if kept is not None else columns
    LOGGER.info(
        "%s repetição %s fold %s: treino %s, teste %s, classes treino %s, "
        "classes teste %s, colunas %s, seed %s, hiperparâmetros %s",
        model, repeat, fold, len(train_ids), len(test_ids),
        y_train.value_counts().to_dict(), y_test.value_counts().to_dict(),
        len(used), seed, effective,
    )
    name = f"fold_{repeat}_{fold}.joblib" if save_model else None
    record = {
        "repeat": repeat, "fold": fold, "columns_used": used,
        "train_ids": train_ids,
        "train_counts": {
            label: int((y_train == label).sum()) for label in classes
        },
        "test_counts": {
            label: int((y_test == label).sum()) for label in classes
        },
        "hyperparameters": effective, "model_file": name,
    }
    rows = pd.DataFrame({
        "repeat": np.int64(repeat), "fold": np.int64(fold),
        c.KEY_COLUMN: test_ids, "y_true": y_test.tolist(), "y_pred": predicted,
    })
    for index, label in enumerate(classes):
        rows[f"{PROBA_PREFIX}{label}"] = probabilities[:, index]
    return rows, record, pipeline if save_model else None


def _run_parameters(
    model: str, classes: tuple[str, ...], config: TrainingConfig, seed: int
) -> dict[str, Any]:
    """Forma configuração canônica com parâmetros de estimador quando cabíveis."""
    parameters: dict[str, Any] = {"target": c.TARGET_COLUMN, "classes": classes}
    if model in (*TREE_MODELS, "identidade"):
        parameters.update(
            hyperparameters=config.hyperparameters,
            class_weight=config.class_weight,
            seed=seed,
        )
    return parameters


def train_run(
    model: str, experiment: str, scheme: str, columns: list[str] | None,
    config: TrainingConfig, force: bool = False,
) -> Path:
    """Executa uma experiência no corpus congelado e salva artefatos rastreáveis."""
    if scheme != "grouped":
        raise ValueError(
            f"esquema não suportado: {scheme}; random é B6 Proposto (010/FR-016)"
        )
    if columns is not None and model not in TREE_MODELS:
        raise ValueError("--columns-file só se aplica a extra_trees e random_forest")
    if model not in MODELS:
        raise ValueError(f"modelo não suportado: {model}")
    classes = target_for_experiment(experiment, config)
    data = load_inputs(config)
    selected = resolve_columns(columns, data.columns_vector)
    full = selected == data.columns_vector
    purpose = purpose_for(model, full)
    table = data.fold_set.table.set_index(c.KEY_COLUMN)
    features = None
    levels = None
    inputs = dict(data.inputs)
    extra: dict[str, Any] = {}
    if model in TREE_MODELS:
        features = table[selected].astype("float64")
    elif model == "identidade":
        features = identity_features(data.fold_set.provenance, table.index)
    elif model == "score_firmware":
        rows, source, t13a = load_scoring_features(
            config.processed_dir, table.index.tolist()
        )
        scoring_hash = file_sha256(config.scoring_config)
        scoring_source = {"path": str(config.scoring_config), "sha256": scoring_hash}
        inputs.update(features=source, scoring_config=scoring_source)
        extra = {"scoring_config": scoring_source, "t13a_columns_read": t13a}
        levels = score_firmware_levels(
            rows, load_scoring_config(config.scoring_config)
        )
        features = rows
    return _execute_folds(
        model, experiment, scheme, selected, config, force, data, table,
        features, levels, inputs, purpose, extra, classes,
    )


def _run_metadata(
    run_id: str, model: str, purpose: str, experiment: str, scheme: str,
    selected: list[str], config: TrainingConfig, seed: int,
    inputs: dict[str, dict[str, str]], records: list[dict[str, Any]],
    extra: dict[str, Any],
) -> dict[str, Any]:
    """Registra parâmetros, proveniência e folds em um manifesto auditável."""
    tree = model in (*TREE_MODELS, "identidade")
    return {
        "run_id": run_id, "model": model, "purpose": purpose,
        "experiment": experiment, "scheme": scheme, "columns": selected,
        "config": {**config.effective, "config_path": str(config.config_path)},
        "hyperparameters": config.hyperparameters if tree else None,
        "class_weight": config.class_weight if tree else None,
        "seeds": [seed], "inputs": inputs, "folds": records,
        "commit": code_commit(),
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        **extra,
    }


def _execute_folds(
    model: str, experiment: str, scheme: str, selected: list[str],
    config: TrainingConfig, force: bool, data: TrainingData, table: pd.DataFrame,
    features: pd.DataFrame | None, levels: pd.Series | None,
    inputs: dict[str, dict[str, str]], purpose: str, extra: dict[str, Any],
    classes: tuple[str, ...],
) -> Path:
    """Agrega folds, constrói identidade do run e persiste a execução."""
    seed = int(data.fold_set.meta["seeds"][0])
    params = {
        "hyperparameters": config.hyperparameters,
        "class_weight": config.class_weight,
    }
    canonical = _run_parameters(model, classes, config, seed)
    run_id = compute_run_id(
        model, experiment, scheme, selected, canonical,
        {name: value["sha256"] for name, value in inputs.items()},
    )
    save_model = model in TREE_MODELS and purpose != "ablation"
    predictions = []
    records = []
    models: dict[str, Pipeline] = {}
    used_columns = list(features.columns) if features is not None else selected
    for _, frame in data.fold_set.folds.groupby(["repeat", "fold"], sort=True):
        rows, record, pipeline = _fold_rows(
            frame, table, classes, model, used_columns, params,
            features, levels, save_model,
        )
        rows["purpose"] = purpose
        predictions.append(rows)
        records.append(record)
        if pipeline is not None:
            models[record["model_file"]] = pipeline
    result = (
        pd.concat(predictions, ignore_index=True)
        .sort_values(["repeat", "fold", c.KEY_COLUMN])
        .reset_index(drop=True)
    )
    meta = _run_metadata(
        run_id, model, purpose, experiment, scheme, selected, config,
        seed, inputs, records, extra,
    )
    return write_run(config.output_dir, run_id, result, meta, models, force)
