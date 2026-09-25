# Implementation Plan: Treino de modelos e baselines

**Branch**: `docs/escopo-restante` | **Date**: 2026-09-25 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/010-treino-modelos/spec.md`

**Note**: spec nova, Status Misto: FR-001 a FR-013 Planejado (TickTick T09
e T05), FR-014 Proposto, sem task. Nenhum código existe ainda; módulos e
testes abaixo são previstos. Estrutura decidida pelo pesquisador em
2026-09-25 ([research.md](research.md)).

## Summary

`scripts/train.py` lê a tabela, a proveniência, os folds e as seeds pela
`load_folds` da `009` (que confere SHA256) e `configs/training.yaml`. Para cada
(repetição, fold), ajusta no treino um filtro de colunas constantes e o
modelo (Extra Trees, Random Forest ou baseline de identidade), com 500
árvores, `max_features="sqrt"`, `class_weight="balanced"` e
`random_state` igual à seed da repetição, e prevê o teste. Os baselines
majoritário e `score_firmware` rodam nos mesmos folds. Cada execução
(modelo, experimento, esquema, conjunto de colunas) grava em
`models/runs/<run_id>/` as predições out-of-fold e os metadados; o braço
principal grava também os modelos por fold.

## Technical Context

**Language/Version**: Python ≥ 3.9

**Primary Dependencies**: scikit-learn (`ExtraTreesClassifier`,
`RandomForestClassifier`, `VarianceThreshold`, `Pipeline`), pandas,
pyarrow, PyYAML; joblib para gravar os modelos (vem com o scikit-learn,
passa a ser declarado em `pyproject.toml`)

**Storage**: `models/runs/<run_id>/predictions.parquet`,
`run.meta.json` e, no braço principal, `fold_<r>_<k>.joblib`

**Testing**: pytest

**Target Platform**: Linux

**Project Type**: pacote `src/models/` com CLI `scripts/train.py`

**Performance Goals**: sem meta; 573 `firmware_id`, 30 colunas, 25 folds
por execução

**Constraints**: sem rede; determinismo em processos separados (SC-002):
`n_jobs=1` no ajuste e na predição, porque `predict_proba` soma as árvores
em threads e, com folhas impuras, a ordem da soma muda o resultado
(medido pelo analyze de 2026-09-25 no scikit-learn 1.7.2); nada ajustado
no teste do fold (SC-001)

**Scale/Scope**: 573 `firmware_id` com rótulo definido hoje (medido em
2026-09-25 sobre `dataset/labels_v2.csv`)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

|Princípio|Resultado|Evidência|
|---|---|---|
|I. Somente análise estática|Não se aplica|Só lê artefatos da `008` e `009`|
|II. Rótulo exclusivamente por CVE|Passa|O alvo é o `security_level` da `008`; o binário é função fixa dele (FR-012); `score_firmware` só é baseline de comparação (FR-010)|
|III. Sem vazamento|Violação justificada|Filtro de variância e modelo ajustados só no treino de cada fold, dentro de um `Pipeline` (FR-002 a FR-004; SC-001); folds agrupados da `009`; baseline de identidade e esquema `random` com `purpose: diagnostico` (FR-006, FR-009; SC-004). O treino no esquema `random` herda a violação da `009`: ver Complexity Tracking|
|IV. Modelos simples|Passa|Só Extra Trees (principal) e Random Forest (baseline de ML); hiperparâmetros fixos; XGBoost fora|
|V. Reprodutibilidade|Passa|Hiperparâmetros, `n_jobs=1`, peso e regras de alvo em `configs/training.yaml`; seed da repetição recebida da `009`; `run_id` determinístico e sem sobrescrita (FR-006); metadados por fold com colunas mantidas pelo filtro (registro do transformador), `firmware_id` de treino e SHA256 (FR-006, FR-007); logs de FR-013. As predições ficam em `models/runs/` por serem saída de modelo; os resultados (métricas e tabelas) vão para `reports/<timestamp>/` pela `011` (decisão do pesquisador, 2026-09-25)|
|VI. Firmware não confiável|Não se aplica|Sem leitura de firmware|
|VII. Integridade científica|Passa|Nenhum número de resultado na spec; hiperparâmetros justificados em research R1|

Re-check após Phase 1: sem mudança.

## Project Structure

### Documentation (this feature)

```text
specs/010-treino-modelos/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── cli.md
├── tasks.md
└── checklists/
    ├── requirements.md
    └── rastreabilidade.md
```

### Source Code (repository root)

```text
src/models/
├── __init__.py
├── training.py       # configuração, alvo, pipeline por fold, execução, gravação
└── baselines.py      # majoritário, identidade, score_firmware

scripts/
└── train.py          # CLI (novo; previsto no AGENTS.md)

configs/
└── training.yaml     # hiperparâmetros, class_weight, experimentos (novo)

tests/
├── test_training.py
├── test_baselines.py
└── test_train_cli.py
```

**Structure Decision**: pacote novo `src/models/` (código); os artefatos
ficam no diretório `models/` da raiz (constituição V).

### US → FR → módulo → teste → TickTick

|FR|US|Módulo (previsto)|Teste (previsto)|TickTick|
|---|---|---|---|---|
|FR-001|US1|`src/models/training.py::load_training_config`, `load_inputs` (via `load_folds` da `009`)|`tests/test_training.py` (SHA256 divergente de tabela, proveniência e folds via `009/FR-006`, configuração com override)|T09|
|FR-002|US1|`src/models/training.py::build_pipeline` (`VarianceThreshold(0.0)` + modelo)|`tests/test_training.py` (US1.2, todas as colunas constantes falha)|T09|
|FR-003|US1|`src/models/training.py::build_pipeline`, `train_run`|`tests/test_training.py` (US1.1, hiperparâmetros e seed nos metadados)|T09|
|FR-004|US2|`src/models/training.py::build_pipeline`|`tests/test_training.py` (US2.1)|T09|
|FR-005|US1|`src/models/training.py::train_run`|`tests/test_training.py` (US1.4, esquema `random`)|T09|
|FR-006|US1|`src/models/training.py::write_run`, `run_id`, `purpose_for`|`tests/test_training.py` (três colunas de probabilidade com classe ausente no treino, `purpose` por modelo e esquema, `run_id` diferente por modelo, diretório existente falha); `tests/test_train_cli.py` (US1.3, `run_id` estável, `--force`)|T09|
|FR-007|US1|`src/models/training.py::write_run`|`tests/test_training.py` (modelos só no braço principal; metadados por fold)|T09|
|FR-008|US3|`src/models/baselines.py::majority_predictions`|`tests/test_baselines.py` (US3.1, empate)|T09|
|FR-009|US3|`src/models/baselines.py::identity_features`|`tests/test_baselines.py` (US3.2, multi-hot)|T09|
|FR-010|US3|`src/models/baselines.py::score_firmware_predictions`|`tests/test_baselines.py` (US3.3, SHA256 da tabela de features divergente, mapeamento binário)|T09|
|FR-011|US4|`src/models/training.py::build_pipeline`; `configs/training.yaml`|`tests/test_training.py` (US4.1)|T05|
|FR-012|US4|`src/models/training.py::target_for_experiment`; `configs/training.yaml`|`tests/test_training.py` (US4.2)|T05|
|FR-013|US1, US2|`scripts/train.py::main`|`tests/test_train_cli.py` (`caplog`)|T09|
|FR-014 [Proposto]|—|—|— (Proposto: sem task)|T05|

### Sem verificação

Nenhum FR Planejado.

### Símbolos com requisito em outra spec

- `load_folds`: `009/FR-006`.
- `score_firmware` e sua configuração: `006-baseline-regras`.
- Conjuntos de colunas das ablations, métricas e importância: `011`.

## Complexity Tracking

|Violação|Por que permanece|Mitigação|
|---|---|---|
|Princípio III — execuções no esquema `random` treinam com modelos em treino e teste (`009/FR-007`)|Medem o efeito da identidade para a `011` (TickTick T03); decisão do pesquisador no analyze da `009`, 2026-09-25|`purpose: diagnostico` em predições e metadados de toda execução `random` (FR-006, SC-004); a `011` nunca as reporta como resultado|
