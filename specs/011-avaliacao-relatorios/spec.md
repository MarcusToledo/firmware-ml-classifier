# Feature Specification: Avaliação e relatórios

**Feature Branch**: `docs/escopo-restante`

**Created**: 2026-09-25

**Status**: Misto

**Input**: User description: "Spec nova (TickTick T10, com as métricas da
T05 e as ablations e diagnósticos da T03) da avaliação: métricas que não
escondem as classes minoritárias sobre as predições out-of-fold da `010`;
comparação com os baselines e com o baseline de identidade, com
incerteza; ablations por grupo de features nos mesmos folds, sem braço
Doc2Vec enquanto a T06 for Proposto; divisão agrupada × aleatória;
`indeterminado` por fabricante; importância de features; relatório em
`reports/<timestamp>/` reprodutível. Probe de fabricante e
leave-one-vendor-out Proposto."

## Clarifications

### Session 2026-09-25

- Q: Agregação das métricas? → A: por repetição, sobre as predições
  out-of-fold concatenadas (cada `firmware_id` previsto uma vez); média e
  desvio entre as repetições (FR-002).
- Q: Incerteza e comparação pareada? → A: bootstrap pareado por grupo da
  `009`: reamostra os grupos com reposição, 2000 vezes, seed 0, sobre as
  predições out-of-fold dos dois modelos; IC 95% percentil da métrica e da
  diferença, média entre repetições; diferença relevante só quando o IC
  não cruza 0, sem p-valor (FR-003).
- Q: Braços de ablation? → A: completo; cada grupo sozinho (E
  estatísticas, B estruturais/Binwalk, S strings, F filesystem da `012`);
  completo sem cada grupo; e o braço sem URL/IP (FR-005, FR-007).
- Q: O que é "sem identificadores textuais explícitos" no vetor atual? →
  A: o braço completo sem `count_urls`, `count_hardcoded_ips` e
  `count_public_ips`, os detectores que podem carregar domínios e IPs do
  fabricante (FR-007).
- Q: Método de importância? → A: permutação no teste de cada fold,
  macro-F1, 10 repetições, seed fixa; média e desvio entre os folds. MDI só
  em apêndice, com o aviso do viés (FR-010).
- Q: Que execuções entram no relatório? → A: as que a própria avaliação
  gera pela `010` a partir da matriz da configuração; `run_id` existente
  com os mesmos parâmetros é reaproveitado, com parâmetros diferentes
  falha (FR-001).
- Q: Formato? → A: tabelas CSV (fonte dos números), `report.md` que as
  reúne, figuras PNG e `report.meta.json` (FR-011).
- Q: Parâmetros do bootstrap? → A: 2000 reamostragens, seed 0, em
  `configs/evaluation.yaml` (FR-003).
- Q: Escopo das ablations? → A: Extra Trees e Random Forest, experimento
  de três classes, esquema `grouped` (FR-005).
- Q: Matriz principal? → A: Extra Trees, Random Forest, majoritário,
  identidade e `score_firmware` nos dois experimentos em `grouped`; Extra
  Trees e Random Forest também em `random`, como diagnóstico (FR-001,
  FR-008).
- Q: Grupo de `entropy_variance_across_sections`? → A: B, como no
  data-model da `001` (FR-005).

### Analyze 2026-09-25

- Q: Como marcar as execuções de diagnóstico nas tabelas por execução? →
  A: coluna `purpose` em toda tabela por execução, e seção separada no
  `report.md`; SC-001 vale para 100% das execuções (FR-008).
- Q: IC da importância? → A: IC 95% percentil da queda entre os folds,
  sem reamostragem nova (FR-010).
- Q: Scorer da permutação num fold sem alguma classe? → A: macro-F1 com as
  classes do experimento fixas e `zero_division=0`; a mesma regra vale
  para as métricas de FR-002 (FR-002, FR-010).
- Q: Braços de ablation do Extra Trees saem como `reportado`? → A: a `010`
  deriva `purpose: ablation` quando o conjunto de colunas não é o completo
  (`010/FR-006`).
- Q: Reaproveitamento de `run_id`? → A: a `011` calcula o `run_id` pela
  API da `010`; reaproveita quando `run.meta.json` e
  `predictions.parquet` existem e o hash recalculado dos parâmetros
  registrados bate; diretório sem os dois arquivos falha pedindo `--force`
  na `010`; commit diferente é permitido e fica registrado por `run_id`
  (FR-001).
- Q: A diferença `grouped` × `random` leva IC? → A: sim, bootstrap
  pareado com os grupos de `folds_grouped` (FR-008).
- Q: Figuras e `report.md` entram na reprodutibilidade? → A: sim: CSV,
  PNG (metadados fixos) e `report.md` idênticos; só `report.meta.json`
  difere em `created_at` (FR-011). O analyze verificou PNG idêntico em dois
  processos com matplotlib 3.10.8 (Agg).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Métricas que não escondem as classes minoritárias (Priority: P1)

O pesquisador calcula, para cada execução da `010`, macro-F1, balanced
accuracy, macro precisão, macro revocação, métricas por classe e matriz de
confusão. A banca vê o desempenho em `cve_conhecida` (49 exemplos) e não
só a acurácia geral (TickTick T05, aceite).

**Why this priority**: com 423/101/49, a acurácia geral premia prever
sempre `sem_cve_conhecida`.

**Independent Test**: calcular as métricas sobre predições de teste com
valores conhecidos e comparar com o cálculo à mão.

**Acceptance Scenarios**:

1. **Given** as predições de uma execução, **When** o pesquisador avalia,
   **Then** o relatório tem as métricas agregadas, as métricas por classe e
   a matriz de confusão, com a regra de agregação registrada.
2. **Given** um fold de teste sem `cve_conhecida`, **When** a avaliação
   roda, **Then** as métricas são calculadas sobre as predições
   out-of-fold da repetição, sem erro, e o fold fica listado em
   `report.meta.json`.

---

### User Story 2 - Modelos contra baselines e identidade (Priority: P1)

O pesquisador compara Extra Trees, Random Forest, majoritário, identidade
e `score_firmware` com a mesma métrica, nos mesmos folds, com incerteza e
comparação pareada. A banca confere se o modelo supera o baseline de
identidade (constituição III).

**Why this priority**: a constituição III exige mostrar que o ganho não
vem só da identidade.

**Independent Test**: comparar duas execuções com predições conhecidas e
conferir diferença, incerteza e resultado da comparação.

**Acceptance Scenarios**:

1. **Given** as execuções da matriz `grouped`, **When** o pesquisador
   avalia, **Then** a tabela de comparação tem cada modelo e baseline com
   macro-F1 e IC 95%, e a diferença pareada do Extra Trees contra cada um
   com IC 95% do bootstrap por grupo.
2. **Given** o baseline de identidade, **When** o relatório é gerado,
   **Then** ele aparece com `purpose: diagnostico`, nunca como modelo
   reportado.

---

### User Story 3 - Ablations por grupo de features (Priority: P1)

O pesquisador mede o efeito de cada grupo de features treinando os
braços de ablation nos mesmos folds (`010/FR-005`) e comparando-os de
forma pareada (TickTick T03).

**Why this priority**: mostra de onde vem o sinal e se o ganho sobre a
identidade depende de algum grupo.

**Independent Test**: rodar a avaliação de ablation com dois braços de
predições conhecidas e conferir a tabela.

**Acceptance Scenarios**:

1. **Given** a lista de braços da configuração, **When** a ablation roda,
   **Then** cada braço é treinado com as mesmas seeds e folds e aparece na
   tabela com a diferença pareada contra o braço completo.
2. **Given** a T06 como Proposto, **When** a ablation roda, **Then** não
   há braço Doc2Vec e nenhum braço contém `doc2vec_*`.

---

### User Story 4 - Diagnósticos de vazamento e de exclusão (Priority: P2)

O pesquisador compara as métricas da divisão agrupada com as da
aleatória (TickTick T03, "Registrar métricas por estratégia de divisão")
e publica a tabela de `indeterminado` por fabricante da `008`.

**Why this priority**: a diferença entre divisões mede o efeito da
identidade; a tabela de `indeterminado` mostra o viés da exclusão
(asus 58, dlink 37, netgear 17, medido em 2026-09-25).

**Independent Test**: gerar o relatório com execuções nos dois esquemas e
conferir a tabela de diferença.

**Acceptance Scenarios**:

1. **Given** execuções `grouped` e `random` do mesmo modelo, **When** o
   relatório é gerado, **Then** há uma tabela com as métricas das duas e a
   diferença, marcada `diagnostico`.
2. **Given** os metadados da `008`, **When** o relatório é gerado,
   **Then** ele tem a proporção de `indeterminado` por fabricante.

---

### User Story 5 - Importância de features (Priority: P2)

O pesquisador apresenta à banca quais features pesam no Extra Trees e no
Random Forest do braço principal, com um método que não favorece features
contínuas ou de muitos valores (constituição IV).

**Why this priority**: explicabilidade é a razão da escolha de árvores.

**Independent Test**: calcular a importância com os modelos de um fold de
teste e uma feature sem sinal, e conferir que ela fica perto de zero.

**Acceptance Scenarios**:

1. **Given** os modelos por fold do braço principal (`010/FR-007`),
   **When** a importância é calculada, **Then** o relatório tem, por
   feature, a queda média de macro-F1 por permutação e o desvio entre
   folds, calculados só com dados de teste de cada fold.
2. **Given** uma coluna sem relação com o alvo num teste sintético,
   **When** a importância é calculada, **Then** o IC 95% percentil entre
   os folds contém 0.

---

### User Story 6 - Relatório reprodutível (Priority: P2)

O pesquisador gera o relatório em `reports/<timestamp>/` com tabelas,
figuras e metadados (`run_id`, SHA256, commit, configuração); o mesmo
comando e configuração reproduzem os números (TickTick T10, aceite).

**Why this priority**: a banca precisa refazer cada número (constituição
V e VII).

**Independent Test**: gerar o relatório duas vezes e comparar as tabelas.

**Acceptance Scenarios**:

1. **Given** as mesmas execuções e configuração, **When** o relatório é
   gerado duas vezes, **Then** CSV, PNG e `report.md` são idênticos e só o
   diretório com timestamp e `created_at` mudam.
2. **Given** uma execução cujo SHA256 da tabela difere das demais, **When**
   o relatório é gerado, **Then** a geração falha citando os `run_id`.

---

### Edge Cases

- Fold de teste sem alguma classe (1 de 25 com as seeds 0 a 4, `009`).
- Métrica indefinida (precisão de classe nunca prevista).
- Execuções de tabelas ou folds diferentes misturadas no mesmo relatório.
- Braço de ablation com todas as colunas removidas pelo filtro num fold:
  a execução falha (`010/FR-002`) e a avaliação para citando o braço.
- Grupo F sem colunas na tabela (antes da `012`): `so_F` e `sem_F` não
  rodam e o relatório registra o motivo.
- Experimento binário: métricas com duas classes.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001** [Planejado, TickTick T10]: O sistema DEVE gerar pela `010`
  (`train_run`) as execuções da matriz de `configs/evaluation.yaml`:
  Extra Trees, Random Forest, majoritário, identidade e `score_firmware`
  nos experimentos `principal` e `binario` com esquema `grouped`; Extra
  Trees e Random Forest também com `random`, nos dois experimentos; e os
  braços de FR-005 e FR-007. O `run_id` DEVE ser calculado pela API da
  `010` (`010/FR-006`); a execução existente DEVE ser reaproveitada quando
  `run.meta.json` e `predictions.parquet` existem e o hash recalculado dos
  parâmetros registrados é igual ao `run_id`; hash diferente ou diretório
  sem os dois arquivos DEVE falhar, citando o `run_id` e pedindo `--force`
  na `010`. Commit diferente é permitido e fica registrado por `run_id`.
  DEVE falhar, citando os `run_id`, quando execuções do mesmo relatório
  têm SHA256 de tabela ou de proveniência diferentes, ou SHA256 de folds
  diferentes dentro do mesmo esquema; e quando o SHA256 da tabela em
  `outputs` de `training_table.meta.json` difere do das execuções.
- **FR-002** [Planejado, TickTick T05]: O sistema DEVE calcular macro-F1,
  balanced accuracy, macro precisão, macro revocação, precisão, revocação
  e F1 por classe e a matriz de confusão, por repetição, sobre as
  predições out-of-fold concatenadas, e reportar média e desvio entre as
  repetições (matriz de confusão somada), sempre com as classes do
  experimento fixas. Métrica indefinida DEVE valer 0 e ser contada no
  relatório. O experimento binário usa as mesmas métricas com duas
  classes. Os folds de teste sem alguma classe (`009/FR-005`) DEVEM ser
  listados em `report.meta.json`.
- **FR-003** [Planejado, TickTick T10]: O sistema DEVE apresentar macro-F1
  como métrica principal e, para cada modelo e baseline, o IC 95% e a
  diferença pareada contra o Extra Trees com IC 95%, por bootstrap
  pareado por grupo (`009/FR-002`): 2000 reamostragens dos grupos com
  reposição, seed 0, lidas de `configs/evaluation.yaml`, IC percentil,
  média entre repetições. Diferença relevante é a de IC que não cruza 0;
  o relatório NÃO DEVE usar p-valor.
- **FR-004** [Planejado, TickTick T10]: O relatório DEVE marcar o baseline
  de identidade como `diagnostico` e mostrar a diferença pareada entre o
  Extra Trees e ele (constituição III).
- **FR-005** [Planejado, TickTick T10]: O sistema DEVE treinar pela
  `010` (`train_run`), com Extra Trees e Random Forest no experimento
  `principal` e esquema `grouped`, e comparar de forma pareada (FR-003)
  contra o braço completo os braços de `configs/evaluation.yaml`:
  completo; cada grupo sozinho; completo sem cada grupo. Grupos: E
  (`entropy`, `byte_mean`, `compress_ratio`), B (`n_filesystems`,
  `n_crypto_signatures`, `has_encrypted_sections`,
  `entropy_variance_across_sections`, `fs_type__*`, `compression_type__*`),
  S (os 11 detectores de strings) e F (colunas da `012`). Braço que
  depende de grupo sem colunas na tabela NÃO DEVE rodar, e o motivo DEVE
  ficar no relatório.
- **FR-006** [Planejado, TickTick T10]: Enquanto a T06 (Doc2Vec) for
  Proposto, NENHUM braço DEVE conter `doc2vec_*` e não DEVE haver braço
  Doc2Vec (decisão do analyze da `007`, 2026-09-25).
- **FR-007** [Planejado, TickTick T03]: O sistema DEVE incluir o braço sem
  identificadores textuais explícitos: o completo sem `count_urls`,
  `count_hardcoded_ips` e `count_public_ips`, nas mesmas condições de
  FR-005.
- **FR-008** [Planejado, TickTick T03]: O sistema DEVE apresentar as
  métricas das divisões `grouped` e `random` do Extra Trees e do Random
  Forest, nos dois experimentos, e a diferença com IC 95% por bootstrap
  pareado reamostrando os grupos de `folds_grouped`, numa tabela marcada
  `diagnostico`. Toda tabela com uma linha por execução DEVE ter a coluna
  `purpose` (`010/FR-006`), e o `report.md` DEVE apresentar as execuções
  `diagnostico` e `ablation` em seções separadas das de resultado.
- **FR-009** [Planejado, TickTick T10]: O relatório DEVE ter a proporção
  de `indeterminado` por fabricante e as contagens de exclusão por motivo,
  lidas dos metadados da `008` (`008/FR-005`, `008/FR-008`).
- **FR-010** [Planejado, TickTick T10]: O sistema DEVE calcular a
  importância de features dos modelos por fold do braço principal
  (`010/FR-007`) por permutação no teste de cada fold (macro-F1 com as
  classes do experimento fixas e `zero_division=0`, 10 repetições, seed da
  configuração, `n_jobs=1`), e apresentar média, desvio e IC 95% percentil
  entre os folds. A importância por impureza (MDI) só pode aparecer em apêndice,
  com o aviso de que favorece features contínuas e de muitos valores.
- **FR-011** [Planejado, TickTick T10]: O sistema DEVE gravar o relatório
  em `reports/<timestamp>/`: tabelas CSV (fonte dos números), `report.md`
  que as reúne, figuras PNG (matriz de confusão, comparação com IC,
  importância) e `report.meta.json` (`run_id`, commit de cada execução,
  SHA256 das entradas, configuração efetiva, braços não executados, folds
  sem classe). CSV, PNG (metadados fixos) e `report.md` DEVEM ser
  idênticos entre gerações com as mesmas execuções e configuração; só
  `report.meta.json` difere, em `created_at`.
- **FR-012** [Planejado, TickTick T10]: O sistema DEVE registrar em log os
  `run_id` avaliados e o tamanho de cada conjunto de predições
  (constituição V).
- **FR-013** [Proposto, TickTick T10]: O sistema DEVE reportar um probe de
  fabricante por bloco de features (acurácia de prever o fabricante com
  cada bloco) contra a maioria.
- **FR-014** [Proposto, TickTick T03]: O sistema DEVE reportar as métricas
  dos folds leave-one-vendor-out (`009/FR-010`).

### Key Entities *(include if feature involves data)*

- **Execução avaliada**: `run_id` da `010`, com modelo, experimento,
  esquema e conjunto de colunas.
- **Braço de ablation**: nome e conjunto de colunas, na configuração.
- **Relatório**: diretório com timestamp, tabelas, figuras e metadados.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001** [Planejado, TickTick T05]: 100% das execuções avaliadas têm
  macro-F1, balanced accuracy, métricas por classe e matriz de confusão
  no relatório.
- **SC-002** [Planejado, TickTick T10]: duas gerações do relatório com as
  mesmas execuções e configuração têm CSV, PNG e `report.md` idênticos
  byte a byte.
- **SC-003** [Planejado, TickTick T10]: 0 braços com `doc2vec_*` enquanto a
  T06 for Proposto.
- **SC-004** [Planejado, TickTick T10]: toda diferença no relatório (entre
  modelos, braços ou esquemas) vem com IC 95% por bootstrap pareado por
  grupo.
- **SC-005** [Planejado, TickTick T03]: 100% das linhas de execução nas
  tabelas têm `purpose`, e 0 execuções `diagnostico` ou `ablation`
  aparecem nas seções de resultado do `report.md`.

## Assumptions

- As predições, modelos e metadados vêm da `010`; os folds, da `009`; a
  tabela e as exclusões, da `008`.
- O texto do TCC (capítulos de metodologia e resultados) fica fora do
  Spec Kit (escopo restante, PR-10).
- `matplotlib` já está declarado em `pyproject.toml`.
