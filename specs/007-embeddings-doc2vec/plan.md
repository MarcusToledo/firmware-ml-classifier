# Implementation Plan: Embeddings Doc2Vec

**Branch**: `docs/specs-retroativas` | **Date**: 2026-09-24 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/007-embeddings-doc2vec/spec.md`

**Note**: plano retroativo. Descreve o código que já existe em `master`; não
há Phase 0 (`research.md`), `contracts/` nem `quickstart.md`. O `tasks.md`
fica para a subtask 3 (validação com `/speckit.analyze`).

## Summary

O treino monta um documento de strings por firmware, com os limites da
extração, treina um Doc2Vec com parâmetros de `doc2vec.*` e grava o modelo;
a extração carrega esse modelo e grava um vetor `doc2vec_*` por firmware,
zerado quando não há modelo. O papel da etapa no pipeline está em
`docs/PIPELINE.md`, §"1. Extração (núcleo compartilhado)"; o Doc2Vec é
variante experimental fora do modelo reportado (constituição, princípio I).

## Technical Context

**Language/Version**: Python ≥ 3.9

**Primary Dependencies**: gensim (`>=4.2` em `pyproject.toml`; 4.4.0 no
`.venv`), numpy, PyYAML (via configuração de `001-extracao-features`,
`001/FR-002`)

**Storage**: arquivo `models/doc2vec.model` (formato `save` do gensim);
colunas `doc2vec_*` em `dataset/processed/*.parquet`, gravadas pela 001

**Testing**: pytest

**Target Platform**: Linux

**Project Type**: biblioteca + CLIs `train-doc2vec` e `inspect-tokens` (em
`pyproject.toml` `[project.scripts]`)

**Performance Goals**: sem meta definida

**Constraints**: `doc2vec.workers=1` obrigatório no treino; leitura e
strings limitadas pela configuração de extração (`max_bytes` de 5 MiB,
`max_strings` 2000, `max_doc_chars` 200000)

**Scale/Scope**: 774 arquivos candidatos ao treino e 840 à extração em
`dataset/raw` (medido em 2026-09-24)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

|Princípio|Resultado|Evidência|
|---|---|---|
|I. Somente análise estática|Passa|Treino, inferência e inspeção usam só strings ASCII lidas do binário (`scripts/train_doc2vec.py::build_documents`, `src/feature_extraction.py::extract_features`). O embedding é variante experimental; não há modelo reportado que o consuma hoje|
|II. Rótulo exclusivamente por CVE|Não se aplica|O Doc2Vec não rotula nem lê cache de CVE|
|III. Sem vazamento|Violação herdada|`scripts/train_doc2vec.py::main` ajusta o modelo sobre toda a entrada, sem partição de treino. Ver Complexity Tracking|
|IV. Modelos simples|Não se aplica|O Doc2Vec é transformador de features, não classificador|
|V. Reprodutibilidade|Violação herdada|Parâmetros versionados e `workers=1` no treino (`tests/test_doc2vec.py::test_train_doc2vec_enforces_workers_one`), mas a inferência depende da ordem de chamada e de `PYTHONHASHSEED`, e o modelo não guarda a partição de treino (`src/features/doc2vec.py::infer_embedding`; `.docs/brainstorming/parecer-doc2vec-oracle.md`). Ver Complexity Tracking|
|VI. Firmware não confiável|Passa parcialmente|Leitura com `max_bytes`; arquivo vazio e sem tokens pulado com warning no treino; ausência de modelo visível em `meta_doc2vec_used` (`pipeline/feature_extraction.py::extract_features_from_path`). Documento sem tokens gera vetor zero com `meta_doc2vec_used=True`, sem marca na linha|
|VII. Integridade científica|Passa|Todo FR tem módulo e teste abaixo ou aparece em "Sem verificação". `tests/test_doc2vec.py::test_infer_embedding_deterministic_same_seed_changes_with_different_seed` não é citado como evidência de FR: passa pelo motivo errado (spec, Edge Cases)|

## Project Structure

### Documentation (this feature)

```text
specs/007-embeddings-doc2vec/
├── spec.md              # /speckit.specify + /speckit.clarify
├── plan.md              # este arquivo
├── data-model.md        # models/doc2vec.model e colunas doc2vec_*
└── checklists/
    └── requirements.md  # checklist de qualidade da spec
```

### Source Code (repository root)

```text
scripts/
├── inspect_tokens.py           # CLI inspect-tokens: tokens por firmware no log
└── train_doc2vec.py            # CLI train-doc2vec: corpus, treino, gravação do modelo
src/
└── features/
    └── doc2vec.py              # Doc2VecConfig, corpus, treino, inferência, save/load

tests/
└── test_doc2vec.py
```

**Structure Decision**: estrutura de projeto único já existente. A fronteira
entre specs está no inventário `.docs/brainstorming/inventario-modulos.md`;
esta spec é dona só dos módulos acima. Os símbolos da 001 que carregam
requisito desta spec aparecem na tabela abaixo com o módulo real.

### FR → módulo → teste

|FR|Módulo|Teste|
|---|---|---|
|FR-001|`scripts/train_doc2vec.py::gather_paths`, `ALLOWED_EXTENSIONS`; `scripts/inspect_tokens.py::gather_paths`, `ALLOWED_EXTENSIONS`; `src/cli_utils.py::gather_paths`|nenhum (ver "Sem verificação")|
|FR-002|`scripts/train_doc2vec.py::build_documents`; `scripts/inspect_tokens.py::extract_tokens`; `src/feature_extraction.py::extract_features`; `src/features/strings.py::tokenize_document`|`test_strings.py::test_tokenize_document_basic` (parcial)|
|FR-003|`scripts/train_doc2vec.py::build_documents`, `main`; `src/features/doc2vec.py::build_corpus`|`test_doc2vec.py::test_build_corpus_preserves_doc_ids_and_tokens` (parcial)|
|FR-004|`src/features/doc2vec.py::Doc2VecConfig`; `pipeline/feature_extraction.py::load_pipeline_config`; `configs/feature_extraction.yaml` (`doc2vec.*`); `scripts/train_doc2vec.py::main`; `scripts/inspect_tokens.py::main`|`test_pipeline_config.py::test_load_pipeline_config_defaults`, `::test_load_pipeline_config_with_overrides`, `::test_override_nested_doc2vec` (parcial)|
|FR-005|`src/features/doc2vec.py::train_doc2vec`|`test_doc2vec.py::test_train_doc2vec_enforces_workers_one`|
|FR-006|`scripts/train_doc2vec.py::main`; `src/features/doc2vec.py::train_doc2vec`, `save_doc2vec`, `load_doc2vec`|`test_doc2vec.py::test_train_doc2vec_model_has_expected_vector_size_and_docvecs`, `::test_save_load_roundtrip_preserves_config_and_infer_behavior` (parcial)|
|FR-007|`pipeline/feature_extraction.py::load_doc2vec_model`, `_init_worker`, `extract_features_batch`|`test_pipeline_config.py::test_null_model_path` (parcial)|
|FR-008|`src/features/doc2vec.py::infer_embedding`; `src/feature_extraction.py::extract_features`, `combine_features`|`test_doc2vec.py::test_infer_embedding_empty_tokens_returns_zero_finite_vector`, `::test_infer_embedding_oov_tokens_finite` (parcial)|
|FR-009|`pipeline/feature_extraction.py::extract_features_from_path`, `_build_error_result`|`test_pipeline_extraction.py::test_extract_features_from_path_valid_file` (parcial)|
|FR-010|`scripts/inspect_tokens.py::main`, `extract_tokens`|nenhum (ver "Sem verificação")|

### Sem verificação

Partes de FR sem teste que as exercite:

- FR-001: inteiro. Nenhum teste chama os filtros de extensão do treino e da
  inspeção nem `src/cli_utils.py::gather_paths`.
- FR-002: os limites de leitura e de strings aplicados no treino e na
  inspeção (só a divisão por espaço em branco tem teste).
- FR-003: tag igual ao SHA256 dos bytes lidos, pulo de arquivo vazio ou sem
  tokens e o erro de corpus vazio (só a montagem do corpus a partir de
  pares prontos tem teste).
- FR-004: padrões `doc2vec.*` além de `vector_size` e `seed`, e
  `--config`/`--override` nos CLIs de treino e de inspeção.
- FR-006: precedência `--output` > `doc2vec.model_path` >
  `models/doc2vec.model` e criação de diretórios.
- FR-007: warning e carga do modelo por processo; só a leitura de
  `model_path: null` tem teste.
- FR-008: vetor zero sem modelo e inferência com modelo dentro da
  extração; as colunas `doc2vec_*` não são conferidas em nenhum teste de
  extração.
- FR-009: `meta_doc2vec_used=True` com modelo carregado.
- FR-010: inteiro.

A verificação de determinismo
`test_doc2vec.py::test_infer_embedding_deterministic_same_seed_changes_with_different_seed`
existe, mas não cobre nenhum FR: o `vec3` difere de `vec1` porque o estado
`model.random` avançou, não por causa de `seed=43` (parecer do oracle;
T06).

### Símbolos com requisito em outra spec

Nenhum.

## Complexity Tracking

|Violação|Por que existe|Alternativa|
|---|---|---|
|Princípio III: o Doc2Vec é ajustado sobre toda a entrada, sem partição de treino nem fold|Herdada do código em `master` (`scripts/train_doc2vec.py::main`); o treino do classificador e os splits ainda não existem|Treino por fold registrado na T06 (Proposto); até lá, `doc2vec_*` fica fora do modelo reportado (princípio I; T07 desliga por padrão)|
|Princípio V: inferência depende da ordem de chamada e de `PYTHONHASHSEED`; `doc2vec.seed` não a afeta; o modelo não guarda a partição de treino|Herdada do código em `master` (`src/features/doc2vec.py::infer_embedding`, `set_global_seed`)|Reiniciar `model.random` antes de cada inferência e exigir `PYTHONHASHSEED`, registrados na T06 (Proposto)|
