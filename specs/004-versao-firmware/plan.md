# Implementation Plan: Versão do firmware a partir do path

**Branch**: `docs/specs-retroativas` | **Date**: 2026-09-24 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/004-versao-firmware/spec.md`

**Note**: plano retroativo. Descreve o código que já existe em `master`; não há
Phase 0 (`research.md`), `contracts/` nem `quickstart.md`. O `tasks.md` é
retroativo: registra a verificação de cada FR e cenário e as lacunas de teste.
As linhas `[Planejado]` (FR-015 a FR-017, TickTick T11) descrevem módulo e
teste previstos; o `tasks.md` as decompõe na fase "Implementação
planejada". FR-018 é `[Proposto]` e não tem task.

## Summary

A inferência lê só o path `raw/<fabricante>/<modelo>[_versão]/arquivo` e
devolve fabricante, modelo, identificador, versão e origem da versão:
sufixo do diretório com prioridade, senão regra de nome de arquivo por
fabricante, e nulo quando não há versão inequívoca. O papel da versão na
rotulagem está em `docs/PIPELINE.md`, §"3. Rotulagem por CVE". Planejado:
o path passa a ser relativo à raiz do dataset (FR-016), paths fora do
layout falham (FR-015) e imagens DD-WRT são marcadas (FR-017).

## Technical Context

**Language/Version**: Python ≥ 3.9

**Primary Dependencies**: só biblioteca padrão (`re`, `urllib.parse`,
`pathlib`)

**Storage**: N/A. Sem artefato próprio; os valores vão às colunas
`meta_*` de `001-extracao-features` (001/FR-009)

**Testing**: pytest

**Target Platform**: Linux

**Project Type**: biblioteca, sem CLI próprio. Chamada pelo lote de
`extract-features` e por `scripts/generate_labels.py`

**Performance Goals**: sem meta definida; só regex sobre o path, sem I/O
(FR-017 reaproveita as strings que a extração já varre)

**Constraints**: não lê o conteúdo do binário; regras fixas em código, sem
parâmetro de configuração. Planejado: FR-017 lê strings do arquivo (e do
filesystem extraído por `001/FR-016`) para marcar imagens de terceiros;
FR-016 exige a raiz do dataset (`--dataset-root`) e grava `meta_path`
relativo a ela

**Scale/Scope**: 840 paths em `dataset/raw`, 6 diretórios de fabricante
(`asus`, `belkin`, `dlink`, `netgear`, `tp_link`, `tplink`), 310 modelos

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

|Princípio|Resultado|Evidência|
|---|---|---|
|I. Somente análise estática|Passa|Só o path é lido (`pipeline/feature_extraction.py::infer_brand_model_label_from_path`); nenhum byte do firmware. Planejado (FR-017): procurar as strings `DD-WRT`/`OpenWrt` nos bytes e no filesystem extraído é leitura estática, sem executar nada|
|II. Rótulo exclusivamente por CVE|Passa|A versão só serve de chave de consulta. Nome ambíguo resulta em versão nula, sem chute: `tests/test_feature_extraction.py::test_infer_path_ambiguous_filename_has_no_version`; casos `None` em `tests/test_firmware_version.py::test_dlink`|
|III. Sem vazamento|Passa|Identidade e versão ficam fora do vetor: `tests/test_pipeline_extraction.py::test_classifier_features_exclude_cve_and_identity_fields`; nulas no modo inferência: `tests/test_pipeline_cli.py::test_cli_without_label_from_path_zeroes_version`|
|IV. Modelos simples|Não se aplica|Sem modelo nesta etapa|
|V. Reprodutibilidade|Passa|Função pura do path, sem aleatoriedade nem config; reaplicada aos 840 `meta_path` de `features_v2.parquet`, reproduz 840/840 (spec, SC-002). Planejado: com FR-016, `meta_path` deixa de ser absoluto (hoje contém `/home/marcus/...`) e a identidade continua função só do path relativo; FR-017 não muda a versão pela marca de string|
|VI. Firmware não confiável|Violação herdada|Par versão/origem inconsistente levanta `ValueError` com o path (`tests/test_pipeline_extraction.py::test_extract_features_rejects_inconsistent_version_metadata`). Mas arquivo direto em `raw/<fabricante>/` recebe o nome do arquivo como modelo sem aviso e o primeiro `raw` do path é usado; latentes, 0 casos no dataset (spec, Edge Cases). Correção Planejado: FR-015 e FR-016. Ver Complexity Tracking|
|VII. Integridade científica|Passa|Todo FR tem módulo e teste abaixo ou aparece em "Sem verificação"; números medidos citam data e artefato|

## Project Structure

### Documentation (this feature)

```text
specs/004-versao-firmware/
├── spec.md                       # /speckit.specify + /speckit.clarify
├── plan.md                       # este arquivo
├── tasks.md                      # verificações retroativas e lacunas
└── checklists/
    ├── requirements.md           # qualidade geral da spec
    └── rastreabilidade.md        # rastreabilidade e testabilidade
```

### Source Code (repository root)

```text
pipeline/
└── firmware_version.py         # regras de versão por fabricante sobre o nome do arquivo

tests/
├── test_feature_extraction.py  # inferência de fabricante, modelo e versão pelo path
└── test_firmware_version.py    # regras Netgear, ASUS, Belkin, D-Link, TP-Link
```

**Structure Decision**: estrutura de projeto único já existente. Esta spec
é dona só de `pipeline/firmware_version.py`. A inferência pelo path
(`infer_brand_model_label_from_path`, `_split_model_version`,
`VERSION_SOURCE_DIRECTORY`, `VERSION_SOURCE_FILENAME`) e a regra "ambos ou
nenhum" ficam em `pipeline/feature_extraction.py`, módulo de
`001-extracao-features`, que os lista em "Símbolos com requisito em outra
spec". A tabela abaixo aponta o módulo real.

### US → FR → módulo → teste

|FR|US|Módulo|Teste|
|---|---|---|---|
|FR-001|US1|`pipeline/feature_extraction.py::infer_brand_model_label_from_path`|`test_feature_extraction.py::test_infer_path_strips_version_suffix`, `::test_infer_path_preserves_normal_model`; `test_pipeline_cli.py::test_cli_label_from_path`|
|FR-002|US1|`pipeline/feature_extraction.py::infer_brand_model_label_from_path`|`test_feature_extraction.py::test_infer_path_no_raw_segment_returns_all_none` (parcial)|
|FR-003|US1|`pipeline/feature_extraction.py::infer_brand_model_label_from_path`|`test_feature_extraction.py::test_infer_path_strips_version_suffix`, `::test_infer_path_preserves_normal_model`, `::test_infer_path_falls_back_to_version_in_filename`; `test_pipeline_cli.py::test_cli_label_from_path`|
|FR-004|US1, US2|`pipeline/feature_extraction.py::_split_model_version`|`test_feature_extraction.py::test_infer_path_strips_version_suffix`, `::test_infer_path_version_suffix_with_simple_digits`, `::test_infer_path_directory_version_with_hyphenated_model`, `::test_infer_path_hardware_revision_suffix_is_part_of_model`|
|FR-005|US2|`pipeline/feature_extraction.py::infer_brand_model_label_from_path`, `VERSION_SOURCE_DIRECTORY`, `VERSION_SOURCE_FILENAME`|`test_feature_extraction.py::test_infer_path_falls_back_to_version_in_filename`, `::test_infer_path_directory_version_wins_over_filename`|
|FR-006|US2, US3|`pipeline/firmware_version.py::infer_version_from_filename`|`test_firmware_version.py::test_unknown_brand_returns_none`, `::test_extension_is_case_insensitive`, `::test_belkin` (caso `%20`) (parcial)|
|FR-007|US2|`pipeline/firmware_version.py::_netgear`|`test_firmware_version.py::test_netgear`|
|FR-008|US2|`pipeline/firmware_version.py::_asus`|`test_firmware_version.py::test_asus`|
|FR-009|US2|`pipeline/firmware_version.py::_belkin`|`test_firmware_version.py::test_belkin`|
|FR-010|US3|`pipeline/firmware_version.py::_dlink`|`test_firmware_version.py::test_dlink`|
|FR-011|US2|`pipeline/firmware_version.py::_tplink`, `_RULES`|`test_firmware_version.py::test_tplink` (parametrizado com `tp_link` e `tplink`)|
|FR-012|US3|`pipeline/firmware_version.py::infer_version_from_filename`; `pipeline/feature_extraction.py::infer_brand_model_label_from_path`|`test_feature_extraction.py::test_infer_path_ambiguous_filename_has_no_version`, `::test_infer_path_preserves_normal_model`; `test_firmware_version.py::test_unknown_brand_returns_none`|
|FR-013|US3|`pipeline/feature_extraction.py::infer_brand_model_label_from_path`, `extract_features_from_path`|`test_pipeline_extraction.py::test_extract_features_rejects_inconsistent_version_metadata`|
|FR-014|US4|`pipeline/feature_extraction.py::_process_path`, `_build_error_result`; `scripts/extract_features.py::main`|`test_pipeline_extraction.py::test_error_result_preserves_version_from_path`, `::test_classifier_features_exclude_cve_and_identity_fields`; `test_pipeline_cli.py::test_cli_label_from_path_extracts_version`, `::test_cli_without_label_from_path_zeroes_version` (parcial)|
|FR-015 [Planejado, TickTick T11]|US5|previsto: `pipeline/feature_extraction.py::infer_brand_model_label_from_path` (layout inválido), `extract_features_batch` (checagem antes do lote); `scripts/extract_features.py::main`|previsto: `tests/test_pipeline_cli.py` (US5.1)|
|FR-016 [Planejado, TickTick T11]|US5|previsto: `pipeline/feature_extraction.py::infer_brand_model_label_from_path` (raiz em vez do primeiro `raw`), `extract_features_from_path` (`meta_path` relativo); `scripts/extract_features.py::main` (`--dataset-root`); `scripts/generate_labels.py::_label_rows` (reinferência sobre o path relativo)|previsto: `tests/test_feature_extraction.py` (US5.2), `tests/test_pipeline_cli.py` (US5.3), `tests/test_generate_labels.py` (reinferência com path relativo)|
|FR-017 [Planejado, TickTick T11]|US5|previsto: `pipeline/feature_extraction.py::extract_features_from_path` (nome `webflash` e banner `DD-WRT` nas strings dos detectores, `meta_third_party`, também sem `--label-from-path`), `infer_brand_model_label_from_path` (sem versão só para a marca de nome)|previsto: `tests/test_pipeline_extraction.py` (US5.4, incluindo firmware oficial com `OpenWrt` sem marca)|
|FR-018 [Proposto, TickTick T11]|—|—|— (Proposto: sem task)|

`test_firmware_version.py` tem 7 testes e `test_feature_extraction.py`, 9.

### Sem verificação

Partes de FR sem teste que as exercite:

- FR-002: path com menos de dois segmentos depois de `raw` e fabricante ou
  modelo vazio (só a ausência de `raw` tem teste).
- FR-006: fabricante com maiúsculas ou espaços (os testes passam o nome já
  em minúsculas).
- FR-014: ramo de exceção de `_process_path`, que chama
  `_build_error_result` (o `except` é marcado `pragma: no cover`). O teste
  de path inexistente passa pelo caminho `empty firmware`, não pela
  exceção; a docstring enganosa já está no `TODO.md`.

### Símbolos com requisito em outra spec

Nenhum.

## Complexity Tracking

|Violação|Por que permanece|Mitigação|
|---|---|---|
|Princípio VI — `raw/<fabricante>/arquivo` é aceito como fabricante e modelo, sem sinalizar o layout incompleto|Comportamento herdado do código em `master`|FR-015 [Planejado, TickTick T11]: falhar antes do lote com `--label-from-path`|
|Princípio VI — o primeiro segmento `raw` do path é usado, mesmo quando está acima do dataset esperado|Comportamento herdado do código em `master`|FR-016 [Planejado, TickTick T11]: layout relativo à raiz do dataset|
