# Feature Specification: Extração estática de features

**Feature Branch**: `docs/specs-retroativas`

**Created**: 2026-09-24

**Status**: Misto

**Input**: User description: "Spec retroativa (Status Implementado) da extração estática de features em lote: leitura limitada do binário, features estatísticas, de strings ASCII e estruturais do Binwalk, tabela features.parquet/CSV com firmware_id, features e colunas meta_*, modo inferência sem identidade, guarda de vazamento e tolerância a falhas. Derivar só do código em master, testes, docs/PIPELINE.md e TODO.md."

## Clarifications

### Session 2026-09-24

- Varredura de ambiguidade (`/speckit.clarify`, histórico da spec
  retroativa): sem ambiguidades críticas. Os FRs `[Implementado]` descrevem
  o comportamento do código em `master`; as decisões em aberto na época
  (limite `max_bytes`, identidade do `firmware_id`, Binwalk ausente) ficaram
  em Edge Cases. Nenhuma pergunta feita nessa varredura.
- Terminologia normalizada: "truncado" passa a significar só o corte por
  `max_strings`/`max_doc_chars` (`meta_truncated`); o corte por `max_bytes`
  é chamado "cortado por `max_bytes`".

### Session 2026-09-24 (escopo restante, TickTick T11 e T07)

- Q: Qual o novo limite `max_bytes` com a leitura em blocos? → A: 256 MiB;
  cobre os 840 arquivos atuais (maior: 150,9 MiB) (FR-015).
- Q: Como registrar o estado do Binwalk? → A: o Binwalk passa a ser
  obrigatório: ausente, a extração falha antes de processar o lote; erro ou
  timeout por arquivo ficam em `meta_binwalk_status` (FR-014).
- Q: De onde vêm as strings quando o filesystem não desempacota? → A: do
  arquivo bruto, como hoje, com a origem registrada em
  `meta_strings_source` (`filesystem` ou `blob`) (FR-016).
- Q: Quais limites o desempacotamento respeita por firmware? → A: 2 GiB
  extraídos, 100 mil arquivos e 300 s; symlinks não seguidos; diretório
  temporário apagado ao fim (FR-016).
- Q: De quais arquivos extraídos saem as strings? → A: de todos os
  arquivos regulares, em ordem lexicográfica de path, sem strings
  repetidas; `max_strings` e `max_doc_chars` continuam valendo (FR-016).
  Revisto no analyze (F1, C1): os detectores varrem todas as strings, em
  streaming, e o dedupe e os limites `max_strings`/`max_doc_chars` valem só
  para o documento de strings.
- Analyze (2026-09-24), decisões do pesquisador: `max_bytes` obrigatório,
  com 256 MiB também sem YAML (D1, FR-019); `binwalk` ≥ 2.3.4 conferido no
  início, rodando isolado (D2); strings em streaming com parada (C1);
  timeout vira falha que exige rodar de novo, sem fallback (D3); Doc2Vec
  desligado também sem YAML e nada carregado (F4); `nao_executado` nas
  linhas sem varredura (C2); leitura de cada arquivo extraído limitada a
  `max_bytes` e extratores conferidos antes do lote (D5, F5).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Extração em lote reprodutível (Priority: P1)

O pesquisador aponta a extração para `dataset/raw` (ou para um arquivo, ou
para uma lista de paths) e recebe uma tabela com uma linha por arquivo
candidato a firmware, gerada a partir de configuração versionada.

**Why this priority**: toda etapa seguinte (busca de CVE, rotulagem, treino)
lê essa tabela. Sem ela não há dataset.

**Independent Test**: rodar a extração sobre um diretório com dois binários
e conferir que a tabela tem duas linhas, com `firmware_id` e as colunas de
feature.

**Acceptance Scenarios**:

1. **Given** um diretório com dois arquivos `.bin`, **When** o pesquisador
   roda a extração com saída parquet, **Then** a tabela tem 2 linhas.
2. **Given** um arquivo de firmware, **When** o pesquisador pede
   `--format csv`, **Then** a saída é CSV com as mesmas colunas do parquet.
3. **Given** a configuração versionada, **When** o pesquisador passa
   `--override feature.max_single_string_len=8`, **Then** o valor
   sobrescrito é aplicado na extração.
4. **Given** vários arquivos e mais de um worker, **When** a extração
   termina, **Then** as linhas seguem a ordem dos paths de entrada.
5. **Given** qualquer execução, **When** a extração termina, **Then** o log
   informa o tempo total e o tempo médio por arquivo.

---

### User Story 2 - Vetor sem identidade nem CVE (Priority: P1)

A banca audita que o vetor de features não carrega fabricante, modelo,
versão nem campos derivados de CVE, e que o modo inferência não expõe
identidade nos metadados.

**Why this priority**: o rótulo é função de fabricante e modelo
(constituição, princípio III). Vazamento invalida as métricas do TCC.

**Independent Test**: extrair um firmware cujo path contém fabricante,
modelo e versão e inspecionar as chaves de feature e as colunas `meta_*`.

**Acceptance Scenarios**:

1. **Given** o arquivo `raw/zyxel/NWA110AX_7.10(ABTG.4)C0/firmware.bin`,
   **When** suas features são extraídas, **Then** as chaves de feature não
   contêm `cvss_max`, `cve_total`, `cve_count_*`, `brand`, `model`,
   `version`, `version_source` nem nenhuma chave `meta_*`.
2. **Given** a extração sem `--label-from-path`, **When** a tabela é
   gravada, **Then** `meta_brand`, `meta_model`, `meta_label`,
   `meta_version` e `meta_version_source` são nulos.
3. **Given** a extração com `--label-from-path`, **When** a tabela é
   gravada, **Then** esses cinco campos saem preenchidos a partir do path.

---

### User Story 3 - Firmware não confiável não derruba o lote (Priority: P2)

O pesquisador processa imagens de terceiros, possivelmente vazias ou
ilegíveis, e o lote termina com a falha registrada na linha do arquivo.

**Why this priority**: o dataset tem imagens malformadas (constituição,
princípio VI). Um arquivo ruim não pode custar a execução inteira nem sumir
da saída.

**Independent Test**: rodar a extração num lote com um arquivo bom e um path
inexistente e conferir as duas linhas.

**Acceptance Scenarios**:

1. **Given** um arquivo vazio, **When** ele é extraído, **Then**
   `meta_read_ok=False`, `meta_error="empty firmware"` e `firmware_id` é
   nulo.
2. **Given** `max_bytes=0`, **When** um arquivo é extraído, **Then**
   `meta_error="max_bytes results in empty read"`.
3. **Given** um lote com um arquivo bom e um path inexistente, **When** a
   extração termina, **Then** há 2 resultados e o do arquivo bom tem
   `read_ok=True`.
4. **Given** uma varredura do Binwalk que termina com código de erro,
   **When** o arquivo é extraído, **Then** a linha registra
   `meta_binwalk_status=erro`, o log emite um aviso e o lote continua.
   *(Planejado, FR-014; hoje as features saem vazias sem registro.)*
5. **Given** um ambiente sem Binwalk, ou com versão anterior a 2.3.4,
   **When** a extração começa, **Then** ela falha antes de processar
   qualquer arquivo. **Given** uma varredura que passa do timeout, **When**
   o lote termina, **Then** a linha registra `meta_binwalk_status=timeout`
   e a execução sai com código diferente de 0. *(Planejado, FR-014.)*
6. **Given** uma configuração sem `max_bytes` no YAML, **When** a extração
   começa, **Then** vale 256 MiB. **Given** `max_bytes` nulo ou não
   positivo, ou `--config` apontando para arquivo inexistente, **When** a
   extração começa, **Then** ela falha antes do lote citando a chave ou o
   arquivo. *(Planejado, FR-019.)*

---

### User Story 4 - Features estatísticas, de strings e estruturais (Priority: P2)

O pesquisador obtém, por firmware, features estatísticas dos bytes,
contagens derivadas das strings ASCII e features estruturais do Binwalk,
sempre com o mesmo conjunto de chaves.

**Why this priority**: o conjunto de chaves estável é o que permite montar
uma matriz de treino; os valores são o sinal que o classificador usa.

**Independent Test**: extrair um firmware com saída do Binwalk simulada e
outro sem Binwalk, e comparar as chaves. Com `001/FR-014` (Planejado), o
caso sem Binwalk passa a falhar antes do lote.

**Acceptance Scenarios**:

1. **Given** uma varredura do Binwalk que reporta squashfs e lzma, **When**
   as features são extraídas, **Then** `n_filesystems`, `fs_type` e
   `compression_type` são preenchidos.
2. **Given** um ambiente sem Binwalk instalado, **When** as features são
   extraídas, **Then** as chaves de Binwalk e de padrões de string estão
   presentes no resultado. *(Substituído por FR-014 quando implementado.)*
3. **Given** a configuração versionada, **When** a extração roda, **Then**
   a tabela não tem colunas `doc2vec_*`; **When** o Doc2Vec é ligado por
   configuração explícita, **Then** as colunas `doc2vec_*` voltam.
   *(Planejado, FR-018, TickTick T07.)*

---

### User Story 5 - Features do firmware inteiro e do filesystem extraído (Priority: P1) *(Planejado)*

O pesquisador obtém features estatísticas calculadas sobre o arquivo
inteiro e strings tiradas dos arquivos do filesystem desempacotado, sem
executar nada e com limites de recursos, e vê na tabela o tamanho real do
arquivo e o resultado do desempacotamento.

**Why this priority**: hoje 696 de 840 arquivos são cortados em 5 MiB e as
2000 primeiras strings cobrem ~3,7% dos bytes lidos, então os detectores de
strings ficam quase cegos (TickTick T11; `TODO.md`, "Documento de
strings"). Sem isso, a ablation de strings mediria ruído de cabeçalho.

**Independent Test**: extrair um firmware maior que 5 MiB com um squashfs
conhecido e outro que não desempacota, e comparar tamanho, estatísticas,
origem das strings e estado do desempacotamento.

**Acceptance Scenarios**:

1. **Given** um arquivo de 20 MiB, **When** ele é extraído, **Then** as
   features estatísticas e o `firmware_id` cobrem os 20 MiB, a memória
   usada não cresce com o tamanho do arquivo e a linha registra o tamanho
   original em `meta_file_size`.
2. **Given** um firmware com squashfs, **When** ele é extraído, **Then** o
   filesystem é desempacotado em diretório temporário, os detectores
   varrem as strings de todos os arquivos extraídos
   (`meta_strings_source=filesystem`) e o diretório é apagado ao fim.
3. **Given** um firmware que não desempacota (ex.: cifrado), **When** ele é
   extraído, **Then** `meta_unpack_status=falha` e as strings vêm do
   arquivo bruto (`meta_strings_source=blob`).
4. **Given** um desempacotamento que passa de 2 GiB ou de 100 mil
   arquivos, **When** o limite é atingido, **Then** a extração do
   filesystem para, `meta_unpack_status` registra o limite atingido, as
   strings vêm do arquivo bruto e o lote continua. **Given** um
   desempacotamento que passa de 300 s, **Then** a linha registra
   `limite_tempo`, sem fallback, e a execução sai com código diferente de
   0.
5. **Given** um filesystem com symlink ou path que aponta para fora do
   diretório temporário, **When** ele é desempacotado pelo extrator,
   **Then** nenhum arquivo é lido nem escrito fora do diretório temporário.
6. **Given** um arquivo extraído maior que `max_bytes`, **When** suas
   strings são lidas, **Then** a leitura para em `max_bytes` e o corte fica
   registrado.

---

### Edge Cases

- Sem Binwalk no PATH, as features estruturais saem vazias (0/nulo) e o
  aviso é só de nível debug. Uma varredura que termina com código de erro
  também resulta em features vazias, sem log. Nenhuma coluna `meta_*`
  registra a falha. Isso conflita com o princípio VI (fallback silencioso);
  a correção é FR-014 (Planejado).
- Com `max_bytes` de 5 MiB, 696 de 840 arquivos (83%) são cortados por
  `max_bytes`, e só 23,3% dos 16,1 GiB do dataset entram nas features
  estatísticas. A mediana é de 14,7 MiB; o maior arquivo tem 150,9 MiB
  (medido em 2026-09-24 sobre `features_v2.parquet`). O Binwalk, ao
  contrário, varre o arquivo inteiro. Nenhuma coluna `meta_*` registra o
  tamanho original: `meta_byte_len` é igual a `meta_bytes_used` (bytes
  lidos), e `meta_max_bytes_applied=True` sempre que há limite, mesmo em
  arquivo menor que ele. `meta_truncated` não registra esse corte: ele cobre
  só os limites de strings e de documento. As strings não dependem do corte:
  5 MiB já rendem ~62 mil strings, e só as `max_strings=2000` primeiras são
  usadas. A leitura completa em streaming é FR-015 (Planejado).
- `firmware_id` identifica só o prefixo lido. Dois binários diferentes com
  os mesmos primeiros `max_bytes` (mesmo bootloader e kernel, rootfs
  diferente) receberiam o mesmo `firmware_id` e seriam agregados como
  aliases na rotulagem. Medido em 2026-09-24: 699 `firmware_id` distintos e
  699 SHA256 de arquivo completo distintos, com 0 colisões. O risco é
  latente. Com FR-015 o `firmware_id` muda de valor (hash do novo prefixo);
  o hash do arquivo completo como identidade é FR-017 (Proposto).
- `meta_path` contém fabricante e modelo mesmo no modo inferência. `meta_*`
  não é feature (constituição, princípio III).
- `max_strings=2000` cobre só o cabeçalho, e os detectores de string ficam
  quase cegos. A correção é FR-016 (Planejado): os detectores varrem as
  strings do filesystem desempacotado, sem o limite do documento. Ver
  também `002-evidencias-seguranca`.
- Sem YAML, com `--config` apontando para arquivo inexistente (falha
  silenciosa) ou com `--override max_bytes=null`, `max_bytes` fica nulo e a
  leitura não tem limite (princípio VI). A correção é FR-019 (Planejado).
- Timeouts (Binwalk e desempacotamento) dependem da carga da máquina. Com
  FR-014 e FR-016, timeout é falha que exige rodar de novo, para que a
  mesma entrada não gere saídas diferentes (princípio V).
- As colunas `doc2vec_*` saem zeradas sem `models/doc2vec.model`, e
  `fs_type` e `compression_type` são texto. Desligar o Doc2Vec por padrão é
  FR-018 (Planejado, TickTick T07); a codificação de `fs_type` e
  `compression_type` fica com a preparação do dataset (TickTick T07 e
  T08).
- O guarda de vazamento confere só as chaves de feature do resultado. Não
  confere `label`/`meta_label` nem a seleção de colunas no treino, que ainda
  não existe.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001** [Implementado]: O sistema DEVE aceitar como entrada um arquivo
  único, um diretório (percorrido recursivamente) ou um arquivo `.txt` com
  um path por linha, e DEVE excluir arquivos ocultos e as extensões `.html`,
  `.pdf`, `.conf`, `.txt`, `.md`, `.csv`, `.json`, `.zip`, `.exe`, `.msi`,
  `.mib` e `.xml`.
- **FR-002** [Implementado]: O sistema DEVE ler a configuração de um YAML
  versionado (padrão `configs/feature_extraction.yaml`) e aplicar overrides
  `chave=valor` com dot-path passados na linha de comando. Sem YAML, DEVE
  usar os padrões `min_string_len` 4, `max_single_string_len` 1024,
  `max_strings` 2000, `max_doc_chars` 200000 e `max_bytes` nulo (sem
  limite).
- **FR-003** [Implementado]: O sistema DEVE ler só os primeiros `max_bytes`
  bytes de cada arquivo. Com `max_bytes<=0`, DEVE registrar o erro
  `max_bytes results in empty read`. Em falha de leitura ou arquivo vazio,
  DEVE registrar `empty firmware` com `read_ok=False`, sem interromper o
  lote.
- **FR-004** [Implementado]: O sistema DEVE definir `firmware_id` como o
  SHA256 dos bytes efetivamente lidos, isto é, dos primeiros `max_bytes`
  (5 MiB na configuração versionada), e não do arquivo inteiro.
  `firmware_id` DEVE ser nulo quando a leitura falha. É a identidade de
  conteúdo usada para agrupar aliases em `005-rotulagem-cve` (005/FR-012).
- **FR-005** [Implementado]: O sistema DEVE calcular as features
  estatísticas `entropy` (Shannon), `byte_mean`, `compress_ratio` (zlib) e
  `entropy_variance_across_sections`. Esta última usa blocos completos de
  64 KiB e DEVE valer 0.0 com menos de 2 blocos.
- **FR-006** [Implementado]: O sistema DEVE extrair strings ASCII
  imprimíveis com comprimento mínimo, truncamento por string, limite de
  quantidade (`max_strings`) e limite de caracteres do documento
  (`max_doc_chars`). DEVE marcar `meta_truncated=True` quando o limite de
  strings ou de documento é atingido.
- **FR-007** [Implementado]: O sistema DEVE derivar da varredura de
  assinaturas do Binwalk (timeout de 60 s) as features `n_filesystems`,
  `fs_type` (tipo mais frequente) e `compression_type` (primeira
  ocorrência). Sem Binwalk ou com falha da varredura, os valores DEVEM ser
  0/nulo e as chaves DEVEM estar presentes.
- **FR-008** [Implementado]: O vetor de features DEVE incluir as 11
  contagens/flags de strings e as 2 features de Binwalk definidas em
  `002-evidencias-seguranca` (002/FR-014), além das colunas `doc2vec_*`
  definidas em `007-embeddings-doc2vec` (007/FR-008).
- **FR-009** [Implementado]: O sistema DEVE gravar a saída em parquet
  (padrão) ou CSV, uma linha por arquivo, com `firmware_id`, as features e
  14 metadados com prefixo `meta_`: `read_ok`, `byte_len`, `bytes_used`,
  `max_bytes`, `truncated`, `max_bytes_applied`, `doc2vec_used`, `error`,
  `path`, `brand`, `model`, `label`, `version` e `version_source`.
- **FR-010** [Implementado]: Sem `--label-from-path` (modo inferência), o
  sistema DEVE gravar `meta_brand`, `meta_model`, `meta_label`,
  `meta_version` e `meta_version_source` como nulos.
- **FR-011** [Implementado]: O vetor de features NÃO DEVE conter campos de
  CVE (`cvss_max`, `cve_total`, `cve_count_*`) nem de identidade (`brand`,
  `model`, `version`, `version_source` e as formas com prefixo `meta_`).
- **FR-012** [Implementado]: O sistema DEVE produzir um resultado por path,
  na ordem de entrada, inclusive quando a extração do arquivo falha. DEVE
  paralelizar por `--workers` (padrão `min(n_arquivos, cpus)`; 1 força
  execução sequencial).
- **FR-013** [Implementado]: O sistema DEVE registrar em log o total de
  arquivos, o tempo total e o tempo médio por arquivo e, para cada arquivo,
  `path`, `read_ok`, `byte_len`, `doc2vec_used` e `error`.
- **FR-014** [Planejado, TickTick T11]: O Binwalk DEVE ser obrigatório,
  na versão 2.3.4 ou posterior: sem ele, ou com versão anterior, a
  extração DEVE falhar antes de processar o lote. Para cada arquivo, o
  sistema DEVE gravar `meta_binwalk_status`: `ok`, `erro`, `timeout` ou
  `nao_executado` (leitura falhou ou linha de exceção). `erro` DEVE gerar
  aviso no log sem interromper o lote. `timeout` DEVE ser falha que exige
  rodar de novo: a linha é gravada e a execução termina com código
  diferente de 0. Quando implementado, substitui a parte "sem Binwalk" de
  FR-007.
- **FR-015** [Planejado, TickTick T11]: O sistema DEVE calcular as features
  estatísticas, o `firmware_id` e as strings lendo o arquivo em blocos, com
  memória limitada que não cresce com o tamanho do arquivo, até `max_bytes`
  (256 MiB na configuração versionada), e DEVE gravar o tamanho original em
  `meta_file_size`. Quando implementado, substitui o valor de 5 MiB citado
  em FR-004.
- **FR-016** [Planejado, TickTick T11]: O sistema DEVE desempacotar
  estaticamente o filesystem do firmware com `binwalk -e` e os extratores
  que ele usa (lista e versões mínimas no plano, conferidas antes do lote,
  como em FR-014, e registradas no log), sem executar nenhum arquivo
  extraído, com `HOME` temporário (sem plugins do usuário), sem privilégio
  de administrador, num diretório temporário apagado ao fim, sem seguir
  symlinks e sem ler ou escrever fora desse diretório. Os limites
  configuráveis são 2 GiB extraídos, 100 mil arquivos e 300 s; a leitura de
  cada arquivo extraído para em `max_bytes`, e `meta_unpack_files_cut`
  conta os arquivos cortados.
  `meta_unpack_status` DEVE ser `ok`, `sem_filesystem`, `falha`,
  `limite_tamanho`, `limite_arquivos`, `limite_tempo` ou `nao_executado`;
  quando mais de um limite é atingido, vale o primeiro. `limite_tempo` é
  falha que exige rodar de novo, como `timeout` em FR-014. Com `ok`, os
  detectores de `002-evidencias-seguranca` DEVEM varrer em streaming as
  strings ASCII de todos os arquivos regulares extraídos, em ordem
  lexicográfica de path, sem o limite `max_strings`; o documento de strings
  (Doc2Vec) é deduplicado e limitado por `max_strings` e `max_doc_chars`.
  `ok` sem nenhuma string é resultado válido. Com `sem_filesystem`, `falha`,
  `limite_tamanho` ou `limite_arquivos`, as strings DEVEM vir do arquivo
  bruto, também em streaming. O sistema DEVE gravar `meta_strings_source`
  (`filesystem`, `blob` ou `nao_executado`). Quando implementados, FR-014 a
  FR-016 acrescentam `meta_binwalk_status`, `meta_file_size`,
  `meta_unpack_status`, `meta_strings_source` e `meta_unpack_files_cut` aos
  metadados de FR-009.
- **FR-017** [Proposto, TickTick T11]: O `firmware_id` DEVE ser o SHA256 do
  arquivo completo, independente de `max_bytes`.
- **FR-018** [Planejado, TickTick T07]: O Doc2Vec DEVE ficar desligado por
  padrão, também sem YAML, e ligado só por chave explícita. Desligado, o
  modelo não é carregado, não há aviso de modelo ausente
  (`007/FR-007`), `meta_doc2vec_used=False` (`007/FR-009`) e a tabela NÃO
  DEVE ter colunas `doc2vec_*`. Ligado, o comportamento de FR-008 e da
  `007-embeddings-doc2vec` se mantém.
- **FR-019** [Planejado, TickTick T11]: `max_bytes` DEVE ser obrigatório e
  positivo: sem YAML, o padrão é 256 MiB; valor nulo, não positivo ou
  `--config` apontando para arquivo inexistente DEVEM falhar antes do lote,
  com mensagem que cita a chave ou o arquivo. Quando implementado,
  substitui o padrão "sem limite" de FR-002 e o erro por arquivo de FR-003
  para `max_bytes<=0` (e o cenário US3.2).

### Key Entities *(include if feature involves data)*

- **Arquivo de firmware**: imagem binária de terceiros sob
  `dataset/raw/<fabricante>/<modelo>[_versão]/`. Entrada não confiável.
- **Registro de features**: uma linha da tabela `features.parquet` (ou CSV)
  por arquivo, com `firmware_id`, as features e os metadados `meta_*`.
- **Configuração de extração**: limites de leitura, de strings e de
  desempacotamento e parâmetros do Doc2Vec, vindos do YAML versionado e dos
  overrides.
- **Metadados de proveniência**: colunas `meta_*` que registram leitura,
  limites aplicados, erro e, fora do modo inferência, identidade do path.
  Não são features.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% dos paths de entrada têm uma linha na saída, inclusive
  os que falham.
- **SC-002**: zero colunas de CVE ou de identidade no vetor de features.
- **SC-003**: a extração dos 840 arquivos de `dataset/raw` gera 840 linhas
  com `meta_read_ok=True`. Resultado observado e registrado no `TODO.md`,
  request "Rodar extract-features e validar output gerado".
- **SC-004** [Planejado, TickTick T11]: 100% das linhas registram
  `meta_binwalk_status`, `meta_unpack_status` e `meta_strings_source`
  (`nao_executado` nas linhas sem varredura).
- **SC-005** [Planejado, TickTick T11]: `meta_bytes_used = meta_file_size`
  em 100% dos 840 arquivos atuais, com memória de pico que não cresce com o
  tamanho do arquivo.
- **SC-006** [Planejado, TickTick T07]: com a configuração versionada, zero
  colunas `doc2vec_*` na tabela.
- **SC-007** [Planejado, TickTick T11]: na reextração dos 840 arquivos,
  zero linhas com `timeout` ou `limite_tempo`, e a fração de arquivos
  regulares extraídos que contribuem com strings aos detectores fica
  registrada no `TODO.md`.

## Assumptions

- O Binwalk é dependência externa opcional; sem ele a extração roda e as
  features estruturais ficam vazias. Com FR-014 (Planejado), passa a ser
  obrigatório na versão 2.3.4 ou posterior.
- O filesystem extraído por FR-016 é apagado ao fim da extração. A spec
  012 (features do filesystem, TickTick T12) também vai usar os arquivos
  extraídos e precisa decidir se reaproveita este passo ou desempacota de
  novo.
- Os artefatos atuais em `dataset/processed/` foram gerados antes das
  colunas `meta_version` e `meta_version_source`. Medido:
  `features.parquet` tem 133 colunas e 12 `meta_*`; `features_v2.parquet`
  tem 134 colunas e 13 `meta_*`. O código atual gera 135 colunas e 14
  `meta_*`.
- A extração de versão a partir do path segue `004-versao-firmware`; os
  achados estruturados seguem `002-evidencias-seguranca`.
