# Classificação de Firmware (TCC)

## Visão geral
Este repositório corresponde a um Trabalho de Conclusão de Curso (TCC)
de Engenharia de Software focado em classificação automatizada de
firmwares embarcados usando análise estática e aprendizado de máquina.

## Objetivos
- Classificar firmwares por classe de vulnerabilidade conhecida: `sem_cve_conhecida`,
  `cve_conhecida` ou `cve_critica`. A ausência de CVE conhecida não prova segurança.
- Gerar rótulos apenas a partir do cache de CVE consultado por fabricante/modelo.
- Extrair features estatísticas, strings ASCII e evidências de segurança, sem incluir
  fabricante/modelo nem campos CVE no vetor do classificador. O Doc2Vec existe no
  código, mas fica fora do núcleo e da entrega mínima do TCC.
- Comparar Extra Trees (modelo principal), Random Forest (baseline ML) e o
  baseline determinístico de regras de `src/scoring.py`. A escolha dos modelos
  ainda está a definir.

## Pipeline experimental
1. Organizar o dataset e preservar fabricante/modelo como metadados de consulta.
2. Extrair features estatísticas, strings, evidências estruturadas e Binwalk.
3. (Fora da entrega mínima) Treinar embeddings Doc2Vec (DM/DBOW) por firmware.
4. Consultar CVEs por fabricante/modelo e gerar rótulos em etapa separada.
5. Treinar e avaliar os modelos supervisionados com rótulos CVE, sem vazamento.
6. Gerar métricas e relatórios reprodutíveis.

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

Extrair features (Doc2Vec desligado por padrão, sem colunas `doc2vec_*`):
- `uv run python scripts/extract_features.py --config configs/feature_extraction.yaml --input dataset/raw/ --output dataset/processed/features.parquet`

Extrair features com embeddings (requer `models/doc2vec.model`):
- `uv run python scripts/extract_features.py --config configs/feature_extraction.yaml --input dataset/raw/ --output dataset/processed/features.parquet --override doc2vec.enabled=true`

Extrair features via CLI instalada:
- `uv run extract-features --config configs/feature_extraction.yaml --input dataset/raw/ --output dataset/processed/features.parquet`

> **`--findings-output`**: grava os achados de segurança estruturados (`SecurityFinding`)
> em JSONL, um por linha, correlacionáveis ao `features.parquet` via `firmware_id` (ex.:
> `... --findings-output dataset/processed/findings.jsonl`). Opcional, sem essa flag,
> os achados são calculados mas descartados, só as contagens/flags (`count_*`/`has_*`)
> vão para o `features.parquet`.

> **`--label-from-path`**: para montar o dataset de treino, adicione essa flag aos comandos
> acima (ex.: `... --output dataset/processed/features.parquet --label-from-path`).
> O pipeline infere `brand`/`model` a partir do caminho
> `dataset/raw/<brand>/<model>/...`, mas o CLI omite esses metadados por padrão.
> A flag é necessária para consultar CVEs. Sem metadados ou sem entrada no cache,
> `generate-labels` falha com contexto; não inventa um rótulo negativo.

Gerar cache de CVEs por fabricante/modelo (obrigatório para rotulagem):
- `uv run python scripts/fetch_cves.py --features dataset/processed/features.parquet`
- Sem `--output`, grava `dataset/processed/cve_cache_v2.json` e
  `dataset/processed/cve_cache_v2.meta.json`; entrada com schema antigo exige `--force`.
- Usa a API pública da NVD v2.0; sem `NVD_API_KEY` no ambiente, o delay entre requisições é de
  6s (1s com a key). Pares já presentes no cache são pulados automaticamente (use `--force`
  para refazer). `--dry-run` lista os pares vendor/model sem fazer requisições.

Gerar rótulos a partir do cache de CVEs:
- `uv run python scripts/generate_labels.py --features dataset/processed/features.parquet --cves dataset/processed/cve_cache_v2.json`
- Sem `--output`, grava `dataset/processed/labels_v2.csv`. Ao lado da tabela ficam
  `<nome>_aliases.jsonl` (aliases e CVEs aplicáveis/indeterminadas por alias) e
  `<nome>.meta.json` (limiar, SHA256 das entradas, commit do código e data).
- `--critical-cvss` ajusta o limiar crítico (padrão: 9.0); `--dry-run` mostra a
  distribuição sem salvar. As features são lidas apenas para obter IDs e metadados;
  a tabela precisa de `meta_version_source` e o cache precisa de `schema_version: 3`
  com `fetched_at`.
- O cache é consultado por fabricante/modelo; a versão do firmware é filtrada na
  rotulagem, e CVEs cuja aplicabilidade não se decide ficam indeterminadas.

Montar a tabela de treino:
- `uv run python scripts/build_dataset.py` (ou `uv run build-dataset`); lê
  `configs/dataset.yaml` e aceita `--features`, `--labels`, `--output-dir` e
  `--override chave=valor`.
- Junta `features_v2.parquet` e só `security_level` de `labels_v2.csv` por
  `firmware_id`; exclui IDs com falha de extração, firmware de terceiros ou rótulo
  `indeterminado`; troca `fs_type`/`compression_type` por one-hot de lista fixa.
  Interrompe sem gravar em estado transitório ou desconhecido, IDs sem par ou
  `features_sha256` divergente do `labels_v2.meta.json`.
- Grava em `dataset/processed/`: `training_table.parquet`,
  `training_table_exclusions.csv` (motivos e fabricantes),
  `training_table_provenance.jsonl` (aliases por ID) e `training_table.meta.json`
  (SHA256 de entradas e saídas, colunas do vetor, contagens, commit).
- `uv run python scripts/validate_dataset.py` (ou `uv run validate-dataset`) confere
  esses artefatos (IDs únicos, vetor sem colunas proibidas ou de texto, classes,
  hashes, colunas) e lista firmwares de `dataset/raw/` ausentes das features.

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

src/evidence:
- `SecurityFinding`: achado auditável com origem, contexto, confiança e detector.
- `scan_strings_findings`: achados em strings ASCII já extraídas.
- `find_crypto_signatures`, `find_encrypted_sections`: achados de Binwalk.

src/labeling/cve_labels:
- `label_from_cve_stats`: converte estatísticas CVE externas em classe de treino.

src/scoring:
- `score_firmware`: baseline determinístico de comparação, sem campos CVE.

src/feature_extraction:
- `extract_features`: extracao completa (stats + embedding).
- `combine_features`: conversao para dicionario plano.

pipeline/feature_extraction:
- `load_pipeline_config`: carregamento de YAML com overrides.
- `extract_features_from_path`, `extract_features_batch`: pipeline de extracao.
