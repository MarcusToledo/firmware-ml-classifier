# Research: Features do filesystem desempacotado

Decisões do pesquisador (clarify e plano, 2026-09-25). Fontes das features:
`.docs/brainstorming/literatura-features-e-modelos.md`, seção 3.

## R1. Inventário, hardening e funções perigosas

- **Decisão**: contagens de arquivos e ELF; proporções de NX, PIE, RELRO
  completo e parcial, canary e FORTIFY; proporção de importação de
  `system`, `popen`, `execve`, `strcpy`, `strcat`, `sprintf`, `vsprintf`,
  `gets`.
- **Justificativa**: Costin et al. (USENIX Security 2014) desempacotam e
  analisam estaticamente os arquivos extraídos; as proteções seguem os
  critérios do checksec 2.7.1 (`filecheck`), usados no OWASP FSTM; a
  lista de funções vem do `config/functions.cfg` do EMBA (lido pelos
  módulos S10 e S13: `strcpy`, `strcat`, `sprintf`, `system`, `popen`) e da
  CWE-676/Flawfinder (`gets`, `vsprintf`, `execve`). O analyze de
  2026-09-25 verificou no GitHub que o EMBA não tem módulo S11 e que a
  lista atribuída ao EMBA no relatório de literatura não conferia;
  `printf`, `fprintf` e `mmap` do EMBA ficaram fora. As proporções
  independem do tamanho do filesystem.

## R2. pyelftools

- **Decisão**: ler ELF com pyelftools, declarado em `pyproject.toml`
  com teto global `pyelftools<0.33` (0.32 é a última sem
  `requires_python`; 0.33 exige Python ≥ 3.10; PyPI, 2026-09-25), a mesma
  versão em todos os ambientes (decisão do analyze).
- **Justificativa**: biblioteca pura Python, madura, trata 32/64 bits e
  endianness; um parser próprio teria de ser escrito e auditado. Promove
  de Proposto (escopo restante PR-04) só esta leitura; Ghidra continua
  Proposto.

## R3. Nulo para indisponível

- **Decisão**: NaN sem unpack `ok` e nas proporções sem denominador;
  `scikit-learn>=1.6`.
- **Justificativa**: zero seria sinal falso (constituição VI). Extra Trees
  e Random Forest aceitam NaN a partir da 1.6 (verificado com 1.7.2 em
  2026-09-25); `VarianceThreshold` também.

## R4. Arquitetura fora do vetor

- **Decisão**: `meta_fs_arch` (arquitetura mais frequente), fora do vetor.
- **Justificativa**: a arquitetura acompanha chipset e linhagem do
  fabricante; como feature, poderia codificar identidade (constituição
  III).

## R5. Prefixo `unpacked_`

- **Decisão**: colunas `unpacked_*`.
- **Justificativa**: `fs_` colidiria com as colunas one-hot `fs_type__*`
  de `008/FR-010` no agrupamento das ablations (`011/FR-005`).

## R6. ELF estático, universo contado e falhas (analyze, 2026-09-25)

- ELF sem tabela de símbolos dinâmicos sai dos denominadores de canary,
  FORTIFY e importações e é contado à parte: zero nesses casos seria sinal
  falso (busybox estático é comum em firmware).
- Só as raízes de filesystem extraídas contam, e ELF repetido conta uma
  vez: os carvados intermediários e rootfs repetidos dependem do extrator.
- `meta_fs_status`/`meta_fs_error`: erro fora do ELF malformado anula só
  as `unpacked_*` e fica visível (constituição VI); a `008` exclui a linha.
- Uma reextração só: 001/T050 depende da 012, para não refazer a
  rotulagem.
