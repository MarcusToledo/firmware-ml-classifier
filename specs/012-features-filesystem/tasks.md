# Tasks: Features do filesystem desempacotado

**Input**: `specs/012-features-filesystem/` (spec.md, plan.md,
research.md, data-model.md)

**Nota**: todos os FRs são Planejado (TickTick T12). Testes antes da
implementação em cada fase.

## Format: `[ID] [P?] [Story] Descrição`

## Phase 1: Setup

- [ ] T001 FR-003, FR-008 — Declarar `pyelftools<0.33` (compatível com Python 3.9) e subir `scikit-learn` para `>=1.6` em `pyproject.toml`
- [ ] T002 FR-005 — Acrescentar `filesystem.dangerous_functions` a `configs/feature_extraction.yaml`
- [ ] T003 FR-002, FR-004, FR-005 — Gerar e versionar ELF de teste pequenos em `tests/fixtures/elf/` (executável com e sem PIE, NX, RELRO completo e parcial, canary, FORTIFY; biblioteca; relocável; estático; MIPS big-endian 32 bits; importações de `strcpy` e `system`; função definida sem importar; ELF truncado), com o script, o comando e as flags de compilação de cada um, conferidas com o checksec 2.7.1 (oráculo do SC-001)

## Phase 2: User Story 1 - Inventário do filesystem (Priority: P1)

- [ ] T004 [US1] FR-002, FR-011 — Cenários US1.1 e US1.2: testes de contagem de arquivos, ELF, executáveis, bibliotecas e estáticos, ELF sem extensão, symlink não seguido, carvados fora da raiz ignorados, ELF repetido contado uma vez e `meta_fs_arch` (moda, empate alfabético, nulo sem ELF, fora do vetor) em `tests/test_filesystem_features.py`
- [ ] T005 [US1] FR-002, FR-011 — `src/features/filesystem.py::find_roots` (raízes de filesystem na saída do extrator), `walk_files` (ordem lexicográfica, sem seguir symlinks, dedupe por SHA256) e `classify_elf`; `meta_fs_arch`

## Phase 3: User Story 2 - Postura de hardening dos binários (Priority: P1)

- [ ] T006 [US2] FR-003, FR-004 — Cenários US2.1 e US2.2: testes de cada proteção nas fixtures pelos critérios do checksec 2.7.1 (inclusive as três tags de `BIND_NOW`), PIE só entre executáveis, estático fora de canary e FORTIFY, relocável fora das proporções e ELF maior que `max_bytes` como malformado sem carregar o arquivo inteiro em `tests/test_filesystem_features.py`
- [ ] T007 [US2] FR-003, FR-004 — `src/features/filesystem.py::read_elf` (pyelftools sobre stream com teto de offset em `max_bytes`) e `hardening`

## Phase 4: User Story 3 - Funções perigosas importadas (Priority: P1)

- [ ] T008 [US3] FR-005 — Cenários US3.1 e US3.2: testes de proporção por função, de função definida que não conta e de ELF estático fora do denominador em `tests/test_filesystem_features.py`
- [ ] T009 [US3] FR-005 — `src/features/filesystem.py::dangerous_imports`

## Phase 5: User Story 4 - Falha visível e sem vazamento (Priority: P2)

- [ ] T010 [US4] FR-006, FR-009, FR-012 — Cenários US4.2, US4.4 e US4.5: testes de ELF truncado contado em `meta_fs_elf_malformed` e em `unpacked_n_elf` (fora de exec, lib e proporções) sem interromper, de filesystem sem ELF, só com `.ko` (contagens de FR-002, proporções nulas) e sem executável (PIE nulo), e de erro de percurso com `meta_fs_status=erro` em `tests/test_filesystem_features.py`
- [ ] T011 [US4] FR-006, FR-009, FR-012 — `src/features/filesystem.py::filesystem_features` (agregação, nulos, malformados, `meta_fs_status`, `meta_fs_error`)
- [ ] T012 [US4] FR-001, FR-007, FR-008, FR-010, FR-012 — Cenários US4.1 e US4.3: testes de colunas `unpacked_*` presentes com unpack `ok` (fixture que chega a `ok`), nulas e `meta_fs_status=nao_executado` em todos os estados diferentes de `ok` de `001/FR-016` (`sem_filesystem`, `falha`, `limite_tamanho`, `limite_arquivos`, `limite_tempo`, `nao_executado`) e no resultado de erro, da linha mantida com `meta_fs_status=erro`, da guarda de vazamento estendida às colunas novas e do log em `tests/test_pipeline_extraction.py`
- [ ] T013 [US4] FR-001, FR-008, FR-010, FR-012 — Chamar `filesystem_features` dentro do contexto do unpack em `pipeline/feature_extraction.py::extract_features_from_path`, gravar nulos e `meta_fs_status` em `_build_error_result` e nos estados sem `ok`, e registrar o log por lote em `extract_features_batch`

## Phase 6: Polish

- [ ] T014 FR-002, FR-011, FR-012 — Atualizar a `001` (dona da tabela de features): `specs/001-extracao-features/data-model.md` (colunas `unpacked_*` e `meta_fs_*`, regra de nulo) e `specs/001-extracao-features/spec.md` (contagem de metadados de FR-009, lista de FR-016 e a Assumption sobre a `012`)
- [ ] T015 FR-010 — Na reextração (001/T050), medir e registrar no `TODO.md` a distribuição de `unpacked_n_elf`, `unpacked_n_elf_static`, `meta_fs_elf_malformed`, `meta_fs_status` e `meta_fs_arch`, e conferir a regra de raízes de filesystem em amostra da saída do extrator
- [ ] T016 FR-002 — Conferir que o grupo F de `configs/evaluation.yaml` (`011/FR-005`, 011/T001) resolve para as 19 colunas `unpacked_*`

## Dependencies & Execution Order

- T001 → T002 → T003 → fases 2 a 5 → Phase 6.
- T013 depende de 001/T044 e 001/T045 (`src/features/unpack.py`) e edita
  `pipeline/feature_extraction.py`: não roda em paralelo com 001/T039,
  T041, T042, T045, T048, T051 nem com 004/T033, T036, T038; T012 edita
  `tests/test_pipeline_extraction.py`: em série com 001/T040, T047, T049 e
  004/T039. T001 edita `pyproject.toml` com 010/T002.
- 001/T050 (reextração única) depende de T013; T015 roda na reextração.
- T016 depende de 011/T001.
