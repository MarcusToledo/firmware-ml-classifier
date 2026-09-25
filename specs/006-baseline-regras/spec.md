# Feature Specification: Baseline determinístico de regras

**Feature Branch**: `docs/specs-retroativas`

**Created**: 2026-09-24

**Status**: Misto

**Input**: User description: "Spec retroativa (Status Implementado) do baseline determinístico de regras fixas: média ponderada de sinais estatísticos, de strings e do Binwalk mais hard rules que só elevam o nível, configurada em YAML versionado. Serve só como referência de comparação com os modelos e nunca gera rótulo de treino. Derivar só do código em master, testes, docs/SCORING.md, docs/PIPELINE.md e TODO.md."

## Clarifications

### Session 2026-09-24

- Varredura de ambiguidade (`/speckit.clarify`, histórico da spec
  retroativa): sem ambiguidades críticas. Os FRs `[Implementado]` descrevem
  o comportamento do código em `master`. Os nomes finais das três classes
  no texto do TCC e a execução do baseline sobre o dataset são decisões
  registradas no `TODO.md`, não escolhas desta spec. Nenhuma pergunta feita
  nessa varredura.
- Terminologia: "nível" é a classe prevista pelo baseline; "rótulo" é só o
  ground truth por CVE de `005-rotulagem-cve` (005/FR-012 e 005/FR-013).
  Os dois usam os mesmos nomes de classe, mas nunca se misturam.

### Session 2026-09-24 (escopo restante, TickTick T11)

- Q: Como o baseline deve tratar um NaN numa feature? → A: como valor
  ausente, com a contagem de valores ausentes ignorados por grupo no
  detalhamento (FR-010). No analyze, o pesquisador incluiu `None` e `pd.NA`
  como ausentes.
- Q: Quais hard rules o resultado deve listar e em que campo? → A: campo
  novo `hard_rules_triggered` com todas as regras cujas condições valeram,
  na ordem de avaliação, mesmo sem elevar o nível; `hard_rule_applied`
  continua com a última que elevou (FR-013).
- Q: Quais faixas a configuração aceita? → A: `0 ≤ low < high ≤ 1`; pesos
  `≥ 0` com soma `> 0` (FR-012). No analyze, o pesquisador decidiu que YAML
  sem a seção `scoring` e chave desconhecida também falham com mensagem de
  contexto.
- Q: Sem grupo presente e com hard rule disparada, qual é o score? → A:
  score 0 e nível igual ao mais grave entre os mínimos das regras que
  dispararam (FR-011).
- Analyze (C2): as constantes dos sub-scores fixas no código são desvio do
  princípio V; o pesquisador pediu FR Planejado para levá-las ao YAML
  versionado (FR-014).

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
8. **Given** features em que todas as estatísticas e flags são NaN, `None`
   ou `pd.NA`, **When** o baseline é calculado, **Then** os três grupos têm
   presença falsa, o score é 0, o nível é `sem_cve_conhecida` e o
   detalhamento registra os valores ausentes por grupo. *(Planejado,
   FR-010; hoje o resultado é `cve_critica` com NaN e erro com `pd.NA`.)*

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
7. **Given** features só com `has_telnetd=True`, sem sinal dos três grupos,
   **When** o baseline é calculado, **Then** o score é 0, o nível é pelo
   menos `cve_conhecida` e a regra `has_telnetd` fica registrada.
   *(Planejado, FR-011; hoje sai `sem_cve_conhecida` sem regra.)*
8. **Given** features de score baixo com `has_telnetd=True` e
   `has_debug_account=True`, **When** o baseline é calculado, **Then**
   `hard_rules_triggered` lista as duas regras e `hard_rule_applied` traz a
   última que elevou. *(Planejado, FR-013; hoje só a última que elevou.)*

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
6. **Given** uma configuração em cada categoria inválida de FR-012 (ex.:
   nível mínimo fora das três classes, `low` maior ou igual a `high`, peso
   negativo, pesos somando 0, YAML vazio, seção `scoring` ausente, chave
   desconhecida), **When** a configuração é carregada, **Then** o
   carregamento falha com mensagem que cita o arquivo e a chave inválida.
   *(Planejado, FR-012.)*

---

### Edge Cases

- Nenhum script do pipeline chama o baseline: não há CLI, artefato nem
  resultado sobre o dataset. Rodá-lo para comparar com os modelos é
  Planejado na spec de treino (TickTick T09).
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
  desatualizada, 0,8 por seção cifrada etc.) são fixas no código. Levá-las
  ao YAML é FR-014 (Planejado).
- Valor ausente representado como NaN (célula nula numa tabela) não é
  tratado como ausente: o grupo conta como presente, NaN numa feature
  estatística vira sub-score máximo e NaN numa flag conta como verdadeiro.
  Features estatísticas, `has_outdated_libssl`, `has_telnetd` e
  `count_hardcoded_passwords` todas em NaN resultam em `cve_critica` (score
  0,64). `pd.NA` numa contagem ou flag derruba o cálculo com `TypeError`.
  Hoje o risco é latente: nenhum script chama o baseline e
  `features_v2.parquet` tem 840/840 linhas com `meta_read_ok=True` e sem
  nulos nas colunas numéricas e booleanas. A correção é FR-010
  (Planejado); a execução sobre o dataset vem com o treino (TickTick T09).
- Sem nenhum grupo presente, ou com os três pesos em 0, o baseline devolve
  `sem_cve_conhecida` sem avaliar as hard rules. Features só com
  `has_telnetd=True` (sem nenhum sinal dos três grupos) saem
  `sem_cve_conhecida`, sem regra aplicada. A correção é FR-011 (Planejado).
- Um nível mínimo de hard rule que não seja uma das três classes (ex.:
  `critico`) é aceito ao carregar a configuração e a regra nunca dispara,
  sem erro nem aviso. Os limiares e pesos também não são validados (ex.:
  `low > high`, peso negativo, pesos todos 0). YAML vazio falha com erro
  genérico (`AttributeError`), não com mensagem de configuração inválida;
  YAML sem a seção `scoring` carrega os padrões sem aviso. Chave
  desconhecida numa seção falha com `TypeError`. A correção é FR-012
  (Planejado).
- Quando mais de uma hard rule eleva o nível, o resultado registra só a
  última que elevou. Registrar todas é FR-013 (Planejado).
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
  features e a mesma configuração DEVEM gerar o mesmo resultado completo
  (todos os campos de FR-001 e os que os FRs Planejado acrescentam), sem
  estado aleatório, inclusive em processos separados e independentemente
  da ordem de execução.
- **FR-010** [Planejado, TickTick T11]: Um valor ausente (`None`, NaN ou
  `pd.NA`) NÃO DEVE contar como sinal presente: não torna o grupo presente,
  não vira sub-score e não conta como flag verdadeira nem como contagem
  maior que 0. O detalhamento DEVE registrar, por grupo, quantos valores
  ausentes foram ignorados.
- **FR-011** [Planejado, TickTick T11]: As hard rules DEVEM ser avaliadas
  também quando nenhum grupo está presente ou a soma dos pesos dos grupos
  presentes é 0; nesse caso o score continua 0 e o nível é o mais grave
  entre os mínimos das regras que dispararam, pela lógica de elevação de
  FR-005. Quando implementado, substitui a precedência do retorno sem hard
  rule de FR-003 e FR-005.
- **FR-012** [Planejado, TickTick T11]: O carregamento da configuração DEVE
  falhar, com mensagem que cita o arquivo e a chave, quando um nível mínimo
  não é uma das três classes, quando os limiares não seguem
  `0 ≤ low < high ≤ 1`, quando algum peso é negativo ou a soma dos pesos é
  0, quando o YAML está vazio ou sem a seção `scoring`, ou quando há chave
  desconhecida. Subseção ou chave ausente dentro de `scoring` continua
  usando o padrão de FR-008.
- **FR-013** [Planejado, TickTick T11]: O resultado DEVE ter o campo
  `hard_rules_triggered`, com todas as hard rules cujas condições valeram,
  na ordem de avaliação, mesmo as que não elevaram o nível.
  `hard_rule_applied` continua com a última que elevou. Pesos, sub-scores e
  nível não mudam.
- **FR-014** [Planejado, TickTick T11]: As constantes dos sub-scores de
  FR-002 (faixas lineares, fatores, saturações, valores por flag e por tipo
  de filesystem ou compressão) DEVEM vir do YAML versionado, com os valores
  atuais como padrão, e seguir as regras de validação de FR-012.

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
  dão o mesmo resultado completo.
- **SC-002**: acrescentar campos de CVE ou identidade às features muda zero
  campos do resultado completo.
- **SC-003**: zero casos em que uma hard rule deixa o nível menos grave que
  o do score.
- **SC-004**: zero chamadas ao baseline na geração de rótulos de treino.
- **SC-005** [Planejado, TickTick T11]: zero valores ausentes (`None`, NaN,
  `pd.NA`) contados como sinal presente, flag verdadeira ou contagem maior
  que 0.
- **SC-006** [Planejado, TickTick T11]: 100% das configurações inválidas
  listadas em FR-012 são rejeitadas no carregamento, com o arquivo e a
  chave na mensagem.
- **SC-007** [Planejado, TickTick T11]: zero constantes de sub-score fixas
  no código; todas vêm do YAML versionado.

## Assumptions

- O baseline é referência de comparação, não ground truth (constituição,
  princípio II). O rótulo de treino segue `005-rotulagem-cve` (005/FR-012
  e 005/FR-013).
- As features de entrada seguem os nomes de `001-extracao-features`; as
  contagens e flags de strings e as features de assinatura do Binwalk vêm
  de `002-evidencias-seguranca` (002/FR-014).
- Não há resultado do baseline sobre o dataset: nenhum número de
  desempenho é afirmado aqui.
