# Implementation Plan: Partição agrupada

**Branch**: `docs/escopo-restante` | **Date**: 2026-09-25 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/009-particao-agrupada/spec.md`

**Note**: spec nova, Status Misto: FR-001 a FR-008 Planejado (TickTick
T03), FR-009 e FR-010 Proposto, sem task. Nenhum código existe ainda;
módulos e testes abaixo são previstos. Estrutura decidida pelo
pesquisador em 2026-09-25 ([research.md](research.md)).

## Summary

`scripts/make_folds.py` lê a tabela de treino e a proveniência da `008`,
confere os SHA256, forma os grupos como componentes conectados do grafo
`firmware_id`–chave de modelo (fabricante e modelo sem caixa, `-`, `_` e
espaços), gera 5 folds × 5 repetições com
`StratifiedGroupKFold` (seeds 0 a 4) e, com as mesmas seeds, a divisão
diagnóstica com `StratifiedKFold`. Checa que nenhum `firmware_id` cruza
treino e teste nos dois esquemas e nenhum modelo no agrupado, grava
`folds_grouped.parquet` e `folds_random.parquet` com metadados e expõe
`load_folds`, que devolve tabela, proveniência, folds e metadados à `010`
e à `011` e recusa artefato com SHA256 diferente.

## Technical Context

**Language/Version**: Python ≥ 3.9

**Primary Dependencies**: scikit-learn (`StratifiedGroupKFold`, desde a
1.0; `pyproject.toml` exige ≥ 1.1), pandas, pyarrow, PyYAML (todos
declarados)

**Storage**: `dataset/processed/folds_grouped.parquet`,
`folds_grouped.meta.json`, `folds_random.parquet`, `folds_random.meta.json`

**Testing**: pytest

**Target Platform**: Linux

**Project Type**: módulo `src/dataset/partition.py` com CLI em `scripts/`

**Performance Goals**: sem meta; até 573 `firmware_id`

**Constraints**: sem rede; sem leitura de binário; determinístico em
processos separados (SC-002); `shuffle=True` com `random_state` fixo

**Scale/Scope**: medido em 2026-09-25 (`features_v2.parquet`,
`dataset/labels_v2.csv`): até 573 `firmware_id` (com rótulo definido; as
exclusões por terceiros e falha de extração da `008` ainda não são
mensuráveis), 226 grupos pela regra de FR-002, maior grupo com 21

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

|Princípio|Resultado|Evidência|
|---|---|---|
|I. Somente análise estática|Não se aplica|Só lê artefatos da `008`|
|II. Rótulo exclusivamente por CVE|Passa|Estratifica pelo `security_level` da `008`, sem recalcular|
|III. Sem vazamento|Violação justificada|Na divisão principal, o grupo por componente conectado com chave canônica de modelo garante que nenhum `firmware_id` nem modelo cruza treino e teste (FR-002, FR-003), com teste de guarda (SC-001); simulação com seeds 0 a 4: 0 modelos cruzando. Nenhum transformador é ajustado aqui. A divisão aleatória (FR-007) põe modelos em treino e teste: ver Complexity Tracking|
|IV. Modelos simples|Não se aplica|Sem modelo|
|V. Reprodutibilidade|Passa|Seeds e folds em `configs/dataset.yaml` (FR-004); folds gravados com configuração efetiva, SHA256 das entradas e do próprio arquivo, commit e contagens (FR-005); `load_folds` confere SHA256 e entrega seeds ao consumidor (FR-006); logs de FR-008|
|VI. Firmware não confiável|Não se aplica|Sem leitura de firmware|
|VII. Integridade científica|Passa|Números da spec citam data e artefato; a simulação de folds sem classe está registrada com parâmetros (research R3)|

Re-check após Phase 1: sem mudança.

## Project Structure

### Documentation (this feature)

```text
specs/009-particao-agrupada/
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
src/dataset/
└── partition.py            # grupos, folds, checagem, gravação, load_folds

scripts/
└── make_folds.py           # CLI (novo)

configs/
└── dataset.yaml            # seção partition: n_splits, n_repeats, seeds

tests/
├── test_partition.py       # grupos, guarda, estratificação, load_folds
└── test_make_folds_cli.py  # reprodutibilidade em dois processos, log
```

**Structure Decision**: módulo no pacote `src/dataset/` da `008`;
configuração na mesma `configs/dataset.yaml`, seção `partition`.

### US → FR → módulo → teste → TickTick

|FR|US|Módulo (previsto)|Teste (previsto)|TickTick|
|---|---|---|---|---|
|FR-001|US2|`src/dataset/partition.py::load_training_inputs`|`tests/test_partition.py` (SHA256 divergente da tabela e da proveniência)|T03|
|FR-002|US1|`src/dataset/partition.py::model_key`, `build_groups`|`tests/test_partition.py` (US1.1, US1.3, US1.4, `in_table=false` ignorado)|T03|
|FR-003|US1|`src/dataset/partition.py::check_no_crossing`|`tests/test_partition.py` (US1.2, guarda sobre folds forjados com cruzamento; modelo só no esquema `grouped`)|T03|
|FR-004|US2|`src/dataset/partition.py::grouped_folds`; `configs/dataset.yaml`|`tests/test_partition.py` (5×5, estratificação, cada `firmware_id` em um teste por repetição)|T03|
|FR-005|US2|`src/dataset/partition.py::write_folds`|`tests/test_make_folds_cli.py` (US2.1, US2.2, fold sem classe registrado)|T03|
|FR-006|US2|`src/dataset/partition.py::load_folds` (devolve `FoldSet`: tabela, proveniência, folds, metadados)|`tests/test_partition.py` (US2.3, proveniência alterada)|T03|
|FR-007|US3|`src/dataset/partition.py::random_folds`|`tests/test_partition.py` (US3.1, mesmas seeds)|T03|
|FR-008|US2|`scripts/make_folds.py::main`|`tests/test_make_folds_cli.py` (`caplog`)|T03|
|FR-009 [Proposto]|—|—|— (Proposto: sem task)|T03|
|FR-010 [Proposto]|US4|—|— (Proposto: sem task)|T03|

### Sem verificação

Nenhum FR Planejado.

### Símbolos com requisito em outra spec

- Tabela de treino e proveniência: `008/FR-013`, `008/FR-014`.
- Treino por fold e ajuste de transformadores no treino: `010`.
- Agregação das métricas e comparação entre divisões: `011`.

## Complexity Tracking

|Violação|Por que permanece|Mitigação|
|---|---|---|
|Princípio III — a divisão aleatória de diagnóstico (FR-007) põe o mesmo modelo em treino e teste (25 de 25 folds na simulação de 2026-09-25)|Mede quanto a divisão não agrupada infla as métricas (TickTick T03, "Comparar divisão aleatória com divisões agrupadas"); sem ela, o efeito da identidade não é quantificado. Decisão do pesquisador no analyze de 2026-09-25|Arquivo separado `folds_random.*` com `purpose: diagnostico` (SC-004); nenhum `firmware_id` cruza; a `010` e a `011` marcam as execuções e tabelas como diagnóstico e nunca as reportam como resultado|
