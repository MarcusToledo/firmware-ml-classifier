# Rastreabilidade e testabilidade Checklist: Features do filesystem desempacotado

**Purpose**: Avaliar a qualidade dos requisitos, cenários, rastreabilidade e requisitos não funcionais para revisão pela banca ou em PR
**Created**: 2026-09-25
**Feature**: [spec.md](../spec.md)

**Review Ownership**: Este checklist pertence ao revisor de qualidade dos requisitos. `[x]` indica que o critério foi revisado e satisfeito; não indica conclusão da implementação.

## Clareza e critérios de aceitação

- [x] CHK001 Cada proteção ELF tem critério objetivo de leitura (segmento, flag ou símbolo)? [Clarity, Spec §FR-004]
- [x] CHK002 Os denominadores das proporções estão definidos, inclusive PIE só entre executáveis? [Clarity, Spec §FR-004, Spec §FR-009]
- [x] CHK003 A representação de feature indisponível está definida e é diferente de zero? [Clarity, Spec §FR-008]
- [x] CHK004 O prefixo das colunas não colide com colunas existentes? [Consistency, Spec §FR-002]

## Cobertura de cenários e casos de borda

- [x] CHK005 Há cenário para symlink, ELF malformado e firmware sem filesystem? [Edge Case, Spec §US1.2, Spec §US4.1, Spec §US4.2]
- [x] CHK006 Há cenário para função definida (não importada) e para RELRO completo × parcial? [Coverage, Spec §US3.2, Spec §US2.2]

## Consistência e rastreabilidade

- [x] CHK007 Cada FR cita a TickTick T12, tem linha na matriz e ao menos uma task? [Traceability, Spec §FR-001–FR-012]
- [x] CHK012 A fonte da lista de funções perigosas e os critérios das proteções são verificáveis (constituição VII)? [Clarity, Spec §FR-004, Spec §FR-005] — corrigido no analyze de 2026-09-25
- [x] CHK013 Falhas fora do ELF malformado ficam visíveis sem perder a linha? [Exception Flow, Spec §FR-012] — decidido no analyze de 2026-09-25
- [x] CHK008 A dependência do unpack de `001/FR-016` e o consumo por `008/FR-003` e `011/FR-005` estão explícitos? [Consistency, Spec §Assumptions]

## Requisitos não funcionais e conflitos

- [x] CHK009 Nada é executado e a leitura é limitada por `max_bytes` (constituição I e VI)? [Conflict, Spec §FR-003]
- [x] CHK010 Nenhuma feature carrega identidade ou CVE, e a arquitetura fica fora do vetor (constituição III)? [Conflict, Spec §FR-007, Spec §FR-011]
- [x] CHK011 A nova dependência e a mudança de versão mínima do scikit-learn estão registradas com justificativa (constituição, Restrições Técnicas)? [Dependency, Spec §FR-003, Spec §FR-008]

## Notes

- Tema: rastreabilidade e testabilidade; profundidade Standard; público: banca e revisor de PR.
- `/speckit.implement` lê o estado deste checklist como gate e não altera os marcadores.
