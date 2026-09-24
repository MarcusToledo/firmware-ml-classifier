# Implementation Plan: Baseline determinístico de regras

**Branch**: `docs/specs-retroativas` | **Date**: 2026-09-24 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/006-baseline-regras/spec.md`

**Note**: plano retroativo. Descreve o código que já existe em `master`; não há Phase 0 (`research.md`), `contracts/` nem `quickstart.md`. O `tasks.md` é retroativo: registra a verificação de cada FR e cenário e as lacunas de teste.

## Summary

O baseline prevê uma das três classes a partir das features de um firmware,
por média ponderada de sub-scores de estatísticas, strings e Binwalk mais
hard rules que só elevam o nível, com parâmetros em YAML versionado e sem
nenhum campo de CVE. O papel dele no pipeline (comparação, nunca verdade)
está em `docs/PIPELINE.md`, §"4. Classificação e baseline".

## Technical Context

**Language/Version**: Python ≥ 3.9

**Primary Dependencies**: PyYAML

**Storage**: N/A (resultado em memória; nada é persistido)

**Testing**: pytest

**Target Platform**: Linux

**Project Type**: biblioteca (sem CLI nem entry point em `pyproject.toml`)

**Performance Goals**: sem meta definida

**Constraints**: nenhum campo de CVE nem de identidade na entrada usada;
parâmetros em `configs/scoring.yaml`

**Scale/Scope**: um firmware por chamada; nenhum script o executa sobre o
dataset hoje

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

|Princípio|Resultado|Evidência|
|---|---|---|
|I. Somente análise estática|Passa|O baseline só lê o dicionário de features já extraídas; não lê nem executa binário (`src/scoring.py::score_firmware`)|
|II. Rótulo exclusivamente por CVE|Passa|Nenhum script chama `score_firmware`: por grep em `**/*.py`, `src.scoring` só é importado por `tests/test_scoring.py`; `scripts/generate_labels.py` não o importa e rotula via `005-rotulagem-cve`|
|III. Sem vazamento|Passa|`tests/test_scoring.py::test_baseline_ignores_cve_fields`, `::test_baseline_has_no_cve_signal`; o baseline lê só as chaves listadas em FR-002 e FR-005|
|IV. Modelos simples|Não se aplica|Regras fixas sem aprendizado; o princípio II prevê o baseline|
|V. Reprodutibilidade|Passa parcialmente|Função pura, sem aleatoriedade (`tests/test_scoring.py::test_deterministic_same_inputs_same_result`); pesos, limiares e níveis das hard rules em `configs/scoring.yaml` (`::test_scoring_config_loads_without_cve_weight`). As constantes dos sub-scores ficam fixas em `src/scoring.py` (versionado), fora do YAML, e não há execução registrada via `logging`, porque nenhum script roda o baseline|
|VI. Firmware não confiável|Não se aplica|O baseline não lê binário. O tratamento de NaN como sinal presente é risco latente, registrado em Edge Cases|
|VII. Integridade científica|Passa|Todo FR tem módulo e teste abaixo ou aparece em "Sem verificação"; nenhum desempenho do baseline é afirmado; números medidos citam data e artefato|

## Project Structure

### Documentation (this feature)

```text
specs/006-baseline-regras/
├── spec.md                       # /speckit.specify + /speckit.clarify
├── plan.md                       # este arquivo
├── tasks.md                      # verificação retroativa
└── checklists/
    ├── requirements.md           # checklist de qualidade da spec
    └── rastreabilidade.md        # checklist de rastreabilidade e testabilidade
```

### Source Code (repository root)

```text
configs/
└── scoring.yaml        # thresholds, weights, hard_rules
src/
└── scoring.py          # sub-scores, média ponderada, limiares, hard rules, load_scoring_config

tests/
└── test_scoring.py
```

**Structure Decision**: estrutura de projeto único já existente. A fronteira
entre specs está no inventário `.docs/brainstorming/inventario-modulos.md`;
esta spec é dona só dos módulos acima. Os nomes das classes
(`LABEL_NO_KNOWN_CVE`, `LABEL_KNOWN_CVE`, `LABEL_CRITICAL_CVE`) são
importados de `src/labeling/cve_labels.py`, módulo de
`005-rotulagem-cve`; `LEVEL_ORDER` e `LEVEL_FROM_INT` ficam em
`src/scoring.py` e só o baseline os usa.

### US → FR → módulo → teste

|FR|US|Módulo|Teste|
|---|---|---|---|
|FR-001|US1|`src/scoring.py::score_firmware`, `ScoringResult`, `SignalResult`, `LEVEL_ORDER`|`test_scoring.py::test_baseline_uses_shared_class_names`, `::test_signals_breakdown_present`, `::test_no_signals_returns_no_known_cve`|
|FR-002|US1|`src/scoring.py::_score_stats`, `_score_strings`, `_score_binwalk`, `_sigmoid` e constantes `_ENCRYPTED_SCORE` … `_OUTDATED_LIB_SCORE`|`test_scoring.py::test_score_strings_outdated_libssl_raises_score`, `::test_score_strings_no_outdated_lib_zero`, `::test_score_strings_outdated_busybox_contributes`, `::test_score_strings_outdated_dropbear_contributes`, `::test_score_strings_passwords_contributes`, `::test_score_strings_combined_features`, `::test_score_strings_cred_pairs_contributes`, `::test_score_strings_public_ips_contributes`, `::test_binwalk_features_contribute`, `::test_n_filesystems_contributes_to_score` (parcial)|
|FR-003|US1, US4|`src/scoring.py::score_firmware`, `_score_stats`, `_score_strings`, `_score_binwalk`|`test_scoring.py::test_stats_only_redistributes_weight`, `::test_n_filesystems_zero_does_not_activate_binwalk_signal`, `::test_empty_features_returns_no_known_cve`, `::test_no_signals_returns_no_known_cve`, `::test_score_strings_no_features_absent`, `::test_score_strings_zero_new_counts_no_dilution` (parcial)|
|FR-004|US1|`src/scoring.py::score_firmware`, `ThresholdConfig`; `configs/scoring.yaml`|`test_scoring.py::test_high_score_maps_to_critical_cve`, `::test_low_risk_maps_to_no_known_cve`, `::test_custom_thresholds` (parcial)|
|FR-005|US3|`src/scoring.py::score_firmware`, `HardRuleConfig`, `LEVEL_ORDER`; `configs/scoring.yaml`|`test_scoring.py::test_hard_rule_telnetd_overrides_to_known_cve`, `::test_hard_rule_debug_account`, `::test_hard_rule_does_not_downgrade`, `::test_hard_rule_hardcoded_passwords` (parcial)|
|FR-006|US2|`src/scoring.py::score_firmware`|`test_scoring.py::test_baseline_ignores_cve_fields`, `::test_baseline_has_no_cve_signal`, `::test_no_signals_returns_no_known_cve` (parcial)|
|FR-007|US2|nenhum chamador de `src/scoring.py::score_firmware` no pipeline|—|
|FR-008|US1, US4|`src/scoring.py::load_scoring_config`, `ScoringConfig`, `ThresholdConfig`, `WeightConfig`, `HardRuleConfig`; `configs/scoring.yaml`|`test_scoring.py::test_scoring_config_loads_without_cve_weight` (parcial)|
|FR-009|US1|`src/scoring.py::score_firmware`|`test_scoring.py::test_deterministic_same_inputs_same_result` (parcial)|

### Sem verificação

Partes de FR sem teste que as exercite:

- FR-002: valores exatos das faixas e constantes (os testes só comparam
  maior/menor); `count_hardcoded_ips`, `entropy_variance_across_sections`
  e `compression_type` não aparecem em nenhum teste.
- FR-003: soma de pesos 0 com grupo presente e o consequente retorno antes
  da avaliação das hard rules.
- FR-004: inclusão exata dos valores de fronteira nos níveis definidos por
  `low` e `high`.
- FR-005: a regra `hardcoded_passwords`; o teste existente já obtém score
  0,375 (`cve_conhecida`) e não confere `hard_rule_applied`. Também faltam
  elevação a `cve_critica` por nível configurado e registro da última regra.
- FR-006: campos de identidade não alterarem o resultado.
- FR-007: ausência de chamadas ao baseline na geração de rótulos e nas
  demais etapas do pipeline.
- FR-008: valores exatos do YAML, subseção ou chave ausente usando o padrão
  e exceção para chave desconhecida.
- FR-009: igualdade do detalhamento e da hard rule entre repetições e
  determinismo entre processos; o teste atual compara apenas nível e score
  em duas chamadas no mesmo processo.

### Símbolos com requisito em outra spec

Nenhum.

## Complexity Tracking

|Requisito|Desvio observado no código atual|Tratamento|
|---|---|---|
|006/FR-003|NaN conta como valor presente e pode maximizar sub-scores ou ativar flags.|Defeito já registrado no `TODO.md`; a spec preserva o comportamento observado em Edge Cases.|
|006/FR-005|Sem grupo presente ou com soma de pesos 0, o retorno antecipado impede a avaliação das hard rules.|Defeito já registrado no `TODO.md`; FR-003 e FR-005 documentam a precedência atual.|
|006/FR-008|Pesos, limiares e níveis mínimos inválidos não são validados; YAML vazio produz `AttributeError` genérico.|Defeito já registrado no `TODO.md`; a validação fica fora desta mudança documental.|
