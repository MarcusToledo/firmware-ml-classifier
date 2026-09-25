# Feature Specification: Busca de CVEs na NVD

**Feature Branch**: `docs/specs-retroativas`

**Created**: 2026-09-24

**Status**: Misto

**Input**: User description: "Spec retroativa (Status Implementado) da busca de CVEs na NVD por fabricante/modelo: pares únicos lidos do parquet de features, resolução de CPE oficial com virtualMatchString e fallback keywordSearch, normalização de fabricante, cache JSON versionado com CVEs, CVSS, severidade e configurations. Única etapa com rede. Derivar só do código em master, testes, docs/PIPELINE.md e TODO.md."

## Clarifications

### Session 2026-09-24

- Varredura de ambiguidade (`/speckit.clarify`, histórico da spec
  retroativa): sem ambiguidades críticas. Os FRs `[Implementado]` descrevem
  o comportamento do código em `master`; os pontos em aberto na época
  (`--output` padrão v1, entrada antiga mantida com `--force` após falha,
  data da consulta não registrada) ficaram em Edge Cases. Nenhuma pergunta
  feita nessa varredura.
- Terminologia normalizada: "par" é o fabricante/modelo como aparece no
  parquet de features (minúsculas, sem espaços nas pontas), usado como
  chave do cache; "forma NVD" é o par depois da normalização usada nas
  consultas.

### Session 2026-09-24 (escopo restante, TickTick T11)

- Q: Com `--force`, o que fazer com a entrada antiga quando a nova
  consulta falha, e qual o código de saída? → A: remover a entrada (o par
  fica ausente e a rotulagem acusa, 005/FR-003); qualquer par com falha,
  com ou sem `--force`, faz a execução terminar com código diferente de 0
  (FR-013).
- Q: Como registrar a data da consulta e o que fazer com as entradas sem
  data? → A: `fetched_at` obrigatório em toda entrada nova (ISO 8601, UTC);
  entrada sem data é tratada como esquema antigo; uma nova busca completa
  gera o cache, também porque o `cvss_max` de FR-016 exige as métricas
  brutas (FR-014).
- Q: Qual o `--output` padrão? → A: `dataset/processed/cve_cache_v2.json`
  (FR-015).
- Q: Como calcular `cvss_max` com mais de uma métrica? → A: maior
  `baseScore` entre as fontes (NVD e CNA) da versão CVSS preferida (3.1,
  senão 3.0, senão 2); `severity` da métrica escolhida (FR-016).
- Q: Como escolher o CPE de um par? → A: percorrer o dicionário inteiro,
  preferir parte `o` e usar `h` só sem `o`; mais de um CPE distinto casando
  é ambiguidade registrada na entrada, e o par cai na busca por texto
  (FR-018).
- Analyze (2026-09-24), decisões do pesquisador: entradas novas com
  `schema_version: 3`, exigido também pela rotulagem (I1; FR-014 e
  005/FR-026); CPEs distintos são tuplas (parte, fabricante, produto)
  diferentes, depois de generalizar a versão (A1, FR-018); metadados da
  execução ao lado do cache (C2, FR-021).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Cache de CVE por par, retomável (Priority: P1)

O pesquisador aponta a busca para o parquet de features extraído com
`--label-from-path` e recebe um cache JSON com uma entrada por par
fabricante/modelo. Uma execução interrompida pode ser retomada sem refazer
os pares já buscados.

**Why this priority**: a rotulagem só lê o cache local. Sem ele não há
rótulo de treino (constituição, princípio II).

**Independent Test**: extrair os pares de uma tabela com linhas repetidas e
vazias e conferir a lista; rodar com `--dry-run` e conferir que nenhuma
requisição é feita.

**Acceptance Scenarios**:

1. **Given** uma tabela com `meta_brand`/`meta_model` iguais a
   `Netgear/DIR-300`, `netgear/dir-300` e ` TP-Link /AC1750`, **When** os
   pares são extraídos, **Then** o resultado é `netgear/dir-300` e
   `tp-link/ac1750`, em ordem alfabética.
2. **Given** linhas com fabricante ou modelo vazio ou nulo, **When** os
   pares são extraídos, **Then** essas linhas são ignoradas.
3. **Given** um par já presente no cache com `schema_version: 2`, **When**
   o pesquisador roda sem `--force`, **Then** o par é pulado sem
   requisição.
4. **Given** o mesmo par, **When** o pesquisador roda com `--force`,
   **Then** o par é consultado de novo e a entrada é substituída.
5. **Given** qualquer tabela, **When** o pesquisador roda com `--dry-run`,
   **Then** os pares e sua forma NVD são listados, sem requisição e sem
   leitura ou escrita do cache.

---

### User Story 2 - Evidência auditável por CVE (Priority: P1)

A banca confere, para cada par, se as CVEs vieram de um CPE oficial da NVD
ou de busca por texto, e tem acesso às `configurations` originais que a
rotulagem avalia por versão.

**Why this priority**: o rótulo precisa ser externo ao classificador e
auditável (constituição, princípio II). Sem a origem e as configurações
não é possível conferir por que uma CVE foi ligada a um firmware.

**Independent Test**: simular o dicionário de CPE e a consulta de CVEs e
conferir `source`, `cpe_name` e os campos de cada CVE na entrada.

**Acceptance Scenarios**:

1. **Given** o dicionário de CPE com
   `cpe:2.3:o:dlink:dir-300_firmware:1.2:*:*:*:*:*:*:*` e o par
   `dlink/dir300`, **When** o CPE é resolvido, **Then** `cpe_name` é
   `cpe:2.3:o:dlink:dir-300_firmware:*:*:*:*:*:*:*:*`.
2. **Given** um CPE com `update` e `edition` específicos
   (`1.2:rev1:home`), **When** o CPE é resolvido, **Then** todos os campos
   a partir da versão viram `*`.
3. **Given** um CPE resolvido, **When** as CVEs são buscadas, **Then** a
   consulta usa `virtualMatchString` e a entrada tem `source="cpe"`.
4. **Given** nenhum CPE correspondente, **When** as CVEs são buscadas,
   **Then** a consulta é por texto, a entrada tem `source="keyword"` e cada
   CVE guarda `id`, `cvss_max`, `severity` e as `configurations` originais.
5. **Given** uma CVE com métricas CVSS v3.1 e v2, **When** ela é gravada,
   **Then** `cvss_max` e `severity` vêm da v3.1; sem nenhuma métrica, são
   `0.0` e `NONE`.

---

### User Story 3 - Nome interno vira termo da NVD (Priority: P2)

O pesquisador usa os nomes de diretório do `dataset/raw` como estão, e a
busca os converte para a grafia que a NVD usa.

**Why this priority**: grafia errada faz a NVD devolver zero CVEs, o que a
rotulagem leria como "sem CVE conhecida". Foi o caso dos 43 pares `tp_link`
no cache v1.

**Independent Test**: normalizar fabricantes e modelos com hífen,
underscore e sem separador e conferir a saída.

**Acceptance Scenarios**:

1. **Given** os fabricantes `dlink`, `tplink` e `tp_link`, **When** são
   normalizados, **Then** viram `d-link`, `tp-link` e `tp-link`; `netgear`
   e `belkin` ficam iguais.
2. **Given** o modelo `dir300`, **When** é normalizado, **Then** vira
   `DIR-300`.
3. **Given** os modelos `td_w8950n` e `f5d7230_4`, **When** são
   normalizados, **Then** viram `TD-W8950N` e `F5D7230-4`, sem underscore.

---

### User Story 4 - Falha de rede não perde progresso nem cria evidência (Priority: P2)

O pesquisador roda a busca por horas contra uma API pública com limite de
taxa. Uma falha num par não derruba a execução, não perde os pares já
buscados e não grava uma entrada que pareça "sem CVE".

**Why this priority**: consulta ausente no cache é erro, não evidência de
ausência de CVE (constituição, princípio II). Uma entrada vazia gravada
após falha viraria rótulo falso.

**Independent Test**: sem teste automatizado; conferível simulando uma
falha HTTP num par e inspecionando o log e o cache.

**Acceptance Scenarios**:

1. **Given** um par cuja consulta falha com erro HTTP, de conexão ou
   timeout, **When** a execução continua, **Then** o log registra
   `[FAIL]` com o par, o par não ganha entrada no cache e o próximo par é
   processado.
2. **Given** uma execução interrompida por exceção, **When** ela termina,
   **Then** o cache em disco contém todos os pares buscados até ali.
3. **Given** uma execução longa, **When** 10 pares são buscados com
   sucesso, **Then** o cache é gravado em disco.

---

### User Story 5 - Cache datado, sem evidência falsa e com CPE inequívoco (Priority: P1) *(Planejado)*

O pesquisador gera o cache num path canônico, com a data de cada consulta,
sem entradas velhas mascarando falhas e com o CPE escolhido sem
ambiguidade; a banca sabe de quando é o retrato da NVD por trás de cada
rótulo.

**Why this priority**: o rótulo depende do cache (constituição, princípio
II). Sem data não há reprodução (princípio V); entrada velha após falha,
CPE ambíguo e `cvss_max` subestimado mudam rótulos sem aviso (TickTick
T11).

**Independent Test**: simular respostas da NVD (falha, várias métricas,
várias páginas de CPE, CPEs ambíguos) e conferir o cache e o código de
saída.

**Acceptance Scenarios**:

1. **Given** um par já em cache e `--force`, **When** a nova consulta
   falha, **Then** a entrada do par é removida e a execução termina com
   código diferente de 0. **Given** uma falha sem `--force`, **Then** a
   execução também termina com código diferente de 0.
2. **Given** uma consulta com sucesso, **When** a entrada é gravada,
   **Then** ela tem `schema_version: 3` e `fetched_at` em ISO 8601 UTC.
   **Given** uma entrada em cache com `schema_version` diferente de 3 e sem
   `--force`, **When** o par é visitado, **Then** a execução é
   interrompida com erro de esquema antigo.
3. **Given** uma execução sem `--output`, **When** o cache é gravado,
   **Then** o arquivo é `dataset/processed/cve_cache_v2.json`.
4. **Given** uma CVE com métrica v3.1 da NVD 7.5 e da CNA 9.8, **When** a
   CVE é gravada, **Then** `cvss_max=9.8` e `severity=CRITICAL`.
5. **Given** um parquet sem `--label-from-path` (0 pares), **When** a busca
   roda, **Then** ela falha com código diferente de 0. **Given** linhas com
   fabricante ou modelo nulo, **Then** o log informa quantas foram
   descartadas.
6. **Given** um dicionário de CPE com o produto na segunda página, **When**
   o CPE é resolvido, **Then** ele é encontrado. **Given** um produto só com
   CPE de parte `h`, **Then** o CPE `h` é usado. **Given** várias versões
   do mesmo produto `o`, **Then** não há ambiguidade. **Given** dois
   produtos `o` distintos que casam o par, **Then** a entrada registra os
   candidatos em `cpe_candidates` e usa a busca por texto.
7. **Given** uma execução que grava o cache, **When** ela termina, **Then**
   `cve_cache_v2.meta.json` ao lado do cache registra os argumentos, o
   caminho e o SHA256 de `--features`, o commit do código, o início e o
   fim da execução e as contagens de pares e falhas.

---

### Edge Cases

- O fluxo da linha de comando (pulo de par em cache, validação de schema,
  falha de rede, gravação final, `--dry-run`, espera entre requisições,
  chave de API) não tem teste automatizado. Ver "Sem verificação" no
  `plan.md`.
- A busca não está registrada como comando instalado em `pyproject.toml`
  (`[project.scripts]`), ao contrário de `extract-features` e
  `generate-labels`; roda só como script. Registrar é FR-020 (Proposto).
- O `--output` padrão é `dataset/cve_cache.json`, o cache v1, de esquema
  agregado (`cvss_max`, `cve_count_*`, `cve_total`, sem `schema_version`;
  336 entradas, medido em 2026-09-24). O artefato em uso é
  `dataset/cve_cache_v2.json`. Rodar com o padrão e sem `--force`
  interrompe a execução com erro de schema antigo no primeiro par já em
  cache; com `--force`, os pares do parquet são regravados no esquema v2 e
  as outras 26 entradas v1 ficam, e o arquivo passa a misturar esquemas. O
  `README.md` também usa os caminhos v1. A correção é FR-015 (Planejado):
  padrão `dataset/processed/cve_cache_v2.json`.
- Os 43 pares `tp_link/*` do cache v1 (`dataset/cve_cache.json`) foram
  buscados com o termo antigo, antes da correção do alias, e têm
  `cve_total=0`. No `dataset/cve_cache_v2.json` as 43 entradas já têm
  `vendor="tp-link"`, a grafia corrigida (38 por texto, 5 por CPE, 37 sem
  CVE). Medido em 2026-09-24; o pesquisador marcou o item de re-busca do
  `TODO.md` como obsoleto para o v2.
- Só o fabricante é normalizado na chave da NVD; a chave do cache usa o
  nome interno. `tplink/<modelo>` e `tp_link/<modelo>` viram entradas e
  consultas separadas, e modelos iguais com grafias diferentes não são
  consolidados (itens de `tplink/` × `tp_link/` no `TODO.md`).
- As regras de normalização de fabricante e modelo ainda não estão
  centralizadas num módulo próprio; pendência do review do Kody no PR #5,
  registrada no `TODO.md`.
- Um par que falha por rede fica fora do cache e a execução termina com
  sucesso (código de saída 0); a falha aparece só no log e no resumo
  (`Failed`). A rotulagem acusa o par ausente como erro
  (005/FR-003). Com `--force`, porém, a entrada anterior do par
  permanece no cache sem marca de que a nova consulta falhou. A correção é
  FR-013 (Planejado).
- Não há nova tentativa nem espera extra para limite de taxa da NVD
  (HTTP 403/503): o par vira falha. Exceções fora de erro HTTP, de conexão
  ou timeout (ex.: resposta JSON inválida) interrompem a execução; o cache
  é gravado antes de sair. Nova tentativa é FR-019 (Proposto).
- Um parquet extraído sem `--label-from-path` tem `meta_brand` e
  `meta_model` nulos (001/FR-010): a busca encontra 0 pares e termina sem
  erro, com o aviso só no log de nível info. Linhas com fabricante ou
  modelo nulo são descartadas sem contagem no log. A correção é FR-017
  (Planejado).
- A resolução de CPE lê só a primeira página (até 2000 produtos) do
  dicionário, aceita só CPE de parte `o` (sistema operacional/firmware) e
  usa o primeiro que coincide. Par cujo produto na NVD é só `h`
  (hardware) cai na busca por texto. A correção é FR-018 (Planejado).
- A busca por texto (`source="keyword"`) casa o texto da CVE e pode trazer
  CVE de outro produto. A filtragem é da rotulagem, pelas
  `configurations` (`005-rotulagem-cve`, 005/FR-006 e 005/FR-007).
- `cvss_max` de cada CVE é o `baseScore` da primeira métrica da versão
  CVSS preferida, não o máximo entre as fontes (NVD e CNA). Métrica v2 sem
  `baseSeverity` recebe `MEDIUM`. A correção é FR-016 (Planejado).
- As entradas não registram a data da consulta. A NVD muda com o tempo;
  reproduzir um rótulo exige o arquivo de cache, e não há como saber a
  data do retrato da NVD que ele contém. A correção é FR-014 (Planejado),
  com uma nova busca completa.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001** [Implementado]: O sistema DEVE ler do parquet de features
  indicado em `--features` (obrigatório) só as colunas `meta_brand` e
  `meta_model`, preenchidas apenas na extração com `--label-from-path`
  (001/FR-010). DEVE derivar os pares únicos fabricante/modelo em
  minúsculas e sem espaços nas pontas, em ordem alfabética, e DEVE ignorar
  linhas com fabricante ou modelo nulo ou vazio.
- **FR-002** [Implementado]: O sistema DEVE converter o par para a forma
  NVD antes de consultar: o fabricante por tabela de aliases (`dlink` →
  `d-link`; `tplink` e `tp_link` → `tp-link`; os demais sem mudança); o
  modelo com `_` trocado por `-`, em maiúsculas e, se não houver hífen,
  com hífen inserido entre um prefixo de 2 a 5 letras e o resto iniciado
  por dígito (`dir300` → `DIR-300`). A forma NVD do modelo NÃO DEVE conter
  underscore.
- **FR-003** [Implementado]: O sistema DEVE consultar o dicionário de CPE
  da NVD pela forma NVD `"<fabricante> <modelo>"` e aceitar o primeiro
  nome CPE 2.3 de parte `o` cujo fabricante e produto coincidam com o par,
  comparando só letras e dígitos em minúsculas e removendo o sufixo
  `firmware` do produto. DEVE generalizar para `*` todos os campos a
  partir da versão.
- **FR-004** [Implementado]: Com CPE resolvido, o sistema DEVE buscar as
  CVEs por `virtualMatchString` com o CPE generalizado e registrar
  `source="cpe"`. Sem CPE, DEVE buscar por `keywordSearch` com a forma NVD
  `"<fabricante> <modelo>"`, registrar `source="keyword"` e `cpe_name`
  nulo. DEVE percorrer todas as páginas (2000 resultados por página) até
  `totalResults`.
- **FR-005** [Implementado]: Para cada CVE, o sistema DEVE gravar `id`,
  `cvss_max`, `severity` e `configurations`, estas copiadas da NVD sem
  alteração. `cvss_max` e `severity` DEVEM vir da primeira métrica CVSS
  v3.1, senão v3.0, senão v2 (v2 sem severidade: `MEDIUM`); sem métrica,
  `0.0` e `NONE`. `severity` DEVE estar em maiúsculas.
- **FR-006** [Implementado]: O sistema DEVE gravar um cache JSON em
  `--output` (padrão `dataset/cve_cache.json`), indexado por
  `"<fabricante>/<modelo>"` na forma do par em minúsculas e sem espaços nas
  pontas (FR-001). Cada entrada nova ou substituída DEVE ter
  `schema_version: 2`, `source`, `vendor` e `model` na forma NVD,
  `cpe_name` e a lista `cves`. Entradas já existentes de outros pares DEVEM
  ser preservadas, mesmo quando usam o esquema antigo.
- **FR-007** [Implementado]: Sem `--force`, o sistema DEVE pular sem
  requisição o par que já tem entrada no cache. Antes de pular, DEVE
  interromper a execução com erro se a entrada não for um objeto com a
  lista `cves` (schema antigo) ou se `schema_version` for diferente de 2.
  Com `--force`, DEVE consultar o par de novo e substituir a entrada.
- **FR-008** [Implementado]: Em erro HTTP, de conexão ou timeout (30 s por
  requisição) na consulta de um par, o sistema DEVE registrar `[FAIL]` em
  log de erro, contar a falha e seguir para o próximo par. NÃO DEVE gravar
  entrada para o par que falhou.
- **FR-009** [Implementado]: O sistema DEVE gravar o cache em disco a cada
  10 pares buscados com sucesso e ao fim da execução, inclusive quando ela
  é interrompida por exceção.
- **FR-010** [Implementado]: O sistema DEVE esperar `--delay` segundos
  entre a consulta de CPE e a de CVEs, entre páginas e entre pares
  consultados; o padrão é 6 s sem a variável de ambiente `NVD_API_KEY` e
  1 s com ela. Com `NVD_API_KEY`, DEVE enviar a chave no cabeçalho
  `apiKey`.
- **FR-011** [Implementado]: Com `--dry-run`, o sistema DEVE listar os
  pares e, quando diferente, a forma NVD (`<par> -> <fabricante> <modelo>`)
  sem fazer requisição e sem ler nem gravar o cache.
- **FR-012** [Implementado]: O sistema DEVE registrar em log o número de
  registros lidos, de pares e de entradas já no cache; por par, o
  progresso (`[FETCH]`, `[SKIP]`, `[FAIL]`) e, em sucesso, o número de CVEs
  e o maior `cvss_max`; e, ao fim, o resumo com pares buscados, em cache,
  com falha e o total de CVEs.
- **FR-013** [Planejado, TickTick T11]: Com `--force`, quando a nova
  consulta de um par falha, o sistema DEVE remover a entrada anterior do
  par. Com qualquer par com falha, com ou sem `--force`, a execução DEVE
  terminar com código diferente de 0, depois de processar os demais pares
  e gravar o cache. Complementa FR-008 quando implementado.
- **FR-014** [Planejado, TickTick T11]: Cada entrada nova ou substituída
  DEVE ter `schema_version: 3` e `fetched_at`, a data e hora da consulta à
  NVD em ISO 8601 (UTC). A validação de FR-007 DEVE tratar como esquema
  antigo toda entrada com `schema_version` diferente de 3. Amplia os
  campos e substitui a versão 2 de FR-006 e FR-007 quando implementado; a
  rotulagem passa a exigir 3 (005/FR-026).
- **FR-015** [Planejado, TickTick T11]: O `--output` padrão DEVE ser
  `dataset/processed/cve_cache_v2.json`. Substitui o padrão de FR-006
  quando implementado.
- **FR-016** [Planejado, TickTick T11]: O `cvss_max` de cada CVE DEVE ser o
  maior `baseScore` entre as métricas de todas as fontes (NVD e CNA) da
  versão CVSS preferida (3.1, senão 3.0, senão 2), e `severity` DEVE vir da
  métrica escolhida (v2 sem severidade: `MEDIUM`; sem métrica: `0.0` e
  `NONE`). Substitui a regra "primeira métrica" de FR-005 quando
  implementado.
- **FR-017** [Planejado, TickTick T11]: Um parquet do qual saem 0 pares
  DEVE fazer a execução falhar com código diferente de 0 e mensagem que
  cite `--label-from-path`. O log DEVE informar quantas linhas foram
  descartadas por fabricante ou modelo nulo ou vazio. Complementa FR-001
  quando implementado.
- **FR-018** [Planejado, TickTick T11]: A resolução de CPE DEVE percorrer
  todas as páginas do dicionário, preferir CPE de parte `o` e usar parte
  `h` só quando não há `o`. Dois CPEs são distintos quando a tupla (parte,
  fabricante, produto) difere depois de generalizar a versão; versões do
  mesmo produto e um par `o`/`h` do mesmo produto não são ambiguidade.
  Mais de um CPE distinto na parte escolhida DEVE ser ambiguidade: o par
  usa a busca por texto. Toda entrada DEVE ter `cpe_candidates` (lista dos
  CPEs distintos com ambiguidade; vazia sem ela). Substitui a regra
  "primeira página, só `o`, primeiro match" de FR-003 quando implementado.
- **FR-019** [Proposto, TickTick T11]: O sistema DEVE tentar de novo, com
  espera crescente, as respostas 403 e 503 da NVD, e tratar JSON inválido
  ou resposta incompleta como falha do par, sem interromper a execução.
- **FR-020** [Proposto, TickTick T11]: A busca DEVE estar registrada como
  comando instalado (`fetch-cves`) em `pyproject.toml`.
- **FR-021** [Planejado, TickTick T11]: Ao gravar o cache, o sistema DEVE
  gravar ao lado, com o mesmo nome-base (`<nome>.meta.json`), os
  argumentos da CLI, o caminho e o SHA256 de `--features`, o commit do
  código, o início e o fim da execução e as contagens de pares buscados,
  pulados e com falha. Com `--dry-run`, nada é gravado.

### Key Entities *(include if feature involves data)*

- **Par fabricante/modelo**: identidade de consulta vinda dos metadados
  `meta_brand`/`meta_model` da tabela de features. Chave do cache. Não é
  feature (constituição, princípio III).
- **Entrada do cache**: resultado da consulta de um par, com origem
  (`source`), forma NVD, CPE resolvido e lista de CVEs. Planejado:
  `schema_version: 3`, `fetched_at` e `cpe_candidates` (FR-014, FR-018).
- **Registro de CVE**: `id`, `cvss_max`, `severity` e `configurations`
  originais da NVD, que a rotulagem avalia por versão.
- **Metadados da busca** (Planejado, FR-021): `<nome>.meta.json` com
  parâmetros, entrada, commit, tempos e contagens da execução.
- **CPE generalizado**: nome CPE 2.3 oficial do firmware do par, com
  versão e campos seguintes em `*`.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% dos pares únicos da tabela de features têm entrada no
  cache. Medido em 2026-09-24: 310 pares em
  `dataset/processed/features_v2.parquet` e 310 entradas em
  `dataset/cve_cache_v2.json`, sem par faltante nem entrada sobrando.
- **SC-002**: 100% das entradas do cache têm `schema_version: 2` e 100%
  das CVEs têm `id`, `cvss_max`, `severity` e `configurations`. Medido em
  2026-09-24 no `dataset/cve_cache_v2.json`: 310/310 entradas e
  2838/2838 CVEs.
- **SC-003**: 100% das entradas registram a origem: `source="cpe"` com
  `cpe_name` preenchido ou `source="keyword"` com `cpe_name` nulo. Medido
  em 2026-09-24 no `dataset/cve_cache_v2.json`: 115 e 195 entradas.
- **SC-004** [Planejado, TickTick T11]: 100% das entradas do cache novo
  têm `fetched_at`; o cache novo vem de uma busca completa.
- **SC-005** [Planejado, TickTick T11]: 100% das execuções com algum par
  com falha terminam com código diferente de 0, e zero entradas anteriores
  ficam no cache depois de falha com `--force`.
- **SC-006** [Planejado, TickTick T11]: os testes de FR-016 e FR-018
  (T046, T049) passam, e na busca completa (T050) 100% dos pares com
  ambiguidade têm `cpe_candidates` não vazio.
- **SC-007** [Planejado, TickTick T11]: rodar de novo a busca com os
  argumentos e a entrada registrados em `cve_cache_v2.meta.json` consulta os
  mesmos pares.

## Assumptions

- A NVD API 2.0 (endpoints de CVE e de CPE) está acessível. Esta é a única
  etapa do pipeline com rede; as seguintes leem só o cache local.
- A tabela de features foi extraída com `--label-from-path`
  (001/FR-010).
- O cache é o retrato da NVD usado no TCC. Reproduzir os rótulos significa
  reusar o arquivo, não consultar a NVD de novo.
- A decisão de quais CVEs se aplicam a cada firmware (005/FR-005 a
  005/FR-011), a agregação em `cve_total`/`cvss_max` (005/FR-012) e o erro
  por par ausente no cache (005/FR-003) pertencem a `005-rotulagem-cve`.
