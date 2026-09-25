# Specification Quality Checklist: Rotulagem por CVE

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-09-24
**Feature**: [spec.md](../spec.md)

## Content Quality

- [x] No implementation details (languages, frameworks, APIs)
- [x] Focused on user value and business needs
- [x] Written for non-technical stakeholders
- [x] All mandatory sections completed

## Requirement Completeness

- [x] No [NEEDS CLARIFICATION] markers remain
- [x] Requirements are testable and unambiguous
- [x] Success criteria are measurable
- [x] Success criteria are technology-agnostic (no implementation details)
- [x] All acceptance scenarios are defined
- [x] Edge cases are identified
- [x] Scope is clearly bounded
- [x] Dependencies and assumptions identified

## Feature Readiness

- [x] All functional requirements have clear acceptance criteria
- [x] User scenarios cover primary flows
- [x] Feature meets measurable outcomes defined in Success Criteria
- [x] No implementation details leak into specification

## Notes

- "No implementation details": a spec cita o artefato (`labels_v2.csv`),
  nomes de coluna (`firmware_id`, `meta_path`, `security_level`,
  `cve_total`, `cvss_max`, `meta_brand`, `meta_model`, `meta_version`),
  os valores de classe (`sem_cve_conhecida`, `cve_conhecida`,
  `cve_critica`, `indeterminado`), campos do cache e da CPE 2.3
  (`schema_version`, `configurations`, `versionEndExcluding`, `update`) e
  opções da CLI (`--critical-cvss`, `--dry-run`, `--output`). Eles são o
  contrato que a banca audita e que o treino consome; a regra de rótulo
  não pode ser auditada sem eles. Não há módulos, funções nem testes no
  `spec.md`; esses ficam no `plan.md`.
- "Written for non-technical stakeholders": os leitores são o pesquisador e
  a banca (constituição, Convenções de Especificação), então termos como
  CPE, CVSS e lógica de três valores são mantidos.
- "Success criteria are technology-agnostic": SC-003 a SC-005 citam
  `labels_v2.csv` e suas colunas, que são contrato, não tecnologia.
- (Histórico, spec retroativa) A pergunta sobre o local canônico da tabela
  de rótulos (`--output` padrão v1 e `dataset/` fora de
  `dataset/processed/`) não alterava nenhum FR e ficou em Edge Cases, sem
  marcador. Hoje é FR-018 (Planejado).
- (Histórico, spec retroativa) Todos os FRs levavam a tag `[Implementado]`;
  limitações conhecidas ficavam em Edge Cases, não em FRs.
- Status Misto (2026-09-24, escopo restante do TCC): FR-018 a FR-024,
  FR-026 e SC-006/SC-007 são `[Planejado, TickTick T04]`; FR-025 é
  `[Proposto, TickTick T04]`. FR-018 resolve o local canônico acima; FR-019
  reverte a limitação de CPE sem base numérica. Os itens acima continuam
  passando para os FRs novos.
