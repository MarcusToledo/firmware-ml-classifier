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
Instalar dependências:
- `python3 -m pip install -r requirements.txt`

Instalar em modo editável (habilita comandos de CLI):
- `python3 -m pip install -e .`

Treinar Doc2Vec (treino separado):
- `python3 scripts/train_doc2vec.py --config configs/feature_extraction.yaml --input dataset/raw/`

Treinar Doc2Vec via CLI instalada:
- `train-doc2vec --config configs/feature_extraction.yaml --input dataset/raw/`

Extrair features com embeddings:
- `python3 scripts/extract_features.py --config configs/feature_extraction.yaml --input dataset/raw/ --output dataset/processed/features.parquet`

Extrair features via CLI instalada:
- `extract-features --config configs/feature_extraction.yaml --input dataset/raw/ --output dataset/processed/features.parquet`

Inspecionar tokens usados no Doc2Vec:
- `python3 scripts/inspect_tokens.py --config configs/feature_extraction.yaml --input dataset/raw/ --limit 50 --max-docs 20`

Inspecionar tokens via CLI instalada:
- `inspect-tokens --config configs/feature_extraction.yaml --input dataset/raw/ --limit 50 --max-docs 20`

Limite de leitura por firmware:
- configurado em `configs/feature_extraction.yaml` via `max_bytes`.

Testes:
- `python3 -m pytest`
- `python3 -m pytest tests/path::test_name`

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
