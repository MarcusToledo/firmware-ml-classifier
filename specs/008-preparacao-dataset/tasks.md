# Tasks: Preparação do dataset de treino

**Input**: `specs/008-preparacao-dataset/` (spec.md, plan.md, research.md,
data-model.md, contracts/cli.md)

**Nota**: spec Planejado (TickTick T08 e T07). Toda task cita o FR que
implementa e o caminho. Testes vêm antes da implementação em cada fase.

## Format: `[ID] [P?] [Story] Descrição`

## Phase 1: Setup

- [ ] T001 FR-001, FR-010 — Criar `configs/dataset.yaml` com os caminhos de entrada (`dataset/processed/features_v2.parquet`, `dataset/processed/labels_v2.csv`), `output_dir: dataset/processed` e a lista fixa do one-hot de `fs_type` e `compression_type`, com comentário da justificativa de domínio
- [ ] T002 FR-001 — Criar o pacote `src/dataset/__init__.py` e o carregamento da configuração com `--config` e `--override` em `src/dataset/training_table.py::load_dataset_config`, reaproveitando `src/cli_utils.py`

## Phase 2: Foundational

- [ ] T003 [US1] FR-001 — Testes de entrada ausente, de coluna exigida ausente, de tabela sem `meta_binwalk_status`, `meta_unpack_status`, `meta_third_party` ou `meta_fs_status` (erro com instrução de extrair de novo) e cenário US1.6 (SHA256 de `--features` em `labels_v2.meta.json` diferente) em `tests/test_training_table.py`
- [ ] T004 [US1] FR-001 — Ler e conferir as duas tabelas e o SHA256 registrado em `labels_v2.meta.json` em `src/dataset/training_table.py::load_inputs`

## Phase 3: User Story 1 - Tabela de treino sem vazamento (Priority: P1)

**Goal**: uma linha por `firmware_id`, só colunas de feature e o alvo.

- [ ] T005 [US1] FR-002 — Cenários US1.1, US1.3, US1.4 e US1.5: testes de aliases colapsados, de `firmware_id` sem par nos dois sentidos, de `firmware_id` nulo e de alias divergente em feature e em `security_level`, sem gravar nada, em `tests/test_training_table.py`
- [ ] T006 [US1] FR-002 — Recusar `firmware_id` nulo, juntar os rótulos por `firmware_id` e colapsar aliases dos `firmware_id` que sobram das exclusões, falhando com a lista de `firmware_id` e colunas, em `src/dataset/training_table.py::collapse_aliases` e `join_labels`
- [ ] T007 [US1] FR-003, FR-004 — Cenário US1.2: teste de guarda de vazamento sobre a tabela de treino (sem `meta_*`, identidade, campos de CVE, `label_strategy`, `alias_count`, `doc2vec_*`) em `tests/test_training_table.py`
- [ ] T008 [US1] FR-003, FR-004 — Selecionar as colunas do vetor e registrar o motivo de cada remoção em `src/dataset/training_table.py::select_feature_columns`

## Phase 4: User Story 2 - Exclusões auditáveis (Priority: P1)

**Goal**: exclusões com todos os motivos e contagens por motivo e fabricante.

- [ ] T009 [US2] FR-005, FR-006, FR-007 — Cenários US2.1, US2.2, US2.4 e US2.5: testes de exclusão por `indeterminado`, `terceiros` e `falha_extracao` (`meta_binwalk_status=erro`, `meta_unpack_status=falha`, `meta_fs_status=erro`), de interrupção por `timeout`, `limite_tempo` e `nao_executado`, de manutenção de `sem_filesystem`, `limite_tamanho` e `limite_arquivos`, e de alias com Binwalk em erro excluído sem falha por divergência em `tests/test_training_table.py`
- [ ] T010 [US2] FR-005, FR-006, FR-007 — Aplicar as exclusões por alias, antes do colapso, e a checagem de falha transitória em `src/dataset/training_table.py::apply_exclusions` e `check_transient_failures`
- [ ] T011 [US2] FR-008 — Cenário US2.3: testes de vários motivos, de `firmware_id` com aliases de dois fabricantes, da invariante de cobertura e de falha com tabela vazia ou classe sem exemplo em `tests/test_training_table.py`
- [ ] T012 [US2] FR-005, FR-008 — Montar o registro de exclusões, as contagens por motivo e fabricante, a proporção de `indeterminado` por fabricante e a falha por tabela vazia ou classe sem exemplo em `src/dataset/training_table.py::build_exclusions`

## Phase 5: User Story 3 - Vetor só com colunas úteis ao modelo (Priority: P2)

**Goal**: sem coluna de texto, constantes registradas, sem escala.

- [ ] T013 [US3] FR-010 — Cenários US3.1 e US3.3: testes de one-hot com valor da lista, nulo (`ausente`) e valor fora da lista (`outro`), com exatamente um 1 por coluna de origem, em `tests/test_training_table.py`
- [ ] T014 [US3] FR-010 — One-hot de lista fixa lida de `configs/dataset.yaml` em `src/dataset/training_table.py::one_hot_fixed`
- [ ] T015 [US3] FR-009, FR-011, FR-012 — Cenário US3.2: testes de constantes (nas linhas da tabela gravada) mantidas e registradas, de motivo por coluna removida ou transformada e de valores numéricos iguais aos da entrada em `tests/test_training_table.py`
- [ ] T016 [US3] FR-009, FR-011 — Registrar as colunas constantes e o relatório de colunas em `src/dataset/training_table.py::constant_columns` e `column_report`

## Phase 6: User Story 4 - Artefato reprodutível e validado (Priority: P2)

**Goal**: artefatos em `dataset/processed/` com metadados e validação.

- [ ] T017 [US4] FR-014 — Teste da proveniência (tabela e exclusões, ordenada por `firmware_id`, aliases por `meta_path`) em `tests/test_training_table.py`
- [ ] T018 [US4] FR-014 — Montar a proveniência em `src/dataset/training_table.py::build_provenance`
- [ ] T019 [US4] FR-013, FR-017 — Cenário US4.1: teste de duas execuções em processos separados com tabela e exclusões idênticas byte a byte e metadados (inclusive SHA256 da tabela) diferentes só em `created_at`, e teste do log (tamanhos, features, classes, exclusões) em `tests/test_build_dataset_cli.py`
- [ ] T020 [US4] FR-013 — Gravar os quatro artefatos e os metadados (SHA256, commit, configuração, colunas, contagens) em `src/dataset/training_table.py::write_artifacts`
- [ ] T021 [US4] FR-001, FR-013, FR-017 — CLI `scripts/build_dataset.py::main` conforme `contracts/cli.md`, com logs de FR-017
- [ ] T022 [P] [US4] FR-015 — Cenários US4.2 e US4.3: testes de artefato íntegro, `firmware_id` duplicado, coluna proibida, coluna de texto, alvo inválido, SHA256 divergente, colunas diferentes dos metadados, órfão, arquivo ignorado pela seleção de `001/FR-001` que não é órfão e `meta_path` absoluto que falha em `tests/test_validate_dataset.py`
- [ ] T023 [US4] FR-015 — Validação em `src/dataset/validation.py` (órfãos pelo caminho relativo à raiz, com a mesma seleção de `scripts/extract_features.py::gather_paths` e `EXCLUDED_EXTENSIONS`, movida para módulo importável pelos dois) e reescrita de `scripts/validate_dataset.py::main` (remover as checagens de layout, ASUS e conteúdo repetido)

## Phase 7: User Story 5 - TP-Link com um só nome de fabricante (Priority: P3)

**Goal**: `tplink` movido para `tp_link` com mapa versionado.

- [ ] T024 [P] [US5] FR-016 — Cenários US5.1 e US5.2: testes de movimentação com `_`→`-` no modelo e SHA256 igual, de mapa gravado, de dry-run sem mudança, de diretório vazio removido e de modelo de destino com arquivo que falha sem mover nada em `tests/test_reorganize_dataset.py`
- [ ] T025 [US5] FR-016 — Modo `--merge-vendor tplink:tp_link` em `scripts/reorganize_dataset.py`, gravando `configs/tplink_merge_map.csv`
- [ ] T026 [US5] FR-016 — Resolver à mão com o pesquisador o modelo `tl_er604w`↔`tl-er604w`, executar a movimentação em `dataset/raw/`, refazer a busca completa na NVD com `scripts/fetch_cves.py` (`003/FR-014`, 003/T050), extrair as features e gerar os rótulos de novo; conferir SC-006

## Phase 8: Polish

- [ ] T027 FR-011 — Registrar no `TODO.md` a lista de colunas do vetor antes e depois, com o motivo de cada remoção (aceite da TickTick T07)
- [ ] T028 FR-013, FR-015 — Gerar o artefato real, rodar `scripts/validate_dataset.py` e registrar no `TODO.md` as contagens por classe, motivo e fabricante (SC-002, SC-004)
- [ ] T029 FR-015, FR-016 — Atualizar `specs/001-extracao-features/plan.md` ("Símbolos com requisito em outra spec": `scripts/validate_dataset.py` e `scripts/reorganize_dataset.py` passam a ter requisito na 008) e o Edge Case de `specs/003-busca-cve/spec.md` sobre `tplink`/`tp_link` separados (consolidados pela 008/FR-016)

## Dependencies & Execution Order

- T001 → T002 → T003 → T004 → fases 3 a 6.
- T005–T006 dependem de T009–T010: as exclusões são avaliadas por alias,
  antes do colapso e da checagem de divergência. T007–T008 dependem de
  T006.
- T013–T016 dependem de T008.
- T017–T021 dependem das fases 3 a 5; T022–T023 dependem de T020.
- Phase 7 é independente das fases 3 a 6 (outro script), mas T026 exige
  `001/FR-014`, `001/FR-016`, `003/FR-014`, `004/FR-016`, `004/FR-017`,
  `005/FR-018` e `005/FR-026` implementados.
- T027–T028 dependem de T026; T029 é independente.
- `[P]`: T022 e T024 mexem em arquivos que nenhuma task em andamento toca.
