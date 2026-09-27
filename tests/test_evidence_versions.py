"""Protege as versões de cada regra de detector contra alterações inadvertidas."""

import hashlib
import inspect
import re

from src.evidence import binwalk_findings as b
from src.evidence import patterns as p

_DETECTOR_PARTS: dict[str, list[object]] = {
    "hardcoded_passwords": [
        p.find_hardcoded_passwords,
        p._PASSWORD_KV_RE,
        p._CREDENTIAL_KEY_TOKENS,
        p._METADATA_KEY_TOKENS,
        p._NULL_LITERALS,
        p._VARIABLE_REF_RE,
        p._TEMPLATE_RE,
        p._CAMEL_BOUNDARY_RE,
        p._DEFAULT_PASSWORDS,
        p._AUTH_CONTEXT_TRIGGERS,
        p._WORD_RE,
        p._key_tokens,
        p._is_credential_key,
        p._is_rejected_value,
        p._has_default_password_token,
    ],
    "credential_pairs": [p.find_credential_pairs, p._CRED_PAIR_RE, p._CRED_PAIR_WEAK],
    "hardcoded_ips": [
        p.find_hardcoded_ips,
        p._iter_contextual_ipv4,
        p._IPV4_RE,
        p._VERSION_IP_PREFIX_RE,
        p._NETWORK_CONTEXT_WORDS,
        p._WORD_RE,
    ],
    "public_ips": [
        p.find_public_ips,
        p._iter_contextual_ipv4,
        p._IPV4_RE,
        p._VERSION_IP_PREFIX_RE,
        p._NETWORK_CONTEXT_WORDS,
        p._WORD_RE,
    ],
    "telnetd": [p.find_telnetd, p._TELNETD_SUBSTR],
    "debug_account": [
        p.find_debug_account,
        p._DEBUG_ACCOUNT_WORDS,
        p._AUTH_CONTEXT_TRIGGERS,
        p._WORD_RE,
    ],
    "outdated_libssl": [
        p.find_outdated_libssl,
        p._find_outdated_version,
        p._parse_version,
        p._LIBSSL_RE,
        p._VERSION_THRESHOLDS,
    ],
    "outdated_busybox": [
        p.find_outdated_busybox,
        p._find_outdated_version,
        p._parse_version,
        p._BUSYBOX_RE,
        p._VERSION_THRESHOLDS,
    ],
    "outdated_dropbear": [
        p.find_outdated_dropbear,
        p._find_outdated_version,
        p._parse_version,
        p._DROPBEAR_RE,
        p._VERSION_THRESHOLDS,
    ],
    "urls": [p.find_urls, p._URL_RE],
    "api_tokens": [
        p.find_api_tokens,
        p._API_TOKEN_RE,
        p._HEX_TOKEN_RE,
        p._API_TOKEN_MIN_ENTROPY,
        p._API_TOKEN_MAX_RUN,
        p._shannon_entropy_chars,
        p._has_ascending_run,
    ],
    "crypto_signatures": [b.find_crypto_signatures, b._CRYPTO_RE],
    "encrypted_sections": [b.find_encrypted_sections, b._ENCRYPTED_RE],
}

_EXPECTED: dict[str, tuple[str, str]] = {
    "hardcoded_passwords": (
        "2.0",
        "73ef16fb882f3aea2cf09dc37f9f333fefe45a1eded27e548fa3c36e89e1cec4",
    ),
    "credential_pairs": (
        "1.0",
        "e9a37d3909a2d8736f9ba8879d52dcd1132c41f6cd517e85b4c9964f18b48e2b",
    ),
    "hardcoded_ips": (
        "2.0",
        "4b50d0c3c68103a18ed462aae8defdd68d32237a560fab1a2bff4d87df72aed0",
    ),
    "public_ips": (
        "2.0",
        "c3dc77c699483f9eed668a2fc57036f2ac672a6d738cb47c779c0de34b89b3fd",
    ),
    "telnetd": (
        "1.0",
        "9d9dd83f417072789df4d9b09684be9bdbc6b43e27d26a2c120d004c7d62e7ff",
    ),
    "debug_account": (
        "2.0",
        "0c47a75b83098e20ae23474af428248f7541b8e72144b25f24e9ee33bdc92b09",
    ),
    "outdated_libssl": (
        "1.0",
        "7a1acd5a3f6243e34040b51c2008fb847e5752d6a5a3210b88bbbecf1a263d65",
    ),
    "outdated_busybox": (
        "1.0",
        "4a604c94f55bf7703b34100cd7969589e2326fff616bc45f967f54eeeb06bbe9",
    ),
    "outdated_dropbear": (
        "2.0",
        "acafad0084e8c1f8ffe362fe708cb363ddd0f4c5bc10a877d497c0ec5d919ea9",
    ),
    "urls": ("1.0", "8bc41df2fb25b1349e79e0149463d699388b63d96475ee38fa1be395aa328517"),
    "api_tokens": (
        "2.0",
        "e50b16d8845d2b198a1402f53c8b5fb38a2640f986f1567b57ac7a531d2187df",
    ),
    "crypto_signatures": (
        "1.0",
        "3c94c59e38d11193d25726d6bf3028436f4052d569dc7cf165960930abc0e212",
    ),
    "encrypted_sections": (
        "2.0",
        "376e0e6c8b7e43c64590075c99713371a98ed65257f896c0f3e2f8eba5facd1b",
    ),
}


def _rule_hash(detector: str) -> str:
    """Calcula hash estável das partes que definem a regra."""
    chunks: list[str] = []
    for part in _DETECTOR_PARTS[detector]:
        if inspect.isfunction(part):
            chunks.append(inspect.getsource(part))
        elif isinstance(part, re.Pattern):
            chunks.append(f"{part.pattern}|{part.flags}")
        elif isinstance(part, (set, frozenset)):
            chunks.append(repr(sorted(part)))
        elif isinstance(part, dict):
            chunks.append(repr(sorted(part.items())))
        else:
            chunks.append(repr(part))
    return hashlib.sha256("".join(chunks).encode()).hexdigest()


def test_detector_rule_versions() -> None:
    """Exige subir a versão e atualizar o hash quando a regra muda."""
    versions = p.DETECTOR_VERSIONS | b.DETECTOR_VERSIONS
    assert _EXPECTED.keys() == versions.keys() == _DETECTOR_PARTS.keys()
    for detector, version in versions.items():
        assert (version, _rule_hash(detector)) == _EXPECTED[
            detector
        ], f"{detector}: suba a versão e atualize o hash da regra"
