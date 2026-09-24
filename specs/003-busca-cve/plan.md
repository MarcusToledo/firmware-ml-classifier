# Implementation Plan: Busca de CVEs na NVD

**Branch**: `docs/specs-retroativas` | **Date**: 2026-09-24 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/003-busca-cve/spec.md`

**Note**: plano retroativo. Descreve o código que já existe em `master`; não
há Phase 0 (`research.md`), `contracts/` nem `quickstart.md`. O `tasks.md`
fica para a subtask 3 (validação com `/speckit.analyze`).

## Summary

A busca lê os pares fabricante/modelo do parquet de features, resolve um
CPE oficial na NVD (ou cai na busca por texto) e grava num cache JSON
versionado cada CVE com CVSS, severidade e `configurations`. O papel da
etapa no pipeline está em `docs/PIPELINE.md`, §"3. Rotulagem por CVE".

## Technical Context

**Language/Version**: Python ≥ 3.9

**Primary Dependencies**: pandas, pyarrow (leitura do parquet), biblioteca
padrão (`urllib`, `json`); NVD API 2.0 (endpoints `cves/2.0` e
`cpes/2.0`), única dependência de rede do pipeline

**Storage**: arquivo JSON: `dataset/cve_cache_v2.json` (artefato em uso);
`--output` padrão `dataset/cve_cache.json` (v1)

**Testing**: pytest, com a NVD simulada por `unittest.mock.patch`

**Target Platform**: Linux

**Project Type**: script CLI (`scripts/fetch_cves.py`), sem entrada em
`pyproject.toml` `[project.scripts]`

**Performance Goals**: sem meta definida; limitada pela taxa da NVD
(`--delay` de 6 s sem chave, 1 s com `NVD_API_KEY`)

**Constraints**: timeout de 30 s por requisição; 2000 resultados por
página; gravação do cache a cada 10 pares buscados

**Scale/Scope**: 310 pares em `dataset/processed/features_v2.parquet`
(medido em 2026-09-24)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

|Princípio|Resultado|Evidência|
|---|---|---|
|I. Somente análise estática|Não se aplica|A etapa não lê binário; consulta só metadados na NVD|
|II. Rótulo exclusivamente por CVE|Passa|Produz o cache do qual sai o rótulo; par com falha de rede não ganha entrada (`scripts/fetch_cves.py::main`), então a ausência chega à rotulagem como erro. Sem teste do ramo de falha (ver "Sem verificação")|
|III. Sem vazamento|Passa|`scripts/fetch_cves.py::main` lê só `meta_brand`/`meta_model` e escreve só o cache; nada volta ao vetor de features. Guarda do vetor em `tests/test_pipeline_extraction.py::test_classifier_features_exclude_cve_and_identity_fields` (001)|
|IV. Modelos simples|Não se aplica|Sem modelo nesta etapa|
|V. Reprodutibilidade|Passa parcialmente|Ordem de pares determinística (`tests/test_fetch_cves.py::test_extract_pairs_sorted`); parâmetros por CLI. Mas a entrada não registra a data da consulta à NVD, e o `--output` padrão (v1) não é o artefato em uso, sem registro versionado do comando que gerou o v2|
|VI. Firmware não confiável|Passa parcialmente|Falha de rede por par vai para log de erro e o par fica fora do cache (`scripts/fetch_cves.py::main`). Com `--force`, a entrada anterior sobrevive à falha sem marca no artefato; parquet sem `meta_brand`/`meta_model` resulta em 0 pares sem erro|
|VII. Integridade científica|Passa|Todo FR tem módulo e teste abaixo ou aparece em "Sem verificação"; números medidos citam data e artefato|

## Project Structure

### Documentation (this feature)

```text
specs/003-busca-cve/
├── spec.md              # /speckit.specify + /speckit.clarify
├── plan.md              # este arquivo
├── data-model.md        # esquema do cache de CVE v2 e medição
└── checklists/
    └── requirements.md  # checklist de qualidade da spec
```

### Source Code (repository root)

```text
scripts/
└── fetch_cves.py        # pares, normalização, CPE, consulta NVD, cache JSON

tests/
└── test_fetch_cves.py
```

**Structure Decision**: estrutura de projeto único já existente. A fronteira
entre specs está no inventário `.docs/brainstorming/inventario-modulos.md`;
esta spec é dona só do módulo acima.

### FR → módulo → teste

|FR|Módulo|Teste|
|---|---|---|
|FR-001|`scripts/fetch_cves.py::extract_pairs`, `main`|`test_fetch_cves.py::test_extract_pairs_dedupes_and_normalizes`, `::test_extract_pairs_skips_missing_values`, `::test_extract_pairs_empty_dataframe`, `::test_extract_pairs_sorted`|
|FR-002|`scripts/fetch_cves.py::VENDOR_ALIASES`, `normalize_vendor`, `normalize_model`|`test_fetch_cves.py::test_normalize_vendor_dlink`, `::test_normalize_vendor_tplink`, `::test_normalize_vendor_tp_link_underscore`, `::test_normalize_vendor_passthrough`, `::test_normalize_model_with_hyphen`, `::test_normalize_model_missing_hyphen`, `::test_normalize_model_underscore_suffix`, `::test_normalize_model_double_underscore`, `::test_normalize_model_underscore_separated_words`, `::test_normalize_model_never_sends_underscore`, `::test_normalize_model_plain`|
|FR-003|`scripts/fetch_cves.py::resolve_cpe_name`, `_fetch_cpe_page`, `_canonical_cpe_token`|`test_fetch_cves.py::test_resolve_cpe_selects_matching_firmware_and_wildcards_version`, `::test_resolve_cpe_generalizes_specific_update_and_edition`|
|FR-004|`scripts/fetch_cves.py::fetch_cves_for_pair`, `_fetch_all_pages`, `_fetch_page`|`test_fetch_cves.py::test_fetch_prefers_resolved_cpe_query`, `::test_fetch_keyword_retains_cve_and_configurations`|
|FR-005|`scripts/fetch_cves.py::extract_cvss`, `severity_bucket`, `_fetch_all_pages`|`test_fetch_cves.py::test_extract_cvss_v31`, `::test_extract_cvss_v30_fallback`, `::test_extract_cvss_v2_fallback`, `::test_extract_cvss_no_metrics`, `::test_extract_cvss_empty_cve`, `::test_fetch_keyword_retains_cve_and_configurations`|
|FR-006|`scripts/fetch_cves.py::fetch_cves_for_pair`, `load_cache`, `save_cache`, `main`|`test_fetch_cves.py::test_fetch_keyword_retains_cve_and_configurations` (parcial: `schema_version`, `source`, `cves`)|
|FR-007|`scripts/fetch_cves.py::main`|sem teste|
|FR-008|`scripts/fetch_cves.py::main`|sem teste|
|FR-009|`scripts/fetch_cves.py::_should_save`, `SAVE_INTERVAL`, `main`|`test_fetch_cves.py::test_should_save_at_interval`, `::test_should_save_between_intervals`|
|FR-010|`scripts/fetch_cves.py::_build_headers`, `DEFAULT_DELAY_NO_KEY`, `DEFAULT_DELAY_WITH_KEY`, `main`|sem teste|
|FR-011|`scripts/fetch_cves.py::main`|sem teste|
|FR-012|`scripts/fetch_cves.py::main`|sem teste|

### Sem verificação

Partes de FR sem teste que as exercite (`main()` não tem teste):

- FR-001: leitura das duas colunas do parquet via `--features`.
- FR-003: filtro de parte `o` (nenhum teste tem CPE de outra parte) e
  leitura só da primeira página do dicionário.
- FR-004: paginação com mais de uma página (os testes simulam uma só).
- FR-005: métrica v2 sem `baseSeverity` (`MEDIUM`).
- FR-006: chave `"<fabricante>/<modelo>"`, `vendor`/`model` na forma NVD,
  gravação do arquivo e preservação de entradas de outros pares.
- FR-007: pulo de par em cache, validação de schema e `--force`.
- FR-008: ramo de falha de rede e ausência de entrada para o par.
- FR-009: gravação final no `finally`.
- FR-010: `--delay`, padrões de 6 s e 1 s e cabeçalho `apiKey`.
- FR-011: `--dry-run`.
- FR-012: mensagens de log e resumo.

### Símbolos com requisito em outra spec

Ficam no módulo desta spec, mas o requisito pertence a outra:

- `_aggregate_scores` em `scripts/fetch_cves.py`: não é chamado pela busca;
  `scripts/generate_labels.py` o usa para `cve_total` e `cvss_max` dos
  rótulos. Requisito em `005-rotulagem-cve`, com os testes
  `test_fetch_cves.py::test_aggregate_empty`,
  `::test_aggregate_mixed_severities` e
  `::test_aggregate_none_severity_ignored`.

## Complexity Tracking

Nenhuma violação.
