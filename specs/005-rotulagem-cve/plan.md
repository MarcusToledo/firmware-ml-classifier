# Implementation Plan: Rotulagem por CVE

**Branch**: `docs/specs-retroativas` | **Date**: 2026-09-24 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/005-rotulagem-cve/spec.md`

**Note**: plano retroativo. Descreve o código que já existe em `master`; não
há Phase 0 (`research.md`), `contracts/` nem `quickstart.md`. O `tasks.md`
fica para a subtask 3 (validação com `/speckit.analyze`).

## Summary

A rotulagem lê as colunas de identificação da tabela de features e o cache
de CVE, separa as CVEs de cada firmware em aplicáveis e indeterminadas pela
versão, agrega por `firmware_id` entre aliases e grava um `security_level`
por linha em `labels_v2.csv`. O fluxo, a escala de severidade e o estado
do dataset estão em `docs/PIPELINE.md`, §"3. Rotulagem por CVE", "Escala
de severidade" e "Estado real do dataset".

## Technical Context

**Language/Version**: Python ≥ 3.9

**Primary Dependencies**: pandas, pyarrow (entrada parquet); biblioteca
padrão (`json`, `re`, `math`)

**Storage**: arquivos: lê `dataset/processed/features_v2.parquet` (ou CSV)
e `dataset/cve_cache_v2.json`; grava `dataset/labels_v2.csv`

**Testing**: pytest

**Target Platform**: Linux

**Project Type**: biblioteca + CLI (`generate-labels`, em `pyproject.toml`
`[project.scripts]`)

**Performance Goals**: sem meta definida

**Constraints**: sem rede (lê só o cache local); limiar `--critical-cvss`
padrão 9.0; `--output` padrão `dataset/labels.csv` (v1, ver Edge Cases da
spec)

**Scale/Scope**: 840 linhas e 699 `firmware_id` em `features_v2.parquet`;
310 entradas em `cve_cache_v2.json` (medido em 2026-09-24)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

|Princípio|Resultado|Evidência|
|---|---|---|
|I. Somente análise estática|Não se aplica|A rotulagem lê tabelas e o cache, nunca o binário|
|II. Rótulo exclusivamente por CVE|Passa|Classe só de `cve_total`/`cvss_max` em `tests/test_cve_labels.py::test_label_depends_only_on_cve_fields`; par ausente é erro em `tests/test_generate_labels.py::test_lookup_missing_pair_fails_instead_of_becoming_negative`; nenhum módulo da rotulagem importa `src/scoring.py` (conferido por grep)|
|III. Sem vazamento|Passa|`labels_v2.csv` não carrega features (`tests/test_generate_labels.py::test_cli_filters_version_before_aggregating_aliases` confere `entropy` fora da saída) e só as colunas de identificação são lidas (`scripts/generate_labels.py::ID_COLUMNS`). Excluir `vendor`, `model`, `version`, `version_source`, `cve_total` e `cvss_max` do treino fica para o treino futuro (`TODO.md`)|
|IV. Modelos simples|Não se aplica|Sem modelo nesta etapa|
|V. Reprodutibilidade|Passa parcialmente|Sem etapa aleatória; o código atual reproduz `labels_v2.csv` em 840/840 linhas (medido em 2026-09-24). Lacunas: sem teste de determinismo entre processos; `--output` padrão aponta para o v1; o artefato fica em `dataset/`, não em `dataset/processed/`, e não registra o limiar usado (pergunta ao pesquisador)|
|VI. Firmware não confiável|Violação herdada|Erros de entrada interrompem a execução e `indeterminado` fica visível no artefato, mas CPE exata sem base numérica vira "não aplicável" sem registro (`src/labeling/cve_labels.py::_match_version`; `tests/test_cve_labels.py::test_exact_cpe_without_parseable_base_keeps_known_limitation`). Ver Complexity Tracking|
|VII. Integridade científica|Passa|Todo FR tem módulo e teste abaixo ou aparece em "Sem verificação"; números medidos citam data e artefato|

## Project Structure

### Documentation (this feature)

```text
specs/005-rotulagem-cve/
├── spec.md              # /speckit.specify + /speckit.clarify
├── plan.md              # este arquivo
├── data-model.md        # esquema de labels_v2.csv
└── checklists/
    └── requirements.md  # checklist de qualidade da spec
```

### Source Code (repository root)

```text
scripts/
└── generate_labels.py      # CLI generate-labels: validação, consulta ao cache, regra C, CSV
src/
└── labeling/
    ├── cve_labels.py       # classes, label_from_cve_stats, applicable_cves_for_version
    └── version_match.py    # parse_version, VersionRange, comparação com padding

tests/
├── test_cve_labels.py
├── test_generate_labels.py
└── test_version_match.py
```

**Structure Decision**: estrutura de projeto único já existente. A fronteira
entre specs está no inventário `.docs/brainstorming/inventario-modulos.md`;
esta spec é dona só dos módulos acima. Dois símbolos de módulos de outras
specs são chamados aqui: `pipeline/feature_extraction.py::infer_brand_model_label_from_path`
(regra de versão de `004-versao-firmware`, `004/FR-004` e `004/FR-005`) e
`scripts/fetch_cves.py::_aggregate_scores` (contagem de `cve_total` e
`cvss_max`, requisito desta spec; ver tabela abaixo).

### FR → módulo → teste

|FR|Módulo|Teste|
|---|---|---|
|FR-001|`scripts/generate_labels.py::_load_features`, `ID_COLUMNS`, `main`|`test_generate_labels.py::test_cli_filters_version_before_aggregating_aliases` (parcial: só CSV)|
|FR-002|`scripts/generate_labels.py::_load_features`, `main`|`test_generate_labels.py::test_cli_rejects_missing_meta_path`, `::test_cli_rejects_duplicate_rows` (parcial)|
|FR-003|`scripts/generate_labels.py::_lookup_cve_entry`, `_label_rows`|`test_generate_labels.py::test_lookup_normalizes_identity_and_rejects_old_cache`, `::test_lookup_missing_pair_fails_instead_of_becoming_negative`, `::test_cli_reports_missing_identity_before_version_divergence`|
|FR-004|`scripts/generate_labels.py::_label_rows`, `_version_or_none`; `pipeline/feature_extraction.py::infer_brand_model_label_from_path`|`test_generate_labels.py::test_cli_rejects_version_divergent_from_meta_path`, `::test_cli_rejects_missing_version_when_meta_path_has_version`, `::test_cli_filters_version_before_aggregating_aliases`|
|FR-005|`src/labeling/cve_labels.py::applicable_cves_for_version`|`test_cve_labels.py::test_missing_version_is_indeterminate`, `::test_missing_version_with_empty_cache_has_negative_evidence`, `::test_applicable_and_indeterminate_cves_are_both_returned`|
|FR-006|`src/labeling/cve_labels.py::_evaluate_cve`, `_evaluate_node`, `_combine`, `_is_other_product`, `_target_parts`|`test_cve_labels.py::test_cve_without_cpe_information_applies_conservatively`, `::test_configuration_that_never_mentions_target_does_not_apply`, `::test_cve_with_only_other_products_does_not_apply`, `::test_cpe_criteria_prevents_other_product_range_from_matching` (parcial)|
|FR-007|`src/labeling/cve_labels.py::_match_platform`, `_match_version`, `_evaluate_node`|`test_cve_labels.py::test_target_hardware_platform_without_revision_is_satisfied`, `::test_target_hardware_platform_with_revision_is_indeterminate`, `::test_non_vulnerable_platform_of_other_product_is_indeterminate`, `::test_and_with_other_vulnerable_product_is_indeterminate`, `::test_configuration_with_unparseable_criteria_stays_indeterminate`|
|FR-008|`src/labeling/version_match.py::parse_version`, `version_in_range`, `versions_equal`; `src/labeling/cve_labels.py::_match_version`|`test_version_match.py::test_parse_version_extracts_leading_numeric_segments`, `::test_version_in_range_respects_boundaries`; `test_cve_labels.py::test_comparable_version_filters_fixed_release`, `::test_unparseable_cpe_bound_is_indeterminate`, `::test_vendor_suffix_is_not_silently_discarded_for_numeric_range`, `::test_build_suffix_in_bound_stays_indeterminate`|
|FR-009|`src/labeling/cve_labels.py::_normalize_cpe_version`, `_match_version`|`test_cve_labels.py::test_leading_v_is_removed_for_any_vendor`, `::test_asus_exact_cpe_version_normalizes_underscores`, `::test_asus_exclusive_bound_normalizes_underscores`, `::test_non_asus_bound_preserves_underscore`, `::test_netgear_exact_cpe_with_package_is_indeterminate_at_base`, `::test_netgear_range_removes_language_package`, `::test_netgear_packaged_bound_is_indeterminate_at_padded_base`|
|FR-010|`src/labeling/cve_labels.py::_match_version`|`test_cve_labels.py::test_exact_cpe_version_is_respected`, `::test_exact_cpe_version_matches_with_different_granularity`, `::test_exact_cpe_prerelease_is_indeterminate_at_matching_base`, `::test_exact_cpe_build_suffix_is_indeterminate_at_base`, `::test_exact_cpe_build_suffix_is_indeterminate_at_padded_base`, `::test_exact_cpe_build_suffix_does_not_match_extra_numeric_segment`, `::test_exact_numeric_cpe_does_not_match_firmware_suffix`, `::test_exact_cpe_build_suffix_does_not_apply_to_different_base`, `::test_exact_cpe_build_suffix_matches_case_insensitively`, `::test_exact_cpe_build_suffix_does_not_match_different_known_build`, `::test_exact_cpe_build_suffix_requires_separator_after_firmware_build`, `::test_exact_cpe_without_parseable_base_keeps_known_limitation`, `::test_exact_cpe_build_and_region_suffix_is_indeterminate`, `::test_exact_cpe_region_variant_is_indeterminate_for_matching_build`|
|FR-011|`src/labeling/cve_labels.py::_match_version`|`test_cve_labels.py::test_exact_cpe_with_specific_update_is_indeterminate_when_version_matches`, `::test_range_with_specific_update_is_indeterminate_inside_range`, `::test_not_applicable_update_marker_keeps_match`|
|FR-012|`scripts/generate_labels.py::_aggregate_firmware_label`, `_label_rows`; `scripts/fetch_cves.py::_aggregate_scores`|`test_generate_labels.py::test_aggregate_all_aliases_with_only_indeterminate_cves`, `::test_aggregate_critical_applicable_with_indeterminate_cve`, `::test_aggregate_known_applicable_with_critical_indeterminate_cve`, `::test_aggregate_known_applicable_with_only_known_indeterminate_cves`, `::test_aggregate_empty_evidence_is_valid_negative`, `::test_aggregate_keeps_indeterminate_cve_when_an_alias_has_no_evidence`, `::test_aggregate_applicable_cve_overrides_same_indeterminate_cve`, `::test_aggregate_deduplicates_applicable_cve_between_aliases`, `::test_cli_filters_version_before_aggregating_aliases`; `test_fetch_cves.py::test_aggregate_empty`, `::test_aggregate_mixed_severities`, `::test_aggregate_none_severity_ignored`|
|FR-013|`src/labeling/cve_labels.py::label_from_cve_stats`, `CveLabelThresholds`, `LABEL_*`; `scripts/generate_labels.py::main` (`--critical-cvss`)|`test_cve_labels.py::test_no_cve_data_returns_no_known_cve`, `::test_cve_total_zero_returns_no_known_cve`, `::test_known_cve_below_critical_threshold`, `::test_known_cve_at_critical_threshold`, `::test_known_cve_above_critical_threshold`, `::test_custom_critical_threshold`, `::test_invalid_cve_count_fails`, `::test_invalid_cvss_fails`, `::test_invalid_threshold_fails`, `::test_indeterminate_is_a_label_quality_state`|
|FR-014|`src/labeling/cve_labels.py::label_from_cve_stats`; `scripts/generate_labels.py::ID_COLUMNS`|`test_cve_labels.py::test_label_depends_only_on_cve_fields`; `test_generate_labels.py::test_cli_filters_version_before_aggregating_aliases`|
|FR-015|`scripts/generate_labels.py::_result_to_record`, `main`|`test_generate_labels.py::test_cli_filters_version_before_aggregating_aliases`, `::test_cli_missing_version_writes_indeterminate` (parcial)|
|FR-016|`scripts/generate_labels.py::main`|—|
|FR-017|`scripts/generate_labels.py::main`|—|

### Sem verificação

Partes de FR sem teste que as exercite:

- FR-001: entrada parquet (os testes da CLI usam só CSV).
- FR-002: tabela vazia, `firmware_id` nulo e cache que não é objeto JSON.
- FR-006: `negate` e produto-alvo derivado de `cpe_name` (os testes usam
  `vendor`/`model`).
- FR-010: versão CPE exata `-` como indeterminada.
- FR-012: erro para CVE sem ID válido.
- FR-013: `--critical-cvss` via CLI (o limiar é testado só pela função).
- FR-015: ordem exata das 9 colunas, criação do diretório de destino e
  ausência de arquivo de saída após erro.
- FR-016: `--dry-run`.
- FR-017: logs de contagem, de distribuição e do caminho gravado.

### Símbolos com requisito em outra spec

Nenhum. Nos módulos desta spec não há símbolo cujo requisito pertença a
outra. No sentido inverso, `scripts/fetch_cves.py::_aggregate_scores`
(módulo de `003-busca-cve`) só é chamado por esta spec e tem requisito
aqui (FR-012); a 003 o lista na sua seção equivalente.

## Complexity Tracking

|Violação|Por que existe|Alternativa|
|---|---|---|
|Princípio VI: CPE exata sem base numérica (ex.: `firmware_4.05.03`) vira "não aplicável" em vez de indeterminada, sem registro no artefato|Herdada de `src/labeling/cve_labels.py::_match_version`. O pesquisador decidiu não corrigir (`TODO.md`, CPE da Belkin); `docs/PIPELINE.md` registra impacto nulo no dataset atual|Devolver indeterminado nesse caso; rejeitada pelo pesquisador enquanto o impacto for nulo|
