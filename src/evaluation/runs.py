"""Carrega execuções e impede comparação de entradas incompatíveis."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from src.dataset import contract as c
from src.evaluation.ablation import ArmSpec
from src.models.training import (
    TrainingConfig,
    TrainingData,
    execute_run,
    prepare_run,
    run_id_from_meta,
)
from src.run_metadata import file_sha256

INPUT_KEYS = ("table", "provenance", "folds")
RUN_FILES = ("run.meta.json", "predictions.parquet")
RUN_ID_PATTERN = re.compile(r"[0-9a-f]{64}")


@dataclass(frozen=True)
class EvaluatedRun:
    """Contém manifesto, predições e hash de uma execução rastreável."""

    run_id: str
    meta: dict[str, Any]
    predictions: pd.DataFrame
    predictions_sha256: str


def load_run(runs_dir: Path, run_id: str) -> EvaluatedRun:
    """Lê manifesto e predições da execução, exigindo identidade coincidente.

    Levanta ValueError quando run_id não é SHA256 hexadecimal (010/FR-006),
    o que também impede caminhos fora de runs_dir.
    """
    if not RUN_ID_PATTERN.fullmatch(run_id):
        raise ValueError(f"run_id inválido: {run_id!r}; esperado SHA256 hexadecimal")
    directory = runs_dir / run_id
    meta_path = directory / "run.meta.json"
    prediction_path = directory / "predictions.parquet"
    for path in (meta_path, prediction_path):
        if not path.is_file():
            raise FileNotFoundError(f"artefato da execução ausente: {path}")
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    if meta.get("run_id") != run_id:
        raise ValueError(f"run_id divergente em {meta_path}: esperado {run_id}, "
                         f"encontrado {meta.get('run_id')}")
    return EvaluatedRun(run_id, meta, pd.read_parquet(prediction_path),
                        file_sha256(prediction_path))


def check_same_inputs(runs: list[EvaluatedRun]) -> None:
    """Recusa execuções de tabelas, proveniências ou folds distintos."""
    if not runs:
        return
    reference = runs[0]
    for run in runs[1:]:
        for key in INPUT_KEYS:
            if (run.meta["inputs"][key]["sha256"]
                    != reference.meta["inputs"][key]["sha256"]):
                raise ValueError(f"entradas {key} divergentes entre run_id "
                                 f"{reference.run_id} e {run.run_id}")


@dataclass(frozen=True)
class ArmRun:
    """Associa um braço à execução avaliada e indica se ela foi reaproveitada."""

    spec: ArmSpec
    run: EvaluatedRun
    reused: bool


def ensure_run(
    spec: ArmSpec, experiment: str, scheme: str, config: TrainingConfig
) -> ArmRun:
    """Reaproveita a execução do braço pelo run_id ou a treina pela 010.

    Levanta ValueError se o diretório existe incompleto ou se os parâmetros
    registrados em run.meta.json não reproduzem o run_id.
    """
    prepared = prepare_run(spec.model, experiment, scheme, spec.columns, config)
    directory = config.output_dir / prepared.run_id
    reused = directory.exists()
    if not reused:
        execute_run(prepared, config, force=False)
    missing = [name for name in RUN_FILES if not (directory / name).is_file()]
    if missing:
        raise ValueError(
            f"execução incompleta: run_id {prepared.run_id} em {directory} sem "
            f"{missing}; reexecute pela 010 com --force"
        )
    run = load_run(config.output_dir, prepared.run_id)
    if run_id_from_meta(run.meta) != run.run_id:
        raise ValueError(
            f"parâmetros registrados em run.meta.json divergem do run_id "
            f"{run.run_id}; reexecute pela 010 com --force"
        )
    return ArmRun(spec, run, reused)


def check_current_inputs(
    runs: list[EvaluatedRun], data: TrainingData, processed_dir: Path
) -> None:
    """Exige que as execuções usem a tabela e os folds congelados atuais.

    Levanta ValueError citando os run_id cuja tabela ou folds divergem.
    """
    meta = json.loads((processed_dir / c.META_FILENAME).read_text(encoding="utf-8"))
    table_sha = meta["outputs"]["table"]["sha256"]
    stale = [run.run_id for run in runs
             if run.meta["inputs"]["table"]["sha256"] != table_sha]
    if stale:
        raise ValueError(
            f"SHA256 da tabela diverge de training_table.meta.json nos run_id {stale}"
        )
    folds_sha = data.inputs["folds"]["sha256"]
    stale = [run.run_id for run in runs
             if run.meta["inputs"]["folds"]["sha256"] != folds_sha]
    if stale:
        raise ValueError(f"SHA256 dos folds diverge do congelamento nos run_id {stale}")


def _test_groups(folds: pd.DataFrame) -> pd.DataFrame:
    """Retorna firmware_id e componente das linhas de teste, um ID por linha.

    Levanta ValueError se algum ID aparece em mais de uma linha de teste.
    """
    test = folds.loc[folds["role"] == "test", [c.KEY_COLUMN, "group"]]
    repeated = sorted(test.loc[test[c.KEY_COLUMN].duplicated(), c.KEY_COLUMN])
    if repeated:
        raise ValueError(f"firmware_id repetido no teste: {repeated}")
    return test.sort_values(c.KEY_COLUMN).reset_index(drop=True)


def _vendors(provenance: pd.DataFrame, exclude_alias_vendor: str) -> pd.DataFrame:
    """Retorna o fabricante único e a presença do alias excluído por ID.

    Levanta ValueError para ID com mais de um fabricante ou fabricante ausente.
    """
    aliases = provenance[[c.KEY_COLUMN, "vendor"]]
    if exclude_alias_vendor not in set(aliases["vendor"]):
        raise ValueError(f"fabricante {exclude_alias_vendor} ausente da proveniência")
    counts = aliases.groupby(c.KEY_COLUMN)["vendor"].nunique()
    multiple = sorted(counts.index[counts > 1])
    if multiple:
        raise ValueError(f"firmware_id com mais de um fabricante: {multiple}")
    vendors = aliases.groupby(c.KEY_COLUMN)["vendor"].first()
    return pd.DataFrame({
        "vendor": vendors, "has_excluded_alias": vendors == exclude_alias_vendor,
    })


def oof_frame(data: TrainingData, exclude_alias_vendor: str) -> pd.DataFrame:
    """Retorna componente, tamanho do componente e fabricante de cada ID de teste.

    Levanta ValueError para ID de teste sem fabricante ou fabricante ambíguo.
    """
    frame = _test_groups(data.fold_set.folds)
    frame["n_group"] = frame.groupby("group")[c.KEY_COLUMN].transform("size")
    vendors = _vendors(data.fold_set.provenance, exclude_alias_vendor)
    missing = sorted(set(frame[c.KEY_COLUMN]) - set(vendors.index))
    if missing:
        raise ValueError(f"firmware_id de teste sem proveniência: {missing}")
    frame = frame.join(vendors, on=c.KEY_COLUMN)
    frame["n_group"] = frame["n_group"].astype("int64")
    frame["has_excluded_alias"] = frame["has_excluded_alias"].astype(bool)
    return frame[[c.KEY_COLUMN, "group", "n_group", "vendor", "has_excluded_alias"]]


def aligned_predictions(run: EvaluatedRun, ids: pd.Series) -> pd.DataFrame:
    """Retorna as predições da execução ordenadas por firmware_id.

    Levanta ValueError se há mais de uma repetição ou se os IDs diferem.
    """
    if run.predictions["repeat"].nunique() != 1:
        raise ValueError(f"run_id {run.run_id}: avaliação exige uma repetição")
    predictions = run.predictions.sort_values(c.KEY_COLUMN).reset_index(drop=True)
    if predictions[c.KEY_COLUMN].tolist() != sorted(ids.tolist()):
        raise ValueError(
            f"run_id {run.run_id}: firmware_id das predições diferem do teste dos folds"
        )
    return predictions
