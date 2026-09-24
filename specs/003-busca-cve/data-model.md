# Data Model: Busca de CVEs na NVD

Esquema do cache JSON gravado pelo código atual em `master` (spec, FR-006).
O arquivo é um objeto JSON; cada chave é um par `"<fabricante>/<modelo>"`
na forma lida do parquet de features (minúsculas, sem espaços nas pontas) e
cada valor é uma entrada. Não há campo global de versão: `schema_version`
fica em cada entrada.

## Entrada do cache

|Campo|Tipo|Significado|
|---|---|---|
|`schema_version`|int|sempre `2`; outro valor interrompe a execução ao pular o par (FR-007) e a rotulagem|
|`source`|texto|`cpe` (CVEs por `virtualMatchString`) ou `keyword` (CVEs por `keywordSearch`) (FR-004)|
|`vendor`|texto|fabricante na forma NVD (ex.: `d-link`, `tp-link`) (FR-002)|
|`model`|texto|modelo na forma NVD (ex.: `DIR-300`) (FR-002)|
|`cpe_name`|texto ou nulo|CPE 2.3 de parte `o` com versão e campos seguintes em `*`; nulo quando `source=keyword` (FR-003)|
|`cves`|lista de registros|todas as CVEs devolvidas pela consulta, em todas as páginas; pode ser vazia|

## Registro de CVE

|Campo|Tipo|Significado|
|---|---|---|
|`id`|texto|identificador da CVE (ex.: `CVE-2020-1111`)|
|`cvss_max`|float|`baseScore` da primeira métrica v3.1, senão v3.0, senão v2; `0.0` sem métrica (FR-005)|
|`severity`|texto|`CRITICAL`, `HIGH`, `MEDIUM`, `LOW` ou `NONE`, em maiúsculas (FR-005)|
|`configurations`|lista|`configurations` da NVD sem alteração (nós, `cpeMatch`, `criteria`, `versionStart*`/`versionEnd*`); vazia quando a NVD ainda não analisou a CVE|

## Regras de validação

- Toda entrada é um objeto com a lista `cves` e `schema_version` igual a 2.
  Entrada fora disso é erro, na busca (ao pular o par) e na rotulagem.
- `cpe_name` é preenchido se e só se `source=cpe`.
- Um par cuja consulta falhou não tem entrada (FR-008). Ausência de par é
  erro na rotulagem, não "sem CVE" (constituição, princípio II;
  `005-rotulagem-cve`).
- A mesma CVE pode aparecer em várias entradas; não há deduplicação entre
  pares.

## Artefatos existentes

Medido em 2026-09-24, só leitura.

**`dataset/cve_cache_v2.json`** (artefato em uso; 57.446.947 bytes):

|Medida|Valor|
|---|---|
|Entradas (pares)|310|
|Entradas com `schema_version: 2`|310|
|`source=cpe` / `source=keyword`|115 / 195|
|Entradas sem CVE (total / `cpe` / `keyword`)|186 / 10 / 176|
|Ocorrências de CVE (total / `cpe` / `keyword`)|2838 / 2776 / 62|
|CVEs distintas|777|
|Maior número de CVEs numa entrada|246|
|`severity` (`MEDIUM` / `HIGH` / `CRITICAL` / `LOW`)|1271 / 1162 / 363 / 42|
|CVEs com `configurations` vazia|5|
|Entradas por fabricante interno (`asus` / `netgear` / `tp_link` / `dlink` / `belkin` / `tplink`)|122 / 56 / 43 / 36 / 27 / 26|
|Pares de `features_v2.parquet` sem entrada / entradas sem par|0 / 0|

As 10 entradas `source=cpe` sem CVE são `dlink/dap_2695`, `dlink/dir-100`,
`dlink/dsr-1000`, `dlink/dsr-1000n`, `dlink/dsr-150`, `dlink/dsr-150n`,
`dlink/dsr-250`, `dlink/dsr-250n`, `dlink/dsr-500` e `dlink/dsr-500n`. As
43 entradas `tp_link/*` têm `vendor="tp-link"`; 37 estão sem CVE.

**`dataset/cve_cache.json`** (v1, `--output` padrão): 336 entradas no
esquema agregado antigo (`cvss_max`, `cve_count_critical`,
`cve_count_high`, `cve_count_medium`, `cve_count_low`, `cve_total`), sem
`schema_version` nem lista `cves`. O código atual o rejeita como schema
antigo. Das 336 chaves, 26 não estão no v2; as 43 entradas `tp_link/*` têm
`cve_total=0`.

## Consumidor

`005-rotulagem-cve` lê o cache pela chave do par, avalia as
`configurations` de cada CVE contra a versão do firmware e agrega
`cve_total`/`cvss_max`.
