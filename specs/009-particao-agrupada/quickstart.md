# Quickstart: partição agrupada

Pré-requisito: artefatos da `008` em `dataset/processed/`.

```bash
python scripts/make_folds.py
```

Conferir no log o número de `firmware_id` e de grupos, o maior grupo e a
contagem por classe de cada fold. Para SC-002, rodar de novo e comparar
`folds_grouped.parquet` e `folds_random.parquet` com `cmp`.
