# Tasks: Extração estática de features

**Input**: `specs/001-extracao-features/` (spec.md, plan.md, data-model.md)

**Nota**: tasks retroativas. O código já existe em `master`; cada task
`[x]` registra uma verificação feita em 2026-09-24 (FR → módulo → teste ou
cenário conferido). Tasks `[ ]` das fases 2 a 6 são lacunas de teste ainda
abertas, espelhadas no `TODO.md`. A Phase 7 decompõe os FRs Planejado
(TickTick T11 e T07); FR-017 é Proposto e não tem task.

## Format: `[ID] [P?] [Story] Descrição`

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
- [ ] T031 [US4] FR-007 — fallback do Binwalk em timeout e com retorno de erro (o Binwalk ausente deixa de ser fallback com FR-014); teste sugerido em `tests/test_pipeline_extraction.py`
- [ ] T032 [US4] FR-008 — conjunto integrado das 11 features de strings, 2 de Binwalk e `doc2vec_*`; teste sugerido em `tests/test_pipeline_extraction.py`
- [ ] T033 [US1] FR-009 — cardinalidade e esquema completo de 14 metadados em parquet e CSV; teste sugerido em `tests/test_pipeline_cli.py`
- [ ] T034 [US2] FR-010 — nulidade simultânea dos cinco metadados sem `--label-from-path`; teste sugerido em `tests/test_pipeline_cli.py`
- [ ] T035 [US1] FR-012 — opção `--workers` da CLI; teste sugerido em `tests/test_pipeline_cli.py`
- [ ] T036 [US1] FR-013 — campos de log por arquivo; teste sugerido em `tests/test_pipeline_cli.py`
- [ ] T037 001/princípio V — determinismo da saída em processos separados; teste sugerido em `tests/test_pipeline_extraction.py`

## Phase 7: Implementação planejada (TickTick T11 e T07)

**Goal**: Binwalk obrigatório com estado por arquivo, leitura completa em
blocos (estatísticas, SHA256 e strings), desempacotamento isolado e
limitado com detectores sobre todas as strings, `max_bytes` obrigatório e
Doc2Vec desligado por padrão.

- [ ] T038 [US3] FR-014 — Conferir, antes do lote, que o Binwalk existe na versão 2.3.4 ou posterior e falhar sem ele, em `scripts/extract_features.py::main` e `pipeline/feature_extraction.py::extract_features_batch`
- [ ] T039 [US3] FR-014 — Gravar `meta_binwalk_status` (`ok`, `erro`, `timeout`, `nao_executado`), avisar no log com `erro` e fazer a execução sair com código ≠ 0 quando houver `timeout`, em `pipeline/feature_extraction.py::_extract_binwalk_descriptions`, `extract_features_from_path`, `_build_error_result` e `scripts/extract_features.py::main`
- [ ] T040 [US3] FR-014 — Cenários US3.4 e US3.5: testes de erro, timeout, `nao_executado` e Binwalk ausente ou antigo em `tests/test_pipeline_extraction.py` e `tests/test_pipeline_cli.py`
- [ ] T041 [US5] FR-015 — Ler o arquivo em blocos até `max_bytes` e calcular `entropy`, `byte_mean`, `compress_ratio`, `entropy_variance_across_sections`, o SHA256 e as strings ASCII de forma incremental, com memória que não cresce com o arquivo, em `src/io_utils.py`, `src/features/statistics.py`, `src/features/strings.py` e `pipeline/feature_extraction.py::extract_features_from_path`
- [ ] T042 [US5] FR-015 — Gravar `meta_file_size` em `pipeline/feature_extraction.py::extract_features_from_path` e `_build_error_result`, e mudar `max_bytes` para 256 MiB em `configs/feature_extraction.yaml`
- [ ] T043 [P] [US5] FR-015 — Cenário US5.1: testes de igualdade entre cálculo em blocos e em memória em `tests/test_statistics.py` e `tests/test_strings.py`
- [ ] T044 [US5] FR-016 — Criar `src/features/unpack.py`: conferir os extratores e as versões antes do lote e registrá-las no log; desempacotar com `binwalk -e` num diretório temporário, com `HOME` temporário, sem privilégio de administrador, sem executar nada e sem seguir symlinks; encerrar o extrator ao passar de 2 GiB, 100 mil arquivos ou 300 s (varredura periódica do diretório); devolver o estado
- [ ] T045 [US5] FR-016 — Passar aos detectores, em streaming e em ordem lexicográfica de path, as strings de todos os arquivos regulares extraídos (leitura de cada um até `max_bytes`, contando `meta_unpack_files_cut`); limitar e deduplicar só o documento de strings; cair para o arquivo bruto com `sem_filesystem`, `falha`, `limite_tamanho` e `limite_arquivos`; tratar `limite_tempo` como falha sem fallback; gravar `meta_unpack_status` e `meta_strings_source` (com `nao_executado` em `_build_error_result`), em `pipeline/feature_extraction.py::extract_features_from_path` e `src/features/strings.py`
- [ ] T046 [US5] FR-016 — Cenários US5.4 a US5.6: testes de limites, symlink, path traversal passando pelo extrator (fixture maliciosa), isolamento de `HOME`, limpeza do diretório e corte por arquivo em `tests/test_unpack.py`
- [ ] T047 [US5] FR-015, FR-016 — Cenários US5.1 a US5.3: testes de `meta_file_size`, memória de pico com `tracemalloc` num arquivo maior que vários blocos, `meta_unpack_status`, `meta_strings_source`, fallback para `blob` e `limite_tempo` sem fallback em `tests/test_pipeline_extraction.py`
- [ ] T048 [US4] FR-018 — Chave `doc2vec.enabled` falsa por padrão (com e sem YAML); desligada, não carregar o modelo, não emitir aviso de modelo ausente, gravar `meta_doc2vec_used=False` e não gerar colunas `doc2vec_*`, em `configs/feature_extraction.yaml`, `pipeline/feature_extraction.py::load_pipeline_config`, `extract_features_batch`, `extract_features_from_path` e `src/feature_extraction.py::combine_features`
- [ ] T049 [US4] FR-018 — Cenário US4.3: testes com o padrão (sem `doc2vec_*`, sem carga do modelo) e com o Doc2Vec ligado em `tests/test_pipeline_extraction.py`
- [ ] T050 [US5] FR-014, FR-015, FR-016, FR-018, FR-019 — Reextrair `dataset/processed/features_v2.parquet` com `--label-from-path` e `--findings-output dataset/processed/findings_v2.jsonl`; medir a distribuição de `meta_binwalk_status`, `meta_unpack_status`, `meta_strings_source` e `meta_unpack_files_cut`, o número de timeouts (SC-007: 0) e a fração de arquivos regulares extraídos que contribuem com strings; registrar colunas antes/depois no `TODO.md`
- [ ] T051 [US3] FR-019 — `max_bytes` obrigatório: padrão 256 MiB sem YAML; erro para nulo, não positivo e `--config` inexistente, em `pipeline/feature_extraction.py::load_pipeline_config`
- [ ] T052 [P] [US3] FR-019 — Cenário US3.6: testes do padrão e das rejeições em `tests/test_pipeline_config.py`

## Dependencies & Execution Order

- Lacunas são independentes entre si; cada uma só depende do módulo citado.
- Phase 7: T051 → T038 → T039 → T040. T041 → T042 → T043. T044 → T045;
  T046 depende de T044 e T047 de T045. T048 → T049. T039, T041, T042,
  T045, T048 e T051 editam `pipeline/feature_extraction.py`: não rodam em
  paralelo entre si. T040, T047 e T049 editam
  `tests/test_pipeline_extraction.py`: em série. T050 depende de todas as
  anteriores, da Phase 6 da `002-evidencias-seguranca` (detectores
  corrigidos) e de 012/T013 (features do filesystem, reextração única); os rótulos da 005 (T056) e a medição dos achados da 002
  (T047) vêm depois de T050.
