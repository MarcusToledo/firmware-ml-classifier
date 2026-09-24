# Tasks: Busca de CVEs na NVD

**Input**: `specs/003-busca-cve/` (spec.md, plan.md, data-model.md)

**Nota**: tasks retroativas. O código já existe em `master`; cada task
`[x]` registra uma verificação feita em 2026-09-24 (FR → módulo → teste ou
cenário conferido). Tasks `[ ]` são lacunas de teste ainda abertas,
espelhadas no `TODO.md`.

## Format: `[ID] [Story] Descrição`

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
- [ ] T030 [US2] FR-003 — filtro de CPE de parte `o` e limite à primeira página do dicionário; teste sugerido em `tests/test_fetch_cves.py`
- [ ] T031 [US2] FR-004 — paginação de CVEs com mais de uma página; teste sugerido em `tests/test_fetch_cves.py`
- [ ] T032 [US2] FR-005 — fallback `MEDIUM` para CVSS v2 sem `baseSeverity`; teste sugerido em `tests/test_fetch_cves.py`
- [ ] T033 [US1] FR-006 — chave do par, forma NVD, persistência e preservação de outras entradas pelo CLI; teste sugerido em `tests/test_fetch_cves.py`
- [ ] T034 [US1] FR-007 — pulo de cache, validação de schema e substituição com `--force`; teste sugerido em `tests/test_fetch_cves.py`
- [ ] T035 [US4] FR-008 — falha de rede, log, ausência de entrada nova e continuação no CLI; teste sugerido em `tests/test_fetch_cves.py`
- [ ] T036 [US4] FR-009 — chamadas de gravação periódica e final pelo CLI; teste sugerido em `tests/test_fetch_cves.py`
- [ ] T037 [US4] FR-010 — `--delay`, padrões por chave de API, esperas e cabeçalho `apiKey`; teste sugerido em `tests/test_fetch_cves.py`
- [ ] T038 [US1] FR-011 — `--dry-run` sem leitura ou escrita do cache nem acesso à rede; teste sugerido em `tests/test_fetch_cves.py`
- [ ] T039 [US4] FR-012 — logs de carregamento, progresso, falha, sucesso e resumo; teste sugerido em `tests/test_fetch_cves.py`

## Dependencies & Execution Order

- Lacunas são independentes entre si; cada uma só depende do módulo citado.
