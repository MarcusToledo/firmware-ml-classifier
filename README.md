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

> **`--label-from-path`**: para montar o dataset de treino, adicione essa flag aos comandos
> acima (ex.: `... --output dataset/processed/features.parquet --label-from-path`).
> O pipeline (`pipeline/feature_extraction.py`) já infere `brand`/`model`/`label` a partir do
> path `dataset/raw/<brand>/<model>/...`, mas `scripts/extract_features.py` **zera esses campos
> por padrão** (para não vazar rótulo em extrações de inferência/produção). Sem a flag,
> `meta_brand`/`meta_model` saem `None` em 100% das linhas, o que quebra silenciosamente o
> merge com o cache de CVE em `generate_labels.py` e impede qualquer firmware de ser
> classificado como `critico` (o sinal de CVE tem peso 0.45, o maior, e é o único caminho de
> escalonamento direto para `critico`).

Gerar cache de CVEs por fabricante/modelo (opcional, mas necessário para labels `critico`):
- `uv run python scripts/fetch_cves.py --features dataset/processed/features.parquet --output dataset/cve_cache.json`
- Usa a API pública da NVD v2.0; sem `NVD_API_KEY` no ambiente, o delay entre requisições é de
  6s (1s com a key). Pares já presentes no cache são pulados automaticamente (use `--force`
  para refazer). `--dry-run` lista os pares vendor/model sem fazer requisições.

Gerar labels de segurança a partir das features (+ CVEs, se disponíveis):
- `uv run python scripts/generate_labels.py --features dataset/processed/features.parquet --cves dataset/cve_cache.json --config configs/scoring.yaml --output dataset/labels.csv`
- Classifica cada firmware em `seguro` / `vulneravel` / `critico` combinando sinais de stats,
  strings suspeitas, binwalk e CVE (pesos em `configs/scoring.yaml`). `--dry-run` mostra a
  distribuição de classes sem salvar.

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
