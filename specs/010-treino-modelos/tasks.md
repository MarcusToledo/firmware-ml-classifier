# Tasks: Treino de modelos e baselines

**Input**: `specs/010-treino-modelos/` (spec.md, plan.md, research.md,
data-model.md, contracts/cli.md)

**Nota**: FR-001 a FR-013 Planejado (TickTick T09 e T05). FR-014 é
Proposto e não tem task. Testes antes da implementação em cada fase.

## Format: `[ID] [P?] [Story] Descrição`

## Phase 1: Setup

- [ ] T001 FR-003, FR-011, FR-012 — Criar `configs/training.yaml` com hiperparâmetros (inclusive `n_jobs: 1`), `class_weight: balanced`, os dois experimentos e `output_dir: models/runs`
- [ ] T002 FR-007 — Declarar `joblib` em `pyproject.toml` e criar o pacote `src/models/__init__.py`

## Phase 2: Foundational

- [ ] T003 [US1] FR-001 — Testes de leitura da configuração com override e de falha por SHA256 divergente da tabela, da proveniência ou dos folds em `tests/test_training.py`
- [ ] T004 [US1] FR-001 — `src/models/training.py::load_training_config` e `load_inputs` (usa `FoldSet` de `load_folds` da `009`, sem ler a tabela à parte)
- [ ] T005 [US4] FR-012 — Cenário US4.2: teste da regra de alvo de cada experimento em `tests/test_training.py`
- [ ] T006 [US4] FR-012 — `src/models/training.py::target_for_experiment`

## Phase 3: User Story 1 - Extra Trees principal por fold (Priority: P1)

- [ ] T007 [US1] FR-002, FR-003, FR-011 — Cenários US1.1, US1.2 e US4.1: testes de um modelo por fold, filtro ajustado só no treino, falha quando nenhuma coluna sobra e parâmetros efetivos do estimador (hiperparâmetros, `n_jobs=1`, peso, seed) em `tests/test_training.py`
- [ ] T008 [US1] FR-002, FR-003, FR-011 — `Pipeline` com `VarianceThreshold(0.0)` e `ExtraTreesClassifier` em `src/models/training.py::build_pipeline`
- [ ] T009 [US1] FR-005, FR-006 — Cenário US1.4: testes de conjunto de colunas por parâmetro, de esquema `random` e de probabilidades com todas as classes quando uma falta no treino em `tests/test_training.py`
- [ ] T010 [US1] FR-005, FR-006 — Laço por (repetição, fold) e predições em `src/models/training.py::train_run`
- [ ] T011 [US1] FR-006, FR-007 — Testes de `run_id` estável e distinto por modelo, de diretório existente que falha sem `--force`, de `purpose` por modelo e esquema (inclusive `random` → `diagnostico`), de configuração efetiva, de modelos gravados só no braço principal e de metadados por fold (colunas, hiperparâmetros, seed, `firmware_id` de treino, SHA256) em `tests/test_training.py`
- [ ] T012 [US1] FR-006, FR-007 — `src/models/training.py::run_id`, `purpose_for` e `write_run`

## Phase 4: User Story 2 - Random Forest como baseline de ML (Priority: P1)

- [ ] T013 [US2] FR-004 — Cenário US2.1: teste de mesmos (repetição, fold, `firmware_id`) e mesmo protocolo que o Extra Trees em `tests/test_training.py`
- [ ] T014 [US2] FR-004 — `RandomForestClassifier` em `src/models/training.py::build_pipeline`

## Phase 5: User Story 3 - Baselines de referência (Priority: P1)

- [ ] T015 [P] [US3] FR-008, FR-009, FR-010 — Cenários US3.1 a US3.3: testes de majoritário (empate em três classes e no binário, probabilidade 1/0), de identidade (one-hot com fabricante canônico, multi-hot, `purpose: diagnostico`) e de `score_firmware` (predição igual à da `006`, probabilidade 1/0, SHA256 da tabela de features divergente, mapeamento binário) em `tests/test_baselines.py`
- [ ] T016 [US3] FR-008 — `src/models/baselines.py::majority_predictions`
- [ ] T017 [US3] FR-009 — `src/models/baselines.py::identity_features` e execução com o Extra Trees de `train_run`, `role=diagnostico`
- [ ] T018 [US3] FR-010 — `src/models/baselines.py::score_firmware_predictions`, lendo a tabela de features registrada em `training_table.meta.json`

## Phase 6: CLI e reprodutibilidade

- [ ] T019 [US1] FR-013 — Cenário US1.3: teste de duas execuções em processos separados com `predictions.parquet` idêntico, no Extra Trees e no baseline de identidade (folhas impuras), e teste do log em `tests/test_train_cli.py`
- [ ] T020 [US1] FR-013 — CLI `scripts/train.py::main` conforme `contracts/cli.md`, com o log de FR-013

## Phase 7: Polish

- [ ] T021 FR-006, FR-007 — Rodar `--model all` nos dois experimentos e nos dois esquemas e registrar os `run_id` no `TODO.md`
- [ ] T022 FR-001, FR-013 — Atualizar `AGENTS.md`: Pipeline Commands com `scripts/train.py` (e, se ainda não estiverem, os comandos de `008` e `009`) e o papel do model-agent sem "tune" (tuning é Proposto, `009/FR-009`)

## Dependencies & Execution Order

- T001 → T002 → T003 → T004 → T005 → T006 → Phase 3 → Phase 4.
- T007 depende de T012 para as asserções que leem `run.meta.json`; as
  asserções sobre o estimador passam com T008.
- Phase 5 depende de T010 e T012 (usa `train_run` e `write_run`).
- Dependências de outras specs: T004 depende de 009/T014 (`load_folds`).
- Phase 6 depende das fases 3 a 5; T021 exige `008` e `009` implementadas.
- `[P]`: T015 só toca `tests/test_baselines.py`.
