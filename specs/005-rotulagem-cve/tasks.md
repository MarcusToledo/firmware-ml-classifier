# Tasks: Rotulagem por CVE

**Input**: `specs/005-rotulagem-cve/` (spec.md, plan.md, data-model.md)

**Nota**: tasks retroativas. O código já existe em `master`; cada task
`[x]` registra uma verificação feita em 2026-09-24 (FR → módulo → teste ou
cenário conferido). Tasks `[ ]` das fases 2 a 7 são lacunas de teste ainda
abertas, espelhadas no `TODO.md`. A Phase 8 decompõe os FRs Planejado
(TickTick T04).

## Format: `[ID] [P?] [Story] Descrição`

## Phase 2: User Story 1 - Rótulo de treino vindo só do cache de CVE (Priority: P1)

**Goal**: Garantir que o rótulo venha só do cache e que consulta ausente interrompa a rotulagem.

- [x] T001 [US1] FR-001 — `scripts/generate_labels.py::_load_features` → `tests/test_generate_labels.py::test_cli_filters_version_before_aggregating_aliases` (parcial)
- [x] T002 [US1] FR-003 — `scripts/generate_labels.py::_lookup_cve_entry` → `tests/test_generate_labels.py::test_lookup_normalizes_identity_and_rejects_old_cache`, `tests/test_generate_labels.py::test_lookup_missing_pair_fails_instead_of_becoming_negative` e `tests/test_generate_labels.py::test_cli_reports_missing_identity_before_version_divergence`
- [x] T003 [US1] FR-013 — `src/labeling/cve_labels.py::label_from_cve_stats` → `tests/test_cve_labels.py::test_custom_critical_threshold` e `tests/test_cve_labels.py::test_invalid_threshold_fails` (parcial)
- [x] T004 [US1] FR-014 — `src/labeling/cve_labels.py::label_from_cve_stats` → `tests/test_cve_labels.py::test_label_depends_only_on_cve_fields`
- [x] T005 [US1] Cenário US1.1 — confirmado (teste `tests/test_cve_labels.py::test_known_cve_at_critical_threshold`)
- [x] T006 [US1] Cenário US1.2 — confirmado (teste `tests/test_cve_labels.py::test_known_cve_below_critical_threshold`)
- [x] T007 [US1] Cenário US1.3 — confirmado (teste `tests/test_cve_labels.py::test_label_depends_only_on_cve_fields`)
- [x] T008 [US1] Cenário US1.4 — confirmado (teste `tests/test_generate_labels.py::test_lookup_missing_pair_fails_instead_of_becoming_negative`)
- [x] T009 [US1] Cenário US1.5 — confirmado (script: CLI temporária com `--critical-cvss 7.0` produziu `cve_critica` para CVSS 7.0)

## Phase 3: User Story 2 - CVEs filtradas pela versão do firmware (Priority: P1)

**Goal**: Separar CVEs aplicáveis, indeterminadas e não aplicáveis pela versão do firmware.

- [x] T010 [US2] FR-005 — `src/labeling/cve_labels.py::applicable_cves_for_version` → `tests/test_cve_labels.py::test_missing_version_is_indeterminate`, `tests/test_cve_labels.py::test_missing_version_with_empty_cache_has_negative_evidence` e `tests/test_cve_labels.py::test_applicable_and_indeterminate_cves_are_both_returned`
- [x] T011 [US2] FR-006 — `src/labeling/cve_labels.py::_evaluate_cve` → `tests/test_cve_labels.py::test_configuration_that_never_mentions_target_does_not_apply` e `tests/test_cve_labels.py::test_cve_with_only_other_products_does_not_apply` (parcial)
- [x] T012 [US2] FR-007 — `src/labeling/cve_labels.py::_match_platform` → `tests/test_cve_labels.py::test_target_hardware_platform_without_revision_is_satisfied` e `tests/test_cve_labels.py::test_and_with_other_vulnerable_product_is_indeterminate`
- [x] T013 [US2] FR-008 — `src/labeling/version_match.py::version_in_range` → `tests/test_version_match.py::test_version_in_range_respects_boundaries` e `tests/test_cve_labels.py::test_comparable_version_filters_fixed_release`
- [x] T014 [US2] FR-009 — `src/labeling/cve_labels.py::_normalize_cpe_version` → `tests/test_cve_labels.py::test_asus_exact_cpe_version_normalizes_underscores`, `tests/test_cve_labels.py::test_leading_v_is_removed_for_any_vendor` e `tests/test_cve_labels.py::test_netgear_range_removes_language_package`
- [x] T015 [US2] FR-010 — `src/labeling/cve_labels.py::_match_version` → `tests/test_cve_labels.py::test_exact_cpe_version_is_respected` e `tests/test_cve_labels.py::test_exact_cpe_build_suffix_is_indeterminate_at_base` (parcial)
- [x] T016 [US2] FR-011 — `src/labeling/cve_labels.py::_match_version` → `tests/test_cve_labels.py::test_exact_cpe_with_specific_update_is_indeterminate_when_version_matches` e `tests/test_cve_labels.py::test_not_applicable_update_marker_keeps_match`
- [x] T017 [US2] Cenário US2.1 — confirmado (teste `tests/test_cve_labels.py::test_comparable_version_filters_fixed_release`)
- [x] T018 [US2] Cenário US2.2 — confirmado (teste `tests/test_cve_labels.py::test_missing_version_is_indeterminate`)
- [x] T019 [US2] Cenário US2.3 — confirmado (teste `tests/test_cve_labels.py::test_missing_version_with_empty_cache_has_negative_evidence`)
- [x] T020 [US2] Cenário US2.4 — confirmado (teste `tests/test_cve_labels.py::test_exact_cpe_with_specific_update_is_indeterminate_when_version_matches`)
- [x] T021 [US2] Cenário US2.5 — confirmado (teste `tests/test_cve_labels.py::test_configuration_that_never_mentions_target_does_not_apply`)

## Phase 4: User Story 3 - Mesmo binário, mesmo rótulo (Priority: P1)

**Goal**: Agregar todos os aliases de um `firmware_id` em um único rótulo e estatísticas comuns.

- [x] T022 [US3] FR-012 — `scripts/generate_labels.py::_aggregate_firmware_label` → `tests/test_generate_labels.py::test_aggregate_applicable_cve_overrides_same_indeterminate_cve` e `tests/test_generate_labels.py::test_cli_filters_version_before_aggregating_aliases` (parcial)
- [x] T023 [US3] FR-015 — `scripts/generate_labels.py::_result_to_record` → `tests/test_generate_labels.py::test_cli_filters_version_before_aggregating_aliases` e `tests/test_generate_labels.py::test_cli_missing_version_writes_indeterminate` (parcial)
- [x] T024 [US3] Cenário US3.1 — confirmado (teste `tests/test_generate_labels.py::test_cli_filters_version_before_aggregating_aliases`)
- [x] T025 [US3] Cenário US3.2 — confirmado (teste `tests/test_generate_labels.py::test_aggregate_critical_applicable_with_indeterminate_cve`)
- [x] T026 [US3] Cenário US3.3 — confirmado (teste `tests/test_generate_labels.py::test_aggregate_known_applicable_with_critical_indeterminate_cve`)
- [x] T027 [US3] Cenário US3.4 — confirmado (teste `tests/test_generate_labels.py::test_aggregate_applicable_cve_overrides_same_indeterminate_cve`)

## Phase 5: User Story 4 - Entrada inconsistente interrompe a rotulagem (Priority: P2)

**Goal**: Tornar explícitas as inconsistências da tabela de features e do cache antes de gerar rótulos.

- [x] T028 [US4] FR-002 — `scripts/generate_labels.py::_load_features` → `tests/test_generate_labels.py::test_cli_rejects_missing_meta_path` e `tests/test_generate_labels.py::test_cli_rejects_duplicate_rows` (parcial)
- [x] T029 [US4] FR-004 — `scripts/generate_labels.py::_label_rows` → `tests/test_generate_labels.py::test_cli_rejects_version_divergent_from_meta_path`, `tests/test_generate_labels.py::test_cli_rejects_missing_version_when_meta_path_has_version` e `tests/test_generate_labels.py::test_cli_filters_version_before_aggregating_aliases`
- [x] T030 [US4] Cenário US4.1 — confirmado (teste `tests/test_generate_labels.py::test_cli_rejects_version_divergent_from_meta_path`)
- [x] T031 [US4] Cenário US4.2 — confirmado (teste `tests/test_generate_labels.py::test_cli_rejects_missing_version_when_meta_path_has_version`)
- [x] T032 [US4] Cenário US4.3 — confirmado (teste `tests/test_generate_labels.py::test_cli_reports_missing_identity_before_version_divergence`)
- [x] T033 [US4] Cenário US4.4 — confirmado (testes `tests/test_generate_labels.py::test_cli_rejects_duplicate_rows` e `tests/test_generate_labels.py::test_cli_rejects_missing_meta_path`)
- [x] T034 [US4] Cenário US4.5 — confirmado (teste `tests/test_generate_labels.py::test_lookup_normalizes_identity_and_rejects_old_cache`)

## Phase 6: User Story 5 - Conferência sem gravar (Priority: P3)

**Goal**: Permitir a conferência dos resultados e logs sem gravar a tabela de rótulos.

- [ ] T035 [US5] FR-016 — `scripts/generate_labels.py::main` → sem teste
- [ ] T036 [US5] FR-017 — `scripts/generate_labels.py::main` → sem teste
- [x] T037 [US5] Cenário US5.1 — confirmado (script: CLI temporária com `--dry-run` emitiu contagens e distribuições e não criou a saída)

## Phase 7: Lacunas de teste

- [ ] T038 [US1] FR-001 — entrada parquet sem cobertura na CLI; teste sugerido em `tests/test_generate_labels.py`
- [ ] T039 [US4] FR-002 — tabela vazia, `firmware_id` nulo e cache JSON que não é objeto sem cobertura; teste sugerido em `tests/test_generate_labels.py`
- [ ] T040 [US2] FR-006 — `negate` e produto-alvo derivado de `cpe_name` sem cobertura; teste sugerido em `tests/test_cve_labels.py`
- [ ] T041 [US2] FR-010 — versão CPE exata `-` como indeterminada sem cobertura; teste sugerido em `tests/test_cve_labels.py`
- [ ] T042 [US3] FR-012 — erro para CVE sem ID válido sem cobertura; teste sugerido em `tests/test_generate_labels.py`
- [ ] T043 [US1] FR-013 — `--critical-cvss` pela CLI sem cobertura permanente; teste sugerido em `tests/test_generate_labels.py`
- [ ] T044 [US3] FR-015 — ordem das 9 colunas, criação do diretório e ausência de saída após erro sem cobertura; teste sugerido em `tests/test_generate_labels.py`
- [ ] T045 [US5] FR-016 — `--dry-run` sem cobertura permanente; teste sugerido em `tests/test_generate_labels.py`
- [ ] T046 [US5] FR-017 — logs de contagem, distribuições e caminho gravado sem cobertura permanente; teste sugerido em `tests/test_generate_labels.py`

## Phase 8: Implementação planejada (TickTick T04)

**Goal**: Rótulo agregado auditável e reproduzível: path canônico com
metadados, CPE sem base numérica indeterminada, `meta_version_source`
conferida e aliases com CVEs por alias.

- [ ] T047 [US6] FR-018 — Trocar o padrão de `--output` para `dataset/processed/labels_v2.csv` e gravar `<nome>.meta.json` ao lado da tabela (limiar, caminhos e SHA256 das entradas, commit, data), sem gravar com `--dry-run`, em `scripts/generate_labels.py::main`
- [ ] T048 [US6] FR-018 — Testes do path padrão, dos auxiliares derivados de `--output`, das chaves dos metadados e de `--dry-run` sem auxiliares em `tests/test_generate_labels.py`
- [ ] T049 [US2] FR-019 — Devolver CVE indeterminada para CPE exata sem base numérica e para CPE numérica contra firmware com sufixo na mesma base, depois da normalização de FR-009, em `src/labeling/cve_labels.py::_match_version`
- [ ] T050 [P] [US2] FR-019 — Trocar `test_exact_cpe_without_parseable_base_keeps_known_limitation` por testes de CVE indeterminada (`firmware_4.05.03`; `1.2rc1` contra `1.2`) e ajustar `test_exact_numeric_cpe_does_not_match_firmware_suffix` em `tests/test_cve_labels.py`
- [ ] T051 [US4] FR-020 — Ler `meta_version_source` (`ID_COLUMNS`, `_load_features`), conferir contra a origem reinferida logo depois de FR-004 em `_label_rows` (nulo contra valor falha) e falhar com a coluna ausente, em `scripts/generate_labels.py`
- [ ] T052 [US4] FR-020 — Acrescentar `meta_version_source` a `_run_cli` e às fixtures dos testes de CLI existentes, e escrever os testes de origem divergente, nulo contra valor e coluna ausente em `tests/test_generate_labels.py`
- [ ] T053 [US6] FR-021, FR-023 — Guardar por alias os IDs ordenados das CVEs aplicáveis e indeterminadas em `_aggregate_firmware_label`, gravar `<nome>_aliases.jsonl` ao lado da tabela (ordem de primeira ocorrência, `versions_differ`) e registrar as contagens no log, também com `--dry-run`, em `scripts/generate_labels.py`
- [ ] T054 [US6] FR-022 — Acrescentar `label_strategy` e `alias_count` depois das 9 colunas em `scripts/generate_labels.py::_result_to_record`
- [ ] T055 [US6] FR-021, FR-022, FR-023 — Testes do JSONL (chaves, ordem, `versions_differ`), das colunas novas e das contagens no log em `tests/test_generate_labels.py`
- [ ] T056 [US6] FR-018, FR-019, FR-020, FR-021, FR-022, FR-023 — Regerar `dataset/processed/labels_v2.csv` a partir de features reextraídas pelo código atual (que já grava `meta_version_source`) e registrar a nova distribuição no `TODO.md`; regerar de novo quando `001/FR-015` (leitura completa) for implementado
- [ ] T057 [US6] FR-018 — Verificar SC-007: rodar de novo a rotulagem com os caminhos e SHA256 registrados em `dataset/processed/labels_v2.meta.json` e comparar tabela e JSONL (0 diferenças), registrando o resultado no `TODO.md`

Fora do Spec Kit: o item "Documentar a limitação na metodologia" da
TickTick T04 é texto do TCC (decisão PR-10 do mapa de escopo restante).

## Dependencies & Execution Order

- Lacunas são independentes entre si; cada uma só depende do módulo citado.
- Phase 8: cada teste pode ser escrito antes da sua implementação (T048
  com T047, T050 com T049, T052 com T051, T055 com T053-T054). T048, T052 e
  T055 editam o mesmo arquivo de teste e não rodam em paralelo; T052 vem
  antes, porque atualiza as fixtures usadas pelas outras. T054 depende de
  T053. T056 depende de T047-T055 e de reextrair as features; T057 depende
  de T056.
