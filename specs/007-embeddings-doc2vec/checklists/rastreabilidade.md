# Checklist de Rastreabilidade e Testabilidade: Embeddings Doc2Vec

**Purpose**: Avaliar a qualidade dos requisitos, cenários, critérios de aceitação e rastreabilidade para revisão pela banca ou em PR.
**Created**: 2026-09-24
**Feature**: [spec.md](../spec.md)

**Note**: Este checklist customizado segue o `/speckit.checklist` e avalia os requisitos escritos, não a conclusão da implementação.
**Review Ownership**: Este artefato pertence ao revisor; a avaliação abaixo foi autorizada pelo pesquisador.
**Marker Semantics**: `[x]` indica que o critério de qualidade dos requisitos foi revisado e satisfeito. Não indica que a implementação está completa.

## Completude e clareza dos requisitos

- [x] CHK001 Os tipos de entrada, a recursão e os critérios exatos de inclusão por nome e extensão estão definidos sem depender do significado ambíguo de “oculto”? [Clarity] [Spec §FR-001] — corrigido: o requisito agora explicita que o nome não começa com `.`
- [x] CHK002 Os limites que formam o documento e a regra de tokenização estão enumerados de modo completo e vinculados à extração compartilhada? [Completeness] [Spec §FR-002]
- [x] CHK003 As condições de descarte, os warnings e a falha por corpus vazio distinguem arquivo vazio, ilegível e documento sem tokens? [Completeness] [Spec §FR-003]
- [x] CHK004 Os padrões de todos os parâmetros `doc2vec.*` e as duas fontes de configuração estão quantificados? [Clarity] [Spec §FR-004]
- [x] CHK005 A precedência do path de saída, a criação de diretórios, a sobrescrita e o registro em log estão definidos objetivamente? [Acceptance Criteria] [Spec §FR-006]
- [x] CHK006 A semântica de `meta_doc2vec_used` cobre modelo ausente, leitura inválida, exceção e documento sem tokens sem contradição interna? [Consistency] [Spec §FR-009]

## Qualidade dos critérios e cobertura de cenários

- [x] CHK007 Os cenários de treino cobrem caminho padrão, override de dimensão, output alternativo, parâmetro inválido e ausência de documentos válidos com resultados observáveis? [Scenario Coverage] [Spec §US1]
- [x] CHK008 Os cenários de extração distinguem modelo ausente, modelo presente, documento sem tokens e tokens fora do vocabulário com resultados mensuráveis? [Scenario Coverage] [Spec §US2]
- [x] CHK009 O cenário de documento sem tokens especifica tanto o vetor zero quanto a proveniência registrada? [Acceptance Criteria] [Spec §FR-008] [Spec §FR-009] — corrigido: o cenário US2.3 agora explicita `meta_doc2vec_used=True`
- [x] CHK010 Os cenários de inspeção quantificam limites de documentos, preview de tokens e corte do documento? [Acceptance Criteria] [Spec §US3]
- [x] CHK011 As situações de aliases repetidos, ordem do corpus, dimensões divergentes e ausência do modelo estão documentadas como edge cases, sem apresentá-las como comportamento resolvido? [Edge Case Coverage] [Spec §Edge Cases]

## Consistência e rastreabilidade

- [x] CHK012 Cada FR implementado possui uma linha única na matriz US → FR → módulo → teste e uma task na primeira história associada? [Traceability] [Spec §FR-001–FR-010]
- [x] CHK013 Cada cobertura parcial ou ausente identifica a parte não exercitada e uma lacuna correspondente, sem usar script descartável como teste permanente? [Traceability] [Gap]
- [x] CHK014 Cada cenário Given/When/Then possui identificador estável `USk.n`, evidência executada e task correspondente? [Traceability] [Spec §US1–US3]
- [x] CHK015 A terminologia “documento”, “token”, “modelo” e “vetor Doc2Vec” permanece consistente entre spec, plan, data model e tasks? [Consistency] [Spec §Clarifications]

## Requisitos não funcionais e constituição

- [ ] CHK016 O requisito de determinismo entre processos possui critério verificável para ordem de inferência e `PYTHONHASHSEED`, em vez de depender apenas da semente global? [Gap] [Spec §Edge Cases] [Constitution V] — pendente: FR-012 é Proposto (TickTick T06)
- [ ] CHK017 O requisito de persistência do transformador enumera metadados legíveis, limites do corpus e `firmware_id` da partição de treino necessários para reprodução? [Gap] [Spec §FR-006] [Constitution V] — pendente: FR-013 é Proposto (TickTick T06)
- [x] CHK018 Os requisitos de entrada não confiável definem limites de leitura e tornam falhas, arquivos vazios e documentos sem tokens observáveis? [Coverage] [Spec §FR-002] [Spec §FR-003] [Constitution VI]

## Requisitos propostos (escopo restante, 2026-09-24)

- [x] CHK019 Cada FR Proposto cita a TickTick de origem (T06), aparece na matriz marcado sem task e não tem task no `tasks.md`? [Traceability] [Spec §FR-011–FR-015]
- [x] CHK020 A condição de uso das violações herdadas (III, V) está explícita: `doc2vec_*` desligado por padrão (`001/FR-018`) e fora do modelo reportado até a T06 ser promovida? [Consistency] [Plan §Complexity Tracking] [001/FR-018]

## Notes

- `[x]` registra a aprovação do revisor sobre a qualidade do requisito.
- `[ ]` identifica requisito constitucional ainda não atendido pelo código e encaminhado ao `TODO.md`.
- `/speckit.implement` lê o estado deste checklist, mas não altera os marcadores.
- `checklists/requirements.md` mantém seu ciclo separado de `/speckit.specify` e `/speckit.clarify`.
