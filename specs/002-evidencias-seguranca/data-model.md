# Data Model: Evidências de segurança

Esquemas do achado de segurança e da linha de `findings.jsonl` gravada com
`--findings-output` pelo código atual em `master` (spec, FR-002 e FR-016).
As 13 colunas de evidência do vetor estão no data-model de
`001-extracao-features` (grupos "Estruturais/Binwalk" e "Strings"); aqui só
a regra de derivação.

## Achado (`SecurityFinding`)

Registro imutável; todos os campos são texto.

|Campo|Significado|
|---|---|
|`type`|categoria do achado (tabela abaixo)|
|`source`|string ASCII ou descrição do Binwalk original, inteira|
|`context`|explicação curta do match (ex.: `key=value assignment: 'password=admin'`)|
|`confidence`|`low`, `medium` ou `high`; fixo por detector|
|`detector`|nome do detector (tabela abaixo)|
|`detector_version`|`1.0` em todos os detectores. Planejado (FR-017, TickTick T11): versão própria por detector, incrementada a cada mudança de regra|

## Detectores

|`detector`|`type`|`confidence`|Entrada|Contagem|Coluna do vetor|
|---|---|---|---|---|---|
|`hardcoded_passwords`|`credential_candidate`|`high` (chave=valor) ou `medium` (token de senha padrão)|strings|por string|`count_hardcoded_passwords`|
|`credential_pairs`|`credential_pair`|`high`|strings|por string|`count_credential_pairs`|
|`hardcoded_ips`|`hardcoded_ip`|`low`|strings|por ocorrência|`count_hardcoded_ips`|
|`public_ips`|`public_ip`|`high`|strings|por ocorrência|`count_public_ips`|
|`telnetd`|`exposed_service`|`high`|strings|por string|`has_telnetd`|
|`debug_account`|`debug_account`|`low`|strings|por string|`has_debug_account`|
|`outdated_libssl`|`outdated_library`|`medium`|strings|por string|`has_outdated_libssl`|
|`outdated_busybox`|`outdated_library`|`medium`|strings|por string|`has_outdated_busybox`|
|`outdated_dropbear`|`outdated_library`|`medium`|strings|por string|`has_outdated_dropbear`|
|`urls`|`url`|`low`|strings|por ocorrência|`count_urls`|
|`api_tokens`|`api_token_candidate`|`low`|strings|por ocorrência|`count_api_tokens`|
|`crypto_signatures`|`crypto_signature`|`medium`|descrições do Binwalk|por descrição|`n_crypto_signatures`|
|`encrypted_sections`|`encrypted_section`|`medium`|descrições do Binwalk|por descrição|`has_encrypted_sections`|

Regras de cada detector: spec, FR-003 a FR-013. Planejado (TickTick T11):
FR-018 (`debug_account`), FR-019 (`api_tokens`), FR-020 (`hardcoded_ips` e
`public_ips`), FR-021 (`encrypted_sections`), FR-022
(`outdated_dropbear`), FR-023 e FR-024 (`hardcoded_passwords`) mudam as
regras; tipos, confianças, contagens e colunas desta tabela não mudam.

## Linha de `findings.jsonl`

Uma linha JSON por achado, UTF-8, sem escape de caracteres não ASCII.
Ordem das chaves:

|Campo|Tipo|Origem|
|---|---|---|
|`firmware_id`|texto (SHA256 hex)|`001/FR-004`; nunca nulo na prática, porque falha de leitura não gera achado|
|`path`|texto|mesmo valor de `meta_path`; contém fabricante e modelo mesmo no modo inferência. Planejado (`004/FR-016`): relativo à raiz do dataset|
|`type`, `source`, `context`, `confidence`, `detector`, `detector_version`|texto|achado (tabela acima)|

## Regras de validação

- Cada coluna de contagem do vetor é igual ao número de linhas do JSONL
  com o mesmo `path` e o `detector` correspondente; cada flag é `True` se
  e só se há ao menos uma linha (spec, FR-014 e SC-001).
- Firmware sem achado e firmware com falha de leitura não têm linha. A
  ausência de linha não distingue os dois casos; a distinção está em
  `meta_read_ok` no `features.parquet`.
- Um `firmware_id` pode aparecer com mais de um `path` (aliases, conteúdo
  idêntico). A chave de correlação exata com o `features.parquet` é o par
  (`firmware_id`, `path` = `meta_path`).
- A mesma descrição do Binwalk pode gerar um achado `crypto_signature` e um
  `encrypted_section` (ambos casam `AES`).

## Artefatos existentes

Medido em 2026-09-24, só leitura, sobre `dataset/processed/`:

|Artefato|Linhas|`firmware_id` distintos|`path` distintos|
|---|---|---|---|
|`findings.jsonl`|3049|194|199|
|`findings_v2.jsonl`|3049|194|199|

Os dois têm as mesmas contagens por detector, tipo e confiança. Todas as
3049 linhas têm as 8 chaves na ordem acima e `firmware_id` não nulo.

Achados de `findings_v2.jsonl` por detector:

|`detector`|`type`|Achados|
|---|---|---|
|`api_tokens`|`api_token_candidate`|1128|
|`hardcoded_passwords`|`credential_candidate`|1055 (1040 `medium`, 15 `high`)|
|`hardcoded_ips`|`hardcoded_ip`|236|
|`debug_account`|`debug_account`|199|
|`crypto_signatures`|`crypto_signature`|184|
|`encrypted_sections`|`encrypted_section`|171|
|`public_ips`|`public_ip`|39|
|`urls`|`url`|37|
|`credential_pairs`, `telnetd`, `outdated_libssl`, `outdated_busybox`, `outdated_dropbear`|—|0|

Por confiança: 1600 `low`, 1395 `medium`, 54 `high`.

Cruzamento com `features_v2.parquet` (840 linhas): 0 divergências entre as
13 colunas de evidência e as contagens de achados por `meta_path`; 199
linhas têm ao menos um achado; todo `path` do JSONL existe no parquet com o
mesmo `firmware_id`.

## Artefato relacionado

`features.parquet` é artefato de `001-extracao-features`; as 13 colunas de
evidência são derivadas dos mesmos achados deste arquivo.
