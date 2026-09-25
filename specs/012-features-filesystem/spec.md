# Feature Specification: Features do filesystem desempacotado

**Feature Branch**: `docs/escopo-restante`

**Created**: 2026-09-25

**Status**: Planejado

**Input**: User description: "Spec nova (Status Planejado, TickTick T12)
das features do filesystem extraído estaticamente pelo unpack de
`001/FR-016`: inventário de arquivos e binários ELF, postura de hardening
dos ELF (NX, PIE, RELRO, canary, FORTIFY) e funções perigosas importadas,
como colunas da tabela de features; sem unpack bem-sucedido, features
marcadas como indisponíveis; nenhuma feature derivada de identidade ou
CVE."

## Clarifications

### Session 2026-09-25

- Q: Como ler os ELF? → A: com pyelftools, declarado em `pyproject.toml`;
  promove de Proposto (escopo restante PR-04) só essa leitura; Ghidra
  continua Proposto (FR-003).
- Q: Como representar features indisponíveis? → A: nulo (NaN) no parquet,
  sem coluna extra; `pyproject.toml` passa a exigir `scikit-learn>=1.6`,
  primeira versão em que Extra Trees e Random Forest aceitam NaN
  (verificado com 1.7.2 em 2026-09-25) (FR-008).
- Q: Forma das funções perigosas? → A: proporção dos ELF lidos que
  importam cada função, 8 colunas (FR-005).
- Q: Arquitetura dos ELF como feature? → A: não; só como metadado
  `meta_fs_arch`, fora do vetor, porque acompanha chipset e linhagem do
  fabricante (constituição III) (FR-011).
- Q: Onde fica o código? → A: `src/features/filesystem.py`, chamado pela
  extração dentro do contexto do unpack da `001` (FR-001).

### Analyze 2026-09-25

- Q: Ordem entre a reextração da `001` e a `012`? → A: uma reextração só:
  001/T050 depende de 012/T013 (FR-001).
- Q: Fonte da lista de funções perigosas (o EMBA não tem S11 e o
  `config/functions.cfg` do S10/S13 não tem `execve`, `vsprintf` e
  `gets`)? → A: mantém as 8 funções; fonte: `functions.cfg` do EMBA para
  `strcpy`, `strcat`, `sprintf`, `system`, `popen`, e CWE-676/Flawfinder
  para `gets`, `vsprintf`, `execve` (FR-005).
- Q: Critérios das proteções? → A: os do checksec 2.7.1 (`filecheck`);
  oráculo do SC-001: flags de compilação registradas pelo script das
  fixtures, conferidas com o checksec 2.7.1 (FR-004).
- Q: ELF estático? → A: sai dos denominadores de canary, FORTIFY e
  importações, fica em NX, PIE e RELRO, e é contado em
  `unpacked_n_elf_static` (FR-004, FR-005).
- Q: Falhas fora do ELF malformado? → A: `meta_fs_status` (`ok`, `erro`,
  `nao_executado`) e `meta_fs_error`; com `erro`, só as `unpacked_*`
  ficam nulas e a linha mantém as features da `001`; a `008` exclui
  `meta_fs_status=erro` como `falha_extracao` (FR-012).
- Q: Que arquivos contar? → A: só os que estão dentro das raízes de
  filesystem extraídas (não os carvados intermediários); ELF com o mesmo
  SHA256 conta uma vez (FR-002).
- Q: Teto do pyelftools? → A: `pyelftools<0.33` em qualquer Python, para
  a mesma versão em todos os ambientes (FR-003).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Inventário do filesystem (Priority: P1)

O pesquisador obtém, para cada firmware com unpack bem-sucedido, quantos
arquivos regulares e quantos binários ELF (executáveis e bibliotecas) o
filesystem extraído tem (Costin et al., USENIX Security 2014).

**Why this priority**: é a base das features de US2 e US3 e mede o
tamanho da superfície do build.

**Independent Test**: extrair features de um diretório de teste com
arquivos comuns, um ELF executável e uma biblioteca, e conferir as
contagens.

**Acceptance Scenarios**:

1. **Given** um filesystem extraído com 3 arquivos regulares, 1 ELF
   executável e 1 biblioteca ELF, **When** as features são extraídas,
   **Then** as contagens são 5 arquivos, 2 ELF, 1 executável e 1
   biblioteca.
2. **Given** um symlink no filesystem extraído, **When** as features são
   extraídas, **Then** ele não é seguido nem contado como arquivo regular
   (`001/FR-016`).

---

### User Story 2 - Postura de hardening dos binários (Priority: P1)

O pesquisador obtém a proporção dos ELF com cada proteção de build (NX,
PIE, RELRO completo e parcial, stack canary, FORTIFY), lida só dos
cabeçalhos e tabelas do ELF, sem executar nada (constituição I).

**Why this priority**: é um sinal de postura de segurança distinto da
CVE específica (OWASP FSTM; checksec), com menor risco de correlação
direta com o rótulo.

**Independent Test**: extrair features de ELF de teste compilados com e
sem cada proteção e conferir as proporções.

**Acceptance Scenarios**:

1. **Given** dois ELF, um com PIE e um sem, **When** as features são
   extraídas, **Then** a proporção de PIE é 0,5.
2. **Given** um ELF com `GNU_RELRO` e `BIND_NOW`, **When** as features são
   extraídas, **Then** ele conta como RELRO completo e não como parcial.

---

### User Story 3 - Funções perigosas importadas (Priority: P1)

O pesquisador obtém, para cada função de uma lista fixa (`system`,
`popen`, `execve`, `strcpy`, `strcat`, `sprintf`, `vsprintf`, `gets`),
a proporção dos ELF que a importam pela tabela de símbolos dinâmicos (EMBA
S10/S11).

**Why this priority**: uso de funções inseguras é indício direto de
código vulnerável, lido estaticamente.

**Independent Test**: extrair features de ELF de teste que importam
algumas funções da lista e conferir as contagens.

**Acceptance Scenarios**:

1. **Given** quatro ELF lidos, dois que importam `strcpy` e um que importa
   `system`, **When** as features são extraídas, **Then** a proporção de
   `strcpy` é 0,5 e a de `system`, 0,25.
2. **Given** um ELF que só define `strcpy` (não importa), **When** as
   features são extraídas, **Then** ele não conta como importador de `strcpy`.

---

### User Story 4 - Falha visível e sem vazamento (Priority: P2)

O pesquisador vê quando as features do filesystem não puderam ser
calculadas e por quê, e a banca confere que nenhuma delas usa identidade
ou CVE (constituição III e VI).

**Why this priority**: zero silencioso para firmware sem filesystem seria
sinal falso; nome de coluna com identidade seria vazamento.

**Independent Test**: extrair features de firmware sem filesystem, com
unpack em falha e com ELF truncado, e rodar o teste de guarda.

**Acceptance Scenarios**:

1. **Given** um firmware com `meta_unpack_status=sem_filesystem`, **When**
   as features são extraídas, **Then** as colunas da 012 ficam nulas, não
   zero, e `meta_fs_status=nao_executado`.
2. **Given** um ELF truncado no filesystem extraído, **When** as features
   são extraídas, **Then** o lote não para, o ELF é contado como
   malformado e fica fora das proporções.
3. **Given** a tabela de features, **When** o teste de guarda roda,
   **Then** nenhuma coluna da 012 tem fabricante, modelo, versão ou campo
   de CVE no nome.
4. **Given** um erro de leitura do diretório extraído, **When** as
   features são extraídas, **Then** `meta_fs_status=erro`,
   `meta_fs_error` cita o erro, as `unpacked_*` ficam nulas e as demais
   features da linha são mantidas.
5. **Given** um filesystem só com módulos `.ko`, **When** as features são
   extraídas, **Then** `unpacked_n_elf` conta os módulos e as proporções
   ficam nulas.

---

### Edge Cases

- ELF de arquitetura ou classe (32/64 bits, endianness) diferentes no
  mesmo filesystem.
- ELF estático, sem tabela de símbolos dinâmicos: fora dos denominadores
  de canary, FORTIFY e importações (FR-004, FR-005).
- Módulos (`.ko`) são ELF relocáveis; `vmlinux` é `ET_EXEC` sem
  `PT_INTERP`; `ET_CORE` e outros tipos contam só em `unpacked_n_elf`
  (FR-002).
- Saída do extrator com arquivos carvados intermediários e rootfs
  repetido: só as raízes de filesystem contam, e ELF repetido conta uma
  vez (FR-002).
- Firmware com milhares de ELF: custo por arquivo e limite de
  `001/FR-016`.
- Arquivo cortado em `max_bytes` (`meta_unpack_files_cut`, `001/FR-016`):
  cabeçalho ELF presente, tabelas fora do trecho lido.
- Nenhum ELF no filesystem: proporções sem denominador.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001** [Planejado, TickTick T12]: Com `meta_unpack_status=ok`
  (`001/FR-016`), o sistema DEVE calcular as features desta spec sobre o
  diretório extraído, antes da limpeza, e gravá-las como colunas da
  tabela de features de `001-extracao-features`.
- **FR-002** [Planejado, TickTick T12]: O sistema DEVE contar, só dentro
  das raízes de filesystem extraídas (sem os arquivos carvados
  intermediários do extrator), arquivos regulares, ELF, ELF executáveis
  (`ET_EXEC`, ou `ET_DYN` com `DT_DEBUG`, como no checksec 2.7.1),
  bibliotecas compartilhadas ELF (`ET_DYN` sem `DT_DEBUG`) e ELF
  estáticos (sem tabela de símbolos dinâmicos), sem seguir symlinks,
  identificando ELF pelo cabeçalho, não pela extensão. ELF com o mesmo
  SHA256 conta uma vez. `ET_REL`, `ET_CORE` e outros tipos contam só no
  total de ELF. Todas as colunas desta spec DEVEM ter o prefixo
  `unpacked_` (não `fs_`, que colide com `fs_type__*` de `008/FR-010`).
- **FR-003** [Planejado, TickTick T12]: O sistema DEVE ler cada ELF
  estaticamente com pyelftools (`pyelftools<0.33`, declarado em
  `pyproject.toml`), sem executar nenhum arquivo, com a leitura limitada
  por `max_bytes` sem carregar o arquivo inteiro em memória; ELF cortado em
  `max_bytes` é malformado (FR-006).
- **FR-004** [Planejado, TickTick T12]: O sistema DEVE calcular, pelos
  critérios do checksec 2.7.1 (`filecheck`), entre os ELF executáveis e
  bibliotecas lidos com sucesso, a proporção com NX (`PT_GNU_STACK` sem
  permissão de execução), RELRO completo (`PT_GNU_RELRO` com `BIND_NOW` —
  `DT_BIND_NOW`, `DF_BIND_NOW` ou `DF_1_NOW` — ou sem `.got.plt`) e RELRO
  parcial (`PT_GNU_RELRO` nas demais condições); e, entre os que têm
  tabela de símbolos dinâmicos, a proporção com stack canary
  (`__stack_chk_fail`, `__stack_chk_guard` ou `__intel_security_cookie`
  importado) e FORTIFY (alguma função `__*_chk` importada); e, só entre
  os executáveis, a proporção com PIE (`ET_DYN` com `DT_DEBUG`). ELF
  relocáveis e de outros tipos ficam fora das proporções.
- **FR-005** [Planejado, TickTick T12]: O sistema DEVE contar, para cada
  função da lista fixa da configuração versionada (`system`, `popen`,
  `execve`, `strcpy`, `strcat`, `sprintf`, `vsprintf`, `gets`), a proporção
  dos ELF executáveis e bibliotecas lidos com sucesso e com tabela de
  símbolos dinâmicos que a importam (símbolo indefinido nessa tabela), uma
  coluna por função. Fontes da lista: `config/functions.cfg` do EMBA
  (`strcpy`, `strcat`, `sprintf`, `system`, `popen`) e CWE-676/Flawfinder
  (`gets`, `vsprintf`, `execve`).
- **FR-006** [Planejado, TickTick T12]: ELF malformado ou cortado (magic
  válido, leitura falha) DEVE ser contado em `meta_fs_elf_malformed` e em
  `unpacked_n_elf`, e ficar fora das contagens de executáveis,
  bibliotecas e estáticos e de todas as proporções, sem interromper o lote
  (constituição VI).
- **FR-007** [Planejado, TickTick T12]: Nenhuma feature desta spec DEVE
  depender de fabricante, modelo, versão, caminho do arquivo no dataset ou
  dado de CVE; o teste de guarda de vazamento DEVE cobrir as colunas novas
  (constituição III).
- **FR-008** [Planejado, TickTick T12]: Sem `meta_unpack_status=ok`, as
  colunas desta spec DEVEM ficar nulas (NaN), nunca zero; o
  `pyproject.toml` DEVE exigir `scikit-learn>=1.6` para que Extra Trees e
  Random Forest aceitem os nulos.
- **FR-009** [Planejado, TickTick T12]: Com unpack `ok`, as contagens
  seguem FR-002 (zero quando não há o tipo); toda proporção sem
  denominador DEVE ficar nula (sem executável ou biblioteca lido, sem ELF
  com símbolos dinâmicos, ou sem executável para PIE).
- **FR-010** [Planejado, TickTick T12]: O sistema DEVE registrar em log,
  por lote, quantos firmwares tiveram as features calculadas, quantos ELF
  foram lidos e quantos malformados (constituição V).
- **FR-011** [Planejado, TickTick T12]: O sistema DEVE gravar em
  `meta_fs_arch` a arquitetura mais frequente dos ELF lidos (`e_machine`),
  fora do vetor de features, nula sem ELF lido e com empate resolvido pela
  ordem alfabética; a arquitetura NÃO DEVE entrar como feature
  (constituição III).
- **FR-012** [Planejado, TickTick T12]: O sistema DEVE gravar
  `meta_fs_status` (`ok`, `erro` ou `nao_executado`) e `meta_fs_error`
  (mensagem ou nulo). Erro de percurso ou exceção no cálculo DEVE resultar
  em `erro`, com as `unpacked_*` nulas e as demais features da linha
  mantidas; sem unpack `ok`, `nao_executado`. A exclusão de
  `meta_fs_status=erro` do treino é da `008` (`008/FR-007`).

### Key Entities *(include if feature involves data)*

- **Filesystem extraído**: diretório temporário de `001/FR-016`.
- **ELF analisado**: tipo (executável, biblioteca, relocável), proteções e
  funções importadas.
- **Features do filesystem**: colunas novas na tabela de features.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001** [Planejado, TickTick T12]: nas fixtures de teste, 100% das
  proteções e importações conferem com as flags de compilação registradas
  pelo script das fixtures, conferidas com o checksec 2.7.1.
- **SC-002** [Planejado, TickTick T12]: 0 firmwares sem unpack `ok` com
  valor zero nas colunas da 012.
- **SC-003** [Planejado, TickTick T12]: 0 colunas da 012 na lista
  proibida do teste de guarda, com fixture que chega a unpack `ok`; a
  identidade codificada nos valores é medida pelo baseline de identidade
  e pela ablation F (`011/FR-004`, `011/FR-005`).
- **SC-004** [Planejado, TickTick T12]: um ELF malformado não interrompe o
  lote e aparece em `meta_fs_elf_malformed`.

## Assumptions

- O unpack, o isolamento, os limites e o estado `meta_unpack_status` são
  de `001/FR-016`; esta spec só lê o diretório extraído.
- As colunas entram no vetor pela `008` (`008/FR-003`) e formam o grupo F
  das ablations (`011/FR-005`).
- Versão de componente (SBOM) fica fora: usaria a mesma informação do
  rótulo (constituição III).
- Na junção da `008`, nulo contra nulo entre aliases é igual (`008/FR-002`).
