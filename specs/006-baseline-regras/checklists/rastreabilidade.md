# Checklist de rastreabilidade e testabilidade: Baseline determinístico de regras

**Finalidade**: avaliar a qualidade dos requisitos, cenários, critérios de aceitação e rastreabilidade da spec retroativa.
**Criado em**: 2026-09-24
**Feature**: [spec.md](../spec.md)

**Responsabilidade da revisão**: este checklist pertence à banca ou ao revisor de PR. `[x]` indica que o critério de qualidade dos requisitos foi revisado e satisfeito; não indica conclusão da implementação.

## Completude e clareza dos requisitos

- [x] CHK001 Os campos do resultado, os três níveis e o tratamento de chaves desconhecidas estão definidos sem depender de inferência? [Completude] [Spec §FR-001]
- [x] CHK002 As fórmulas de cada grupo identificam entradas, faixas, constantes, saturação e composição do sub-score? [Clareza] [Spec §FR-002]
- [x] CHK003 Os critérios de presença, redistribuição de pesos e retorno antecipado têm precedência explícita sobre as hard rules? [Consistência] [Conflict] [Spec §FR-003] [Spec §FR-005] — corrigido: FR-005 agora explicita a precedência de FR-003.
- [x] CHK004 A inclusão dos valores exatos de `low` e `high` nas classes adjacentes está definida sem ambiguidade? [Clareza] [Spec §FR-004]
- [x] CHK005 A ordem das hard rules, a proibição de rebaixamento e o significado de “última regra” formam um contrato verificável? [Clareza] [Spec §FR-005]
- [x] CHK006 Os defaults de configuração e a consequência de uma chave desconhecida estão especificados para cada subseção? [Completude] [Spec §FR-008]

## Qualidade dos critérios de aceitação

- [x] CHK007 Os critérios mensuráveis cobrem o resultado completo, inclusive detalhamento, hard rule e campos de identidade? [Critérios de aceitação] [Spec §SC-001] [Spec §SC-002] — corrigido: SC-001 e SC-002 passaram a cobrir todo o resultado e identidade.
- [x] CHK008 A ausência de dependência de CVE e identidade está formulada tanto como requisito negativo quanto como resultado mensurável? [Consistência] [Spec §FR-006] [Spec §SC-002]
- [x] CHK009 A separação entre previsão do baseline e rótulo de treino tem um critério objetivo de zero chamadas? [Critérios de aceitação] [Spec §FR-007] [Spec §SC-004]
- [x] CHK010 O determinismo exige igualdade do resultado completo em processos separados e sem dependência da ordem? [Não funcional] [Spec §FR-009] [Spec §SC-001] — corrigido: FR-009 e o cenário US1.7 agora cobrem processos separados.

## Cobertura de cenários e casos de borda

- [x] CHK011 Os cenários cobrem entradas vazias, risco baixo, risco alto, limiares customizados e fronteiras inclusivas? [Cobertura de cenários] [Spec §FR-001] [Spec §FR-004] — corrigido: o cenário US1.6 cobre as duas fronteiras.
- [x] CHK012 Há cenários separados para campos de CVE, campos de identidade e ausência de uso na geração de rótulos? [Cobertura de cenários] [Spec §FR-006] [Spec §FR-007] — corrigido: os cenários US2.3 e US2.4 cobrem as duas lacunas.
- [x] CHK013 As três hard rules, o nível mínimo configurável, o não rebaixamento e a última regra aplicada têm cenários de aceitação? [Cobertura de cenários] [Spec §FR-005] — corrigido: os cenários US3.4 a US3.6 cobrem os casos ausentes.
- [x] CHK014 Os fluxos alternativos de configuração parcial e de chave desconhecida têm resultados esperados explícitos? [Fluxo de exceção] [Spec §FR-008] — corrigido: os cenários US4.4 e US4.5 cobrem fallback e exceção.
- [x] CHK015 O retorno sem hard rule quando não há grupo ou a soma dos pesos é 0 está documentado como limitação observável e sem conflito interno? [Caso de borda] [Spec §FR-003] [Spec §FR-005] — corrigido: FR-005 referencia a precedência de FR-003.

## Consistência, rastreabilidade e requisitos não funcionais

- [x] CHK016 Cada FR implementado aparece uma vez na matriz e numa task da primeira user story associada, com lacuna explícita quando a cobertura é parcial? [Rastreabilidade] [Spec §FR-001–FR-009]
- [x] CHK017 Cada cenário Given/When/Then Implementado possui identificador `USk.n`, evidência executada e task correspondente? Os cenários Planejado (US1.8, US3.7, US3.8, US4.6) são citados pelas tasks de teste da Phase 6. [Rastreabilidade] [Spec §User Scenarios & Testing]
- [x] CHK018 Os domínios numéricos aceitos e o tratamento exigido para NaN estão definidos como contrato seguro e verificável? [Completude] [Gap] [Spec §FR-001] [Spec §FR-002] [Spec §FR-003] — definido em FR-010 (Planejado, T11) e SC-005; o código atual segue em Edge Cases
- [x] CHK019 A validade de pesos, limiares, níveis mínimos e YAML vazio tem regras de rejeição claras e mensuráveis? [Completude] [Gap] [Spec §FR-008] — definida em FR-012 (Planejado, T11) e SC-006
- [x] CHK020 A aplicabilidade dos princípios V e VI está delimitada: configuração versionada e determinismo são exigidos, enquanto leitura limitada do binário pertence à extração? [Assumption] [Spec §FR-008] [Spec §FR-009]

## Requisitos planejados (escopo restante, 2026-09-24)

- [x] CHK021 Cada FR Planejado cita a TickTick de origem, tem linha prevista na matriz do `plan.md` e ao menos uma task na fase "Implementação planejada"? [Rastreabilidade] [Spec §FR-010–FR-014]
- [x] CHK022 A precedência nova de FR-011 sobre o retorno antecipado de FR-003/FR-005 está explícita, com score e nível definidos para o caso sem grupo? [Consistência] [Spec §FR-003] [Spec §FR-005] [Spec §FR-011]
- [x] CHK023 `hard_rules_triggered` e `hard_rule_applied` têm significados distintos e não contraditórios? [Clareza] [Spec §FR-005] [Spec §FR-013]
- [x] CHK024 Cada FR Planejado tem cenário Given/When/Then marcado como Planejado? [Cobertura de cenários] [Spec §US1.8] [Spec §US3.7] [Spec §US3.8] [Spec §US4.6]

## Notas

- Profundidade: Standard.
- Público: banca e revisor de PR.
- Foco: qualidade dos critérios de aceitação, cobertura de cenários e bordas, consistência entre spec/plan/tasks, rastreabilidade e princípios V e VI.
- `/speckit.implement` lê o estado deste checklist e não altera os marcadores.
- `checklists/requirements.md` mantém seu ciclo separado.
