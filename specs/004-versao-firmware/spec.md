# Feature Specification: Versão do firmware a partir do path

**Feature Branch**: `docs/specs-retroativas`

**Created**: 2026-09-24

**Status**: Implementado

**Input**: User description: "Spec retroativa (Status Implementado) da inferência de fabricante, modelo e versão do firmware a partir do path: fabricante e modelo pelo diretório, versão pelo sufixo do diretório (prioritária) ou por regra de nome de arquivo por fabricante, com origem registrada e sem chute quando não há versão. Derivar só do código em master, testes, docs/PIPELINE.md e TODO.md."

## Clarifications

### Session 2026-09-24

- Varredura de ambiguidade (`/speckit.clarify`): sem ambiguidades
  críticas. Por ser spec retroativa, cada FR descreve o comportamento do
  código em `master`: a prioridade entre diretório e nome de arquivo, o
  formato aceito por fabricante e o retorno sem versão já estão fixados no
  código e nos testes. As lacunas de cobertura (firmwares sem versão,
  extração relaxada, arquivos `*webflash*`) são limitações registradas em
  Edge Cases e no `TODO.md`. Nenhuma pergunta feita.
- Terminologia: "sem versão" significa `version` e `version_source` nulos;
  "origem" é o valor de `version_source` (`directory` ou `filename`).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Fabricante e modelo pelo diretório (Priority: P1)

O pesquisador organiza o dataset em
`dataset/raw/<fabricante>/<modelo>[_versão]/arquivo` e obtém, para cada
arquivo, fabricante, modelo e o identificador `<fabricante>_<modelo>`, sem
editar tabela à mão.

**Why this priority**: a busca de CVE e a rotulagem consultam o cache por
fabricante e modelo. Sem essa identidade não há rótulo.

**Independent Test**: inferir a identidade de paths com e sem sufixo de
versão no diretório do modelo e de um path fora do layout.

**Acceptance Scenarios**:

1. **Given** o path `dataset/raw/zyxel/NWA110AX_7.10(ABTG.4)C0/file.bin`,
   **When** a identidade é inferida, **Then** fabricante é `zyxel`, modelo é
   `nwa110ax` e o identificador é `zyxel_nwa110ax`.
2. **Given** o path `dataset/raw/dlink/dir-300/file.bin`, **When** a
   identidade é inferida, **Then** o modelo é `dir-300` e o identificador é
   `dlink_dir-300`.
3. **Given** o path `dataset/raw/belkin/f5d7234_4/...`, **When** a
   identidade é inferida, **Then** o modelo é `f5d7234_4`: o `_4` é revisão
   de hardware, não versão.
4. **Given** o path `some/other/dir/file.bin`, sem segmento `raw`, **When**
   a identidade é inferida, **Then** fabricante, modelo, identificador,
   versão e origem são nulos.

---

### User Story 2 - Versão com origem registrada (Priority: P1)

O pesquisador obtém a versão do firmware e de onde ela veio: do sufixo do
diretório do modelo ou do nome do arquivo, segundo a regra do fabricante.

**Why this priority**: a aplicabilidade de uma CVE depende da versão
(`005-rotulagem-cve`, 005/FR-005 e 005/FR-008). A origem permite auditar quanto do rótulo depende de
cada regra.

**Independent Test**: inferir a versão de um diretório com sufixo, de um
diretório sem sufixo com versão no nome do arquivo e de um caso com as
duas.

**Acceptance Scenarios**:

1. **Given** o diretório `dsr1000n_1.2`, **When** a versão é inferida,
   **Then** a versão é `1.2` e a origem é `directory`.
2. **Given** o path
   `dataset/raw/asus/rt-ac68u/RT-AC68U_3.0.0.4_384_45717-gadd52a8.trx`,
   **When** a versão é inferida, **Then** a versão é `3.0.0.4.384.45717` e
   a origem é `filename`.
3. **Given** o path `dataset/raw/dlink/dsr1000n_1.2/DSR-1000N_FW_9.99_WW`,
   **When** a versão é inferida, **Then** a versão é `1.2` e a origem é
   `directory`: o diretório vence o nome do arquivo.
4. **Given** o arquivo Netgear `R6250-V1.0.1.80_1.0.75.chk`, **When** a
   versão é inferida pelo nome, **Then** a versão é `1.0.1.80`: o segundo
   número é pacote de idioma.

---

### User Story 3 - Sem chute quando não há versão inequívoca (Priority: P1)

A banca audita que nenhum firmware recebe uma versão adivinhada. Quando o
nome não traz uma versão inequívoca, o firmware fica sem versão e a
rotulagem o trata como incerto.

**Why this priority**: uma versão errada gera um rótulo falsamente
determinado (constituição, princípios II e VII). Sem versão, o rótulo
fica `indeterminado` ou é decidido pelos limites em `005-rotulagem-cve`
(005/FR-005, 005/FR-012).

**Independent Test**: inferir a versão de nomes ambíguos e de fabricante
sem regra, e passar à extração um par versão/origem inconsistente.

**Acceptance Scenarios**:

1. **Given** o arquivo D-Link `DIR_1760_FW101B04.BIN`, **When** a versão é
   inferida, **Then** versão e origem são nulas (`101` poderia ser `1.01`,
   mas isso seria chute).
2. **Given** o arquivo D-Link `DIR-300_REVB5_FIRMWARE_2.15.B01_WW.BIN`,
   **When** a versão é inferida, **Then** ela é nula: o sufixo de build
   `B01` muda a versão e não é truncado.
3. **Given** o fabricante `zyxel`, que não tem regra de nome de arquivo,
   **When** a versão de `NWA110AX_7.10.bin` é inferida pelo nome, **Then**
   ela é nula.
4. **Given** uma versão sem origem, ou uma origem sem versão, **When** a
   extração de um arquivo é pedida, **Then** ela é rejeitada com erro que
   cita o path.

---

### User Story 4 - Identidade no artefato só quando pedida (Priority: P2)

O pesquisador grava fabricante, modelo, identificador, versão e origem na
tabela de features só quando pede `--label-from-path`; a identidade
também sobrevive a uma falha de leitura do arquivo.

**Why this priority**: o modo inferência não deve expor identidade
(`001/FR-010`), e um arquivo ilegível ainda precisa ser rastreável até o
modelo e a versão.

**Independent Test**: extrair com e sem `--label-from-path` um arquivo em
diretório com versão, e extrair um path inexistente dentro do layout.

**Acceptance Scenarios**:

1. **Given** `raw/zyxel/NWA110AX_7.10(ABTG.4)C0/firmware.bin` e
   `--label-from-path`, **When** a tabela é gravada, **Then**
   `meta_version` é `7.10(ABTG.4)C0` e `meta_version_source` é
   `directory`.
2. **Given** o mesmo arquivo sem `--label-from-path`, **When** a tabela é
   gravada, **Then** `meta_version` e `meta_version_source` são nulos.
3. **Given** o path inexistente `raw/dlink/dsr1000n_1.2/firmware.bin`,
   **When** ele é extraído no lote, **Then** a leitura falha
   (`read_ok=False`) e os metadados guardam fabricante `dlink`, modelo
   `dsr1000n`, versão `1.2` e origem `directory`.

---

### Edge Cases

- Firmwares sem versão. Medido em 2026-09-24 sobre
  `dataset/processed/features_v2.parquet`: 226 de 840 linhas (26,9%) têm
  `meta_version` nulo (tp_link 73, asus 69, dlink 68, tplink 13, belkin 2,
  netgear 1), e 214 de 699 `firmware_id` não têm versão em nenhum alias.
  As 614 linhas com versão vêm todas do nome do arquivo; nenhuma vem do
  diretório. Isso coincide com `docs/PIPELINE.md`, §"Estado real do
  dataset" (0 `directory`, 614 `filename`, 226 sem versão) e com o
  `labels_v2.csv`. A rotulagem trata as CVEs desses firmwares como
  indeterminadas. Usar evidência independente de versão (+13
  `firmware_id`) é trabalho futuro no `TODO.md`, request "Analisar
  aplicabilidade de CVE por versão do firmware".
- A extração relaxada pelo nome do arquivo (D-Link compacto `FW101B04`,
  D-Link com build `1.04B58`, ASUS compacto `30043763754`) daria versão a
  mais 37 `firmware_id`, segundo `docs/PIPELINE.md`, §"Limitações da
  rotulagem". Levada como trabalho futuro no `TODO.md`.
- Os 23 arquivos `*webflash*` (ex.: `tl-wr710v1-webflash.bin`) ficam sem
  versão. Verificar se são DD-WRT antes de atribuir versão está pendente
  no `TODO.md`.
- Divergência entre as regras: quando o diretório tem versão, a do nome do
  arquivo não é calculada nem comparada, e um conflito não fica registrado
  em lugar nenhum. A versão do diretório é gravada como está (pode ter
  parênteses e letras, ex.: `7.10(ABTG.4)C0`), enquanto a do nome do
  arquivo é sempre números separados por ponto. Nenhuma linha do dataset
  atual usa a versão do diretório.
- O sufixo do diretório só é separado quando o modelo começa por letra,
  tem um dígito e não tem `_`, e a versão começa por `N.N`. Um diretório
  como `archer_c20i_1.0` ficaria inteiro como modelo. Medido em 2026-09-24:
  nenhum dos 310 modelos de `features_v2.parquet` tem sufixo `_N.N` não
  separado.
- Um arquivo posto direto em `raw/<fabricante>/`, sem diretório de modelo,
  recebe o nome do arquivo (em minúsculas) como modelo, em vez de
  identidade nula. O primeiro segmento `raw` do path (sem distinção de
  maiúsculas) é o usado, então um diretório `raw` acima do dataset
  desviaria a inferência. Nenhum dos dois ocorre hoje: a inferência atual
  sobre os 840 `meta_path` reproduz fabricante, modelo e versão gravados.
- As grafias `tplink/` e `tp_link/` usam a mesma regra de nome de arquivo,
  mas geram identificadores diferentes para o mesmo modelo (ex.:
  `tplink_tl_er604w` e `tp_link_tl-er604w`). A consolidação está pendente
  no `TODO.md`.
- Fabricante sem regra de nome de arquivo (ex.: `zyxel`) só obtém versão
  pelo diretório. Os seis diretórios de fabricante do dataset atual
  (`asus`, `belkin`, `dlink`, `netgear`, `tp_link`, `tplink`) têm regra.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001** [Implementado]: O sistema DEVE inferir fabricante e modelo do
  layout `raw/<fabricante>/<modelo>[_versão]/arquivo`, usando o primeiro
  segmento `raw` do path (sem distinção de maiúsculas): o fabricante é o
  segmento seguinte e o modelo, o próximo. Ambos DEVEM ser gravados sem
  espaços nas pontas e em minúsculas.
- **FR-002** [Implementado]: Quando o path não tem segmento `raw`, tem
  menos de dois segmentos depois dele ou resulta em fabricante ou modelo
  vazio, o sistema DEVE devolver fabricante, modelo, identificador, versão
  e origem nulos.
- **FR-003** [Implementado]: O sistema DEVE formar o identificador
  (`label`) como `<fabricante>_<modelo>`, já sem o sufixo de versão.
- **FR-004** [Implementado]: O sistema DEVE separar o segmento do modelo
  em modelo e versão quando ele tem a forma `<modelo>_<versão>`, com o
  modelo começando por letra, contendo ao menos um dígito e formado só por
  letras, dígitos e hífen, e a versão começando por dígitos, ponto e
  dígito. A versão DEVE ser mantida como está no diretório. Fora dessa
  forma, o segmento inteiro DEVE ser o modelo (ex.: `f5d7234_4`).
- **FR-005** [Implementado]: A versão do diretório DEVE ter prioridade,
  com origem `directory`. Sem versão no diretório, o sistema DEVE aplicar
  a regra de nome de arquivo do fabricante e, se ela achar versão, gravar
  origem `filename`.
- **FR-006** [Implementado]: Antes de aplicar a regra do fabricante, o
  sistema DEVE decodificar escapes de URL do nome do arquivo (ex.: `%20`)
  e remover uma extensão final `.bin`, `.img`, `.trx`, `.chk`, `.zip` ou
  `.rom`, sem distinção de maiúsculas. O fabricante DEVE ser casado sem
  distinção de maiúsculas. Fabricante sem regra DEVE resultar em versão
  nula.
- **FR-007** [Implementado]: Regra Netgear: o sistema DEVE aceitar, nesta
  ordem, (a) `-V` ou `_V` (ou `v`) seguido de 3 ou 4 números separados por
  ponto; (b) `-` seguido de 4 números separados por ponto; (c) `_` seguido
  de 3 ou 4 números separados por `_`, convertidos para ponto. O número
  deve terminar em `_`, `.`, `-` ou no fim do nome nos casos (a), e em `_`
  ou no fim nos casos (b) e (c). O primeiro número encontrado é a versão;
  o seguinte (pacote de idioma) é ignorado.
- **FR-008** [Implementado]: Regra ASUS: o sistema DEVE aceitar, no fim do
  nome, `_` seguido de 3 a 6 números separados por ponto e até dois grupos
  de build `_NN` (2 a 6 dígitos), opcionalmente seguidos de `-g<hash>`,
  `_combo` e `.<letra maiúscula>` de região. Os grupos de build DEVEM
  entrar na versão, unidos por ponto (ex.: `3.0.0.4.384.45717`); o hash, o
  `_combo` e a letra de região, não.
- **FR-009** [Implementado]: Regra Belkin: o sistema DEVE aceitar a
  primeira versão de 3 números separados por ponto, precedida de `_`, `-`
  ou espaço e de `v` opcional, e seguida do fim do nome ou de `_`, `.`,
  `-`, espaço ou `(`.
- **FR-010** [Implementado]: Regra D-Link: o sistema DEVE coletar os
  candidatos de 2 a 6 números separados por ponto que não sejam precedidos
  de dígito ou ponto nem seguidos de dígito ou de letra (com ou sem ponto
  antes dela), descartar os que têm forma de data `AAAA.M.D` e aceitar a
  versão só quando resta exatamente um candidato distinto.
- **FR-011** [Implementado]: Regra TP-Link, para os diretórios `tp_link` e
  `tplink`: o sistema DEVE aceitar `_` seguido de 3 números separados por
  `_` e seguido de `_up` ou de `_<6 dígitos>R<dígitos>`, convertidos para
  ponto; senão, `_` seguido de 3 números separados por ponto e de
  `_[<8 dígitos>-rel<dígitos>]`.
- **FR-012** [Implementado]: Quando nem o diretório nem a regra do
  fabricante dão uma versão inequívoca, o sistema NÃO DEVE atribuir
  versão: versão e origem DEVEM ser nulas.
- **FR-013** [Implementado]: `version` e `version_source` DEVEM estar ambos
  preenchidos ou ambos nulos. A extração de um arquivo que recebe só um
  dos dois DEVE ser rejeitada com erro que cita o path.
- **FR-014** [Implementado]: O sistema DEVE inferir a identidade de todo
  arquivo do lote e mantê-la nos metadados do resultado mesmo quando a
  leitura falha ou a extração do arquivo levanta exceção. Os valores
  chegam à tabela como `meta_brand`, `meta_model`, `meta_label`,
  `meta_version` e `meta_version_source` só com `--label-from-path`
  (`001/FR-009`, `001/FR-010`) e nunca entram no vetor de features
  (`001/FR-011`).

### Key Entities *(include if feature involves data)*

- **Path do firmware**: localização do arquivo no layout
  `raw/<fabricante>/<modelo>[_versão]/arquivo`. É a única entrada; o
  conteúdo do binário não é lido.
- **Identidade inferida**: fabricante, modelo, identificador
  `<fabricante>_<modelo>`, versão e origem da versão. É metadado de
  consulta, não feature.
- **Regra de versão por fabricante**: padrão aplicado ao nome do arquivo
  de um fabricante (Netgear, ASUS, Belkin, D-Link, TP-Link) que devolve
  uma versão numérica com pontos ou nada.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% das linhas têm versão e origem ambas preenchidas ou
  ambas nulas. Medido em 2026-09-24 sobre `dataset/labels_v2.csv`: 0 de
  840 linhas com par inconsistente (614 com versão).
- **SC-002**: a inferência é função só do path. Medido em 2026-09-24:
  aplicada aos 840 `meta_path` de `features_v2.parquet`, reproduz
  `meta_brand`, `meta_model` e `meta_version` em 840 de 840 linhas.
- **SC-003**: nenhuma versão atribuída sem regra do fabricante ou sufixo
  de diretório. Resultado observado em 2026-09-24 sobre
  `features_v2.parquet`: 614 de 840 linhas (73,1%) com versão, todas de
  origem `filename`, e 485 de 699 `firmware_id` com versão em ao menos um
  alias.

## Assumptions

- O dataset é curado no layout `raw/<fabricante>/<modelo>[_versão]/`; a
  identidade depende dessa organização, não do conteúdo do binário.
- As regras de nome de arquivo cobrem as convenções observadas no dataset
  atual de cada fabricante; um formato novo cai em versão nula até ganhar
  regra.
- A rotulagem em `005-rotulagem-cve` reaplica esta inferência sobre
  `meta_path` e exige que a versão coincida com `meta_version` (005/FR-004). Mudar uma
  regra de versão exige reextrair as features antes de regerar os rótulos
  (`docs/PIPELINE.md`, §"3. Rotulagem por CVE").
- O `features_v2.parquet` atual foi gerado antes de `meta_version_source`
  (ver Assumptions de `001-extracao-features`); a origem está no
  `labels_v2.csv`.
