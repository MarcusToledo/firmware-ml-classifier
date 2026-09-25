# Feature Specification: Embeddings Doc2Vec

**Feature Branch**: `docs/specs-retroativas`

**Created**: 2026-09-24

**Status**: Misto

**Input**: User description: "Spec retroativa (Status Implementado) dos embeddings Doc2Vec: treino de um modelo com um documento de strings por firmware, parâmetros versionados, inferência de um vetor doc2vec_* por firmware na extração (zeros sem modelo) e inspeção de tokens. Variante experimental fora do modelo reportado (constituição, princípio I). Derivar só do código em master, testes, docs/PIPELINE.md e TODO.md."

## Clarifications

### Session 2026-09-24

- Varredura de ambiguidade (`/speckit.clarify`, histórico da spec
  retroativa): sem ambiguidades críticas. Os FRs `[Implementado]` descrevem
  o comportamento do código em `master`; as decisões em aberto
  (determinismo da inferência, treino por partição, conjunto de arquivos do
  treino) ficaram em Edge Cases. Nenhuma pergunta feita nessa varredura.
- Terminologia: "documento" é o texto de strings de um firmware definido em
  `001/FR-006`; "token" é cada pedaço desse texto separado por espaço em
  branco; "vetor Doc2Vec" são as colunas `doc2vec_*` de uma linha.

### Session 2026-09-24 (escopo restante, TickTick T06)

- O pesquisador classificou a T06 inteira como Proposto (mapa de escopo
  restante, PR-01): FR-011 a FR-015 são `[Proposto, TickTick T06]`, sem
  task. A varredura não achou ambiguidade que mude a entrega do TCC; as
  escolhas de implementação ficam para quando a T06 for promovida.
- Com `001/FR-018` (Planejado, TickTick T07), o Doc2Vec fica desligado por
  padrão: o modelo não é carregado, não há aviso de modelo ausente
  (FR-007) e `meta_doc2vec_used=False` (FR-009).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Treinar o modelo Doc2Vec a partir do dataset (Priority: P1)

O pesquisador aponta o treino para `dataset/raw` e obtém um modelo Doc2Vec
gravado em `models/doc2vec.model`, com um documento de strings por
firmware e parâmetros vindos da configuração versionada.

**Why this priority**: sem o modelo, as colunas `doc2vec_*` da extração
saem zeradas e a variante experimental não pode entrar na ablation
(constituição, princípio I).

**Independent Test**: treinar com dois documentos e conferir que o modelo
tem um vetor de documento por `firmware_id`, com `vector_size` posições.

**Acceptance Scenarios**:

1. **Given** um diretório com firmwares `.bin`, **When** o pesquisador roda
   `train-doc2vec --input dataset/raw`, **Then** o modelo é gravado em
   `models/doc2vec.model` e o log informa o path.
2. **Given** a configuração versionada, **When** o pesquisador passa
   `--override doc2vec.vector_size=200`, **Then** o modelo tem vetores de
   200 posições.
3. **Given** `--output outro/caminho.model`, **When** o treino termina,
   **Then** o modelo é gravado nesse path, e os diretórios que faltam são
   criados.
4. **Given** `--override doc2vec.workers=2`, **When** o treino começa,
   **Then** ele falha com erro que cita `workers`, sem gravar modelo.
5. **Given** uma entrada sem nenhum documento válido (arquivos vazios ou
   sem tokens), **When** o treino roda, **Then** ele falha com
   `No valid documents found for Doc2Vec training`.

---

### User Story 2 - Vetor Doc2Vec na tabela de features (Priority: P1)

O pesquisador roda a extração e recebe, em cada linha de
`features.parquet`, um vetor `doc2vec_0` … `doc2vec_{n-1}` inferido do
documento do firmware. A banca vê em `meta_doc2vec_used` se o vetor veio
de um modelo ou é zero. Com `001/FR-018` (Planejado), isso só vale com o
Doc2Vec ligado por chave explícita.

**Why this priority**: é o único caminho pelo qual o embedding chega ao
dataset; a banca precisa distinguir vetor inferido de vetor ausente.

**Independent Test**: extrair um firmware sem modelo configurado e conferir
que as colunas `doc2vec_*` são zero e `meta_doc2vec_used=False`.

**Acceptance Scenarios**:

1. **Given** `doc2vec.model_path` apontando para arquivo inexistente,
   **When** a extração roda, **Then** o log registra um warning de que os
   embeddings serão zero, as `vector_size` colunas `doc2vec_*` saem 0.0 e
   `meta_doc2vec_used=False`.
2. **Given** um modelo treinado e um firmware legível, **When** a extração
   roda, **Then** as colunas `doc2vec_*` recebem o vetor inferido e
   `meta_doc2vec_used=True`.
3. **Given** um modelo treinado e um documento sem tokens, **When** o
   vetor é inferido, **Then** ele é zero, com `vector_size` posições, e
   `meta_doc2vec_used=True`.
4. **Given** tokens que não existem no vocabulário do modelo, **When** o
   vetor é inferido, **Then** todos os valores são finitos.

---

### User Story 3 - Inspecionar os tokens antes do treino (Priority: P3)

O pesquisador confere quais tokens o treino veria para uma amostra de
firmwares, com os mesmos limites de leitura e de strings, sem treinar nada.

**Why this priority**: ajuda a calibrar `max_strings` e `max_doc_chars`,
mas não gera artefato.

**Independent Test**: rodar a inspeção sobre um diretório com
`--max-docs 1 --limit 5` e conferir uma linha de log com `firmware_id`,
contagem e 5 tokens.

**Acceptance Scenarios**:

1. **Given** `dataset/raw`, **When** o pesquisador roda
   `inspect-tokens --input dataset/raw --limit 50 --max-docs 20`, **Then**
   o log mostra até 20 firmwares, cada um com `firmware_id`, número total
   de tokens e os 50 primeiros tokens.
2. **Given** `--override feature.max_doc_chars=1000`, **When** a inspeção
   roda, **Then** os tokens refletem o documento cortado em 1000
   caracteres.

---

### Edge Cases

- A inferência não é determinística. O vetor depende da ordem das
  inferências no mesmo modelo (o estado aleatório interno do modelo avança
  a cada chamada) e de `PYTHONHASHSEED` (o vetor inicial é derivado de
  `hash()`). `doc2vec.seed` não altera a inferência: a extração reinicia as
  sementes globais de `random` e `numpy` antes de cada inferência, e a
  biblioteca não usa nenhuma delas. Os três fatos foram medidos pelo oracle
  (`.docs/brainstorming/parecer-doc2vec-oracle.md`). Com vários workers,
  cada um tem sua cópia do modelo, e o vetor passa a depender do
  escalonamento [inferência do oracle pelo mecanismo; não medido].
  Correção Proposto: FR-012 (T06).
- A verificação automatizada de determinismo da inferência passa pelo
  motivo errado: o terceiro vetor difere porque o estado interno avançou,
  não por causa da semente diferente (ver `plan.md`). Correção Proposto:
  FR-012 (T06).
- `models/doc2vec.model` não existe (nem a pasta `models/`). Em
  `features.parquet` e `features_v2.parquet`, as 100 colunas `doc2vec_*`
  são zero e `meta_doc2vec_used=False` em 840 de 840 linhas (medido em
  2026-09-24; já registrado no `TODO.md`). Com `001/FR-018` (Planejado,
  TickTick T07) o Doc2Vec fica desligado por padrão e sem `doc2vec_*`.
- O treino não é por fold nem restrito à partição de treino: usa todos os
  arquivos da entrada. Isso conflita com o princípio III (transformador
  ajustado só no treino). Também não há artefato separado de embeddings
  alinhados a `firmware_id` nem registro da partição (requisitos do
  `AGENTS.md`, "Doc2Vec Requirements"). Correção Proposto: FR-011 e FR-013
  (T06).
- Treino e extração escolhem arquivos por regras diferentes. O treino
  aceita só as extensões `.bin`, `.img`, `.trx`, `.chk`, `.fw` e `.rom`; a
  extração aceita tudo fora da lista de exclusão de `001/FR-001`. Em
  `dataset/raw`, a extração vê 840 arquivos e o treino 774; os 66 restantes
  (sem extensão, sufixos de versão como `.17_ww`, `.bix`, `.hex`, `.7z`)
  recebem vetor de um modelo que não os viu no treino (medido em
  2026-09-24). Correção Proposto: FR-014 (T06).
- O corpus de treino tem aliases repetidos. Os 774 candidatos ao treino
  têm 633 `firmware_id` distintos, e 215 linhas compartilham `firmware_id`
  com outra (medido em 2026-09-24 sobre `features_v2.parquet`, filtrando
  `meta_path` pelas extensões do treino). Cada cópia entra como documento
  com a mesma tag, então o mesmo conteúdo pesa mais no vocabulário e no
  vetor do documento. Correção Proposto: FR-014 (T06).
- A ordem do corpus é a ordem em que o sistema de arquivos devolve os
  arquivos, sem ordenação. O resultado do treino depende dessa ordem
  [inferência: o treino por SGD é sensível à ordem dos documentos; não
  medido]. Correção Proposto: FR-014 (T06).
- O modelo carregado na extração não é conferido contra a configuração. O
  número de colunas `doc2vec_*` segue o modelo, mas um documento sem tokens
  gera `vector_size` zeros da configuração: se os dois diferirem, as linhas
  terão números diferentes de colunas. A inferência usa `epochs`, `alpha` e
  `min_alpha` da configuração de extração, não os do treino. Correção
  Proposto: FR-015 (T06).
- `meta_doc2vec_used=True` também quando o documento não tem tokens e o
  vetor é zero. A linha não distingue vetor inferido de vetor zero nesse
  caso. Correção Proposto: FR-015 (T06).
- Só `doc2vec.workers` é validado no treino. Os outros parâmetros passam
  apenas por conversão de tipo; a extração ignora `doc2vec.workers`.
  Correção Proposto: FR-015 (T06).
- O modelo gravado não registra os limites de leitura e de strings
  (`max_bytes`, `feature.*`) usados para montar o corpus, nem
  `PYTHONHASHSEED`. Ver `data-model.md`. Correção Proposto: FR-013 (T06).
- O documento cobre só as 2000 primeiras strings (`max_strings`), que são
  cabeçalho e ruído. Ver o item "Documento de strings" do `TODO.md`.
- A inspeção de tokens só escreve no log; não gera artefato.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001** [Implementado]: O treino e a inspeção de tokens DEVEM aceitar
  como entrada um diretório (percorrido recursivamente), um arquivo `.txt`
  com um path por linha ou um arquivo único, e DEVEM considerar só arquivos
  cujo nome não começa com `.` e cuja extensão é `.bin`, `.img`, `.trx`,
  `.chk`, `.fw` ou `.rom` (sem distinção de maiúsculas). Um arquivo único
  fora dessas extensões DEVE ser ignorado com warning.
- **FR-002** [Implementado]: O sistema DEVE montar um documento por
  firmware com a mesma leitura e os mesmos limites da extração
  (`max_bytes`, `feature.min_string_len`, `feature.max_single_string_len`,
  `feature.max_strings`, `feature.max_doc_chars`; `001/FR-003` e
  `001/FR-006`) e DEVE dividi-lo em tokens por espaço em branco,
  descartando tokens vazios, sem mudar caixa nem filtrar tokens.
- **FR-003** [Implementado]: No treino, cada documento DEVE levar como tag
  o SHA256 dos bytes lidos, a mesma definição de `firmware_id` de
  `001/FR-004`. Arquivo vazio ou ilegível e arquivo sem tokens DEVEM ser
  pulados com warning que cita o path. Sem nenhum documento válido, o
  treino DEVE falhar com `No valid documents found for Doc2Vec training`.
- **FR-004** [Implementado]: O treino e a inspeção DEVEM ler a
  configuração do YAML versionado (`--config`, padrão
  `configs/feature_extraction.yaml`) com overrides `--override chave=valor`
  repetíveis. Os parâmetros `doc2vec.*` DEVEM ter os padrões
  `vector_size` 100, `window` 5, `epochs` 20, `min_count` 2, `seed` 42,
  `workers` 1, `dm` 1, `alpha` 0.025 e `min_alpha` 0.0001, iguais na
  configuração versionada e na ausência dela. A chave `doc2vec.enabled`
  (desligada por padrão) é definida por `001/FR-018` (Planejado).
- **FR-005** [Implementado]: O treino DEVE recusar `doc2vec.workers`
  diferente de 1 com erro que cita `workers`, antes de treinar.
- **FR-006** [Implementado]: O treino DEVE gravar o modelo em `--output`,
  se passado; senão em `doc2vec.model_path`; senão em
  `models/doc2vec.model`. DEVE criar os diretórios que faltam, sobrescrever
  o arquivo existente e registrar o path em log. O modelo gravado DEVE ter
  um vetor de documento de `vector_size` posições por tag do corpus.
- **FR-007** [Implementado]: A extração DEVE carregar o modelo de
  `doc2vec.model_path` uma vez por processo (uma vez no modo sequencial,
  uma por worker no modo paralelo). Sem path configurado ou com arquivo
  inexistente, DEVE registrar warning de que os embeddings serão zero e
  seguir sem modelo.
- **FR-008** [Implementado]: Com modelo, a extração DEVE inferir um vetor
  por firmware a partir dos tokens do documento, usando `doc2vec.epochs`,
  `doc2vec.alpha` e `doc2vec.min_alpha` da configuração, e gravá-lo nas
  colunas float `doc2vec_0` … `doc2vec_{n-1}` (`001/FR-008`). Sem modelo,
  ou com documento sem tokens, o vetor DEVE ser zero com `vector_size`
  posições. Tokens fora do vocabulário DEVEM gerar valores finitos.
- **FR-009** [Implementado]: A extração DEVE gravar
  `meta_doc2vec_used=True` quando há modelo carregado e a leitura do
  firmware deu certo, e `False` nos demais casos, inclusive na linha de
  exceção inesperada (`001/FR-009`).
- **FR-010** [Implementado]: A inspeção de tokens DEVE registrar em log,
  para cada firmware não vazio, o `firmware_id`, o número total de tokens e
  os primeiros `--limit` tokens (padrão 50), parando após `--max-docs`
  firmwares (padrão 20). Firmware vazio DEVE ser pulado com warning e não
  conta no limite.
- **FR-011** [Proposto, TickTick T06]: O treino DEVE usar só os documentos
  da partição de treino (um modelo por fold da partição da spec de
  partição, TickTick T03) e registrar os `firmware_id` usados.
- **FR-012** [Proposto, TickTick T06]: A inferência DEVE ser determinística
  entre processos: reiniciar o estado aleatório do modelo antes de cada
  inferência e exigir `PYTHONHASHSEED` fixo, com teste entre processos.
- **FR-013** [Proposto, TickTick T06]: O treino DEVE gravar ao lado do
  modelo os parâmetros, os limites de leitura e de strings do corpus,
  `PYTHONHASHSEED`, a semente e os `firmware_id` de treino, e um artefato de
  embeddings alinhado a `firmware_id` em `models/`.
- **FR-014** [Proposto, TickTick T06]: Treino e extração DEVEM escolher os
  mesmos arquivos (regra de `001/FR-001`); o corpus DEVE ter um documento
  por `firmware_id`, em ordem determinística. Quando implementado,
  substitui a aceitação de tags repetidas de FR-003.
- **FR-015** [Proposto, TickTick T06]: A extração DEVE conferir a dimensão
  do modelo contra `doc2vec.vector_size`, inferir com os parâmetros do
  treino, gravar `meta_doc2vec_used=False` para documento sem tokens e
  validar todos os parâmetros `doc2vec.*`. Quando implementado, substitui
  o caso "sem tokens" de FR-009.

### Key Entities *(include if feature involves data)*

- **Documento de strings**: texto de um firmware formado pelas strings
  ASCII limitadas (`001/FR-006`); vira a lista de tokens do Doc2Vec.
- **Modelo Doc2Vec**: arquivo `models/doc2vec.model` com vocabulário,
  pesos, hiperparâmetros e um vetor por documento de treino.
- **Parâmetros Doc2Vec**: bloco `doc2vec.*` da configuração de extração
  versionada.
- **Vetor Doc2Vec**: colunas `doc2vec_*` de uma linha de
  `features.parquet`, com a proveniência em `meta_doc2vec_used`.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: com o Doc2Vec ligado (`001/FR-018`), 100% das linhas de
  `features.parquet` com leitura bem-sucedida têm `vector_size` colunas
  `doc2vec_*`. Sem modelo, 100% delas são zero com
  `meta_doc2vec_used=False`: observado em 840 de 840 linhas de
  `features.parquet` e `features_v2.parquet` (medido em 2026-09-24).
- **SC-002**: 100% dos treinos com `doc2vec.workers` diferente de 1 falham
  antes de gravar modelo.
- **SC-003**: o modelo treinado tem exatamente um vetor de documento por
  tag distinta do corpus.

## Assumptions

- O Doc2Vec é variante experimental. As colunas `doc2vec_*` estão hoje no
  vetor da `001-extracao-features` (`001/FR-008`); com `001/FR-018`
  (Planejado) só aparecem com o Doc2Vec ligado. Só entram no modelo reportado se
  superarem na ablation uma representação simples (constituição, princípio
  I). O treino do classificador, onde essa exclusão será aplicada, ainda
  não existe.
- O gensim é dependência obrigatória (`pyproject.toml`), mesmo quando não
  há modelo.
- O modelo é produzido localmente pelo pesquisador; não há download de
  embeddings externos.
