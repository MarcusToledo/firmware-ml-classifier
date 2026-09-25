# Contrato: treino

## `scripts/train.py`

```text
python scripts/train.py --model {extra_trees,random_forest,majoritario,identidade,score_firmware,all}
                        [--experiment {principal,binario}] [--scheme {grouped,random}]
                        [--columns-file PATH] [--config configs/training.yaml]
                        [--override chave=valor ...] [--force]
```

- `--columns-file`: lista de colunas do vetor (uma por linha), usada pela
  `011` nas ablations; sem ela, todas as colunas da tabela.
- Saída 0: grava `models/runs/<run_id>/` de cada execução e imprime os
  `run_id`.
- Saída ≠ 0: SHA256 divergente (tabela, proveniência, folds ou tabela de
  features do `score_firmware`), coluna pedida inexistente na tabela,
  nenhuma coluna depois do filtro num fold (cita repetição, fold e
  colunas), diretório `models/runs/<run_id>/` já existente sem `--force`.

## `src/models/training.py::train_run`

```python
train_run(model: str, experiment: str, scheme: str,
          columns: list[str] | None, config: TrainingConfig,
          force: bool = False) -> Path
```

Devolve o diretório da execução. A `011` chama esta função para os braços
de ablation.
