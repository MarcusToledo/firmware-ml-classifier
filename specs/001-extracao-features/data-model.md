# Data Model: Extração estática de features

Esquema do registro gravado em `features.parquet` (ou CSV) pelo código
atual em `master`. Uma linha por arquivo de entrada (spec, FR-009 e
FR-012). Com a configuração versionada (`doc2vec.vector_size=100`), o
registro tem 135 colunas.

## Registro de features

|Grupo|Colunas|Qtde.|Tipo|Origem|
|---|---|---|---|---|
|Identidade de conteúdo|`firmware_id`|1|texto (SHA256 hex) ou nulo|SHA256 dos bytes lidos, até `max_bytes` (FR-004)|
|Estatísticas|`entropy`, `byte_mean`, `compress_ratio`|3|float|bytes lidos (FR-005)|
|Doc2Vec|`doc2vec_0` … `doc2vec_{vector_size-1}`|100 no padrão|float|documento de strings; zeros sem modelo. Requisito em `007-embeddings-doc2vec`|
|Estruturais/Binwalk|`n_filesystems`, `n_crypto_signatures`, `has_encrypted_sections`, `fs_type`, `compression_type`, `entropy_variance_across_sections`|6|int, int, bool, texto ou nulo, texto ou nulo, float|varredura do Binwalk sobre o arquivo inteiro (FR-007); `n_crypto_signatures` e `has_encrypted_sections` definidas em `002-evidencias-seguranca`; `entropy_variance_across_sections` vem dos bytes lidos (FR-005)|
|Strings|`count_hardcoded_passwords`, `count_credential_pairs`, `count_hardcoded_ips`, `count_public_ips`, `count_urls`, `count_api_tokens`, `has_telnetd`, `has_debug_account`, `has_outdated_libssl`, `has_outdated_busybox`, `has_outdated_dropbear`|11|int (6), bool (5)|strings ASCII limitadas por `max_strings` (FR-006); detectores definidos em `002-evidencias-seguranca`|
|Metadados|14 colunas `meta_*` (tabela abaixo)|14|ver abaixo|leitura, configuração e path|

Total: 1 + 3 + 100 + 6 + 11 + 14 = 135.

## Metadados `meta_*`

Não são features (constituição, princípio III). Servem para proveniência e
para as etapas de busca de CVE e rotulagem.

|Coluna|Tipo|Significado|
|---|---|---|
|`meta_read_ok`|bool|leitura produziu bytes e `max_bytes` é válido|
|`meta_byte_len`|int|bytes lidos (não o tamanho original do arquivo)|
|`meta_bytes_used`|int|bytes lidos; hoje igual a `meta_byte_len`|
|`meta_max_bytes`|int ou nulo|limite configurado|
|`meta_truncated`|bool|limite de strings (`max_strings`) ou de documento (`max_doc_chars`) atingido; não reflete o corte por `max_bytes`|
|`meta_max_bytes_applied`|bool|há limite configurado, mesmo que o arquivo seja menor|
|`meta_doc2vec_used`|bool|modelo Doc2Vec carregado e leitura ok|
|`meta_error`|texto ou nulo|`empty firmware`, `max_bytes results in empty read` ou mensagem da exceção|
|`meta_path`|texto|path do arquivo; contém fabricante e modelo mesmo no modo inferência|
|`meta_brand`|texto ou nulo|fabricante do path; nulo sem `--label-from-path` (FR-010)|
|`meta_model`|texto ou nulo|modelo do path, sem sufixo de versão; nulo sem `--label-from-path`|
|`meta_label`|texto ou nulo|`<fabricante>_<modelo>`; nulo sem `--label-from-path`. Não é rótulo de treino (constituição, princípio II)|
|`meta_version`|texto ou nulo|versão do path (`004-versao-firmware`); nulo sem `--label-from-path`|
|`meta_version_source`|texto ou nulo|`directory` ou `filename`; nulo junto com `meta_version`|

## Regras de validação

- Linha de erro de leitura (`empty firmware`, `max_bytes results in empty
  read`): `meta_read_ok=False`, `firmware_id` nulo, `meta_error`
  preenchido. As features continuam presentes, calculadas sobre zero bytes
  (0, 0.0, nulo ou `False`).
- Linha de exceção inesperada na extração do arquivo: mesmos metadados, com
  `meta_error` igual à mensagem da exceção, e sem nenhuma feature (as
  colunas saem nulas na tabela).
- `meta_version` e `meta_version_source` são ambos nulos ou ambos
  preenchidos (regra de `004-versao-firmware`).
- Nenhuma coluna fora de `meta_*` pode ter nome de CVE (`cvss_max`,
  `cve_total`, `cve_count_*`) ou de identidade (`brand`, `model`,
  `version`, `version_source`) (FR-011).

## Artefatos existentes

Os artefatos em `dataset/processed/` são anteriores às colunas de versão
(medido em 2026-09-24):

|Artefato|Colunas|`meta_*`|Falta|
|---|---|---|---|
|`features.parquet`|133|12|`meta_version`, `meta_version_source`|
|`features_v2.parquet`|134|13|`meta_version_source`|

O código atual gera 135 colunas e 14 `meta_*`.

## Artefato relacionado

`findings.jsonl` (`--findings-output`) é artefato de
`002-evidencias-seguranca`: um achado por linha, correlacionável a este
registro por `firmware_id`.
