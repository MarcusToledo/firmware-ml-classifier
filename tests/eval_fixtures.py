"""Monta corpus congelado e configurações sintéticas para a avaliação (011)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import yaml

from src.dataset import contract as c
from src.evaluation.config import EvaluationConfig, load_evaluation_config
from src.models.training import TrainingConfig, load_training_config
from tests.dataset_fixtures import build_frozen_corpus, feature_row

VENDORS = ("acme", "beta", "tp_link")
N_IDS = 36
ABLATIONS = [
    {"arm": "B2_menos_D", "label": "B2−D", "remove": ["count_urls", "has_telnetd"]},
    {"arm": "B2_menos_H", "label": "B2−H", "remove": ["unpacked_n_files"]},
    {"arm": "B2_linha", "label": "B2′",
     "remove": ["count_urls", "count_non_public_ips", "count_public_ips"]},
]


def _class_index(index: int) -> int:
    """Retorna a classe do ID: tp_link só tem sem_cve_conhecida."""
    return 0 if VENDORS[index % 3] == "tp_link" else (index // 3) % 3


def _rows() -> tuple[list[dict[str, Any]], dict[str, str]]:
    """Retorna linhas de features e rótulos; id-00 e id-03 dividem um modelo."""
    rng = np.random.default_rng(1)
    rows, levels = [], {}
    for index in range(N_IDS):
        firmware_id = f"id-{index:02}"
        model = "m0" if index in (0, 3) else f"m{index}"
        label = _class_index(index)
        rows.append(feature_row(
            firmware_id, f"{VENDORS[index % 3]}/{model}/fw{index}.bin",
            entropy=5.0 + label + index / 1000, byte_mean=float(rng.uniform(0, 255)),
            has_telnetd=index % 4 == 0, count_urls=index % 5,
            unpacked_n_files=10.0 + index, count_non_public_ips=index % 2,
            count_public_ips=index % 3,
        ))
        levels[firmware_id] = c.TARGET_CLASSES[label]
    return rows, levels


def evaluation_corpus(tmp_path: Path) -> tuple[Path, Path]:
    """Constrói o corpus e grava training.yaml rápido; retorna (processed, yaml)."""
    rows, levels = _rows()
    processed = build_frozen_corpus(tmp_path, rows, levels)
    raw = yaml.safe_load(Path("configs/training.yaml").read_text(encoding="utf-8"))
    raw.update(
        processed_dir=str(processed), output_dir=str(tmp_path / "runs"),
        scoring_config=str(Path("configs/scoring.yaml").resolve()),
    )
    raw["hyperparameters"]["n_estimators"] = 20
    training_yaml = tmp_path / "training.yaml"
    training_yaml.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")
    return processed, training_yaml


def evaluation_yaml(tmp_path: Path, training_yaml: Path) -> Path:
    """Grava evaluation.yaml com as ablações do corpus sintético."""
    raw = yaml.safe_load(Path("configs/evaluation.yaml").read_text(encoding="utf-8"))
    raw.update(training_config=str(training_yaml),
               output_dir=str(tmp_path / "reports"), ablations=ABLATIONS)
    path = tmp_path / "evaluation.yaml"
    path.write_text(yaml.safe_dump(raw, sort_keys=False, allow_unicode=True),
                    encoding="utf-8")
    return path


def evaluation_configs(
    tmp_path: Path, overrides: dict[str, str] | None = None
) -> tuple[EvaluationConfig, TrainingConfig]:
    """Retorna as configurações carregadas da avaliação e do treino sintéticos."""
    _, training_yaml = evaluation_corpus(tmp_path)
    config = load_evaluation_config(
        evaluation_yaml(tmp_path, training_yaml), overrides or {}
    )
    return config, load_training_config(training_yaml, {})
