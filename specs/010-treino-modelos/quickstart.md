# Quickstart: treino

Pré-requisitos: artefatos da `008` e da `009` em `dataset/processed/`.

```bash
python scripts/train.py --model all
python scripts/train.py --model all --experiment binario
python scripts/train.py --model all --scheme random
```

Conferir no log, por fold, tamanhos, classes, colunas usadas,
hiperparâmetros e seed. Para SC-002, rodar de novo em outro processo e
comparar os `predictions.parquet` com `cmp`.
