# Design: precisão da detecção de credenciais em `string_patterns.py`

- **Data:** 2026-09-12
- **Branch:** `fix/credential-detection-accuracy`
- **Origem:** falso positivo encontrado ao inspecionar a 1ª amostra gerada do dataset; análise cruzada com `docs/Relatorio_Tecnico_LLM_Deteccao_Credenciais_Firmware.pdf` (spec v2.0, Marcus Toledo, 2026).

## Contexto

`src/features/string_patterns.py` é um módulo puro regex/stdlib (sem dependências
externas) que extrai sinais de segurança de strings ASCII de firmware. Duas de suas
funções alimentam `scoring.py` via `scan_strings()`:

- `count_hardcoded_passwords(strings) -> int`
- `count_credential_pairs(strings) -> int`

O relatório técnico propõe uma reformulação completa orientada a ingestão por LLM
(ontologia de 8 rótulos, schema JSON de resposta, prompts de sistema). Esse aparato é
desnecessário aqui: o pipeline de classificação de firmware deste projeto é
determinístico (regex + features estatísticas + doc2vec), sem chamada a LLM em tempo
de inferência. O valor real do relatório para este trabalho é (a) o diagnóstico de
falsos positivos/negativos da heurística atual e (b) a decisão de arquitetura
"classificar antes de contar" — separar extração de candidatos da decisão de
aceitá-los — adaptada aqui em Python puro, sem LLM.

## Problema (causa raiz)

1. **Falsos positivos por valor não-concreto.** `_PASSWORD_KV_RE` aceita qualquer
   `\S+` como valor: `password=%s`, `password=${PASSWORD}`, `password=NULL` e
   `password_length=8` são hoje contados como credencial.
2. **Falsos positivos por token isolado genérico.** O fallback de
   `count_hardcoded_passwords` conta qualquer string cujo split por espaço contenha um
   token igual a um item de `_DEFAULT_PASSWORDS` — incluindo palavras comuns em texto
   de firmware sem relação com autenticação (`test`, `system`, `service`, `support`,
   `guest`, `default`), gerando ruído alto (`"self test"`, `"system ready"`, etc.).
3. **Falsos negativos por chave composta.** `\b(?:password|passwd|...)\b` exige a
   palavra isolada; chaves compostas sem separador (`adminPassword`, `wl0_wpa_psk`) não
   batem por causa do `\b`.
4. **Falsos negativos por família ausente.** Credenciais em `userinfo` de URL
   (`http://admin:admin@host/`) só são pegas incidentalmente por `count_credential_pairs`
   quando ambos os lados caem na lista fraca — não há extração dedicada para essa
   família.
5. **Responsabilidades misturadas.** `count_hardcoded_passwords()` combina extração,
   decisão de aceitação e agregação na mesma função, dificultando testar cada regra
   isoladamente (mesmo diagnóstico do relatório).

## Não objetivos

- Não introduzir chamadas a LLM nem o schema de resposta do relatório (decisão
  confirmada com o usuário).
- Não alterar o schema de features (`scan_strings()` mantém as mesmas chaves) nem
  `scoring.py` — sem novos pesos, sem novas colunas no dataset.
- Não reprocessar o dataset já extraído como parte desta branch (fica como
  recomendação para antes do próximo retrain, já que os *valores* das duas features
  mudam mesmo sem mudar o schema).

## Arquitetura proposta

Refatorar internamente `count_hardcoded_passwords` e `count_credential_pairs` para
compartilhar duas etapas, sem expor uma API pública nova (as duas funções mantêm a
assinatura `list[str] -> int`):

```
strings
  -> extract_kv_candidates(s)        # regex estrutural: key=value, user:pass, URL userinfo
  -> _is_rejected(candidate)         # placeholder / variável / template / nulo / metadado
  -> aceita como candidato válido
  -> count_hardcoded_passwords()     # agrega candidatos "plaintext"
  -> count_credential_pairs()        # agrega candidatos "pair" (inclui URL userinfo)
```

A ordem importa: **filtros de rejeição rodam antes de qualquer contagem positiva**,
para que `password=%s` nunca chegue a ser candidato aceito — mesma precedência do
relatório (exclusões antes de positivos).

### 1. Filtros de rejeição (novo)

Um valor de `key=value` é rejeitado (não conta como credencial) se:

| Categoria | Exemplos | Detecção |
|---|---|---|
| Format specifier | `%s`, `%d`, `%.*s`, `%s\n` | regex `^%[.\d*]*[sdxu]` |
| Variável | `$PASSWORD`, `${PASSWORD}`, `$1` | regex `^\$\{?\w*\}?$` |
| Template | `{password}`, `{{password}}`, `<password>` | regex de delimitadores casados |
| Nulo | `NULL`, `null`, `None`, `none`, `nil`, `undefined`, `(null)` | comparação case-insensitive contra um `frozenset` |
| Metadado (chave) | `password_length`, `password_hash_algorithm` | chave termina em sufixo de `_METADATA_SUFFIXES` (`_length`, `_len`, `_size`, `_hash`, `_algorithm`, `_policy`, `_timeout`) |

### 2. Aliases de chave expandidos + composição

- Ampliar `_PASSWORD_KV_RE` com os aliases do relatório: `passphrase`, `pass_phrase`,
  `pswd`, `psw`, `userpass`, `loginpass`, `wpa_psk`, `wpa_passphrase`, `ftp_pass`,
  `enable_password`, `admin_password`, `root_password`, `telnet_password`,
  `ssh_password`, `http_password`, `pppoe_password`.
- Trocar o `\b(?:...)\b` por um casamento que tolera prefixo composto
  (`snake_case`, `kebab-case`, `camelCase`) antes da palavra-chave, mantendo
  case-insensitive — cobre `adminPassword=`, `wl0_wpa_psk=`.

### 3. Nova família: `URL_USERINFO`

Nova regex dedicada para extrair `user:pass` do trecho `scheme://user:pass@` em URLs.
Alimenta `count_credential_pairs` como uma fonte adicional de candidatos, com a mesma
regra de aceitação da seção 4 abaixo (usuário reconhecível) — sem exigir que o valor da
senha esteja na lista fraca, já que o delimitador de protocolo (`://...@`) já é o sinal
estrutural forte que o relatório pede para essa família.

### 4. Contexto exigido para tokens isolados

Em vez de casar qualquer token de `_DEFAULT_PASSWORDS` em qualquer string, o match só
conta se a mesma string também apresentar um **sinal de contexto de autenticação**:

- a string contém uma palavra-gatilho (`login`, `senha`, `passwd`, `password`, `user`,
  `account`, `credential`, `auth`) próxima ao token, **ou**
- o token faz parte de um par delimitado por `:`/`=` (já capturado pelas etapas 1–3).

Isso elimina falsos positivos tipo `"self test"` / `"system ready"` mantendo a
cobertura de casos como `"default password: admin"` ou `"login: root"`.

### 5. Testes de regressão

Novo fixture `tests/fixtures/credential_cases.jsonl`, formato inspirado no §9.1 do
relatório:

```json
{"id": "neg_placeholder_01", "text": "password=%s", "expected_passwords": 0, "expected_pairs": 0}
{"id": "pos_kv_wpa_psk", "text": "wpa_psk=12345678", "expected_passwords": 1, "expected_pairs": 0}
{"id": "pos_url_userinfo", "text": "http://admin:admin@192.168.1.1/", "expected_passwords": 0, "expected_pairs": 1}
```

Carregado via `pytest.mark.parametrize` em `tests/test_string_patterns.py`, cobrindo:
- os *hard negatives* obrigatórios do relatório (§9.3);
- os casos de fronteira do relatório (§6.2) que se aplicam sem o schema de rótulos
  completo (ex.: `admin:admin123` deve virar par válido; `setPassword("admin")` deve
  contar; `passwd` isolado não deve contar);
- os falsos positivos reais encontrados na amostra gerada (a ser anexado pelo usuário
  como caso adicional).

## Impacto e follow-ups

- `scoring.py` e o dict retornado por `scan_strings()` não mudam de formato — só o
  valor numérico das duas contagens muda (deve ficar mais baixo em firmwares "normais"
  e mais alto em firmwares com credenciais reais).
- Dataset já extraído (`dataset/`) fica com valores antigos para essas duas colunas até
  uma re-extração; recomendado rodar `extract_features` novamente antes do próximo
  treino, mesmo sem migração de schema.
- Item aberto do relatório (comparação regra vs. LLM vs. híbrido, features separadas
  por família) fica registrado como possível P2 futuro, fora desta branch.

## Arquivos afetados

- `src/features/string_patterns.py` (lógica)
- `tests/test_string_patterns.py` (testes existentes + novos parametrizados)
- `tests/fixtures/credential_cases.jsonl` (novo)
