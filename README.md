# Classificação de Firmware (TCC)

## Visão geral
Este repositório corresponde a um Trabalho de Conclusão de Curso (TCC)
de Engenharia de Software focado em classificação automatizada de
firmwares embarcados usando análise estática e aprendizado de máquina.

## Objetivos
- Classificar firmware por fabricante (supervisionado).
- Extrair features estatísticas de binários (tamanho, entropia, bytes).
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

Treinar Doc2Vec (treino separado):
- `python3 scripts/train_doc2vec.py --config configs/feature_extraction.yaml --input dataset/raw/`

Extrair features com embeddings:
- `python3 scripts/extract_features.py --config configs/feature_extraction.yaml --input dataset/raw/`

Inspecionar tokens usados no Doc2Vec:
- `python3 scripts/inspect_tokens.py --config configs/feature_extraction.yaml --input dataset/raw/ --limit 50 --max-docs 20`

Limite de leitura por firmware:
- configurado em `configs/feature_extraction.yaml` via `max_bytes`.

Testes:
- `python3 -m pytest`
- `python3 -m pytest tests/path::test_name`

