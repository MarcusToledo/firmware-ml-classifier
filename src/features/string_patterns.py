"""Pure regex-based security pattern detection over extracted ASCII strings.

All functions receive a ``list[str]`` of strings (as returned by
``extract_ascii_strings``) and return counts or boolean flags.
No external dependencies beyond the standard library.
"""
from __future__ import annotations

import re

# ---------------------------------------------------------------------------
# Password patterns
# ---------------------------------------------------------------------------

# Generic identifier=value / identifier:value scanner. The value stops at
# whitespace, "&" and ";" so that a rejected match earlier in a delimiter-free
# string (e.g. a URL query string) never swallows a real credential later in
# the same string. Whether a given key/value pair is actually a credential is
# decided afterwards by _is_credential_key() and _is_rejected_value().
_PASSWORD_KV_RE = re.compile(r"\b([A-Za-z][A-Za-z0-9_-]{0,40})\s*[=:]\s*([^\s&;]+)")

_CREDENTIAL_KEY_TOKENS: frozenset[str] = frozenset(
    {
        "password",
        "passwd",
        "pwd",
        "pass",
        "secret",
        "credential",
        "passphrase",
        "pswd",
        "psw",
        "userpass",
        "loginpass",
        "psk",
    }
)

# A key token from this set means the match describes *metadata about* a
# credential (its length, hash, rotation policy...) rather than the
# credential itself — e.g. password_length=8, password_hash=<digest>.
_METADATA_KEY_TOKENS: frozenset[str] = frozenset(
    {"length", "len", "size", "hash", "algorithm", "algo", "policy", "timeout"}
)

_NULL_LITERALS: frozenset[str] = frozenset(
    {"null", "none", "nil", "undefined", "(null)"}
)

_VARIABLE_REF_RE = re.compile(r"^\$\{?\w+\}?$")
_TEMPLATE_RE = re.compile(r"^\{\{?\w+\}?\}$|^<\w+>$")
_CAMEL_BOUNDARY_RE = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")

# TODO: Review passwords list and add more common default passwords if necessary
_DEFAULT_PASSWORDS: frozenset[str] = frozenset(
    {
        "admin",
        "password",
        "1234",
        "12345",
        "123456",
        "admin123",
        "root",
        "toor",
        "pass",
        "test",
        "1234567890",
        "guest",
        "default",
        "support",
        "supervisor",
        "service",
        "system",
        "ubnt",
        "huawei",
        "zte521",
        "telnet",
        "enable",
    }
)

_AUTH_CONTEXT_TRIGGERS: frozenset[str] = frozenset(
    {
        "login",
        "user",
        "username",
        "account",
        "credential",
        "auth",
        "senha",
        "password",
        "passwd",
        "pwd",
        "default",
    }
)

# ---------------------------------------------------------------------------
# Credential pair patterns (user:pass where both are weak defaults)
# ---------------------------------------------------------------------------

_CRED_PAIR_RE = re.compile(r"\b([A-Za-z0-9]{1,20}):([A-Za-z0-9]{1,20})\b")
_CRED_PAIR_WEAK: frozenset[str] = frozenset(
    {
        "admin",
        "root",
        "guest",
        "test",
        "default",
        "user",
        "support",
        "supervisor",
        "service",
        "system",
        "ubnt",
        "huawei",
        "zte521",
        "password",
        "1234",
        "12345",
        "123456",
        "admin123",
        "toor",
        "pass",
        "enable",
        "telnet",
    }
)

# ---------------------------------------------------------------------------
# IP address patterns
# ---------------------------------------------------------------------------

_IPV4_RE = re.compile(r"\b(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})\b")
_IP_EXCLUDES: frozenset[str] = frozenset({"0.0.0.0", "255.255.255.255"})

# ---------------------------------------------------------------------------
# Service / account patterns
# ---------------------------------------------------------------------------

_TELNETD_SUBSTR = "telnetd"
_DEBUG_ACCOUNT_RE = re.compile(r"\b(?:debug|guest|test)\b", re.IGNORECASE)

# ---------------------------------------------------------------------------
# Library version patterns
# ---------------------------------------------------------------------------

_LIBSSL_RE = re.compile(r"OpenSSL[\s/]+([\d]+\.[\d]+\.[\d]+[a-z]?)", re.IGNORECASE)
_BUSYBOX_RE = re.compile(r"BusyBox[\s_]*v?([\d]+\.[\d]+\.[\d]+)", re.IGNORECASE)
_DROPBEAR_RE = re.compile(r"Dropbear\s+(?:SSH\s+)?v?([\d]{4}\.[\d]+)", re.IGNORECASE)
_VERSION_THRESHOLDS: dict[str, tuple[int, ...]] = {
    "libssl": (1, 1, 1),  # < OpenSSL 1.1.1 → outdated
    "busybox": (1, 33, 0),  # < BusyBox 1.33.0 → outdated
    "dropbear": (2022, 82),  # < Dropbear 2022.82 → outdated
}

# ---------------------------------------------------------------------------
# URL and token patterns
# ---------------------------------------------------------------------------

_URL_RE = re.compile(r"https?://[^\s\"'<>]+", re.IGNORECASE)
_API_TOKEN_RE = re.compile(
    r"(?<![A-Za-z0-9])(?:[0-9a-fA-F]{32,}|[A-Za-z0-9+/=_\-]{32,})(?![A-Za-z0-9])"
)


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _parse_version(v: str) -> tuple[int, ...]:
    """Parse a dotted version string into a tuple of ints.

    Examples::

        _parse_version("1.1.1a") -> (1, 1, 1)
        _parse_version("2022.82") -> (2022, 82)
    """
    parts: list[int] = []
    for segment in re.split(r"[.\-_]", v):
        digits = re.match(r"(\d+)", segment)
        if digits:
            parts.append(int(digits.group(1)))
    return tuple(parts)


def _key_tokens(key: str) -> list[str]:
    """Split a key into lowercase tokens across snake_case/kebab-case/camelCase.

    Examples::

        _key_tokens("admin_password") -> ["admin", "password"]
        _key_tokens("adminPassword") -> ["admin", "password"]
        _key_tokens("wl0_wpa_psk") -> ["wl0", "wpa", "psk"]
    """
    spaced = _CAMEL_BOUNDARY_RE.sub("_", key)
    return [t.lower() for t in re.split(r"[_-]", spaced) if t]


def _is_credential_key(key: str) -> bool:
    """Return True if *key* denotes a credential value, not metadata about one."""
    tokens = set(_key_tokens(key))
    if tokens & _METADATA_KEY_TOKENS:
        return False
    return bool(tokens & _CREDENTIAL_KEY_TOKENS)


def _is_rejected_value(value: str) -> bool:
    """Return True if *value* is a placeholder, variable ref, template or null.

    These never represent a concrete, hardcoded credential.
    """
    if value.startswith("%"):
        return True
    if _VARIABLE_REF_RE.match(value):
        return True
    if _TEMPLATE_RE.match(value):
        return True
    if value.strip("()").lower() in _NULL_LITERALS:
        return True
    return False


def _has_plaintext_credential(s: str) -> bool:
    """Return True if *s* has a key=value pair with a concrete credential."""
    for m in _PASSWORD_KV_RE.finditer(s):
        key, value = m.group(1), m.group(2)
        if not _is_credential_key(key):
            continue
        if _is_rejected_value(value):
            continue
        return True
    return False


# ---------------------------------------------------------------------------
# Public functions
# ---------------------------------------------------------------------------


def count_hardcoded_passwords(strings: list[str]) -> int:
    """Count strings that contain hardcoded credentials.

    Counts key=value/key:value pairs with a concrete literal — rejecting
    format specifiers, variable references, templates, null literals and
    metadata keys (``password_length``, ``password_hash``) — plus bare
    occurrences of well-known default passwords (see
    ``_has_default_password_token``, added in Task 2).
    """
    count = 0
    for s in strings:
        if _has_plaintext_credential(s):
            count += 1
            continue
        tokens = s.split()
        if any(t.lower() in _DEFAULT_PASSWORDS for t in tokens):
            count += 1
    return count


def count_credential_pairs(strings: list[str]) -> int:
    """Count strings containing colon-separated weak credential pairs.

    Matches patterns like ``admin:admin`` or ``root:1234`` where both the
    username and password appear in the set of known default/weak values.
    Both sides must be 1–20 alphanumeric characters.  Counts per string,
    not per token — a string with multiple pairs is counted once.
    """
    count = 0
    for s in strings:
        for m in _CRED_PAIR_RE.finditer(s):
            if (
                m.group(1).lower() in _CRED_PAIR_WEAK
                and m.group(2).lower() in _CRED_PAIR_WEAK
            ):
                count += 1
                break
    return count


def count_hardcoded_ips(strings: list[str]) -> int:
    """Count strings that contain valid non-excluded IPv4 addresses."""
    count = 0
    for s in strings:
        for m in _IPV4_RE.finditer(s):
            octets = tuple(int(g) for g in m.groups())
            if any(o > 255 for o in octets):
                continue
            ip = ".".join(str(o) for o in octets)
            if ip in _IP_EXCLUDES:
                continue
            # Exclude loopback (127.x.x.x)
            if octets[0] == 127:
                continue
            count += 1
    return count


def count_public_ips(strings: list[str]) -> int:
    """Count strings containing hardcoded public (non-RFC-1918) IPv4 addresses.

    Excludes loopback (127.x), link-local (169.254.x), RFC-1918 private
    ranges (10.x, 172.16-31.x, 192.168.x), multicast (224-239.x),
    reserved (240+), and broadcast/all-zeros.  Public IPs hardcoded in
    firmware are high-confidence indicators of C2 or telemetry endpoints.
    """
    count = 0
    for s in strings:
        for m in _IPV4_RE.finditer(s):
            a, b, c, d = (int(g) for g in m.groups())
            if any(o > 255 for o in (a, b, c, d)):
                continue
            ip = f"{a}.{b}.{c}.{d}"
            if ip in _IP_EXCLUDES:
                continue
            if a == 127:
                continue  # loopback
            if a == 10:
                continue  # RFC-1918 /8
            if a == 172 and 16 <= b <= 31:
                continue  # RFC-1918 /12
            if a == 192 and b == 168:
                continue  # RFC-1918 /16
            if a == 169 and b == 254:
                continue  # link-local
            if 224 <= a <= 239:
                continue  # multicast
            if a >= 240:
                continue  # reserved / class E
            count += 1
    return count


def has_telnetd(strings: list[str]) -> bool:
    """Return True if any string contains the substring 'telnetd'."""
    return any(_TELNETD_SUBSTR in s for s in strings)


def has_debug_account(strings: list[str]) -> bool:
    """Return True if any string contains a debug/guest/test account name."""
    return any(_DEBUG_ACCOUNT_RE.search(s) for s in strings)


def has_outdated_libssl(strings: list[str]) -> bool:
    """Return True if an OpenSSL version string below threshold is found."""
    threshold = _VERSION_THRESHOLDS["libssl"]
    for s in strings:
        m = _LIBSSL_RE.search(s)
        if m:
            version = _parse_version(m.group(1))
            if version < threshold:
                return True
    return False


def has_outdated_busybox(strings: list[str]) -> bool:
    """Return True if a BusyBox version string below threshold is found."""
    threshold = _VERSION_THRESHOLDS["busybox"]
    for s in strings:
        m = _BUSYBOX_RE.search(s)
        if m:
            version = _parse_version(m.group(1))
            if version < threshold:
                return True
    return False


def has_outdated_dropbear(strings: list[str]) -> bool:
    """Return True if a Dropbear version string below threshold is found."""
    threshold = _VERSION_THRESHOLDS["dropbear"]
    for s in strings:
        m = _DROPBEAR_RE.search(s)
        if m:
            version = _parse_version(m.group(1))
            if version < threshold:
                return True
    return False


def count_urls(strings: list[str]) -> int:
    """Count HTTP/HTTPS URLs found across all strings."""
    count = 0
    for s in strings:
        count += len(_URL_RE.findall(s))
    return count


def count_api_tokens(strings: list[str]) -> int:
    """Count long hex or base64-like tokens (32+ chars) across all strings."""
    count = 0
    for s in strings:
        count += len(_API_TOKEN_RE.findall(s))
    return count


def scan_strings(strings: list[str]) -> dict[str, int | bool]:
    """Run all pattern checks and return a flat feature dict.

    Keys returned:
        count_hardcoded_passwords, count_credential_pairs,
        count_hardcoded_ips, count_public_ips,
        has_telnetd, has_debug_account,
        has_outdated_libssl, has_outdated_busybox, has_outdated_dropbear,
        count_urls, count_api_tokens
    """
    return {
        "count_hardcoded_passwords": count_hardcoded_passwords(strings),
        "count_credential_pairs": count_credential_pairs(strings),
        "count_hardcoded_ips": count_hardcoded_ips(strings),
        "count_public_ips": count_public_ips(strings),
        "has_telnetd": has_telnetd(strings),
        "has_debug_account": has_debug_account(strings),
        "has_outdated_libssl": has_outdated_libssl(strings),
        "has_outdated_busybox": has_outdated_busybox(strings),
        "has_outdated_dropbear": has_outdated_dropbear(strings),
        "count_urls": count_urls(strings),
        "count_api_tokens": count_api_tokens(strings),
    }
