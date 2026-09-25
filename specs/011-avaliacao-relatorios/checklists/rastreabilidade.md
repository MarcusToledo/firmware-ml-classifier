# Rastreabilidade e testabilidade Checklist: Avaliação e relatórios

**Purpose**: Avaliar a qualidade dos requisitos, cenários, rastreabilidade e requisitos não funcionais para revisão pela banca ou em PR
**Created**: 2026-09-25
**Feature**: [spec.md](../spec.md)

**Review Ownership**: Este checklist pertence ao revisor de qualidade dos requisitos. `[x]` indica que o critério foi revisado e satisfeito; não indica conclusão da implementação.

## Clareza e critérios de aceitação

- [x] CHK001 A regra de agregação das métricas está definida, inclusive com fold de teste sem alguma classe? [Clarity, Spec §FR-002]
- [x] CHK002 O método de incerteza e de comparação pareada tem unidade de reamostragem, número, seed e critério de leitura? [Clarity, Spec §FR-003]
- [x] CHK003 Grupos e braços de ablation estão enumerados por coluna, com o destino de grupo sem colunas? [Clarity, Spec §FR-005, Spec §FR-007]
- [x] CHK004 O método de importância é calculado fora do treino e o uso do MDI está restrito? [Clarity, Spec §FR-010]

## Cobertura de cenários e casos de borda

- [x] CHK005 Há cenário para métricas com classe ausente num fold? [Edge Case, Spec §US1.2]
- [x] CHK006 Há cenário para comparação com o baseline de identidade marcado como diagnóstico? [Coverage, Spec §US2.2]
- [x] CHK007 Há cenário para ausência de braço Doc2Vec e para feature sem sinal na importância? [Coverage, Spec §US3.2, Spec §US5.2]
- [x] CHK008 Mistura de execuções de tabelas ou folds diferentes tem resultado definido? [Exception Flow, Spec §FR-001, Spec §US6.2]

## Consistência e rastreabilidade

- [x] CHK009 Cada FR Planejado cita T10, T05 ou T03, tem linha na matriz e ao menos uma task; FR-013 e FR-014 são Proposto sem task? [Traceability, Spec §FR-001–FR-014]
- [x] CHK010 A exclusão do braço Doc2Vec cumpre a decisão do analyze da `007`? [Consistency, Spec §FR-006]
- [x] CHK011 O tratamento de `purpose: diagnostico` é o mesmo da `010` (identidade e `random`)? [Consistency, Spec §FR-004, Spec §FR-008, Spec §SC-005]

## Requisitos não funcionais e conflitos

- [x] CHK012 Os resultados vão para `reports/<timestamp>/` com metadados que permitem refazer cada número (constituição V)? [Coverage, Spec §FR-011, Spec §SC-002]
- [x] CHK013 Toda diferença entre modelos vem com incerteza e sem p-valor (constituição VII)? [Measurability, Spec §FR-003, Spec §SC-004]
- [x] CHK014 O relatório mostra se o modelo supera o baseline de identidade (constituição III)? [Coverage, Spec §FR-004]

## Notes

- Tema: rastreabilidade e testabilidade; profundidade Standard; público: banca e revisor de PR.
- `/speckit.implement` lê o estado deste checklist como gate e não altera os marcadores.
