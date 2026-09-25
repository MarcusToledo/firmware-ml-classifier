# Tasks: Busca de CVEs na NVD

**Input**: `specs/003-busca-cve/` (spec.md, plan.md, data-model.md)

**Nota**: tasks retroativas. O código já existe em `master`; cada task
`[x]` registra uma verificação feita em 2026-09-24 (FR → módulo → teste ou
cenário conferido). Tasks `[ ]` das fases 1 a 5 são lacunas de teste ainda
abertas, espelhadas no `TODO.md`. A Phase 6 decompõe os FRs Planejado
(TickTick T11); FR-019 e FR-020 são Proposto e não têm task.

## Format: `[ID] [P?] [Story] Descrição`

## Phase 1: User Story 1 - Cache de CVE por par, retomável (Priority: P1)

**Goal**: gerar um cache JSON por par fabricante/modelo, retomável sem repetir pares válidos.

- [x] T001 [US1] FR-001 — `scripts/fetch_cves.py::extract_pairs`, `main` → `tests/test_fetch_cves.py::test_extract_pairs_dedupes_and_normalizes`, `tests/test_fetch_cves.py::test_extract_pairs_skips_missing_values`, `tests/test_fetch_cves.py::test_extract_pairs_empty_dataframe`, `tests/test_fetch_cves.py::test_extract_pairs_sorted` (parcial)
- [x] T002 [US1] FR-002 — `scripts/fetch_cves.py::VENDOR_ALIASES`, `normalize_vendor`, `normalize_model` → `tests/test_fetch_cves.py::test_normalize_vendor_dlink`, `tests/test_fetch_cves.py::test_normalize_vendor_tplink`, `tests/test_fetch_cves.py::test_normalize_vendor_tp_link_underscore`, `tests/test_fetch_cves.py::test_normalize_vendor_passthrough`, `tests/test_fetch_cves.py::test_normalize_model_with_hyphen`, `tests/test_fetch_cves.py::test_normalize_model_missing_hyphen`, `tests/test_fetch_cves.py::test_normalize_model_underscore_suffix`, `tests/test_fetch_cves.py::test_normalize_model_double_underscore`, `tests/test_fetch_cves.py::test_normalize_model_underscore_separated_words`, `tests/test_fetch_cves.py::test_normalize_model_never_sends_underscore`, `tests/test_fetch_cves.py::test_normalize_model_plain`
- [x] T003 [US1] FR-006 — `scripts/fetch_cves.py::fetch_cves_for_pair`, `load_cache`, `save_cache`, `main` → `tests/test_fetch_cves.py::test_fetch_keyword_retains_cve_and_configurations` (parcial)
- [ ] T004 [US1] FR-007 — `scripts/fetch_cves.py::main` → sem teste
- [ ] T005 [US1] FR-011 — `scripts/fetch_cves.py::main` → sem teste
- [x] T006 [US1] Cenário US1.1 — confirmado (teste `tests/test_fetch_cves.py::test_extract_pairs_dedupes_and_normalizes`)
- [x] T007 [US1] Cenário US1.2 — confirmado (teste `tests/test_fetch_cves.py::test_extract_pairs_skips_missing_values`)
- [x] T008 [US1] Cenário US1.3 — confirmado (script: simulou cache v2 e comprovou pulo sem chamar a NVD)
- [x] T009 [US1] Cenário US1.4 — confirmado (script: simulou `--force` e comprovou nova consulta e substituição)
- [x] T010 [US1] Cenário US1.5 — confirmado (script: simulou `--dry-run` e comprovou listagem sem rede nem cache)

## Phase 2: User Story 2 - Evidência auditável por CVE (Priority: P1)

**Goal**: preservar a origem da consulta, o CPE resolvido e a evidência auditável de cada CVE.

- [x] T011 [US2] FR-003 — `scripts/fetch_cves.py::resolve_cpe_name`, `_fetch_cpe_page`, `_canonical_cpe_token` → `tests/test_fetch_cves.py::test_resolve_cpe_selects_matching_firmware_and_wildcards_version`, `tests/test_fetch_cves.py::test_resolve_cpe_generalizes_specific_update_and_edition` (parcial)
- [x] T012 [US2] FR-004 — `scripts/fetch_cves.py::fetch_cves_for_pair`, `_fetch_all_pages`, `_fetch_page` → `tests/test_fetch_cves.py::test_fetch_prefers_resolved_cpe_query`, `tests/test_fetch_cves.py::test_fetch_keyword_retains_cve_and_configurations` (parcial)
- [x] T013 [US2] FR-005 — `scripts/fetch_cves.py::extract_cvss`, `severity_bucket`, `_fetch_all_pages` → `tests/test_fetch_cves.py::test_extract_cvss_v31`, `tests/test_fetch_cves.py::test_extract_cvss_v30_fallback`, `tests/test_fetch_cves.py::test_extract_cvss_v2_fallback`, `tests/test_fetch_cves.py::test_extract_cvss_no_metrics`, `tests/test_fetch_cves.py::test_extract_cvss_empty_cve`, `tests/test_fetch_cves.py::test_fetch_keyword_retains_cve_and_configurations` (parcial)
- [x] T014 [US2] Cenário US2.1 — confirmado (teste `tests/test_fetch_cves.py::test_resolve_cpe_selects_matching_firmware_and_wildcards_version`)
- [x] T015 [US2] Cenário US2.2 — confirmado (teste `tests/test_fetch_cves.py::test_resolve_cpe_generalizes_specific_update_and_edition`)
- [x] T016 [US2] Cenário US2.3 — confirmado (teste `tests/test_fetch_cves.py::test_fetch_prefers_resolved_cpe_query`)
- [x] T017 [US2] Cenário US2.4 — confirmado (teste `tests/test_fetch_cves.py::test_fetch_keyword_retains_cve_and_configurations`)
- [x] T018 [US2] Cenário US2.5 — confirmado (testes `tests/test_fetch_cves.py::test_extract_cvss_v31` e `tests/test_fetch_cves.py::test_extract_cvss_no_metrics`)

## Phase 3: User Story 3 - Nome interno vira termo da NVD (Priority: P2)

**Goal**: converter nomes internos de fabricante e modelo para a grafia usada pela NVD.

- [x] T019 [US3] Cenário US3.1 — confirmado (testes `tests/test_fetch_cves.py::test_normalize_vendor_dlink`, `tests/test_fetch_cves.py::test_normalize_vendor_tplink`, `tests/test_fetch_cves.py::test_normalize_vendor_tp_link_underscore` e `tests/test_fetch_cves.py::test_normalize_vendor_passthrough`)
- [x] T020 [US3] Cenário US3.2 — confirmado (teste `tests/test_fetch_cves.py::test_normalize_model_missing_hyphen`)
- [x] T021 [US3] Cenário US3.3 — confirmado (testes `tests/test_fetch_cves.py::test_normalize_model_underscore_separated_words` e `tests/test_fetch_cves.py::test_normalize_model_underscore_suffix`)

## Phase 4: User Story 4 - Falha de rede não perde progresso nem cria evidência (Priority: P2)

**Goal**: manter o progresso observável e não criar uma entrada nova quando uma consulta falha.

- [ ] T022 [US4] FR-008 — `scripts/fetch_cves.py::main` → sem teste
- [x] T023 [US4] FR-009 — `scripts/fetch_cves.py::_should_save`, `SAVE_INTERVAL`, `main` → `tests/test_fetch_cves.py::test_should_save_at_interval`, `tests/test_fetch_cves.py::test_should_save_between_intervals` (parcial)
- [ ] T024 [US4] FR-010 — `scripts/fetch_cves.py::_build_headers`, `DEFAULT_DELAY_NO_KEY`, `DEFAULT_DELAY_WITH_KEY`, `main` → sem teste
- [ ] T025 [US4] FR-012 — `scripts/fetch_cves.py::main` → sem teste
- [x] T026 [US4] Cenário US4.1 — confirmado (script: simulou `URLError`, conferiu `[FAIL]`, ausência de entrada nova e processamento do par seguinte)
- [x] T027 [US4] Cenário US4.2 — confirmado (script: lançou exceção não capturada no segundo par e conferiu a gravação do primeiro no `finally`)
- [x] T028 [US4] Cenário US4.3 — confirmado (script: simulou dez sucessos e observou a gravação periódica e a final)

## Phase 5: Lacunas de teste

- [ ] T029 [US1] FR-001 — leitura seletiva de `meta_brand` e `meta_model` via `--features`; teste sugerido em `tests/test_fetch_cves.py`
- [ ] T030 [US2] FR-003 — filtro de CPE de parte `o` (o limite à primeira página deixa de valer com FR-018, T048); teste sugerido em `tests/test_fetch_cves.py`
- [ ] T031 [US2] FR-004 — paginação de CVEs com mais de uma página; teste sugerido em `tests/test_fetch_cves.py`
- [ ] T032 [US2] FR-005 — fallback `MEDIUM` para CVSS v2 sem `baseSeverity`; teste sugerido em `tests/test_fetch_cves.py`
- [ ] T033 [US1] FR-006 — chave do par, forma NVD, persistência e preservação de outras entradas pelo CLI; teste sugerido em `tests/test_fetch_cves.py`
- [ ] T034 [US1] FR-007 — pulo de cache, validação de schema e substituição com `--force`; teste sugerido em `tests/test_fetch_cves.py`
- [ ] T035 [US4] FR-008 — falha de rede, log, ausência de entrada nova e continuação no CLI; teste sugerido em `tests/test_fetch_cves.py`
- [ ] T036 [US4] FR-009 — chamadas de gravação periódica e final pelo CLI; teste sugerido em `tests/test_fetch_cves.py`
- [ ] T037 [US4] FR-010 — `--delay`, padrões por chave de API, esperas e cabeçalho `apiKey`; teste sugerido em `tests/test_fetch_cves.py`
- [ ] T038 [US1] FR-011 — `--dry-run` sem leitura ou escrita do cache nem acesso à rede; teste sugerido em `tests/test_fetch_cves.py`
- [ ] T039 [US4] FR-012 — logs de carregamento, progresso, falha, sucesso e resumo; teste sugerido em `tests/test_fetch_cves.py`

## Phase 6: Implementação planejada (TickTick T11)

**Goal**: Cache datado, sem entrada velha após falha, com `cvss_max` pelo
maior score, CPE inequívoco, path canônico e falha explícita com 0 pares.

- [ ] T040 [US5] FR-013 — Remover a entrada anterior do par quando a consulta com `--force` falha e terminar com código ≠ 0 quando algum par falhou, depois de gravar o cache, em `scripts/fetch_cves.py::main`
- [ ] T041 [US5] FR-013 — Cenário US5.1: testes com a NVD simulada (falha com e sem `--force`, código de saída) em `tests/test_fetch_cves.py`
- [ ] T042 [US5] FR-014 — Gravar `schema_version: 3` e `fetched_at` (ISO 8601, UTC) em `scripts/fetch_cves.py::fetch_cves_for_pair` e tratar como esquema antigo toda entrada com versão diferente de 3 em `main`
- [ ] T043 [US5] FR-014 — Cenário US5.2: testes de `schema_version: 3`, `fetched_at` e de entrada v2 recusada em `tests/test_fetch_cves.py`
- [ ] T044 [US5] FR-015 — Mudar o padrão de `--output` para `dataset/processed/cve_cache_v2.json` em `scripts/fetch_cves.py::main`, com teste do cenário US5.3 em `tests/test_fetch_cves.py`
- [ ] T045 [US5] FR-016 — Maior `baseScore` entre as fontes da versão preferida e `severity` da métrica escolhida em `scripts/fetch_cves.py::extract_cvss`
- [ ] T046 [US5] FR-016 — Cenário US5.4: acrescentar teste com duas fontes na mesma versão em `tests/test_fetch_cves.py`
- [ ] T047 [US5] FR-017 — Falhar com 0 pares (mensagem com `--label-from-path`) em `scripts/fetch_cves.py::main` e contar no log as linhas descartadas por identidade nula em `extract_pairs` (que continua devolvendo lista vazia), com teste do cenário US5.5 em `tests/test_fetch_cves.py`
- [ ] T048 [US5] FR-018 — Percorrer todas as páginas do dicionário de CPE, preferir `o`, usar `h` sem `o`, distinguir CPEs pela tupla (parte, fabricante, produto) e gravar `cpe_candidates` em toda entrada (caindo na busca por texto com ambiguidade), em `scripts/fetch_cves.py::resolve_cpe_name`, `_fetch_cpe_page` e `fetch_cves_for_pair`
- [ ] T049 [US5] FR-018 — Cenário US5.6: testes de segunda página, parte `h`, versões do mesmo produto sem ambiguidade e ambiguidade real em `tests/test_fetch_cves.py`
- [ ] T050 [US5] FR-013, FR-014, FR-015, FR-016, FR-017, FR-018, FR-021 — Rodar a busca completa sobre as features reextraídas (`001-extracao-features`, T050) gerando `dataset/processed/cve_cache_v2.json` e o `.meta.json`; medir SC-004 (100% com `fetched_at`) e SC-006 (pares com ambiguidade com `cpe_candidates` não vazio); registrar no `TODO.md` a data, o número de pares, de CVEs, de pares com `cpe_candidates` e com parte `h`, e as falhas
- [ ] T051 [US5] FR-021 — Gravar `<nome>.meta.json` ao lado do cache (argumentos, caminho e SHA256 de `--features`, commit, início e fim, contagens), sem gravar com `--dry-run`, em `scripts/fetch_cves.py::main` e `save_cache`
- [ ] T052 [US5] FR-021 — Cenário US5.7: teste do conteúdo dos metadados e de `--dry-run` sem gravação em `tests/test_fetch_cves.py`

## Dependencies & Execution Order

- Lacunas são independentes entre si; cada uma só depende do módulo citado.
- Phase 6: todas as implementações editam `scripts/fetch_cves.py` e todos
  os testes `tests/test_fetch_cves.py`: nenhuma task desta fase roda em
  paralelo. Ordem sugerida: T047, T044, T042, T045, T048, T040, T051, com
  o teste de cada uma logo depois. T050 depende de todas e de `001/T050`
  (pares da tabela reextraída); os rótulos da 005 (T056) são regerados
  depois de T050, lendo o cache novo por `--cves`.
