# Research: Partição agrupada

Decisões do pesquisador (clarify e plano, 2026-09-25). Medições citam data
e artefato.

## R1. Grupo = componente conectado do grafo `firmware_id`–modelo

- **Decisão**: cada `firmware_id` liga-se às chaves de modelo dos seus
  aliases (fabricante e modelo em minúsculas, sem `-`, `_` e espaços); cada
  componente conectado é um grupo. Só as linhas `in_table=true` da
  proveniência entram.
- **Justificativa**: 73 `firmware_id` são o mesmo binário em mais de um
  modelo (34 em 2, 26 em 3, 12 em 4 ou mais; 63 ASUS, 9 Netgear, 1
  TP-Link), medido em 2026-09-25 sobre `features_v2.parquet`. Agrupar só
  por modelo poria o mesmo binário em treino e teste. O componente é o
  menor agrupamento que impede os dois cruzamentos (FR-003). O TODO.md já
  previa agrupar por modelo depois de deduplicar por `firmware_id`; o
  parecer do oracle propôs (fabricante, modelo), e a medição mostrou que
  não basta. O analyze de 2026-09-25 mediu grafias diferentes do mesmo
  modelo (11 ASUS, como `rt-n13u`/`rtn13u`, e `tl-er604w`/`tl_er604w`) que,
  sem a chave canônica, cruzavam treino e teste em 24 de 25 folds; com a
  chave, 0. Revisões de hardware continuam modelos distintos, como na
  `004`.
- **Alternativas rejeitadas**: só modelo (viola FR-003); família definida
  à mão (curadoria sem regra objetiva).

## R2. 5 folds × 5 repetições, seeds 0 a 4

- **Decisão**: `StratifiedGroupKFold(n_splits=5, shuffle=True,
  random_state=seed)` para cada seed.
- **Justificativa**: proposta do parecer do oracle (5×5, mesmas partições
  para todos os braços); equilíbrio entre tamanho do teste e estabilidade.

## R3. Fold de teste sem alguma classe é aceito e registrado

- **Decisão**: não interrompe; vai para metadados e log; a `011` decide a
  agregação.
- **Justificativa**: simulação em 2026-09-25 (`StratifiedGroupKFold`,
  573 `firmware_id`, seeds 0 a 19), usada para escolher k com grupos
  sem chave canônica: k=3 → 1 de 60 folds de teste sem alguma classe; k=5
  → 5 de 100 (mediana 8 `cve_conhecida` por fold de teste); k=10 → 44 de
  200. Com a regra final (226 grupos), k=5 → 2 de 100. Trocar seeds até
  todos os folds terem as três classes seria escolher a partição olhando
  os dados.

## R4. Sem tuning, sem folds internos

- **Decisão**: hiperparâmetros fixos na configuração da `010`; CV aninhada
  fica Proposto (FR-009).
- **Justificativa**: com 573 exemplos e 49 `cve_conhecida`, folds internos
  teriam poucos exemplos da classe rara; hiperparâmetros fixos e
  justificados são mais simples de auditar (constituição IV).

## R5. Um arquivo por esquema; leitura com checagem na 009

- **Decisão**: `folds_grouped.*` e `folds_random.*`; `load_folds` em
  `src/dataset/partition.py` confere SHA256 da tabela, da proveniência e
  dos folds e devolve tudo junto, com as seeds, para que o consumidor não
  releia configuração nem tabela (analyze, 2026-09-25). A lista de seeds
  define o número de repetições.
- **Justificativa**: o nome e os metadados separam o diagnóstico do
  resultado principal; uma única função de leitura evita que `010` e
  `011` repitam a checagem de FR-006.

## R6. Divisão diagnóstica

- **Decisão**: `StratifiedKFold` com as mesmas seeds e parâmetros.
- **Justificativa**: a diferença de métricas entre as duas divisões mede o
  efeito da identidade (TickTick T03); mesmas seeds deixam a comparação
  pareada por repetição. Viola a constituição III (modelos em treino e
  teste) e está no Complexity Tracking, com decisão do pesquisador no
  analyze de 2026-09-25.
