# Baseline determinístico de regras

O módulo `src/scoring.py` produz uma previsão por regras sobre sinais extraídos
do firmware. Ele serve para comparar com Extra Trees e Random Forest; não gera
rótulos de treino. Os rótulos de referência vêm exclusivamente do cache CVE
por meio de `src/labeling/cve_labels.py` e `scripts/generate_labels.py`.

## Cálculo

Cada grupo presente produz um sub-score de 0 a 1. O score final é a média
ponderada dos grupos presentes; grupos ausentes têm peso zero. Com nenhum
grupo presente, o score é zero. Os parâmetros estão em
`configs/scoring.yaml`.

| Grupo | Peso configurado | Sinais |
|---|---:|---|
| Stats | 0,10 | entropia, compressibilidade, média de bytes |
| Strings | 0,30 | credenciais, IPs, bibliotecas desatualizadas |
| Binwalk | 0,15 | seções cifradas, assinaturas, filesystem e compressão |

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

O cache de `scripts/fetch_cves.py` usa fabricante/modelo e atualmente não
filtra a versão exata do firmware. Uma entrada ausente indica consulta
incompleta, por isso `generate-labels` interrompe a execução em vez de
atribuir `sem_cve_conhecida`.

## Execução

```bash
uv run python scripts/generate_labels.py \
  --features dataset/processed/features.parquet \
  --cves dataset/cve_cache.json \
  --output dataset/processed/labels_v2.csv
```

Para consultar apenas a distribuição sem salvar, adicione `--dry-run`.
Para calcular o baseline em código:

```python
from pathlib import Path

from src.scoring import load_scoring_config, score_firmware

config = load_scoring_config(Path("configs/scoring.yaml"))
result = score_firmware({"entropy": 7.5, "has_telnetd": True}, config)
print(result.level, result.numeric_score, result.hard_rule_applied)
```

O baseline e os rótulos CVE precisam ser avaliados no mesmo conjunto de
firmwares antes de qualquer afirmação de desempenho. Este documento não
contém métricas experimentais.
