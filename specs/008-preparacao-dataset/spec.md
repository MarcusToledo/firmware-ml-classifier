# Feature Specification: Preparação do dataset de treino

**Feature Branch**: `docs/escopo-restante`

**Created**: 2026-09-25

**Status**: Planejado

**Input**: User description: "Spec nova (Status Planejado, TickTick T08 e
T07) da preparação do dataset de treino: juntar por `firmware_id` as
features (001, e 012 quando implementada) e só o `security_level` da
rotulagem (005), sem identidade, campos de CVE, `meta_*` nem `doc2vec_*` no
vetor; excluir `indeterminado`, imagens de terceiros (004/FR-017) e falhas
de extração com motivo e contagem por fabricante; tratar detectores
constantes e codificar `fs_type`/`compression_type`, sem scaler; gravar a
tabela em `dataset/processed/` com metadados e validá-la no lugar de
`scripts/validate_dataset.py`; unificar `tplink`/`tp_link` em
`dataset/raw/`."

## Clarifications

### Session 2026-09-25

- Q: Destino dos 5 detectores constantes? → A: a 008 mantém as colunas e
  registra nos metadados as constantes na entrada, como diagnóstico; o
  filtro de variância, ajustado só na partição de treino, é FR da `010`
  (FR-009).
- Q: Codificação de `fs_type` e `compression_type`? → A: one-hot com
  lista fixa de categorias na configuração versionada, mais `outro` e
  `ausente`, sem ajuste a dados (FR-010).
- Q: Lista fixa do one-hot? → A: as categorias observadas: `fs_type`
  `squashfs`, `jffs2`, `cramfs`, `ubifs`; `compression_type` `lzma`,
  `gzip`, `xz`, `lzo`; mais `outro` e `ausente` em cada (FR-010).
- Q: Onde fica a proveniência por `firmware_id`? → A: em arquivo da 008 ao
  lado da tabela, com os `firmware_id` da tabela e das exclusões (FR-014).
- Q: O que conta como falha de extração? → A: leitura falha,
  `meta_binwalk_status=erro` e `meta_unpack_status=falha` são exclusão com
  motivo; `timeout` e `limite_tempo` interrompem a preparação pedindo nova
  extração; `sem_filesystem`, `limite_tamanho` e `limite_arquivos`
  continuam na tabela (FR-007).
- Q: Aliases do mesmo `firmware_id` com valores diferentes? → A: a
  preparação falha listando `firmware_id` e colunas, sem gravar (FR-002).
- Q: O que fazer com as checagens de `dataset/raw/` de
  `scripts/validate_dataset.py`? → A: a validação nova confere o artefato
  e os órfãos (arquivo de `dataset/raw/` sem linha na tabela de features);
  as demais checagens saem com o script (FR-015).
- Q: Órfão faz a validação falhar? → A: sim, com saída diferente de 0 e a
  lista por fabricante (FR-015).
- Q: Nome canônico do fabricante TP-Link? → A: `tp_link`; os 27 arquivos
  de `tplink` são movidos e os 26 pares, buscados de novo (FR-016).
- Q: `firmware_id` com mais de um motivo de exclusão? → A: o registro
  lista todos; a contagem por motivo pode somar mais que o total de
  excluídos (FR-008).
- Q: Como as features do filesystem (`012`) chegam à 008? → A: como
  colunas da mesma tabela de features; a forma final é confirmada no
  clarify da `012` (FR-003).
- Q: Nomes dos artefatos? → A: `dataset/processed/training_table.parquet`,
  `training_table_exclusions.csv`, `training_table_provenance.jsonl` e
  `training_table.meta.json` (FR-013, FR-014).
- Q: Tabela de features sem `meta_binwalk_status`, `meta_unpack_status` ou
  `meta_third_party`? → A: falhar citando a coluna e pedindo nova extração,
  como `005/FR-020` (FR-001).
- Q: Contagem por fabricante com aliases de fabricantes diferentes? → A:
  o `firmware_id` conta uma vez em cada fabricante dos aliases; o log
  registra quantos `firmware_id` têm mais de um fabricante (FR-008).
- Q: Tabela vazia ou classe sem exemplo depois das exclusões? → A: os dois
  interrompem a preparação sem gravar, citando a contagem por classe
  (FR-008).

### Analyze 2026-09-25

- Q: Linha de feature com `firmware_id` nulo (leitura falhou)? → A:
  interrompe a preparação pedindo nova extração, como `005/FR-002`;
  `meta_binwalk_status=nao_executado` também (FR-002, FR-007).
- Q: Modelos TP-Link escritos com `_` em `tplink` e `-` em `tp_link`? → A:
  o mapa troca `_` por `-` no nome do modelo; diretório de modelo de
  destino que já tem arquivo é erro, resolvido à mão pelo pesquisador
  (FR-016).
- Q: Ordem entre exclusões e checagem de aliases divergentes? → A:
  exclusões por alias primeiro; a divergência só é checada nos
  `firmware_id` que ficam (FR-002).
- Q: Como garantir que os rótulos vieram da mesma tabela de features? →
  A: o SHA256 de `--features` em `labels_v2.meta.json` (`005/FR-018`)
  DEVE ser igual ao da tabela lida (FR-001).
- Q: Como justificar a lista fixa do one-hot? → A: por domínio: tipos de
  filesystem e de compressão de firmware embarcado que o Binwalk
  reconhece, não pela contagem no dataset (FR-010).
- Q: Como comparar órfãos? → A: pelo caminho relativo à raiz do dataset
  (`004/FR-016`), aplicando à listagem a regra de seleção de arquivos de
  `001/FR-001` (FR-015).
- Q: Busca de CVE depois da unificação? → A: a busca completa na NVD, com
  `003/FR-014`, porque `005/FR-026` recusa o cache v2 inteiro (FR-016).
- Q: Caminho da tabela de features? → A:
  `dataset/processed/features_v2.parquet` (FR-001).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Tabela de treino sem vazamento (Priority: P1)

O pesquisador gera, a partir da tabela de features (`001-extracao-features`)
e da tabela de rótulos (`005-rotulagem-cve`), uma tabela com uma linha por
`firmware_id`, as colunas de feature e o alvo `security_level`. A banca
confere que nenhuma coluna do vetor carrega identidade do dispositivo,
dado de CVE ou metadado de proveniência (constituição, princípio III).

**Why this priority**: todo número do TCC sai desta tabela; um vazamento
aqui invalida treino e avaliação (TickTick T08).

**Independent Test**: gerar a tabela a partir de features e rótulos de
teste com aliases, colunas `meta_*`, `doc2vec_*` e campos de CVE, e
conferir as linhas, as colunas e o alvo.

**Acceptance Scenarios**:

1. **Given** uma tabela de features com dois aliases do mesmo
   `firmware_id` e os rótulos correspondentes, **When** o pesquisador
   prepara o dataset, **Then** a tabela tem uma linha para esse
   `firmware_id`, com as features e o `security_level`.
2. **Given** entradas com `meta_*`, `vendor`, `model`, `version`,
   `version_source`, `cve_total`, `cvss_max`, `label_strategy`,
   `alias_count` e `doc2vec_*`, **When** a tabela é gerada, **Then**
   nenhuma dessas colunas está no vetor e o teste de guarda de vazamento
   passa.
3. **Given** um `firmware_id` presente nas features e ausente nos rótulos
   (ou o contrário), **When** o pesquisador prepara o dataset, **Then** a
   execução falha listando os `firmware_id` sem par, sem gravar nada.
4. **Given** dois aliases do mesmo `firmware_id`, nenhum excluído, com
   `n_filesystems` diferente, **When** o pesquisador prepara o dataset,
   **Then** a execução falha citando o `firmware_id` e a coluna, sem
   gravar nada.
5. **Given** uma linha de feature com `firmware_id` nulo, **When** o
   pesquisador prepara o dataset, **Then** a execução falha citando o
   arquivo e pedindo nova extração, sem gravar nada.
6. **Given** `labels_v2.meta.json` com SHA256 de `--features` diferente
   do da tabela de features lida, **When** o pesquisador prepara o
   dataset, **Then** a execução falha citando os dois SHA256.

---

### User Story 2 - Exclusões auditáveis (Priority: P1)

O pesquisador vê quais firmwares ficaram fora do treino e por quê:
rótulo `indeterminado`, imagem de terceiros marcada em `meta_third_party`
(`004/FR-017`) e falha de extração. A banca confere as contagens por
motivo e por fabricante e que nenhum firmware sumiu sem registro.

**Why this priority**: 126 dos 699 `firmware_id` são `indeterminado`
(medido em 2026-09-25 sobre `dataset/labels_v2.csv`), concentrados em
alguns fabricantes (asus 58, dlink 37, netgear 17); excluir sem registro distorce a comparação por fabricante
(TickTick T08, aceite).

**Independent Test**: preparar o dataset com linhas de cada motivo de
exclusão e conferir o registro de exclusões e as contagens.

**Acceptance Scenarios**:

1. **Given** firmwares com rótulo `indeterminado`, **When** o dataset é
   preparado, **Then** eles ficam fora da tabela e aparecem no registro de
   exclusões com o motivo e os fabricantes dos aliases.
2. **Given** uma imagem com `meta_third_party` preenchido, **When** o
   dataset é preparado, **Then** ela fica fora da tabela com o motivo
   `terceiros`.
3. **Given** qualquer entrada, **When** o dataset é preparado, **Then** o
   número de linhas da tabela mais o de `firmware_id` excluídos é igual ao
   número de `firmware_id` distintos da entrada.
4. **Given** um arquivo com `meta_binwalk_status=timeout`, **When** o
   dataset é preparado, **Then** a execução falha pedindo nova extração,
   sem gravar nada.
5. **Given** um `firmware_id` com um alias `meta_binwalk_status=erro` e
   outro `ok`, com `fs_type` diferente, **When** o dataset é preparado,
   **Then** ele é excluído como `falha_extracao`, sem falha por
   divergência.

---

### User Story 3 - Vetor só com colunas úteis ao modelo (Priority: P2)

O pesquisador treina com um vetor sem colunas de texto e com os
detectores constantes tratados por regra registrada; a lista de colunas
antes e depois do tratamento fica registrada com a justificativa de cada
remoção (TickTick T07).

**Why this priority**: 105 das 120 colunas de feature são constantes
(medido em 2026-09-25 sobre `features_v2.parquet`) (100 `doc2vec_*` e 5 detectores) e `fs_type`/`compression_type`
são texto, que o scikit-learn não aceita.

**Independent Test**: preparar o dataset com colunas constantes e com
`fs_type`/`compression_type` preenchidos e nulos, e conferir o vetor e a
lista de colunas registrada.

**Acceptance Scenarios**:

1. **Given** `fs_type` e `compression_type` com valores e nulos, **When**
   o dataset é preparado, **Then** o vetor não tem coluna de texto e o
   nulo tem representação própria.
2. **Given** detectores constantes na entrada, **When** o dataset é
   preparado, **Then** eles continuam no vetor e aparecem nos metadados
   como constantes na entrada.
3. **Given** `fs_type=yaffs2`, fora da lista fixa, **When** o dataset é
   preparado, **Then** a linha tem 1 na coluna `outro` de `fs_type`.

---

### User Story 4 - Artefato reprodutível e validado (Priority: P2)

O pesquisador grava a tabela em `dataset/processed/` com metadados
(entradas e SHA256, commit, parâmetros, colunas, contagens) e a valida
antes do treino. Rodar de novo com as mesmas entradas gera a mesma
tabela (constituição, princípio V).

**Why this priority**: a banca precisa reproduzir o dataset de onde saem
os números; `scripts/validate_dataset.py` ainda lê o `labels.csv` v1
(`TODO.md`, pendência de `scripts/validate_dataset.py`).

**Independent Test**: preparar o dataset duas vezes com as mesmas
entradas, comparar os artefatos e rodar a validação contra um artefato
íntegro e contra artefatos com defeito.

**Acceptance Scenarios**:

1. **Given** as mesmas entradas e configuração, **When** o dataset é
   preparado em dois processos, **Then** a tabela e o registro de
   exclusões são idênticos e os metadados só diferem na data.
2. **Given** uma tabela com `firmware_id` duplicado, coluna proibida ou
   SHA256 de entrada diferente do registrado, **When** o pesquisador roda
   a validação, **Then** ela falha citando o problema.
3. **Given** um arquivo em `dataset/raw/` sem linha na tabela de
   features, **When** o pesquisador roda a validação, **Then** ela falha
   listando o órfão sob o fabricante.

---

### User Story 5 - TP-Link com um só nome de fabricante (Priority: P3)

O pesquisador reorganiza `dataset/raw/` para que os firmwares TP-Link
fiquem sob `tp_link`, com um mapa versionado dos
arquivos movidos, e regera features e rótulos (TickTick T08).

**Why this priority**: `tplink` (27 arquivos em 26 modelos, 26 chaves no
cache) e `tp_link` (82 arquivos, 43 chaves), medidos em 2026-09-25 em
`dataset/raw/` e `dataset/cve_cache_v2.json`, aparecem como fabricantes distintos e
distorcem a contagem por fabricante, o baseline de identidade e o
agrupamento da partição.

**Independent Test**: aplicar o mapa num diretório de teste e conferir
que não sobra arquivo sob o nome descartado e que todo arquivo movido
está no mapa.

**Acceptance Scenarios**:

1. **Given** o mapa de movimentação, **When** o pesquisador reorganiza
   `dataset/raw/`, **Then** nenhum arquivo fica sob `tplink`, os modelos
   usam `-` no lugar de `_` e o SHA256 de cada arquivo é o mesmo antes e
   depois.
2. **Given** `tplink/tl_er604w/` e `tp_link/tl-er604w/`, ambos com
   arquivo, **When** o pesquisador reorganiza `dataset/raw/`, **Then** a
   execução falha citando o modelo, sem mover nada.

---

### Edge Cases

- Aliases do mesmo `firmware_id` com valores de feature ou
  `security_level` diferentes: com `firmware_id` calculado sobre o prefixo
  lido (`001/FR-004`), dois arquivos distintos com o mesmo prefixo
  compartilham o ID, e as features estruturais varrem o arquivo inteiro
  (`001/FR-007`). Depois das exclusões, a preparação falha (FR-002).
- Linha de feature com `firmware_id` nulo (leitura falhou, `001/FR-004`):
  a rotulagem já falha (`005/FR-002`) e a preparação também (FR-002).
- Tabela de features anterior a `001/FR-014`, `001/FR-016` ou
  `004/FR-017`, sem `meta_binwalk_status`, `meta_unpack_status` ou
  `meta_third_party`, como o `features_v2.parquet` atual: a preparação
  falha pedindo nova extração (FR-001).
- Tabela de features com `doc2vec_*` (gerada com o Doc2Vec ligado ou antes
  de `001/FR-018`): as colunas NÃO entram no vetor enquanto a T06 for
  Proposto (decisão do pesquisador no analyze da 007, 2026-09-25).
- Todas as linhas excluídas, ou uma classe sem nenhum exemplo depois das
  exclusões (`cve_conhecida` tem 49 `firmware_id` hoje): a preparação
  falha (FR-008).
- `fs_type` ou `compression_type` com valor fora da lista fixa: vai para
  `outro` (FR-010).
- Os 5 detectores constantes hoje (`count_credential_pairs`,
  `has_telnetd`, `has_outdated_libssl`, `has_outdated_busybox`,
  `has_outdated_dropbear`) podem deixar de ser constantes com
  `001/FR-015` e `001/FR-016`; por isso a 008 não os remove (FR-009).
- Modelos TP-Link com o mesmo nome em `tplink` e `tp_link` depois de
  trocar `_` por `-`: medido em 2026-09-25, `tl_er604w`↔`tl-er604w` (os
  dois com arquivo) e `archer_d7b`↔`archer-d7b` (o de `tplink` vazio). O
  primeiro faz a movimentação falhar até o pesquisador resolver à mão;
  diretórios vazios de `tplink/` não contam e são removidos (FR-016).
- A unificação muda as chaves `<fabricante>/<modelo>` do cache de CVE
  (`005/FR-003`): os rótulos só podem ser regerados depois da busca
  completa na NVD com `003/FR-014` (`003-busca-cve`, única etapa com
  rede).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001** [Planejado, TickTick T08]: O sistema DEVE ler a tabela de
  features de `001-extracao-features`
  (`dataset/processed/features_v2.parquet`) e a tabela de rótulos de
  `005/FR-018` (`dataset/processed/labels_v2.csv`), com caminhos vindos da
  configuração versionada ou de override na linha de comando, e falhar
  citando o caminho quando uma delas não existe ou não tem as colunas
  exigidas. A tabela de features sem `meta_binwalk_status`
  (`001/FR-014`), `meta_unpack_status` (`001/FR-016`) ou
  `meta_third_party` (`004/FR-017`) DEVE falhar citando a coluna e a
  instrução de extrair de novo. DEVE falhar citando os dois valores quando
  o SHA256 de `--features` registrado em `labels_v2.meta.json`
  (`005/FR-018`) difere do SHA256 da tabela de features lida.
- **FR-002** [Planejado, TickTick T08]: O sistema DEVE juntar as tabelas
  por `firmware_id` e gravar uma linha por `firmware_id`. DEVE falhar, sem
  gravar nada: citando o arquivo e pedindo nova extração quando alguma
  linha de feature tem `firmware_id` nulo; listando os `firmware_id` quando
  algum não tem par na outra tabela; e listando `firmware_id` e colunas
  quando aliases de um `firmware_id` que não foi excluído (FR-005 a
  FR-007, avaliados antes) têm valores diferentes numa coluna de feature ou
  em `security_level`.
- **FR-003** [Planejado, TickTick T08]: O vetor de features DEVE conter
  só colunas de feature da tabela de `001-extracao-features`, inclusive as
  acrescentadas por `012` quando implementada, e as colunas derivadas por
  FR-010. NÃO DEVEM entrar
  `firmware_id` (chave), `meta_*`, `vendor`, `model`, `version`,
  `version_source`, `cve_total`, `cvss_max`, `cve_count_*`,
  `label_strategy`, `alias_count` nem qualquer outra coluna da tabela de
  rótulos além do alvo `security_level`. O teste de guarda de vazamento em
  `tests/` DEVE cobrir a tabela de treino (constituição, princípio III).
- **FR-004** [Planejado, TickTick T08]: Enquanto a T06 (Doc2Vec) for
  Proposto, o vetor NÃO DEVE conter colunas `doc2vec_*`, mesmo quando a
  tabela de features as tem; a remoção DEVE ficar registrada na lista de
  colunas de FR-011.
- **FR-005** [Planejado, TickTick T08]: O sistema DEVE excluir da tabela
  os `firmware_id` com `security_level` `indeterminado` e registrar, por
  fabricante, a proporção de `indeterminado` entre os `firmware_id` da
  entrada.
- **FR-006** [Planejado, TickTick T08]: O sistema DEVE excluir da tabela
  os `firmware_id` com algum alias com `meta_third_party` preenchido
  (`004/FR-017`).
- **FR-007** [Planejado, TickTick T08]: O sistema DEVE excluir da tabela
  os `firmware_id` com algum alias com falha de extração:
  `meta_binwalk_status=erro` ou `meta_unpack_status=falha`. Com
  `meta_binwalk_status` `timeout` ou `nao_executado`, ou
  `meta_unpack_status` `limite_tempo` ou `nao_executado`, em algum alias,
  DEVE falhar sem gravar nada, listando os arquivos e pedindo nova
  extração. `sem_filesystem`, `limite_tamanho` e `limite_arquivos` NÃO
  excluem.
- **FR-008** [Planejado, TickTick T08]: O sistema DEVE gravar um registro
  de exclusões com uma linha por `firmware_id` excluído, todos os motivos
  que se aplicam (`indeterminado`, `terceiros`, `falha_extracao`) e os
  fabricantes dos aliases, e registrar no log e nos metadados as contagens
  por motivo e por fabricante. Um `firmware_id` conta uma vez em cada
  motivo e em cada fabricante dos aliases; o log DEVE registrar quantos
  `firmware_id` têm aliases de mais de um fabricante. Linhas da tabela
  mais `firmware_id` excluídos DEVEM somar os `firmware_id` distintos da
  entrada. Quando a tabela fica vazia ou alguma das três classes fica sem
  exemplo, o sistema DEVE falhar sem gravar nada, citando a contagem por
  classe.
- **FR-009** [Planejado, TickTick T07]: O sistema NÃO DEVE remover
  colunas por critério calculado sobre os dados; DEVE registrar nos
  metadados as colunas do vetor constantes nas linhas da tabela gravada. O filtro de
  variância, ajustado só na partição de treino, fica com `010`. Nenhum
  código de detector é removido.
- **FR-010** [Planejado, TickTick T07]: O sistema DEVE substituir
  `fs_type` e `compression_type` por colunas one-hot com lista fixa de
  categorias na configuração versionada, sem ajuste a dados: `fs_type`
  `squashfs`, `jffs2`, `cramfs`, `ubifs`; `compression_type` `lzma`,
  `gzip`, `xz`, `lzo`; mais `outro` (valor fora da lista) e `ausente`
  (nulo) em cada. Cada linha tem exatamente um 1 por coluna de origem. A
  lista vem do domínio (tipos de filesystem e de compressão de firmware
  embarcado que o Binwalk reconhece), não da contagem no dataset.
- **FR-011** [Planejado, TickTick T07]: O sistema DEVE registrar nos
  metadados a lista de colunas de feature da entrada e a do vetor, com o
  motivo de cada coluna removida ou transformada.
- **FR-012** [Planejado, TickTick T08]: O sistema NÃO DEVE escalar nem
  normalizar as features (constituição, princípio IV: árvores não exigem
  escala).
- **FR-013** [Planejado, TickTick T08]: O sistema DEVE gravar a tabela e
  o registro de exclusões em `dataset/processed/training_table.parquet` e
  `dataset/processed/training_table_exclusions.csv`, com metadados em
  `dataset/processed/training_table.meta.json`:
  caminhos e SHA256 das entradas e dos artefatos gravados (inclusive a
  tabela), commit do código, parâmetros, colunas,
  contagens por classe, por motivo e por fabricante, e data da execução.
  As linhas DEVEM sair ordenadas por `firmware_id`; a data é o único campo
  que muda entre execuções com as mesmas entradas.
- **FR-014** [Planejado, TickTick T08]: O sistema DEVE gravar, fora do
  vetor, em `dataset/processed/training_table_provenance.jsonl`, uma linha
  por `firmware_id` da tabela e do registro de exclusões, ordenada por
  `firmware_id`, com `in_table` (verdadeiro para os da tabela) e os aliases
  (`meta_path`, fabricante e modelo). É a
  fonte da partição agrupada (`009`), do baseline de identidade (`010`) e
  da avaliação por fabricante (`011`); o SHA256 do arquivo vai para os
  metadados.
- **FR-015** [Planejado, TickTick T08]: O sistema DEVE oferecer uma
  validação do artefato que falha, citando o problema, quando há
  `firmware_id` duplicado, coluna proibida por FR-003/FR-004, coluna de
  texto no vetor, alvo fora das três classes definidas, SHA256 de entrada
  diferente do registrado, colunas diferentes das dos metadados, ou
  arquivo de `dataset/raw/` sem linha na tabela de features (órfão,
  listado por fabricante). Órfãos são comparados pelo caminho relativo à
  raiz do dataset (`004/FR-016`; `meta_path` absoluto falha pedindo nova
  extração), e a listagem de `dataset/raw/` aplica a regra de seleção de
  arquivos de `001/FR-001`. Substitui `scripts/validate_dataset.py`, que lê
  o `labels.csv` v1; as demais checagens do script saem com ele: layout é
  `004/FR-015` (que também pega os arquivos soltos em `asus/` da checagem
  "ASUS não roteador") e conteúdo repetido é alias.
- **FR-016** [Planejado, TickTick T08]: O sistema DEVE mover os
  arquivos de `dataset/raw/tplink/<modelo>/` para
  `dataset/raw/tp_link/<modelo'>/`, em que `<modelo'>` é o nome do modelo
  com `_` trocado por `-` (convenção de `tp_link`), com um mapa versionado
  (caminho antigo, caminho novo, SHA256), sem alterar o conteúdo. DEVE
  falhar sem mover nada, citando o modelo, quando o diretório de destino
  já tem arquivo. Diretórios de `tplink/` sem arquivo não contam como
  modelo e são removidos depois da movimentação. Depois, a busca completa
  na NVD gravada no cache (`003-busca-cve`, com `003/FR-014`) DEVE rodar
  de novo, e features e rótulos, ser regerados.
- **FR-017** [Planejado, TickTick T08]: O sistema DEVE registrar em log o
  tamanho da entrada, o da tabela, a contagem de features do vetor, a
  distribuição de `security_level` e as contagens de exclusão
  (constituição, princípio V).

### Key Entities *(include if feature involves data)*

- **Tabela de features**: saída de `001-extracao-features`, uma linha por
  arquivo; aliases compartilham `firmware_id`.
- **Tabela de rótulos**: saída de `005-rotulagem-cve` (`005/FR-015`,
  `005/FR-018`, `005/FR-022`), uma linha por linha da tabela de features.
- **Tabela de treino**: uma linha por `firmware_id` rotulado e não
  excluído; `firmware_id`, colunas do vetor e `security_level`.
- **Registro de exclusões**: uma linha por `firmware_id` excluído, com
  todos os motivos e os fabricantes.
- **Proveniência**: uma linha por `firmware_id` (tabela e exclusões), com
  os aliases (`meta_path`, fabricante, modelo); fora do vetor.
- **Metadados da preparação**: entradas e SHA256, commit, parâmetros,
  colunas antes e depois, contagens e data.
- **Mapa de movimentação TP-Link**: caminho antigo, caminho novo e SHA256
  de cada arquivo movido.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001** [Planejado, TickTick T08]: 0 colunas do vetor pertencem à
  lista proibida de FR-003/FR-004, conferido pelo teste de guarda de
  vazamento.
- **SC-002** [Planejado, TickTick T08]: 100% dos `firmware_id` distintos
  da entrada estão na tabela ou no registro de exclusões, e nenhum nos
  dois.
- **SC-003** [Planejado, TickTick T08]: duas execuções com as mesmas
  entradas em processos separados geram tabela e registro de exclusões
  idênticos byte a byte.
- **SC-004** [Planejado, TickTick T08]: a validação rejeita 100% dos
  defeitos listados em FR-015 nos artefatos de teste e aceita o artefato
  íntegro.
- **SC-005** [Planejado, TickTick T07]: 0 colunas de texto no vetor, e
  100% das colunas removidas ou transformadas têm motivo registrado.
- **SC-006** [Planejado, TickTick T08]: depois da unificação, 0 arquivos
  e 0 diretórios sob `dataset/raw/tplink/`, e 100% dos arquivos movidos
  no mapa com o mesmo SHA256.

## Assumptions

- A tabela de rótulos segue `005/FR-018`, `005/FR-022` e `005/FR-026`
  (cache `schema_version: 3`); o rótulo é igual entre aliases do mesmo
  `firmware_id` (`005`, US3).
- A extração roda com o Doc2Vec desligado por padrão (`001/FR-018`).
- A partição (treino, validação, teste) é da `009`; o treino e os
  baselines, da `010`; métricas e relatórios, da `011`. A 008 entrega a
  tabela com todos os `firmware_id` elegíveis, sem partição.
- As features do filesystem desempacotado (`012`, TickTick T12) chegam
  como colunas da tabela de features; a forma final é confirmada no
  clarify da `012`.
- O filtro de variância ajustado na partição de treino (FR-009) e a
  codificação de qualquer outra coluna dependente de dados são da `010`.
- Balanceamento de classes (class_weight, oversampling) é da `010`.
