# Implementation Plan: Versão do firmware a partir do path

**Branch**: `docs/specs-retroativas` | **Date**: 2026-09-24 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/004-versao-firmware/spec.md`

**Note**: plano retroativo. Descreve o código que já existe em `master`; não
há Phase 0 (`research.md`), `data-model.md` (a spec não é dona de
artefato), `contracts/` nem `quickstart.md`. O `tasks.md` fica para a
subtask 3 (validação com `/speckit.analyze`).

## Summary

A inferência lê só o path `raw/<fabricante>/<modelo>[_versão]/arquivo` e
devolve fabricante, modelo, identificador, versão e origem da versão:
sufixo do diretório com prioridade, senão regra de nome de arquivo por
fabricante, e nulo quando não há versão inequívoca. O papel da versão na
rotulagem está em `docs/PIPELINE.md`, §"3. Rotulagem por CVE".

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

**Constraints**: não lê o conteúdo do binário; regras fixas em código, sem
parâmetro de configuração

**Scale/Scope**: 840 paths em `dataset/raw`, 6 diretórios de fabricante
(`asus`, `belkin`, `dlink`, `netgear`, `tp_link`, `tplink`), 310 modelos

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

|Princípio|Resultado|Evidência|
|---|---|---|
|I. Somente análise estática|Passa|Só o path é lido (`pipeline/feature_extraction.py::infer_brand_model_label_from_path`); nenhum byte do firmware|
|II. Rótulo exclusivamente por CVE|Passa|A versão só serve de chave de consulta. Nome ambíguo resulta em versão nula, sem chute: `tests/test_feature_extraction.py::test_infer_path_ambiguous_filename_has_no_version`; casos `None` em `tests/test_firmware_version.py::test_dlink`|
|III. Sem vazamento|Passa|Identidade e versão ficam fora do vetor: `tests/test_pipeline_extraction.py::test_classifier_features_exclude_cve_and_identity_fields`; nulas no modo inferência: `tests/test_pipeline_cli.py::test_cli_without_label_from_path_zeroes_version`|
|IV. Modelos simples|Não se aplica|Sem modelo nesta etapa|
|V. Reprodutibilidade|Passa|Função pura do path, sem aleatoriedade nem config; reaplicada aos 840 `meta_path` de `features_v2.parquet`, reproduz 840/840 (spec, SC-002)|
|VI. Firmware não confiável|Passa parcialmente|Par versão/origem inconsistente levanta `ValueError` com o path (`tests/test_pipeline_extraction.py::test_extract_features_rejects_inconsistent_version_metadata`). Arquivo direto em `raw/<fabricante>/` recebe o nome do arquivo como modelo sem aviso; latente, 0 casos no dataset (spec, Edge Cases)|
|VII. Integridade científica|Passa|Todo FR tem módulo e teste abaixo ou aparece em "Sem verificação"; números medidos citam data e artefato|

## Project Structure

### Documentation (this feature)

```text
specs/004-versao-firmware/
├── spec.md              # /speckit.specify + /speckit.clarify
├── plan.md              # este arquivo
└── checklists/
    └── requirements.md  # checklist de qualidade da spec
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

### FR → módulo → teste

|FR|Módulo|Teste|
|---|---|---|
|FR-001|`pipeline/feature_extraction.py::infer_brand_model_label_from_path`|`test_feature_extraction.py::test_infer_path_strips_version_suffix`, `::test_infer_path_preserves_normal_model`; `test_pipeline_cli.py::test_cli_label_from_path`|
|FR-002|`pipeline/feature_extraction.py::infer_brand_model_label_from_path`|`test_feature_extraction.py::test_infer_path_no_raw_segment_returns_all_none` (parcial)|
|FR-003|`pipeline/feature_extraction.py::infer_brand_model_label_from_path`|`test_feature_extraction.py::test_infer_path_strips_version_suffix`, `::test_infer_path_preserves_normal_model`, `::test_infer_path_falls_back_to_version_in_filename`; `test_pipeline_cli.py::test_cli_label_from_path`|
|FR-004|`pipeline/feature_extraction.py::_split_model_version`|`test_feature_extraction.py::test_infer_path_strips_version_suffix`, `::test_infer_path_version_suffix_with_simple_digits`, `::test_infer_path_directory_version_with_hyphenated_model`, `::test_infer_path_hardware_revision_suffix_is_part_of_model`|
|FR-005|`pipeline/feature_extraction.py::infer_brand_model_label_from_path`, `VERSION_SOURCE_DIRECTORY`, `VERSION_SOURCE_FILENAME`|`test_feature_extraction.py::test_infer_path_falls_back_to_version_in_filename`, `::test_infer_path_directory_version_wins_over_filename`|
|FR-006|`pipeline/firmware_version.py::infer_version_from_filename`|`test_firmware_version.py::test_unknown_brand_returns_none`, `::test_extension_is_case_insensitive`, `::test_belkin` (caso `%20`)|
|FR-007|`pipeline/firmware_version.py::_netgear`|`test_firmware_version.py::test_netgear`|
|FR-008|`pipeline/firmware_version.py::_asus`|`test_firmware_version.py::test_asus`|
|FR-009|`pipeline/firmware_version.py::_belkin`|`test_firmware_version.py::test_belkin`|
|FR-010|`pipeline/firmware_version.py::_dlink`|`test_firmware_version.py::test_dlink`|
|FR-011|`pipeline/firmware_version.py::_tplink`, `_RULES`|`test_firmware_version.py::test_tplink` (parametrizado com `tp_link` e `tplink`)|
|FR-012|`pipeline/firmware_version.py::infer_version_from_filename`; `pipeline/feature_extraction.py::infer_brand_model_label_from_path`|`test_feature_extraction.py::test_infer_path_ambiguous_filename_has_no_version`, `::test_infer_path_preserves_normal_model`; `test_firmware_version.py::test_unknown_brand_returns_none`|
|FR-013|`pipeline/feature_extraction.py::infer_brand_model_label_from_path`, `extract_features_from_path`|`test_pipeline_extraction.py::test_extract_features_rejects_inconsistent_version_metadata`|
|FR-014|`pipeline/feature_extraction.py::_process_path`, `_build_error_result`; `scripts/extract_features.py::main`|`test_pipeline_extraction.py::test_error_result_preserves_version_from_path`, `::test_classifier_features_exclude_cve_and_identity_fields`; `test_pipeline_cli.py::test_cli_label_from_path_extracts_version`, `::test_cli_without_label_from_path_zeroes_version`|

`test_firmware_version.py` tem 7 testes e `test_feature_extraction.py`, 8.

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

Nenhuma violação.
