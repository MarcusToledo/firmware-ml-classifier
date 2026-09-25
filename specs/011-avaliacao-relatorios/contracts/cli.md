# Contrato: avaliação

## `scripts/evaluate.py`

```text
python scripts/evaluate.py [--config configs/evaluation.yaml]
                           [--override chave=valor ...]
```

- Gera as execuções que faltam pela `010` (`train_run`), avalia e grava
  `reports/<timestamp>/`; imprime o diretório.
- Saída ≠ 0: `run_id` existente com hash recalculado diferente ou
  diretório incompleto (pede `--force` na `010`); execuções com SHA256 de
  tabela ou proveniência diferentes, ou de folds diferentes no mesmo
  esquema; meta da `008` com SHA256 da tabela diferente (FR-001); falha de
  treino de um braço (`010/FR-002`), citando o braço.
