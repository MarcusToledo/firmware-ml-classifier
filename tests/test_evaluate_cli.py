"""Exercita a CLI de avaliação final com relatórios byte a byte idênticos (011)."""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

import pandas as pd

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


def test_excluded_vendor_without_corpus_reports_not_applicable(
    tmp_path: Path,
) -> None:
    """Registra a exclusão válida sem estimar o cenário sem alias."""
    processed, training_yaml = evaluation_corpus(tmp_path, exclude_tp_link=True)
    freeze = json.loads(
        (processed / "corpus.freeze.json").read_text(encoding="utf-8")
    )
    assert freeze["exclusions"]["excluded_by_vendor_reason"]["tp_link"][
        "indeterminado"
    ] > 0
    config = evaluation_yaml(tmp_path, training_yaml)
    process = _evaluate(config)
    assert process.returncode == 0, process.stderr
    reason = "tp_link com 0 firmware_id no corpus congelado"
    assert "WARNING" in process.stderr and reason in process.stderr
    report = Path(process.stdout.strip())
    scenarios = pd.read_csv(report / "sensitivity_comparison.csv")
    excluded = scenarios.set_index("scenario").loc["sem_alias_tp_link"]
    assert excluded["status"] == "não aplicável"
    assert excluded["reason"] == reason
    numeric = [
        "n_firmware_id", "n_components", "macro_f1_b2", "macro_f1_b2_ci_low",
        "macro_f1_b2_ci_high", "macro_f1_b1", "macro_f1_b1_ci_low",
        "macro_f1_b1_ci_high", "delta", "delta_ci_low", "delta_ci_high",
    ]
    assert excluded[numeric].isna().all()
    for name in ("todos_fabricantes", "peso_componente"):
        assert pd.notna(scenarios.set_index("scenario").loc[name, "delta"])
    text = (report / "report.md").read_text(encoding="utf-8")
    scenario_line = next(
        line for line in text.splitlines() if line.startswith("| sem_alias_tp_link |")
    )
    cells = [cell.strip() for cell in scenario_line.strip("|").split("|")]
    assert cells[:3] == ["sem_alias_tp_link", "não aplicável", reason]
    assert all(not cell for cell in cells[3:])
    manifest = _manifest(report)
    assert manifest["sensitivity_scenarios"]["sem_alias_tp_link"] == {
        "status": "não aplicável", "reason": reason,
    }


def test_unknown_vendor_fails_without_report(tmp_path: Path) -> None:
    """Recusa fabricante sem proveniência nem exclusões no congelamento."""
    _, training_yaml = evaluation_corpus(tmp_path)
    config = evaluation_yaml(tmp_path, training_yaml)
    process = _evaluate(
        config, "--override", "sensitivity.exclude_alias_vendor=inexistente"
    )
    assert process.returncode == 1
    assert "fabricante inexistente ausente" in process.stderr
    assert not (tmp_path / "reports").exists()
