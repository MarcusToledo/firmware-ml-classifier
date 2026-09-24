# Feature Specification: Busca de CVEs na NVD

**Feature Branch**: `docs/specs-retroativas`

**Created**: 2026-09-24

**Status**: Implementado

**Input**: User description: "Spec retroativa (Status Implementado) da busca de CVEs na NVD por fabricante/modelo: pares únicos lidos do parquet de features, resolução de CPE oficial com virtualMatchString e fallback keywordSearch, normalização de fabricante, cache JSON versionado com CVEs, CVSS, severidade e configurations. Única etapa com rede. Derivar só do código em master, testes, docs/PIPELINE.md e TODO.md."

## Clarifications

### Session 2026-09-24

- Varredura de ambiguidade (`/speckit.clarify`): sem ambiguidades
  críticas. Por ser spec retroativa, cada FR descreve o comportamento do
  código em `master`; os pontos em aberto (`--output` padrão v1, entrada
  antiga mantida com `--force` após falha, data da consulta não
  registrada) são limitações registradas em Edge Cases, não escolhas de
  spec. Nenhuma pergunta feita.
- Terminologia normalizada: "par" é o fabricante/modelo como aparece no
  parquet de features (minúsculas, sem espaços nas pontas), usado como
  chave do cache; "forma NVD" é o par depois da normalização usada nas
  consultas.

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

### Edge Cases

- O fluxo da linha de comando (pulo de par em cache, validação de schema,
  falha de rede, gravação final, `--dry-run`, espera entre requisições,
  chave de API) não tem teste automatizado. Ver "Sem verificação" no
  `plan.md`.
- A busca não está registrada como comando instalado em `pyproject.toml`
  (`[project.scripts]`), ao contrário de `extract-features` e
  `generate-labels`; roda só como script.
- O `--output` padrão é `dataset/cve_cache.json`, o cache v1, de esquema
  agregado (`cvss_max`, `cve_count_*`, `cve_total`, sem `schema_version`;
  336 entradas, medido em 2026-09-24). O artefato em uso é
  `dataset/cve_cache_v2.json`. Rodar com o padrão e sem `--force`
  interrompe a execução com erro de schema antigo no primeiro par já em
  cache; com `--force`, os pares do parquet são regravados no esquema v2 e
  as outras 26 entradas v1 ficam, e o arquivo passa a misturar esquemas. O
  `README.md` também usa os caminhos v1.
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
  permanece no cache sem marca de que a nova consulta falhou.
- Não há nova tentativa nem espera extra para limite de taxa da NVD
  (HTTP 403/503): o par vira falha. Exceções fora de erro HTTP, de conexão
  ou timeout (ex.: resposta JSON inválida) interrompem a execução; o cache
  é gravado antes de sair.
- Um parquet extraído sem `--label-from-path` tem `meta_brand` e
  `meta_model` nulos (001/FR-010): a busca encontra 0 pares e termina sem
  erro, com o aviso só no log de nível info. Linhas com fabricante ou
  modelo nulo são descartadas sem contagem no log.
- A resolução de CPE lê só a primeira página (até 2000 produtos) do
  dicionário, aceita só CPE de parte `o` (sistema operacional/firmware) e
  usa o primeiro que coincide. Par cujo produto na NVD é só `h`
  (hardware) cai na busca por texto.
- A busca por texto (`source="keyword"`) casa o texto da CVE e pode trazer
  CVE de outro produto. A filtragem é da rotulagem, pelas
  `configurations` (`005-rotulagem-cve`, 005/FR-006 e 005/FR-007).
- `cvss_max` de cada CVE é o `baseScore` da primeira métrica da versão
  CVSS preferida, não o máximo entre as fontes (NVD e CNA). Métrica v2 sem
  `baseSeverity` recebe `MEDIUM`.
- As entradas não registram a data da consulta. A NVD muda com o tempo;
  reproduzir um rótulo exige o arquivo de cache, e não há como saber a
  data do retrato da NVD que ele contém.

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
  `"<fabricante>/<modelo>"` na forma do par (FR-001). Cada entrada DEVE ter
  `schema_version: 2`, `source`, `vendor` e `model` na forma NVD,
  `cpe_name` e a lista `cves`. Entradas já existentes de outros pares DEVEM
  ser preservadas.
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

### Key Entities *(include if feature involves data)*

- **Par fabricante/modelo**: identidade de consulta vinda dos metadados
  `meta_brand`/`meta_model` da tabela de features. Chave do cache. Não é
  feature (constituição, princípio III).
- **Entrada do cache**: resultado da consulta de um par, com origem
  (`source`), forma NVD, CPE resolvido e lista de CVEs.
- **Registro de CVE**: `id`, `cvss_max`, `severity` e `configurations`
  originais da NVD, que a rotulagem avalia por versão.
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
