"""Protege as versões de cada regra de detector contra alterações inadvertidas."""

import hashlib
import inspect
import re

from src.evidence import binwalk_findings as b
from src.evidence import patterns as p

_DETECTOR_PARTS: dict[str, list[object]] = {
    p.DETECTOR_HARDCODED_PASSWORDS: [
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
    p.DETECTOR_CREDENTIAL_PAIRS: [
        p.find_credential_pairs,
        p._CRED_PAIR_RE,
        p._CRED_PAIR_WEAK,
    ],
    p.DETECTOR_HARDCODED_IPS: [
        p.find_hardcoded_ips,
        p._iter_contextual_ipv4,
        p._IPV4_RE,
        p._VERSION_IP_PREFIX_RE,
        p._NETWORK_CONTEXT_WORDS,
        p._WORD_RE,
        (
            p._MAX_IPV4_OCTET,
            p._UNSPECIFIED_FIRST_OCTET,
            p._LOOPBACK_FIRST_OCTET,
        ),
    ],
    p.DETECTOR_PUBLIC_IPS: [
        p.find_public_ips,
        p._iter_contextual_ipv4,
        p._IPV4_RE,
        p._VERSION_IP_PREFIX_RE,
        p._NETWORK_CONTEXT_WORDS,
        p._WORD_RE,
        (
            p._MAX_IPV4_OCTET,
            p._UNSPECIFIED_FIRST_OCTET,
            p._LOOPBACK_FIRST_OCTET,
        ),
    ],
    p.DETECTOR_TELNETD: [p.find_telnetd, p._TELNETD_SUBSTR],
    p.DETECTOR_DEBUG_ACCOUNT: [
        p.find_debug_account,
        p._DEBUG_ACCOUNT_WORDS,
        p._AUTH_CONTEXT_TRIGGERS,
        p._WORD_RE,
    ],
    p.DETECTOR_OUTDATED_LIBSSL: [
        p.find_outdated_libssl,
        p._find_outdated_version,
        p._parse_version,
        p._LIBSSL_RE,
        p._VERSION_THRESHOLDS,
    ],
    p.DETECTOR_OUTDATED_BUSYBOX: [
        p.find_outdated_busybox,
        p._find_outdated_version,
        p._parse_version,
        p._BUSYBOX_RE,
        p._VERSION_THRESHOLDS,
    ],
    p.DETECTOR_OUTDATED_DROPBEAR: [
        p.find_outdated_dropbear,
        p._find_outdated_version,
        p._parse_version,
        p._DROPBEAR_RE,
        p._VERSION_THRESHOLDS,
    ],
    p.DETECTOR_URLS: [p.find_urls, p._URL_RE],
    p.DETECTOR_API_TOKENS: [
        p.find_api_tokens,
        p._API_TOKEN_RE,
        p._HEX_TOKEN_RE,
        p._API_TOKEN_MIN_ENTROPY,
        p._API_TOKEN_MAX_RUN,
        p._TOKEN_CONTEXT_LENGTH,
        p.shannon_entropy,
        p._has_ascending_run,
    ],
    b.DETECTOR_CRYPTO_SIGNATURES: [b.find_crypto_signatures, b._CRYPTO_RE],
    b.DETECTOR_ENCRYPTED_SECTIONS: [b.find_encrypted_sections, b._ENCRYPTED_RE],
}

_EXPECTED: dict[str, tuple[str, str]] = {
    p.DETECTOR_HARDCODED_PASSWORDS: (
        "2.0",
        "15ffc82fb4ad66a4b0564143dfa5448c98801d7c5936209f3f8e8088600bd704",
    ),
    p.DETECTOR_CREDENTIAL_PAIRS: (
        "1.0",
        "94ae0030d1b63c144cb2ec5cfc1651c7b13d0d3ff941b37a9d12612a42f25227",
    ),
    p.DETECTOR_HARDCODED_IPS: (
        "2.0",
        "83942e9e0ed01dbacbfb8290f9989815fea102a1d247ee932d9196f7b56b1a63",
    ),
    p.DETECTOR_PUBLIC_IPS: (
        "2.0",
        "ed51fe15222b1f3d99022885f42c9c4a9446643aab75423d5d3f2524d8d195bc",
    ),
    p.DETECTOR_TELNETD: (
        "1.0",
        "05f33b81cd900f00e375b54fd20f67988f2a2f8aab66ffcee9c898cc122f706d",
    ),
    p.DETECTOR_DEBUG_ACCOUNT: (
        "2.0",
        "ae28ec239c50ce713689f1d05e4fb66bff0f8472174a948a59627a8f8165ce27",
    ),
    p.DETECTOR_OUTDATED_LIBSSL: (
        "1.0",
        "859b9199d1a33893bf4cc219ecad0350015913e3ad67db805ae39aa889a688ea",
    ),
    p.DETECTOR_OUTDATED_BUSYBOX: (
        "1.0",
        "06caca75534d5e215f03b6528733e1784f45b45d8d169d35d9f1e6e958bb32ef",
    ),
    p.DETECTOR_OUTDATED_DROPBEAR: (
        "2.0",
        "b5984c6e2598d30f21f42b5ab641a0c1a2e06a8a087361c0f43be2aa2d33b3e4",
    ),
    p.DETECTOR_URLS: (
        "1.0",
        "b52c02688f385a1042a85795312dd4de0991bdba42f09d8145cd9fbfae8831ce",
    ),
    p.DETECTOR_API_TOKENS: (
        "2.0",
        "e5eb0a2cb38af411f54c907380f94f49a7157585f4050d4f67ffd6803845e165",
    ),
    b.DETECTOR_CRYPTO_SIGNATURES: (
        "1.0",
        "dda8d8ace86e5d900b27d10524d3feefc342ab6f61e04ed2133fc7739ceb8ad6",
    ),
    b.DETECTOR_ENCRYPTED_SECTIONS: (
        "2.0",
        "106f58db1c84dd16465117c52f80cf19e499e6effcabd140894e307c5493f894",
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
