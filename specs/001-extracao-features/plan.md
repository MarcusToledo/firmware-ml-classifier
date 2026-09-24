# Implementation Plan: Extração estática de features

**Branch**: `docs/specs-retroativas` | **Date**: 2026-09-24 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/001-extracao-features/spec.md`

**Note**: plano retroativo. Descreve o código que já existe em `master`; não
há Phase 0 (`research.md`), `contracts/` nem `quickstart.md`. O `tasks.md` é
retroativo: registra a verificação de cada FR e cenário e as lacunas de teste.

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
├── spec.md                        # /speckit.specify + /speckit.clarify
├── plan.md                        # este arquivo
├── data-model.md                  # esquema do registro de features.parquet
├── tasks.md                       # verificação retroativa de FRs e cenários
└── checklists/
    ├── requirements.md            # checklist de qualidade da spec
    └── rastreabilidade.md         # checklist de rastreabilidade e testabilidade
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

### US → FR → módulo → teste

|FR|US|Módulo|Teste|
|---|---|---|---|
|FR-001|US1|`scripts/extract_features.py::gather_paths`|`test_pipeline_cli.py::test_cli_directory_input` (parcial)|
|FR-002|US1|`pipeline/feature_extraction.py::load_pipeline_config`, `apply_overrides`|`test_pipeline_config.py::test_load_pipeline_config_defaults`, `test_pipeline_config.py::test_load_pipeline_config_with_overrides`; `test_pipeline_cli.py::test_cli_with_override`|
|FR-003|US3|`src/io_utils.py::read_binary`; `pipeline/feature_extraction.py::extract_features_from_path`|`test_io_utils.py::test_read_binary_max_bytes_zero_returns_empty`, `test_io_utils.py::test_read_binary_missing_file_returns_empty_and_logs_warning`; `test_pipeline_extraction.py::test_extract_features_from_path_max_bytes_zero`, `test_pipeline_extraction.py::test_extract_features_from_path_empty_file` (parcial)|
|FR-004|US1|`pipeline/feature_extraction.py::extract_features_from_path`|`test_pipeline_extraction.py::test_extract_features_from_path_valid_file` (parcial)|
|FR-005|US4|`src/features/statistics.py`; `src/feature_extraction.py::combine_features`|`test_statistics.py::test_entropy_known_distribution`, `test_statistics.py::test_byte_mean_empty_returns_zero`, `test_statistics.py::test_compress_ratio_level_affects_output`, `test_statistics.py::test_entropy_variance_different_blocks`|
|FR-006|US4|`src/features/strings.py`; `src/feature_extraction.py::extract_features`|`test_strings.py::test_extract_ascii_strings_min_len`, `test_strings.py::test_extract_ascii_strings_max_string_len_truncates`, `test_strings.py::test_limit_strings_truncates`, `test_strings.py::test_strings_to_document_truncates`; `test_feature_vector.py::test_extract_features_exposes_limited_strings` (parcial)|
|FR-007|US4|`src/features/binwalk.py`; `pipeline/feature_extraction.py::_extract_binwalk_descriptions`|`test_binwalk_features.py::test_count_filesystems_matches`, `test_binwalk_features.py::test_detect_fs_type_returns_most_common`, `test_binwalk_features.py::test_detect_compression_first_match`; `test_pipeline_extraction.py::test_extract_features_with_mocked_binwalk`, `test_pipeline_extraction.py::test_extract_features_includes_binwalk_keys` (parcial)|
|FR-008|US4|`pipeline/feature_extraction.py::extract_features_from_path`|`test_pipeline_extraction.py::test_extract_features_includes_string_pattern_keys`, `test_pipeline_extraction.py::test_extract_features_includes_binwalk_keys` (parcial)|
|FR-009|US1, US2, US3|`scripts/extract_features.py::main`|`test_pipeline_cli.py::test_cli_basic_file`, `test_pipeline_cli.py::test_cli_csv_output`, `test_pipeline_cli.py::test_cli_directory_input` (parcial)|
|FR-010|US2|`scripts/extract_features.py::main`|`test_pipeline_cli.py::test_cli_without_label_from_path_zeroes_version`, `test_pipeline_cli.py::test_cli_label_from_path`, `test_pipeline_cli.py::test_cli_label_from_path_extracts_version` (parcial)|
|FR-011|US2|`pipeline/feature_extraction.py::extract_features_from_path`|`test_pipeline_extraction.py::test_classifier_features_exclude_cve_and_identity_fields`|
|FR-012|US1, US3|`pipeline/feature_extraction.py::extract_features_batch`|`test_pipeline_extraction.py::test_extract_features_batch_continues_on_error`, `test_pipeline_extraction.py::test_extract_features_batch_sequential_mode`, `test_pipeline_extraction.py::test_extract_features_batch_preserves_order_with_multiple_workers`, `test_pipeline_extraction.py::test_extract_features_batch_empty_list_returns_empty` (parcial)|
|FR-013|US1|`scripts/extract_features.py::main`|`test_pipeline_cli.py::test_cli_reports_elapsed_time`, `test_pipeline_cli.py::test_cli_basic_file` (parcial)|

### Sem verificação

Partes de FR sem teste que as exercite:

- FR-001: entrada `.txt`, filtro das extensões excluídas e arquivos ocultos.
- FR-003: leitura parcial com `max_bytes>0` e mensagens exatas nos metadados
  para arquivo vazio e limite não positivo.
- FR-004: valor de `firmware_id` como SHA256 exato do prefixo lido.
- FR-006: valor de `meta_truncated` no registro.
- FR-007: fallback 0/nulo quando o Binwalk está ausente, excede o timeout ou
  encerra com erro.
- FR-008: conjunto integrado completo das 11 features de strings, 2 features
  de Binwalk e colunas `doc2vec_*`.
- FR-009: cardinalidade da saída e esquema completo dos 14 metadados em
  parquet e CSV.
- FR-010: nulidade simultânea dos cinco metadados de identidade sem
  `--label-from-path`.
- FR-012: `--workers` via CLI (o lote paralelo é testado só pela função).
- FR-013: os cinco campos do log emitido para cada arquivo.

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
