# Tasks: Baseline determinístico de regras

**Input**: `specs/006-baseline-regras/` (spec.md, plan.md)

**Nota**: tasks retroativas. O código já existe em `master`; cada task
`[x]` registra uma verificação feita em 2026-09-24 (FR → módulo → teste ou
cenário conferido). Tasks `[ ]` das fases 1 a 5 são lacunas de teste ainda
abertas, espelhadas no `TODO.md`. A Phase 6 decompõe os FRs Planejado
(TickTick T11).

## Format: `[ID] [P?] [Story] Descrição`

## Phase 1: User Story 1 - Previsão determinística para comparação (Priority: P1)

**Goal**: receber as features e a configuração do baseline e obter nível, score, detalhamento dos sinais e hard rule aplicada.

- [x] T001 [US1] FR-001 — `src/scoring.py::score_firmware` → `tests/test_scoring.py::test_baseline_uses_shared_class_names`, `tests/test_scoring.py::test_signals_breakdown_present`, `tests/test_scoring.py::test_no_signals_returns_no_known_cve`
- [x] T002 [US1] FR-002 — `src/scoring.py::_score_stats`, `src/scoring.py::_score_strings`, `src/scoring.py::_score_binwalk` → `tests/test_scoring.py::test_score_strings_outdated_libssl_raises_score`, `tests/test_scoring.py::test_binwalk_features_contribute`, `tests/test_scoring.py::test_n_filesystems_contributes_to_score` (parcial)
- [x] T003 [US1] FR-003 — `src/scoring.py::score_firmware` → `tests/test_scoring.py::test_stats_only_redistributes_weight`, `tests/test_scoring.py::test_n_filesystems_zero_does_not_activate_binwalk_signal`, `tests/test_scoring.py::test_no_signals_returns_no_known_cve` (parcial)
- [x] T004 [US1] FR-004 — `src/scoring.py::score_firmware` → `tests/test_scoring.py::test_high_score_maps_to_critical_cve`, `tests/test_scoring.py::test_low_risk_maps_to_no_known_cve`, `tests/test_scoring.py::test_custom_thresholds` (parcial)
- [x] T005 [US1] FR-008 — `src/scoring.py::load_scoring_config` → `tests/test_scoring.py::test_scoring_config_loads_without_cve_weight` (parcial)
- [x] T006 [US1] FR-009 — `src/scoring.py::score_firmware` → `tests/test_scoring.py::test_deterministic_same_inputs_same_result` (parcial)
- [x] T007 [US1] Cenário US1.1 — confirmado (teste `tests/test_scoring.py::test_no_signals_returns_no_known_cve`)
- [x] T008 [US1] Cenário US1.2 — confirmado (teste `tests/test_scoring.py::test_high_score_maps_to_critical_cve`)
- [x] T009 [US1] Cenário US1.3 — confirmado (teste `tests/test_scoring.py::test_low_risk_maps_to_no_known_cve`)
- [x] T010 [US1] Cenário US1.4 — confirmado (script: comparou por igualdade os dois resultados completos)
- [x] T011 [US1] Cenário US1.5 — confirmado (teste `tests/test_scoring.py::test_custom_thresholds`)
- [x] T012 [US1] Cenário US1.6 — confirmado (script: usou o score calculado como `low` e como `high`)
- [x] T013 [US1] Cenário US1.7 — confirmado (script: comparou a representação do resultado em dois processos)

## Phase 2: User Story 2 - Baseline sem sinal de CVE (Priority: P1)

**Goal**: tornar auditável que campos de CVE e identidade não afetam o baseline e que sua saída não gera rótulos de treino.

- [x] T014 [US2] FR-006 — `src/scoring.py::score_firmware` → `tests/test_scoring.py::test_baseline_ignores_cve_fields`, `tests/test_scoring.py::test_baseline_has_no_cve_signal`, `tests/test_scoring.py::test_no_signals_returns_no_known_cve` (parcial)
- [ ] T015 [US2] FR-007 — nenhum chamador no pipeline → sem teste
- [x] T016 [US2] Cenário US2.1 — confirmado (teste `tests/test_scoring.py::test_baseline_ignores_cve_fields`)
- [x] T017 [US2] Cenário US2.2 — confirmado (teste `tests/test_scoring.py::test_baseline_has_no_cve_signal`)
- [x] T018 [US2] Cenário US2.3 — confirmado (script: comparou resultados completos com e sem campos `meta_*`)
- [x] T019 [US2] Cenário US2.4 — confirmado (script: buscou chamadas em `src/`, `scripts/` e `pipeline/`)

## Phase 3: User Story 3 - Hard rules só elevam o nível (Priority: P2)

**Goal**: elevar previsões de score baixo por indicadores configurados sem rebaixar níveis mais graves.

- [x] T020 [US3] FR-005 — `src/scoring.py::score_firmware` → `tests/test_scoring.py::test_hard_rule_telnetd_overrides_to_known_cve`, `tests/test_scoring.py::test_hard_rule_debug_account`, `tests/test_scoring.py::test_hard_rule_does_not_downgrade`, `tests/test_scoring.py::test_hard_rule_hardcoded_passwords` (parcial)
- [x] T021 [US3] Cenário US3.1 — confirmado (teste `tests/test_scoring.py::test_hard_rule_telnetd_overrides_to_known_cve`)
- [x] T022 [US3] Cenário US3.2 — confirmado (teste `tests/test_scoring.py::test_hard_rule_debug_account`)
- [x] T023 [US3] Cenário US3.3 — confirmado (teste `tests/test_scoring.py::test_hard_rule_does_not_downgrade`)
- [x] T024 [US3] Cenário US3.4 — confirmado (script: zerou o peso de `strings` e observou `hardcoded_passwords`)
- [x] T025 [US3] Cenário US3.5 — confirmado (script: configurou mínimo `cve_critica` para `has_telnetd`)
- [x] T026 [US3] Cenário US3.6 — confirmado (script: aplicou `has_telnetd` e depois `has_debug_account`)

## Phase 4: User Story 4 - Configuração versionada e grupos ausentes (Priority: P2)

**Goal**: carregar os parâmetros do YAML versionado e redistribuir os pesos quando grupos de sinais estão ausentes.

- [x] T027 [US4] Cenário US4.1 — confirmado (teste `tests/test_scoring.py::test_scoring_config_loads_without_cve_weight`)
- [x] T028 [US4] Cenário US4.2 — confirmado (teste `tests/test_scoring.py::test_stats_only_redistributes_weight`)
- [x] T029 [US4] Cenário US4.3 — confirmado (teste `tests/test_scoring.py::test_n_filesystems_zero_does_not_activate_binwalk_signal`)
- [x] T030 [US4] Cenário US4.4 — confirmado (script: carregou YAML parcial e comparou os padrões)
- [x] T031 [US4] Cenário US4.5 — confirmado (script: observou `TypeError` para chave desconhecida)

## Phase 5: Lacunas de teste

- [ ] T032 [US1] FR-002 — faltam valores exatos das fórmulas e cobertura de `count_hardcoded_ips`, `entropy_variance_across_sections` e `compression_type`; teste sugerido em `tests/test_scoring.py`
- [ ] T033 [US1] FR-003 — falta soma de pesos 0 com grupo presente e o score 0 resultante (sem testar o retorno antes das hard rules, que FR-011 remove); teste sugerido em `tests/test_scoring.py`
- [ ] T034 [US1] FR-004 — faltam as fronteiras inclusivas exatas de `low` e `high`; teste sugerido em `tests/test_scoring.py`
- [ ] T035 [US3] FR-005 — faltam a hard rule `hardcoded_passwords`, mínimo `cve_critica` configurado e última regra aplicada; teste sugerido em `tests/test_scoring.py`
- [ ] T036 [US2] FR-006 — falta provar que campos de identidade não alteram o resultado; teste sugerido em `tests/test_scoring.py`
- [ ] T037 [US2] FR-007 — falta guarda que impeça o baseline de ser chamado pela geração de rótulos ou pelo pipeline; teste sugerido em `tests/test_scoring.py`
- [ ] T038 [US1] FR-008 — faltam valores exatos do YAML, defaults parciais e rejeição de chave desconhecida; teste sugerido em `tests/test_scoring.py`
- [ ] T039 [US1] FR-009 — faltam detalhamento, hard rule e determinismo entre processos; teste sugerido em `tests/test_scoring.py`

## Phase 6: Implementação planejada (TickTick T11)

**Goal**: valor ausente como ausência de sinal, hard rules também no
retorno antecipado, configuração validada, registro de todas as regras
disparadas e constantes dos sub-scores no YAML.

- [ ] T040 [US1] FR-010 — Tratar `None`, NaN e `pd.NA` como ausentes e contar os ausentes ignorados por grupo no detalhamento, em `src/scoring.py::_score_stats`, `_score_strings`, `_score_binwalk`, `score_firmware` e `SignalResult`
- [ ] T041 [US1] FR-010 — Cenário US1.8: testes de `None`, NaN e `pd.NA` em cada grupo, em cada flag e em contagens em `tests/test_scoring.py`
- [ ] T042 [US3] FR-011 — Avaliar as hard rules antes do retorno antecipado, com score 0 e o mais grave entre os mínimos das regras disparadas, em `src/scoring.py::score_firmware`; atualizar o texto de FR-003, FR-005 e do Edge Case correspondente em `specs/006-baseline-regras/spec.md`
- [ ] T043 [US3] FR-011 — Cenário US3.7: testes de só `has_telnetd`, de soma de pesos 0 com grupo presente e de mínimos diferentes em `tests/test_scoring.py`
- [ ] T044 [US4] FR-012 — Validar níveis mínimos, `0 ≤ low < high ≤ 1`, pesos `≥ 0` com soma `> 0`, YAML vazio, seção `scoring` ausente e chave desconhecida, com arquivo e chave na mensagem, em `src/scoring.py::load_scoring_config`
- [ ] T045 [US4] FR-012 — Cenário US4.6: uma rejeição por categoria de FR-012 em `tests/test_scoring.py`
- [ ] T046 [US3] FR-013 — Acrescentar `hard_rules_triggered` a `ScoringResult` e preenchê-lo na ordem de avaliação em `src/scoring.py::score_firmware`
- [ ] T047 [US3] FR-013 — Cenário US3.8: teste com duas regras disparadas, uma sem elevar o nível, em `tests/test_scoring.py`
- [ ] T048 [US4] FR-014 — Levar as constantes dos sub-scores de FR-002 a uma subseção de `configs/scoring.yaml`, carregá-las e validá-las em `src/scoring.py::load_scoring_config` e usá-las em `_score_stats`, `_score_strings` e `_score_binwalk`
- [ ] T049 [US4] FR-014 — Testes de padrões iguais aos valores atuais e de constante alterada no YAML mudando o sub-score em `tests/test_scoring.py`

## Dependencies & Execution Order

- Lacunas são independentes entre si; cada uma só depende do módulo citado.
- Phase 6: cada teste pode ser escrito antes da sua implementação. As
  implementações editam o mesmo `src/scoring.py` e os testes o mesmo
  `tests/test_scoring.py`: nenhuma task desta fase roda em paralelo.
  Ordem sugerida: T044 → T048 (configuração), depois T040 → T042 → T046
  (`score_firmware`).
