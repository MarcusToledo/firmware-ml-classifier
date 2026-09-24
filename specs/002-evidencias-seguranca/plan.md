# Implementation Plan: Evidências de segurança

**Branch**: `docs/specs-retroativas` | **Date**: 2026-09-24 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/002-evidencias-seguranca/spec.md`

**Note**: plano retroativo. Descreve o código que já existe em `master`; não
há Phase 0 (`research.md`), `contracts/` nem `quickstart.md`. O `tasks.md`
fica para a subtask 3 (validação com `/speckit.analyze`).

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
`detector_version` fixo em `1.0`

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
|V. Reprodutibilidade|Passa parcialmente|Regras determinísticas (regex, listas e limiares fixos) e `detector_version` em cada achado. Mas `_DETECTOR_VERSION` (`src/evidence/patterns.py`, `src/evidence/binwalk_findings.py`) é constante de módulo, igual para todos os detectores, e não muda com a regra|
|VI. Firmware não confiável|Violação herdada|Strings só ASCII (passa). Binwalk ausente ou com erro deixa `n_crypto_signatures=0` e `has_encrypted_sections=False` sem registro no artefato; herdado de `pipeline/feature_extraction.py::_extract_binwalk_descriptions` (`001-extracao-features`). Ver Complexity Tracking|
|VII. Integridade científica|Passa|Todo FR tem módulo e teste abaixo ou aparece em "Sem verificação"; números medidos citam data e artefato|

## Project Structure

### Documentation (this feature)

```text
specs/002-evidencias-seguranca/
├── spec.md              # /speckit.specify + /speckit.clarify
├── plan.md              # este arquivo
├── data-model.md        # esquema do achado e da linha de findings.jsonl
└── checklists/
    └── requirements.md  # checklist de qualidade da spec
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

### FR → módulo → teste

|FR|Módulo|Teste|
|---|---|---|
|FR-001|`pipeline/feature_extraction.py::extract_features_from_path` (passa `feature_vector.strings` e `descriptions`); assinaturas `list[str]` em `src/evidence/patterns.py` e `src/evidence/binwalk_findings.py`|`test_pipeline_extraction.py::test_extract_features_from_path_calls_extract_ascii_strings_once`, `::test_extract_features_from_path_empty_file_has_no_findings`|
|FR-002|`src/evidence/findings.py::SecurityFinding`; `_DETECTOR_VERSION` em `src/evidence/patterns.py` e `src/evidence/binwalk_findings.py`|`test_evidence_findings.py::test_security_finding_holds_all_fields`, `::test_security_finding_is_frozen`|
|FR-003|`src/evidence/patterns.py::find_hardcoded_passwords`, `count_hardcoded_passwords`, `_PASSWORD_KV_RE`, `_DEFAULT_PASSWORDS`|`test_evidence_patterns.py::test_passwords_empty`, `::test_passwords_kv_match`, `::test_passwords_kv_colon`, `::test_passwords_kv_case_insensitive`, `::test_passwords_default_token`, `::test_passwords_default_token_root`, `::test_passwords_no_match`, `::test_passwords_multiple_strings`, `::test_passwords_finding_has_high_confidence_on_kv_match`, `::test_passwords_finding_has_medium_confidence_on_default_token`|
|FR-004|`src/evidence/patterns.py::find_credential_pairs`, `count_credential_pairs`, `_CRED_PAIR_RE`, `_CRED_PAIR_WEAK`|`test_evidence_patterns.py::test_cred_pairs_empty`, `::test_cred_pairs_admin_admin`, `::test_cred_pairs_root_1234`, `::test_cred_pairs_non_weak_ignored`, `::test_cred_pairs_long_hash_ignored`, `::test_cred_pairs_multiple_strings`, `::test_cred_pairs_multiple_in_one_string_counts_once`, `::test_cred_pairs_finding_has_high_confidence`|
|FR-005|`src/evidence/patterns.py::find_hardcoded_ips`, `count_hardcoded_ips`, `_IPV4_RE`, `_IP_EXCLUDES`|`test_evidence_patterns.py::test_ips_empty`, `::test_ips_valid_match`, `::test_ips_multiple`, `::test_ips_excludes_broadcast`, `::test_ips_excludes_all_zeros`, `::test_ips_excludes_loopback`, `::test_ips_invalid_octet`, `::test_ips_invalid_octet_256`, `::test_ips_no_match`, `::test_ips_finding_has_low_confidence`|
|FR-006|`src/evidence/patterns.py::find_public_ips`, `count_public_ips`|`test_evidence_patterns.py::test_public_ips_empty`, `::test_public_ips_routable`, `::test_public_ips_c2_candidate`, `::test_public_ips_ignores_private_10`, `::test_public_ips_ignores_private_192_168`, `::test_public_ips_ignores_rfc1918_172`, `::test_public_ips_172_32_is_public`, `::test_public_ips_ignores_link_local`, `::test_public_ips_ignores_multicast`, `::test_public_ips_multiple_in_one_string`, `::test_public_ips_finding_has_high_confidence`|
|FR-007|`src/evidence/patterns.py::find_telnetd`, `has_telnetd`|`test_evidence_patterns.py::test_telnetd_empty`, `::test_telnetd_true`, `::test_telnetd_false`, `::test_telnetd_substring`, `::test_telnetd_finding_has_high_confidence`|
|FR-008|`src/evidence/patterns.py::find_debug_account`, `has_debug_account`, `_DEBUG_ACCOUNT_RE`|`test_evidence_patterns.py::test_debug_account_empty`, `::test_debug_account_debug`, `::test_debug_account_guest`, `::test_debug_account_test`, `::test_debug_account_case_insensitive`, `::test_debug_account_no_partial_match`, `::test_debug_account_no_match`, `::test_debug_account_finding_has_low_confidence`|
|FR-009|`src/evidence/patterns.py::_find_outdated_version`, `_parse_version`, `_VERSION_THRESHOLDS`, `_LIBSSL_RE`, `_BUSYBOX_RE`, `_DROPBEAR_RE`, `find_outdated_*`, `has_outdated_*`|`test_evidence_patterns.py::test_libssl_empty`, `::test_libssl_outdated`, `::test_libssl_outdated_1_1_0`, `::test_libssl_current`, `::test_libssl_newer`, `::test_libssl_no_match`, `::test_libssl_slash_separator`, `::test_libssl_finding_has_medium_confidence`, `::test_busybox_empty`, `::test_busybox_outdated`, `::test_busybox_current`, `::test_busybox_newer`, `::test_busybox_no_match`, `::test_busybox_no_space_variant`, `::test_busybox_underscore_separator`, `::test_dropbear_empty`, `::test_dropbear_outdated`, `::test_dropbear_current`, `::test_dropbear_newer`, `::test_dropbear_no_match`|
|FR-010|`src/evidence/patterns.py::find_urls`, `count_urls`, `_URL_RE`|`test_evidence_patterns.py::test_urls_empty`, `::test_urls_http`, `::test_urls_https`, `::test_urls_multiple_in_one_string`, `::test_urls_no_match`, `::test_urls_finding_has_low_confidence`|
|FR-011|`src/evidence/patterns.py::find_api_tokens`, `count_api_tokens`, `_API_TOKEN_RE`|`test_evidence_patterns.py::test_tokens_empty`, `::test_tokens_hex_32_chars`, `::test_tokens_too_short`, `::test_tokens_no_match`|
|FR-012|`src/evidence/binwalk_findings.py::find_crypto_signatures`, `count_crypto_signatures`, `_CRYPTO_RE`|`test_evidence_binwalk_findings.py::test_count_crypto_signatures_empty`, `::test_count_crypto_signatures_matches`, `::test_count_crypto_signatures_certificate`, `::test_crypto_signature_finding_has_medium_confidence`|
|FR-013|`src/evidence/binwalk_findings.py::find_encrypted_sections`, `has_encrypted_sections`, `_ENCRYPTED_RE`|`test_evidence_binwalk_findings.py::test_has_encrypted_false_empty`, `::test_has_encrypted_true`, `::test_has_encrypted_cipher`, `::test_has_encrypted_false_no_match`, `::test_encrypted_section_finding_has_medium_confidence`|
|FR-014|`src/evidence/patterns.py::findings_to_counts`, `scan_strings`, `_COUNT_DETECTORS`, `_BOOL_DETECTORS`; `count_crypto_signatures`, `has_encrypted_sections`; chamada em `pipeline/feature_extraction.py::extract_features_from_path`|`test_evidence_patterns.py::test_findings_to_counts_matches_scan_strings`, `::test_scan_strings_returns_all_keys`, `::test_scan_strings_empty_defaults`, `::test_scan_strings_detects_features`; `test_pipeline_extraction.py::test_extract_features_includes_string_pattern_keys`, `::test_extract_features_includes_binwalk_keys`, `::test_extract_features_with_mocked_binwalk`|
|FR-015|`src/evidence/patterns.py::scan_strings_findings`; `pipeline/feature_extraction.py::extract_features_from_path`, `PipelineResult.findings`|`test_evidence_patterns.py::test_scan_strings_findings_returns_all_matches`; `test_pipeline_extraction.py::test_extract_features_from_path_includes_structured_findings`, `::test_extract_features_from_path_empty_file_has_no_findings`|
|FR-016|`scripts/extract_features.py::main` (`--findings-output`)|`test_pipeline_cli.py::test_cli_findings_output`, `::test_cli_without_findings_output_does_not_write_file`|

### Sem verificação

Partes de FR sem teste que as exercite:

- FR-001: ausência de consulta a CVE, NVD ou identidade (garantida só pela
  assinatura `list[str]` dos detectores) e reuso das descrições do Binwalk
  sem nova varredura.
- FR-002: o valor de `type` de cada detector (só o teste da dataclass
  confere `type`, com valor montado à mão) e `detector_version="1.0"` nos
  achados gerados pelos detectores.
- FR-006: exclusão de `0.0.0.0`, `255.255.255.255`, `127.0.0.0/8` e do
  primeiro octeto ≥ 240 no detector `public_ips`.
- FR-007: distinção de maiúsculas em `telnetd`.
- FR-009: `confidence`, `detector` e `type` dos achados de BusyBox e
  Dropbear; `type` do achado de OpenSSL.
- FR-011: a forma não hexadecimal (`[A-Za-z0-9+/=_-]`), a exigência de
  borda sem letra ou dígito, o `confidence` e o `context` com 12
  caracteres.
- FR-014: igualdade entre a contagem do vetor e o número de achados quando
  um detector tem mais de um achado. `test_findings_to_counts_matches_scan_strings`
  compara `findings_to_counts(scan_strings_findings(s))` com `scan_strings(s)`,
  que é a mesma expressão, e passa por construção.
- FR-015: a ordem dos achados na lista.
- FR-016: presença dos seis campos do achado em cada linha (o teste confere
  `detector`, `firmware_id` e `path`), UTF-8 sem escape, criação do
  diretório pai e log do total.

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
|Princípio VI: Binwalk ausente ou encerrado com erro deixa `n_crypto_signatures=0` e `has_encrypted_sections=False`, indistinguíveis de "sem cripto", sem registro no artefato|Herdada de `pipeline/feature_extraction.py::_extract_binwalk_descriptions` (`001-extracao-features`, Complexity Tracking)|Correção pendente registrada no `TODO.md`|
