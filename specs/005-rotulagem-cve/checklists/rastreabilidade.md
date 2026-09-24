# Checklist de rastreabilidade e testabilidade: Rotulagem por CVE

**Purpose**: Avaliar a qualidade dos requisitos, cenários, rastreabilidade e requisitos não funcionais da rotulagem por CVE.
**Created**: 2026-09-24
**Feature**: [spec.md](../spec.md)

**Note**: Este checklist foi gerado segundo o fluxo de `/speckit.checklist` para revisão pela banca ou por revisor de PR.
**Review Ownership**: Este artefato pertence ao revisor. `[x]` indica que o critério de qualidade dos requisitos foi revisado e satisfeito, não que a implementação esteja concluída.

## Acceptance Criteria Quality

- [x] CHK001 Os resultados de classe e os limites de CVSS estão definidos com valores objetivos e verificáveis? [Spec §FR-013]
- [x] CHK002 As pré-condições e mensagens observáveis de erro identificam os dados que tornam a rotulagem inválida? [Spec §FR-002, Spec §FR-003, Spec §FR-004]
- [x] CHK003 A saída especifica cardinalidade, ordem e conjunto exato de colunas sem termos subjetivos? [Spec §FR-015]

## Scenario Coverage

- [x] CHK004 Cada fluxo primário das cinco user stories possui critérios Given/When/Then vinculáveis a pelo menos um FR? [Spec §FR-003, Spec §FR-005, Spec §FR-012, Spec §FR-016]
- [x] CHK005 Os cenários distinguem claramente os estados aplicável, não aplicável, indeterminado e sem CVE conhecida? [Spec §FR-005, Spec §FR-012, Spec §FR-013]
- [x] CHK006 Os fluxos de exceção cobrem identidade ausente, divergência de versão, linha duplicada e entrada de cache inválida? [Spec §FR-002, Spec §FR-003, Spec §FR-004]

## Edge Case Coverage

- [x] CHK007 As regras para versão ausente, CPE exata, limites, sufixos e `update` definem resultados sem depender de interpretação do leitor? [Spec §FR-005, Spec §FR-008, Spec §FR-009, Spec §FR-010, Spec §FR-011]
- [x] CHK008 A agregação entre aliases define deduplicação, precedência e limites inferior e superior para todos os estados? [Spec §FR-012]
- [x] CHK009 As limitações aceitas e os dados necessários para medi-las estão explicitados separadamente dos comportamentos normativos? [Assumption, Spec §Edge Cases]

## Consistency and Traceability

- [x] CHK010 Os termos `aplicável`, `indeterminada`, `não aplicável`, `indeterminado` e `alias` mantêm o mesmo significado entre spec, plan, data model e tasks? [Consistency, Spec §Clarifications]
- [x] CHK011 Cada FR Implementado aparece uma vez na matriz US → FR → módulo → teste e em uma task de verificação? [Spec §FR-001–FR-017]
- [x] CHK012 Cada cenário numerado possui evidência e resultado registrados nas tasks e no relatório de validação? [Spec §User Scenarios & Testing]
- [x] CHK013 Toda cobertura parcial ou ausente na matriz tem uma lacuna única em `Sem verificação` e na fase `Lacunas de teste`? [Gap, Spec §FR-001, Spec §FR-002, Spec §FR-006, Spec §FR-010, Spec §FR-012, Spec §FR-013, Spec §FR-015, Spec §FR-016, Spec §FR-017]

## Non-Functional Requirements

- [ ] CHK014 O requisito de persistência define e satisfaz local canônico, parâmetros e entradas necessários para reproduzir o artefato em outro processo? [Conflict, Spec §FR-015, princípio V] — pendente: TODO.md 005/princípio V
- [x] CHK015 Os requisitos tornam falhas de entrada observáveis antes da gravação e proíbem saída parcial silenciosa? [Spec §FR-002, Spec §FR-003, Spec §FR-004, Spec §FR-015, princípio VI]
- [ ] CHK016 O tratamento especificado para CPE exata sem base numérica preserva a incerteza de modo compatível com a exigência de erro visível? [Conflict, Spec §FR-010, princípio VI] — pendente: limitação aceita pelo pesquisador (TODO.md, "CPE da Belkin": decidido não corrigir); ver Complexity Tracking

## Notes

- Avaliação autorizada pelo pesquisador para profundidade Standard e público banca/revisor de PR.
- Itens abertos registram conflitos herdados do código; a spec descreve o comportamento atual conforme a hierarquia de verdade.
- `/speckit.implement` lê o estado deste checklist e não altera seus marcadores.
