# Implementation Plan: Evidências de segurança

**Branch**: `docs/specs-retroativas` | **Date**: 2026-09-24 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/002-evidencias-seguranca/spec.md`

**Note**: plano retroativo. Descreve o código que já existe em `master`; não há Phase 0 (`research.md`), `contracts/` nem `quickstart.md`. O `tasks.md` é retroativo: registra a verificação de cada FR e cenário e as lacunas de teste. As linhas `[Planejado]` (FR-017 a FR-024, TickTick T11) descrevem módulo e teste previstos; o `tasks.md` as decompõe na fase "Implementação planejada".

## Summary

A camada de evidências roda 11 detectores sobre as strings ASCII e 2 sobre
as descrições do Binwalk que a extração já produziu, gera achados
estruturados e auditáveis e deriva deles as 13 contagens/flags do vetor de
features; o CLI grava os achados em JSONL com `--findings-output`. O papel
da camada no pipeline está em `docs/PIPELINE.md`, §"2. Camada de
evidências" (que ainda cita 8 detectores de string; são 11).

## Technical Context

**Language/Version**: Python ≥ 3.9

**Primary Dependencies**: só biblioteca padrão nos módulos donos (`re`,
`dataclasses`); o JSONL é gravado com `json` pelo CLI de
`001-extracao-features`

**Storage**: arquivo opcional `dataset/processed/findings*.jsonl`

**Testing**: pytest

**Target Platform**: Linux

**Project Type**: biblioteca, exposta pelo CLI `extract-features`
(`--findings-output`)

**Performance Goals**: sem meta definida. Cada detector roda duas vezes por
firmware (contagem e achado)

**Constraints**: entrada limitada por `max_strings=2000` e
`max_single_string_len=1024` em `configs/feature_extraction.yaml`;
`detector_version` fixo em `1.0` (planejado: versão por detector, FR-017)

**Scale/Scope**: 840 firmwares; 3049 achados em
`dataset/processed/findings_v2.jsonl` (medido em 2026-09-24)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

|Princípio|Resultado|Evidência|
|---|---|---|
|I. Somente análise estática|Passa|Os detectores recebem `list[str]` (`src/evidence/patterns.py`, `src/evidence/binwalk_findings.py`); não abrem arquivo nem executam o Binwalk. Strings reaproveitadas: `tests/test_pipeline_extraction.py::test_extract_features_from_path_calls_extract_ascii_strings_once`|
|II. Rótulo exclusivamente por CVE|Não se aplica|A camada não rotula; `confidence` é atributo do achado, não rótulo|
|III. Sem vazamento|Passa|Nenhum detector recebe CVE nem identidade; as 13 colunas passam pela guarda `tests/test_pipeline_extraction.py::test_classifier_features_exclude_cve_and_identity_fields`. O `path` do JSONL tem identidade, mas o JSONL não é feature|
|IV. Modelos simples|Não se aplica|Sem modelo nesta etapa|
|V. Reprodutibilidade|Violação herdada|Regras determinísticas (regex, listas e limiares fixos) e `detector_version` em cada achado. Porém, `_DETECTOR_VERSION` (`src/evidence/patterns.py`, `src/evidence/binwalk_findings.py`) é constante de módulo, igual para todos os detectores, e não muda com a regra. Correção Planejado: FR-017. Ver Complexity Tracking|
|VI. Firmware não confiável|Violação herdada|Strings só ASCII (passa). Binwalk ausente ou com erro deixa `n_crypto_signatures=0` e `has_encrypted_sections=False` sem registro no artefato; herdado de `pipeline/feature_extraction.py::_extract_binwalk_descriptions` (`001-extracao-features`), com correção Planejado em `001/FR-014`. Ver Complexity Tracking|
|VII. Integridade científica|Passa|Todo FR tem módulo e teste abaixo ou aparece em "Sem verificação"; números medidos citam data e artefato|

## Project Structure

### Documentation (this feature)

```text
specs/002-evidencias-seguranca/
├── spec.md                    # /speckit.specify + /speckit.clarify
├── plan.md                    # este arquivo
├── data-model.md              # esquema do achado e da linha de findings.jsonl
├── tasks.md                   # verificação retroativa por FR e cenário e implementação planejada
└── checklists/
    ├── requirements.md        # checklist de qualidade da spec
    └── rastreabilidade.md     # checklist de rastreabilidade e testabilidade
```

### Source Code (repository root)

```text
src/
└── evidence/
    ├── findings.py          # SecurityFinding (dataclass imutável)
    ├── patterns.py          # 11 detectores de string, findings_to_counts, scan_strings(_findings)
    └── binwalk_findings.py  # crypto_signatures, encrypted_sections

tests/
├── test_evidence_binwalk_findings.py
├── test_evidence_findings.py
└── test_evidence_patterns.py
```

**Structure Decision**: estrutura de projeto único já existente. A fronteira
entre specs está no inventário `.docs/brainstorming/inventario-modulos.md`;
esta spec é dona só dos módulos acima. A chamada aos detectores e o JSONL
ficam em módulos de `001-extracao-features` (ver "Símbolos com requisito
nesta spec em módulos de outra spec").

### US → FR → módulo → teste

|FR|US|Módulo|Teste|
|---|---|---|---|
|FR-001|US1, US3|`pipeline/feature_extraction.py::extract_features_from_path`; assinaturas `list[str]` em `src/evidence/patterns.py` e `src/evidence/binwalk_findings.py`|`test_pipeline_extraction.py::test_extract_features_from_path_calls_extract_ascii_strings_once`, `::test_extract_features_from_path_empty_file_has_no_findings` (parcial)|
|FR-002|US1|`src/evidence/findings.py::SecurityFinding`; `_DETECTOR_VERSION` em `src/evidence/patterns.py` e `src/evidence/binwalk_findings.py`|`test_evidence_findings.py::test_security_finding_holds_all_fields`, `::test_security_finding_is_frozen` (parcial)|
|FR-003|US1, US2|`src/evidence/patterns.py::find_hardcoded_passwords`, `count_hardcoded_passwords`, `_PASSWORD_KV_RE`, `_DEFAULT_PASSWORDS`|`test_evidence_patterns.py::test_passwords_kv_match`, `::test_passwords_default_token`, `::test_passwords_finding_has_high_confidence_on_kv_match`|
|FR-004|US2|`src/evidence/patterns.py::find_credential_pairs`, `count_credential_pairs`, `_CRED_PAIR_RE`, `_CRED_PAIR_WEAK`|`test_evidence_patterns.py::test_cred_pairs_admin_admin`, `::test_cred_pairs_multiple_in_one_string_counts_once`, `::test_cred_pairs_finding_has_high_confidence`|
|FR-005|US2|`src/evidence/patterns.py::find_hardcoded_ips`, `count_hardcoded_ips`, `_IPV4_RE`, `_IP_EXCLUDES`|`test_evidence_patterns.py::test_ips_valid_match`, `::test_ips_excludes_broadcast`, `::test_ips_invalid_octet`, `::test_ips_finding_has_low_confidence`|
|FR-006|US2|`src/evidence/patterns.py::find_public_ips`, `count_public_ips`|`test_evidence_patterns.py::test_public_ips_routable`, `::test_public_ips_ignores_rfc1918_172`, `::test_public_ips_ignores_multicast`, `::test_public_ips_multiple_in_one_string` (parcial)|
|FR-007|US1, US2|`src/evidence/patterns.py::find_telnetd`, `has_telnetd`|`test_evidence_patterns.py::test_telnetd_true`, `::test_telnetd_false`, `::test_telnetd_substring`, `::test_telnetd_finding_has_high_confidence` (parcial)|
|FR-008|US2|`src/evidence/patterns.py::find_debug_account`, `has_debug_account`, `_DEBUG_ACCOUNT_RE`|`test_evidence_patterns.py::test_debug_account_debug`, `::test_debug_account_case_insensitive`, `::test_debug_account_no_partial_match`, `::test_debug_account_finding_has_low_confidence`|
|FR-009|US2|`src/evidence/patterns.py::_find_outdated_version`, `_VERSION_THRESHOLDS`, `_LIBSSL_RE`, `_BUSYBOX_RE`, `_DROPBEAR_RE`, `find_outdated_*`, `has_outdated_*`|`test_evidence_patterns.py::test_libssl_outdated`, `::test_libssl_finding_has_medium_confidence`, `::test_busybox_outdated`, `::test_busybox_current`, `::test_dropbear_outdated`, `::test_dropbear_current` (parcial)|
|FR-010|US2|`src/evidence/patterns.py::find_urls`, `count_urls`, `_URL_RE`|`test_evidence_patterns.py::test_urls_http`, `::test_urls_multiple_in_one_string`, `::test_urls_finding_has_low_confidence`|
|FR-011|US2|`src/evidence/patterns.py::find_api_tokens`, `count_api_tokens`, `_API_TOKEN_RE`|`test_evidence_patterns.py::test_tokens_hex_32_chars`, `::test_tokens_too_short`, `::test_tokens_no_match` (parcial)|
|FR-012|US2|`src/evidence/binwalk_findings.py::find_crypto_signatures`, `count_crypto_signatures`, `_CRYPTO_RE`|`test_evidence_binwalk_findings.py::test_count_crypto_signatures_matches`, `::test_count_crypto_signatures_certificate`, `::test_crypto_signature_finding_has_medium_confidence`|
|FR-013|US2|`src/evidence/binwalk_findings.py::find_encrypted_sections`, `has_encrypted_sections`, `_ENCRYPTED_RE`|`test_evidence_binwalk_findings.py::test_has_encrypted_true`, `::test_has_encrypted_cipher`, `::test_encrypted_section_finding_has_medium_confidence`|
|FR-014|US2|`src/evidence/patterns.py::findings_to_counts`, `scan_strings`; integração em `pipeline/feature_extraction.py::extract_features_from_path`|`test_evidence_patterns.py::test_findings_to_counts_matches_scan_strings`, `::test_scan_strings_returns_all_keys`, `::test_scan_strings_empty_defaults`; `test_pipeline_extraction.py::test_extract_features_with_mocked_binwalk` (parcial)|
|FR-015|US1|`src/evidence/patterns.py::scan_strings_findings`; `pipeline/feature_extraction.py::PipelineResult.findings`|`test_evidence_patterns.py::test_scan_strings_findings_returns_all_matches`; `test_pipeline_extraction.py::test_extract_features_from_path_includes_structured_findings` (parcial)|
|FR-016|US1|`scripts/extract_features.py::main` (`--findings-output`)|`test_pipeline_cli.py::test_cli_findings_output`, `::test_cli_without_findings_output_does_not_write_file` (parcial)|
|FR-017 [Planejado, TickTick T11]|US4|previsto: `src/evidence/patterns.py` e `src/evidence/binwalk_findings.py` (versão por detector no lugar de `_DETECTOR_VERSION`)|previsto: `tests/test_evidence_versions.py` (hash de cada detector = constantes da regra + código-fonte da função `find_*` e das auxiliares que ela chama, registrado no teste; falha se o hash muda sem a versão)|
|FR-018 [Planejado, TickTick T11]|US4|previsto: `src/evidence/patterns.py::find_debug_account`, `_DEBUG_ACCOUNT_RE`, lista de gatilhos de autenticação e tokenização `[A-Za-z0-9]+` compartilhadas com FR-023|previsto: `tests/test_evidence_patterns.py` (US4.1)|
|FR-019 [Planejado, TickTick T11]|US4|previsto: `src/evidence/patterns.py::find_api_tokens`, `_API_TOKEN_RE`; entropia de Shannon e checagem de sequência em função auxiliar; limiar 4,3 bits/caractere e tamanho de sequência 5 como constantes versionadas|previsto: `tests/test_evidence_patterns.py` (US4.2)|
|FR-020 [Planejado, TickTick T11]|US4|previsto: `src/evidence/patterns.py::_IPV4_RE`, `_IP_EXCLUDES`, `find_hardcoded_ips`, `find_public_ips`; lista versionada de contexto de rede. Lista inicial, a confirmar na implementação contra os achados medidos: `ip`, `ipaddr`, `host`, `hostname`, `server`, `gateway`, `gw`, `dns`, `ntp`, `route`, `addr`, `address`, `proxy`, `remote`, `peer`, `connect`, `bind`, `listen`|previsto: `tests/test_evidence_patterns.py` (US4.3)|
|FR-021 [Planejado, TickTick T11]|US4|previsto: `src/evidence/binwalk_findings.py::_ENCRYPTED_RE`, `find_encrypted_sections`|previsto: `tests/test_evidence_binwalk_findings.py` (US4.4)|
|FR-022 [Planejado, TickTick T11]|US4|previsto: `src/evidence/patterns.py::_DROPBEAR_RE`, `_find_outdated_version`|previsto: `tests/test_evidence_patterns.py` (US4.5)|
|FR-023 [Planejado, TickTick T11]|US4|previsto: `src/evidence/patterns.py::find_hardcoded_passwords`, `count_hardcoded_passwords`, lista de gatilhos de autenticação (commit `6cc13ef`)|previsto: `tests/test_evidence_patterns.py` (US4.6)|
|FR-024 [Planejado, TickTick T11]|US4|previsto: `src/evidence/patterns.py::_PASSWORD_KV_RE`, `find_hardcoded_passwords`; listas de token de credencial, de metadado e de valores rejeitados (commit `ccf31e4`)|previsto: `tests/test_evidence_patterns.py` (US4.8)|

### Sem verificação

- FR-001: ausência de consulta a CVE, NVD ou identidade e reuso das descrições do Binwalk sem nova varredura.
- FR-002: `type` e `detector_version="1.0"` nos achados gerados por cada detector.
- FR-006: exclusão de `0.0.0.0`, `255.255.255.255`, `127.0.0.0/8` e do primeiro octeto maior ou igual a 240.
- FR-007: distinção de maiúsculas em `telnetd`.
- FR-009: `confidence`, `detector` e `type` dos achados de BusyBox e Dropbear, e `type` do achado de OpenSSL.
- FR-011: forma não hexadecimal, bordas sem letra ou dígito, `confidence` e `context` limitado aos 12 primeiros caracteres.
- FR-014: igualdade entre o número de achados e as contagens com mais de um achado; o teste atual compara duas chamadas da mesma expressão e passa por construção.
- FR-015: ordem completa dos 13 detectores na lista de achados.
- FR-016: oito campos em cada linha, UTF-8 sem escape, criação do diretório pai e log do total.

### Símbolos com requisito em outra spec

Nenhum.

### Símbolos com requisito nesta spec em módulos de outra spec

Ficam em módulos de `001-extracao-features`, mas o requisito é desta spec:

- Chamada a `scan_strings`, `scan_strings_findings`,
  `count_crypto_signatures`, `has_encrypted_sections`,
  `find_crypto_signatures` e `find_encrypted_sections` e o campo
  `PipelineResult.findings` em `pipeline/feature_extraction.py`
  (FR-001, FR-014, FR-015).
- Opção `--findings-output` e gravação do JSONL em
  `scripts/extract_features.py::main` (FR-016).

## Complexity Tracking

|Violação|Por que existe|Alternativa|
|---|---|---|
|Princípio VI: Binwalk ausente ou encerrado com erro deixa `n_crypto_signatures=0` e `has_encrypted_sections=False`, indistinguíveis de "sem cripto", sem registro no artefato|Herdada de `pipeline/feature_extraction.py::_extract_binwalk_descriptions` (`001-extracao-features`, Complexity Tracking)|`001/FR-014` [Planejado, TickTick T11]: Binwalk obrigatório e `meta_binwalk_status`|
|Princípio V: `detector_version` é a constante de módulo `1.0` e não muda quando a regra do detector muda|Herdada de `src/evidence/patterns.py::_DETECTOR_VERSION` e `src/evidence/binwalk_findings.py::_DETECTOR_VERSION`|FR-017 [Planejado, TickTick T11]: versão por detector com teste de guarda|
