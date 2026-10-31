# Baseline determinístico de regras

O módulo `src/scoring.py` produz uma previsão por regras sobre sinais extraídos
do firmware. Ele serve para comparar com Extra Trees e Random Forest; não gera
rótulos de treino. Os rótulos de referência vêm exclusivamente do cache CVE
por meio de `src/labeling/cve_labels.py` e `scripts/generate_labels.py`.

## Cálculo

Cada grupo presente produz um sub-score de 0 a 1. O score final é a média
ponderada dos grupos presentes; grupos ausentes têm peso zero. Sem grupos
presentes, o score é zero e a classe inicial é `sem_cve_conhecida`,
independentemente dos limiares. `configs/scoring.yaml` define pesos, limiares,
níveis mínimos das regras e parâmetros dos sub-scores (faixas, fatores e
saturações); `src/scoring.py` define os valores padrão dessas opções quando
omitidas no YAML.

| Grupo | Peso configurado | Sinais lidos pelo sub-score |
|---|---:|---|
| Stats | 0,10 | `entropy`, `compress_ratio`, `byte_mean` |
| Strings | 0,30 | `count_hardcoded_passwords`, `count_credential_pairs`, `count_non_public_ips`, `count_public_ips`, `has_outdated_libssl`, `has_outdated_busybox`, `has_outdated_dropbear` |
| Binwalk | 0,15 | `has_encrypted_sections`, `n_crypto_signatures`, `entropy_variance_across_sections`, `fs_type`, `compression_type`, `n_filesystems` |

Os pesos preservam as razões relativas anteriores à remoção do sinal CVE.
Quando os três grupos estão presentes, a implementação divide pela soma
0,55. Esses valores e os limiares são hipóteses heurísticas, não parâmetros
ajustados ou validados empiricamente para este TCC.

O score abaixo de 0,20 prevê `sem_cve_conhecida`; de 0,20 até menos de
0,60 prevê `cve_conhecida`; a partir de 0,60 prevê `cve_critica`.
Esses nomes são classes previstas para permitir comparação com o
classificador supervisionado. O baseline não consulta CVEs e uma previsão
`sem_cve_conhecida` não prova ausência de vulnerabilidade.

As regras `has_telnetd`, `has_debug_account` e
`count_hardcoded_passwords > 0` elevam, no mínimo, a previsão para
`cve_conhecida`. Elas nunca rebaixam uma classe. O resultado inclui score
numérico, contribuição de cada grupo e regra aplicada para auditoria.

## Separação entre features e rótulos

`cvss_max`, `cve_total` e `cve_count_*` definem o rótulo externo e não
participam do baseline nem do vetor do classificador. `meta_brand` e
`meta_model` são metadados de consulta, não features. A guarda em
`tests/test_pipeline_extraction.py` verifica essa separação.

O cache de `scripts/fetch_cves.py` é consultado por fabricante/modelo; a
aplicabilidade à versão do firmware é avaliada depois, na rotulagem por
`src/labeling/cve_labels.py` e `scripts/generate_labels.py`. Quando as CVEs
indeterminadas podem mudar a classe, o rótulo é `indeterminado`. Uma entrada
ausente no cache indica consulta incompleta, por isso `generate_labels.py`
interrompe a execução em vez de atribuir `sem_cve_conhecida`.

## Execução

```bash
uv run python scripts/generate_labels.py \
  --features dataset/processed/features_v2.parquet \
  --cves dataset/processed/cve_cache_v2.json \
  --output dataset/processed/labels_v2.csv
```

Para consultar apenas a distribuição sem salvar, adicione `--dry-run`.
O caminho de features corresponde ao `configs/dataset.yaml`; o cache CVE
usa o caminho padrão de `scripts/fetch_cves.py` e a saída corresponde ao
padrão de `scripts/generate_labels.py`.

Para calcular o baseline em código:

```python
from pathlib import Path

from src.scoring import load_scoring_config, score_firmware

config = load_scoring_config(Path("configs/scoring.yaml"))
result = score_firmware({"entropy": 7.5, "has_telnetd": True}, config)
print(result.level, result.numeric_score, result.hard_rule_applied)
```

No treino, `scripts/train.py --model score_firmware` executa o baseline nos
folds congelados. Ele lê as features brutas, inclusive colunas retiradas do
vetor do classificador na seleção de detectores, e as registra em
`t13a_columns_read` nos metadados da execução; não usa o vetor selecionado.

O baseline e os rótulos CVE precisam ser avaliados no mesmo conjunto de
firmwares antes de qualquer afirmação de desempenho. Este documento não
contém métricas experimentais.
