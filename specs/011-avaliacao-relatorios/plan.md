# Implementation Plan: Avaliação e relatórios

**Branch**: `docs/escopo-restante` | **Date**: 2026-09-25 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/011-avaliacao-relatorios/spec.md`

**Note**: spec nova, Status Misto: FR-001 a FR-012 Planejado (TickTick
T10, T05 e T03), FR-013 e FR-014 Proposto, sem task. Nenhum código existe
ainda; módulos e testes abaixo são previstos. Estrutura decidida pelo
pesquisador em 2026-09-25 ([research.md](research.md)).

## Summary

`scripts/evaluate.py` lê `configs/evaluation.yaml`, gera pela `010`
(`train_run`) a matriz de execuções e os braços de ablation, reaproveitando
`run_id` existentes com os mesmos parâmetros, e confere que todas usam a
mesma tabela e os mesmos folds. Calcula as métricas por repetição sobre as
predições out-of-fold, os IC 95% e as diferenças pareadas por bootstrap
por grupo da `009`, a importância por permutação nos modelos do braço
principal e as tabelas de diagnóstico (agrupada × aleatória,
`indeterminado` por fabricante). Grava CSV, `report.md`, PNG e
`report.meta.json` em `reports/<timestamp>/`.

## Technical Context

**Language/Version**: Python ≥ 3.9

**Primary Dependencies**: scikit-learn (`metrics`,
`inspection.permutation_importance`), numpy, pandas, matplotlib, PyYAML
(todos declarados)

**Storage**: `reports/<timestamp>/` com `*.csv`, `report.md`, `*.png`,
`report.meta.json`

**Testing**: pytest

**Target Platform**: Linux

**Project Type**: pacote `src/evaluation/` com CLI `scripts/evaluate.py`

**Performance Goals**: sem meta; 2000 reamostragens × execuções × 5
repetições sobre até 573 `firmware_id`

**Constraints**: CSV, PNG e `report.md` determinísticos (SC-002):
ordenação fixa de linhas e colunas, formato numérico fixo, PNG com
`metadata` fixo, seeds da configuração; `n_jobs=1` na permutação (mesma
razão de `010` R8); macro-F1 com classes fixas; nada de p-valor (FR-003)

**Scale/Scope**: matriz principal de 14 execuções (5 baselines/modelos ×
2 experimentos em `grouped` + ET e RF × 2 experimentos em `random`) e até
20 execuções de ablation (10 braços × 2 modelos, com F)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

|Princípio|Resultado|Evidência|
|---|---|---|
|I. Somente análise estática|Não se aplica|Só lê artefatos da `008` a `010`|
|II. Rótulo exclusivamente por CVE|Passa|Métricas contra o `security_level` da `008`; `score_firmware` só como baseline|
|III. Sem vazamento|Violação justificada|Métricas só sobre predições out-of-fold; importância no teste de cada fold; comparação obrigatória com o baseline de identidade (FR-004); coluna `purpose` em toda tabela e seções separadas no `report.md` (FR-008, SC-005); sem braço Doc2Vec (FR-006). A `011` dispara as execuções no esquema `random` (FR-001): ver Complexity Tracking|
|IV. Modelos simples|Passa|Modelos Extra Trees e Random Forest; os demais são baselines sem família nova; importância por permutação, sem o viés do MDI|
|V. Reprodutibilidade|Passa|Resultados em `reports/<timestamp>/` com `run_id`, commit por execução, SHA256 e configuração efetiva (FR-011); seeds do bootstrap e da permutação na configuração; CSV, PNG e `report.md` idênticos entre gerações (SC-002); logs de FR-012|
|VI. Firmware não confiável|Não se aplica|Sem leitura de firmware|
|VII. Integridade científica|Passa|Nenhum número de resultado na spec; incerteza obrigatória em toda diferença (SC-004)|

Re-check após Phase 1: sem mudança.

## Project Structure

### Documentation (this feature)

```text
specs/011-avaliacao-relatorios/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── cli.md
├── tasks.md
└── checklists/
    ├── requirements.md
    └── rastreabilidade.md
```

### Source Code (repository root)

```text
src/evaluation/
├── __init__.py
├── runs.py          # matriz de execuções, reaproveitamento de run_id, checagem de SHA256
├── metrics.py       # métricas por repetição, matriz de confusão
├── comparison.py    # bootstrap pareado por grupo
├── ablation.py      # grupos e braços
├── importance.py    # permutação por fold
└── report.py        # CSV, report.md, PNG, report.meta.json

scripts/
└── evaluate.py      # CLI (novo)

configs/
└── evaluation.yaml  # matriz, grupos, braços, bootstrap, permutação (novo)

tests/
├── test_eval_runs.py
├── test_eval_metrics.py
├── test_eval_comparison.py
├── test_eval_ablation.py
├── test_eval_importance.py
├── test_eval_report.py
└── test_evaluate_cli.py
```

**Structure Decision**: pacote novo `src/evaluation/`; a `011` chama
`train_run` da `010` e `load_folds` da `009`.

### US → FR → módulo → teste → TickTick

|FR|US|Módulo (previsto)|Teste (previsto)|TickTick|
|---|---|---|---|---|
|FR-001|US6|`src/evaluation/runs.py::build_matrix`, `ensure_run` (usa `010` `run_id`), `check_same_inputs`|`tests/test_eval_runs.py` (reaproveita, hash divergente e diretório incompleto falham, SHA256 de folds por esquema, meta da `008` divergente, US6.2)|T10|
|FR-002|US1|`src/evaluation/metrics.py::metrics_by_repeat`|`tests/test_eval_metrics.py` (US1.1, US1.2, valores à mão, métrica indefinida = 0, binário)|T05|
|FR-003|US2|`src/evaluation/comparison.py::paired_group_bootstrap`|`tests/test_eval_comparison.py` (US2.1, reamostragem por grupo, seed fixa)|T10|
|FR-004|US2|`src/evaluation/report.py::comparison_table`|`tests/test_eval_comparison.py` (US2.2)|T10|
|FR-005|US3|`src/evaluation/ablation.py::resolve_arms`; `configs/evaluation.yaml`|`tests/test_eval_ablation.py` (US3.1, grupo F ausente)|T10|
|FR-006|US3|`src/evaluation/ablation.py::resolve_arms`|`tests/test_eval_ablation.py` (US3.2)|T10|
|FR-007|US3|`configs/evaluation.yaml` (braço `sem_url_ip`)|`tests/test_eval_ablation.py` (colunas do braço)|T03|
|FR-008|US4|`src/evaluation/report.py::split_diagnostic_table`, `write_report` (seções por `purpose`)|`tests/test_eval_report.py` (US4.1, IC com grupos de `folds_grouped`, SC-005)|T03|
|FR-009|US4|`src/evaluation/report.py::exclusion_tables`|`tests/test_eval_report.py` (US4.2)|T10|
|FR-010|US5|`src/evaluation/importance.py::permutation_by_fold` (scorer com classes fixas)|`tests/test_eval_importance.py` (US5.1, US5.2, fold sem classe, aviso do MDI)|T10|
|FR-011|US6|`src/evaluation/report.py::write_report`|`tests/test_evaluate_cli.py` (US6.1, dois processos com CSV, PNG e `report.md` idênticos)|T10|
|FR-012|US6|`scripts/evaluate.py::main`|`tests/test_evaluate_cli.py` (`caplog`)|T10|
|FR-013 [Proposto]|—|—|— (Proposto: sem task)|T10|
|FR-014 [Proposto]|—|—|— (Proposto: sem task)|T03|

### Sem verificação

Nenhum FR Planejado.

### Símbolos com requisito em outra spec

- `train_run`, `run.meta.json`, `purpose`: `010/FR-005` a `010/FR-007`.
- `load_folds` e grupos: `009/FR-002`, `009/FR-006`.
- Contagens de exclusão e `indeterminado` por fabricante: `008/FR-005`,
  `008/FR-008`.

## Complexity Tracking

|Violação|Por que permanece|Mitigação|
|---|---|---|
|Princípio III — a `011` gera execuções no esquema `random` (FR-001), com modelos em treino e teste (`009/FR-007`)|Mede o efeito da identidade (TickTick T03); decisão do pesquisador no analyze da `009`, registrada também na `009` e na `010`|`purpose: diagnostico` em toda tabela; seção separada no `report.md`; nunca nas seções de resultado (FR-008, SC-005)|
