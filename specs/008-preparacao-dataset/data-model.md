# Data Model: Preparação do dataset de treino

Todos os artefatos ficam em `dataset/processed/` (FR-013, FR-014). Linhas
ordenadas por `firmware_id`.

## Entradas

|Entrada|Origem|Colunas lidas|
|---|---|---|
|Tabela de features|`001-extracao-features` (`dataset/processed/features_v2.parquet`)|`firmware_id`, colunas de feature (inclusive de `012`), `meta_path`, `meta_brand`, `meta_model`, `meta_read_ok`, `meta_binwalk_status` (`001/FR-014`), `meta_unpack_status` (`001/FR-016`), `meta_third_party` (`004/FR-017`)|
|Tabela de rótulos|`005/FR-018` (`dataset/processed/labels_v2.csv`)|`firmware_id`, `security_level`|
|Metadados da rotulagem|`005/FR-018` (`labels_v2.meta.json`)|SHA256 de `--features`, conferido contra o da tabela de features (FR-001)|

Colunas de feature são as que não começam com `meta_` e não são
`firmware_id`. Ausência de `meta_binwalk_status`, `meta_unpack_status` ou
`meta_third_party` é erro (FR-001), assim como `firmware_id` nulo (FR-002).

## `training_table.parquet`

|Coluna|Tipo|Regra|
|---|---|---|
|`firmware_id`|texto|chave; fora do vetor|
|colunas numéricas e booleanas de feature|como na entrada|sem escala (FR-012); constantes mantidas (FR-009)|
|`fs_type__<categoria>`|int 0/1|`squashfs`, `jffs2`, `cramfs`, `ubifs`, `outro`, `ausente` (FR-010)|
|`compression_type__<categoria>`|int 0/1|`lzma`, `gzip`, `xz`, `lzo`, `outro`, `ausente` (FR-010)|
|`security_level`|texto|`sem_cve_conhecida`, `cve_conhecida` ou `cve_critica`; alvo|

Não entram: `meta_*`, `doc2vec_*`, `fs_type`, `compression_type` (texto),
e colunas da tabela de rótulos além de `security_level` (FR-003, FR-004).
Estado atual (2026-09-25), sem `012`: 18 colunas numéricas e booleanas +
12 one-hot = 30 colunas no vetor.

## `training_table_exclusions.csv`

|Coluna|Tipo|Regra|
|---|---|---|
|`firmware_id`|texto|um por linha|
|`reasons`|texto|motivos separados por `;`, em ordem fixa: `falha_extracao`, `terceiros`, `indeterminado` (FR-008)|
|`vendors`|texto|fabricantes distintos dos aliases, ordenados, separados por `;`|

## `training_table_provenance.jsonl`

Uma linha por `firmware_id` da tabela e das exclusões (FR-014):

```json
{"firmware_id": "…", "in_table": true,
 "aliases": [{"meta_path": "tp_link/archer_c7/…", "vendor": "tp_link", "model": "archer_c7"}]}
```

Aliases ordenados por `meta_path`.

## `training_table.meta.json`

|Campo|Conteúdo|
|---|---|
|`inputs`|caminho e SHA256 da tabela de features e da de rótulos|
|`outputs`|SHA256 da tabela, das exclusões e da proveniência|
|`commit`|commit do código|
|`config`|configuração efetiva, com overrides|
|`columns_input`|colunas de feature da entrada|
|`columns_vector`|colunas do vetor, na ordem da tabela|
|`column_changes`|por coluna removida ou transformada: motivo (`doc2vec_t06_proposto`, `texto_one_hot`)|
|`constant_columns`|colunas do vetor constantes nas linhas da tabela gravada (FR-009)|
|`counts`|entrada (linhas, `firmware_id`), tabela, por classe, por motivo, por fabricante, `firmware_id` com mais de um fabricante, proporção de `indeterminado` por fabricante|
|`created_at`|data da execução; único campo que muda entre execuções iguais|

## `configs/tplink_merge_map.csv`

|Coluna|Regra|
|---|---|
|`old_path`|relativo a `dataset/raw/`, sob `tplink/`|
|`new_path`|sob `tp_link/`, com `_` trocado por `-` no nome do modelo; nome do arquivo igual|
|`sha256`|do arquivo; igual antes e depois (SC-006)|
