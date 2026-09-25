# Rastreabilidade e testabilidade Checklist: Partição agrupada

**Purpose**: Avaliar a qualidade dos requisitos, cenários, rastreabilidade e requisitos não funcionais para revisão pela banca ou em PR
**Created**: 2026-09-25
**Feature**: [spec.md](../spec.md)

**Review Ownership**: Este checklist pertence ao revisor de qualidade dos requisitos. `[x]` indica que o critério foi revisado e satisfeito; não indica conclusão da implementação.

## Clareza e critérios de aceitação

- [x] CHK001 A regra de grupo é objetiva, determinística e independente da ordem das linhas? [Clarity, Spec §FR-002]
- [x] CHK002 Folds, repetições, seeds e alvo da estratificação estão fixados em configuração versionada? [Clarity, Spec §FR-004]
- [x] CHK003 O comportamento com fold de teste sem alguma classe está definido e registrado? [Edge Case, Spec §FR-005]
- [x] CHK004 A diferença entre divisão principal e diagnóstica está marcada no nome e nos metadados? [Clarity, Spec §FR-007, Spec §SC-004]

## Cobertura de cenários e casos de borda

- [x] CHK005 Há cenário de binário em dois modelos e de modelo com dois binários no mesmo grupo? [Coverage, Spec §US1.1]
- [x] CHK006 Há cenário para tabela diferente da registrada, na geração e na leitura? [Exception Flow, Spec §FR-001, Spec §US2.3]
- [x] CHK007 Grupo grande, classe rara e componente com classes diferentes estão nos casos de borda com medição? [Edge Case, Spec §Edge Cases]

## Consistência e rastreabilidade

- [x] CHK008 Cada FR Planejado cita a TickTick T03, tem linha na matriz do `plan.md` e ao menos uma task; FR-009 e FR-010 estão marcados Proposto sem task? [Traceability, Spec §FR-001–FR-010]
- [x] CHK009 As entradas citam `008/FR-013` e `008/FR-014`, e o que fica com `010` e `011` está explícito? [Consistency, Spec §Assumptions]
- [x] CHK010 A decisão "sem tuning" está coerente entre esta spec (FR-009 Proposto) e o que a `010` vai especificar? [Consistency, Spec §FR-009]

## Requisitos não funcionais e conflitos

- [x] CHK011 A garantia de que nenhum `firmware_id` nem modelo cruza treino e teste tem teste de guarda (constituição III)? [Coverage, Spec §FR-003, Spec §SC-001]
- [x] CHK012 A reprodutibilidade em processos separados é mensurável (constituição V)? [Measurability, Spec §SC-002]
- [x] CHK013 A violação da constituição III pela divisão aleatória está registrada no Complexity Tracking com justificativa e mitigação? [Conflict, Spec §FR-007] — decidido no analyze de 2026-09-25
- [x] CHK014 A chave de modelo junta grafias diferentes do mesmo modelo, com medição? [Clarity, Spec §FR-002, Spec §US1.4] — decidido no analyze de 2026-09-25

## Notes

- Tema: rastreabilidade e testabilidade; profundidade Standard; público: banca e revisor de PR.
- `/speckit.implement` lê o estado deste checklist como gate e não altera os marcadores.
