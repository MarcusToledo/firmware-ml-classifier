# Checklist de Rastreabilidade e Testabilidade: Busca de CVEs na NVD

**Objetivo**: avaliar a qualidade dos requisitos, cenários, critérios de aceitação e vínculos entre spec, plano e tasks
**Criado em**: 2026-09-24
**Feature**: [spec.md](../spec.md)

**Nota**: este checklist customizado foi gerado com base no contexto da feature pelo procedimento de `/speckit.checklist`.
**Responsabilidade da revisão**: este artefato pertence ao revisor; `[x]` indica que o critério de qualidade do requisito foi revisado e satisfeito.
**Semântica do marcador**: `[x]` não indica que a implementação foi concluída; indica apenas aprovação da qualidade dos requisitos.

## Critérios de aceitação e mensurabilidade

- [x] CHK001 Os resultados esperados para deduplicação, normalização, ordenação e descarte de valores ausentes estão definidos de forma objetiva? [Spec §FR-001]
- [x] CHK002 As regras de alias, substituição de underscore, caixa e inserção de hífen eliminam interpretações alternativas para a forma NVD? [Spec §FR-002]
- [x] CHK003 A preferência entre CVSS v3.1, v3.0, v2 e ausência de métrica está ordenada e tem resultados mensuráveis? [Spec §FR-005]
- [x] CHK004 O contrato de cada entrada nova ou substituída distingue com clareza o esquema v2 das entradas antigas preservadas? [Spec §FR-006] — corrigido: o escopo de `schema_version: 2` foi limitado às entradas novas ou substituídas.

## Cobertura de cenários e casos de borda

- [x] CHK005 Os cenários cobrem fluxo principal, retomada, atualização forçada e modo sem efeitos externos? [Spec §FR-007, Spec §FR-011]
- [x] CHK006 A resolução de CPE especifica os critérios de coincidência, a parte aceita, o primeiro resultado e a generalização dos campos? [Spec §FR-003]
- [x] CHK007 Os caminhos alternativos por CPE e por palavra-chave definem origem, parâmetros de consulta e conteúdo auditável? [Spec §FR-004]
- [x] CHK008 Os requisitos descrevem paginação, primeira página do dicionário de CPE e ausência de nova tentativa como limites explícitos, sem deixar esses comportamentos implícitos? [Spec §FR-003, Spec §FR-004, Gap]
- [x] CHK009 As falhas HTTP, de conexão, timeout e exceções não capturadas têm efeitos sobre progresso, cache e continuidade claramente diferenciados? [Spec §FR-008, Spec §FR-009]

## Consistência e rastreabilidade

- [x] CHK010 Cada FR Implementado tem um vínculo único entre US, módulo e teste ou uma lacuna explícita no plano e nas tasks? [Spec §FR-001–FR-012]
- [x] CHK011 Cada cenário de aceitação possui identificador `US<k>.<n>` e evidência de execução registrada nas tasks? [Spec §User Scenarios, Assumption]
- [x] CHK012 As partes sem teste permanente estão descritas de modo consistente entre `plan.md`, `tasks.md` e a futura pendência por FR no `TODO.md`? [Gap]
- [x] CHK013 A separação de responsabilidade entre busca de CVE e rotulagem aponta de forma inequívoca para 005/FR-003 e 005/FR-005–FR-012? [Spec §Assumptions, Spec §FR-006]

## Requisitos não funcionais

- [x] CHK014 Os requisitos quantificam timeout, intervalo de persistência, atraso padrão, paginação e uso da chave de API para permitir reprodução objetiva? [Spec §FR-004, Spec §FR-009, Spec §FR-010]
- [ ] CHK015 A falha de uma nova consulta com `--force` impede que evidência anterior pareça atual, conforme o princípio II? [Conflict, Spec §FR-008] — pendente: FR-013 (Planejado, T11) remove a entrada e sai com código ≠ 0; satisfeito só depois da implementação
- [ ] CHK016 O cache registra informação suficiente para datar o retrato mutável da NVD, conforme o princípio V? [Gap, Spec §SC-001–SC-003] — pendente: FR-014 (Planejado, T11) exige `fetched_at`; satisfeito só depois da implementação e da busca completa

## Requisitos planejados (escopo restante, 2026-09-24)

- [x] CHK017 Cada FR Planejado cita a TickTick de origem, tem linha prevista na matriz do `plan.md` e ao menos uma task na fase "Implementação planejada"; os FRs Proposto estão marcados sem task? [Traceability] [Spec §FR-013–FR-021]
- [x] CHK018 Cada FR Planejado diz qual FR Implementado ele substitui, complementa ou amplia (FR-001, FR-003, FR-005, FR-006, FR-007, FR-008)? [Consistency] [Spec §FR-013–FR-018]
- [x] CHK019 Cada FR Planejado tem cenário observável em User Story 5 citado por uma task de teste? [Coverage] [Spec §US5.1–US5.7]
- [x] CHK020 O efeito das mudanças nos rótulos (nova busca completa, `schema_version: 3` exigido pela 005, `cvss_max` pelo maior score, CPE `h`) está explícito e ligado à regeneração da 005? [Dependencies] [Spec §FR-014] [Spec §FR-016] [Spec §FR-018] [005/FR-026]
- [x] CHK021 A ambiguidade de CPE tem critério objetivo (tupla parte, fabricante, produto) que não transforma versões do mesmo produto em ambiguidade? [Clarity] [Spec §FR-018] [Spec §US5.6]

## Notes

- Marcar itens `[x]` somente após a revisão confirmar a qualidade do requisito.
- Manter `[ ]` quando a qualidade depende de correção no código registrada no `TODO.md`.
- `/speckit.implement` lê o estado do checklist como gate e não altera marcadores.
- `checklists/requirements.md` mantém seu ciclo separado de `/speckit.specify` e `/speckit.clarify`.
