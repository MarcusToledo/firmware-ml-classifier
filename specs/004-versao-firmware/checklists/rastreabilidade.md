# Rastreabilidade e testabilidade Checklist: Versão do firmware a partir do path

**Purpose**: Avaliar a qualidade dos requisitos, cenários, rastreabilidade e requisitos não funcionais para revisão pela banca ou em PR
**Created**: 2026-09-24
**Feature**: [spec.md](../spec.md)

**Review Ownership**: Este checklist pertence ao revisor de qualidade dos requisitos. `[x]` indica que o critério foi revisado e satisfeito; não indica conclusão da implementação.

## Clareza e critérios de aceitação

- [x] CHK001 Os limites do layout usado para inferir fabricante e modelo estão definidos sem depender de conhecimento externo? [Clarity, Spec §FR-001]
- [x] CHK002 Os resultados nulos para paths fora do layout estão descritos para todos os campos da identidade? [Completeness, Spec §FR-002]
- [x] CHK003 A distinção entre revisão de hardware e versão de firmware tem critérios objetivos e exemplo de fronteira? [Clarity, Spec §FR-004]
- [x] CHK004 A precedência entre versão do diretório e versão do arquivo define tanto o valor quanto a origem esperados? [Acceptance Criteria, Spec §FR-005]
- [x] CHK005 Os formatos aceitos e rejeitados por fabricante delimitam número de grupos, separadores, builds e sufixos? [Measurability, Spec §FR-007, Spec §FR-008, Spec §FR-009, Spec §FR-010, Spec §FR-011]

## Cobertura de cenários e casos de borda

- [x] CHK006 Os cenários cobrem identidade com versão no diretório, modelo comum, revisão de hardware e ausência do segmento `raw`? [Coverage, Spec §FR-001, Spec §FR-002, Spec §FR-004]
- [x] CHK007 Os cenários cobrem versão vinda do diretório, do nome do arquivo e a precedência quando ambas existem? [Coverage, Spec §FR-005]
- [x] CHK008 Os cenários de ambiguidade deixam claro quando versão e origem devem permanecer nulas? [Edge Case, Spec §FR-010, Spec §FR-012]
- [x] CHK009 O cenário de metadados inconsistentes define uma falha observável e exige que o erro cite o path? [Exception Flow, Spec §FR-013]
- [x] CHK010 Os cenários distinguem a gravação com e sem `--label-from-path` e preservam a identidade em falha de leitura? [Coverage, Spec §FR-014]

## Consistência e rastreabilidade

- [x] CHK011 Cada FR Implementado tem módulo, teste ou lacuna explícita e uma task retroativa correspondente? [Traceability, Spec §FR-001–FR-014]
- [x] CHK012 Cada cenário Given/When/Then tem identificador estável e evidência de execução registrada no `tasks.md`? [Traceability, Spec §User Scenarios & Testing]
- [x] CHK013 A terminologia `version_source`, `directory`, `filename` e “sem versão” é consistente entre spec, plan e tasks? [Consistency, Spec §Clarifications]

## Requisitos não funcionais e conflitos

- [x] CHK014 A especificação define um resultado seguro e observável para arquivo direto em `raw/<fabricante>/`, em vez de apenas registrar o fallback silencioso como limitação? [Conflict, Gap, Spec §FR-001, Spec §Edge Cases] — definido em FR-015 (Planejado, T11); o código atual segue em Edge Cases
- [x] CHK015 A especificação exige sinalização quando um segmento `raw` acima do dataset desvia a identidade inferida? [Conflict, Gap, Spec §FR-001, Spec §Edge Cases] — resolvido por FR-016 (Planejado, T11): a identidade passa a ser relativa à raiz do dataset
- [ ] CHK016 A auditabilidade define como registrar divergência entre a versão do diretório e a versão inferível do arquivo? [Gap, Spec §FR-005, Spec §Edge Cases] — pendente: FR-018 é Proposto (sem compromisso de implementação)

## Requisitos planejados (escopo restante, 2026-09-24)

- [x] CHK017 Cada FR Planejado cita a TickTick de origem, tem linha prevista na matriz do `plan.md` e ao menos uma task na fase "Implementação planejada"; o FR Proposto está marcado sem task? [Traceability] [Spec §FR-015–FR-018]
- [x] CHK018 O efeito de FR-016 e FR-017 sobre outras specs (`meta_path` relativo em `001/FR-009` e no data-model da 001, `path` do JSONL da 002, reinferência em `005/FR-004` com recusa de `meta_path` absoluto; `meta_third_party` no data-model da 001) está explícito e tem task? [Consistency] [Spec §FR-016] [Spec §FR-017]
- [x] CHK020 A detecção de terceiros tem critério objetivo sem falso positivo medido (nome `webflash` ou banner `DD-WRT`; `OpenWrt` sozinho não marca) e não quebra a reinferência da 005? [Clarity] [Spec §FR-017] [Spec §SC-005]
- [x] CHK019 Cada FR Planejado tem cenário observável em User Story 5 citado por uma task de teste? [Coverage] [Spec §US5.1–US5.4]

## Notes

- Tema: rastreabilidade e testabilidade; profundidade Standard; público: banca e revisor de PR.
- O foco inclui qualidade dos critérios de aceitação, cenários, casos de borda, consistência entre spec, plan e tasks, rastreabilidade e os princípios V e VI.
- `/speckit.implement` lê o estado deste checklist como gate e não altera os marcadores.
- `checklists/requirements.md` mantém seu ciclo de vida separado.
