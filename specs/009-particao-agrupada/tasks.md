# Tasks: Partição agrupada

**Input**: `specs/009-particao-agrupada/` (spec.md, plan.md, research.md,
data-model.md, contracts/cli.md)

**Nota**: FR-001 a FR-008 Planejado (TickTick T03). FR-009 e FR-010 são
Proposto e não têm task. Testes antes da implementação em cada fase.

## Format: `[ID] [P?] [Story] Descrição`

## Phase 1: Setup

- [ ] T001 FR-004 — Acrescentar a seção `partition` (`n_splits: 5`, `seeds: [0, 1, 2, 3, 4]`) a `configs/dataset.yaml`, lida pelo carregador da `008` (`load_dataset_config`)

## Phase 2: Foundational

- [ ] T002 [US2] FR-001 — Testes de SHA256 divergente da tabela e da proveniência em relação a `outputs` de `training_table.meta.json` em `tests/test_partition.py`
- [ ] T003 [US2] FR-001 — Ler e conferir as entradas da `008` em `src/dataset/partition.py::load_training_inputs`

## Phase 3: User Story 1 - Grupos sem vazamento (Priority: P1)

- [ ] T004 [US1] FR-002 — Cenários US1.1, US1.3 e US1.4: testes de binário em dois modelos, de modelo com dois binários, de chave canônica (caixa, `-`, `_`, espaços), de linhas `in_table=false` ignoradas e de identificador de grupo igual com linhas em outra ordem em `tests/test_partition.py`
- [ ] T005 [US1] FR-002 — Chave canônica e componentes conectados do grafo `firmware_id`–chave de modelo, com identificador `g:` + menor `firmware_id`, em `src/dataset/partition.py::model_key` e `build_groups`
- [ ] T006 [US1] FR-003 — Cenário US1.2: teste de guarda sobre folds gerados e sobre folds forjados com `firmware_id` cruzando (os dois esquemas) e com chave de modelo cruzando (só `grouped`) em `tests/test_partition.py`
- [ ] T007 [US1] FR-003 — Checagem de cruzamento por esquema, falhando sem gravar, em `src/dataset/partition.py::check_no_crossing`

## Phase 4: User Story 2 - Divisão principal reprodutível (Priority: P1)

- [ ] T008 [US2] FR-004 — Testes de 5 folds × `len(seeds)` repetições com as seeds da configuração, de estratificação por `security_level` e de cada `firmware_id` no teste de exatamente um fold por repetição (SC-003) em `tests/test_partition.py`
- [ ] T009 [US2] FR-004 — Folds com `StratifiedGroupKFold(shuffle=True, random_state=seed)` em `src/dataset/partition.py::grouped_folds`
- [ ] T010 [US2] FR-005, FR-008 — Cenários US2.1 e US2.2: teste de duas execuções em processos separados com parquet idêntico e metadados diferentes só em `created_at`, de fold de teste sem classe registrado sem interromper, de contagem por classe e fabricante (multi-fabricante), de configuração efetiva nos metadados e do log em `tests/test_make_folds_cli.py`
- [ ] T011 [US2] FR-005 — Gravar `folds_grouped.parquet` e `folds_grouped.meta.json` em `src/dataset/partition.py::write_folds`
- [ ] T012 [US2] FR-005, FR-008 — CLI `scripts/make_folds.py::main` conforme `contracts/cli.md`, com o log de FR-008
- [ ] T013 [US2] FR-006 — Cenário US2.3: testes de `load_folds` com tabela, proveniência e arquivo de folds alterados, e de `FoldSet` com seeds e SHA256 em `tests/test_partition.py`
- [ ] T014 [US2] FR-006 — `src/dataset/partition.py::FoldSet` e `load_folds`

## Phase 5: User Story 3 - Diagnóstico com divisão aleatória (Priority: P2)

- [ ] T015 [US3] FR-007 — Cenário US3.1: teste de `folds_random.*` separado, com `scheme: random` e `purpose: diagnostico`, com as mesmas seeds e sem `firmware_id` repetido em treino e teste em `tests/test_partition.py`
- [ ] T016 [US3] FR-007 — `src/dataset/partition.py::random_folds` e gravação em `write_folds`

## Phase 6: Polish

- [ ] T017 FR-005, FR-008 — Gerar os folds reais e registrar no `TODO.md` o número de grupos, o maior grupo e os folds de teste sem alguma classe

## Dependencies & Execution Order

- T001 → T002 → T003 → Phase 3 → Phase 4 → Phase 5 → T017.
- Dependências da `008`: T001 depende de 008/T001 (`configs/dataset.yaml`);
  T003 de 008/T002 (`src/dataset/`, `load_dataset_config`); T002 e T003 de
  008/T020 (`training_table.meta.json` com `outputs`).
- T010–T012 dependem de T009 e T007; T013–T014 dependem de T011.
- T016 reaproveita `write_folds` (T011).
- Depende da `008` implementada (T020 da 008, `write_artifacts`) para
  T017.
