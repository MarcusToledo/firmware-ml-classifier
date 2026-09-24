# Feature Specification: Rotulagem por CVE

**Feature Branch**: `docs/specs-retroativas`

**Created**: 2026-09-24

**Status**: Implementado

**Input**: User description: "Spec retroativa (Status Implementado) da rotulagem por CVE: para cada firmware, CVEs do cache consultado por fabricante/modelo filtradas pela versão quando conhecida, separação entre aplicáveis e indeterminadas, agregação por firmware_id entre aliases, nível de segurança derivado de cve_total e cvss_max e tabela labels_v2.csv. Par ausente no cache é erro. Derivar só do código em master, testes, docs/PIPELINE.md e TODO.md."

## Clarifications

### Session 2026-09-24

- Varredura de ambiguidade (`/speckit.clarify`): sem ambiguidades críticas
  no comportamento. Por ser spec retroativa, cada FR descreve o código em
  `master`; as regras de versão, de agregação e de classe estão todas
  decididas no código e cobertas por teste.
- Q: Onde a tabela de rótulos deve ficar por padrão? → A: em
  `dataset/processed/labels_v2.csv`, com registro do limiar
  `--critical-cvss` e das entradas (princípio V). Decisão do pesquisador,
  ainda não implementada: nenhum FR muda; o desvio atual está em Edge
  Cases e a correção no `TODO.md`.
- Terminologia normalizada: uma CVE é **aplicável**, **indeterminada** ou
  **não aplicável** à versão do firmware; `indeterminado` é o estado do
  rótulo do firmware. **Alias** é cada linha da tabela de features que
  compartilha o mesmo `firmware_id` (mesmo binário sob outro path,
  fabricante ou modelo).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Rótulo de treino vindo só do cache de CVE (Priority: P1)

A banca audita que o rótulo de cada firmware vem só das CVEs do cache
consultado por fabricante e modelo, decidido por `cve_total` e `cvss_max`,
e que uma consulta ausente no cache interrompe a rotulagem em vez de virar
"sem CVE".

**Why this priority**: o ground truth precisa ser externo ao classificador
e auditável (constituição, princípio II). Um par ausente tratado como
negativo produziria rótulos falsos sem aviso.

**Independent Test**: rotular estatísticas de CVE com e sem campos extras
de features, e rotular uma linha cujo par fabricante/modelo não está no
cache.

**Acceptance Scenarios**:

1. **Given** estatísticas `cve_total=1` e `cvss_max=9.0`, **When** o
   rótulo é calculado com o limiar padrão, **Then** o resultado é
   `cve_critica`.
2. **Given** `cve_total=3` e `cvss_max=5.5`, **When** o rótulo é
   calculado, **Then** o resultado é `cve_conhecida`.
3. **Given** `cve_total=0` junto de campos como `entropy`,
   `count_hardcoded_passwords` e `has_telnetd`, **When** o rótulo é
   calculado, **Then** o resultado é `sem_cve_conhecida`, sem influência
   dos campos extras.
4. **Given** um firmware de `unknown/x1` e um cache sem essa chave,
   **When** a rotulagem roda, **Then** ela falha com erro que cita
   `unknown/x1`.
5. **Given** `--critical-cvss 7.0` e `cvss_max=7.0`, **When** o rótulo é
   calculado, **Then** o resultado é `cve_critica`.

---

### User Story 2 - CVEs filtradas pela versão do firmware (Priority: P1)

O pesquisador rotula cada firmware só com as CVEs que se aplicam à sua
versão, quando ela é conhecida, e vê como indeterminadas as CVEs cuja
aplicabilidade não dá para decidir.

**Why this priority**: o cache é por fabricante/modelo. Sem filtrar pela
versão, uma versão corrigida herdaria as CVEs das anteriores.

**Independent Test**: avaliar uma CVE com `versionEndExcluding=2.0` para
as versões 1.9 e 2.0, e a mesma CVE para um firmware sem versão.

**Acceptance Scenarios**:

1. **Given** uma CVE com `versionEndExcluding=2.0`, **When** a versão é
   `1.9`, **Then** a CVE é aplicável; **When** a versão é `2.0`, **Then**
   ela é não aplicável.
2. **Given** um firmware sem versão (nulo, em branco ou sem número
   inicial), **When** as CVEs da entrada são avaliadas, **Then** todas são
   indeterminadas.
3. **Given** uma entrada de cache sem CVEs, **When** o firmware não tem
   versão, **Then** não há CVE aplicável nem indeterminada.
4. **Given** a CPE `tl-sg2008_firmware:1.0.0:build_20180529_rel.40524`,
   **When** a versão do firmware é `1.0.0`, **Then** a CVE é
   indeterminada; **When** é `1.0.1`, **Then** é não aplicável.
5. **Given** uma CVE com uma configuração para outro modelo e outra para o
   modelo-alvo com `versionEndExcluding=2.0`, **When** a versão é `1.0`,
   **Then** a CVE é aplicável, sem que a configuração do outro modelo a
   deixe indeterminada.

---

### User Story 3 - Mesmo binário, mesmo rótulo (Priority: P1)

O pesquisador obtém um único rótulo por `firmware_id`: aliases do mesmo
binário sob modelos diferentes somam as evidências de todos os modelos.

**Why this priority**: fabricantes reaproveitam o binário sob nomes
comerciais diferentes, e a cobertura da NVD varia por nome. Rótulos
diferentes para o mesmo conteúdo contaminam o treino.

**Independent Test**: rotular dois aliases do mesmo `firmware_id` com
versões e entradas de cache diferentes e comparar as linhas.

**Acceptance Scenarios**:

1. **Given** dois aliases do mesmo `firmware_id`, um com CVE não aplicável
   à sua versão e outro com uma CVE aplicável de CVSS 7.5, **When** a
   rotulagem roda, **Then** as duas linhas saem `cve_conhecida` com
   `cve_total=1`.
2. **Given** uma CVE aplicável de CVSS 9.8 e uma indeterminada de 7.5,
   **When** o rótulo é agregado, **Then** ele é `cve_critica`.
3. **Given** uma CVE aplicável de CVSS 7.5 e uma indeterminada de 9.8,
   **When** o rótulo é agregado, **Then** ele é `indeterminado`, com
   `cve_total=1` e `cvss_max=7.5`.
4. **Given** a mesma CVE aplicável em um alias e indeterminada em outro,
   **When** o rótulo é agregado, **Then** ela conta como aplicável.

---

### User Story 4 - Entrada inconsistente interrompe a rotulagem (Priority: P2)

O pesquisador recebe erro explícito quando a tabela de features ou o
cache não permitem um rótulo confiável, em vez de rótulos silenciosamente
errados.

**Why this priority**: rótulo inválido deve ficar visível (constituição,
princípio VI). A tabela de features pode estar desatualizada em relação à
regra de versão.

**Independent Test**: rodar a rotulagem com uma linha cuja `meta_version`
diverge da versão do path e com linhas duplicadas.

**Acceptance Scenarios**:

1. **Given** `meta_path` em `dir300_2.0/` e `meta_version='1.0'`, **When**
   a rotulagem roda, **Then** ela falha citando o `firmware_id`, as duas
   versões e a instrução de reextrair as features com
   `--label-from-path`.
2. **Given** `meta_path` com versão e `meta_version` nulo, **When** a
   rotulagem roda, **Then** ela falha da mesma forma.
3. **Given** `meta_brand` e `meta_model` nulos, **When** a rotulagem roda,
   **Then** ela falha com `meta_brand/meta_model ausentes`, antes de
   conferir a versão.
4. **Given** duas linhas com o mesmo `firmware_id` e `meta_path`, ou uma
   linha com `meta_path` nulo, **When** a tabela é carregada, **Then** a
   rotulagem falha antes de consultar o cache.
5. **Given** uma entrada do cache sem `schema_version: 2` ou sem lista
   `cves`, **When** ela é consultada, **Then** a rotulagem falha.

---

### User Story 5 - Conferência sem gravar (Priority: P3)

O pesquisador roda a rotulagem com `--dry-run` para ver no log a
distribuição de classes e a origem da versão sem sobrescrever a tabela de
rótulos.

**Why this priority**: permite conferir o efeito de uma mudança de regra
antes de regerar o artefato.

**Independent Test**: rodar com `--dry-run` e conferir que o log traz a
distribuição e que nenhum arquivo é gravado.

**Acceptance Scenarios**:

1. **Given** `--dry-run`, **When** a rotulagem termina, **Then** o log
   informa a contagem de firmwares e de entradas do cache, a distribuição
   das quatro classes e a da origem da versão, e nenhum arquivo é gravado.

---

### Edge Cases

- O `--output` padrão ainda é o v1, `dataset/labels.csv`. Gerar o
  artefato atual exige passar `--output dataset/labels_v2.csv`; sem isso a
  execução sobrescreve o `labels.csv` antigo, que ainda existe no disco.
  Além disso, `dataset/labels_v2.csv` fica fora de `dataset/processed/`,
  local de tabelas finais do princípio V. O local canônico decidido é
  `dataset/processed/labels_v2.csv` (ver Clarifications); a correção está
  no `TODO.md`.
- O `features_v2.parquet` atual não tem `meta_version_source` (conferido
  em 2026-09-24). Por isso a rotulagem reinfere `version_source` a partir
  de `meta_path`, pela regra de `004-versao-firmware`, e só confere a
  versão contra `meta_version`. `meta_version_source`, quando existe no
  parquet, não é lido nem conferido. Qualquer mudança na regra de versão
  exige reextrair as features antes de regerar os rótulos; senão a
  checagem de coerência falha.
- `labels_v2.csv` mantém o estado `indeterminado` (137 de 840 linhas; 126
  de 699 `firmware_id`, medido em 2026-09-24). O treino futuro precisa
  excluí-lo e usar do arquivo só `security_level`, porque
  `version_source` nulo tende a coincidir com `indeterminado` (83 das 137
  linhas `indeterminado` têm `version_source` nulo, mesma medição).
  Tratado no `TODO.md`, itens "Excluir registros `indeterminado` do
  treino" e "Implementar `scripts/train.py`".
- Firmware sem versão tem todas as CVEs da entrada como indeterminadas,
  inclusive as que só citam outros produtos ou não têm `configurations`.
  Evidência independente de versão está no `TODO.md` como trabalho futuro.
- CVE sem `configurations` é aplicável a qualquer versão (decisão
  conservadora). Uma CVE achada só por busca textual pode assim ser ligada
  a um modelo que ela não afeta. Registrado em `docs/PIPELINE.md`,
  "Limitações da rotulagem", e no mesmo item de trabalho futuro do
  `TODO.md`.
- Versão CPE exata sem base numérica inicial (ex.: `firmware_4.05.03`,
  erro de cadastro da NVD na Belkin) resulta em CVE não aplicável: a
  incerteza vira evidência negativa. Decidido como limitação aceita no
  `TODO.md`; `docs/PIPELINE.md` registra impacto nulo no dataset atual.
  Firmware com sufixo (ex.: `1.2rc1`) contra CPE exata numérica (`1.2`)
  também resulta em não aplicável; `docs/PIPELINE.md` registra zero
  ocorrência hoje.
- Condições que os metadados não resolvem ficam indeterminadas: versão CPE
  `-` no produto-alvo, revisão de hardware específica, limites em data
  (ex.: `versionEndExcluding=2017-01-06`) e outro produto vulnerável numa
  configuração `AND`. Elas formam o resíduo de `indeterminado`.
- O recall de `sem_cve_conhecida` depende do cache por modelo de
  `003-busca-cve`: uma entrada vazia é evidência negativa válida, mesmo
  quando um modelo irmão tem CVEs. Os 43 pares `tp_link/*` buscados antes
  da correção do alias de fabricante precisam de nova busca antes de
  rótulos confiáveis (`TODO.md`).
- A agregação usa `firmware_id`, que é o SHA256 só do prefixo lido
  (`001/FR-004`). Dois binários diferentes com o mesmo prefixo seriam
  tratados como aliases e receberiam o mesmo rótulo. Não há colisão no
  dataset atual (medição registrada em `001-extracao-features`, Edge
  Cases); registrado no `TODO.md`.
- Qualquer erro de entrada interrompe a execução inteira sem gravar
  nenhum rótulo; não há saída parcial com as linhas válidas.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001** [Implementado]: O sistema DEVE receber, por `--features` e
  `--cves` (ambos obrigatórios), a tabela de features (parquet se a
  extensão for `.parquet`, senão CSV) e o cache de CVE em JSON. Da tabela,
  DEVE ler só as colunas `firmware_id`, `meta_path`, `meta_brand`,
  `meta_model` e `meta_version`.
- **FR-002** [Implementado]: O sistema DEVE falhar, antes de rotular,
  quando a tabela de features está vazia, quando há `firmware_id` ou
  `meta_path` nulo, quando há linhas duplicadas pelo par
  `firmware_id` + `meta_path`, ou quando o cache não é um objeto JSON.
- **FR-003** [Implementado]: O sistema DEVE buscar a entrada do cache pela
  chave `<meta_brand>/<meta_model>`, sem espaços nas pontas e em
  minúsculas. DEVE falhar, com o `firmware_id` na mensagem, quando
  `meta_brand` ou `meta_model` está ausente, quando a chave não está no
  cache (consulta ausente não é evidência de que não há CVE), ou quando a
  entrada não tem lista `cves` ou não tem `schema_version` igual a 2.
- **FR-004** [Implementado]: O sistema DEVE reinferir versão e origem da
  versão a partir de `meta_path`, pela regra de `004-versao-firmware`, e
  falhar quando a versão reinferida difere de `meta_version` (inclusive
  nulo contra valor), citando `firmware_id`, `meta_path`, as duas versões
  e a instrução de reextrair as features com `--label-from-path`. A coluna
  `version_source` gravada DEVE ser a reinferida.
- **FR-005** [Implementado]: Para cada linha, o sistema DEVE separar as
  CVEs da entrada do cache em aplicáveis e indeterminadas, na ordem do
  cache, descartando as não aplicáveis. Sem versão (nula, em branco ou sem
  segmento numérico inicial), DEVE tratar todas as CVEs da entrada como
  indeterminadas; uma entrada sem CVEs DEVE resultar em nenhuma aplicável
  e nenhuma indeterminada.
- **FR-006** [Implementado]: O sistema DEVE avaliar cada CVE pelas suas
  `configurations` em lógica de três valores (aplicável, não aplicável,
  indeterminada): nós `AND`/`OR` com filhos e `negate`, e configurações
  combinadas por `OR`. CVE sem `configurations` DEVE ser aplicável.
  Configuração cujas CPEs são todas legíveis e nenhuma cita o
  produto-alvo DEVE ser descartada; se todas forem descartadas, a CVE é
  não aplicável. O produto-alvo DEVE vir do `cpe_name` da entrada ou, na
  falta dele, de `vendor`/`model`, comparados em minúsculas, só com letras
  e dígitos e sem o sufixo `firmware` no produto.
- **FR-007** [Implementado]: Uma condição de plataforma
  (`vulnerable=false`) DEVE ser satisfeita só quando é o hardware do
  próprio produto-alvo sem revisão (versão `-` ou `*`); qualquer outra
  DEVE ser indeterminada. Uma CPE vulnerável de outro produto DEVE ser não
  aplicável num nó `OR` e indeterminada dentro de um contexto `AND`. CPE
  ilegível DEVE ser indeterminada.
- **FR-008** [Implementado]: O sistema DEVE comparar versões pelos
  segmentos numéricos iniciais, com segmentos finais ausentes valendo zero
  (`1.2` = `1.2.0`), respeitando `versionStartIncluding`,
  `versionStartExcluding`, `versionEndIncluding` e `versionEndExcluding`.
  Limite não numérico após a normalização, ou limites diante de uma
  versão de firmware que não é puramente numérica (ex.:
  `7.10(ABTG.4)C0`), DEVEM tornar a CVE indeterminada.
- **FR-009** [Implementado]: Antes de comparar, o sistema DEVE normalizar
  versões CPE exatas e limites (regra B1): remover `v`/`V` inicial seguido
  de dígito para qualquer fabricante; trocar `_` por `.` para ASUS; para
  Netgear, remover o pacote de idioma após `_` (forma `X.Y.Z[.W]_...`) e
  tornar a CVE indeterminada quando a versão do firmware é igual à base.
  Para os demais fabricantes, `_` DEVE ser mantido.
- **FR-010** [Implementado]: Para versão CPE exata (guarda B), o sistema
  DEVE: com `*`, avaliar só os limites; com `-`, tornar a CVE
  indeterminada; com igualdade ignorando caixa, ou com CPE e firmware
  numéricos iguais após padding de zeros, considerá-la aplicável. Quando
  a CPE tem sufixo (build, beta ou variante regional) e a mesma base
  numérica do firmware, DEVE ser indeterminada se o firmware não tem
  sufixo, ou se a CPE é a versão completa do firmware seguida de separador
  não alfanumérico e qualificador; senão, não aplicável. Base numérica
  distinta, CPE sem base numérica e CPE numérica contra firmware com
  sufixo DEVEM ser não aplicáveis.
- **FR-011** [Implementado]: Quando o campo `update` da CPE é literal
  (diferente de `*` e `-`) e a versão casa, a CVE DEVE ser indeterminada.
  `update` igual a `-` NÃO DEVE restringir o casamento.
- **FR-012** [Implementado]: O sistema DEVE agregar por `firmware_id`
  (regra C): unir por ID de CVE as aplicáveis (A) e as indeterminadas (U)
  de todos os aliases, retirar de U os IDs presentes em A e rotular com
  `label(A)` quando `label(A) = label(A ∪ U)`, e `indeterminado` caso
  contrário. `cve_total` e `cvss_max` DEVEM descrever só A (limite
  inferior). Todos os aliases DEVEM receber o mesmo rótulo e as mesmas
  estatísticas. CVE sem ID válido DEVE gerar erro.
- **FR-013** [Implementado]: O sistema DEVE derivar a classe só de
  `cve_total` e `cvss_max`: `sem_cve_conhecida` com `cve_total=0`,
  `cve_critica` com `cvss_max` maior ou igual ao limiar `--critical-cvss`
  (padrão 9.0) e `cve_conhecida` nos demais casos. DEVE falhar com
  `cve_total` que não é inteiro não negativo, com `cvss_max` fora de
  [0, 10] ou não numérico, e com limiar fora de [0, 10]. `indeterminado`
  DEVE ser um quarto estado, distinto das três classes.
- **FR-014** [Implementado]: O rótulo NÃO DEVE usar features, achados de
  evidência nem o baseline de regras de `006-baseline-regras`: só as CVEs
  do cache e a versão do firmware.
- **FR-015** [Implementado]: O sistema DEVE gravar em `--output` um CSV
  com uma linha por linha da tabela de entrada, na mesma ordem, e as
  colunas `firmware_id`, `meta_path`, `vendor`, `model`, `version`,
  `version_source`, `security_level`, `cve_total` e `cvss_max`, nessa
  ordem, sem nenhuma coluna de feature. `vendor`, `model` e `version` DEVEM
  ser cópias de `meta_brand`, `meta_model` e `meta_version`. O diretório
  de destino DEVE ser criado se não existir.
- **FR-016** [Implementado]: Com `--dry-run`, o sistema DEVE executar toda
  a rotulagem e os logs sem gravar a saída.
- **FR-017** [Implementado]: O sistema DEVE registrar em log o número de
  firmwares e de entradas do cache, a distribuição de `security_level`
  nas quatro classes, a distribuição de `version_source` (`directory`,
  `filename`, nulo) e o caminho gravado.

### Key Entities *(include if feature involves data)*

- **Entrada do cache de CVE**: resultado da consulta por fabricante/modelo,
  definido em `003-busca-cve`. Contém as CVEs com ID, CVSS, severidade e
  `configurations`.
- **CVE avaliada**: uma CVE da entrada classificada como aplicável,
  indeterminada ou não aplicável para a versão de um firmware.
- **Alias**: linha da tabela de features que compartilha `firmware_id`
  com outra.
- **Registro de rótulo**: uma linha de `labels_v2.csv`, com identificação,
  versão, `security_level` e as estatísticas de CVE aplicáveis.
- **Nível de segurança** (`security_level`): `sem_cve_conhecida`,
  `cve_conhecida`, `cve_critica` ou o estado `indeterminado`.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% das linhas da tabela de features têm uma linha na
  tabela de rótulos, ou a execução falha sem gravar nada.
- **SC-002**: zero pares fabricante/modelo ausentes no cache viram
  `sem_cve_conhecida`; todo par ausente interrompe a execução.
- **SC-003**: zero `firmware_id` com mais de um `security_level` em
  `labels_v2.csv`. Medido em 2026-09-24: 699 `firmware_id`, 74 com mais de
  um alias, nenhum com rótulos diferentes.
- **SC-004**: `labels_v2.csv` tem só as 9 colunas de FR-015, nenhuma de
  feature.
- **SC-005**: a rotulagem do código atual sobre `features_v2.parquet` e
  `cve_cache_v2.json` reproduz `labels_v2.csv`: 840 linhas e 699
  `firmware_id`, com 0 diferenças em `security_level`, `cve_total`,
  `cvss_max` e `version_source` (medido em 2026-09-24, em memória, sem
  gravar). A distribuição por `firmware_id` (423 `sem_cve_conhecida`, 49
  `cve_conhecida`, 101 `cve_critica`, 126 `indeterminado`) é a registrada
  no `TODO.md` e em `docs/PIPELINE.md`.

## Assumptions

- A tabela de features foi extraída com `--label-from-path`; sem isso
  `meta_brand`, `meta_model` e `meta_version` saem nulos (`001/FR-010`) e
  a rotulagem falha.
- O cache segue o formato `schema_version: 2` de `003-busca-cve`, com
  cada CVE trazendo `id`, `cvss_max`, `severity` e `configurations`.
- A versão e sua origem seguem a regra de `004-versao-firmware`.
- O treino, ainda não implementado, junta rótulos e features por
  `firmware_id` e usa só `security_level`.
