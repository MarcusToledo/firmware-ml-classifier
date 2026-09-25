# Rastreabilidade e testabilidade Checklist: Treino de modelos e baselines

**Purpose**: Avaliar a qualidade dos requisitos, cenários, rastreabilidade e requisitos não funcionais para revisão pela banca ou em PR
**Created**: 2026-09-25
**Feature**: [spec.md](../spec.md)

**Review Ownership**: Este checklist pertence ao revisor de qualidade dos requisitos. `[x]` indica que o critério foi revisado e satisfeito; não indica conclusão da implementação.

## Clareza e critérios de aceitação

- [x] CHK001 Hiperparâmetros, peso por classe e seed estão fixados com valores e fonte na configuração versionada? [Clarity, Spec §FR-003, Spec §FR-011]
- [x] CHK002 A regra do alvo binário está definida e aplicada também ao `score_firmware`? [Clarity, Spec §FR-012, Spec §FR-010]
- [x] CHK003 O que é persistido em `models/` e em que execuções está definido sem ambiguidade? [Clarity, Spec §FR-007]
- [x] CHK004 O formato das predições cobre classe ausente no treino do fold? [Edge Case, Spec §FR-006]

## Cobertura de cenários e casos de borda

- [x] CHK005 Há cenário para filtro de variância ajustado só no treino? [Coverage, Spec §US1.2]
- [x] CHK006 Há cenário para cada baseline (majoritário, identidade, regras)? [Coverage, Spec §US3.1–US3.3]
- [x] CHK007 Empate no majoritário e entrada em texto do `score_firmware` têm resultado definido? [Edge Case, Spec §FR-008, Spec §FR-010]

## Consistência e rastreabilidade

- [x] CHK008 Cada FR Planejado cita T09 ou T05, tem linha na matriz e ao menos uma task; FR-014 é Proposto sem task? [Traceability, Spec §FR-001–FR-014]
- [x] CHK009 A decisão "sem tuning" é a mesma da `009` e o filtro de variância cumpre `008/FR-009`? [Consistency, Spec §Assumptions, Spec §FR-002]
- [x] CHK010 A fronteira com a `011` (métricas, ablations, importância) está explícita e a interface `train_run` está no contrato? [Consistency, Spec §FR-005]

## Requisitos não funcionais e conflitos

- [x] CHK011 Nenhum ajuste usa `firmware_id` do teste do fold, com critério mensurável (constituição III)? [Coverage, Spec §SC-001]
- [x] CHK012 O baseline de identidade e as execuções no esquema `random` são impedidos de aparecer como resultado reportado, com o uso da divisão aleatória no Complexity Tracking (constituição III)? [Conflict, Spec §FR-006, Spec §FR-009, Spec §SC-004]
- [x] CHK014 O determinismo da predição não depende de paralelismo (`n_jobs`)? [Measurability, Spec §FR-003, Spec §SC-002] — decidido no analyze de 2026-09-25
- [x] CHK013 Só Extra Trees e Random Forest entram como modelos (constituição IV)? [Conflict, Spec §Assumptions]

## Notes

- Tema: rastreabilidade e testabilidade; profundidade Standard; público: banca e revisor de PR.
- `/speckit.implement` lê o estado deste checklist como gate e não altera os marcadores.
