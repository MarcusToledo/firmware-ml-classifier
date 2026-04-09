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

_PASSWORD_KV_RE = re.compile(
    r"\b(?:password|passwd|pass|pwd|secret|credential)\s*[=:]\s*(\S+)",
    re.IGNORECASE,
)
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

_LIBSSL_RE = re.compile(r"OpenSSL\s+([\d]+\.[\d]+\.[\d]+[a-z]?)", re.IGNORECASE)
_BUSYBOX_RE = re.compile(r"BusyBox\s+v?([\d]+\.[\d]+\.[\d]+)", re.IGNORECASE)
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
    for segment in re.split(r"[.\-]", v):
        digits = re.match(r"(\d+)", segment)
        if digits:
            parts.append(int(digits.group(1)))
    return tuple(parts)


# ---------------------------------------------------------------------------
# Public functions
# ---------------------------------------------------------------------------


def count_hardcoded_passwords(strings: list[str]) -> int:
    """Count strings that contain hardcoded credentials.

    Counts both key=value patterns (``password=admin``) and bare occurrences
    of well-known default passwords.
    """
    count = 0
    for s in strings:
        # key=value match
        m = _PASSWORD_KV_RE.search(s)
        if m:
            count += 1
            continue
        # exact token match against known defaults
        tokens = s.split()
        if any(t.lower() in _DEFAULT_PASSWORDS for t in tokens):
            count += 1
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
        count_hardcoded_passwords, count_hardcoded_ips,
        has_telnetd, has_debug_account,
        has_outdated_libssl, has_outdated_busybox, has_outdated_dropbear,
        count_urls, count_api_tokens
    """
    return {
        "count_hardcoded_passwords": count_hardcoded_passwords(strings),
        "count_hardcoded_ips": count_hardcoded_ips(strings),
        "has_telnetd": has_telnetd(strings),
        "has_debug_account": has_debug_account(strings),
        "has_outdated_libssl": has_outdated_libssl(strings),
        "has_outdated_busybox": has_outdated_busybox(strings),
        "has_outdated_dropbear": has_outdated_dropbear(strings),
        "count_urls": count_urls(strings),
        "count_api_tokens": count_api_tokens(strings),
    }
