# Research: Treino de modelos e baselines

Decisões do pesquisador (clarify e plano, 2026-09-25).

## R1. Hiperparâmetros fixos, iguais para ET e RF

- **Decisão**: `n_estimators=500`, `max_features="sqrt"`,
  `min_samples_leaf=1`, `max_depth=None`; `bootstrap` no padrão de cada
  modelo (ET sem, RF com).
- **Justificativa**: sem tuning (decisão do clarify da `009`: 49
  `cve_conhecida` não sustentam folds internos). Os valores são os padrões
  do scikit-learn, exceto o número de árvores, que sobe para 500 para
  reduzir a variância da estimativa e da importância. Parâmetros iguais
  deixam a comparação ET × RF depender só do algoritmo (constituição IV).
- **Alternativas rejeitadas**: padrões com 100 árvores; folha mínima 2.

## R2. `class_weight="balanced"`

- **Decisão**: peso inverso à frequência no treino de cada fold.
- **Justificativa**: 423/101/49 por `firmware_id` (medido em 2026-09-25);
  sem peso, a floresta tende a ignorar `cve_conhecida` (TickTick T05).
  `balanced_subsample` só difere no RF e quebraria a igualdade de
  protocolo.

## R3. Experimentos

- **Decisão**: principal com três classes; complementar binário
  `sem_cve_conhecida` × `com_cve`.
- **Justificativa**: as três classes são a regra de rótulo da `005`; o
  binário (423 × 150) responde à pergunta "há CVE conhecida?" com menos
  desbalanceamento.

## R4. Baselines

- **Majoritário**: referência mínima (TickTick T05; Arp et al., P6).
- **Identidade**: Extra Trees com o mesmo protocolo sobre one-hot de
  fabricante (parecer do oracle, braço B1); exigido pela constituição III
  como diagnóstico, nunca modelo reportado.
- **`score_firmware`**: baseline de regras da `006` (constituição II);
  lê as colunas brutas da tabela de features, porque usa `fs_type` e
  `compression_type` em texto.

## R5. Persistência e predições

- **Decisão**: `models/runs/<run_id>/` com `predictions.parquet` e
  `run.meta.json` para toda execução; modelos por fold só no braço
  principal (colunas completas, `grouped`, três classes).
- **Justificativa**: a constituição V exige salvar todo transformador
  treinado com hiperparâmetros, seed e `firmware_id` de treino; os
  metadados por fold (colunas mantidas pelo filtro, hiperparâmetros, seed,
  `firmware_id` de treino) cumprem o registro em toda execução, e os 50 modelos do braço principal
  servem à importância na `011` sem gravar centenas de modelos de
  ablation. O `run_id` é o hash de modelo, experimento, esquema, colunas,
  configuração efetiva e entradas, sem commit; diretório existente falha
  (ou é substituído com `--force`), para não misturar execuções. As
  predições ficam em `models/runs/` por serem saída de modelo; os
  resultados vão para `reports/<timestamp>/` na `011` (analyze,
  2026-09-25).

## R8. `n_jobs=1`

- **Decisão**: `n_jobs=1` no ajuste e na predição.
- **Justificativa**: o analyze de 2026-09-25 verificou no scikit-learn
  1.7.2 que `predict_proba` soma as árvores em threads; com folhas impuras
  (baseline de identidade, ablations com poucas colunas), 20 chamadas com
  `n_jobs=-1` deram 4 resultados diferentes. O dataset é pequeno e o custo
  serial é aceitável.

## R9. `purpose`

- **Decisão**: `reportado` só para o Extra Trees em `grouped` com colunas
  completas; `baseline` para Random Forest (baseline de ML, constituição
  IV), majoritário e `score_firmware`; `ablation` para braços com colunas
  não completas (decisão do analyze da `011`); `diagnostico` para
  identidade e todo `random`.
- **Justificativa**: impede que número de partição não agrupada ou de
  identidade apareça como resultado (constituição III).

## R6. Seed

- **Decisão**: `random_state` = seed da repetição da `009`.
- **Justificativa**: uma só lista de seeds na configuração; o pareamento
  por repetição entre modelos fica natural para os testes da `011`.

## R7. Estrutura

- **Decisão**: `src/models/` (código), `scripts/train.py`,
  `configs/training.yaml`; joblib declarado em `pyproject.toml`.
- **Justificativa**: `scripts/train.py` já é previsto no `AGENTS.md`; a
  constituição exige dependências declaradas, e joblib passa a ser
  importado diretamente.
