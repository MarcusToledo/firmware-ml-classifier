# Tasks: Extração estática de features

**Input**: `specs/001-extracao-features/` (spec.md, plan.md, data-model.md)

**Nota**: tasks retroativas. O código já existe em `master`; cada task
`[x]` registra uma verificação feita em 2026-09-24 (FR → módulo → teste ou
cenário conferido). Tasks `[ ]` são lacunas de teste ainda abertas,
espelhadas no `TODO.md`.

## Format: `[ID] [Story] Descrição`

## Phase 2: User Story 1 - Extração em lote reprodutível (Priority: P1)

**Goal**: gerar, a partir de configuração versionada, uma tabela com uma linha por arquivo candidato a firmware.

- [x] T001 [US1] FR-001 — `scripts/extract_features.py::gather_paths` → `tests/test_pipeline_cli.py::test_cli_directory_input` (parcial)
- [x] T002 [US1] FR-002 — `pipeline/feature_extraction.py::load_pipeline_config` → `tests/test_pipeline_config.py::test_load_pipeline_config_with_overrides`
- [x] T003 [US1] FR-004 — `pipeline/feature_extraction.py::extract_features_from_path` → `tests/test_pipeline_extraction.py::test_extract_features_from_path_valid_file` (parcial)
- [x] T004 [US1] FR-009 — `scripts/extract_features.py::main` → `tests/test_pipeline_cli.py::test_cli_basic_file` (parcial)
- [x] T005 [US1] FR-012 — `pipeline/feature_extraction.py::extract_features_batch` → `tests/test_pipeline_extraction.py::test_extract_features_batch_preserves_order_with_multiple_workers` (parcial)
- [x] T006 [US1] FR-013 — `scripts/extract_features.py::main` → `tests/test_pipeline_cli.py::test_cli_reports_elapsed_time` (parcial)
- [x] T007 [US1] Cenário US1.1 — confirmado (script: CLI sobre diretório temporário produziu exatamente duas linhas)
- [x] T008 [US1] Cenário US1.2 — confirmado (script: saídas parquet e CSV do mesmo firmware tiveram colunas idênticas)
- [x] T009 [US1] Cenário US1.3 — confirmado (script: override dot-path limitou a string extraída a oito caracteres)
- [x] T010 [US1] Cenário US1.4 — confirmado (teste `tests/test_pipeline_extraction.py::test_extract_features_batch_preserves_order_with_multiple_workers`)
- [x] T011 [US1] Cenário US1.5 — confirmado (teste `tests/test_pipeline_cli.py::test_cli_reports_elapsed_time`)

## Phase 3: User Story 2 - Vetor sem identidade nem CVE (Priority: P1)

**Goal**: manter o vetor sem identidade ou CVE e ocultar a identidade dos metadados no modo inferência.

- [x] T012 [US2] FR-010 — `scripts/extract_features.py::main` → `tests/test_pipeline_cli.py::test_cli_without_label_from_path_zeroes_version` (parcial)
- [x] T013 [US2] FR-011 — `pipeline/feature_extraction.py::extract_features_from_path` → `tests/test_pipeline_extraction.py::test_classifier_features_exclude_cve_and_identity_fields`
- [x] T014 [US2] Cenário US2.1 — confirmado (teste `tests/test_pipeline_extraction.py::test_classifier_features_exclude_cve_and_identity_fields`)
- [x] T015 [US2] Cenário US2.2 — confirmado (script: modo inferência gravou nulos nos cinco metadados de identidade)
- [x] T016 [US2] Cenário US2.3 — confirmado (script: modo rotulado preencheu os cinco metadados a partir do path)

## Phase 4: User Story 3 - Firmware não confiável não derruba o lote (Priority: P2)

**Goal**: concluir o lote e registrar uma linha de falha para firmware vazio ou ilegível.

- [x] T017 [US3] FR-003 — `src/io_utils.py::read_binary`, `pipeline/feature_extraction.py::extract_features_from_path` → `tests/test_pipeline_extraction.py::test_extract_features_from_path_empty_file` (parcial)
- [x] T018 [US3] Cenário US3.1 — confirmado (script: arquivo vazio produziu `read_ok=False`, erro exato e `firmware_id` nulo)
- [x] T019 [US3] Cenário US3.2 — confirmado (script: `max_bytes=0` produziu a mensagem de erro especificada)
- [x] T020 [US3] Cenário US3.3 — confirmado (teste `tests/test_pipeline_extraction.py::test_extract_features_batch_continues_on_error`)

## Phase 5: User Story 4 - Features estatísticas, de strings e estruturais (Priority: P2)

**Goal**: produzir um conjunto estável de features estatísticas, de strings ASCII e estruturais do Binwalk.

- [x] T021 [US4] FR-005 — `src/features/statistics.py` → `tests/test_statistics.py::test_entropy_variance_different_blocks`
- [x] T022 [US4] FR-006 — `src/features/strings.py`, `src/feature_extraction.py::extract_features` → `tests/test_feature_vector.py::test_extract_features_exposes_limited_strings` (parcial)
- [x] T023 [US4] FR-007 — `src/features/binwalk.py`, `pipeline/feature_extraction.py::_extract_binwalk_descriptions` → `tests/test_pipeline_extraction.py::test_extract_features_with_mocked_binwalk` (parcial)
- [x] T024 [US4] FR-008 — `pipeline/feature_extraction.py::extract_features_from_path` → `tests/test_pipeline_extraction.py::test_extract_features_includes_string_pattern_keys` (parcial)
- [x] T025 [US4] Cenário US4.1 — confirmado (script: Binwalk simulado com squashfs e LZMA preencheu as três features)
- [x] T026 [US4] Cenário US4.2 — confirmado (script: Binwalk ausente manteve todas as chaves estruturais e de padrões)

## Phase 6: Lacunas de teste

- [ ] T027 [US1] FR-001 — entrada `.txt`, extensões excluídas e arquivos ocultos; teste sugerido em `tests/test_pipeline_cli.py`
- [ ] T028 [US3] FR-003 — leitura com `max_bytes>0` e mensagens exatas de erro nos metadados; teste sugerido em `tests/test_pipeline_extraction.py`
- [ ] T029 [US1] FR-004 — SHA256 exato dos bytes limitados por `max_bytes`; teste sugerido em `tests/test_pipeline_extraction.py`
- [ ] T030 [US4] FR-006 — propagação de truncamento para `meta_truncated`; teste sugerido em `tests/test_pipeline_extraction.py`
- [ ] T031 [US4] FR-007 — fallback do Binwalk ausente, em timeout e com retorno de erro; teste sugerido em `tests/test_pipeline_extraction.py`
- [ ] T032 [US4] FR-008 — conjunto integrado das 11 features de strings, 2 de Binwalk e `doc2vec_*`; teste sugerido em `tests/test_pipeline_extraction.py`
- [ ] T033 [US1] FR-009 — cardinalidade e esquema completo de 14 metadados em parquet e CSV; teste sugerido em `tests/test_pipeline_cli.py`
- [ ] T034 [US2] FR-010 — nulidade simultânea dos cinco metadados sem `--label-from-path`; teste sugerido em `tests/test_pipeline_cli.py`
- [ ] T035 [US1] FR-012 — opção `--workers` da CLI; teste sugerido em `tests/test_pipeline_cli.py`
- [ ] T036 [US1] FR-013 — campos de log por arquivo; teste sugerido em `tests/test_pipeline_cli.py`
- [ ] T037 001/princípio V — determinismo da saída em processos separados; teste sugerido em `tests/test_pipeline_extraction.py`

## Dependencies & Execution Order

- Lacunas são independentes entre si; cada uma só depende do módulo citado.
