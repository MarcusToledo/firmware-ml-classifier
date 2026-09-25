# Contrato: partição agrupada

## `scripts/make_folds.py`

```text
python scripts/make_folds.py [--config configs/dataset.yaml]
                             [--processed-dir dataset/processed]
                             [--override partition.seeds=[0,1,2,3,4,5,6,7,8,9] ...]
```

- Saída 0: grava `folds_grouped.*` e `folds_random.*`.
- Saída ≠ 0, sem gravar nada: SHA256 da tabela ou da proveniência
  diferente do registrado (FR-001); `firmware_id` cruzando treino e teste
  em qualquer esquema, ou chave de modelo cruzando em `grouped` (FR-003).

## `src/dataset/partition.py::load_folds`

```python
@dataclass(frozen=True)
class FoldSet:
    table: pandas.DataFrame        # training_table.parquet
    provenance: pandas.DataFrame   # linhas in_table=true
    folds: pandas.DataFrame        # repeat, seed, fold, firmware_id, role, group
    meta: dict                     # folds_<scheme>.meta.json

load_folds(processed_dir: Path, scheme: str) -> FoldSet
```

- `scheme`: `grouped` ou `random`.
- Falha, citando os dois valores, quando o SHA256 da tabela, da
  proveniência ou do arquivo de folds difere do registrado (FR-006). O
  consumidor usa `FoldSet.table`, sem ler a tabela à parte.
