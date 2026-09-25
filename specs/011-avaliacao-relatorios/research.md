# Research: Avaliação e relatórios

Decisões do pesquisador (clarify e plano, 2026-09-25).

## R1. Métricas por repetição sobre predições out-of-fold

- **Decisão**: em cada repetição, cada `firmware_id` é previsto uma vez;
  as métricas saem dessas predições concatenadas; média e desvio entre
  as repetições.
- **Justificativa**: com 49 `cve_conhecida`, 1 de 25 folds de teste fica
  sem alguma classe (`009`); macro-F1 por fold ficaria indefinido nesses
  folds. A concatenação usa cada exemplo uma vez por repetição.
- **Alternativa rejeitada**: média por fold.

## R2. Bootstrap pareado por grupo, sem p-valor

- **Decisão**: reamostrar com reposição os grupos da `009` (não os
  `firmware_id`), 2000 vezes, seed 0; IC 95% percentil da métrica e da
  diferença entre dois modelos sobre as mesmas reamostragens; média entre
  repetições.
- **Justificativa**: os exemplos de um grupo não são independentes;
  reamostrar grupos respeita a mesma unidade da partição. O pareamento
  (mesmas reamostragens para os dois modelos) reduz a variância da
  diferença. O parecer do oracle sugeriu Wilcoxon ou bootstrap pareado;
  o teste t corrigido de Nadeau e Bengio exige métrica por fold, que R1
  descarta. Sem p-valor: a banca lê o IC.

## R3. Ablations

- **Decisão**: grupos E, B, S, F (F quando a `012` existir); braços
  completo, cada grupo sozinho, completo sem cada grupo e `sem_url_ip`;
  Extra Trees e Random Forest, três classes, `grouped`.
- **Justificativa**: "cada grupo sozinho" mostra o sinal próprio;
  "completo sem o grupo" mostra a contribuição marginal. Sem braço
  Doc2Vec enquanto a T06 for Proposto (decisão do analyze da `007`).
  `entropy_variance_across_sections` fica em B, como no data-model da
  `001`.

## R4. Braço sem identificadores textuais explícitos

- **Decisão**: completo sem `count_urls`, `count_hardcoded_ips` e
  `count_public_ips`.
- **Justificativa**: o vetor não tem strings brutas nem `doc2vec_*`
  (`008/FR-003`, `008/FR-004`); os detectores de URL e IP são os que podem
  carregar domínios e endereços do fabricante (TickTick T03, "ablação
  removendo identificadores textuais explícitos").

## R5. Importância por permutação

- **Decisão**: `permutation_importance` no teste de cada fold, macro-F1
  com as classes do experimento fixas e `zero_division=0` (via
  `make_scorer`), 10 repetições, seed da configuração, `n_jobs=1`; média,
  desvio e IC 95% percentil entre os folds; MDI só em apêndice.
  O scorer padrão `f1_macro` não fixa as classes: num fold sem uma classe,
  a permutação muda o denominador (verificado no analyze de 2026-09-25:
  0,762 × 0,508 no mesmo exemplo).
- **Justificativa**: a importância por impureza favorece features
  contínuas e de muitos valores (Strobl et al., 2007, citado no parecer do
  oracle); a permutação no teste mede a queda de desempenho fora do
  treino.

## R6. Execuções geradas pela avaliação

- **Decisão**: a `011` gera a matriz pela `010`; calcula o `run_id` pela
  API da `010`; reaproveita a execução quando `run.meta.json` e
  `predictions.parquet` existem e o hash recalculado bate; senão falha
  pedindo `--force`; commit diferente é permitido e registrado.
- **Justificativa**: o relatório fica completo por construção e a
  reexecução não refaz treino já feito.

## R7. Formato

- **Decisão**: CSV (fonte dos números), `report.md`, PNG e
  `report.meta.json` em `reports/<timestamp>/`; CSV, PNG (com `metadata`
  fixo) e `report.md` idênticos entre gerações.
- **Justificativa**: o analyze de 2026-09-25 verificou PNG idêntico em
  dois processos com matplotlib 3.10.8 (Agg); só `report.meta.json` guarda
  a data.

## R8. IC na diferença entre esquemas

- **Decisão**: a diferença `grouped` × `random` usa o mesmo bootstrap
  pareado, reamostrando os grupos de `folds_grouped` (os mesmos
  `firmware_id` estão nas duas execuções).
- **Justificativa**: toda diferença do relatório vem com incerteza
  (SC-004).
