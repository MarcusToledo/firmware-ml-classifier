# Research: Preparação do dataset de treino

Todas as decisões abaixo são do pesquisador (clarify e plano, 2026-09-25).
Números medidos citam data e artefato.

## R1. Detectores constantes ficam no vetor; filtro vai para a 010

- **Decisão**: a 008 não remove coluna por critério calculado sobre os
  dados; registra as constantes como diagnóstico. O filtro de variância,
  ajustado só na partição de treino, é FR da `010`.
- **Justificativa**: um filtro calculado sobre todo o dataset é
  transformador ajustado a dados (constituição III). Os 5 detectores são
  constantes porque o documento cobre só o cabeçalho (`max_strings=2000`,
  TickTick T07) e podem variar depois de `001/FR-015` e `001/FR-016`.
- **Alternativas rejeitadas**: lista fixa de remoção na 008 (precisaria
  ser revista quando a 001 mudar); manter sem filtro nenhum.

## R2. One-hot de lista fixa para `fs_type` e `compression_type`

- **Decisão**: categorias fixas em `configs/dataset.yaml`: `fs_type`
  `squashfs`, `jffs2`, `cramfs`, `ubifs`; `compression_type` `lzma`,
  `gzip`, `xz`, `lzo`; mais `outro` e `ausente`.
- **Justificativa**: a lista vem do domínio: tipos de filesystem e de
  compressão de firmware embarcado que o Binwalk reconhece (decisão do
  pesquisador no analyze, 2026-09-25), não da contagem no dataset. Sem
  ajuste a dados, a codificação é igual em treino e teste e não viola III.
  Para referência, valores medidos em `features_v2.parquet`
  (2026-09-25): `fs_type` squashfs 661, nulo 154, jffs2 23, cramfs 1,
  ubifs 1; `compression_type` lzma 592, nulo 135, gzip 91, xz 20, lzo 2.
- **Alternativas rejeitadas**: codificador ajustado no treino; remover as
  colunas.

## R3. Sem scaler

- **Decisão**: nenhuma escala ou normalização (FR-012).
- **Justificativa**: Extra Trees e Random Forest dividem por limiar e não
  dependem da escala (constituição IV); o scaler do roadmap antigo do
  `TODO.md` foi descartado.

## R4. Proveniência em arquivo da 008

- **Decisão**: `training_table_provenance.jsonl`, uma linha por
  `firmware_id` da tabela e das exclusões, com os aliases.
- **Justificativa**: `009`, `010` e `011` leem identidade de um artefato
  com o mesmo conjunto de `firmware_id` da tabela, cujo SHA256 fica nos
  metadados; o vetor fica sem identidade (III).
- **Alternativa rejeitada**: ler `labels_v2_aliases.jsonl` (`005/FR-021`),
  que cobre também os `firmware_id` fora da tabela e muda com a rotulagem.

## R5. Falhas de extração

- **Decisão**: `meta_binwalk_status=erro` e `meta_unpack_status=falha`
  excluem com motivo `falha_extracao`; `timeout`, `limite_tempo`,
  `nao_executado` e `firmware_id` nulo (leitura falha, `001/FR-004`)
  interrompem pedindo nova extração (analyze, 2026-09-25: a rotulagem já
  falha com `firmware_id` nulo, `005/FR-002`);
  `sem_filesystem`, `limite_tamanho` e `limite_arquivos` ficam.
- **Justificativa**: `001/FR-014` e `001/FR-016` tratam tempo esgotado como
  falha que exige rodar de novo; excluir um resultado transitório tornaria
  a tabela dependente da máquina (princípio V). Nos demais estados de
  unpack as strings vêm do arquivo bruto e a linha é válida. As exclusões
  são avaliadas por alias antes da checagem de divergência (R6).

## R5b. Rótulos da mesma tabela de features

- **Decisão**: o SHA256 de `--features` em `labels_v2.meta.json`
  (`005/FR-018`) DEVE ser igual ao da tabela lida (analyze, 2026-09-25).
- **Justificativa**: a junção por `firmware_id` aceitaria rótulos de outra
  geração de features com os mesmos IDs, como depois da movimentação
  TP-Link, que muda `meta_path` e não muda `firmware_id` (princípio VI).

## R6. Aliases divergentes falham

- **Decisão**: falhar listando `firmware_id` e colunas (FR-002).
- **Justificativa**: princípio VI proíbe fallback silencioso; divergência
  é possível com `firmware_id` do prefixo (`001/FR-004`) e Binwalk sobre o
  arquivo inteiro (`001/FR-007`). A checagem vale só para os `firmware_id`
  que sobram das exclusões, para que um alias com Binwalk em erro seja
  excluído e não aborte a preparação (analyze, 2026-09-25).

## R7. Todos os motivos de exclusão; contagem por fabricante de cada alias

- **Decisão**: o registro lista todos os motivos; o `firmware_id` conta
  uma vez em cada motivo e em cada fabricante dos aliases.
- **Justificativa**: o registro audita cada causa; a invariante de
  cobertura (SC-002) vale sobre `firmware_id`, não sobre as contagens.

## R8. Validação: artefato e órfãos

- **Decisão**: `scripts/validate_dataset.py` é reescrito: confere o
  artefato (FR-015) e falha com órfãos de `dataset/raw/`; as checagens de
  layout, ASUS não roteador e conteúdo repetido saem.
- **Justificativa**: layout é `004/FR-015`, que também pega os arquivos
  soltos em `asus/` que a checagem "ASUS não roteador" olhava; conteúdo
  repetido vira alias por `firmware_id`; o script lia o `labels.csv` v1.
  Órfãos são comparados pelo caminho relativo à raiz (`004/FR-016`) com a
  seleção de arquivos de `001/FR-001`, para não acusar arquivos que a
  extração ignora de propósito (analyze, 2026-09-25).

## R9. Estrutura

- **Decisão**: pacote `src/dataset/`; CLIs `scripts/build_dataset.py`
  (previsto na estrutura-alvo do `AGENTS.md`) e `scripts/validate_dataset.py`;
  configuração `configs/dataset.yaml` com `--config` e `--override`, como
  na extração; movimentação TP-Link como modo novo de
  `scripts/reorganize_dataset.py`, com mapa em `configs/tplink_merge_map.csv`.
- **Justificativa**: segue a separação atual (`src/labeling/` para regra,
  `scripts/` para CLI); `dataset/` não é versionado, então o mapa fica em
  `configs/`.

## R10. TP-Link canônico: `tp_link`

- **Decisão**: mover os 27 arquivos de `tplink` (26 modelos com arquivo)
  para `tp_link` (82 arquivos), trocando `_` por `-` no nome do modelo;
  diretório de destino com arquivo é erro resolvido à mão; depois, busca
  completa na NVD com `003/FR-014`, porque `005/FR-026` recusa o cache v2.
- **Justificativa**: medido em 2026-09-25: `tplink` usa `_` e `tp_link`
  usa `-`; com a troca, `tl_er604w`↔`tl-er604w` coincidem (os dois com
  arquivo) e `archer_d7b`↔`archer-d7b` (o de `tplink` vazio). Sem a troca,
  o mesmo dispositivo seria dois modelos no cache, na partição e no
  baseline de identidade. A busca NVD de `tp_link` já foi corrigida para
  `tp-link` (`TODO.md`, histórico).

## R11. `doc2vec_*` fora do vetor

- **Decisão**: FR-004 tira `doc2vec_*` do vetor enquanto a T06 for
  Proposto.
- **Justificativa**: decisão do pesquisador no analyze da `007`
  (2026-09-25); o Doc2Vec ajustado no dataset inteiro é vazamento
  transdutivo (Arp et al., USENIX Security 2022, P3), registrado nas
  violações III/V da `007`.
