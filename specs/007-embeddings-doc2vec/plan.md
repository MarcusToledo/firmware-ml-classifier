# Implementation Plan: Embeddings Doc2Vec

**Branch**: `docs/specs-retroativas` | **Date**: 2026-09-24 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/007-embeddings-doc2vec/spec.md`

**Note**: plano retroativo. Descreve o código que já existe em `master`; não há Phase 0 (`research.md`), `contracts/` nem `quickstart.md`. O `tasks.md` é retroativo: registra a verificação de cada FR e cenário e as lacunas de teste. FR-011 a FR-015 são `[Proposto, TickTick T06]`: aparecem na matriz sem módulo previsto e não têm task (regra do escopo restante para FR Proposto).

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
|VII. Integridade científica|Passa|Todo FR Implementado tem módulo e teste abaixo ou aparece em "Sem verificação"; FR-011 a FR-015 são Proposto, sem compromisso de implementação. `tests/test_doc2vec.py::test_infer_embedding_deterministic_same_seed_changes_with_different_seed` não é citado como evidência de FR: passa pelo motivo errado (spec, Edge Cases)|

## Project Structure

### Documentation (this feature)

```text
specs/007-embeddings-doc2vec/
├── spec.md                     # /speckit.specify + /speckit.clarify
├── plan.md                     # este arquivo
├── tasks.md                    # verificação retroativa de FRs e cenários
├── data-model.md               # models/doc2vec.model e colunas doc2vec_*
└── checklists/
    ├── requirements.md         # checklist de qualidade da spec
    └── rastreabilidade.md      # checklist de rastreabilidade e testabilidade
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

### US → FR → módulo → teste

|FR|US|Módulo|Teste|
|---|---|---|---|
|FR-001|US1, US3|`scripts/train_doc2vec.py::gather_paths`, `ALLOWED_EXTENSIONS`; `scripts/inspect_tokens.py::gather_paths`, `ALLOWED_EXTENSIONS`; `src/cli_utils.py::gather_paths`|—|
|FR-002|US1, US2, US3|`scripts/train_doc2vec.py::build_documents`; `scripts/inspect_tokens.py::extract_tokens`; `src/feature_extraction.py::extract_features`; `src/features/strings.py::tokenize_document`|`tests/test_strings.py::test_tokenize_document_basic` (parcial)|
|FR-003|US1|`scripts/train_doc2vec.py::build_documents`, `main`; `src/features/doc2vec.py::build_corpus`|`tests/test_doc2vec.py::test_build_corpus_preserves_doc_ids_and_tokens` (parcial)|
|FR-004|US1, US3|`src/features/doc2vec.py::Doc2VecConfig`; `pipeline/feature_extraction.py::load_pipeline_config`; `configs/feature_extraction.yaml` (`doc2vec.*`); `scripts/train_doc2vec.py::main`; `scripts/inspect_tokens.py::main`|`tests/test_pipeline_config.py::test_load_pipeline_config_defaults`, `tests/test_pipeline_config.py::test_load_pipeline_config_with_overrides`, `tests/test_pipeline_config.py::test_override_nested_doc2vec` (parcial)|
|FR-005|US1|`src/features/doc2vec.py::train_doc2vec`|`tests/test_doc2vec.py::test_train_doc2vec_enforces_workers_one`|
|FR-006|US1|`scripts/train_doc2vec.py::main`; `src/features/doc2vec.py::train_doc2vec`, `save_doc2vec`, `load_doc2vec`|`tests/test_doc2vec.py::test_train_doc2vec_model_has_expected_vector_size_and_docvecs`, `tests/test_doc2vec.py::test_save_load_roundtrip_preserves_config_and_infer_behavior` (parcial)|
|FR-007|US2|`pipeline/feature_extraction.py::load_doc2vec_model`, `_init_worker`, `extract_features_batch`|`tests/test_pipeline_config.py::test_null_model_path` (parcial)|
|FR-008|US2|`src/features/doc2vec.py::infer_embedding`; `src/feature_extraction.py::extract_features`, `combine_features`|`tests/test_doc2vec.py::test_infer_embedding_empty_tokens_returns_zero_finite_vector`, `tests/test_doc2vec.py::test_infer_embedding_oov_tokens_finite` (parcial)|
|FR-009|US2|`pipeline/feature_extraction.py::extract_features_from_path`, `_build_error_result`|`tests/test_pipeline_extraction.py::test_extract_features_from_path_valid_file` (parcial)|
|FR-010|US3|`scripts/inspect_tokens.py::main`, `extract_tokens`|—|
|FR-011 [Proposto, TickTick T06]|—|—|— (Proposto: sem task)|
|FR-012 [Proposto, TickTick T06]|—|—|— (Proposto: sem task)|
|FR-013 [Proposto, TickTick T06]|—|—|— (Proposto: sem task)|
|FR-014 [Proposto, TickTick T06]|—|—|— (Proposto: sem task)|
|FR-015 [Proposto, TickTick T06]|—|—|— (Proposto: sem task)|

### Sem verificação

Partes de FR sem teste que as exercite:

- FR-001: os três tipos de entrada, a recursão e os filtros de nome e
  extensão nos CLIs de treino e inspeção.
- FR-002: a aplicação conjunta dos limites de leitura, strings e documento
  no treino e na inspeção; só a divisão por espaço em branco tem teste.
- FR-003: o SHA256 dos bytes lidos como tag, o pulo de arquivo vazio,
  ilegível ou sem tokens e o erro de corpus vazio; só a montagem do corpus
  a partir de pares prontos tem teste.
- FR-004: os padrões `doc2vec.*` além de `vector_size` e `seed`, e
  `--config`/`--override` nos CLIs de treino e inspeção.
- FR-006: a precedência `--output` > `doc2vec.model_path` >
  `models/doc2vec.model`, a criação de diretórios, a sobrescrita e o log.
- FR-007: o warning de modelo ausente e a carga única por processo; só a
  leitura de `model_path: null` tem teste.
- FR-008: a extração integrada sem e com modelo e as colunas
  `doc2vec_*`; só a inferência isolada vazia e com tokens OOV tem teste.
- FR-009: `meta_doc2vec_used=True` com modelo carregado, inclusive quando
  o documento não tem tokens; só o caso sem modelo tem teste.
- FR-010: o limite de documentos, o preview, o log e o pulo de firmware
  vazio na inspeção.

A verificação de determinismo
`tests/test_doc2vec.py::test_infer_embedding_deterministic_same_seed_changes_with_different_seed`
existe, mas não cobre nenhum FR: o `vec3` difere de `vec1` porque o estado
`model.random` avançou, não por causa de `seed=43` (parecer do oracle;
T06).

### Símbolos com requisito em outra spec

Nenhum.

## Complexity Tracking

|Violação|Por que existe|Alternativa|
|---|---|---|
|Princípio III: o Doc2Vec é ajustado sobre toda a entrada, sem partição de treino nem fold|Herdada do código em `master` (`scripts/train_doc2vec.py::main`). A violação só tem efeito se `doc2vec_*` entrar num modelo; `001/FR-018` (Planejado, TickTick T07) desliga o Doc2Vec por padrão, o princípio I o mantém fora do modelo reportado, e as specs de preparação (008) e de avaliação (011) terão FR Planejado que exclui `doc2vec_*` e o braço Doc2Vec da ablation enquanto a T06 for Proposto (decisão do pesquisador no analyze de 2026-09-25)|FR-011 e FR-013 [Proposto, TickTick T06]; devem ser promovidos a Planejado antes de qualquer uso de `doc2vec_*` num modelo|
|Princípio V: inferência depende da ordem de chamada e de `PYTHONHASHSEED`; `doc2vec.seed` não a afeta; o modelo não guarda a partição de treino|Herdada do código em `master` (`src/features/doc2vec.py::infer_embedding`, `set_global_seed`); mesmo alcance da linha acima|FR-012 e FR-013 [Proposto, TickTick T06]; mesma condição de promoção|
