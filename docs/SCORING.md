# Sistema de Scoring Deterministico

Sistema de rotulagem automatica que gera ground truth (labels de treino) para o classificador ML.
Combina multiplos sinais extraidos do firmware e produz um nivel de seguranca: **Seguro / Vulneravel / Critico**.

## Principios

- **Deterministico**: mesmas features → mesmo label. Essencial para reprodutibilidade do TCC.
- **Extensivel**: funciona hoje com poucas features; absorve CVEs, strings e Binwalk sem quebrar.
- **Auditavel**: retorna a contribuicao de cada sinal para justificar o label gerado.
- **Configuravel**: thresholds e pesos em YAML (`configs/scoring.yaml`) — ajuste sem mudar codigo.

## Arquitetura

### Modelo: Weighted Signals + Hard Rules

Cada grupo de sinais calcula um sub-score entre 0.0–1.0.
O score final e a media ponderada dos sinais presentes, mapeado para classe via thresholds.
Hard rules sobrescrevem o resultado quando necessario (so escalam, nunca rebaixam).

```
score_total = Σ(signal_score × weight) / Σ(weight dos sinais presentes)

score < 0.30  →  "seguro"      (0)
score < 0.60  →  "vulneravel"  (1)
score >= 0.60 →  "critico"     (2)
```

Sinais ausentes (feature ainda nao implementada) tem peso 0 e sao ignorados automaticamente.
Os pesos dos sinais presentes sao redistribuidos proporcionalmente.

### Hard Rules (overrides)

Hard rules so escalam o nivel — nunca rebaixam. Sao avaliadas nesta ordem:

| Condicao | Nivel minimo |
|---|---|
| `has_telnetd = True` | vulneravel |
| `has_debug_account = True` | vulneravel |
| `count_hardcoded_passwords > 0` | vulneravel |
| `cvss_max >= 9.0` | critico |

## Grupos de Sinais

### 1. Stats (peso: 0.10) — Ativo

Features estatisticas do binario. Peso baixo porque sao ambiguas sem contexto.

| Feature | Formula do sub-score | Interpretacao |
|---|---|---|
| `entropy` | `clamp((entropy - 6.0) / 2.0)` | Alta entropia (>7.5) → comprimido/criptografado |
| `compress_ratio` | `clamp((ratio - 0.80) / 0.20)` | Ratio perto de 1.0 → incompressivel, suspeito |
| `byte_mean` | `abs(mean - 127.5) / 127.5 × 0.3` | Desvio de 127.5 → sinal fraco, downweighted |

### 2. CVE (peso: 0.45) — Ativo

Dados de vulnerabilidades conhecidas via NVD API v2.0. Peso dominante — e o sinal mais confiavel.

| Feature | Formula do sub-score | Peso interno |
|---|---|---|
| `cvss_max` | `clamp(cvss / 10.0)` | 3.0 (dominante) |
| `cve_count_critical` | `sigmoid(count, mid=2, steep=1.5)` | 1.5 |
| `cve_count_high` | `sigmoid(count, mid=3, steep=1.0)` | 1.0 |

Sub-score final = media ponderada interna dos sub-componentes.

**Como funciona o lookup**: `generate_labels.py` faz merge do CVE cache usando a chave
`"{meta_brand}/{meta_model}"` (lowercase), que e o mesmo formato gerado por `fetch_cves.py`.
Exemplo: `"dlink/dir-300"` → `{cvss_max: 9.8, cve_count_critical: 5, ...}`.

**Normalizacao de nomes**: `fetch_cves.py` normaliza vendor e model antes de consultar a NVD:
- Vendor aliases: `dlink` → `d-link`, `tplink` → `tp-link`
- Model sem hifen: `dir300` → `DIR-300`, `dsr1000n` → `DSR-1000N`
- Model com underscore: `f5d7230_4` → `F5D7230-4`

**Limitacao conhecida**: OpenWrt retorna 0 CVEs na NVD porque e open-source e as vulnerabilidades
sao reportadas contra o chipset ou vendor original, nao contra "openwrt". Esses firmwares
sempre terao `cvss_max=0.0` no cache — o scoring depende unicamente do sinal stats para eles.

### 3. Strings (peso: 0.30) — Ativo

Padroes suspeitos encontrados nas strings ASCII do firmware.

| Feature | Formula do sub-score | Interpretacao |
|---|---|---|
| `count_hardcoded_passwords` | `sigmoid(count, mid=1, steep=2)` | Senhas hardcoded via key=value (`password=admin`) ou token avulso (`root`) |
| `count_credential_pairs` | `sigmoid(count, mid=1, steep=3)` | Pares `usuario:senha` fracos (`admin:admin`, `root:1234`) |
| `count_hardcoded_ips` | `sigmoid(count, mid=2, steep=1)` | IPs hardcoded no binario (inclui ranges privados) |
| `count_public_ips` | `sigmoid(count, mid=1, steep=2.5)` | IPs publicos (nao-RFC-1918) — indicadores de C2 ou telemetria |
| `has_outdated_libssl` | `0.6 se True, 0.0 se False` | OpenSSL < 1.1.1 detectado |
| `has_outdated_busybox` | `0.6 se True, 0.0 se False` | BusyBox < 1.33.0 detectado |
| `has_outdated_dropbear` | `0.6 se True, 0.0 se False` | Dropbear SSH < 2022.82 detectado |

Sub-score final = media dos sub-scores positivos (features zeradas nao diluem o resultado).

**Deteccao de libs**: as regexes aceitam variantes de formato comuns em firmwares reais:
- BusyBox: `BusyBox v1.19.4`, `BusyBox1.19.4`, `busybox_1.19.4`
- OpenSSL: `OpenSSL 1.0.2k`, `OpenSSL/1.0.2k` (banners HTTP como `Apache/2.2.31 OpenSSL/1.0.2k`)

**Deteccao de IPs publicos**: exclui RFC-1918 (`10.x`, `172.16-31.x`, `192.168.x`), loopback, link-local, multicast e reservados. IPs publicos hardcoded sao incomuns em firmware legitimo.

### 4. Binwalk (peso: 0.15) — Parcialmente implementado

Analise estrutural do firmware via Binwalk.

| Feature | Formula do sub-score | Status |
|---|---|---|
| `has_encrypted_sections` | `0.8 se True, 0.0 se False` | Pendente (Binwalk) |
| `n_crypto_signatures` | `min(1.0, count / 5) × 0.5` | Pendente (Binwalk) |
| `entropy_variance_across_sections` | `min(1.0, var / 3.0)` | **Implementado** em `src/features/statistics.py` |
| `fs_type` | `0.4 se cramfs/jffs2, 0.0 caso contrario` | Pendente (Binwalk) |
| `compression_type` | `0.2 se gzip, 0.0 caso contrario` | Pendente (Binwalk) |

`entropy_variance_across_sections` ja esta disponivel via `src/features/statistics.py`
(divide o binario em blocos de tamanho `BLOCK_SIZE` e calcula a variancia das entropias por secao),
mas ainda nao e emitida pelo pipeline de extracao de features.

## Configuracao

Arquivo: `configs/scoring.yaml`

```yaml
scoring:
  thresholds:
    low: 0.30    # < 0.30 → seguro
    high: 0.60   # >= 0.60 → critico

  weights:
    stats: 0.10
    cve: 0.45
    strings: 0.30
    binwalk: 0.15

  hard_rules:
    has_telnetd_min_level: "vulneravel"
    has_debug_account_min_level: "vulneravel"
    hardcoded_passwords_min_level: "vulneravel"
    cvss_critical_threshold: 9.0
```

Os pesos nao precisam somar 1.0 — a normalizacao e feita automaticamente sobre os sinais presentes.

## Uso

### Buscar CVEs (NVD API)

```bash
# Sem API key: 6s de delay entre requests (~15min para 157 pares)
fetch-cves --features dataset/processed/features.parquet --output dataset/cve_cache.json

# Com API key: 1s de delay (~3min)
NVD_API_KEY=<sua-key> fetch-cves --features dataset/processed/features.parquet

# Dry-run: lista os pares sem fazer requests
fetch-cves --features dataset/processed/features.parquet --dry-run

# Re-fetch forcado (ignora cache)
fetch-cves --features dataset/processed/features.parquet --force
```

### Gerar labels (dry-run)

```bash
generate-labels \
  --features dataset/processed/features.parquet \
  --config configs/scoring.yaml \
  --dry-run
```

### Gerar labels.csv com CVEs

```bash
generate-labels \
  --features dataset/processed/features.parquet \
  --cves dataset/cve_cache.json \
  --config configs/scoring.yaml \
  --output dataset/labels.csv
```

### Output (labels.csv)

| Coluna | Descricao |
|---|---|
| `firmware_id` | SHA256 do firmware |
| `meta_path` | Caminho original do arquivo |
| `vendor` | Fabricante (dlink, netgear, etc) |
| `model` | Modelo do dispositivo |
| `security_level` | seguro / vulneravel / critico |
| `numeric_score` | Score numerico 0.0–1.0 |
| `signal_stats` | Sub-score do sinal stats |
| `signal_cve` | Sub-score do sinal CVE |
| `signal_strings` | Sub-score do sinal strings |
| `signal_binwalk` | Sub-score do sinal binwalk |
| `hard_rule_applied` | Hard rule acionada (se alguma) |

## Estado Atual

**Dataset**: 305 firmwares, 6 vendors (dlink=103, netgear=80, openwrt=49, belkin=43, tplink=27, zyxel=3).

**CVE cache**: 157 pares vendor/model indexados em `dataset/cve_cache.json`.

**Sinais ativos**: `stats` + `cve` + `strings`.

**Sinais pendentes**: `binwalk` (parcial).

**Distribuicao atual** (stats + CVEs, sem strings/binwalk):

> Rodar `generate-labels --features dataset/processed/features.parquet --cves dataset/cve_cache.json --config configs/scoring.yaml --dry-run` para ver distribuicao atualizada.

**Distribuicao anterior** (so com stats, para referencia):

| Label | Count | % |
|---|---|---|
| seguro | 70 | 23.0% |
| vulneravel | 52 | 17.0% |
| critico | 183 | 60.0% |

## Proximos Passos

1. **Emitir `entropy_variance_across_sections` no pipeline** — Ja implementado em `src/features/statistics.py`, falta incluir no `pipeline/feature_extraction.py`.
3. **Integracao Binwalk** — Extrair filesystem type, crypto signatures, encrypted sections. Ativa o restante do sinal binwalk (peso 0.15).
4. **Calibracao de thresholds** — Apos todos os sinais ativos, ajustar thresholds no YAML para distribuicao desejada.
5. **Revisao manual** — Amostrar labels gerados e validar manualmente para garantir qualidade do ground truth.

## Arquivos Relacionados

| Arquivo | Descricao |
|---|---|
| `src/scoring.py` | Logica pura de scoring (sem I/O) |
| `configs/scoring.yaml` | Configuracao de thresholds, pesos e hard rules |
| `scripts/fetch_cves.py` | CLI para buscar CVEs na NVD API e gerar `cve_cache.json` |
| `scripts/generate_labels.py` | CLI para gerar `labels.csv` a partir de features + CVE cache |
| `dataset/cve_cache.json` | Cache de CVEs indexado por `"{brand}/{model}"` |
| `src/features/string_patterns.py` | Deteccao de padroes suspeitos nas strings ASCII |
| `tests/test_string_patterns.py` | Testes unitarios dos detectores de strings |
| `tests/test_scoring.py` | Testes cobrindo determinismo, hard rules, redistribuicao |

## Nota sobre Doc2Vec

Embeddings Doc2Vec **nao entram no scoring**. Sao input do ML (features numericas para o classificador), nao regras interpretaveis. O scoring usa apenas sinais com semantica clara e auditavel.
