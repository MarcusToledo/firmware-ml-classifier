# Feature Specification: Evidências de segurança

**Feature Branch**: `docs/specs-retroativas`

**Created**: 2026-09-24

**Status**: Implementado

**Input**: User description: "Spec retroativa (Status Implementado) da camada de evidências de segurança: 11 detectores sobre as strings ASCII já extraídas e 2 sobre as descrições do Binwalk, achados estruturados SecurityFinding auditáveis, contagens/flags que entram no vetor de features e JSONL opcional via --findings-output. Derivar só do código em master, testes, docs/PIPELINE.md e TODO.md."

## Clarifications

### Session 2026-09-24

- Varredura de ambiguidade (`/speckit.clarify`): sem ambiguidades
  críticas. Cada detector é uma regra fixa (regex, lista ou limiar de
  versão) lida no código em `master`; os falsos positivos e os detectores
  constantes são limitações registradas em Edge Cases, no `TODO.md` e em
  T07, não escolhas de spec. Nenhuma pergunta feita.
- Terminologia normalizada: "achado" é um registro com `type`, `source`,
  `context`, `confidence`, `detector` e `detector_version`. "Contagem por
  ocorrência" conta cada match dentro de uma string; "contagem por string"
  conta no máximo um achado por string. A regra de cada detector diz qual
  das duas vale.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Banca audita cada achado (Priority: P1)

A banca abre o arquivo de achados de uma extração e, para cada contagem ou
flag de evidência, vê o texto de origem, a explicação do match, a confiança,
o detector e a versão do detector, ligados ao firmware por `firmware_id` e
`path`.

**Why this priority**: uma contagem sem o texto que a gerou não é
auditável. A banca precisa conferir se um "credential_candidate" é mesmo
credencial antes de aceitar a feature (constituição, princípio VII).

**Independent Test**: extrair um firmware cujos bytes contêm
`password=admin telnetd` com `--findings-output` e ler o JSONL.

**Acceptance Scenarios**:

1. **Given** um firmware com os bytes `password=admin telnetd`, **When** o
   pesquisador roda a extração com `--findings-output findings.jsonl`,
   **Then** o arquivo tem achados dos detectores `hardcoded_passwords` e
   `telnetd`, e toda linha tem `firmware_id` e `path`.
2. **Given** a mesma extração sem `--findings-output`, **When** ela
   termina, **Then** nenhum arquivo JSONL é criado.
3. **Given** a string `password=secret123`, **When** os detectores rodam,
   **Then** há um achado com `detector="hardcoded_passwords"`,
   `confidence="high"` e `source` igual à string original.
4. **Given** um arquivo vazio, **When** ele é extraído, **Then** não há
   nenhum achado para ele.

---

### User Story 2 - Contagens e flags estáveis no vetor (Priority: P1)

O pesquisador recebe, para todo firmware, as mesmas 13 colunas de evidência
no vetor de features: 11 derivadas das strings e 2 da varredura do Binwalk,
com 0/`False` quando não há achado.

**Why this priority**: o conjunto fixo de colunas é o que permite montar a
matriz de treino; a contagem precisa bater com os achados auditados na
User Story 1.

**Independent Test**: rodar os detectores sobre uma lista vazia e sobre
uma lista com credencial, IP, `telnetd` e OpenSSL antigo, e comparar as
contagens com os achados.

**Acceptance Scenarios**:

1. **Given** nenhuma string, **When** os detectores rodam, **Then** as 11
   colunas de strings estão presentes, com 0 nas contagens e `False` nas
   flags.
2. **Given** as strings `password=admin`, `192.168.1.1`,
   `/usr/sbin/telnetd` e `OpenSSL 1.0.2k`, **When** as contagens são
   derivadas dos achados, **Then** o resultado é igual ao das contagens
   calculadas direto das strings.
3. **Given** uma varredura do Binwalk que reporta `AES encrypted block`,
   **When** as features são extraídas, **Then** `n_crypto_signatures=1` e
   `has_encrypted_sections=True`.
4. **Given** a string `admin:admin root:root`, **When** os detectores
   rodam, **Then** `count_credential_pairs=1` (contagem por string).
   **Given** a string `8.8.8.8 and 1.1.1.1`, **Then** `count_public_ips=2`
   (contagem por ocorrência).

---

### User Story 3 - Evidência sem nova leitura e sem CVE (Priority: P2)

A camada de evidências interpreta só o que a extração já produziu (strings
ASCII e descrições do Binwalk). Não lê o firmware de novo e não consulta
CVE, NVD nem identidade do path.

**Why this priority**: reler o binário dobraria o custo em firmwares
grandes; usar CVE ou identidade nas evidências vazaria o rótulo para o
vetor (constituição, princípio III).

**Independent Test**: extrair um firmware contando quantas vezes as strings
ASCII são extraídas, e extrair um arquivo vazio.

**Acceptance Scenarios**:

1. **Given** um firmware, **When** ele é extraído, **Then** as strings
   ASCII são extraídas uma única vez e reaproveitadas pelos detectores.
2. **Given** um firmware com falha de leitura, **When** ele é extraído,
   **Then** a lista de achados é vazia e as 13 colunas de evidência valem
   0/`False`.
3. **Given** qualquer firmware, **When** as colunas de evidência são
   geradas, **Then** nenhuma delas tem nome de CVE (`cvss_max`,
   `cve_total`, `cve_count_*`) nem de identidade.

---

### Edge Cases

- Cada detector roda duas vezes por firmware: uma para a contagem/flag do
  vetor e outra para os achados. O mesmo vale para os 2 detectores de
  Binwalk. O resultado não muda, só o custo. O comentário no código diz o
  contrário ("sem rodar deteccao duas vezes"). Pendente no `TODO.md`,
  request "Responder o review do Kody no PR #5", e no TickTick ("Rodar
  detecção de strings e Binwalk uma única vez").
- `hardcoded_passwords` tem falso positivo alto: 98,6% dos achados
  (1040/1055) são token avulso, como `" -- System halted"` contado por
  conter "system" (registrado no `TODO.md`). Medido em 2026-09-24 sobre
  `findings_v2.jsonl`: os tokens mais frequentes são `System` (245),
  `default` (133), `Default` (116), `system` (104) e `Enable` (93). A
  correção feita no #4 ainda não foi portada (`TODO.md`, request
  "Responder o review do Kody no PR #5").
- As strings vêm limitadas a `max_strings=2000` pela extração. Essas 2000
  strings cobrem ~3,7% dos bytes lidos e são cabeçalho mais ruído de
  payload comprimido, então os detectores de string ficam quase cegos
  (`TODO.md`, item "Documento de strings"). Medido em 2026-09-24: só 199
  dos 840 paths têm ao menos um achado em `findings_v2.jsonl`.
- 5 detectores são constantes em 840/840: `count_credential_pairs=0`,
  `has_telnetd`, `has_outdated_libssl`, `has_outdated_busybox` e
  `has_outdated_dropbear` sempre `False`. Registrado no `TODO.md` e
  conferido em 2026-09-24 sobre `features_v2.parquet`. Decisão em T07
  (subtask 4).
- `debug_account` casa qualquer palavra inteira `debug`, `guest` ou `test`.
  Medido em 2026-09-24 sobre `findings_v2.jsonl`: 128 dos 199 achados são
  `test`, vindos de mensagens como `"mtest   - simple RAM test"` e
  `"DRAM Test Fail at address %p."`. Registrado no `TODO.md`.
- `api_tokens` aceita qualquer sequência de 32+ caracteres de
  `[A-Za-z0-9+/=_-]`. Medido em 2026-09-24: 1121 dos 1128 achados de
  `findings_v2.jsonl` não são hexadecimais; exemplos são identificadores e
  paths como `WLAN_ABandRegion0_ChannelselectItems_3` e
  `0123456789abcdefghijklmnopqrstuvwxyz`. Registrado no `TODO.md`.
- `public_ips` e `hardcoded_ips` casam números de versão com 4 partes.
  Medido em 2026-09-24: os 39 achados de `public_ips` em
  `findings_v2.jsonl` vêm de textos com forma de versão, como `7.0.1.0`
  (23 achados), `Linux-2.6.22.18` e
  `(E03.AZ.3)3.12.8.31`; a máscara `255.255.255.0` aparece 11 vezes como
  `hardcoded_ips`. Registrado no `TODO.md`.
- `encrypted_sections` casa `AES`, e o Binwalk descreve tabelas de código
  AES como `AES S-Box` e `AES Inverse S-Box`. Medido em 2026-09-24: 137 dos
  171 achados de `encrypted_sections` são essas tabelas, e em 8 dos 17
  paths com `has_encrypted_sections=True` elas são o único motivo. Como
  `AES` também está na regra de `crypto_signatures`, a mesma descrição gera
  achado nos dois detectores. Registrado no `TODO.md`.
- A regra de Dropbear exige ano com 4 dígitos (`2020.81`). Versões no
  formato `0.NN` não casam e não geram achado. Registrado no `TODO.md`.
- `detector_version` é `1.0` para os 13 detectores e não muda quando uma
  regra muda. Um JSONL gerado antes e depois de portar a correção de
  `hardcoded_passwords` teria a mesma versão com regras diferentes.
  Registrado no `TODO.md`.
- Sem Binwalk no PATH, ou com a varredura encerrada com erro, não há
  achados de Binwalk: `n_crypto_signatures=0` e
  `has_encrypted_sections=False` ficam indistinguíveis de "sem cripto".
  Limitação herdada de `001/FR-007`, registrada no `TODO.md`.
- O JSONL só tem linha para firmware com achado. Firmware sem achado e
  firmware com falha de leitura não aparecem; a cobertura se confere
  cruzando com `features.parquet`. Aliases (mesmo `firmware_id` em paths
  diferentes) repetem os achados, um bloco por path: 3 `firmware_id` de
  `findings_v2.jsonl` têm mais de um path, e 74 `firmware_id` de
  `features_v2.parquet` têm mais de uma linha (medido em 2026-09-24). A
  correlação exata usa `firmware_id` e `path`.
- O campo `path` do JSONL contém fabricante e modelo mesmo no modo
  inferência, como `meta_path` (`001/FR-010`). O JSONL não é feature
  (constituição, princípio III).
- `docs/PIPELINE.md` diz "8 detectores" de strings; são 11 (registrado no
  `TODO.md`).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001** [Implementado]: Os detectores de string DEVEM receber só as
  strings ASCII já extraídas e limitadas pela extração (`001/FR-006`), e os
  de Binwalk só as descrições da varredura já feita (`001/FR-007`). A
  camada de evidências NÃO DEVE ler o firmware, executar o Binwalk nem
  consultar CVE, NVD ou identidade do path. Com falha de leitura, não há
  strings nem descrições, e a lista de achados DEVE ser vazia.
- **FR-002** [Implementado]: Todo achado DEVE ter os campos de texto
  `type`, `source` (a string ou descrição original), `context` (explicação
  do match), `confidence` (`low`, `medium` ou `high`), `detector` e
  `detector_version` (`1.0` em todos os detectores), e DEVE ser imutável.
- **FR-003** [Implementado]: O detector `hardcoded_passwords` DEVE gerar no
  máximo um achado `credential_candidate` por string: `confidence="high"`
  quando a string casa `password|passwd|pass|pwd|secret|credential`
  seguido de `=` ou `:` e de um valor (sem distinção de maiúsculas); senão,
  `confidence="medium"` quando algum token separado por espaço é igual, sem
  distinção de maiúsculas, a uma das 22 senhas padrão: `admin`, `password`,
  `1234`, `12345`, `123456`, `admin123`, `root`, `toor`, `pass`, `test`,
  `1234567890`, `guest`, `default`, `support`, `supervisor`, `service`,
  `system`, `ubnt`, `huawei`, `zte521`, `telnet`, `enable`.
- **FR-004** [Implementado]: O detector `credential_pairs` DEVE gerar no
  máximo um achado `credential_pair` (`confidence="high"`) por string que
  contém `usuário:senha`, cada lado com 1 a 20 caracteres alfanuméricos e
  ambos, sem distinção de maiúsculas, na lista de 22 valores fracos: as
  senhas padrão de FR-003 sem `1234567890` e com `user`.
- **FR-005** [Implementado]: O detector `hardcoded_ips` DEVE gerar um
  achado `hardcoded_ip` (`confidence="low"`) por ocorrência de IPv4 com
  octetos ≤ 255, exceto `0.0.0.0`, `255.255.255.255` e `127.0.0.0/8`.
- **FR-006** [Implementado]: O detector `public_ips` DEVE gerar um achado
  `public_ip` (`confidence="high"`) por ocorrência de IPv4 aceito por
  FR-005 que não esteja em `10.0.0.0/8`, `172.16.0.0/12`,
  `192.168.0.0/16`, `169.254.0.0/16`, `224.0.0.0`–`239.255.255.255`
  (multicast) nem com primeiro octeto ≥ 240.
- **FR-007** [Implementado]: O detector `telnetd` DEVE gerar um achado
  `exposed_service` (`confidence="high"`) por string que contém a
  substring `telnetd`, com distinção de maiúsculas.
- **FR-008** [Implementado]: O detector `debug_account` DEVE gerar um
  achado `debug_account` (`confidence="low"`) por string que contém a
  palavra inteira `debug`, `guest` ou `test`, sem distinção de maiúsculas.
- **FR-009** [Implementado]: Os detectores `outdated_libssl`,
  `outdated_busybox` e `outdated_dropbear` DEVEM gerar um achado
  `outdated_library` (`confidence="medium"`) por string cuja primeira
  versão encontrada está abaixo do limiar, sem distinção de maiúsculas:
  `OpenSSL` seguido de um ou mais espaços ou `/` e versão `X.Y.Z[letra]`,
  limiar 1.1.1; `BusyBox` seguido de zero ou mais espaços ou `_`, `v`
  opcional e versão `X.Y.Z`, limiar 1.33.0; `Dropbear`, espaço, `SSH`
  opcional, `v` opcional e versão `AAAA.N`, limiar 2022.82. A versão DEVE
  ser comparada como tupla de inteiros, ignorando o sufixo de letra
  (`1.1.1a` não é desatualizada).
- **FR-010** [Implementado]: O detector `urls` DEVE gerar um achado `url`
  (`confidence="low"`) por ocorrência de `http://` ou `https://` seguido de
  caracteres até espaço, aspas, `<` ou `>`.
- **FR-011** [Implementado]: O detector `api_tokens` DEVE gerar um achado
  `api_token_candidate` (`confidence="low"`) por ocorrência de sequência
  com 32 ou mais caracteres hexadecimais ou de `[A-Za-z0-9+/=_-]`, sem
  letra ou dígito colado antes ou depois. O `context` DEVE mostrar só os 12
  primeiros caracteres do token.
- **FR-012** [Implementado]: O detector `crypto_signatures` DEVE gerar um
  achado `crypto_signature` (`confidence="medium"`) por descrição do
  Binwalk que contém a palavra `AES`, `DES` ou `RSA`, ou o texto
  `certificate` ou `private key`, sem distinção de maiúsculas.
- **FR-013** [Implementado]: O detector `encrypted_sections` DEVE gerar um
  achado `encrypted_section` (`confidence="medium"`) por descrição do
  Binwalk que contém `encrypt`, a palavra `AES` ou `cipher`, sem distinção
  de maiúsculas.
- **FR-014** [Implementado]: O sistema DEVE derivar do número de achados
  de cada detector as 13 colunas de evidência do vetor de features:
  `count_hardcoded_passwords`, `count_credential_pairs`,
  `count_hardcoded_ips`, `count_public_ips`, `count_urls`,
  `count_api_tokens` e `n_crypto_signatures` valem o número de achados do
  detector; `has_telnetd`, `has_debug_account`, `has_outdated_libssl`,
  `has_outdated_busybox`, `has_outdated_dropbear` e
  `has_encrypted_sections` valem `True` se há ao menos um achado. Em
  resultados regulares de `extract_features_from_path`, as 13 colunas DEVEM
  estar presentes, com 0/`False` sem achado, inclusive em falha de leitura
  tratada. Uma exceção inesperada capturada pelo lote produz um resultado de
  erro sem features.
- **FR-015** [Implementado]: O resultado da extração de cada firmware DEVE
  carregar a lista de todos os achados, na ordem `hardcoded_passwords`,
  `credential_pairs`, `hardcoded_ips`, `public_ips`, `telnetd`,
  `debug_account`, `outdated_libssl`, `outdated_busybox`,
  `outdated_dropbear`, `urls`, `api_tokens`, `crypto_signatures`,
  `encrypted_sections`.
- **FR-016** [Implementado]: Com `--findings-output <arquivo>`, o sistema
  DEVE gravar um JSONL em UTF-8, uma linha por achado, com `firmware_id`,
  `path` e os seis campos do achado, na ordem dos firmwares de entrada.
  DEVE criar o diretório pai, sobrescrever o arquivo e registrar em log o
  total de achados gravados. Sem a opção, NÃO DEVE gravar arquivo de
  achados.

### Key Entities *(include if feature involves data)*

- **Achado de segurança**: observação de um detector sobre uma string ou
  descrição, com origem, contexto, confiança, detector e versão. Não é
  veredito de vulnerabilidade.
- **Detector**: regra fixa (regex, lista de valores ou limiar de versão)
  identificada por `detector` e `detector_version`.
- **Coluna de evidência**: contagem ou flag derivada dos achados de um
  detector; uma das 13 colunas do vetor de features.
- **Arquivo de achados**: `findings.jsonl` (`--findings-output`), um achado
  por linha, correlacionável ao `features.parquet` por `firmware_id` e
  `path`.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: em 100% das linhas da tabela de features, cada uma das 13
  colunas de evidência é igual à contagem (ou à presença) de achados do
  detector correspondente no arquivo de achados, para o mesmo path. Medido
  em 2026-09-24: 0 divergências entre `features_v2.parquet` (840 linhas) e
  `findings_v2.jsonl`.
- **SC-002**: 100% das linhas do arquivo de achados têm os 8 campos
  (`firmware_id`, `path` e os seis do achado) e `firmware_id` não nulo.
  Medido em 2026-09-24: 3049 de 3049 linhas em `findings_v2.jsonl`; o
  total de 3049 achados é o registrado no `TODO.md`, request "Rodar
  extract-features e validar output gerado".
- **SC-003**: as 13 colunas de evidência estão presentes em 100% das linhas
  da tabela de features, inclusive sem Binwalk e com falha de leitura. A
  exceção é a linha de exceção inesperada, que sai sem nenhuma feature
  (data-model de `001-extracao-features`).

## Assumptions

- As strings e as descrições do Binwalk vêm de `001-extracao-features`
  (`001/FR-006`, `001/FR-007`). Os limites de lá (`max_strings`,
  `max_single_string_len`, Binwalk opcional) valem aqui.
- `confidence` é um valor fixo por detector (e por ramo, em
  `hardcoded_passwords`), escolhido pelo autor da regra. Não é
  probabilidade medida.
- As colunas de evidência também são lidas pelo baseline de
  `006-baseline-regras` (`006/FR-002`, `006/FR-005`), que não gera rótulo
  de treino (`006/FR-007`; constituição, princípio II).
- `dataset/processed/findings.jsonl` e `findings_v2.jsonl` têm os mesmos
  3049 achados e a mesma distribuição por detector (medido em 2026-09-24).
