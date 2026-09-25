# Data Model: Rotulagem por CVE

Esquema do registro gravado em `labels_v2.csv` pelo código atual em
`master`. Uma linha por linha da tabela de features de entrada, na mesma
ordem (spec, FR-015). A chave de junção com a tabela de features é
`firmware_id` + `meta_path`; o treino junta por `firmware_id`.

## Registro de rótulo

|Coluna|Tipo|Origem|
|---|---|---|
|`firmware_id`|texto (SHA256 hex)|cópia de `firmware_id` da tabela de features (`001/FR-004`); nunca nulo (FR-002)|
|`meta_path`|texto|cópia de `meta_path`; nunca nulo|
|`vendor`|texto|cópia de `meta_brand`|
|`model`|texto|cópia de `meta_model`|
|`version`|texto ou nulo|cópia de `meta_version`, conferida contra a versão reinferida do path (FR-004)|
|`version_source`|texto ou nulo|`directory` ou `filename`, reinferido de `meta_path` pela regra de `004-versao-firmware` (`004/FR-004`, `004/FR-005`); nulo quando `version` é nulo (`004/FR-013`)|
|`security_level`|texto|`sem_cve_conhecida`, `cve_conhecida`, `cve_critica` ou `indeterminado` (FR-012, FR-013)|
|`cve_total`|int ≥ 0|número de CVEs aplicáveis (A) do `firmware_id`, somadas entre aliases e sem repetir ID; limite inferior|
|`cvss_max`|float em [0, 10]|maior CVSS entre as CVEs aplicáveis (A); 0.0 sem aplicáveis; limite inferior|

Nenhuma coluna de feature nem `meta_*` além de `meta_path` (FR-015). Nenhuma
dessas colunas pode entrar no vetor de features; do arquivo, o treino usa só
`security_level` (constituição, princípio III).

## Regras de validação

- Todos os aliases de um `firmware_id` têm o mesmo `security_level`,
  `cve_total` e `cvss_max` (regra C, FR-012).
- `security_level=sem_cve_conhecida` implica `cve_total=0`.
- `security_level` em `cve_conhecida` ou `cve_critica` implica
  `cve_total>0`; `cve_critica` implica `cvss_max` maior ou igual ao
  limiar usado (9.0 por padrão). O limiar não é gravado no arquivo.
- `indeterminado` pode ter `cve_total` 0 ou maior: ele indica que as CVEs
  indeterminadas mudariam a classe, não a ausência de aplicáveis.
- `version` e `version_source` são ambos nulos ou ambos preenchidos.

## Planejado (TickTick T04)

Esquema previsto; nada disso existe no código atual.

### Colunas novas do registro de rótulo (FR-022)

|Coluna|Tipo|Origem|
|---|---|---|
|`label_strategy`|texto|`alias_unico` (um alias) ou `agregacao_conservadora` (regra C com mais de um alias)|
|`alias_count`|int ≥ 1|número de aliases do `firmware_id`|

As duas vêm depois das 9 colunas atuais. Como as demais, não entram no
vetor de features.

### `<nome>.meta.json` (FR-018)

Ao lado da tabela, com o mesmo nome-base (no padrão,
`dataset/processed/labels_v2.meta.json`). Não é gravado com `--dry-run`.

|Chave|Tipo|Conteúdo|
|---|---|---|
|`critical_cvss`|float em [0, 10]|valor de `--critical-cvss` usado|
|`features_path`|texto|caminho de `--features`|
|`features_sha256`|texto (SHA256 hex)|hash do arquivo de features|
|`cves_path`|texto|caminho de `--cves`|
|`cves_sha256`|texto (SHA256 hex)|hash do cache de CVE|
|`code_commit`|texto|commit do código que gerou a tabela|
|`generated_at`|texto (ISO 8601, UTC)|data e hora da execução; único campo que muda entre execuções com as mesmas entradas|

### `<nome>_aliases.jsonl` (FR-021, FR-023)

Ao lado da tabela, com o mesmo nome-base (no padrão,
`dataset/processed/labels_v2_aliases.jsonl`). Uma linha por `firmware_id`,
na ordem da primeira ocorrência na tabela de entrada. Não é gravado com
`--dry-run`.

|Chave|Tipo|Conteúdo|
|---|---|---|
|`firmware_id`|texto (SHA256 hex)|identidade de conteúdo|
|`label_strategy`|texto|igual à coluna do registro de rótulo|
|`versions_differ`|bool|verdadeiro quando os aliases têm versões diferentes; nulo contra preenchido conta como diferente|
|`aliases`|lista|um objeto por alias, na ordem da tabela de entrada|
|`aliases[].meta_path`|texto|path do alias|
|`aliases[].vendor`, `aliases[].model`, `aliases[].version`|texto ou nulo|cópias de `meta_brand`, `meta_model` e `meta_version`|
|`aliases[].applicable_cves`|lista de texto|IDs ordenados das CVEs aplicáveis ao alias, antes da agregação|
|`aliases[].indeterminate_cves`|lista de texto|IDs ordenados das CVEs indeterminadas do alias, antes da agregação|

### Coluna nova de entrada (FR-020)

A rotulagem passa a ler também `meta_version_source` da tabela de
features; tabela sem a coluna é erro.

## Artefato existente

Medido em 2026-09-24, somente leitura, sobre `dataset/labels_v2.csv`:

|Medida|Valor|
|---|---|
|Linhas|840|
|`firmware_id` distintos|699|
|`firmware_id` com mais de um alias|74|
|`firmware_id` com mais de um `security_level`|0|
|Colunas|as 9 da tabela acima, nessa ordem|

Distribuição de `security_level`:

|`security_level`|Linhas|`firmware_id`|
|---|---:|---:|
|`sem_cve_conhecida`|468|423|
|`cve_conhecida`|68|49|
|`cve_critica`|167|101|
|`indeterminado`|137|126|
|Total|840|699|

`version_source`: 614 `filename`, 0 `directory` e 226 nulos. Das 137
linhas `indeterminado`, 83 têm `version_source` nulo. Nenhuma linha
`sem_cve_conhecida` tem `cve_total>0`.

Os números conferem com `docs/PIPELINE.md` ("Estado real do dataset") e com
o `TODO.md` (423/49/101/126 por `firmware_id`). Rodar a rotulagem do código
atual em memória sobre `dataset/processed/features_v2.parquet` e
`dataset/cve_cache_v2.json` (310 entradas) reproduziu o arquivo: 840
linhas, 0 diferenças em `security_level`, `cve_total`, `cvss_max` e
`version_source`.

O `dataset/labels.csv` (v1) ainda existe e é o destino padrão de
`--output` (spec, Edge Cases).

## Artefatos relacionados

- Entrada: tabela de features de `001-extracao-features`
  (`dataset/processed/features_v2.parquet`), extraída com
  `--label-from-path`. Só `firmware_id`, `meta_path`, `meta_brand`,
  `meta_model` e `meta_version` são lidas; com FR-020 (Planejado), também
  `meta_version_source`.
- Entrada: cache de CVE de `003-busca-cve` (`dataset/cve_cache_v2.json`,
  `schema_version: 2`; `003/FR-006`).
