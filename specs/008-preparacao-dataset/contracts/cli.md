# Contrato de CLI: preparação do dataset

## `scripts/build_dataset.py`

```text
python scripts/build_dataset.py [--config configs/dataset.yaml]
                                [--features PATH] [--labels PATH]
                                [--output-dir dataset/processed]
                                [--override chave=valor ...]
```

- Padrões em `configs/dataset.yaml`; flags e `--override` têm precedência
  e ficam registrados em `config` nos metadados (princípio V).
- Saída 0: grava os quatro artefatos de `data-model.md`.
- Saída ≠ 0, sem gravar nada: entrada ausente, sem coluna exigida ou com
  SHA256 de features diferente do registrado na rotulagem (FR-001);
  `firmware_id` nulo, sem par ou alias divergente (FR-002); falha
  transitória ou `nao_executado` (FR-007); tabela vazia ou alguma das
  três classes sem exemplo (FR-008).

## `scripts/validate_dataset.py`

```text
python scripts/validate_dataset.py [--processed-dir dataset/processed]
                                   [--raw dataset/raw]
```

- Saída 0: artefato íntegro e sem órfãos.
- Saída ≠ 0, com uma linha por problema: `firmware_id` duplicado, coluna
  proibida, coluna de texto no vetor, alvo fora das três classes, SHA256
  de entrada diferente do registrado, colunas diferentes das dos
  metadados, órfãos por fabricante, comparados pelo caminho relativo à
  raiz e com a seleção de arquivos de `001/FR-001` (FR-015).

## `scripts/reorganize_dataset.py --merge-vendor tplink:tp_link`

```text
python scripts/reorganize_dataset.py --merge-vendor tplink:tp_link [--execute]
```

- Sem `--execute` (padrão do script): só mostra o plano.
- Com `--execute`: grava `configs/tplink_merge_map.csv`, move os
  arquivos trocando `_` por `-` no nome do modelo e remove os diretórios
  vazios de `tplink/`; falha sem mover nada, citando o modelo, se algum
  diretório de destino já tem arquivo (FR-016).
