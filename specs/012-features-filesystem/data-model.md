# Data Model: Features do filesystem desempacotado

Colunas acrescentadas à tabela de features da `001`. Sem
`meta_unpack_status=ok`, todas as `unpacked_*` são nulas (FR-008).

## Features (`unpacked_*`)

|Coluna|Tipo|Regra|
|---|---|---|
Universo: arquivos dentro das raízes de filesystem extraídas, sem os
carvados intermediários; ELF com o mesmo SHA256 conta uma vez (FR-002).

|Coluna|Tipo|Regra|
|---|---|---|
|`unpacked_n_files`|int ou nulo|arquivos regulares, sem seguir symlinks|
|`unpacked_n_elf`|int ou nulo|ELF pelo cabeçalho (inclui relocáveis, outros tipos e malformados)|
|`unpacked_n_elf_exec`|int ou nulo|`ET_EXEC`, ou `ET_DYN` com `DT_DEBUG` (checksec 2.7.1)|
|`unpacked_n_elf_lib`|int ou nulo|`ET_DYN` sem `DT_DEBUG`|
|`unpacked_n_elf_static`|int ou nulo|executáveis e bibliotecas sem tabela de símbolos dinâmicos|
|`unpacked_prop_nx`|float ou nulo|entre executáveis e bibliotecas lidos|
|`unpacked_prop_pie`|float ou nulo|entre executáveis lidos|
|`unpacked_prop_relro_full`|float ou nulo|entre executáveis e bibliotecas lidos|
|`unpacked_prop_relro_partial`|float ou nulo|idem|
|`unpacked_prop_canary`|float ou nulo|entre os lidos com símbolos dinâmicos|
|`unpacked_prop_fortify`|float ou nulo|idem|
|`unpacked_prop_import_<função>`|float ou nulo|8 colunas: `system`, `popen`, `execve`, `strcpy`, `strcat`, `sprintf`, `vsprintf`, `gets`; entre os lidos com símbolos dinâmicos|

Total: 5 contagens + 6 proporções de hardening + 8 de importação = 19.

## Metadados (`meta_*`, fora do vetor)

|Coluna|Tipo|Regra|
|---|---|---|
|`meta_fs_elf_malformed`|int ou nulo|ELF que o pyelftools não conseguiu ler (inclui cortados em `max_bytes`); nulo sem unpack `ok`|
|`meta_fs_arch`|texto ou nulo|`e_machine` mais frequente entre os ELF lidos; empate pela ordem alfabética; nulo sem ELF lido|
|`meta_fs_status`|texto|`ok`, `erro` ou `nao_executado` (FR-012)|
|`meta_fs_error`|texto ou nulo|mensagem do erro com `erro`|

## `configs/feature_extraction.yaml`

|Chave|Valor|
|---|---|
|`filesystem.dangerous_functions`|as 8 funções acima|
