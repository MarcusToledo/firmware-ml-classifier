"""Carrega execuções e impede comparação de entradas incompatíveis."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from src.run_metadata import file_sha256

INPUT_KEYS = ("table", "provenance", "folds")
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
