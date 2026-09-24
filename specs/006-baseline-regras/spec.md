# Feature Specification: Baseline determinístico de regras

**Feature Branch**: `docs/specs-retroativas`

**Created**: 2026-09-24

**Status**: Implementado

**Input**: User description: "Spec retroativa (Status Implementado) do baseline determinístico de regras fixas: média ponderada de sinais estatísticos, de strings e do Binwalk mais hard rules que só elevam o nível, configurada em YAML versionado. Serve só como referência de comparação com os modelos e nunca gera rótulo de treino. Derivar só do código em master, testes, docs/SCORING.md, docs/PIPELINE.md e TODO.md."

## Clarifications

### Session 2026-09-24

- Varredura de ambiguidade (`/speckit.clarify`): sem ambiguidades
  críticas. Por ser spec retroativa, cada FR descreve o comportamento do
  código em `master`. Os nomes finais das três classes no texto do TCC e a
  execução do baseline sobre o dataset são decisões já registradas no
  `TODO.md`, não escolhas desta spec. Nenhuma pergunta feita.
- Terminologia: "nível" é a classe prevista pelo baseline; "rótulo" é só o
  ground truth por CVE de `005-rotulagem-cve` (005/FR-012 e 005/FR-013).
  Os dois usam os mesmos nomes de classe, mas nunca se misturam.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Previsão determinística para comparação (Priority: P1)

O pesquisador passa as features de um firmware e a configuração do baseline
e recebe um nível previsto, um score numérico, a contribuição de cada grupo
de sinais e a hard rule aplicada, se houver.

**Why this priority**: o baseline é a referência sem aprendizado contra a
qual Extra Trees e Random Forest serão comparados (constituição, princípios
II e IV).

**Independent Test**: calcular o baseline para um conjunto de features de
risco alto, um de risco baixo e um vazio, e conferir nível e score.

**Acceptance Scenarios**:

1. **Given** features sem nenhum sinal reconhecido (ou vazias), **When** o
   baseline é calculado, **Then** o nível é `sem_cve_conhecida`, o score é
   0 e nenhuma hard rule é aplicada.
2. **Given** `entropy=7.99`, `compress_ratio=0.999`,
   `count_hardcoded_passwords=5`, `has_outdated_libssl=True` e
   `has_encrypted_sections=True`, **When** o baseline é calculado, **Then**
   o score é ≥ 0,60 e o nível é `cve_critica`.
3. **Given** `entropy=5.0`, `byte_mean=127.5` e `compress_ratio=0.60`,
   **When** o baseline é calculado, **Then** o score é < 0,20 e o nível é
   `sem_cve_conhecida`.
4. **Given** as mesmas features e a mesma configuração, **When** o baseline
   é calculado duas vezes, **Then** nível, score, detalhamento e hard rule
   aplicada são idênticos.
5. **Given** limiares `low=0.10` e `high=0.30`, **When** o baseline é
   calculado para `entropy=7.5` e `compress_ratio=0.90`, **Then** o nível é
   `cve_conhecida` ou `cve_critica`.
6. **Given** features cujo score é exatamente igual a um limiar, **When**
   o baseline é calculado, **Then** o limite `low` pertence a
   `cve_conhecida` e o limite `high` pertence a `cve_critica`.
7. **Given** as mesmas features e a mesma configuração em dois processos
   separados, **When** cada processo calcula o baseline, **Then** os
   resultados completos são idênticos.

---

### User Story 2 - Baseline sem sinal de CVE (Priority: P1)

A banca audita que o baseline não usa nenhum campo derivado de CVE e que
sua saída não vira rótulo de treino.

**Why this priority**: se o baseline lesse CVE, a comparação com os modelos
mediria a fórmula do rótulo, não o conteúdo do binário (constituição,
princípios II e III).

**Independent Test**: calcular o baseline com e sem `cvss_max` e
`cve_count_critical` nas features e comparar os resultados.

**Acceptance Scenarios**:

1. **Given** features com `entropy=7.5` e `compress_ratio=0.9`, **When**
   são acrescentados `cvss_max=10.0` e `cve_count_critical=10`, **Then**
   nível, score e hard rule aplicada não mudam.
2. **Given** qualquer entrada, **When** o baseline é calculado, **Then** o
   detalhamento tem exatamente três grupos: `stats`, `strings` e `binwalk`.
3. **Given** features reconhecidas, **When** são acrescentados campos de
   identidade (`meta_brand`, `meta_model` e `meta_version`), **Then** nível,
   score, detalhamento e hard rule aplicada não mudam.
4. **Given** o pipeline de geração de rótulos de treino, **When** suas
   dependências são auditadas, **Then** nenhuma delas chama o baseline.

---

### User Story 3 - Hard rules só elevam o nível (Priority: P2)

O pesquisador marca certos indicadores (telnetd, conta de debug, senha
hardcoded) como suficientes para um nível mínimo, sem que eles rebaixem uma
previsão mais grave.

**Why this priority**: são sinais de alto risco que a média ponderada
dilui; a regra precisa ser explícita e auditável no resultado.

**Independent Test**: calcular o baseline para features de score baixo com
`has_telnetd=True` e para features de score alto com `has_telnetd=True`.

**Acceptance Scenarios**:

1. **Given** features de score baixo e `has_telnetd=True`, **When** o
   baseline é calculado, **Then** o nível é pelo menos `cve_conhecida` e a
   regra aplicada é `has_telnetd`.
2. **Given** features de score baixo e `has_debug_account=True`, **When** o
   baseline é calculado, **Then** o nível é pelo menos `cve_conhecida` e a
   regra aplicada é `has_debug_account`.
3. **Given** features que já levam a `cve_critica` e `has_telnetd=True`,
   **When** o baseline é calculado, **Then** o nível continua
   `cve_critica`.
4. **Given** features de score baixo, `count_hardcoded_passwords=1` e peso
   0 para o grupo `strings`, **When** o baseline é calculado, **Then** o
   nível é pelo menos `cve_conhecida` e a regra aplicada é
   `hardcoded_passwords`.
5. **Given** `has_telnetd=True` e nível mínimo configurado como
   `cve_critica`, **When** o baseline é calculado para features de score
   baixo, **Then** o nível é `cve_critica`.
6. **Given** duas hard rules que elevam o nível em sequência, **When** o
   baseline é calculado, **Then** o resultado registra a última regra que
   elevou o nível.

---

### User Story 4 - Configuração versionada e grupos ausentes (Priority: P2)

O pesquisador ajusta pesos, limiares e hard rules num YAML versionado, e um
grupo de sinais ausente não puxa o score para baixo.

**Why this priority**: parâmetros de execução vêm de configuração
versionada (constituição, princípio V), e features ausentes não podem
contar como risco zero.

**Independent Test**: carregar `configs/scoring.yaml` e calcular o baseline
com só as features estatísticas.

**Acceptance Scenarios**:

1. **Given** `configs/scoring.yaml`, **When** a configuração é carregada,
   **Then** o baseline calcula com os três grupos e nenhum peso de CVE.
2. **Given** só `entropy`, `byte_mean` e `compress_ratio`, **When** o
   baseline é calculado, **Then** só o grupo `stats` está presente, os
   outros dois têm peso 0 e o score é maior que 0.
3. **Given** `n_filesystems=0` e nenhum outro sinal do Binwalk, **When** o
   baseline é calculado, **Then** o grupo `binwalk` não está presente.
4. **Given** uma configuração cuja seção `scoring` omite uma subseção ou
   chave, **When** a configuração é carregada, **Then** o valor padrão
   correspondente é usado.
5. **Given** uma configuração com chave desconhecida numa subseção de
   `scoring`, **When** a configuração é carregada, **Then** o carregamento
   é interrompido com exceção.

---

### Edge Cases

- Nenhum script do pipeline chama o baseline: não há CLI, artefato nem
  resultado sobre o dataset. Falta rodá-lo para comparar com os modelos;
  registrado no `TODO.md`.
- Os nomes finais das três classes no texto do TCC estão pendentes
  (`TODO.md`). O baseline usa hoje os nomes `sem_cve_conhecida`,
  `cve_conhecida` e `cve_critica`, os mesmos de `security_level` em
  `005-rotulagem-cve` (005/FR-013). Os nomes são iguais, mas o sentido
  não: o baseline não consulta CVE, e `sem_cve_conhecida` previsto por ele
  não prova ausência de vulnerabilidade. O baseline nunca prevê
  `indeterminado`, que na rotulagem é estado de qualidade (005/FR-012 e
  005/FR-013); a comparação precisa excluir essas linhas.
- `docs/SCORING.md` está desatualizado (cache sem filtro de versão,
  `cve_cache.json`/`labels.csv` v1); registrado no `TODO.md`. O documento
  também diz que os parâmetros estão em `configs/scoring.yaml`, mas só
  pesos, limiares e níveis mínimos das hard rules estão lá; as constantes
  dos sub-scores (faixas lineares, sigmoides, 0,6 por biblioteca
  desatualizada, 0,8 por seção cifrada etc.) são fixas no código.
- Valor ausente representado como NaN (célula nula numa tabela) não é
  tratado como ausente: o grupo conta como presente, NaN numa feature
  estatística vira sub-score máximo e NaN numa flag conta como verdadeiro.
  Features estatísticas, `has_outdated_libssl`, `has_telnetd` e
  `count_hardcoded_passwords` todas em NaN resultam em `cve_critica` (score
  0,64). Hoje o risco é latente: nenhum script chama o baseline e
  `features_v2.parquet` tem 840/840 linhas com `meta_read_ok=True`.
- Sem nenhum grupo presente, ou com os três pesos em 0, o baseline devolve
  `sem_cve_conhecida` sem avaliar as hard rules. Features só com
  `has_telnetd=True` (sem nenhum sinal dos três grupos) saem
  `sem_cve_conhecida`, sem regra aplicada.
- Um nível mínimo de hard rule que não seja uma das três classes (ex.:
  `critico`) é aceito ao carregar a configuração e a regra nunca dispara,
  sem erro nem aviso. Os limiares e pesos também não são validados (ex.:
  `low > high`, peso negativo).
- YAML vazio falha com erro genérico (`AttributeError`), não com mensagem
  de configuração inválida. Chave desconhecida numa seção falha com
  `TypeError`.
- Quando mais de uma hard rule eleva o nível, o resultado registra só a
  última que elevou.
- `has_telnetd` e `has_debug_account` só entram nas hard rules, não no
  sub-score de strings; `count_urls` e `count_api_tokens` não entram no
  baseline.
- Alcance das hard rules no dataset (medido em 2026-09-24 sobre
  `features_v2.parquet`, 840 linhas): `has_telnetd` é falso em 840/840,
  `has_debug_account` é verdadeiro em 47 e `count_hardcoded_passwords > 0`
  em 141. O detector de senha hardcoded tem alta taxa de falso positivo
  (`TODO.md`, detector `hardcoded_passwords`), e a hard rule herda esse
  ruído. Os detectores constantes são tratados em T07 (subtask 4).
- Os pesos e limiares são hipóteses heurísticas, não ajustadas nem
  validadas empiricamente neste TCC.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001** [Implementado]: O sistema DEVE receber as features de um
  firmware, pelos nomes de coluna de `001-extracao-features`, e uma
  configuração, e DEVE devolver: um nível entre `sem_cve_conhecida`,
  `cve_conhecida` e `cve_critica` (nessa ordem de gravidade); um score
  numérico entre 0 e 1 (com pesos não negativos); o detalhamento dos grupos
  `stats`, `strings` e `binwalk` (sub-score, peso efetivo, presença e texto
  de detalhe); e o nome da hard rule aplicada, ou nulo. Chaves de feature
  desconhecidas DEVEM ser ignoradas.
- **FR-002** [Implementado]: O sistema DEVE calcular cada sub-score entre 0
  e 1 como a média das partes disponíveis do grupo:
  - `stats` (features de `001/FR-005`): `entropy` linear de 6 a 8 bits,
    `compress_ratio` linear de 0,80 a 1,0 e o desvio de `byte_mean` em
    relação a 127,5, multiplicado por 0,3;
  - `strings` (features de `001/FR-008`): `count_hardcoded_passwords`,
    `count_credential_pairs`, `count_hardcoded_ips` e `count_public_ips`
    por sigmoide, só quando maiores que 0; `has_outdated_libssl`,
    `has_outdated_busybox` e `has_outdated_dropbear` valem 0,6 quando
    verdadeiros e 0 quando falsos;
  - `binwalk` (features de `001/FR-005`, `001/FR-007` e `001/FR-008`):
    `has_encrypted_sections` 0,8; `n_crypto_signatures` saturando em 5, com
    fator 0,5; `entropy_variance_across_sections` saturando em 3; `fs_type`
    `cramfs`/`jffs2` 0,4; `compression_type` `gzip` 0,2; `n_filesystems`
    maior que 0 saturando em 3, com fator 0,3.
- **FR-003** [Implementado]: Um grupo DEVE contar como presente quando ao
  menos uma de suas features tem valor (para `n_filesystems`, valor maior
  que 0). O score DEVE ser a média dos sub-scores ponderada pelos pesos
  configurados dos grupos presentes; grupo ausente DEVE ter peso 0. Sem
  grupo presente (ou com soma de pesos 0), o sistema DEVE devolver score 0
  e `sem_cve_conhecida`, sem hard rule.
- **FR-004** [Implementado]: O sistema DEVE mapear o score para o nível por
  dois limiares: abaixo de `low` é `sem_cve_conhecida`; de `low` até abaixo
  de `high` é `cve_conhecida`; a partir de `high` é `cve_critica`. Os
  valores versionados são `low` 0,20 e `high` 0,60.
- **FR-005** [Implementado]: Quando houver ao menos um grupo presente e a
  soma dos pesos for diferente de 0, o sistema DEVE aplicar três hard rules
  depois do mapeamento: `has_telnetd` verdadeiro,
  `has_debug_account` verdadeiro e `count_hardcoded_passwords` maior que 0.
  Cada uma DEVE elevar o nível ao mínimo configurado (`cve_conhecida` na
  configuração versionada) só quando ele é mais grave que o nível atual, e
  NÃO DEVE rebaixar o nível. O resultado DEVE registrar o nome da última
  regra que elevou o nível (`has_telnetd`, `has_debug_account` ou
  `hardcoded_passwords`). Sem grupo presente ou com soma de pesos 0,
  prevalece o retorno sem hard rule de FR-003.
- **FR-006** [Implementado]: O baseline NÃO DEVE ler campos derivados de
  CVE (`cvss_max`, `cve_total`, `cve_count_*`) nem de identidade: o
  resultado só depende das features listadas em FR-002 e das três flags
  das hard rules.
- **FR-007** [Implementado]: O baseline NÃO DEVE gerar rótulo de
  treino: nenhuma etapa do pipeline grava sua previsão, e a rotulagem de
  `005-rotulagem-cve` não o consulta (005/FR-014).
- **FR-008** [Implementado]: O sistema DEVE ler pesos (`stats` 0,10,
  `strings` 0,30, `binwalk` 0,15), limiares e níveis mínimos das hard rules
  da seção `scoring` de um YAML versionado (`configs/scoring.yaml`), nas
  subseções `thresholds`, `weights` e `hard_rules`. Subseção ou chave
  ausente DEVE usar o valor padrão, igual ao versionado. Chave desconhecida
  numa subseção DEVE interromper o carregamento com exceção.
- **FR-009** [Implementado]: O baseline DEVE ser determinístico: as mesmas
  features e a mesma configuração DEVEM gerar o mesmo nível, score,
  detalhamento e hard rule, sem estado aleatório, inclusive em processos
  separados e independentemente da ordem de execução.

### Key Entities *(include if feature involves data)*

- **Features de um firmware**: dicionário com as colunas de feature de
  `001-extracao-features` para um arquivo. Entrada do baseline.
- **Configuração do baseline**: limiares `low`/`high`, pesos por grupo e
  nível mínimo de cada hard rule, vindos de `configs/scoring.yaml`.
- **Resultado do baseline**: nível previsto, score numérico, detalhamento
  por grupo e hard rule aplicada. Não é persistido e não é rótulo.
- **Nível**: uma das três classes `sem_cve_conhecida`, `cve_conhecida` e
  `cve_critica`, ordenadas por gravidade.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% das repetições com as mesmas features e configuração
  dão o mesmo nível, score, detalhamento e hard rule aplicada.
- **SC-002**: acrescentar campos de CVE ou identidade às features muda zero
  resultados (nível, score, detalhamento e hard rule).
- **SC-003**: zero casos em que uma hard rule deixa o nível menos grave que
  o do score.
- **SC-004**: zero chamadas ao baseline na geração de rótulos de treino.

## Assumptions

- O baseline é referência de comparação, não ground truth (constituição,
  princípio II). O rótulo de treino segue `005-rotulagem-cve` (005/FR-012
  e 005/FR-013).
- As features de entrada seguem os nomes de `001-extracao-features`; as
  contagens e flags de strings e as features de assinatura do Binwalk vêm
  de `002-evidencias-seguranca` (002/FR-014).
- Não há resultado do baseline sobre o dataset: nenhum número de
  desempenho é afirmado aqui.
