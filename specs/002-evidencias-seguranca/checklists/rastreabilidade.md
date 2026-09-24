# Checklist de rastreabilidade e testabilidade: Evidências de segurança

**Purpose**: Avaliar a qualidade dos requisitos, cenários, critérios de aceite e vínculos entre spec, plano, tasks, código e testes.
**Created**: 2026-09-24
**Feature**: [spec.md](../spec.md)

**Note**: Este checklist customizado segue o `/speckit.checklist` e avalia requisitos, não a implementação.
**Review Ownership**: Artefato do revisor para a banca e a revisão de PR. `[x]` indica que o critério de qualidade do requisito foi revisado e satisfeito.
**Marker Semantics**: `[x]` não declara que a implementação está concluída; indica apenas aprovação da qualidade do requisito.

## Acceptance Criteria Quality

- [x] CHK001 Os resultados esperados dos detectores definem categoria, confiança e cardinalidade de forma objetiva? [Spec §FR-003–FR-013]
- [x] CHK002 A derivação das 13 colunas distingue sem ambiguidade contagens e flags booleanas? [Spec §FR-014]
- [x] CHK003 O formato JSONL define campos, codificação, sobrescrita, ordem e observabilidade por log com critérios verificáveis? [Spec §FR-016]

## Scenario Coverage

- [x] CHK004 Os cenários cobrem os fluxos primários de auditoria, agregação e isolamento de CVE/identidade? [Spec §US1–US3]
- [x] CHK005 Os cenários de ausência de achado e omissão de `--findings-output` têm resultados explícitos? [Spec §US1.2, §US1.4, §US2.1]
- [x] CHK006 A regra de contagem por string e por ocorrência está exemplificada sem depender de interpretação implícita? [Spec §US2.4, §FR-004, §FR-006]

## Edge Case Coverage

- [x] CHK007 A falha de leitura tratada e a exceção inesperada estão diferenciadas quanto a achados e presença das colunas? [Spec §FR-001, §FR-014, §SC-003] — corrigido: FR-014 passou a registrar a exceção inesperada sem features.
- [x] CHK008 As limitações conhecidas de falso positivo dos detectores estão quantificadas e ligadas às regras correspondentes? [Spec §Edge Cases, §FR-005, §FR-006, §FR-008, §FR-011–FR-013]
- [x] CHK009 As limitações de cobertura causadas por `max_strings` e pelos cinco detectores constantes estão documentadas com medição e escopo? [Spec §Edge Cases, Assumption]

## Consistency and Traceability

- [x] CHK010 Cada FR Implementado aparece uma única vez na matriz US → FR → módulo → teste e em uma task de verificação? [Spec §FR-001–FR-016]
- [x] CHK011 Cada cenário numerado possui evidência executada e uma task com o mesmo identificador? [Spec §US1.1–US3.3]
- [x] CHK012 As nove coberturas parciais estão marcadas de modo consistente no plano, nas tasks e na fase de lacunas? [Gap, Spec §FR-001, §FR-002, §FR-006, §FR-007, §FR-009, §FR-011, §FR-014–FR-016]
- [x] CHK013 Os módulos de `001-extracao-features` usados por esta feature estão distinguidos dos módulos próprios sem criar uma segunda fonte de requisitos? [Assumption, Spec §FR-001, §FR-014–FR-016]

## Non-Functional Requirements

- [ ] CHK014 O requisito de `detector_version` permite identificar de forma inequívoca a regra que produziu cada artefato? [Conflict, Spec §FR-002, Constituição princípio V] — pendente: TODO.md 002/FR-002
- [ ] CHK015 O requisito torna distinguíveis “Binwalk indisponível/com erro” e “varredura sem evidência criptográfica”? [Conflict, Spec §FR-001, Constituição princípio VI] — pendente: TODO.md 001/FR-007
- [x] CHK016 Os critérios mensuráveis citam artefato, população, data da medição e exceções relevantes, sem apresentar resultado não executado? [Spec §SC-001–SC-003]

## Notes

- Avaliação autorizada pelo pesquisador em 2026-09-24.
- Profundidade: Standard. Público: banca e revisor de PR.
- Foco: qualidade dos critérios de aceite, cobertura de cenários e casos-limite, consistência, rastreabilidade e princípios V e VI.
- `/speckit.implement` lê os marcadores como gate e não os altera.
- `checklists/requirements.md` mantém ciclo separado.
