# Quickstart: preparação do dataset de treino

Pré-requisitos: `001/FR-014`, `001/FR-016`, `004/FR-016`, `004/FR-017`,
`003/FR-014`, `005/FR-018` e `005/FR-026` implementados.

1. Unificar TP-Link (uma vez, FR-016):

   ```bash
   python scripts/reorganize_dataset.py --merge-vendor tplink:tp_link
   python scripts/reorganize_dataset.py --merge-vendor tplink:tp_link --execute
   ```

   Se falhar por modelo já existente em `tp_link/`, resolver à mão e
   rodar de novo. Depois, refazer a busca completa na NVD
   (`scripts/fetch_cves.py`, `003-busca-cve`), extrair as features e gerar
   os rótulos:

   ```bash
   python scripts/extract_features.py --input dataset/raw \
       --output dataset/processed/features_v2.parquet \
       --label-from-path --dataset-root dataset/raw
   python scripts/generate_labels.py \
       --features dataset/processed/features_v2.parquet \
       --cves dataset/cve_cache_v2.json
   ```

2. Preparar a tabela:

   ```bash
   python scripts/build_dataset.py
   ```

   Conferir no log o tamanho da entrada e da tabela, as features do vetor,
   as classes e as exclusões por motivo e fabricante.

3. Validar:

   ```bash
   python scripts/validate_dataset.py
   ```

4. Reprodutibilidade (SC-003): rodar o passo 2 de novo e comparar
   `training_table.parquet` e `training_table_exclusions.csv` com
   `cmp`; os metadados só diferem em `created_at`.
