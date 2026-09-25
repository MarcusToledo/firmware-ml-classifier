# Data Model: Partição agrupada

## Entradas

|Entrada|Origem|Uso|
|---|---|---|
|`training_table.parquet`|`008/FR-013`|`firmware_id`, `security_level`|
|`training_table_provenance.jsonl`|`008/FR-014`|aliases (fabricante, modelo) dos `firmware_id` com `in_table=true`|
|`training_table.meta.json`|`008/FR-013`|SHA256 da tabela e da proveniência, em `outputs` (FR-001)|

## `folds_grouped.parquet` e `folds_random.parquet`

Uma linha por (repetição, fold, `firmware_id`), ordenadas nessa ordem.

|Coluna|Tipo|Regra|
|---|---|---|
|`repeat`|int|0 a `len(seeds)-1`|
|`seed`|int|seed da repetição|
|`fold`|int|0 a `n_splits-1`|
|`firmware_id`|texto|todos os `firmware_id` da tabela em cada (repetição, fold)|
|`role`|texto|`train` ou `test`|
|`group`|texto|só em `folds_grouped`: `g:` + menor `firmware_id` do componente (determinístico, FR-002)|

Chave de modelo (FR-002): `<fabricante>/<modelo>` em minúsculas, sem `-`,
`_` e espaços (ex.: `asus/rt-n13u` e `asus/rtn13u` → `asus/rtn13u`).

## `folds_grouped.meta.json` e `folds_random.meta.json`

|Campo|Conteúdo|
|---|---|
|`scheme`|`grouped` ou `random`|
|`purpose`|`principal` (grouped) ou `diagnostico` (random)|
|`config`|configuração efetiva, com overrides|
|`group_rule`|`componente_firmware_id_modelo` ou `nenhum`|
|`n_splits`, `seeds`|da configuração efetiva; repetições = `len(seeds)`|
|`inputs`|SHA256 da tabela e da proveniência (iguais aos `outputs` da `008`)|
|`folds_sha256`|SHA256 do parquet de folds|
|`n_firmware_id`, `n_groups`, `max_group_size`|contagens|
|`per_fold`|por (repetição, fold): contagem por classe e por fabricante em treino e teste (uma vez em cada fabricante dos aliases)|
|`test_folds_missing_class`|lista de (repetição, fold, classes ausentes)|
|`commit`, `created_at`|`created_at` é o único campo que muda entre execuções iguais|
