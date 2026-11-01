"""Exercita a CLI de avaliação final com relatórios byte a byte idênticos (011)."""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

from src.run_metadata import file_sha256
from tests.eval_fixtures import N_IDS, evaluation_corpus, evaluation_yaml

FAST = ["--override", "bootstrap.n_resamples=50",
        "--override", "permutation.n_repeats=2"]
COMPARED = ("*.csv", "*.png", "report.md", "columns_*.txt")


def _evaluate(config: Path, *extra: str) -> subprocess.CompletedProcess[str]:
    """Executa a CLI com a configuração temporária e overrides rápidos."""
    command = [sys.executable, "scripts/evaluate.py", "--config", str(config),
               *FAST, *extra]
    return subprocess.run(command, capture_output=True, text=True, check=False)


def _compared_files(report: Path) -> dict[str, str]:
    """Retorna o SHA256 dos artefatos que devem ser idênticos entre gerações."""
    return {path.name: file_sha256(path)
            for pattern in COMPARED for path in sorted(report.glob(pattern))}


def _manifest(report: Path) -> dict:
    """Lê o manifesto sem o instante de criação."""
    meta = json.loads((report / "report.meta.json").read_text(encoding="utf-8"))
    meta.pop("created_at")
    return meta


def test_reports_are_identical_and_hide_diagnostics_from_results(
    tmp_path: Path,
) -> None:
    """Gera dois relatórios iguais, sem IDs de firmware e com resultado isolado."""
    _, training_yaml = evaluation_corpus(tmp_path)
    config = evaluation_yaml(tmp_path, training_yaml)
    reports = []
    for _ in range(2):
        process = _evaluate(config)
        assert process.returncode == 0, process.stderr
        reports.append(Path(process.stdout.strip()))
        time.sleep(1.1)
    first, second = reports
    assert first != second
    assert len(_compared_files(first)) == 18
    assert _compared_files(first) == _compared_files(second)
    assert _manifest(first) == _manifest(second)
    ids = [f"id-{index:02}".encode() for index in range(N_IDS)]
    for path in first.iterdir():
        content = path.read_bytes()
        assert not any(firmware_id in content for firmware_id in ids), path.name
    arms = _manifest(first)["arms"]
    text = (first / "report.md").read_text(encoding="utf-8")
    result = text[text.index("## Resultado"):text.index("## Baselines")]
    assert arms["B2"] in text
    for arm in ("B1", "B2_menos_D", "B2_menos_H", "B2_linha"):
        assert arms[arm] not in result


def test_unknown_ablation_column_fails_without_report(tmp_path: Path) -> None:
    """Sai com código 1 e não cria relatório quando a ablação é inválida."""
    _, training_yaml = evaluation_corpus(tmp_path)
    config = evaluation_yaml(tmp_path, training_yaml)
    ablation = '[{arm: X, label: X, remove: ["coluna_inexistente"]}]'
    process = _evaluate(config, "--override", f"ablations={ablation}")
    assert process.returncode == 1
    assert "inexistente" in process.stderr
    assert not (tmp_path / "reports").exists()
