# TODO

## Request: Analisar aplicabilidade de CVE por versão do firmware

### Completed
- [x] Confirmar que a extração atual remove o sufixo de versão do modelo.
- [x] Confirmar que o cache usa somente a chave fabricante/modelo.
- [x] Confirmar que a coleta descarta CVE, CPE e intervalos afetados após
      agregar contagens e CVSS.
- [x] Registrar no `docs/PIPELINE.md` o risco de rotular como vulnerável uma
      versão corrigida do mesmo modelo.
- [x] Preservar `meta_version` inferida do path fora do vetor de features.
- [x] Versionar as entradas do cache e guardar ID da CVE, critérios CPE,
      configurações e limites de versão.
- [x] Consultar CPE oficial antes da busca textual por fabricante/modelo.
- [x] Comparar versões com limites inclusivos e exclusivos.
- [x] Tratar como indeterminadas as CVEs sem comparação confiável de versão
      ou condição CPE.
- [x] Aplicar a regra C: unir aplicáveis e indeterminadas de todos os aliases
      e decidir o rótulo pelos limites inferior e superior.
- [x] Aplicar a normalização B1 a versões CPE exatas e limites.
- [x] Validar a regra C + B1 com 355 testes passando e conferir o dry-run
      sobre 840 linhas e 699 `firmware_id`.
- [x] Investigar o gap de sufixos de build, confirmar impacto zero no
      `labels_v2.csv` atual e recomendar a guarda por base numérica (opção B).
- [x] Implementar a guarda da opção B para CPE exata com sufixo: com a
      mesma base numérica e padding, build desconhecido ou qualificador extra
      fica indeterminado; build conhecido diferente e base distinta não se
      aplicam. Impacto zero no dataset atual.
- [x] Implementar a opção (b) do campo `update` da CPE: `update` literal com
      versão casando fica indeterminado. Corrige o falso positivo do
      TL-SG2008; `labels_v2.csv` regenerado (423/49/101/126 por
      `firmware_id`), 369 testes passando.
- [x] Registrar a origem de `meta_version` (`meta_version_source` no parquet e
      `version_source` no `labels_v2.csv`).
- [x] Extração relaxada de versão pelo nome do arquivo levada como trabalho
      futuro no TCC (documentada em `docs/PIPELINE.md`).
- [x] CPE da Belkin (`firmware_4.05.03`): decidido não corrigir; limitação
      documentada.

### Pending
- [ ] Trabalho futuro: avaliar evidência independente de versão para
      firmwares sem versão (+13 `firmware_id`); a regra de CVE sem
      `configurations` exige validação manual contra advisories.
- [ ] Excluir registros `indeterminado` do treino e reportar métricas e sua
      proporção por vendor.
- [ ] Verificar se os 23 arquivos `*webflash*` são imagens DD-WRT antes de
      atribuir versão.

## Request: Registrar ajuste pendente em docs/PIPELINE.md

### Completed
- [x] Confirmar o worktree que contém o `docs/PIPELINE.md` recriado.
- [x] Adicionar uma OBS sobre a separação entre ground truth CVE e baseline.
- [x] Sinalizar que `LEVEL_ORDER` pertence a `src/scoring.py`.
- [x] Explicar que o ground truth usa apenas CVE e que `LEVEL_ORDER` e hard
      rules pertencem ao baseline.
- [x] Corrigir a referência de `LEVEL_ORDER` em `docs/PIPELINE.md`.
- [x] Revisar `docs/PIPELINE.md` antes de publicar ou commitar.

### Pending
- [ ] None.

## Request: Retomar análise interrompida do Claude

### Completed
- [x] Recuperar e aceitar o handoff mais recente do ai-memory.
- [x] Confirmar que as hard rules de `src/scoring.py` afetam somente a
      previsão do baseline determinístico.
- [x] Confirmar que `scripts/generate_labels.py` gera o rótulo de treino
      exclusivamente com `cve_total` e `cvss_max` via
      `label_from_cve_stats()`.
- [x] Identificar que a seção "Escala de severidade" do `docs/PIPELINE.md`
      revertido misturava a explicação do baseline com a rotulagem CVE.

### Pending
- [ ] Manter explícita a separação entre baseline e ground truth caso
      `docs/PIPELINE.md` seja recriado.
- [ ] Decidir os nomes finais das três classes no texto do TCC.
- [ ] Avaliar a consolidação dos modelos duplicados entre `tplink/` e
      `tp_link/`.

## Request: Retomar o plano de classificação via CVE

### Completed
- [x] Conferir o handoff do ai-memory, os commits das tarefas 1–7 e o checkout.
- [x] Validar a suíte anterior à tarefa 8 (214 testes passaram).
- [x] Confirmar que `tests/test_cve_labels.py` falha na coleta sem `src.labeling`.
- [x] Resolver o escopo: seguir classificação via CVE e atualizar `AGENTS.md`.
- [x] Implementar rotulagem CVE, geração de labels e baseline sem sinal CVE.
- [x] Adicionar teste de guarda para CVE e identidade fora das features.
- [x] Atualizar `AGENTS.md`, `README.md` e `docs/SCORING.md`.
- [x] Revisar os commits das tarefas 8–14 com o Claude: aprovados, com uma
      correção em `tests/test_scoring.py` (nomes de teste e literais
      "seguro"/"vulneravel"/"critico" ainda espalhados no código, em vez de
      usar as constantes `LABEL_*` de `src/labeling/cve_labels.py`).

### Pending
- [ ] None.

## Request: Rodar extract-features e validar output gerado

### Completed
- [x] Rodar `extract-features` com `--findings-output` contra os 840 firmwares reais em `dataset/raw/`.
- [x] Validar schema do `features.parquet` gerado (133 colunas, sem vazamento de campo CVE, `meta_read_ok=True` em 840/840).
- [x] Validar `findings.jsonl` (3049 achados, correlacionáveis ao `features.parquet` por `firmware_id`).
- [x] Corrigir normalização de vendor `tp_link` para `tp-link` em `scripts/fetch_cves.py`: as 43 entradas `tp_link/*` já no cache retornavam 0 CVEs porque a busca na NVD usava o termo errado (`VENDOR_ALIASES` só tinha `tplink`, não `tp_link`).

### Pending
- [ ] Doc2Vec: `models/doc2vec.model` não existe (pasta `models/` nem existe). Rodar `train-doc2vec` antes da próxima extração. Hoje as 100 colunas `doc2vec_0`..`doc2vec_99` do `features.parquet` são todas zero (`meta_doc2vec_used=False` em 840/840).
- [ ] Re-rodar `fetch_cves.py --force` para os 43 pares `tp_link/*` já em cache. Foram buscados com o termo antigo antes da correção do alias, precisam ser refeitos antes de gerar labels confiáveis para esses firmwares.
- [ ] Detector `hardcoded_passwords` (`src/evidence/patterns.py`): 98,6% dos achados (1040/1055 no dataset real) são match de token avulso com alta taxa de falso positivo, ex. `" -- System halted"` (mensagem de kernel) contado como credencial por conter a palavra "system". Já sendo tratado em outra branch.
- [ ] `dataset/raw/tplink/` (grafia com underscore, ex. `tl_er604w`) e `dataset/raw/tp_link/` (grafia com hífen, ex. `tl-er604w`) parecem ter modelos em comum sob nomes diferentes. Só o vendor foi normalizado nesta correção, o nome do modelo não. Avaliar se vale consolidar.

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
- [ ] Implementar `scripts/train.py` com 4 modelos: Random Forest, Extra Trees,
      XGBoost e MLP. Fazer merge com `labels_v2.csv` por `firmware_id` e usar
      dele somente `security_level`; excluir `vendor`, `model`, `version`,
      `version_source`, `cve_total`, `cvss_max` e todas as colunas `meta_*`
      do parquet.
- [ ] Validar com `StratifiedGroupKFold` agrupado por modelo, após deduplicar
      por `firmware_id`, no lugar de `RepeatedStratifiedKFold` e LOOCV.
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

Registro histórico: o scoring deixou de gerar rótulos de treino. A rotulagem
atual usa somente CVEs; `src/scoring.py` é baseline de comparação.

### Completed
- [x] Criar `src/scoring.py` com weighted signals + hard rules (stats, cve, strings, binwalk).
- [x] Criar `configs/scoring.yaml` com thresholds, pesos e hard rules configuraveis.
- [x] Criar `scripts/generate_labels.py` com CLI (--features, --cves, --config, --output, --dry-run).
- [x] Adicionar entry point `generate-labels` em `pyproject.toml`.
- [x] Criar `tests/test_scoring.py` com 14 testes (determinismo, hard rules, redistribuicao de peso, fallback).
- [x] Mudar filtro de extensoes de allowlist para excludelist em `extract_features.py` (3 → 305 firmwares).
- [x] Extrair firmware de ZIPs e remover ZIPs sem firmware do dataset.
- [x] Re-extrair features para os 305 firmwares (6 vendors: dlink, netgear, openwrt, belkin, tplink, zyxel).
- [x] Gerar `dataset/labels_v2.csv` com o cache e as features v2 validados.

### Pending
- [ ] None.

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
