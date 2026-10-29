"""Exercita o congelamento do corpus sobre artefatos reais da 008 e da 009."""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import pytest
import yaml

from src.dataset import contract as c
from src.dataset.corpus import (
    FREEZE_FILENAME,
    FreezeConfig,
    freeze_corpus,
    load_freeze_config,
    write_freeze,
)
from src.dataset.partition import (
    FOLDS_FILENAME,
    PartitionConfig,
    build_partition,
    write_folds,
)
from src.dataset.training_table import (
    build_training_table,
    load_dataset_config,
    write_artifacts,
)
from src.run_metadata import file_sha256
from tests.dataset_fixtures import feature_row, write_config, write_inputs

ROOT = Path(__file__).resolve().parents[1]
MILESTONE = date(2026, 10, 11)
FROZEN_AT = datetime(2026, 10, 30, 10, 0, tzinfo=timezone(timedelta(hours=-3)))


def _corpus(tmp_path: Path, reason: str = "rodada de dados") -> Path:
    """Gera tabela, folds e configuração com seção ``freeze``; retorna o YAML."""
    rows = [
        feature_row(f"id-{index:02}", f"acme/m{index}/fw.bin") for index in range(15)
    ]
    rows.append(
        feature_row("id-falha", "acme/falha/fw.bin", meta_unpack_status="falha")
    )
    rows.append(feature_row("id-ind", "acme/ind/fw.bin"))
    levels = {f"id-{i:02}": c.TARGET_CLASSES[i % 3] for i in range(15)}
    levels |= {"id-falha": c.TARGET_CLASSES[0], "id-ind": c.REASON_INDETERMINATE}
    features, labels = write_inputs(tmp_path / "inputs", rows, levels)
    processed = tmp_path / "processed"
    config = write_config(tmp_path, features, labels, processed)
    write_artifacts(build_training_table(load_dataset_config(config, {})), processed)
    write_folds(build_partition(PartitionConfig(5, (0,), processed)), processed)
    raw = yaml.safe_load(config.read_text())
    raw["partition"] = {"n_splits": 5, "seeds": [0]}
    raw["freeze"] = {"milestone": MILESTONE, "deviation_reason": reason}
    config.write_text(yaml.safe_dump(raw, sort_keys=False))
    (tmp_path / "raw").mkdir()
    return config


def _config(tmp_path: Path, reason: str = "rodada de dados") -> FreezeConfig:
    """Monta o corpus e lê a configuração do congelamento."""
    return load_freeze_config(_corpus(tmp_path, reason), None, tmp_path / "raw")


def test_manifest_counts_support_from_new_artifacts(tmp_path: Path) -> None:
    """Conta classes e componentes da tabela nova e registra o desvio com motivo."""
    config = _config(tmp_path)
    manifest = freeze_corpus(config, FROZEN_AT)
    table = pd.read_parquet(config.processed_dir / c.TABLE_FILENAME)
    support = manifest["support"]
    assert support["by_class"] == {name: 5 for name in c.TARGET_CLASSES}
    assert support["n_firmware_id"] == len(table) == 15
    assert sum(group["n"] for group in support["by_group"]) == 15
    for group in support["by_group"]:
        assert sum(group["classes"].values()) == group["n"]
    assert manifest["exclusions"]["excluded_by_reason"] == {
        c.REASON_EXTRACTION_FAILURE: 1,
        c.REASON_THIRD_PARTY: 0,
        c.REASON_INDETERMINATE: 1,
    }
    folds = manifest["hashes"]["artifacts"]["folds"]
    assert folds["sha256"] == file_sha256(config.processed_dir / FOLDS_FILENAME)
    assert manifest["deviation"] == {
        "milestone": "2026-10-11",
        "effective_date": "2026-10-30",
        "days_after_milestone": 19,
        "reason": "rodada de dados",
    }
    assert manifest["frozen_at"] == "2026-10-30T10:00:00-03:00"


def test_delay_without_reason_is_refused(tmp_path: Path) -> None:
    """Recusa congelar depois do marco sem motivo; no prazo o motivo é opcional."""
    config = _config(tmp_path, reason="")
    with pytest.raises(ValueError, match="sem freeze.deviation_reason"):
        freeze_corpus(config, FROZEN_AT)
    on_time = datetime(2026, 10, 11, 23, 0, tzinfo=FROZEN_AT.tzinfo)
    assert freeze_corpus(config, on_time)["deviation"]["reason"] is None


@pytest.mark.parametrize("name", [FOLDS_FILENAME, c.TABLE_FILENAME])
def test_tampered_artifact_blocks_freeze(tmp_path: Path, name: str) -> None:
    """Recusa folds ou tabela regravados sem a última linha, citando o SHA256."""
    config = _config(tmp_path)
    path = config.processed_dir / name
    frame = pd.read_parquet(path)
    frame.iloc[:-1].to_parquet(path, index=False)
    with pytest.raises(ValueError, match="SHA256 divergente"):
        freeze_corpus(config, FROZEN_AT)


def test_existing_freeze_is_not_overwritten(tmp_path: Path) -> None:
    """Mantém o primeiro congelamento intacto em uma segunda gravação."""
    config = _config(tmp_path)
    manifest = freeze_corpus(config, FROZEN_AT)
    path = write_freeze(manifest, config.processed_dir)
    before = path.read_bytes()
    with pytest.raises(FileExistsError):
        write_freeze({"outro": True}, config.processed_dir)
    assert path.read_bytes() == before


def test_missing_raw_dir_is_refused(tmp_path: Path) -> None:
    """Não pula a checagem de órfãos quando o diretório de firmwares falta."""
    config = _config(tmp_path)
    (tmp_path / "raw").rmdir()
    with pytest.raises(FileNotFoundError, match="firmwares ausente"):
        freeze_corpus(config, FROZEN_AT)


def _run(config: Path, raw: Path) -> subprocess.CompletedProcess[str]:
    """Executa a CLI em outro processo."""
    return subprocess.run(
        [
            sys.executable,
            "scripts/freeze_corpus.py",
            "--config",
            str(config),
            "--raw",
            str(raw),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def test_cli_is_deterministic_apart_from_date(tmp_path: Path) -> None:
    """Dois processos geram o mesmo registro, exceto data e dias de desvio."""
    config = _corpus(tmp_path)
    output = tmp_path / "processed" / FREEZE_FILENAME
    manifests = []
    for _ in range(2):
        result = _run(config, tmp_path / "raw")
        assert result.returncode == 0, result.stderr
        manifests.append(json.loads(output.read_text()))
        output.unlink()
    for manifest in manifests:
        manifest.pop("frozen_at")
        manifest.pop("deviation")
    assert manifests[0] == manifests[1]


def test_cli_without_reason_writes_nothing(tmp_path: Path) -> None:
    """Sai com erro e não cria o registro quando falta o motivo do desvio."""
    config = _corpus(tmp_path, reason="")
    result = _run(config, tmp_path / "raw")
    assert result.returncode == 1
    assert "deviation_reason" in result.stderr
    assert not (tmp_path / "processed" / FREEZE_FILENAME).exists()
