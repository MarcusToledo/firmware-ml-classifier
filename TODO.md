# TODO

## Request: Create/Improve AGENTS.md and establish TODO tracking

### Completed
- [x] Review existing `AGENTS.md` and `README.md` for current guidance and commands.
- [x] Update `AGENTS.md` with build/lint/test commands, code style guidelines, and TODO tracking rules.
- [x] Confirm no Cursor/Copilot rules are present and document that in `AGENTS.md`.

### Pending
- [ ] None.

## Request: Add pt-br only response rule

### Completed
- [x] Add rule requiring pt-br responses with only technical English terms in `AGENTS.md`.

### Pending
- [ ] None.

## Request: Persistir features extraidas

### Completed
- [x] Adicionar exportacao das features com metadados (parquet/csv) no CLI.
- [x] Renomear metadados de label para brand/model/label e ajustar inferencia.
- [x] Incluir meta_bytes_used e meta_max_bytes para rastrear limites aplicados.
- [x] Atualizar testes com novos metadados e flag label-from-path.

### Pending
- [ ] None.

## Request: Feature extraction skeleton

### Completed
- [x] Create feature extraction modules and functions for static features and Doc2Vec.
- [x] Add unit tests with pytest for statistics, strings, and io_utils.
- [x] Update string extraction with max_string_len and normalization.
- [x] Expand string extraction tests for limits and normalization.
- [x] Add compressibility level validation and logging.
- [x] Mark truncation when string or document limits apply.
- [x] Seed Doc2Vec inference for deterministic embeddings.
- [x] Reuse strings_to_document in feature extraction.
- [x] Add YAML-based pipeline config with overrides.
- [x] Add CLI entry for batch feature extraction.
- [x] Add pipeline tests for config, extraction, and CLI.
- [x] Add Doc2Vec unit tests with realistic tokens and determinism checks.
- [x] Add Doc2Vec training CLI script.

### Pending
- [ ] Adjust default limits (`max_strings`, `max_doc_chars`) after dataset profiling.

## Request: Remover duplicacao de utilitarios CLI

### Completed
- [x] Centralizar parse_overrides e gather_paths em `src/cli_utils.py`.
- [x] Atualizar scripts para reutilizar utilitarios CLI.

### Pending
- [ ] None.

## Request: Organizacao de imports

### Completed
- [x] Reordenar imports por grupo (stdlib/third-party/local) em arquivos relevantes.

### Pending
- [ ] None.

## Request: Configuracao e packaging

### Completed
- [x] Adicionar `pyproject.toml` com metadata, dependencias e entry points.
- [x] Criar pacote `scripts` para entry points.
- [x] Adicionar versoes minimas em `requirements.txt`.
- [x] Refatorar `scripts/inspect_tokens.py` para reutilizar utilitarios CLI.

### Pending
- [ ] None.

## Request: Documentacao de codigo

### Completed
- [x] Atualizar docstrings de funcoes publicas.
- [x] Adicionar secao API Interna no README.

### Pending
- [ ] None.

## Request: Consistencia de termos

### Completed
- [x] Ajustar README para incluir --output nos exemplos de extracao.
- [x] Alinhar descricao de features com o que o pipeline gera.
- [x] Atualizar descricao do projeto em pyproject.toml com acentos.

### Pending
- [ ] None.

## Request: Roadmap TCC — Pipeline completo de classificacao de seguranca

### Fase 1 — Pipeline Minimo Viavel (Mes 1-2)

#### Coleta e Rotulagem
- [x] Coletar 50+ firmwares de roteadores de pelo menos 5 fabricantes (D-Link, TP-Link, Netgear, Zyxel, Belkin).
- [x] Organizar firmwares em `dataset/raw/<vendor>/<model>/`.
- [x] Implementar `scripts/fetch_cves.py` para consultar NVD API (vendor+model → CVSS max + contagem por severidade).
- [x] Mover normalizacao de modelo (version suffix stripping) de `fetch_cves.py` para `feature_extraction.py`.
- [x] Corrigir lookup do CVE cache para usar `brand/model` em vez de `firmware_id`.
- [x] Migrar chaves Zyxel no `cve_cache.json` para nomes normalizados.
- [x] Criar `dataset/labels.csv` com colunas: firmware_id, vendor, model, cvss_max, cve_count, security_level.
- [x] Definir scoring deterministico para mapeamento automatico score → nivel de seguranca.
- [ ] Comecar com 3 classes (Seguro, Vulneravel, Critico); testar 5 classes se dataset > 150.
- [ ] Revisao manual dos rotulos gerados automaticamente.

#### Features — Binwalk
- [ ] Integrar Binwalk ao pipeline de extracao de features.
- [ ] Extrair features derivadas: `n_filesystems`, `n_crypto_signatures`, `has_encrypted_sections`, `entropy_variance_across_sections`.

#### Features — Strings suspeitas e bibliotecas
- [ ] Implementar regex patterns sobre strings existentes para detectar: hardcoded passwords, IPs, backdoors.
- [ ] Extrair versoes de bibliotecas (libssl, busybox, dropbear) via regex nas strings.
- [ ] Gerar features: `count_hardcoded_passwords`, `count_hardcoded_ips`, `has_telnetd`, `libssl_version_age`.

#### Treino e Avaliacao
- [ ] Implementar `scripts/train.py` com 4 modelos: Random Forest, Extra Trees, XGBoost, MLP.
- [ ] Implementar `RepeatedStratifiedKFold(n_splits=5, n_repeats=10)` como estrategia de validacao.
- [ ] Implementar LOOCV como validacao secundaria.
- [ ] Reportar macro F1-score, acuracia, confusion matrix normalizada e intervalo de confianca.
- [ ] Implementar split train/val/test com seeds fixos.
- [ ] Implementar geracao de relatorios em `reports/`.

#### Pre-processamento
- [ ] Aplicar `StandardScaler` ou `MinMaxScaler` nas features estatisticas (entropia, byte_mean, compress_ratio).
- [ ] Reduzir dimensionalidade do Doc2Vec: PCA para 10-20 componentes ou reduzir `vector_size` para 30.
- [ ] Treinar baseline com apenas 3 features estatisticas (sem Doc2Vec) para validar contribuicao.
- [ ] Comparar baseline vs baseline + Doc2Vec vs baseline + Doc2Vec + Binwalk features.

### Fase 2 — Enriquecimento de Features (Mes 3-4)

- [ ] Implementar deteccao de metadados ELF (arch, endianness, sections) com `pyelftools`.
- [ ] Avaliar integracao do Ghidra headless para grafo de chamadas e funcoes perigosas (strcpy, sprintf).
- [ ] Implementar ablation study (contribuicao de cada grupo de features).
- [ ] Implementar feature importance com SHAP ou built-in do RF/XGBoost.

### Fase 3 — Refinamento e Escrita (Mes 5-6)

- [ ] Experimentar com 5 classes se dataset > 150 amostras.
- [ ] Hyperparameter tuning com Optuna ou GridSearchCV.
- [ ] Gerar graficos e tabelas finais para o TCC.
- [ ] Escrever capitulo de metodologia e resultados.

## Request: Sistema de scoring deterministico para labels de treino

### Completed
- [x] Criar `src/scoring.py` com weighted signals + hard rules (stats, cve, strings, binwalk).
- [x] Criar `configs/scoring.yaml` com thresholds, pesos e hard rules configuraveis.
- [x] Criar `scripts/generate_labels.py` com CLI (--features, --cves, --config, --output, --dry-run).
- [x] Adicionar entry point `generate-labels` em `pyproject.toml`.
- [x] Criar `tests/test_scoring.py` com 14 testes (determinismo, hard rules, redistribuicao de peso, fallback).
- [x] Mudar filtro de extensoes de allowlist para excludelist em `extract_features.py` (3 → 305 firmwares).
- [x] Extrair firmware de ZIPs e remover ZIPs sem firmware do dataset.
- [x] Re-extrair features para os 305 firmwares (6 vendors: dlink, netgear, openwrt, belkin, tplink, zyxel).

### Pending
- [ ] Re-gerar labels apos implementar CVEs e strings para distribuicao mais equilibrada.

### Decisoes Arquiteturais Registradas
- Priorizar tree-based models (RF, Extra Trees) sobre MLP para datasets pequenos.
- MLP tende a overfitting com <200 amostras; manter como experimento comparativo.
- ISA tem baixo valor como feature para roteadores (quase sempre MIPS/ARM).
- Sequencia de ferramentas: Binwalk (Fase 1) → Regex strings (Fase 1) → pyelftools (Fase 2) → Ghidra (Fase 2).
- Nao reportar apenas acuracia; usar macro F1-score como metrica principal.
- Dataset atual: 305 firmwares de 6 vendors (dlink=103, netgear=80, openwrt=49, belkin=43, tplink=27, zyxel=3).
- Firmwares identificados como "data" pelo `file` com entropia >7.5 + `n_filesystems=0` + `compression_type=None` são padrão típico de firmware encriptado com formato proprietário. O scoring já captura esse padrão via `entropy_variance_across_sections`.
- OpenWrt retorna 0 CVEs na NVD (open-source, CVEs reportados contra chipsets/vendors originais) — substituir por Linksys.
- Usar class_weight='balanced' em todos os modelos sklearn para compensar desbalanceamento.
- Scoring atual (so stats): seguro=23%, vulneravel=17%, critico=60% — esperado rebalancear com CVE+strings.

## Request: Qualidade e ferramentas

### Completed
- [x] Adicionar ruff, black, mypy e pre-commit em pyproject.toml.
- [x] Criar .pre-commit-config.yaml com hooks.
- [x] Criar src/py.typed para PEP 561.
- [x] Atualizar README com secao de qualidade.

### Pending
- [ ] None.

## Request: Configurar debug Python no VS Code para arquivo atual

### Completed
- [x] Criar `.vscode/launch.json` com configuracao `Python: Arquivo atual` usando `${file}`.
- [x] Definir `cwd` como `${workspaceFolder}` e terminal integrado para execucao consistente.

### Pending
- [ ] None.
