# Implementation Plan: Preparação do dataset de treino

**Branch**: `docs/escopo-restante` | **Date**: 2026-09-25 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/008-preparacao-dataset/spec.md`

**Note**: spec nova, Status Planejado (TickTick T08 e T07). Nenhum código
existe ainda; módulos e testes abaixo são previstos. Decisões de estrutura
(pacote, comandos, configuração, movimentação TP-Link) foram tomadas pelo
pesquisador em 2026-09-25 e estão em [research.md](research.md).

## Summary

Um comando novo, `scripts/build_dataset.py`, junta por `firmware_id` a
tabela de features (`001-extracao-features`, com as colunas de `012`
quando implementada) e só o `security_level` da tabela de rótulos
(`005/FR-018`), conferindo que os rótulos vieram dessa mesma tabela
(SHA256). Falha em `firmware_id` nulo, par ausente, coluna de extração
ausente e falha transitória; exclui `indeterminado`, imagens de terceiros
e falhas de extração com todos os motivos e só depois checa aliases
divergentes; troca `fs_type` e
`compression_type` por one-hot de lista fixa; tira `doc2vec_*`, `meta_*`,
identidade e campos de CVE do vetor. Grava em `dataset/processed/` a
tabela, as exclusões, a proveniência e os metadados. O
`scripts/validate_dataset.py` é reescrito para validar esse artefato e os
órfãos de `dataset/raw/`, e o `scripts/reorganize_dataset.py` ganha o modo
que move `tplink` para `tp_link`, trocando `_` por `-` no modelo, com mapa
versionado.

## Technical Context

**Language/Version**: Python ≥ 3.9

**Primary Dependencies**: pandas e pyarrow (já declarados em
`pyproject.toml`, usados pela extração); PyYAML para a configuração;
`hashlib` e `subprocess` (commit via `git rev-parse`) da biblioteca padrão

**Storage**: arquivos em `dataset/processed/`: `training_table.parquet`,
`training_table_exclusions.csv`, `training_table_provenance.jsonl`,
`training_table.meta.json`; mapa TP-Link em `configs/tplink_merge_map.csv`

**Testing**: pytest

**Target Platform**: Linux

**Project Type**: biblioteca `src/dataset/` com dois CLIs em `scripts/`

**Performance Goals**: sem meta; 840 linhas e ~130 colunas cabem em
memória

**Constraints**: sem rede (constituição, Restrições Técnicas); nenhum
critério calculado sobre os dados remove ou codifica coluna (FR-009,
FR-010); saída ordenada por `firmware_id` e determinística (FR-013,
SC-003); falha sem gravar nada nos casos de FR-001, FR-002 e FR-007

**Scale/Scope**: medido em 2026-09-25 sobre `features_v2.parquet` e
`dataset/labels_v2.csv`: 840 linhas, 699 `firmware_id`, 20 colunas de
feature fora `doc2vec_*` (5 constantes), 126 `firmware_id`
`indeterminado`

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

|Princípio|Resultado|Evidência|
|---|---|---|
|I. Somente análise estática|Passa|Lê só as tabelas de features e rótulos; nenhum binário é lido, exceto o SHA256 dos arquivos movidos (FR-016) e a listagem de `dataset/raw/` na validação de órfãos (FR-015)|
|II. Rótulo exclusivamente por CVE|Passa|O alvo é o `security_level` da `005`, sem recálculo; `indeterminado` sai do treino (FR-005) e não vira negativo|
|III. Sem vazamento|Passa|FR-003 e FR-004 tiram identidade, `meta_*`, campos de CVE, colunas da rotulagem e `doc2vec_*` do vetor, com teste de guarda sobre a tabela (SC-001). Nenhum transformador é ajustado a dados na 008: one-hot de lista fixa definida pelo domínio (tipos que o Binwalk reconhece em firmware embarcado), não pela contagem no dataset (FR-010); filtro de variância adiado para a `010` (FR-009). A proveniência fica fora do vetor, para a partição agrupada (FR-014)|
|IV. Modelos simples|Passa|Sem scaler (FR-012); sem modelo nesta etapa|
|V. Reprodutibilidade|Passa|Configuração versionada `configs/dataset.yaml` com `--override` registrado; metadados com SHA256 das entradas, commit, parâmetros e colunas (FR-013); saída ordenada; logs de tamanho, features e classes (FR-017). Sem etapa aleatória|
|VI. Firmware não confiável|Passa|Falhas de extração ficam no registro de exclusões com motivo (FR-007, FR-008); `firmware_id` nulo, falha transitória, alias divergente, coluna ausente e rótulos de outra tabela de features interrompem com a lista de arquivos (FR-001, FR-002, FR-007)|
|VII. Integridade científica|Passa|Todos os FRs são Planejado com TickTick; números da spec citam data e artefato|

Re-check após Phase 1: sem mudança; `data-model.md` não cria coluna de
vetor derivada de dado de treino.

## Project Structure

### Documentation (this feature)

```text
specs/008-preparacao-dataset/
├── spec.md                  # /speckit.specify + /speckit.clarify
├── plan.md                  # este arquivo
├── research.md              # decisões do clarify e do plano
├── data-model.md            # artefatos e colunas
├── quickstart.md            # como rodar e conferir
├── contracts/
│   └── cli.md               # build_dataset, validate_dataset, reorganize_dataset
├── tasks.md                 # /speckit.tasks
└── checklists/
    ├── requirements.md
    └── rastreabilidade.md
```

### Source Code (repository root)

```text
src/dataset/
├── __init__.py
├── training_table.py        # leitura, junção, exclusões, one-hot, vetor, metadados
└── validation.py            # validação do artefato e órfãos

scripts/
├── build_dataset.py         # CLI da preparação (novo)
├── validate_dataset.py      # reescrito: artefato + órfãos
└── reorganize_dataset.py    # novo modo --merge-vendor tplink:tp_link

configs/
├── dataset.yaml             # caminhos e lista fixa do one-hot (novo)
└── tplink_merge_map.csv     # mapa versionado da movimentação (novo)

tests/
├── test_training_table.py   # junção, exclusões, one-hot, guarda de vazamento
├── test_build_dataset_cli.py
├── test_validate_dataset.py
└── test_reorganize_dataset.py
```

**Structure Decision**: pacote novo `src/dataset/`, paralelo a
`src/labeling/`; os scripts só fazem parse de argumentos e chamam o
pacote. `scripts/validate_dataset.py` e `scripts/reorganize_dataset.py`
passam a ter requisito nesta spec (hoje listados em
`001-extracao-features`, "Símbolos com requisito em outra spec", como
curadoria fora do pipeline).

### US → FR → módulo → teste → TickTick

|FR|US|Módulo (previsto)|Teste (previsto)|TickTick|
|---|---|---|---|---|
|FR-001|US1|`src/dataset/training_table.py::load_inputs`; `scripts/build_dataset.py::main`; `configs/dataset.yaml`|`tests/test_training_table.py` (arquivo ausente, coluna de extração ausente, US1.6); `tests/test_build_dataset_cli.py` (override de caminho)|T08|
|FR-002|US1, US2|`src/dataset/training_table.py::collapse_aliases`, `join_labels`|`tests/test_training_table.py` (US1.1, US1.3, US1.4, US1.5, US2.5)|T08|
|FR-003|US1|`src/dataset/training_table.py::select_feature_columns`|`tests/test_training_table.py` (guarda de vazamento, US1.2)|T08|
|FR-004|US1|`src/dataset/training_table.py::select_feature_columns`|`tests/test_training_table.py` (`doc2vec_*` na entrada, fora do vetor)|T08|
|FR-005|US2|`src/dataset/training_table.py::apply_exclusions`|`tests/test_training_table.py` (US2.1, proporção por fabricante)|T08|
|FR-006|US2|`src/dataset/training_table.py::apply_exclusions`|`tests/test_training_table.py` (US2.2)|T08|
|FR-007|US2|`src/dataset/training_table.py::apply_exclusions`, `check_transient_failures`|`tests/test_training_table.py` (exclusão por erro; US2.4, `nao_executado`, US2.5)|T08|
|FR-008|US2|`src/dataset/training_table.py::build_exclusions`|`tests/test_training_table.py` (vários motivos, multi-fabricante, US2.3)|T08|
|FR-009|US3|`src/dataset/training_table.py::constant_columns`|`tests/test_training_table.py` (US3.2)|T07|
|FR-010|US3|`src/dataset/training_table.py::one_hot_fixed`; `configs/dataset.yaml`|`tests/test_training_table.py` (US3.1, US3.3)|T07|
|FR-011|US3|`src/dataset/training_table.py::column_report`|`tests/test_training_table.py` (motivo por coluna)|T07|
|FR-012|US3|`src/dataset/training_table.py` (sem etapa de escala)|`tests/test_training_table.py` (valores numéricos iguais aos da entrada)|T08|
|FR-013|US4|`src/dataset/training_table.py::write_artifacts`|`tests/test_build_dataset_cli.py` (US4.1, dois processos)|T08|
|FR-014|US4|`src/dataset/training_table.py::build_provenance`|`tests/test_training_table.py` (tabela + exclusões, ordem)|T08|
|FR-015|US4|`src/dataset/validation.py` (órfãos com a seleção de `scripts/extract_features.py::gather_paths`/`EXCLUDED_EXTENSIONS`, que a extração usa, movida para módulo compartilhado); `scripts/validate_dataset.py::main`|`tests/test_validate_dataset.py` (US4.2, US4.3, artefato íntegro, arquivo ignorado pela seleção não é órfão, `meta_path` absoluto falha)|T08|
|FR-016|US5|`scripts/reorganize_dataset.py` (modo `--merge-vendor`, `_`→`-` no modelo, remoção de diretórios vazios); `configs/tplink_merge_map.csv`|`tests/test_reorganize_dataset.py` (US5.1, US5.2)|T08|
|FR-017|US1, US2|`src/dataset/training_table.py`; `scripts/build_dataset.py::main`|`tests/test_build_dataset_cli.py` (`caplog`)|T08|

### Sem verificação

- FR-016, passo seguinte à movimentação: busca completa na NVD
  (`003-busca-cve` com `003/FR-014`, usa rede) e regeração de features e
  rótulos. É
  execução do pipeline, conferida pela validação (FR-015) sobre o
  artefato regerado, não por teste.

### Símbolos com requisito em outra spec

- Filtro de variância ajustado só na partição de treino (FR-009): FR da
  `010-treino-modelos`.
- Leitura da proveniência para agrupar: `009-particao-agrupada`.

## Complexity Tracking

Sem violação.
