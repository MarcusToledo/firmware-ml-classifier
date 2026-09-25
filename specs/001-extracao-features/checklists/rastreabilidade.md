# Rastreabilidade e testabilidade Checklist: Extração estática de features

**Purpose**: avaliar a qualidade dos requisitos, cenários, critérios e vínculos de rastreabilidade para revisão da banca ou de PR.
**Created**: 2026-09-24
**Feature**: [spec.md](../spec.md)

**Note**: checklist customizado gerado segundo `/speckit.checklist` com profundidade Standard.
**Review Ownership**: este checklist pertence ao revisor de qualidade dos requisitos. Um item recebe `[x]` somente quando o revisor conclui que o critério de qualidade está satisfeito.
**Marker Semantics**: `[x]` significa que a qualidade do requisito foi revisada e aprovada; não significa que o trabalho de implementação esteja concluído.

## Completude e clareza dos requisitos

- [x] CHK001 As três formas de entrada e todas as classes de arquivo excluídas estão enumeradas sem depender de interpretação externa? [Completude] [Spec §FR-001]
- [x] CHK002 Os padrões de configuração e a semântica dos overrides por dot-path estão definidos com valores objetivos? [Clareza] [Spec §FR-002]
- [x] CHK003 Os resultados de arquivo vazio, falha de leitura e limite não positivo distinguem erro, `read_ok` e identidade de conteúdo? [Clareza] [Spec §FR-003]
- [x] CHK004 A definição de `firmware_id` explicita quais bytes entram no SHA256 e quando o valor é nulo? [Clareza] [Spec §FR-004]
- [x] CHK005 O esquema da saída enumera todos os 14 metadados e separa metadados de features? [Completude] [Spec §FR-009]

## Qualidade dos critérios de aceitação

- [x] CHK006 Os resultados dos cenários de lote, CSV, override, ordem e logging são observáveis e objetivos? [Acceptance Criteria Quality] [Spec §FR-001] [Spec §FR-002] [Spec §FR-012] [Spec §FR-013]
- [x] CHK007 Os limites e resultados das features estatísticas são definidos de forma mensurável, inclusive para menos de dois blocos? [Acceptance Criteria Quality] [Spec §FR-005]
- [x] CHK008 A semântica de truncamento separa os limites de strings e documento do corte por `max_bytes`? [Consistency] [Spec §FR-006]
- [x] CHK009 Os resultados esperados com e sem Binwalk são especificados sem omitir a presença das chaves? [Acceptance Criteria Quality] [Spec §FR-007]

## Cobertura de cenários e casos extremos

- [x] CHK010 Há cenários primários para cada uma das quatro user stories e cada cenário tem resultado verificável? [Scenario Coverage] [Spec §FR-001]
- [x] CHK011 Os casos de arquivo vazio, limite zero, path inexistente e Binwalk ausente estão cobertos pelos requisitos ou por Edge Cases? [Edge Case Coverage] [Spec §FR-003] [Spec §FR-007]
- [x] CHK012 O modo inferência e o modo `--label-from-path` definem os cinco campos de identidade em estados mutuamente consistentes? [Scenario Coverage] [Spec §FR-010]
- [x] CHK013 As limitações de corte por `max_bytes`, colisão potencial do prefixo e alcance de `max_strings` estão explicitadas como riscos, sem serem apresentadas como resultados resolvidos? [Assumption] [Spec §FR-004] [Spec §FR-006]

## Consistência e rastreabilidade

- [x] CHK014 Cada FR implementado está ligado a user story, módulo, evidência de teste e, quando parcial, a uma lacuna única? [Traceability] [Spec §FR-001]
- [x] CHK015 A lacuna de determinismo entre processos está explicitamente registrada sem alegar evidência inexistente? [Gap] [Spec §FR-012]
- [ ] CHK016 O requisito de fallback do Binwalk é compatível com a exigência de tornar falhas de firmware visíveis no artefato ou na exceção? [Conflict] [Spec §FR-007] — pendente: FR-014 (Planejado, T11) define Binwalk obrigatório e `meta_binwalk_status`; satisfeito só depois da implementação

## Requisitos planejados (escopo restante, 2026-09-24)

- [x] CHK017 Cada FR Planejado cita a TickTick de origem, tem linha prevista na matriz do `plan.md` e ao menos uma task na fase "Implementação planejada"; o FR Proposto está marcado sem task? [Traceability] [Spec §FR-014–FR-019]
- [x] CHK018 Os valores do clarify e do analyze (256 MiB, 2 GiB, 100 mil arquivos, 300 s, binwalk ≥ 2.3.4) e os valores de `meta_binwalk_status`, `meta_unpack_status`, `meta_strings_source` e `meta_unpack_files_cut` (inclusive `nao_executado`) estão definidos sem ambiguidade entre spec e data-model? [Clarity] [Spec §FR-014–FR-016]
- [x] CHK019 As substituições de comportamento Implementado (FR-002 e FR-003 sobre `max_bytes`; FR-004 valor; FR-007 sem Binwalk; FR-009 metadados; US4.2) estão explícitas nos FRs Planejado? [Consistency] [Spec §FR-002] [Spec §FR-003] [Spec §FR-004] [Spec §FR-007] [Spec §FR-009] [Spec §FR-014–FR-016] [Spec §FR-019]
- [x] CHK020 O desempacotamento tem requisitos de segurança observáveis (sem execução, versão mínima do extrator, `HOME` isolado, sem privilégio, sem seguir symlinks, sem escrita fora do diretório, limites totais e por arquivo, limpeza)? [Non-Functional] [Spec §FR-014] [Spec §FR-016] [Spec §US5.4–US5.6]
- [x] CHK021 Cada cenário Planejado (US3.4-US3.6, US4.3, US5.1-US5.6) é citado por uma task de teste? [Traceability] [Spec §User Scenarios & Testing]
- [x] CHK022 Os limites de tempo não tornam a saída dependente da carga da máquina (timeout é falha que exige rodar de novo) e o risco está no Complexity Tracking? [Non-Functional] [Spec §FR-014] [Spec §FR-016] [Spec §SC-007] [princípio V]
- [x] CHK023 A memória da extração não cresce com o tamanho do arquivo nem do filesystem extraído (strings em streaming; dedupe só no documento)? [Non-Functional] [Spec §FR-015] [Spec §FR-016] [Spec §SC-005] [princípio VI]

## Notes

- Tema: rastreabilidade e testabilidade; profundidade: Standard; público: banca/revisor de PR.
- Foco: qualidade dos critérios de aceitação, cobertura de cenários e edge cases, consistência entre spec, plan e tasks, rastreabilidade e requisitos não funcionais dos princípios V e VI.
- `/speckit.implement` lê o estado deste checklist como gate e não altera os marcadores.
- `checklists/requirements.md` mantém seu ciclo separado de `/speckit.specify` e `/speckit.clarify`.
