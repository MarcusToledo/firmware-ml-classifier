# Implementation Plan: Features do filesystem desempacotado

**Branch**: `docs/escopo-restante` | **Date**: 2026-09-25 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/012-features-filesystem/spec.md`

**Note**: spec nova, Status Planejado (TickTick T12). Nenhum código existe
ainda; módulos e testes abaixo são previstos. Depende do unpack de
`001/FR-016` (001/T044, T045). Estrutura decidida pelo pesquisador em
2026-09-25 ([research.md](research.md)).

## Summary

`src/features/filesystem.py::filesystem_features(root, max_bytes)` acha as
raízes de filesystem na saída do unpack da `001`, percorre-as sem seguir
symlinks, identifica ELF pelo cabeçalho (repetidos por SHA256 contam uma
vez), lê cada um com pyelftools sobre stream limitado a `max_bytes` e
devolve as contagens de arquivos e ELF (inclusive estáticos), as
proporções de NX, PIE, RELRO, canary e FORTIFY pelos critérios do checksec
2.7.1, as proporções de importação das 8 funções perigosas e os metadados
`meta_fs_elf_malformed`, `meta_fs_arch`, `meta_fs_status` e
`meta_fs_error`. A extração chama a
função dentro do contexto do unpack, antes da limpeza; sem unpack `ok`, as
colunas `unpacked_*` ficam nulas.

## Technical Context

**Language/Version**: Python ≥ 3.9

**Primary Dependencies**: pyelftools (nova, pura Python, domínio público;
`pyelftools<0.33` em qualquer Python: 0.32 é a última versão sem
`requires_python`, e a 0.33 exige Python ≥ 3.10, verificado no PyPI em
2026-09-25); scikit-learn passa a `>=1.6` (NaN em Extra Trees e Random
Forest; 1.6.x é a última linha compatível com Python 3.9)

**Storage**: colunas `unpacked_*` e `meta_fs_*` na tabela de features da
`001`

**Testing**: pytest, com ELF de teste pequenos versionados em
`tests/fixtures/elf/` (gerados uma vez por script documentado, sem
compilar na suíte)

**Target Platform**: Linux

**Project Type**: módulo em `src/features/`, chamado por
`pipeline/feature_extraction.py`

**Performance Goals**: sem meta; o custo cresce com o número de ELF,
limitado pelos 100 mil arquivos de `001/FR-016`

**Constraints**: nada é executado (constituição I); leitura limitada por
`max_bytes`; ELF malformado não interrompe o lote (VI); nenhum dado de
identidade ou CVE (III)

**Scale/Scope**: até 840 firmwares; número de ELF por firmware ainda não
medido (depende de 001/T050)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

|Princípio|Resultado|Evidência|
|---|---|---|
|I. Somente análise estática|Passa|Só lê cabeçalhos, program headers, seção dinâmica e símbolos dinâmicos dos arquivos extraídos pelo unpack estático de `001/FR-016`; nada é executado (FR-003)|
|II. Rótulo exclusivamente por CVE|Não se aplica|Não gera rótulo|
|III. Sem vazamento|Passa|Features não usam fabricante, modelo, versão, path ou CVE, com teste de guarda (FR-007, SC-003); arquitetura só em `meta_fs_arch`, fora do vetor (FR-011); sem SBOM|
|IV. Modelos simples|Não se aplica|Sem modelo|
|V. Reprodutibilidade|Passa|Lista de funções na configuração versionada; percurso em ordem lexicográfica; resultado função só dos bytes lidos; logs de FR-010|
|VI. Firmware não confiável|Passa|Leitura limitada por `max_bytes` sem carregar o arquivo inteiro; symlinks não seguidos; ELF malformado contado em `meta_fs_elf_malformed` sem parar o lote (FR-006, SC-004); outras falhas em `meta_fs_status`/`meta_fs_error`, com a linha mantida e excluída pela `008` (FR-012); sem unpack `ok`, nulo em vez de zero (FR-008, SC-002)|
|VII. Integridade científica|Passa|Nenhum número de resultado; versão do pyelftools conferida no PyPI com data|

Re-check após Phase 1: sem mudança.

## Project Structure

### Documentation (this feature)

```text
specs/012-features-filesystem/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── tasks.md
└── checklists/
    ├── requirements.md
    └── rastreabilidade.md
```

### Source Code (repository root)

```text
src/features/
└── filesystem.py            # percurso, classificação ELF, proteções, importações

pipeline/
└── feature_extraction.py    # chama filesystem_features no contexto do unpack (001)

configs/
└── feature_extraction.yaml  # seção filesystem: lista de funções perigosas

tests/
├── fixtures/elf/            # ELF de teste versionados + script que os gerou
├── test_filesystem_features.py
└── test_pipeline_extraction.py  # colunas nulas sem unpack ok; guarda de vazamento
```

**Structure Decision**: módulo novo em `src/features/`, ao lado de
`binwalk.py` e `statistics.py`; o unpack continua da `001`
(`src/features/unpack.py`).

### US → FR → módulo → teste → TickTick

|FR|US|Módulo (previsto)|Teste (previsto)|TickTick|
|---|---|---|---|---|
|FR-001|US1|`pipeline/feature_extraction.py::extract_features_from_path` (dentro do contexto de `src/features/unpack.py`)|`tests/test_pipeline_extraction.py` (colunas presentes com unpack `ok`)|T12|
|FR-002|US1|`src/features/filesystem.py::find_roots`, `walk_files`, `classify_elf`|`tests/test_filesystem_features.py` (US1.1, US1.2, carvados ignorados, ELF repetido)|T12|
|FR-003|US2|`src/features/filesystem.py::read_elf` (pyelftools, `max_bytes`)|`tests/test_filesystem_features.py` (arquivo maior que `max_bytes`)|T12|
|FR-004|US2|`src/features/filesystem.py::hardening`|`tests/test_filesystem_features.py` (US2.1, US2.2, relocável fora)|T12|
|FR-005|US3|`src/features/filesystem.py::dangerous_imports`; `configs/feature_extraction.yaml`|`tests/test_filesystem_features.py` (US3.1, US3.2)|T12|
|FR-006|US4|`src/features/filesystem.py::read_elf`|`tests/test_filesystem_features.py` (US4.2)|T12|
|FR-007|US4|`src/features/filesystem.py`|`tests/test_pipeline_extraction.py` (US4.3, guarda estendida)|T12|
|FR-008|US4|`pipeline/feature_extraction.py::extract_features_from_path`, `_build_error_result`; `pyproject.toml`|`tests/test_pipeline_extraction.py` (US4.1)|T12|
|FR-009|US4|`src/features/filesystem.py::filesystem_features`|`tests/test_filesystem_features.py` (sem ELF, sem executável)|T12|
|FR-010|US1|`pipeline/feature_extraction.py::extract_features_batch`|`tests/test_pipeline_extraction.py` (`caplog`)|T12|
|FR-011|US1|`src/features/filesystem.py::filesystem_features`|`tests/test_filesystem_features.py` (`meta_fs_arch`, fora do vetor)|T12|
|FR-012|US4|`src/features/filesystem.py::filesystem_features`; `pipeline/feature_extraction.py::extract_features_from_path`|`tests/test_filesystem_features.py` (US4.4); `tests/test_pipeline_extraction.py` (linha mantida com `erro`)|T12|

### Sem verificação

Nenhum FR.

### Símbolos com requisito em outra spec

- Unpack, limites e `meta_unpack_status`: `001/FR-016`.
- Entrada no vetor: `008/FR-003`; grupo F das ablations: `011/FR-005`.

## Complexity Tracking

Sem violação.
