"""Exercita baselines majoritário, identidade e score sem métricas."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from src.dataset import contract as c
from src.models.baselines import (
    identity_features,
    load_scoring_features,
    majority_class,
)
from src.models.training import load_training_config, train_run
from src.run_metadata import file_sha256
from tests.dataset_fixtures import build_frozen_corpus, feature_row


def baseline_config(tmp_path: Path):
    """Cria corpus e configuração rápida de saída isolada."""
    rows = [
        feature_row(
            f"id-{index:02}", f"{('Acme', 'Beta', 'Gamma')[index % 3]}/m{index}/fw.bin",
            has_telnetd=index == 0,
            count_hardcoded_passwords=index % 2,
            has_debug_account=False,
        )
        for index in range(30)
    ]
    levels = {f"id-{index:02}": c.TARGET_CLASSES[index % 3] for index in range(30)}
    processed = build_frozen_corpus(tmp_path, rows, levels)
    config = load_training_config(Path("configs/training.yaml"), {
        "processed_dir": str(processed),
        "output_dir": str(tmp_path / "runs"),
        "hyperparameters.n_estimators": "20",
    })
    return config, processed


def test_majority_tie_and_alias_identity(tmp_path: Path) -> None:
    """Desempata classe fixa e normaliza fabricantes de todos os aliases."""
    predicted = majority_class(pd.Series(c.TARGET_CLASSES), c.TARGET_CLASSES)
    assert predicted == c.TARGET_CLASSES[0]
    provenance = pd.DataFrame([
        {"firmware_id": "a", "vendor": "TP-Link"},
        {"firmware_id": "a", "vendor": "tp_link"},
        {"firmware_id": "a", "vendor": "Beta"},
        {"firmware_id": "b", "vendor": "Beta"},
    ])
    encoded = identity_features(provenance, pd.Index(["a", "b"]))
    assert encoded.columns.tolist() == ["fabricante__beta", "fabricante__tplink"]
    assert encoded.loc["a"].tolist() == [1.0, 1.0]
    assert encoded.loc["b"].tolist() == [1.0, 0.0]
    config, _ = baseline_config(tmp_path)
    path = train_run("identidade", "principal", "grouped", None, config)
    purpose = pd.read_parquet(path / "predictions.parquet")["purpose"]
    assert set(purpose) == {"diagnostico"}
    assert not list(path.glob("*.joblib"))


def test_scoring_reads_t13a_raw_features_and_checks_hash(tmp_path: Path) -> None:
    """Conserva detectores T13-A do BR e recusa features alteradas."""
    config, processed = baseline_config(tmp_path)
    path = train_run("score_firmware", "principal", "grouped", None, config)
    meta = json.loads((path / "run.meta.json").read_text())
    assert meta["t13a_columns_read"] == [
        "count_hardcoded_passwords", "has_debug_account"
    ]
    predictions = pd.read_parquet(path / "predictions.parquet").set_index("firmware_id")
    assert predictions.loc["id-00", "y_pred"] in c.TARGET_CLASSES[1:]
    assert set(predictions["purpose"]) == {"baseline"}
    assert not list(path.glob("*.joblib"))
    source = processed / "../inputs/features_v2.parquet"
    source.write_bytes(source.read_bytes() + b"alterado")
    with pytest.raises(ValueError, match="difere de training_table.meta.json"):
        train_run("score_firmware", "principal", "grouped", None, config, force=True)


@pytest.mark.parametrize("suffix", [".csv", ".txt"])
def test_scoring_features_follow_008_formats(tmp_path: Path, suffix: str) -> None:
    """Lê features em CSV como a 008 e recusa formato que ela não aceita."""
    rows = [
        feature_row("id-00", "acme/m0/fw.bin", has_debug_account=True),
        feature_row("id-01", "acme/m1/fw.bin", has_debug_account=False),
    ]
    source = tmp_path / f"features_v2{suffix}"
    pd.DataFrame(rows).to_csv(source, index=False)
    meta = {
        "inputs": {"features": {"path": str(source), "sha256": file_sha256(source)}},
        "column_changes": {"has_debug_account": "t13a_reformular"},
    }
    (tmp_path / c.META_FILENAME).write_text(json.dumps(meta))
    if suffix == ".txt":
        with pytest.raises(ValueError, match="Formato de features inválido"):
            load_scoring_features(tmp_path, ["id-00"])
        return
    frame, read, t13a = load_scoring_features(tmp_path, ["id-01", "id-00"])
    assert frame.index.tolist() == ["id-01", "id-00"]
    assert frame["has_debug_account"].tolist() == [False, True]
    assert read == {"path": str(source), "sha256": file_sha256(source)}
    assert t13a == ["has_debug_account"]
