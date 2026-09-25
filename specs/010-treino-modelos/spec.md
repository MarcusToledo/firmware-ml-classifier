# Feature Specification: Treino de modelos e baselines

**Feature Branch**: `docs/escopo-restante`

**Created**: 2026-09-25

**Status**: Misto

**Input**: User description: "Spec nova (TickTick T09, com itens da T05)
do treino: Extra Trees (principal) e Random Forest (baseline de ML)
ajustados só no treino de cada fold da `009`, com filtro de variância
ajustado no treino (`008/FR-009`), hiperparâmetros fixos e seed em
configuração versionada; baselines majoritário, de identidade (só
diagnóstico) e `score_firmware` (`006`) nos mesmos folds; `class_weight` e
experimento multiclasse ou binário; modelos em `models/` com
hiperparâmetros, seed e `firmware_id` de treino; predições out-of-fold
para a `011`. Oversampling e tuning Proposto; XGBoost fora (exige emenda
da constituição)."

## Clarifications

### Session 2026-09-25

- Q: Hiperparâmetros? → A: iguais para Extra Trees e Random Forest:
  `n_estimators=500`, `max_features="sqrt"`, `min_samples_leaf=1`,
  `max_depth=None`; `bootstrap` no padrão de cada modelo (FR-003).
- Q: Peso por classe? → A: `balanced`, calculado no treino de cada fold
  (FR-011).
- Q: Experimentos? → A: principal com as três classes de
  `security_level`; complementar binário, `sem_cve_conhecida` contra
  `com_cve` (`cve_conhecida` + `cve_critica`) (FR-012).
- Q: Forma do baseline de identidade? → A: Extra Trees com os mesmos
  hiperparâmetros e peso, só com one-hot de fabricante da proveniência;
  `firmware_id` com aliases de mais de um fabricante recebe 1 em cada
  (FR-009).
- Q: Entrada de `fs_type` e `compression_type` do `score_firmware`? → A:
  as colunas brutas da tabela de features registrada nos metadados da
  `008`, com SHA256 conferido (FR-010).
- Q: O que persistir em `models/`? → A: o modelo de cada fold só para o
  conjunto completo de colunas, o esquema `grouped` e o experimento
  principal; nas demais execuções, predições e metadados por fold
  (FR-007).
- Q: Seed dos modelos? → A: a seed da repetição da `009`, igual em todos
  os folds da repetição e em todos os modelos (FR-003).
- Q: Onde gravar as predições? → A: `models/runs/<run_id>/`, com
  `predictions.parquet` e `run.meta.json`; `run_id` determinístico, hash
  da configuração efetiva e dos SHA256 das entradas (FR-006).

### Analyze 2026-09-25

- Q: Determinismo de `predict_proba` com `n_jobs>1` (soma das árvores em
  threads; o reviewer mediu 4 resultados diferentes em 20 chamadas no
  baseline de identidade)? → A: `n_jobs=1` em ajuste e predição, fixo na
  configuração (FR-003).
- Q: Execuções no esquema `random` marcadas como reportadas? → A: campo
  `purpose` derivado, nos metadados e nas predições: `diagnostico` para o
  baseline de identidade e para todo `scheme=random`; `baseline` para
  Random Forest, majoritário e `score_firmware`; `reportado` só para o
  Extra Trees no esquema `grouped`. O uso da divisão aleatória fica no
  Complexity Tracking (decisão da `009`) (FR-006).
- Q: Predições em `models/runs/` sem timestamp, contra "resultados em
  `reports/`"? → A: mantidas: são saída de modelo, sem métrica; os
  resultados são as tabelas da `011` em `reports/<timestamp>/` (FR-006).
- Q: Probabilidades do majoritário e do `score_firmware`? → A: 1 na classe
  prevista e 0 nas demais (FR-008, FR-010).
- Q: O que entra no `run_id` e o que fazer se o diretório existe? → A:
  hash de modelo, experimento, esquema, colunas ordenadas, configuração
  efetiva, configuração da `006` no `score_firmware` e SHA256 de todas as
  entradas; o commit fica só nos metadados. Diretório existente falha
  citando o `run_id`; `--force` substitui (FR-006).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Extra Trees principal por fold (Priority: P1)

O pesquisador treina o Extra Trees em cada (repetição, fold) da divisão
principal, ajustando o filtro de variância e o modelo só no treino, e
grava o modelo e as predições do teste. A banca confere que nada foi
ajustado com dados de teste e que cada número pode ser refeito
(constituição, princípios III, IV e V).

**Why this priority**: o Extra Trees é o modelo principal (constituição
IV; TickTick T09).

**Independent Test**: treinar com uma tabela e folds de teste pequenos e
conferir predições, artefatos e metadados de cada fold.

**Acceptance Scenarios**:

1. **Given** a tabela da `008` e os folds da `009`, **When** o
   pesquisador treina o Extra Trees, **Then** há um modelo por
   (repetição, fold) e uma predição (classe e probabilidade por classe)
   para cada `firmware_id` do teste de cada fold.
2. **Given** uma coluna constante no treino de um fold e variável no
   teste, **When** o fold é treinado, **Then** o filtro de variância a
   remove nesse fold, e a lista de colunas usadas fica nos metadados do
   fold.
3. **Given** as mesmas entradas e configuração, **When** o treino roda em
   dois processos, **Then** as predições são idênticas.
4. **Given** um conjunto de colunas passado por parâmetro, **When** o
   treino roda, **Then** só essas colunas entram no modelo e o conjunto
   fica nos metadados.

---

### User Story 2 - Random Forest como baseline de ML (Priority: P1)

O pesquisador treina o Random Forest com o mesmo protocolo, os mesmos
folds e o mesmo filtro, para comparar com o Extra Trees fold a fold.

**Why this priority**: baseline de ML exigido pela constituição IV
(TickTick T09).

**Independent Test**: treinar os dois modelos com os mesmos folds e
conferir que as predições cobrem os mesmos `firmware_id` por fold.

**Acceptance Scenarios**:

1. **Given** os folds da `009`, **When** o pesquisador treina o Random
   Forest, **Then** as predições têm os mesmos (repetição, fold,
   `firmware_id`) do Extra Trees.

---

### User Story 3 - Baselines de referência (Priority: P1)

O pesquisador gera, nos mesmos folds, as predições de três referências:
classe majoritária do treino, modelo que só vê o fabricante (baseline de
identidade, diagnóstico) e o baseline de regras `score_firmware` da
`006`. A banca compara os modelos com elas.

**Why this priority**: sem baseline não há como dizer se o ganho vem do
conteúdo do binário ou da identidade (constituição III; Arp et al.,
USENIX Security 2022, pitfall P6; TickTick T05 "Comparar com baseline
majoritário").

**Independent Test**: gerar as três referências com tabela e folds de
teste e conferir as predições.

**Acceptance Scenarios**:

1. **Given** um fold cujo treino tem maioria `sem_cve_conhecida`,
   **When** o baseline majoritário roda, **Then** todas as predições do
   teste são `sem_cve_conhecida`.
2. **Given** a proveniência da `008`, **When** o baseline de identidade
   roda, **Then** ele usa só o fabricante, suas predições e metadados têm
   `purpose: diagnostico` e ele não aparece como modelo reportado.
3. **Given** um firmware com `has_telnetd` verdadeiro, **When** o
   baseline de regras roda, **Then** a predição é a de `score_firmware`
   com a configuração versionada da `006`, sem nenhum ajuste a dados.

---

### User Story 4 - Desbalanceamento de classes (Priority: P2)

O pesquisador treina com peso por classe e roda o experimento principal
e o complementar (multiclasse ou binário) para que a classe rara não
seja ignorada (TickTick T05).

**Why this priority**: 423 `sem_cve_conhecida`, 101 `cve_critica` e 49
`cve_conhecida` por `firmware_id` (medido em 2026-09-25 sobre
`dataset/labels_v2.csv`, sem `indeterminado`).

**Independent Test**: treinar com o peso configurado e conferir que ele
está nos metadados; rodar os dois experimentos e conferir o alvo de cada
um.

**Acceptance Scenarios**:

1. **Given** a configuração de peso por classe, **When** o treino roda,
   **Then** Extra Trees e Random Forest usam o mesmo peso e ele fica nos
   metadados.
2. **Given** o experimento complementar, **When** o treino roda, **Then**
   o alvo é derivado de `security_level` pela regra fixa da
   configuração, registrada nos metadados.

---

### Edge Cases

- Fold de teste sem alguma classe (cerca de 5% dos folds de teste sem
  `cve_conhecida`, `009`): as predições são gravadas normalmente; a
  agregação é da `011`.
- Fold de treino sem alguma classe: o modelo não prevê essa classe; as
  probabilidades precisam manter as três colunas.
- Coluna constante no treino do fold: removida pelo filtro só nesse fold.
- Tabela ou folds com SHA256 diferente do registrado: a leitura falha
  (`009/FR-006`).
- `score_firmware` lê `fs_type` e `compression_type` em texto, que a
  tabela de treino substitui por one-hot (`008/FR-010`): o baseline lê as
  colunas brutas da tabela de features (FR-010).
- Empate de contagem no majoritário: vence a classe na ordem
  `sem_cve_conhecida`, `cve_conhecida`, `cve_critica`; no binário,
  `sem_cve_conhecida`, `com_cve` (FR-008).
- Conjunto de colunas de ablation todo constante no treino de um fold: o
  filtro não deixa coluna, e a execução falha citando repetição, fold e
  colunas (FR-002).
- No experimento binário, `score_firmware` prevê três níveis: `cve_conhecida`
  e `cve_critica` viram `com_cve` pela mesma regra do alvo (FR-012).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001** [Planejado, TickTick T09]: O sistema DEVE ler a tabela de
  treino, a proveniência, os folds e as seeds pela leitura de
  `009/FR-006`, que falha com SHA256 divergente, e a configuração de
  `configs/training.yaml` ou de override registrado.
- **FR-002** [Planejado, TickTick T09]: Para cada (repetição, fold), o
  sistema DEVE ajustar só nos `firmware_id` de treino um filtro que
  remove colunas constantes, e aplicá-lo ao teste; as colunas usadas por
  fold DEVEM ficar nos metadados (é o registro do transformador ajustado,
  constituição V). Se nenhuma coluna sobra, a execução DEVE falhar citando
  repetição, fold e colunas.
- **FR-003** [Planejado, TickTick T09]: O sistema DEVE treinar o Extra
  Trees em cada (repetição, fold), só com os `firmware_id` de treino, com
  hiperparâmetros fixos lidos da configuração versionada
  (`n_estimators=500`, `max_features="sqrt"`, `min_samples_leaf=1`,
  `max_depth=None`, `n_jobs=1` no ajuste e na predição) e `random_state`
  igual à seed da repetição, recebida de `009/FR-006`.
- **FR-004** [Planejado, TickTick T09]: O sistema DEVE treinar o Random
  Forest com o mesmo protocolo, folds, filtro, peso por classe e seed de
  FR-003.
- **FR-005** [Planejado, TickTick T09]: O sistema DEVE aceitar, por
  parâmetro, o conjunto de colunas do vetor a usar (para as ablations da
  `011`) e o esquema de folds (`grouped` ou `random`), e registrá-los nos
  metadados.
- **FR-006** [Planejado, TickTick T09]: Para cada execução (modelo ou
  baseline, experimento, esquema, conjunto de colunas), o sistema DEVE
  gravar em `models/runs/<run_id>/predictions.parquet` as predições do
  teste de cada fold: repetição, fold, `firmware_id`, classe verdadeira,
  classe prevista e probabilidade de cada classe do experimento, sempre
  com todas as classes, mesmo as ausentes no treino do fold, e `purpose`.
  Os metadados vão para `models/runs/<run_id>/run.meta.json`, com a
  configuração efetiva (overrides e regra do alvo) e `purpose`. `purpose`
  DEVE ser `diagnostico` no baseline de identidade e em todo esquema
  `random`, `ablation` em toda execução de Extra Trees ou Random Forest em
  `grouped` com conjunto de colunas diferente do completo, `baseline` no
  Random Forest, no majoritário e no `score_firmware` com colunas
  completas, e `reportado` só no Extra Trees em `grouped` com colunas
  completas. O cálculo do `run_id` DEVE ser exposto como função pública
  para a `011`.
  O `run_id` DEVE ser o hash SHA256 de modelo, experimento, esquema,
  colunas ordenadas, configuração efetiva, configuração da `006` (no
  `score_firmware`) e SHA256 de todas as entradas. Se o diretório já
  existe, a execução DEVE falhar citando o `run_id`, salvo com `--force`,
  que o substitui. As predições são saída de modelo; métricas e tabelas
  (resultados) ficam na `011`, em `reports/<timestamp>/`.
- **FR-007** [Planejado, TickTick T09]: O sistema DEVE persistir em
  `models/runs/<run_id>/` o modelo de cada (repetição, fold) do Extra
  Trees e do Random Forest quando a execução usa o conjunto completo de
  colunas, o esquema `grouped` e o experimento principal. Toda execução
  DEVE registrar em `run.meta.json`, por fold, hiperparâmetros, seed,
  colunas usadas, `firmware_id` de treino e SHA256 da tabela e dos folds
  (constituição V).
- **FR-008** [Planejado, TickTick T09]: O sistema DEVE gerar nos mesmos
  folds as predições do baseline majoritário, ajustado no treino de cada
  fold, com probabilidade 1 na classe prevista e 0 nas demais. Empate de
  contagem é resolvido pela ordem `sem_cve_conhecida`, `cve_conhecida`,
  `cve_critica` (no binário, `sem_cve_conhecida`, `com_cve`).
- **FR-009** [Planejado, TickTick T09]: O sistema DEVE gerar nos mesmos
  folds as predições do baseline de identidade, que usa só o fabricante
  da proveniência (`008/FR-014`): Extra Trees com os hiperparâmetros,
  peso e seed de FR-003 e FR-011, sobre one-hot de fabricante (1 em cada
  fabricante dos aliases; fabricante em minúsculas, sem `-`, `_` e
  espaços, como a chave de `009/FR-002`), com `purpose: diagnostico`. Ele NÃO DEVE ser apresentado como modelo
  reportado (constituição III).
- **FR-010** [Planejado, TickTick T09]: O sistema DEVE gerar nos mesmos
  folds as predições do baseline `score_firmware` (`006`) com a
  configuração versionada da `006`, sem ajuste a dados. A entrada são as
  colunas de feature brutas da tabela de features registrada em
  `training_table.meta.json` (`008/FR-013`), por `firmware_id`, com o
  SHA256 conferido; divergência falha. A probabilidade é 1 no nível
  previsto e 0 nos demais.
- **FR-011** [Planejado, TickTick T05]: Extra Trees e Random Forest DEVEM
  usar `class_weight="balanced"`, lido da configuração versionada e
  calculado no treino de cada fold.
- **FR-012** [Planejado, TickTick T05]: O sistema DEVE rodar o
  experimento principal, com as três classes de `security_level`, e o
  complementar binário, `sem_cve_conhecida` contra `com_cve`
  (`cve_conhecida` e `cve_critica`), com a regra de cada alvo na
  configuração e nos metadados. A regra vale também para as predições do
  `score_firmware`.
- **FR-013** [Planejado, TickTick T09]: O sistema DEVE registrar em log,
  por modelo e fold, tamanho do treino e do teste, contagem por classe,
  número de colunas usadas, hiperparâmetros e seed (constituição V).
- **FR-014** [Proposto, TickTick T05]: Oversampling DEVE ocorrer só no
  treino de cada fold, depois da divisão por grupos, e nunca no teste.

### Key Entities *(include if feature involves data)*

- **Execução de treino**: modelo, esquema de folds, experimento, conjunto
  de colunas, hiperparâmetros, seeds, SHA256 das entradas.
- **Predição out-of-fold**: repetição, fold, `firmware_id`, classe
  verdadeira, prevista e probabilidades.
- **Modelo persistido**: artefato em `models/` com metadados.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001** [Planejado, TickTick T09]: 100% dos `firmware_id` do teste de
  cada fold têm predição de cada modelo e baseline, e 0 `firmware_id` de
  teste entram no ajuste do filtro ou do modelo do fold.
- **SC-002** [Planejado, TickTick T09]: duas execuções com as mesmas
  entradas em processos separados geram predições idênticas.
- **SC-003** [Planejado, TickTick T09]: 100% dos artefatos em `models/`
  têm hiperparâmetros, seed, `firmware_id` de treino e SHA256 das
  entradas.
- **SC-004** [Planejado, TickTick T09]: o baseline de identidade e todas
  as execuções no esquema `random` têm `purpose: diagnostico` em 100% das
  predições e metadados.

## Assumptions

- Hiperparâmetros fixos, sem tuning (decisão do clarify da `009`); tuning
  com validação aninhada é `009/FR-009` (Proposto).
- Métricas, intervalos, testes pareados, ablations e relatórios são da
  `011`; esta spec entrega predições e modelos.
- XGBoost e outras famílias ficam fora até emenda da constituição (IV).
- O Doc2Vec não entra (`008/FR-004`).
