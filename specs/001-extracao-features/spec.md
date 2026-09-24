# Feature Specification: Extração estática de features

**Feature Branch**: `docs/specs-retroativas`

**Created**: 2026-09-24

**Status**: Implementado

**Input**: User description: "Spec retroativa (Status Implementado) da extração estática de features em lote: leitura limitada do binário, features estatísticas, de strings ASCII e estruturais do Binwalk, tabela features.parquet/CSV com firmware_id, features e colunas meta_*, modo inferência sem identidade, guarda de vazamento e tolerância a falhas. Derivar só do código em master, testes, docs/PIPELINE.md e TODO.md."

## Clarifications

### Session 2026-09-24

- Varredura de ambiguidade (`/speckit.clarify`): sem ambiguidades
  críticas. Por ser spec retroativa, cada FR descreve o comportamento do
  código em `master`; as decisões em aberto (limite `max_bytes`, identidade
  do `firmware_id`, Binwalk ausente) são limitações registradas em Edge
  Cases e no `TODO.md`, não escolhas de spec. Nenhuma pergunta feita.
- Terminologia normalizada: "truncado" passa a significar só o corte por
  `max_strings`/`max_doc_chars` (`meta_truncated`); o corte por `max_bytes`
  é chamado "cortado por `max_bytes`".

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

---

### User Story 4 - Features estatísticas, de strings e estruturais (Priority: P2)

O pesquisador obtém, por firmware, features estatísticas dos bytes,
contagens derivadas das strings ASCII e features estruturais do Binwalk,
sempre com o mesmo conjunto de chaves.

**Why this priority**: o conjunto de chaves estável é o que permite montar
uma matriz de treino; os valores são o sinal que o classificador usa.

**Independent Test**: extrair um firmware com saída do Binwalk simulada e
outro sem Binwalk, e comparar as chaves.

**Acceptance Scenarios**:

1. **Given** uma varredura do Binwalk que reporta squashfs e lzma, **When**
   as features são extraídas, **Then** `n_filesystems`, `fs_type` e
   `compression_type` são preenchidos.
2. **Given** um ambiente sem Binwalk instalado, **When** as features são
   extraídas, **Then** as chaves de Binwalk e de padrões de string estão
   presentes no resultado.

---

### Edge Cases

- Sem Binwalk no PATH, as features estruturais saem vazias (0/nulo) e o
  aviso é só de nível debug. Uma varredura que termina com código de erro
  também resulta em features vazias, sem log. Nenhuma coluna `meta_*`
  registra a falha. Isso conflita com o princípio VI (fallback silencioso);
  registrado no `TODO.md`.
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
  usadas. Registrado no `TODO.md`.
- `firmware_id` identifica só o prefixo lido. Dois binários diferentes com
  os mesmos primeiros `max_bytes` (mesmo bootloader e kernel, rootfs
  diferente) receberiam o mesmo `firmware_id` e seriam agregados como
  aliases na rotulagem. Medido em 2026-09-24: 699 `firmware_id` distintos e
  699 SHA256 de arquivo completo distintos, com 0 colisões. O risco é
  latente; registrado no `TODO.md`.
- `meta_path` contém fabricante e modelo mesmo no modo inferência. `meta_*`
  não é feature (constituição, princípio III).
- `max_strings=2000` cobre só o cabeçalho, e os detectores de string ficam
  quase cegos. Ver o item "Documento de strings" do `TODO.md` e a spec
  `002-evidencias-seguranca`.
- As colunas `doc2vec_*` saem zeradas sem `models/doc2vec.model`, e
  `fs_type` e `compression_type` são texto. Ambos tratados em T07
  (subtask 4).
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
  conteúdo usada para agrupar aliases em `005-rotulagem-cve`.
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
  `002-evidencias-seguranca`, além das colunas `doc2vec_*` definidas em
  `007-embeddings-doc2vec`.
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

### Key Entities *(include if feature involves data)*

- **Arquivo de firmware**: imagem binária de terceiros sob
  `dataset/raw/<fabricante>/<modelo>[_versão]/`. Entrada não confiável.
- **Registro de features**: uma linha da tabela `features.parquet` (ou CSV)
  por arquivo, com `firmware_id`, as features e os metadados `meta_*`.
- **Configuração de extração**: limites de leitura e de strings e
  parâmetros do Doc2Vec, vindos do YAML versionado e dos overrides.
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

## Assumptions

- O Binwalk é dependência externa opcional; sem ele a extração roda e as
  features estruturais ficam vazias.
- Os artefatos atuais em `dataset/processed/` foram gerados antes das
  colunas `meta_version` e `meta_version_source`. Medido:
  `features.parquet` tem 133 colunas e 12 `meta_*`; `features_v2.parquet`
  tem 134 colunas e 13 `meta_*`. O código atual gera 135 colunas e 14
  `meta_*`.
- A extração de versão a partir do path segue `004-versao-firmware`; os
  achados estruturados seguem `002-evidencias-seguranca`.
