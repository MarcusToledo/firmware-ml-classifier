# Data Model: Avaliação e relatórios

## `configs/evaluation.yaml`

|Chave|Conteúdo|
|---|---|
|`matrix`|lista de (modelo, experimento, esquema) da matriz principal (FR-001)|
|`groups`|E, B, S, F com as colunas (prefixo `*` permitido, ex.: `fs_type__*`; F = `unpacked_*` da `012`)|
|`arms`|`completo`, `so_<grupo>`, `sem_<grupo>`, `sem_url_ip`|
|`ablation_models`|`extra_trees`, `random_forest`; experimento `principal`; esquema `grouped`|
|`bootstrap`|`n_resamples: 2000`, `seed: 0`, `ci: 0.95`|
|`permutation`|`n_repeats: 10`, `seed: 0`, `scoring: f1_macro`|

## `reports/<timestamp>/`

|Arquivo|Linhas|Colunas|
|---|---|---|
|`metrics.csv`|uma por execução|`run_id`, `model`, `experiment`, `scheme`, `arm`, `purpose`, média e desvio de cada métrica agregada, número de métricas indefinidas|
|`metrics_per_class.csv`|execução × classe|`run_id`, `purpose`, precisão, revocação, F1 (média e desvio)|
|`confusion.csv`|execução × classe verdadeira × prevista|`run_id`, `purpose`, contagem somada nas repetições|
|`comparison.csv`|execução da matriz `grouped`|macro-F1, IC 95%, diferença contra o Extra Trees e IC 95%, `purpose`|
|`ablation.csv`|braço × modelo|macro-F1, IC 95%, diferença contra o completo e IC 95%; braço não executado com motivo|
|`split_diagnostic.csv`|modelo × experimento|macro-F1 em `grouped` e `random`, diferença e IC 95% (grupos de `folds_grouped`); marcado `diagnostico`|
|`exclusions.csv`|fabricante|proporção de `indeterminado`, contagens por motivo (da `008`)|
|`importance.csv`|modelo × feature|queda média de macro-F1, desvio e IC 95% percentil entre folds|
|`report.md`|—|reúne as tabelas; seções separadas para `diagnostico` e `ablation`; sem data|
|`*.png`|—|matriz de confusão, comparação com IC, importância|
|`report.meta.json`|—|`run_id` avaliados com o commit de cada um, SHA256 da tabela, da proveniência, dos folds por esquema e de `training_table.meta.json`, configuração efetiva, braços não executados, folds de teste sem classe, `created_at`|

Linhas ordenadas por chave fixa; floats com formato fixo; PNG com
`metadata` fixo; CSV, PNG e `report.md` idênticos entre gerações (SC-002).
