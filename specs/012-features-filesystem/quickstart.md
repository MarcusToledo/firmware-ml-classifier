# Quickstart: features do filesystem desempacotado

Pré-requisitos: `001/FR-016` implementado (unpack) e pyelftools instalado
(`python -m pip install -e ".[dev]"`).

```bash
python scripts/extract_features.py --input dataset/raw \
    --output dataset/processed/features_v2.parquet \
    --label-from-path --dataset-root dataset/raw
```

Conferir no log quantos firmwares tiveram as features `unpacked_*`
calculadas, quantos ELF foram lidos e quantos malformados.
