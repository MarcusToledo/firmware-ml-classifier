# Tasks: Evidências de segurança

**Input**: `specs/002-evidencias-seguranca/` (spec.md, plan.md, data-model.md)

**Nota**: tasks retroativas. O código já existe em `master`; cada task
`[x]` registra uma verificação feita em 2026-09-24 (FR → módulo → teste ou
cenário conferido). Tasks `[ ]` são lacunas de teste ainda abertas,
espelhadas no `TODO.md`.

## Format: `[ID] [Story] Descrição`

## Phase 2: User Story 1 - Banca audita cada achado (Priority: P1)

**Goal**: Permitir que a banca relacione cada evidência ao texto de origem, à regra e ao firmware.

- [x] T001 [US1] FR-001 — `pipeline/feature_extraction.py::extract_features_from_path` → `tests/test_pipeline_extraction.py::test_extract_features_from_path_calls_extract_ascii_strings_once` (parcial)
- [x] T002 [US1] FR-002 — `src/evidence/findings.py::SecurityFinding` → `tests/test_evidence_findings.py::test_security_finding_holds_all_fields` (parcial)
- [x] T003 [US1] FR-003 — `src/evidence/patterns.py::find_hardcoded_passwords` → `tests/test_evidence_patterns.py::test_passwords_finding_has_high_confidence_on_kv_match`
- [x] T004 [US1] FR-007 — `src/evidence/patterns.py::find_telnetd` → `tests/test_evidence_patterns.py::test_telnetd_finding_has_high_confidence` (parcial)
- [x] T005 [US1] FR-015 — `src/evidence/patterns.py::scan_strings_findings` → `tests/test_pipeline_extraction.py::test_extract_features_from_path_includes_structured_findings` (parcial)
- [x] T006 [US1] FR-016 — `scripts/extract_features.py::main` → `tests/test_pipeline_cli.py::test_cli_findings_output` (parcial)
- [x] T007 [US1] Cenário US1.1 — confirmado (teste `tests/test_pipeline_cli.py::test_cli_findings_output`)
- [x] T008 [US1] Cenário US1.2 — confirmado (teste `tests/test_pipeline_cli.py::test_cli_without_findings_output_does_not_write_file`)
- [x] T009 [US1] Cenário US1.3 — confirmado (teste `tests/test_evidence_patterns.py::test_passwords_finding_has_high_confidence_on_kv_match`)
- [x] T010 [US1] Cenário US1.4 — confirmado (teste `tests/test_pipeline_extraction.py::test_extract_features_from_path_empty_file_has_no_findings`)

## Phase 3: User Story 2 - Contagens e flags estáveis no vetor (Priority: P1)

**Goal**: Manter 13 colunas de evidência estáveis e derivadas dos mesmos achados auditáveis.

- [x] T011 [US2] FR-004 — `src/evidence/patterns.py::find_credential_pairs` → `tests/test_evidence_patterns.py::test_cred_pairs_multiple_in_one_string_counts_once`
- [x] T012 [US2] FR-005 — `src/evidence/patterns.py::find_hardcoded_ips` → `tests/test_evidence_patterns.py::test_ips_valid_match`
- [x] T013 [US2] FR-006 — `src/evidence/patterns.py::find_public_ips` → `tests/test_evidence_patterns.py::test_public_ips_multiple_in_one_string` (parcial)
- [x] T014 [US2] FR-008 — `src/evidence/patterns.py::find_debug_account` → `tests/test_evidence_patterns.py::test_debug_account_case_insensitive`
- [x] T015 [US2] FR-009 — `src/evidence/patterns.py::_find_outdated_version` → `tests/test_evidence_patterns.py::test_libssl_outdated`, `tests/test_evidence_patterns.py::test_busybox_outdated`, `tests/test_evidence_patterns.py::test_dropbear_outdated` (parcial)
- [x] T016 [US2] FR-010 — `src/evidence/patterns.py::find_urls` → `tests/test_evidence_patterns.py::test_urls_multiple_in_one_string`
- [x] T017 [US2] FR-011 — `src/evidence/patterns.py::find_api_tokens` → `tests/test_evidence_patterns.py::test_tokens_hex_32_chars` (parcial)
- [x] T018 [US2] FR-012 — `src/evidence/binwalk_findings.py::find_crypto_signatures` → `tests/test_evidence_binwalk_findings.py::test_count_crypto_signatures_matches`
- [x] T019 [US2] FR-013 — `src/evidence/binwalk_findings.py::find_encrypted_sections` → `tests/test_evidence_binwalk_findings.py::test_has_encrypted_true`
- [x] T020 [US2] FR-014 — `src/evidence/patterns.py::findings_to_counts` → `tests/test_evidence_patterns.py::test_scan_strings_returns_all_keys`, `tests/test_pipeline_extraction.py::test_extract_features_with_mocked_binwalk` (parcial)
- [x] T021 [US2] Cenário US2.1 — confirmado (teste `tests/test_evidence_patterns.py::test_scan_strings_returns_all_keys`, `tests/test_evidence_patterns.py::test_scan_strings_empty_defaults`)
- [x] T022 [US2] Cenário US2.2 — confirmado (script: comparou as contagens derivadas dos achados com o dicionário esperado explícito)
- [x] T023 [US2] Cenário US2.3 — confirmado (teste `tests/test_pipeline_extraction.py::test_extract_features_with_mocked_binwalk`)
- [x] T024 [US2] Cenário US2.4 — confirmado (teste `tests/test_evidence_patterns.py::test_cred_pairs_multiple_in_one_string_counts_once`, `tests/test_evidence_patterns.py::test_public_ips_multiple_in_one_string`)

## Phase 4: User Story 3 - Evidência sem nova leitura e sem CVE (Priority: P2)

**Goal**: Reaproveitar apenas strings e descrições já extraídas, sem introduzir identidade ou dados de CVE.

- [x] T025 [US3] Cenário US3.1 — confirmado (teste `tests/test_pipeline_extraction.py::test_extract_features_from_path_calls_extract_ascii_strings_once`)
- [x] T026 [US3] Cenário US3.2 — confirmado (script: simulou path ausente e conferiu achados vazios e as 13 evidências em 0/`False`)
- [x] T027 [US3] Cenário US3.3 — confirmado (teste `tests/test_pipeline_extraction.py::test_classifier_features_exclude_cve_and_identity_fields`)

## Phase 5: Lacunas de teste

- [ ] T028 [US1] FR-001 — ausência de consulta a CVE, NVD ou identidade e reuso das descrições do Binwalk sem nova varredura; teste sugerido em `tests/test_pipeline_extraction.py`
- [ ] T029 [US1] FR-002 — `type` e `detector_version="1.0"` nos achados gerados por cada detector; teste sugerido em `tests/test_evidence_patterns.py`
- [ ] T030 [US2] FR-006 — exclusões de IP público ainda não exercitadas; teste sugerido em `tests/test_evidence_patterns.py`
- [ ] T031 [US1] FR-007 — distinção de maiúsculas em `telnetd`; teste sugerido em `tests/test_evidence_patterns.py`
- [ ] T032 [US2] FR-009 — metadados dos achados de BusyBox, Dropbear e OpenSSL; teste sugerido em `tests/test_evidence_patterns.py`
- [ ] T033 [US2] FR-011 — token não hexadecimal, bordas, confiança e contexto truncado; teste sugerido em `tests/test_evidence_patterns.py`
- [ ] T034 [US2] FR-014 — contagens derivadas com mais de um achado sem comparação tautológica; teste sugerido em `tests/test_evidence_patterns.py`
- [ ] T035 [US1] FR-015 — ordem completa dos 13 detectores na lista de achados; teste sugerido em `tests/test_evidence_patterns.py`
- [ ] T036 [US1] FR-016 — oito campos, UTF-8, diretório pai e log do total no JSONL; teste sugerido em `tests/test_pipeline_cli.py`

## Dependencies & Execution Order

- Lacunas são independentes entre si; cada uma só depende do módulo citado.
