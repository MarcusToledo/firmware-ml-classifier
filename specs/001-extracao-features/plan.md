# Implementation Plan: Extração estática de features

**Branch**: `docs/specs-retroativas` | **Date**: 2026-09-24 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/001-extracao-features/spec.md`

**Note**: plano retroativo. Descreve o código que já existe em `master`; não
há Phase 0 (`research.md`), `contracts/` nem `quickstart.md`. O `tasks.md`
fica para a subtask 3 (validação com `/speckit.analyze`).

## Summary

A extração lê cada firmware com limite de bytes, calcula features
estatísticas, de strings ASCII e estruturais do Binwalk e grava uma tabela
com uma linha por arquivo (`firmware_id`, features e metadados `meta_*`),
sem executar o binário. O fluxo e o papel da etapa no pipeline estão em
`docs/PIPELINE.md`, §"1. Extração (núcleo compartilhado)".

## Technical Context

**Language/Version**: Python ≥ 3.9

**Primary Dependencies**: numpy, pandas, pyarrow, PyYAML, gensim (só via
`007-embeddings-doc2vec`), CLI externa `binwalk` (opcional)

**Storage**: arquivos: `dataset/processed/*.parquet` / `.csv`

**Testing**: pytest

**Target Platform**: Linux

**Project Type**: biblioteca + CLI (`extract-features`, em `pyproject.toml`
`[project.scripts]`)

**Performance Goals**: sem meta definida; o CLI registra tempo total e
médio por arquivo

**Constraints**: `max_bytes` de 5 MiB em `configs/feature_extraction.yaml`;
timeout do Binwalk de 60 s

**Scale/Scope**: 840 arquivos em `dataset/raw`

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

|Princípio|Resultado|Evidência|
|---|---|---|
|I. Somente análise estática|Passa|Só leitura de bytes e Binwalk em modo assinatura (`binwalk <arquivo>`, sem `-e`), sem execução do binário|
|II. Rótulo exclusivamente por CVE|Não se aplica|A extração não rotula; `meta_label` é metadado de path, não rótulo de treino|
|III. Sem vazamento|Passa|Guarda em `tests/test_pipeline_extraction.py::test_classifier_features_exclude_cve_and_identity_fields`; modo inferência em `tests/test_pipeline_cli.py::test_cli_without_label_from_path_zeroes_version`|
|IV. Modelos simples|Não se aplica|Sem modelo nesta etapa|
|V. Reprodutibilidade|Passa parcialmente|Config versionada e overrides na CLI existem. O determinismo entre processos não tem teste; lacuna registrada para a subtask 3|
|VI. Firmware não confiável|Violação herdada|`max_bytes` e lote tolerante a falhas existem, mas Binwalk ausente (log debug) ou encerrado com código de erro (sem log) resulta em features estruturais vazias sem registro no artefato. Ver Complexity Tracking|
|VII. Integridade científica|Passa|Todo FR tem módulo e teste abaixo ou aparece em "Sem verificação"; números medidos citam data e artefato|

## Project Structure

### Documentation (this feature)

```text
specs/001-extracao-features/
├── spec.md              # /speckit.specify + /speckit.clarify
├── plan.md              # este arquivo
├── data-model.md        # esquema do registro de features.parquet
└── checklists/
    └── requirements.md  # checklist de qualidade da spec
```

### Source Code (repository root)

```text
configs/
└── feature_extraction.yaml     # config versionada (max_bytes, feature.*, doc2vec.*)
pipeline/
└── feature_extraction.py       # config, extração por path, lote paralelo
scripts/
└── extract_features.py         # CLI extract-features: coleta de paths, meta_*, parquet/CSV
src/
├── feature_extraction.py       # FeatureVector: estatísticas, strings, documento
├── io_utils.py                 # read_binary com max_bytes, normalize_binary
└── features/
    ├── binwalk.py              # n_filesystems, fs_type, compression_type
    ├── statistics.py           # entropy, byte_mean, compress_ratio, variância por bloco
    └── strings.py              # strings ASCII com limites

tests/
├── test_binwalk_features.py
├── test_feature_vector.py
├── test_io_utils.py
├── test_pipeline_cli.py
├── test_pipeline_config.py
├── test_pipeline_extraction.py
├── test_statistics.py
└── test_strings.py
```

**Structure Decision**: estrutura de projeto único já existente. A fronteira
entre specs (módulos donos de cada uma) está no inventário
`.docs/brainstorming/inventario-modulos.md`; esta spec é dona só dos
módulos acima.

### FR → módulo → teste

|FR|Módulo|Teste|
|---|---|---|
|FR-001|`scripts/extract_features.py::gather_paths`|`test_pipeline_cli.py::test_cli_directory_input` (parcial)|
|FR-002|`pipeline/feature_extraction.py::load_pipeline_config`, `apply_overrides`|`test_pipeline_config.py::test_load_pipeline_config_defaults`, `::test_load_pipeline_config_with_overrides`; `test_pipeline_cli.py::test_cli_with_override`|
|FR-003|`src/io_utils.py::read_binary`; `pipeline/feature_extraction.py::extract_features_from_path`|`test_io_utils.py::test_read_binary_max_bytes_zero_returns_empty`, `::test_read_binary_missing_file_returns_empty_and_logs_warning`; `test_pipeline_extraction.py::test_extract_features_from_path_max_bytes_zero`, `::test_extract_features_from_path_empty_file`|
|FR-004|`pipeline/feature_extraction.py::extract_features_from_path`|`test_pipeline_extraction.py::test_extract_features_from_path_valid_file`|
|FR-005|`src/features/statistics.py`; `src/feature_extraction.py::combine_features`|`test_statistics.py` (9 testes)|
|FR-006|`src/features/strings.py`; `src/feature_extraction.py::extract_features`|`test_strings.py` (9 testes); `test_feature_vector.py::test_extract_features_exposes_limited_strings`|
|FR-007|`src/features/binwalk.py`; `pipeline/feature_extraction.py::_extract_binwalk_descriptions`|`test_binwalk_features.py` (11 testes); `test_pipeline_extraction.py::test_extract_features_with_mocked_binwalk`, `::test_extract_features_includes_binwalk_keys`|
|FR-008|`pipeline/feature_extraction.py::extract_features_from_path`|`test_pipeline_extraction.py::test_extract_features_includes_string_pattern_keys`|
|FR-009|`scripts/extract_features.py::main`|`test_pipeline_cli.py::test_cli_basic_file`, `::test_cli_csv_output`|
|FR-010|`scripts/extract_features.py::main`|`test_pipeline_cli.py::test_cli_without_label_from_path_zeroes_version`, `::test_cli_label_from_path`|
|FR-011|`pipeline/feature_extraction.py::extract_features_from_path`|`test_pipeline_extraction.py::test_classifier_features_exclude_cve_and_identity_fields`|
|FR-012|`pipeline/feature_extraction.py::extract_features_batch`|`test_pipeline_extraction.py::test_extract_features_batch_continues_on_error`, `::test_extract_features_batch_sequential_mode`, `::test_extract_features_batch_preserves_order_with_multiple_workers`, `::test_extract_features_batch_empty_list_returns_empty`|
|FR-013|`scripts/extract_features.py::main`|`test_pipeline_cli.py::test_cli_reports_elapsed_time`|

### Sem verificação

Partes de FR sem teste que as exercite:

- FR-001: filtro de extensões excluídas e entrada `.txt` com lista de paths.
- FR-003: leitura parcial com `max_bytes>0` (só `max_bytes=0` e arquivo
  ausente têm teste).
- FR-006: valor de `meta_truncated` no registro.
- FR-012: `--workers` via CLI (o lote paralelo é testado só pela função).

### Símbolos com requisito em outra spec

Ficam nos módulos desta spec, mas o requisito pertence a outra:

- `infer_brand_model_label_from_path` em `pipeline/feature_extraction.py`:
  004/FR-001, 004/FR-002, 004/FR-003, 004/FR-005, 004/FR-012 e
  004/FR-013.
- `_split_model_version` em `pipeline/feature_extraction.py`: 004/FR-004.
- `VERSION_SOURCE_*` em `pipeline/feature_extraction.py`: 004/FR-005.
- Regra "ambos ou nenhum" de `version`/`version_source` (`ValueError` em
  `extract_features_from_path`): 004/FR-013.
- Identidade inferida para todo arquivo e preservada no erro
  (`_process_path` e campos de identidade em `_build_error_result`, em
  `pipeline/feature_extraction.py`): 004/FR-014.
- Chamada a `scan_strings`, `scan_strings_findings`,
  `count_crypto_signatures`, `has_encrypted_sections`,
  `find_crypto_signatures`, `find_encrypted_sections` e o campo
  `PipelineResult.findings` em `pipeline/feature_extraction.py`:
  002/FR-001, 002/FR-014 e 002/FR-015.
- `--findings-output` em `scripts/extract_features.py`: 002/FR-016.
- `load_doc2vec_model`, `_init_worker` e a carga do modelo em
  `extract_features_batch` (`pipeline/feature_extraction.py`): 007/FR-007.
- Padrões `doc2vec.*` em `load_pipeline_config`
  (`pipeline/feature_extraction.py`): 007/FR-004.
- `doc2vec_used=False` em `_build_error_result`
  (`pipeline/feature_extraction.py`): 007/FR-009.
- `extract_features` em `src/feature_extraction.py`: 007/FR-002 e
  007/FR-008.
- Colunas `doc2vec_*` via `combine_features` em
  `src/feature_extraction.py`: 007/FR-008.
- `tokenize_document` em `src/features/strings.py`: 007/FR-002.

### Utilitários sem spec

- `src/cli_utils.py`: parse de overrides e coleta de paths, compartilhado
  pelos scripts. Sem regra de domínio.
- `scripts/reorganize_dataset.py` e `scripts/validate_dataset.py`: curadoria
  pontual do `dataset/raw`, com caminhos fixos, fora do pipeline
  reprodutível. O `validate_dataset.py` ainda lê o `labels.csv` v1.
- Marcadores de pacote: `pipeline/__init__.py`, `src/__init__.py`,
  `src/features/__init__.py`, `src/evidence/__init__.py`,
  `src/labeling/__init__.py`, `scripts/__init__.py` e `src/py.typed`.

## Complexity Tracking

|Violação|Por que existe|Alternativa|
|---|---|---|
|Princípio VI: Binwalk ausente (log debug) ou encerrado com código de erro (sem log) resulta em features estruturais vazias, sem coluna `meta_*` que registre a falha|Herdada do código em `master` (`_extract_binwalk_descriptions`)|Correção pendente registrada no `TODO.md`|
