# Implementation Plan: Busca de CVEs na NVD

**Branch**: `docs/specs-retroativas` | **Date**: 2026-09-24 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/003-busca-cve/spec.md`

**Note**: plano retroativo. Descreve o código que já existe em `master`; não há Phase 0 (`research.md`), `contracts/` nem `quickstart.md`. O `tasks.md` é retroativo: registra a verificação de cada FR e cenário e as lacunas de teste. As linhas `[Planejado]` (FR-013 a FR-018, TickTick T11) descrevem módulo e teste previstos; o `tasks.md` as decompõe na fase "Implementação planejada". FR-019 e FR-020 são `[Proposto]` e não têm task.

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
`--output` padrão `dataset/cve_cache.json` (v1). Planejado:
`dataset/processed/cve_cache_v2.json`, gerado por busca completa (FR-014,
FR-015)

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
|II. Rótulo exclusivamente por CVE|Passa parcialmente|Produz o cache do qual sai o rótulo; par com falha de rede não ganha entrada (`scripts/fetch_cves.py::main`), então a ausência chega à rotulagem como erro. Sem teste do ramo de falha (ver "Sem verificação"). Com `--force`, a entrada antiga sobrevive à falha: correção Planejado em FR-013|
|III. Sem vazamento|Passa|`scripts/fetch_cves.py::main` lê só `meta_brand`/`meta_model` e escreve só o cache; nada volta ao vetor de features. Guarda do vetor em `tests/test_pipeline_extraction.py::test_classifier_features_exclude_cve_and_identity_fields` (001)|
|IV. Modelos simples|Não se aplica|Sem modelo nesta etapa|
|V. Reprodutibilidade|Passa parcialmente|Ordem de pares determinística (`tests/test_fetch_cves.py::test_extract_pairs_sorted`); parâmetros por CLI. Mas a entrada não registra a data da consulta à NVD, o `--output` padrão (v1) não é o artefato em uso e não há registro versionado do comando que gerou o v2. Correção Planejado: FR-014 (data), FR-015 (path) e FR-021 (metadados da execução ao lado do cache). Ver Complexity Tracking|
|VI. Firmware não confiável|Violação herdada|Falha de rede por par vai para log de erro e o par fica fora do cache (`scripts/fetch_cves.py::main`). Mas, com `--force`, a entrada anterior sobrevive à falha sem marca no artefato, e um parquet sem `meta_brand`/`meta_model` resulta em 0 pares sem erro, com linhas descartadas sem contagem. Correção Planejado: FR-013 e FR-017. Ver Complexity Tracking|
|VII. Integridade científica|Passa|Todo FR tem módulo e teste abaixo ou aparece em "Sem verificação"; números medidos citam data e artefato|

## Project Structure

### Documentation (this feature)

```text
specs/003-busca-cve/
├── spec.md                        # /speckit.specify + /speckit.clarify
├── plan.md                        # este arquivo
├── data-model.md                  # esquema do cache de CVE v2 e medição
├── tasks.md                       # verificação retroativa de FRs e cenários
└── checklists/
    ├── requirements.md            # checklist de qualidade da spec
    └── rastreabilidade.md         # checklist de rastreabilidade e testabilidade
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

### US → FR → módulo → teste

|FR|US|Módulo|Teste|
|---|---|---|---|
|FR-001|US1|`scripts/fetch_cves.py::extract_pairs`, `main`|`tests/test_fetch_cves.py::test_extract_pairs_dedupes_and_normalizes`, `tests/test_fetch_cves.py::test_extract_pairs_skips_missing_values`, `tests/test_fetch_cves.py::test_extract_pairs_empty_dataframe`, `tests/test_fetch_cves.py::test_extract_pairs_sorted` (parcial)|
|FR-002|US1, US3|`scripts/fetch_cves.py::VENDOR_ALIASES`, `normalize_vendor`, `normalize_model`|`tests/test_fetch_cves.py::test_normalize_vendor_dlink`, `tests/test_fetch_cves.py::test_normalize_vendor_tplink`, `tests/test_fetch_cves.py::test_normalize_vendor_tp_link_underscore`, `tests/test_fetch_cves.py::test_normalize_vendor_passthrough`, `tests/test_fetch_cves.py::test_normalize_model_with_hyphen`, `tests/test_fetch_cves.py::test_normalize_model_missing_hyphen`, `tests/test_fetch_cves.py::test_normalize_model_underscore_suffix`, `tests/test_fetch_cves.py::test_normalize_model_double_underscore`, `tests/test_fetch_cves.py::test_normalize_model_underscore_separated_words`, `tests/test_fetch_cves.py::test_normalize_model_never_sends_underscore`, `tests/test_fetch_cves.py::test_normalize_model_plain`|
|FR-003|US2|`scripts/fetch_cves.py::resolve_cpe_name`, `_fetch_cpe_page`, `_canonical_cpe_token`|`tests/test_fetch_cves.py::test_resolve_cpe_selects_matching_firmware_and_wildcards_version`, `tests/test_fetch_cves.py::test_resolve_cpe_generalizes_specific_update_and_edition` (parcial)|
|FR-004|US2|`scripts/fetch_cves.py::fetch_cves_for_pair`, `_fetch_all_pages`, `_fetch_page`|`tests/test_fetch_cves.py::test_fetch_prefers_resolved_cpe_query`, `tests/test_fetch_cves.py::test_fetch_keyword_retains_cve_and_configurations` (parcial)|
|FR-005|US2|`scripts/fetch_cves.py::extract_cvss`, `severity_bucket`, `_fetch_all_pages`|`tests/test_fetch_cves.py::test_extract_cvss_v31`, `tests/test_fetch_cves.py::test_extract_cvss_v30_fallback`, `tests/test_fetch_cves.py::test_extract_cvss_v2_fallback`, `tests/test_fetch_cves.py::test_extract_cvss_no_metrics`, `tests/test_fetch_cves.py::test_extract_cvss_empty_cve`, `tests/test_fetch_cves.py::test_fetch_keyword_retains_cve_and_configurations` (parcial)|
|FR-006|US1, US2|`scripts/fetch_cves.py::fetch_cves_for_pair`, `load_cache`, `save_cache`, `main`|`tests/test_fetch_cves.py::test_fetch_keyword_retains_cve_and_configurations` (parcial)|
|FR-007|US1|`scripts/fetch_cves.py::main`|—|
|FR-008|US4|`scripts/fetch_cves.py::main`|—|
|FR-009|US4|`scripts/fetch_cves.py::_should_save`, `SAVE_INTERVAL`, `main`|`tests/test_fetch_cves.py::test_should_save_at_interval`, `tests/test_fetch_cves.py::test_should_save_between_intervals` (parcial)|
|FR-010|US4|`scripts/fetch_cves.py::_build_headers`, `DEFAULT_DELAY_NO_KEY`, `DEFAULT_DELAY_WITH_KEY`, `main`|—|
|FR-011|US1|`scripts/fetch_cves.py::main`|—|
|FR-012|US4|`scripts/fetch_cves.py::main`|—|
|FR-013 [Planejado, TickTick T11]|US5|previsto: `scripts/fetch_cves.py::main` (remoção da entrada com `--force` e código de saída)|previsto: `tests/test_fetch_cves.py` (US5.1, com a NVD simulada)|
|FR-014 [Planejado, TickTick T11]|US5|previsto: `scripts/fetch_cves.py::fetch_cves_for_pair` (`schema_version: 3`, `fetched_at`), `main` (validação de esquema)|previsto: `tests/test_fetch_cves.py` (US5.2)|
|FR-015 [Planejado, TickTick T11]|US5|previsto: `scripts/fetch_cves.py::main` (padrão de `--output`)|previsto: `tests/test_fetch_cves.py` (US5.3)|
|FR-016 [Planejado, TickTick T11]|US5|previsto: `scripts/fetch_cves.py::extract_cvss`, `severity_bucket`|previsto: `tests/test_fetch_cves.py` (US5.4; teste novo com duas fontes na mesma versão)|
|FR-017 [Planejado, TickTick T11]|US5|previsto: `scripts/fetch_cves.py::main` (falha com 0 pares), `extract_pairs` (contagem de descartes)|previsto: `tests/test_fetch_cves.py` (US5.5)|
|FR-018 [Planejado, TickTick T11]|US5|previsto: `scripts/fetch_cves.py::resolve_cpe_name`, `_fetch_cpe_page` (paginação, parte `h`, tupla de distinção, `cpe_candidates`), `fetch_cves_for_pair`|previsto: `tests/test_fetch_cves.py` (US5.6)|
|FR-019 [Proposto, TickTick T11]|—|—|— (Proposto: sem task)|
|FR-020 [Proposto, TickTick T11]|—|—|— (Proposto: sem task)|
|FR-021 [Planejado, TickTick T11]|US5|previsto: `scripts/fetch_cves.py::main`, `save_cache` (gravação de `<nome>.meta.json`)|previsto: `tests/test_fetch_cves.py` (US5.7)|

### Sem verificação

Partes de FR sem teste permanente que as exercite (`main()` não tem teste):

- FR-001: leitura das duas colunas do parquet via `--features`.
- FR-003: filtro de parte `o` e leitura só da primeira página do dicionário
  de CPE.
- FR-004: paginação com mais de uma página.
- FR-005: métrica v2 sem `baseSeverity`, que recebe `MEDIUM`.
- FR-006: chave `"<fabricante>/<modelo>"`, `vendor`/`model` na forma NVD,
  gravação do arquivo e preservação de entradas de outros pares.
- FR-007: pulo de par em cache, validação de schema e `--force`.
- FR-008: ramo de falha de rede, ausência de entrada nova e continuação.
- FR-009: gravação periódica chamada por `main` e gravação final no `finally`.
- FR-010: `--delay`, padrões de 6 s e 1 s e cabeçalho `apiKey`.
- FR-011: fluxo `--dry-run` sem acesso à rede nem ao cache.
- FR-012: mensagens de progresso, falha e resumo.

### Símbolos com requisito em outra spec

Ficam no módulo desta spec, mas o requisito pertence a outra:

- `_aggregate_scores` em `scripts/fetch_cves.py`: não é chamado pela busca;
  `scripts/generate_labels.py` o usa para `cve_total` e `cvss_max` dos
  rótulos. Requisito em `005-rotulagem-cve` (005/FR-012), com os testes
  `test_fetch_cves.py::test_aggregate_empty`,
  `::test_aggregate_mixed_severities` e
  `::test_aggregate_none_severity_ignored`.

## Complexity Tracking

|Violação|Justificativa|Mitigação pendente|
|---|---|---|
|FR-006: o `--output` padrão aponta para o cache v1 e `--force` pode produzir um arquivo de esquemas mistos|O caminho padrão histórico foi mantido, enquanto o artefato v2 em uso tem outro nome|FR-015 [Planejado, TickTick T11]: padrão `dataset/processed/cve_cache_v2.json`|
|Princípio II: com `--force`, uma falha de rede preserva a entrada anterior sem indicar que a nova consulta falhou|A execução retomável evita perder evidência já gravada, mas o artefato pode aparentar uma consulta atual bem-sucedida|FR-013 [Planejado, TickTick T11]: remover a entrada e sair com código ≠ 0|
|Princípio V: as entradas não registram a data da consulta à NVD|O código atual preserva o retrato da NVD, mas não permite datá-lo sem evidência externa|FR-014 [Planejado, TickTick T11]: `fetched_at` obrigatório e busca completa|
|Princípio VI: parquet sem `meta_brand`/`meta_model` gera 0 pares e a execução termina sem erro; linhas com identidade nula são descartadas sem contagem|Herdada de `scripts/fetch_cves.py::extract_pairs` e `main`. Achado no analyze de 2026-09-24 (C1)|FR-017 [Planejado, TickTick T11]: falhar com 0 pares e contar descartes|
|Princípio V: não há registro versionado do comando e da entrada que geraram o cache|Herdada de `scripts/fetch_cves.py::main`. Achado no analyze de 2026-09-24 (C2)|FR-021 [Planejado, TickTick T11]: `<nome>.meta.json` ao lado do cache|
