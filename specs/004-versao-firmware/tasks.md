# Tasks: Versão do firmware a partir do path

**Input**: `specs/004-versao-firmware/` (spec.md, plan.md)

**Nota**: tasks retroativas. O código já existe em `master`; cada task
`[x]` registra uma verificação feita em 2026-09-24 (FR → módulo → teste ou
cenário conferido). Tasks `[ ]` das fases 2 a 6 são lacunas de teste ainda
abertas, espelhadas no `TODO.md`. A Phase 7 decompõe os FRs Planejado
(TickTick T11); FR-018 é Proposto e não tem task.

## Format: `[ID] [P?] [Story] Descrição`

## Phase 2: User Story 1 - Fabricante e modelo pelo diretório (Priority: P1)

**Goal**: Inferir fabricante, modelo e identificador a partir do layout do dataset.

- [x] T001 [US1] FR-001 — `pipeline/feature_extraction.py::infer_brand_model_label_from_path` → `tests/test_feature_extraction.py::test_infer_path_strips_version_suffix`
- [x] T002 [US1] FR-002 — `pipeline/feature_extraction.py::infer_brand_model_label_from_path` → `tests/test_feature_extraction.py::test_infer_path_no_raw_segment_returns_all_none` (parcial)
- [x] T003 [US1] FR-003 — `pipeline/feature_extraction.py::infer_brand_model_label_from_path` → `tests/test_feature_extraction.py::test_infer_path_preserves_normal_model`
- [x] T004 [US1] FR-004 — `pipeline/feature_extraction.py::_split_model_version` → `tests/test_feature_extraction.py::test_infer_path_hardware_revision_suffix_is_part_of_model`
- [x] T005 [US1] Cenário US1.1 — confirmado (teste `tests/test_feature_extraction.py::test_infer_path_strips_version_suffix`)
- [x] T006 [US1] Cenário US1.2 — confirmado (teste `tests/test_feature_extraction.py::test_infer_path_preserves_normal_model`)
- [x] T007 [US1] Cenário US1.3 — confirmado (teste `tests/test_feature_extraction.py::test_infer_path_hardware_revision_suffix_is_part_of_model`)
- [x] T008 [US1] Cenário US1.4 — confirmado (teste `tests/test_feature_extraction.py::test_infer_path_no_raw_segment_returns_all_none`)

## Phase 3: User Story 2 - Versão com origem registrada (Priority: P1)

**Goal**: Inferir a versão e registrar se ela veio do diretório ou do nome do arquivo.

- [x] T009 [US2] FR-005 — `pipeline/feature_extraction.py::infer_brand_model_label_from_path` → `tests/test_feature_extraction.py::test_infer_path_directory_version_wins_over_filename`
- [x] T010 [US2] FR-006 — `pipeline/firmware_version.py::infer_version_from_filename` → `tests/test_firmware_version.py::test_belkin`, `tests/test_firmware_version.py::test_extension_is_case_insensitive` (parcial)
- [x] T011 [US2] FR-007 — `pipeline/firmware_version.py::_netgear` → `tests/test_firmware_version.py::test_netgear`
- [x] T012 [US2] FR-008 — `pipeline/firmware_version.py::_asus` → `tests/test_firmware_version.py::test_asus`
- [x] T013 [US2] FR-009 — `pipeline/firmware_version.py::_belkin` → `tests/test_firmware_version.py::test_belkin`
- [x] T014 [US2] FR-011 — `pipeline/firmware_version.py::_tplink` → `tests/test_firmware_version.py::test_tplink`
- [x] T015 [US2] Cenário US2.1 — confirmado (teste `tests/test_feature_extraction.py::test_infer_path_version_suffix_with_simple_digits`)
- [x] T016 [US2] Cenário US2.2 — confirmado (teste `tests/test_feature_extraction.py::test_infer_path_falls_back_to_version_in_filename`)
- [x] T017 [US2] Cenário US2.3 — confirmado (teste `tests/test_feature_extraction.py::test_infer_path_directory_version_wins_over_filename`)
- [x] T018 [US2] Cenário US2.4 — confirmado (teste `tests/test_firmware_version.py::test_netgear`)

## Phase 4: User Story 3 - Sem chute quando não há versão inequívoca (Priority: P1)

**Goal**: Manter versão e origem nulas quando a inferência não é inequívoca.

- [x] T019 [US3] FR-010 — `pipeline/firmware_version.py::_dlink` → `tests/test_firmware_version.py::test_dlink`
- [x] T020 [US3] FR-012 — `pipeline/firmware_version.py::infer_version_from_filename` → `tests/test_feature_extraction.py::test_infer_path_ambiguous_filename_has_no_version`
- [x] T021 [US3] FR-013 — `pipeline/feature_extraction.py::extract_features_from_path` → `tests/test_pipeline_extraction.py::test_extract_features_rejects_inconsistent_version_metadata`
- [x] T022 [US3] Cenário US3.1 — confirmado (teste `tests/test_firmware_version.py::test_dlink`)
- [x] T023 [US3] Cenário US3.2 — confirmado (teste `tests/test_firmware_version.py::test_dlink`)
- [x] T024 [US3] Cenário US3.3 — confirmado (teste `tests/test_firmware_version.py::test_unknown_brand_returns_none`)
- [x] T025 [US3] Cenário US3.4 — confirmado (teste `tests/test_pipeline_extraction.py::test_extract_features_rejects_inconsistent_version_metadata`)

## Phase 5: User Story 4 - Identidade no artefato só quando pedida (Priority: P2)

**Goal**: Gravar identidade e versão apenas com `--label-from-path` e preservá-las em falhas de leitura.

- [x] T026 [US4] FR-014 — `pipeline/feature_extraction.py::_process_path`, `scripts/extract_features.py::main` → `tests/test_pipeline_extraction.py::test_error_result_preserves_version_from_path`, `tests/test_pipeline_cli.py::test_cli_label_from_path_extracts_version`, `tests/test_pipeline_cli.py::test_cli_without_label_from_path_zeroes_version` (parcial)
- [x] T027 [US4] Cenário US4.1 — confirmado (teste `tests/test_pipeline_cli.py::test_cli_label_from_path_extracts_version`)
- [x] T028 [US4] Cenário US4.2 — confirmado (teste `tests/test_pipeline_cli.py::test_cli_without_label_from_path_zeroes_version`)
- [x] T029 [US4] Cenário US4.3 — confirmado (teste `tests/test_pipeline_extraction.py::test_error_result_preserves_version_from_path`)

## Phase 6: Lacunas de teste

- [ ] T030 [US1] FR-002 — paths com menos de dois segmentos depois de `raw` e segmentos de fabricante ou modelo vazios; teste sugerido em `tests/test_feature_extraction.py`
- [ ] T031 [US2] FR-006 — fabricante com maiúsculas ou espaços antes da seleção da regra; teste sugerido em `tests/test_firmware_version.py`
- [ ] T032 [US4] FR-014 — exceção levantada durante a extração e preservação da identidade por `_build_error_result`; teste sugerido em `tests/test_pipeline_extraction.py`

## Phase 7: Implementação planejada (TickTick T11)

**Goal**: Identidade só de paths no layout, relativa à raiz do dataset, e
imagens de terceiros marcadas sem versão do fabricante.

- [ ] T033 [US5] FR-016 — Inferir a identidade relativa à raiz (`--dataset-root` com precedência, senão o diretório de entrada; path fora da raiz com `--label-from-path` é erro) em `pipeline/feature_extraction.py::infer_brand_model_label_from_path`, gravar `meta_path` relativo em `extract_features_from_path` e aceitar `--dataset-root` em `scripts/extract_features.py::main`
- [ ] T034 [US5] FR-016 — Reinferir sobre o `meta_path` relativo e recusar `meta_path` absoluto com instrução de reextrair, em `scripts/generate_labels.py::_label_rows` (`005-rotulagem-cve`, FR-004)
- [ ] T035 [US5] FR-016 — Cenários US5.2 e US5.3: testes de raiz com `raw` acima, de precedência de `--dataset-root`, de arquivo único sem `--dataset-root` e de reinferência com path relativo em `tests/test_feature_extraction.py`, `tests/test_pipeline_cli.py` e `tests/test_generate_labels.py`
- [ ] T036 [US5] FR-015 — Com `--label-from-path`, listar os paths fora do layout e falhar antes do lote em `pipeline/feature_extraction.py::extract_features_batch` e `scripts/extract_features.py::main`
- [ ] T037 [US5] FR-015 — Cenário US5.1: teste de arquivo direto em `<raiz>/<fabricante>/` em `tests/test_pipeline_cli.py`
- [ ] T038 [US5] FR-017 — Gravar `meta_third_party=dd-wrt` pelo nome `webflash` ou pelo banner `DD-WRT` (caixa exata) nas strings varridas pelos detectores, também sem `--label-from-path`, e não atribuir versão só à imagem marcada pelo nome, em `pipeline/feature_extraction.py::extract_features_from_path` e `infer_brand_model_label_from_path`
- [ ] T039 [US5] FR-017 — Cenário US5.4: testes de `*webflash*`, de banner `DD-WRT` com versão mantida e de firmware oficial com `OpenWrt` sem marca em `tests/test_pipeline_extraction.py`
- [ ] T040 [US5] FR-015, FR-016, FR-017 — Na reextração (`001-extracao-features`, T050), conferir que a identidade dos 840 arquivos não mudou (SC-004) e registrar no `TODO.md` a lista de arquivos com `meta_third_party`, com zero firmwares oficiais com versão marcados (SC-005)
- [ ] T041 [US5] FR-016 — Migrar os testes e as verificações que dependem do segmento `raw` (FR-001, FR-002; `test_infer_path_no_raw_segment_returns_all_none` e os cenários US1 e US4 com `raw/...`) para o path relativo à raiz, em `tests/test_feature_extraction.py` e `tests/test_pipeline_cli.py`

## Dependencies & Execution Order

- Lacunas são independentes entre si; cada uma só depende do módulo citado.
- Phase 7: T033 → T036 (a checagem de layout usa a raiz) → T037; T033 →
  T034 → T035 → T041; T038 → T039. T033, T036 e T038 editam
  `pipeline/feature_extraction.py` e rodam em série. T038 usa as strings
  varridas pelos detectores só depois de `001/T045`. T040 depende de todas
  e de `001/T050`.
