# Feature Specification: Partição agrupada

**Feature Branch**: `docs/escopo-restante`

**Created**: 2026-09-25

**Status**: Misto

**Input**: User description: "Spec nova (TickTick T03) da
partição do dataset de treino da 008: grupo por `firmware_id` e modelo
para que nenhum `firmware_id` nem modelo apareça em treino e teste;
divisão principal por StratifiedGroupKFold repetido com seeds em
configuração versionada; folds gravados e reutilizados por todos os
modelos e braços (010/011); divisão aleatória só como diagnóstico;
leave-one-vendor-out Proposto."

## Clarifications

### Session 2026-09-25

- Q: Unidade de grupo? → A: componente conectado do grafo que liga cada
  `firmware_id` aos pares (fabricante, modelo) dos seus aliases (FR-002).
- Q: Folds e repetições? → A: 5 folds × 5 repetições, seeds 0 a 4 na
  configuração versionada (FR-004).
- Q: Fold de teste sem alguma classe? → A: aceitar e registrar nos
  metadados e no log; a `011` decide a agregação das métricas (FR-005).
- Q: Validação para hiperparâmetros? → A: sem tuning; hiperparâmetros
  fixos na configuração versionada da `010`, e sem folds internos. Tuning
  fica Proposto (FR-009).
- Q: Formato dos folds? → A: um arquivo por esquema,
  `dataset/processed/folds_grouped.parquet` e
  `dataset/processed/folds_random.parquet`, cada um com `.meta.json`
  (FR-005, FR-007).
- Q: Contagem por fabricante nos metadados? → A: sim, em treino e teste de
  cada fold, com o fabricante da proveniência (FR-005).

### Analyze 2026-09-25

- Q: Grafias diferentes do mesmo modelo (`rt-n13u`/`rtn13u`,
  `tl-er604w`/`tl_er604w`)? → A: a chave do grafo é fabricante e modelo em
  minúsculas, sem `-`, `_` e espaços; a guarda usa a mesma chave. Revisões
  de hardware (`b1`, `c1`) continuam modelos distintos (`004/FR-004`)
  (FR-002, FR-003).
- Q: A divisão aleatória põe modelos em treino e teste, contra a
  constituição III? → A: violação registrada no Complexity Tracking da
  009 e da `010`, justificada como medida do vazamento, nunca número
  reportado (FR-007).
- Q: Como a `010` recebe seeds e SHA256? → A: `load_folds` devolve a
  tabela de treino, os folds e os metadados juntos; o consumidor não lê a
  tabela por conta própria (FR-006).
- Q: `n_repeats` e `seeds` redundantes? → A: só `seeds`; o número de
  repetições é o tamanho da lista (FR-004).
- Medição com a regra final (2026-09-25, `features_v2.parquet` e
  `dataset/labels_v2.csv`, 573 `firmware_id` com rótulo definido, antes
  das exclusões por terceiros e falha de extração da `008`): 226 grupos, o
  maior com 21 `firmware_id`; `cve_conhecida` em 14 grupos e
  `cve_critica` em 32; 12 grupos com classes diferentes. Simulação 5×5:
  com seeds 0 a 4, 0 modelos cruzando e 1 de 25 folds de teste sem alguma
  classe; com seeds 0 a 19, 2 de 100.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Grupos sem vazamento (Priority: P1)

O pesquisador atribui a cada `firmware_id` da tabela de treino um grupo,
de forma que nenhum `firmware_id` e nenhum modelo apareçam ao mesmo tempo
em treino e teste. A banca confere a regra e o teste de guarda
(constituição, princípio III).

**Why this priority**: 73 dos 699 `firmware_id` são o mesmo binário
publicado para mais de um modelo (medido em 2026-09-25 sobre
`features_v2.parquet`; ex.: um binário em 9 modelos ASUS). Agrupar só por
modelo poria o mesmo binário em treino e teste (TickTick T03, aceite).

**Independent Test**: gerar os grupos a partir de uma proveniência de
teste com um binário em dois modelos e um modelo com dois binários, e
conferir que os dois ficam no mesmo grupo e em um só lado de cada fold.

**Acceptance Scenarios**:

1. **Given** um `firmware_id` com aliases nos modelos A e B, e outro
   `firmware_id` só no modelo B, **When** o pesquisador gera os grupos,
   **Then** os dois `firmware_id` ficam no mesmo grupo.
2. **Given** qualquer fold de `folds_grouped`, **When** o teste de guarda
   roda, **Then** nenhum `firmware_id` e nenhum modelo (chave canônica de
   FR-002) aparece em treino e teste do mesmo fold.
3. **Given** a mesma proveniência com as linhas em outra ordem, **When** o
   pesquisador gera os grupos, **Then** os identificadores de grupo são os
   mesmos.
4. **Given** aliases em `asus/rt-n13u` e `asus/rtn13u`, **When** o
   pesquisador gera os grupos, **Then** os `firmware_id` dos dois ficam no
   mesmo grupo.

---

### User Story 2 - Divisão principal reprodutível (Priority: P1)

O pesquisador gera a divisão principal do TCC, validação cruzada
estratificada por classe e agrupada, repetida com seeds da configuração
versionada, e grava os folds. Treino e avaliação de todos os modelos e
braços usam os mesmos folds (constituição, princípio V).

**Why this priority**: todos os números do TCC são médias sobre esses
folds; folds diferentes por modelo invalidariam a comparação pareada
(TickTick T03, "Definir a divisão principal do TCC").

**Independent Test**: gerar os folds duas vezes, em processos separados,
com a mesma tabela e configuração, e comparar os artefatos.

**Acceptance Scenarios**:

1. **Given** a mesma tabela e configuração, **When** os folds são gerados
   em dois processos, **Then** os artefatos são idênticos e os metadados
   só diferem na data.
2. **Given** os folds gravados, **When** o pesquisador lê os metadados,
   **Then** vê seeds, número de folds e repetições, regra de grupo, SHA256
   da entrada, contagem por classe e por fabricante em cada fold e os
   folds de teste sem alguma classe.
3. **Given** uma tabela de treino diferente da registrada nos folds,
   **When** um consumidor (010/011) lê os folds, **Then** a leitura falha
   citando os dois SHA256.

---

### User Story 3 - Diagnóstico com divisão aleatória (Priority: P2)

O pesquisador gera também uma divisão estratificada sem grupos, com as
mesmas seeds, marcada como diagnóstico. A `011` compara as métricas das
duas divisões para mostrar quanto a divisão aleatória infla o resultado.

**Why this priority**: a diferença entre as duas divisões mede o
vazamento por identidade (TickTick T03, "Comparar divisão aleatória com
divisões agrupadas"); não é resultado principal.

**Independent Test**: gerar a divisão diagnóstica e conferir que ela está
marcada como diagnóstico e usa as mesmas seeds da principal.

**Acceptance Scenarios**:

1. **Given** a configuração, **When** o pesquisador gera as divisões,
   **Then** `folds_random.parquet` é separado de `folds_grouped.parquet`,
   com `purpose: diagnostico` nos metadados.

---

### User Story 4 - Estresse por fabricante (Priority: P3) *(Proposto)*

O pesquisador avalia com leave-one-vendor-out: treina sem um fabricante e
testa nele, para medir generalização a fabricante não visto (TickTick
T03, "Criar avaliação adicional agrupada por fabricante").

**Why this priority**: diagnóstico adicional; a constituição III já é
atendida pelo baseline de identidade (`010`) e pela divisão agrupada.

**Independent Test**: gerar os folds por fabricante e conferir que cada
fabricante é teste em exatamente um fold.

**Acceptance Scenarios**:

1. **Given** os fabricantes da proveniência, **When** o pesquisador gera os folds por
   fabricante, **Then** há um fold por fabricante e nenhum fabricante do
   teste aparece no treino.

---

### Edge Cases

- Classe rara: `cve_conhecida` aparece em só 14 dos 226 grupos, e
  `cve_critica` em 32 (medição da seção Analyze). Com 5 folds, 1 de 25
  folds de teste com as seeds 0 a 4 (2 de 100 com as seeds 0 a 19) fica
  sem alguma classe: aceito e registrado (FR-005).
- Grupo grande: o maior grupo tem 21 `firmware_id`; ele desequilibra o
  tamanho dos folds.
- Grupo com classes diferentes: 12 grupos misturam classes; a
  estratificação por grupo é aproximada.
- Grafias diferentes do mesmo modelo: 11 modelos ASUS com 2 ou 3 grafias
  (`rt-n13u`/`rtn13u`, `rt-n12-d1`/`rt-n12d1`…) e `tl-er604w`/`tl_er604w`
  (medido em 2026-09-25); a chave canônica de FR-002 os junta.
- `firmware_id` com aliases de dois fabricantes (1 hoje): o grupo liga os
  dois fabricantes.
- Tabela de treino regerada depois dos folds (outro SHA256): folds
  antigos não valem.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001** [Planejado, TickTick T03]: O sistema DEVE ler a tabela de
  treino e a proveniência de `008/FR-013` e `008/FR-014` e falhar, citando
  os valores, quando o SHA256 de alguma delas difere do registrado em
  `outputs` de `training_table.meta.json`.
- **FR-002** [Planejado, TickTick T03]: O sistema DEVE atribuir a cada
  `firmware_id` da tabela o grupo dado pelo componente conectado do grafo
  que liga cada `firmware_id` às chaves de modelo dos seus aliases na
  proveniência (`008/FR-014`), usando só as linhas com `in_table=true`. A
  chave de modelo é fabricante e modelo em minúsculas, sem `-`, `_` e
  espaços. O identificador do grupo DEVE ser determinístico e independente
  da ordem das linhas.
- **FR-003** [Planejado, TickTick T03]: Em todo fold dos dois esquemas,
  nenhum `firmware_id` DEVE aparecer em treino e teste; em todo fold de
  `folds_grouped`, também nenhuma chave de modelo de FR-002. A geração
  DEVE falhar sem gravar nada se a checagem falhar, e o teste de guarda em
  `tests/` DEVE cobri-la (constituição III).
- **FR-004** [Planejado, TickTick T03]: A divisão principal DEVE ser
  validação cruzada estratificada por `security_level` e agrupada pelo
  grupo de FR-002, com 5 folds e seeds 0 a 4, lidos da configuração
  versionada ou de override registrado. O número de repetições é o
  tamanho da lista de seeds.
- **FR-005** [Planejado, TickTick T03]: O sistema DEVE gravar os folds em
  `dataset/processed/folds_grouped.parquet` (por repetição e fold, cada
  `firmware_id` com papel treino ou teste e o grupo) e os metadados em
  `dataset/processed/folds_grouped.meta.json`: `scheme` (`grouped`),
  `purpose` (`principal`), configuração efetiva com overrides, seeds,
  número de folds, regra de grupo, SHA256 da tabela, da proveniência e do
  arquivo de folds, contagem de grupos, contagem por classe e por
  fabricante em treino e teste de cada fold (o `firmware_id` conta uma vez
  em cada fabricante dos aliases, como em `008/FR-008`), lista de folds de
  teste sem alguma classe, commit e data. A data é o único campo que muda entre
  execuções iguais. Fold de teste sem alguma classe NÃO DEVE interromper a
  geração.
- **FR-006** [Planejado, TickTick T03]: O sistema DEVE oferecer a leitura
  usada por `010` e `011`, que devolve juntos a tabela de treino, a
  proveniência, os folds e os metadados (seeds, SHA256), e falha, citando
  os valores, quando o SHA256 da tabela, da proveniência ou do arquivo de
  folds difere do registrado. O consumidor NÃO DEVE ler a tabela por conta
  própria.
- **FR-007** [Planejado, TickTick T03]: O sistema DEVE gerar, em
  `dataset/processed/folds_random.parquet` e `folds_random.meta.json`,
  com `scheme: random` e `purpose: diagnostico`, uma divisão estratificada
  por `security_level` sem grupos, com os mesmos folds e seeds da
  principal. Nenhum `firmware_id` aparece em treino e teste; modelos
  aparecem, o que viola a constituição III e está registrado no Complexity
  Tracking: a divisão só mede o vazamento e nenhum número dela é
  resultado reportado.
- **FR-008** [Planejado, TickTick T03]: O sistema DEVE registrar em log o
  número de `firmware_id` e de grupos, o tamanho do maior grupo e a
  contagem por classe em cada fold (constituição V).
- **FR-009** [Proposto, TickTick T03]: Quando houver escolha de
  hiperparâmetros por dados (tuning), a partição DEVE gerar folds internos
  agrupados pela regra de FR-002 dentro do treino de cada fold externo,
  sem nenhum `firmware_id` do teste externo. Enquanto isso, a `010` usa
  hiperparâmetros fixos e não há folds internos.
- **FR-010** [Proposto, TickTick T03]: O sistema DEVE gerar folds
  leave-one-vendor-out, um por fabricante, em artefato separado marcado
  `estresse`.

### Key Entities *(include if feature involves data)*

- **Grupo**: identificador por `firmware_id`, derivado da proveniência
  (`008/FR-014`); fora do vetor.
- **Fold**: repetição, índice e os `firmware_id` de treino e de teste,
  com o grupo de cada um.
- **Metadados da partição**: seeds, parâmetros, regra de grupo, SHA256 das
  entradas, contagens, commit e data.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001** [Planejado, TickTick T03]: 0 `firmware_id` e 0 chaves de
  modelo (FR-002) em treino e teste do mesmo fold, em todos os folds da
  divisão principal.
- **SC-002** [Planejado, TickTick T03]: duas gerações com a mesma entrada
  e configuração, em processos separados, produzem folds idênticos.
- **SC-003** [Planejado, TickTick T03]: 100% dos `firmware_id` da tabela
  aparecem no teste de exatamente um fold por repetição.
- **SC-004** [Planejado, TickTick T03]: a divisão diagnóstica é
  identificável em 100% dos artefatos: pelo nome `folds_random.*` e por
  `purpose: diagnostico` nos metadados.

## Assumptions

- A tabela de treino vem da `008` e já exclui `indeterminado`, terceiros e
  falhas de extração; a proveniência traz também os excluídos, marcados
  `in_table=false` (`008/FR-014`), que a 009 ignora.
- O treino por fold, os baselines e o ajuste de transformadores
  (`008/FR-009`) dentro do treino de cada fold são da `010`; métricas,
  comparação entre divisões e testes pareados, da `011`.
- Sem rede e sem leitura de binário: a partição usa só os artefatos da
  `008`.
