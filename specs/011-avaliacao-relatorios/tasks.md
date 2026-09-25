# Tasks: Avaliação e relatórios

**Input**: `specs/011-avaliacao-relatorios/` (spec.md, plan.md,
research.md, data-model.md, contracts/cli.md)

**Nota**: FR-001 a FR-012 Planejado (TickTick T10, T05 e T03). FR-013 e
FR-014 são Proposto e não têm task. Testes antes da implementação em cada
fase.

## Format: `[ID] [P?] [Story] Descrição`

## Phase 1: Setup

- [ ] T001 FR-001, FR-003, FR-005, FR-007, FR-010 — Criar `configs/evaluation.yaml` com a matriz, os grupos E/B/S/F, os braços (inclusive `sem_url_ip`), os modelos de ablation, o bootstrap e a permutação
- [ ] T002 FR-001 — Criar o pacote `src/evaluation/__init__.py`

## Phase 2: Foundational

- [ ] T003 [US6] FR-001 — Testes de matriz gerada pela `010` (inclusive `random` nos dois experimentos), de `run_id` reaproveitado, de falha com hash recalculado diferente e com diretório incompleto, de commit diferente registrado, de SHA256 de folds comparado por esquema e de falha com tabela, proveniência ou meta da `008` divergentes (US6.2), e de falha de treino de braço citando o braço em `tests/test_eval_runs.py`
- [ ] T004 [US6] FR-001 — `src/evaluation/runs.py::build_matrix`, `ensure_run` (via `010` `run_id`) e `check_same_inputs`

## Phase 3: User Story 1 - Métricas que não escondem as classes minoritárias (Priority: P1)

- [ ] T005 [US1] FR-002 — Cenários US1.1 e US1.2: testes com predições de valores conhecidos (três classes e binário), classes fixas, métrica indefinida = 0 e contada, fold de teste sem classe listado em `tests/test_eval_metrics.py`
- [ ] T006 [US1] FR-002 — `src/evaluation/metrics.py::metrics_by_repeat` e matriz de confusão somada

## Phase 4: User Story 2 - Modelos contra baselines e identidade (Priority: P1)

- [ ] T007 [US2] FR-003 — Cenário US2.1: testes de bootstrap pareado por grupo (reamostra grupos, mesmas reamostragens para os dois modelos, seed fixa, IC percentil, diferença idêntica a zero entre um modelo e ele mesmo) em `tests/test_eval_comparison.py`
- [ ] T008 [US2] FR-003 — `src/evaluation/comparison.py::paired_group_bootstrap`
- [ ] T009 [US2] FR-004 — Cenário US2.2: teste da tabela de comparação com a linha de identidade marcada `diagnostico` e a diferença do Extra Trees contra ela em `tests/test_eval_comparison.py`
- [ ] T010 [US2] FR-004 — `src/evaluation/report.py::comparison_table`

## Phase 5: User Story 3 - Ablations por grupo de features (Priority: P1)

- [ ] T011 [US3] FR-005, FR-006, FR-007 — Cenários US3.1 e US3.2: testes de resolução dos braços contra as colunas da tabela, grupo F ausente registrado sem executar, nenhum braço com `doc2vec_*` e colunas do braço `sem_url_ip` em `tests/test_eval_ablation.py`
- [ ] T012 [US3] FR-005, FR-006, FR-007 — `src/evaluation/ablation.py::resolve_arms` e tabela de ablation com diferença pareada contra o completo

## Phase 6: User Story 4 - Diagnósticos de vazamento e de exclusão (Priority: P2)

- [ ] T013 [US4] FR-008, FR-009 — Cenários US4.1 e US4.2: testes da tabela `grouped` × `random` com IC pelos grupos de `folds_grouped`, marcada `diagnostico`, de `purpose` em toda tabela por execução e seções separadas no `report.md` (SC-005) e da tabela de exclusões lida dos metadados da `008` em `tests/test_eval_report.py`
- [ ] T014 [US4] FR-008, FR-009 — `src/evaluation/report.py::split_diagnostic_table` e `exclusion_tables`

## Phase 7: User Story 5 - Importância de features (Priority: P2)

- [ ] T015 [P] [US5] FR-010 — Cenários US5.1 e US5.2: testes de permutação no teste de cada fold com os modelos gravados, de scorer com classes fixas num fold sem classe, de feature sem sinal com IC 95% contendo 0 e de aviso do MDI no apêndice em `tests/test_eval_importance.py`
- [ ] T016 [US5] FR-010 — `src/evaluation/importance.py::permutation_by_fold` (`make_scorer` com classes fixas, `zero_division=0`, `n_jobs=1`, IC percentil) e MDI em apêndice com aviso

## Phase 8: User Story 6 - Relatório reprodutível (Priority: P2)

- [ ] T017 [US6] FR-011, FR-012 — Cenário US6.1: teste de duas gerações em processos separados com CSV, PNG e `report.md` idênticos e `report.meta.json` completo, de IC em toda diferença (SC-004), e teste do log em `tests/test_evaluate_cli.py`
- [ ] T018 [US6] FR-011 — `src/evaluation/report.py::write_report` (CSV ordenados com formato fixo, `report.md` sem data e com seções por `purpose`, PNG com `metadata` fixo, `report.meta.json`)
- [ ] T019 [US6] FR-012 — CLI `scripts/evaluate.py::main` conforme `contracts/cli.md`

## Phase 9: Polish

- [ ] T020 FR-011 — Gerar o relatório real e registrar no `TODO.md` o diretório em `reports/` e os `run_id`
- [ ] T021 FR-011 — Acrescentar `scripts/evaluate.py` aos Pipeline Commands do `AGENTS.md`

## Dependencies & Execution Order

- T001 → T002 → T003 → T004 → fases 3 a 8 → Phase 9.
- T004 depende de `010` (T010, T012: `train_run`, `write_run`) e de `009`
  (T014: `load_folds`).
- T013 depende de `008` (T020: metadados com contagens); T013–T014
  testam o módulo `report.py`, sem depender da CLI (T019).
- Grupo F: quando a `012` for implementada, enumerar as colunas F em
  `configs/evaluation.yaml` (T001).
- T016 depende dos modelos por fold do braço principal (`010/FR-007`).
- `[P]`: T015 só toca `tests/test_eval_importance.py`.
