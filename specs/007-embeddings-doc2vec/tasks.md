# Tasks: Embeddings Doc2Vec

**Input**: `specs/007-embeddings-doc2vec/` (spec.md, plan.md, data-model.md)

**Nota**: tasks retroativas. O código já existe em `master`; cada task
`[x]` registra uma verificação feita em 2026-09-24 (FR → módulo → teste ou
cenário conferido). Tasks `[ ]` são lacunas de teste ainda abertas,
espelhadas no `TODO.md`. FR-011 a FR-015 são `[Proposto, TickTick T06]` e
não têm task: ganham tasks só quando o pesquisador promover a T06 a
Planejado.

## Format: `[ID] [Story] Descrição`

## Phase 1: User Story 1 - Treinar o modelo Doc2Vec a partir do dataset (Priority: P1)

**Goal**: Obter um modelo Doc2Vec gravado, com um documento de strings por firmware e parâmetros da configuração versionada.

- [ ] T001 [US1] FR-001 — `scripts/train_doc2vec.py::gather_paths`, `src/cli_utils.py::gather_paths` → sem teste
- [x] T002 [US1] FR-002 — `scripts/train_doc2vec.py::build_documents`, `src/features/strings.py::tokenize_document` → `tests/test_strings.py::test_tokenize_document_basic` (parcial)
- [x] T003 [US1] FR-003 — `scripts/train_doc2vec.py::build_documents`, `src/features/doc2vec.py::build_corpus` → `tests/test_doc2vec.py::test_build_corpus_preserves_doc_ids_and_tokens` (parcial)
- [x] T004 [US1] FR-004 — `src/features/doc2vec.py::Doc2VecConfig`, `pipeline/feature_extraction.py::load_pipeline_config` → `tests/test_pipeline_config.py::test_load_pipeline_config_defaults`, `tests/test_pipeline_config.py::test_load_pipeline_config_with_overrides`, `tests/test_pipeline_config.py::test_override_nested_doc2vec` (parcial)
- [x] T005 [US1] FR-005 — `src/features/doc2vec.py::train_doc2vec` → `tests/test_doc2vec.py::test_train_doc2vec_enforces_workers_one`
- [x] T006 [US1] FR-006 — `scripts/train_doc2vec.py::main`, `src/features/doc2vec.py::train_doc2vec`, `save_doc2vec`, `load_doc2vec` → `tests/test_doc2vec.py::test_train_doc2vec_model_has_expected_vector_size_and_docvecs`, `tests/test_doc2vec.py::test_save_load_roundtrip_preserves_config_and_infer_behavior` (parcial)
- [x] T007 [US1] Cenário US1.1 — confirmado (script: treinou corpus sintético e conferiu modelo padrão e log do path)
- [x] T008 [US1] Cenário US1.2 — confirmado (script: aplicou `doc2vec.vector_size=200` e carregou modelo com 200 posições)
- [x] T009 [US1] Cenário US1.3 — confirmado (script: gravou `--output` aninhado e conferiu a criação dos diretórios)
- [x] T010 [US1] Cenário US1.4 — confirmado (script: `workers=2` falhou citando `workers` sem gravar modelo)
- [x] T011 [US1] Cenário US1.5 — confirmado (script: corpus vazio ou sem tokens falhou com a mensagem definida)

## Phase 2: User Story 2 - Vetor Doc2Vec na tabela de features (Priority: P1)

**Goal**: Produzir as colunas `doc2vec_*` e a proveniência `meta_doc2vec_used` em cada linha extraída.

- [x] T012 [US2] FR-007 — `pipeline/feature_extraction.py::load_doc2vec_model`, `_init_worker`, `extract_features_batch` → `tests/test_pipeline_config.py::test_null_model_path` (parcial)
- [x] T013 [US2] FR-008 — `src/features/doc2vec.py::infer_embedding`, `src/feature_extraction.py::extract_features`, `combine_features` → `tests/test_doc2vec.py::test_infer_embedding_empty_tokens_returns_zero_finite_vector`, `tests/test_doc2vec.py::test_infer_embedding_oov_tokens_finite` (parcial)
- [x] T014 [US2] FR-009 — `pipeline/feature_extraction.py::extract_features_from_path`, `_build_error_result` → `tests/test_pipeline_extraction.py::test_extract_features_from_path_valid_file` (parcial)
- [x] T015 [US2] Cenário US2.1 — confirmado (script: path inexistente emitiu warning, produziu 20 zeros e marcou `meta_doc2vec_used=False`)
- [x] T016 [US2] Cenário US2.2 — confirmado (script: modelo real mínimo produziu 100 colunas finitas não nulas e `meta_doc2vec_used=True`)
- [x] T017 [US2] Cenário US2.3 — confirmado (script: documento sem tokens produziu 100 zeros e `meta_doc2vec_used=True`)
- [x] T018 [US2] Cenário US2.4 — confirmado (teste `tests/test_doc2vec.py::test_infer_embedding_oov_tokens_finite`)

## Phase 3: User Story 3 - Inspecionar os tokens antes do treino (Priority: P3)

**Goal**: Inspecionar uma amostra de tokens com os mesmos limites usados no treino, sem gerar modelo.

- [ ] T019 [US3] FR-010 — `scripts/inspect_tokens.py::main`, `extract_tokens` → sem teste
- [x] T020 [US3] Cenário US3.1 — confirmado (script: `--max-docs 1 --limit 5` registrou um firmware e cinco tokens)
- [x] T021 [US3] Cenário US3.2 — confirmado (script: `feature.max_doc_chars=10` excluiu tokens além do corte)

## Phase 4: Lacunas de teste

- [ ] T022 [US1] FR-001 — os três tipos de entrada, a recursão e os filtros de nome e extensão nos CLIs; teste sugerido em `tests/test_doc2vec_cli.py`
- [ ] T023 [US1] FR-002 — aplicação conjunta dos limites no treino e na inspeção; teste sugerido em `tests/test_doc2vec_cli.py`
- [ ] T024 [US1] FR-003 — SHA256 como tag, pulos com warning e erro de corpus vazio; teste sugerido em `tests/test_doc2vec_cli.py`
- [ ] T025 [US1] FR-004 — padrões completos e opções `--config` e `--override` nos dois CLIs; teste sugerido em `tests/test_doc2vec_cli.py`
- [ ] T026 [US1] FR-006 — precedência do output, criação de diretórios, sobrescrita e log; teste sugerido em `tests/test_doc2vec_cli.py`
- [ ] T027 [US2] FR-007 — warning de ausência e carga única do modelo por processo; teste sugerido em `tests/test_pipeline_extraction.py`
- [ ] T028 [US2] FR-008 — colunas `doc2vec_*` na extração integrada sem e com modelo; teste sugerido em `tests/test_pipeline_extraction.py`
- [ ] T029 [US2] FR-009 — `meta_doc2vec_used=True` com modelo, inclusive sem tokens; teste sugerido em `tests/test_pipeline_extraction.py`
- [ ] T030 [US3] FR-010 — limite, preview, log e pulo de firmware vazio na inspeção; teste sugerido em `tests/test_doc2vec_cli.py`

## Dependencies & Execution Order

- Lacunas são independentes entre si; cada uma só depende do módulo citado.
