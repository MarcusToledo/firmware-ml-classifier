"""Contrato compartilhado da tabela de treino (spec 008).

Reúne nomes de colunas, arquivos, motivos de exclusão e estados de extração
usados pela preparação (`training_table`) e pela validação (`validation`).
"""

from __future__ import annotations

from src.features.filesystem import FS_STATUS_ERROR
from src.features.unpack import (
    STATUS_ENCRYPTED,
    STATUS_FAILURE,
    STATUS_FILES,
    STATUS_NO_FILESYSTEM,
    STATUS_NOT_RUN,
    STATUS_OK,
    STATUS_SIZE,
    STATUS_TIME,
)
from src.labeling.cve_labels import (
    LABEL_CRITICAL_CVE,
    LABEL_INDETERMINATE,
    LABEL_KNOWN_CVE,
    LABEL_NO_KNOWN_CVE,
)

KEY_COLUMN = "firmware_id"
TARGET_COLUMN = "security_level"
TARGET_CLASSES = (LABEL_NO_KNOWN_CVE, LABEL_KNOWN_CVE, LABEL_CRITICAL_CVE)
LABEL_VALUES = TARGET_CLASSES + (LABEL_INDETERMINATE,)

TABLE_FILENAME = "training_table.parquet"
EXCLUSIONS_FILENAME = "training_table_exclusions.csv"
PROVENANCE_FILENAME = "training_table_provenance.jsonl"
META_FILENAME = "training_table.meta.json"

EXTRACTION_STATUS_COLUMNS = (
    "meta_binwalk_status",
    "meta_unpack_status",
    "meta_third_party",
    "meta_fs_status",
)
IDENTITY_COLUMNS = ("meta_path", "meta_brand", "meta_model")

FORBIDDEN_PREFIXES = ("meta_", "doc2vec_", "cve_count_")
FORBIDDEN_COLUMNS = frozenset(
    {
        "vendor",
        "model",
        "version",
        "version_source",
        "cve_total",
        "cvss_max",
        "label_strategy",
        "alias_count",
    }
)

ONE_HOT_SOURCES = ("fs_type", "compression_type")
ONE_HOT_OTHER = "outro"
ONE_HOT_MISSING = "ausente"
ONE_HOT_SEPARATOR = "__"

REASON_EXTRACTION_FAILURE = "falha_extracao"
REASON_THIRD_PARTY = "terceiros"
REASON_INDETERMINATE = "indeterminado"
REASON_ORDER = (REASON_EXTRACTION_FAILURE, REASON_THIRD_PARTY, REASON_INDETERMINATE)

CHANGE_DOC2VEC = "doc2vec_t06_proposto"
CHANGE_ONE_HOT = "texto_one_hot"
CHANGE_T13A_REMOVE = "t13a_retirar"
CHANGE_T13A_REFORMULATE = "t13a_reformular"

# Decisões da T13-A (013/FR-006; relatório reports/t13a_20261028T223405Z):
# colunas de detectores retirados ou a reformular saem do vetor reportado
# (002/FR-035, FR-036). A extração continua a produzi-las; reformular exige
# regra pré-registrada e nova validação antes de voltar ao vetor.
T13A_EXCLUDED_COLUMNS: dict[str, str] = {
    "count_hardcoded_passwords": CHANGE_T13A_REMOVE,
    "count_credential_pairs": CHANGE_T13A_REMOVE,
    "count_api_tokens": CHANGE_T13A_REMOVE,
    "count_non_public_ips": CHANGE_T13A_REFORMULATE,
    "count_public_ips": CHANGE_T13A_REFORMULATE,
    "has_debug_account": CHANGE_T13A_REFORMULATE,
    "n_crypto_signatures": CHANGE_T13A_REFORMULATE,
    "has_encrypted_sections": CHANGE_T13A_REFORMULATE,
}

# Estados do Binwalk vêm de `pipeline/feature_extraction.py`; `src/` não importa
# `pipeline/`, então os literais ficam aqui.
BINWALK_KEEP = frozenset({"ok"})
BINWALK_EXCLUDE = frozenset({"erro"})
BINWALK_ABORT = frozenset({"timeout", STATUS_NOT_RUN})

# `criptografado` é limite do dado, não falha operacional (001/FR-020).
UNPACK_KEEP = frozenset(
    {STATUS_OK, STATUS_NO_FILESYSTEM, STATUS_ENCRYPTED, STATUS_SIZE, STATUS_FILES}
)
UNPACK_EXCLUDE = frozenset({STATUS_FAILURE})
UNPACK_ABORT = frozenset({STATUS_TIME, STATUS_NOT_RUN})

FS_KEEP = frozenset({"ok", STATUS_NOT_RUN})
FS_EXCLUDE = frozenset({FS_STATUS_ERROR})


def is_forbidden_column(name: str) -> bool:
    """Indica se a coluna não pode entrar no vetor de features (008/FR-006)."""
    return (
        name in FORBIDDEN_COLUMNS
        or name.startswith(FORBIDDEN_PREFIXES)
        or name in ONE_HOT_SOURCES
    )
