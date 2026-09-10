# Classificação de Firmware (TCC)

## Visão geral
Este repositório corresponde a um Trabalho de Conclusão de Curso (TCC)
de Engenharia de Software focado em classificação automatizada de
firmwares embarcados usando análise estática e aprendizado de máquina.

## Objetivos
- Classificar firmware por fabricante (supervisionado).
- Extrair features estatisticas de binarios (entropia, media de bytes, compress_ratio).
- Extrair strings ASCII e embeddings Doc2Vec para features semânticas.
- Treinar modelos Extra Trees (principal) e Random Forest (baseline).

## Pipeline experimental
1. Coleta e organização de dataset por fabricante.
2. Extração de features estatísticas e strings.
3. Treino de embeddings Doc2Vec (DM/DBOW) por firmware.
4. Treino e avaliação de modelos supervisionados.
5. Geração de métricas e relatórios.

## Como executar
Instalar dependências (cria `.venv` e resolve a partir de `pyproject.toml`/`uv.lock`):
- `uv sync`

Instalar incluindo ferramentas de desenvolvimento (pytest, ruff, black, mypy, pre-commit):
- `uv sync --extra dev`

O modo editável e os comandos de CLI (`train-doc2vec`, `extract-features`, `inspect-tokens`, `generate-labels`) já ficam disponíveis dentro do `.venv` após o `uv sync`, sem passo separado de instalação.

Treinar Doc2Vec (treino separado):
- `uv run python scripts/train_doc2vec.py --config configs/feature_extraction.yaml --input dataset/raw/`

Treinar Doc2Vec via CLI instalada:
- `uv run train-doc2vec --config configs/feature_extraction.yaml --input dataset/raw/`

Extrair features com embeddings:
- `uv run python scripts/extract_features.py --config configs/feature_extraction.yaml --input dataset/raw/ --output dataset/processed/features.parquet`

Extrair features via CLI instalada:
- `uv run extract-features --config configs/feature_extraction.yaml --input dataset/raw/ --output dataset/processed/features.parquet`

Inspecionar tokens usados no Doc2Vec:
- `uv run python scripts/inspect_tokens.py --config configs/feature_extraction.yaml --input dataset/raw/ --limit 50 --max-docs 20`

Inspecionar tokens via CLI instalada:
- `uv run inspect-tokens --config configs/feature_extraction.yaml --input dataset/raw/ --limit 50 --max-docs 20`

Limite de leitura por firmware:
- configurado em `configs/feature_extraction.yaml` via `max_bytes`.

Testes (requer `uv sync --extra dev`):
- `uv run pytest`
- `uv run pytest tests/path::test_name`

## Qualidade de codigo

Instalar ferramentas de desenvolvimento:
- `uv sync --extra dev`

Configurar pre-commit:
- `uv run pre-commit install`

Rodar manualmente:
- `uv run ruff check .`
- `uv run black .`
- `uv run mypy src/`

Atualizar/travar dependências:
- `uv add <pacote>` — adiciona dependência de produção (atualiza `pyproject.toml` e `uv.lock`).
- `uv add --optional dev <pacote>` — adiciona dependência de desenvolvimento.
- `uv remove <pacote>` — remove dependência.
- `uv lock --upgrade` — atualiza versões travadas no `uv.lock` sem mudar o `pyproject.toml`.

## API Interna

src/io_utils:
- `read_binary`: leitura segura de binarios com limite opcional.
- `normalize_binary`: validacao de tipo para bytes.

src/features/statistics:
- `shannon_entropy`, `byte_mean`, `compress_ratio`: features estatisticas.

src/features/strings:
- `extract_ascii_strings`: extracao de strings ASCII.
- `limit_strings`, `strings_to_document`, `tokenize_document`: processamento de texto.

src/features/doc2vec:
- `build_corpus`, `train_doc2vec`: treino de Doc2Vec.
- `infer_embedding`: inferencia de embeddings.
- `save_doc2vec`, `load_doc2vec`: persistencia de modelos.

src/feature_extraction:
- `extract_features`: extracao completa (stats + embedding).
- `combine_features`: conversao para dicionario plano.

pipeline/feature_extraction:
- `load_pipeline_config`: carregamento de YAML com overrides.
- `extract_features_from_path`, `extract_features_batch`: pipeline de extracao.
