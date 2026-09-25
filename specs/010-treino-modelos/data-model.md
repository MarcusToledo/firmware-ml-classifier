# Data Model: Treino de modelos e baselines

## `configs/training.yaml`

|Chave|Valor|
|---|---|
|`models.extra_trees`, `models.random_forest`|`n_estimators: 500`, `max_features: sqrt`, `min_samples_leaf: 1`, `max_depth: null`, `n_jobs: 1`|
|`class_weight`|`balanced`|
|`experiments.principal`|alvo `security_level` (3 classes)|
|`experiments.binario`|`sem_cve_conhecida` → `sem_cve_conhecida`; `cve_conhecida`, `cve_critica` → `com_cve`|
|`output_dir`|`models/runs`|

## `models/runs/<run_id>/predictions.parquet`

Uma linha por (repetição, fold, `firmware_id` do teste).

|Coluna|Tipo|
|---|---|
|`repeat`, `fold`|int|
|`firmware_id`|texto|
|`y_true`, `y_pred`|texto|
|`proba__<classe>`|float, uma coluna por classe do experimento; 0 para classe ausente no treino do fold; 1/0 no majoritário e no `score_firmware`|
|`purpose`|texto, igual ao de `run.meta.json`|

## `models/runs/<run_id>/run.meta.json`

|Campo|Conteúdo|
|---|---|
|`run_id`|SHA256 de modelo, experimento, esquema, colunas ordenadas, configuração efetiva, configuração da `006` (só `score_firmware`) e SHA256 de todas as entradas; sem commit|
|`model`|`extra_trees`, `random_forest`, `majoritario`, `identidade`, `score_firmware`|
|`purpose`|`reportado` (Extra Trees, `grouped`), `baseline` (Random Forest, majoritário, `score_firmware`, em `grouped`) ou `diagnostico` (identidade e todo `random`)|
|`config`|configuração efetiva, com overrides e regra do alvo|
|`experiment`, `scheme`|`principal`/`binario`; `grouped`/`random`|
|`columns`|conjunto de colunas pedido|
|`hyperparameters`, `class_weight`, `seeds`|efetivos|
|`inputs`|SHA256 da tabela, da proveniência e dos folds (de `009/FR-006`) e, no `score_firmware`, da tabela de features|
|`folds`|por (repetição, fold): colunas usadas depois do filtro, `firmware_id` de treino, contagem por classe em treino e teste, arquivo do modelo quando persistido|
|`commit`, `created_at`|`created_at` é o único campo que muda entre execuções iguais|

## `models/runs/<run_id>/fold_<repeat>_<fold>.joblib`

`Pipeline` (filtro + modelo) ajustado; só em Extra Trees e Random Forest
com colunas completas, `grouped` e `principal` (FR-007).
