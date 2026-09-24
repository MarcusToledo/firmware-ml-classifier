# TODO

## Request: Estruturar requisitos e histórias de usuário do TCC no Spec Kit

### Completed
- [x] Avaliar a task do TickTick: Spec Kit como única fonte dos requisitos
      (sem `docs/requirements/`), RNF na constituição, status por spec/FR.
- [x] Reorganizar a task no TickTick em 5 subtasks com critério de aceite e
      separar a skill de Requirements Engineering para o OMP.
- [x] Mover o System Design para a última subtask: as specs planejadas mudam
      a arquitetura; o inventário de módulos que define as specs retroativas
      passa para a subtask das specs retroativas.
- [x] Subtask 1: `specify init` (1.0.9) no branch `docs/spec-kit-constitution`
      com `--integration generic --commands-dir .omp/commands/`. Testado no
      OMP headless: `/speckit.*` expande o template e substitui `$ARGUMENTS`.
      A integração `claude` (skills em `.claude/skills/`) não expande
      `/skill:speckit-*` no modo `-p`; descartada.
- [x] Subtask 1: rascunho da constituição v1.0.0 em
      `.specify/memory/constitution.md` (7 princípios, convenção de Status,
      referência `NNN/FR-###`, pt-br, slug ASCII via `--short-name`).
- [x] Subtask 1: `AGENTS.md` troca o Project Scope (Immutable) por
      `@.specify/memory/constitution.md`; import confirmado no OMP headless.
- [x] Review da constituição (revisão 1): famílias de features revistas com
      literatura (Costin 2014/2017, EMBER, FACT, EMBA); Doc2Vec avaliado com o
      oracle e rebaixado a variante experimental; regras de split agrupado,
      ajuste só no treino e baseline de identidade; modelos alternativos
      registrados no princípio IV; `docs/` deixa de ser fonte de verdade.
- [x] Confirmar que a inferência do Doc2Vec não é determinística: duas
      chamadas seguidas no mesmo modelo dão vetores diferentes e
      `Doc2VecConfig.seed` não altera a inferência (gensim usa `model.random`
      e `hash()`).
- [x] Tirar o Doc2Vec do núcleo e da entrega mínima (constituição,
      princípio I; `AGENTS.md`; `README.md`): o código fica, as colunas
      `doc2vec_*` não entram no modelo reportado.
- [x] TickTick: T06 marcado como `[Proposto]` (tag `proposto`, prioridade
      baixa, item de determinismo adicionado); subtask 4 exclui T06 e inclui
      T07.
- [x] TickTick: criada a T07 (limpar campos de feature não utilizados). No
      `features.parquet` atual, 105 das 120 colunas de feature são constantes
      em 840/840: `doc2vec_0..99` e 5 detectores de strings
      (`count_credential_pairs`, `has_telnetd`, `has_outdated_*`).
- [x] Constituição (revisão 2): só invariantes. Saíram o catálogo de features
      da literatura, a lista de modelos considerados, o nome do Doc2Vec e
      detalhes de implementação (nome do teste de guarda, semente em
      `configs/`, `model.random`). Relatórios salvos em
      `.docs/brainstorming/literatura-features-e-modelos.md` e
      `.docs/brainstorming/parecer-doc2vec-oracle.md`; subtask 4 no TickTick
      aponta para eles como fonte dos `research.md`.
- [x] Subtask 1: constituição v1.0.0 aprovada e ratificada em 2026-09-24;
      Sync Impact Report removido.
- [x] Subtask 2: inventário de módulos e fronteiras das specs em
      `.docs/brainstorming/inventario-modulos.md` (7 specs; utilitários sem
      spec justificados).
- [x] Subtask 2: spec piloto `specs/001-extracao-features/` (`spec.md`,
      clarify sem ambiguidades críticas, `plan.md`, `data-model.md`) na
      branch `docs/specs-retroativas`.
- [x] Subtask 2: specs retroativas 002–007 (spec, clarify, plan, data-model
      quando dono de artefato) na branch `docs/specs-retroativas`;
      referências entre specs no formato `NNN/FR-###`.
- [x] Clarify da 005: local canônico da tabela de rótulos decidido como
      `dataset/processed/labels_v2.csv`.

### Pending
- [ ] Alinhar o item de `scripts/train.py` do roadmap (4 modelos, com XGBoost
      e MLP) com o escopo do `AGENTS.md` (Extra Trees + Random Forest).
- [ ] T07: limpar os campos de feature não utilizados (Doc2Vec desligado por
      padrão sem gravar `doc2vec_*`; decidir os 5 detectores constantes;
      codificar `fs_type` e `compression_type`).
- [ ] Pós-entrega mínima — Doc2Vec (T06, Proposto): reiniciar `model.random` antes de cada `infer_vector`,
      exigir `PYTHONHASHSEED`, treinar por fold e rever
      `tests/test_doc2vec.py`, que segundo o oracle passa pelo motivo errado.
- [ ] Documento de strings: segundo medição do oracle (amostra de 40), as
      2000 primeiras strings (`max_strings`) cobrem ~3,7% dos bytes lidos e
      são cabeçalho mais ruído de payload comprimido; os detectores de
      `src/evidence/patterns.py` ficam quase cegos. Avaliar extração do
      filesystem desempacotado ou filtro de ruído.
- [ ] Pós-entrega mínima — `scripts/train_doc2vec.py` filtra por extensão e
      `scripts/extract_features.py` por exclusão: conjuntos de firmware
      diferentes entre treino e extração do Doc2Vec.
- [ ] `docs/SCORING.md` desatualizado: diz que o cache não filtra versão e
      usa `cve_cache.json`/`labels.csv` (v1).
- [ ] Roadmap: marcar como feitos a integração do Binwalk e os regex de
      strings, já implementados; `libssl_version_age` segue pendente.
- [ ] O baseline `score_firmware` não é chamado por nenhum script; falta
      rodá-lo sobre o dataset para comparar com os modelos.
- [ ] Validar as specs contra código e testes (matriz US → FR → módulo →
      teste) e registrar as lacunas de teste.
- [ ] Especificar T03, T04, T05, T06 e o treino de Extra Trees/Random Forest.
- [ ] Gerar o System Design a partir dos `plan.md` de todas as specs,
      separando componentes implementados e planejados.
- [ ] Binwalk ausente (log debug) ou encerrado com código de erro (sem log)
      gera features estruturais vazias sem registro no artefato
      (constituição, princípio VI), em
      `pipeline/feature_extraction.py::_extract_binwalk_descriptions`.
- [ ] `max_bytes=5 MiB` corta 696/840 arquivos, e as features estatísticas
      veem 23,3% dos bytes do dataset. Avaliar leitura completa em streaming,
      com `max_bytes` alto para cumprir o princípio VI: bincount
      incremental, `zlib.compressobj`, variância por bloco e strings com
      parada em `max_strings`. Exige reextrair e regerar os rótulos, porque o
      `firmware_id` muda. A implementação atual carrega o arquivo inteiro na
      memória: processar o arquivo de 150,9 MiB inteiro foi morto por OOM
      nesta máquina (7,9 GB). Nenhuma coluna guarda o tamanho original do
      arquivo (`meta_byte_len` = bytes lidos).
- [ ] `firmware_id` é o SHA256 do prefixo de `max_bytes` (0 colisões
      medidas em 2026-09-24). Avaliar trocar pelo SHA256 do arquivo
      completo, com leitura sequencial e memória constante.
- [ ] `scripts/validate_dataset.py` desatualizado para `labels_v2.csv`: lê o
      `labels.csv` v1, compara paths relativos e acusa como duplicata o
      `firmware_id` compartilhado por aliases.
- [ ] `docs/PIPELINE.md`: diz "8 detectores" em `patterns.py` (são 11) e
      chama o módulo de `stats.py` (é `statistics.py`).
- [ ] Docstring de
      `tests/test_pipeline_extraction.py::test_error_result_preserves_version_from_path`
      diz que o path inexistente faz `read_binary` levantar exceção e
      exercita o ramo de erro de `_process_path`, mas `read_binary` engole o
      `OSError` e o teste passa pelo caminho `empty firmware`.
- [ ] Mover `labels_v2.csv` para `dataset/processed/labels_v2.csv`, trocar o
      `--output` padrão de `scripts/generate_labels.py` (hoje o v1
      `dataset/labels.csv`) e registrar `--critical-cvss` e as entradas
      (constituição, princípio V; decisão do clarify da 005).
- [ ] 002: `debug_account` casa qualquer palavra inteira debug/guest/test,
      em `src/evidence/patterns.py::_DEBUG_ACCOUNT_RE`. Medido em 2026-09-24
      no `findings_v2.jsonl`: 128 dos 199 achados são "test", de mensagens
      de bootloader (ex.: "mtest - simple RAM test").
- [ ] 002: `api_tokens` aceita qualquer sequência de 32+ caracteres de
      `[A-Za-z0-9+/=_-]`, em `src/evidence/patterns.py::_API_TOKEN_RE`.
      Medido em 2026-09-24: 1121 dos 1128 achados não são hexadecimais
      (nomes de configuração, alfabetos, paths de build).
- [ ] 002: os detectores de IP casam versões com 4 partes, em
      `src/evidence/patterns.py::_IPV4_RE` (`find_public_ips`,
      `find_hardcoded_ips`). Medido em 2026-09-24: os 39 `public_ips` vêm de
      textos de versão ("7.0.1.0" 23x); a máscara 255.255.255.0 aparece 11x
      como `hardcoded_ips`.
- [ ] 002: "AES" casa as tabelas de código "AES S-Box", em
      `src/evidence/binwalk_findings.py::_ENCRYPTED_RE`/`_CRYPTO_RE`.
      Medido em 2026-09-24: 137 dos 171 achados de `encrypted_sections` são
      essas tabelas, único motivo em 8 dos 17 paths com
      `has_encrypted_sections=True`; a mesma descrição gera achado nos dois
      detectores.
- [ ] 002: Dropbear antigo no formato 0.NN (ex.: "Dropbear 0.52") não casa,
      em `src/evidence/patterns.py::_DROPBEAR_RE` (exige ano `\d{4}\.\d+`).
- [ ] 002: `detector_version` é a constante "1.0" por módulo e não muda com a
      regra, em `src/evidence/patterns.py::_DETECTOR_VERSION` e
      `src/evidence/binwalk_findings.py::_DETECTOR_VERSION` (princípio V):
      portar a correção de `hardcoded_passwords` manteria a mesma versão.
- [ ] 002: teste passa por construção, em
      `tests/test_evidence_patterns.py::test_findings_to_counts_matches_scan_strings`:
      `scan_strings` é a própria expressão comparada (`patterns.py` L524).
- [ ] 003: `main()` sem teste (pulo de cache, schema, `--force`, falha de
      rede, gravação, `--dry-run`, `--delay`, `NVD_API_KEY`), em
      `scripts/fetch_cves.py::main`; `tests/test_fetch_cves.py` importa só
      funções auxiliares.
- [ ] 003: busca de CVE sem comando instalado, em `pyproject.toml`
      `[project.scripts]` (L31-35 não têm `fetch-cves`).
- [ ] 003: `--output` padrão aponta para o cache v1, em
      `scripts/fetch_cves.py::main` (L321): sem `--force` aborta com
      "Cache CVE em schema antigo"; com `--force` mistura esquemas (26
      entradas v1 ficam). `README.md` L62/L68 usam os caminhos v1. Medido em
      2026-09-24: `dataset/cve_cache.json` com 336 entradas v1.
- [ ] 003: com `--force`, falha de rede mantém a entrada antiga sem marca e
      a execução sai com código 0, em `scripts/fetch_cves.py::main` (o
      `except` só loga).
- [ ] 003: sem nova tentativa/backoff para 403/503 da NVD, e JSON inválido
      ou `IncompleteRead` abortam a execução, em
      `scripts/fetch_cves.py::main`/`_fetch_page`/`_fetch_cpe_page` (`except`
      restrito a `URLError`/`HTTPError`/`TimeoutError`).
- [ ] 003: parquet sem `--label-from-path` gera 0 pares e sai sem erro;
      linhas com brand/model nulo são descartadas sem contagem no log, em
      `scripts/fetch_cves.py::extract_pairs`.
- [ ] 003: resolução de CPE lê só a primeira página (até 2000 produtos),
      aceita só a parte `o` e pega o primeiro match, em
      `scripts/fetch_cves.py::resolve_cpe_name`/`_fetch_cpe_page`; produto
      só `h` cai na busca por texto.
- [ ] 003: `cvss_max` por CVE é o baseScore da primeira métrica, não o
      máximo entre fontes; v2 sem `baseSeverity` vira MEDIUM, em
      `scripts/fetch_cves.py::extract_cvss`.
- [ ] 003: entradas do cache não registram a data da consulta à NVD
      (princípio V), em `scripts/fetch_cves.py::fetch_cves_for_pair`.
- [ ] 003: docstring diz "lowercase bucket name", mas a função devolve
      maiúsculas, em `scripts/fetch_cves.py::severity_bucket`.
- [ ] 004: arquivo direto em `raw/<fabricante>/arquivo` vira modelo e label
      `<fabricante>_<arquivo>` em vez de identidade nula (fallback
      silencioso, princípio VI), em
      `pipeline/feature_extraction.py::infer_brand_model_label_from_path`
      (L85). Medido em 2026-09-24: 0 casos no `features_v2.parquet`.
- [ ] 004: usa o primeiro segmento `raw` do path, sem distinção de
      maiúsculas; um `raw` acima de `dataset/` desviaria a identidade sem
      aviso, em
      `pipeline/feature_extraction.py::infer_brand_model_label_from_path`
      (L79-82). Latente: 840/840 `meta_path` reproduzidos.
- [ ] 004: versão do diretório gravada crua (ex.: `7.10(ABTG.4)C0`), sem a
      normalização das regras de nome de arquivo, e conflito com a versão
      do nome não registrado, em
      `pipeline/feature_extraction.py::_split_model_version` (L67-69).
      Impacto atual nulo: 0 linhas `directory` (medido em 2026-09-24).
- [ ] 005: `meta_version_source` do parquet não é lido nem conferido contra
      o reinferido, em `scripts/generate_labels.py::ID_COLUMNS`; o
      `features_v2.parquet` atual nem tem a coluna (medido em 2026-09-24).
- [ ] 005: lacunas de teste da rotulagem (`--dry-run`, logs,
      `--critical-cvss` via CLI, entrada parquet, tabela vazia, CPE versão
      "-", `negate`, alvo por `cpe_name`, CVE sem ID), em
      `tests/test_generate_labels.py`, `tests/test_cve_labels.py` e
      `tests/test_version_match.py`.
- [ ] 005: `docs/PIPELINE.md` §3 (L163-165) cita `labels.csv`; o artefato
      atual é `labels_v2.csv`.
- [ ] 006: NaN conta como sinal presente, em
      `src/scoring.py::_score_stats`/`_score_strings`/`score_firmware`:
      estatística NaN vira sub-score máximo e `has_*` NaN conta como
      verdadeiro. Verificado em 2026-09-24: tudo NaN → `cve_critica`, score
      0,6417. Latente (sem chamador; 840/840 `meta_read_ok=True`).
- [ ] 006: hard rules puladas sem grupo presente ou com soma de pesos 0, em
      `src/scoring.py::score_firmware` (retorno antecipado). Verificado:
      `{"has_telnetd": True}` dá `sem_cve_conhecida`, regra None.
- [ ] 006: configuração sem validação, em
      `src/scoring.py::HardRuleConfig`/`load_scoring_config`: nível mínimo
      fora das três classes é aceito e a regra nunca dispara; `low > high` e
      pesos negativos passam; YAML vazio dá `AttributeError` genérico.
- [ ] 006: teste passa pelo motivo errado, em
      `tests/test_scoring.py::test_hard_rule_hardcoded_passwords`: o score já
      é 0,375 sem a regra e `hard_rule_applied=None` (verificado em
      2026-09-24); a regra `hardcoded_passwords` fica sem teste.
- [ ] 006: `docs/SCORING.md` diz que os parâmetros estão em
      `configs/scoring.yaml`, mas as constantes dos sub-scores são fixas em
      `src/scoring.py`; a linha do Binwalk omite
      `entropy_variance_across_sections` e `n_filesystems`.
- [ ] 006: `src/scoring.py::score_firmware` registra só a última hard rule
      que elevou o nível; `has_telnetd`/`has_debug_account` não entram no
      sub-score de strings; `count_urls`/`count_api_tokens` não entram no
      baseline (`_score_strings`).
- [ ] 007: `meta_doc2vec_used=True` mesmo quando o documento não tem tokens
      e o vetor sai zero, em
      `pipeline/feature_extraction.py::extract_features_from_path` (L295) e
      `src/feature_extraction.py::extract_features` (L72-76).
- [ ] 007: dimensão do modelo carregado não é conferida contra
      `doc2vec.vector_size`, em `src/feature_extraction.py::extract_features`
      (L73-76): linhas podem ter números diferentes de colunas; a inferência
      usa epochs/alpha da config de extração, não os do treino.
- [ ] 007: corpus de treino repete aliases, em
      `scripts/train_doc2vec.py::build_documents`. Medido em 2026-09-24: 774
      candidatos, 633 `firmware_id` distintos, 215 linhas compartilham
      `firmware_id` com a mesma tag.
- [ ] 007: ordem do corpus depende do sistema de arquivos, em
      `src/cli_utils.py::gather_paths` (L36, `rglob` sem sort). [INFERENCE:
      o treino é sensível à ordem; não medido]
- [ ] 007: o modelo não grava os limites do corpus (`max_bytes`,
      `feature.*`) e não há artefato de embeddings alinhado a `firmware_id`
      (`AGENTS.md`, princípio V), em `scripts/train_doc2vec.py::main` e
      `src/features/doc2vec.py::save_doc2vec`. `PYTHONHASHSEED` já está na
      T06.
- [ ] 007: só `workers` é validado em
      `src/features/doc2vec.py::train_doc2vec`; a extração lê
      `doc2vec.workers` e o ignora
      (`pipeline/feature_extraction.py::load_pipeline_config`).
- [ ] 007: `scripts/train_doc2vec.py` e `scripts/inspect_tokens.py` sem
      teste; nenhum teste de extração confere `doc2vec_*` nem
      `meta_doc2vec_used=True`.

## Request: Responder o review do Kody no PR #5

### Completed
- [x] Responder as threads do Kody e resolver as já atendidas.
- [x] Marcar como pendentes a escolha dos modelos e a centralização das
      regras de normalização de `scripts/fetch_cves.py`.

### Pending
- [ ] Rodar a detecção de strings e do Binwalk uma única vez em
      `pipeline/feature_extraction.py`: derivar as contagens de
      `scan_strings_findings` com `findings_to_counts` e de
      `find_crypto_signatures`/`find_encrypted_sections`, em vez de chamar
      os detectores de novo. Corrigir o comentário "sem rodar deteccao duas
      vezes". PR separado; o resultado das features não muda.
- [ ] Portar para `src/evidence/patterns.py` a correção de
      `hardcoded_passwords` feita no #4 (`src/features/string_patterns.py`).

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
- [x] Re-busca dos 43 pares `tp_link/*`: obsoleto para o `cve_cache_v2.json`,
      cujas 43 entradas já têm `vendor="tp-link"` (medido em 2026-09-24); o
      problema vale só para o cache v1.

### Pending
- [ ] Pós-entrega mínima — Doc2Vec: `models/doc2vec.model` não existe (pasta `models/` nem existe). Hoje as 100 colunas `doc2vec_0`..`doc2vec_99` do `features.parquet` são todas zero (`meta_doc2vec_used=False` em 840/840); ficam fora do vetor do modelo reportado (constituição, princípio I).
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
- [ ] Pós-entrega mínima — Reduzir dimensionalidade do Doc2Vec: PCA para 10-20 componentes ou reduzir `vector_size` para 30.
- [ ] Treinar baseline com apenas as features estatisticas para validar contribuicao.
- [ ] Comparar baseline vs baseline + strings vs baseline + strings + Binwalk features; Doc2Vec só entra depois da entrega mínima.

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
