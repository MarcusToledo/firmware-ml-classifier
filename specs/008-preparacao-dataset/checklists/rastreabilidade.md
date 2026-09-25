# Rastreabilidade e testabilidade Checklist: Preparação do dataset de treino

**Purpose**: Avaliar a qualidade dos requisitos, cenários, rastreabilidade e requisitos não funcionais para revisão pela banca ou em PR
**Created**: 2026-09-25
**Feature**: [spec.md](../spec.md)

**Review Ownership**: Este checklist pertence ao revisor de qualidade dos requisitos. `[x]` indica que o critério foi revisado e satisfeito; não indica conclusão da implementação.

## Clareza e critérios de aceitação

- [x] CHK001 A lista de colunas proibidas no vetor é fechada e cobre identidade, `meta_*`, campos de CVE, colunas da rotulagem e `doc2vec_*`? [Clarity, Spec §FR-003, Spec §FR-004]
- [x] CHK002 Os estados de extração que excluem, que interrompem e que mantêm a linha, inclusive `firmware_id` nulo e `nao_executado`, estão enumerados sem sobreposição? [Clarity, Spec §FR-002, Spec §FR-007] — corrigido no analyze de 2026-09-25
- [x] CHK003 A lista fixa do one-hot e o destino de valor fora da lista e de nulo estão definidos? [Clarity, Spec §FR-010]
- [x] CHK004 A regra de contagem por motivo e por fabricante com múltiplos motivos ou fabricantes está definida e separada da invariante de cobertura? [Measurability, Spec §FR-008, Spec §SC-002]
- [x] CHK005 Os campos dos metadados e o único campo que muda entre execuções iguais estão definidos? [Measurability, Spec §FR-013, Spec §SC-003]

## Cobertura de cenários e casos de borda

- [x] CHK006 Há cenário para par ausente, alias divergente e falha transitória, todos sem gravar nada? [Exception Flow, Spec §US1.3, Spec §US1.4, Spec §US2.4]
- [x] CHK007 Há cenário para cada motivo de exclusão e para a invariante de cobertura? [Coverage, Spec §US2.1–US2.3]
- [x] CHK008 Tabela vazia e classe sem exemplo têm resultado definido? [Edge Case, Spec §FR-008]
- [x] CHK009 A entrada gerada antes de `001/FR-014`, `001/FR-016` ou `004/FR-017` tem resultado definido? [Edge Case, Spec §FR-001]
- [x] CHK010 A colisão de modelo na unificação TP-Link, inclusive com `_` e `-`, tem resultado definido? [Edge Case, Spec §FR-016, Spec §US5.2]

## Consistência e rastreabilidade

- [x] CHK011 Cada FR cita a TickTick de origem (T08 ou T07), tem linha na matriz do `plan.md` e ao menos uma task; cada SC cita a TickTick e tem task? [Traceability, Spec §FR-001–FR-017, Spec §SC-001–SC-006]
- [x] CHK012 As dependências de outras specs (`001/FR-014`, `001/FR-016`, `001/FR-018`, `004/FR-017`, `005/FR-018`, `005/FR-022`, `005/FR-026`, `003`) estão citadas no formato `NNN/FR-###`? [Consistency, Spec §Assumptions]
- [x] CHK013 O que fica com `009`, `010` e `011` (partição, filtro de variância, balanceamento, métricas) está explícito para não ser implementado aqui? [Consistency, Spec §Assumptions, Spec §FR-009]
- [x] CHK014 Os nomes dos artefatos são iguais em spec, plan, data-model e contrato? [Consistency, Spec §FR-013, Spec §FR-014]

## Requisitos não funcionais e conflitos

- [x] CHK015 Nenhum requisito calcula remoção ou codificação de coluna sobre os dados antes da partição (princípio III)? [Conflict, Spec §FR-009, Spec §FR-010]
- [x] CHK016 O teste de guarda de vazamento sobre a tabela de treino é requisito explícito (constituição III)? [Coverage, Spec §FR-003, Spec §SC-001]
- [x] CHK017 A etapa com rede (busca dos pares TP-Link novos) está isolada na `003` e citada como pré-requisito dos rótulos? [Dependency, Spec §FR-016, Spec §Edge Cases]

## Notes

- Tema: rastreabilidade e testabilidade; profundidade Standard; público: banca e revisor de PR.
- `/speckit.implement` lê o estado deste checklist como gate e não altera os marcadores.
- `checklists/requirements.md` mantém seu ciclo de vida separado.
