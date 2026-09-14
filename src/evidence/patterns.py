"""Security evidence detectors over already-extracted ASCII strings.

Every function here consumes a ``list[str]`` of strings (as returned by
``src.features.strings.extract_ascii_strings``) — it never re-extracts
strings from a firmware image itself, only interprets what
``src/features/*`` already extracted. Each detector exposes two views of
the same match: a ``find_*`` function returning structured
``SecurityFinding`` objects (for audit and per-detector precision/recall
evaluation), and a ``count_*``/``has_*`` function returning the flat
count/flag used as a classifier feature.
"""

from __future__ import annotations

import re

from src.evidence.findings import SecurityFinding

_DETECTOR_VERSION = "1.0"

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


def find_hardcoded_passwords(strings: list[str]) -> list[SecurityFinding]:
    """Find strings that contain hardcoded credentials.

    Matches both key=value patterns (``password=admin``, high confidence)
    and bare occurrences of well-known default passwords (medium
    confidence). At most one finding per string, mirroring the original
    count semantics.
    """
    findings: list[SecurityFinding] = []
    for s in strings:
        m = _PASSWORD_KV_RE.search(s)
        if m:
            findings.append(
                SecurityFinding(
                    type="credential_candidate",
                    source=s,
                    context=f"key=value assignment: {m.group(0)!r}",
                    confidence="high",
                    detector="hardcoded_passwords",
                    detector_version=_DETECTOR_VERSION,
                )
            )
            continue
        tokens = s.split()
        matched = next((t for t in tokens if t.lower() in _DEFAULT_PASSWORDS), None)
        if matched is not None:
            findings.append(
                SecurityFinding(
                    type="credential_candidate",
                    source=s,
                    context=f"default password token: {matched!r}",
                    confidence="medium",
                    detector="hardcoded_passwords",
                    detector_version=_DETECTOR_VERSION,
                )
            )
    return findings


def count_hardcoded_passwords(strings: list[str]) -> int:
    """Count strings that contain hardcoded credentials."""
    return len(find_hardcoded_passwords(strings))


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


def find_credential_pairs(strings: list[str]) -> list[SecurityFinding]:
    """Find strings containing colon-separated weak credential pairs.

    Matches patterns like ``admin:admin`` or ``root:1234`` where both
    sides are in the known weak/default set. At most one finding per
    string (a string with multiple pairs still counts once), mirroring
    the original count semantics.
    """
    findings: list[SecurityFinding] = []
    for s in strings:
        for m in _CRED_PAIR_RE.finditer(s):
            if (
                m.group(1).lower() in _CRED_PAIR_WEAK
                and m.group(2).lower() in _CRED_PAIR_WEAK
            ):
                findings.append(
                    SecurityFinding(
                        type="credential_pair",
                        source=s,
                        context=f"weak user:pass pair: {m.group(0)!r}",
                        confidence="high",
                        detector="credential_pairs",
                        detector_version=_DETECTOR_VERSION,
                    )
                )
                break
    return findings


def count_credential_pairs(strings: list[str]) -> int:
    """Count strings containing colon-separated weak credential pairs."""
    return len(find_credential_pairs(strings))


# ---------------------------------------------------------------------------
# IP address patterns
# ---------------------------------------------------------------------------

_IPV4_RE = re.compile(r"\b(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})\b")
_IP_EXCLUDES: frozenset[str] = frozenset({"0.0.0.0", "255.255.255.255"})


def find_hardcoded_ips(strings: list[str]) -> list[SecurityFinding]:
    """Find strings that contain valid non-excluded IPv4 addresses."""
    findings: list[SecurityFinding] = []
    for s in strings:
        for m in _IPV4_RE.finditer(s):
            octets = tuple(int(g) for g in m.groups())
            if any(o > 255 for o in octets):
                continue
            ip = ".".join(str(o) for o in octets)
            if ip in _IP_EXCLUDES:
                continue
            if octets[0] == 127:
                continue
            findings.append(
                SecurityFinding(
                    type="hardcoded_ip",
                    source=s,
                    context=f"IPv4 address: {ip}",
                    confidence="low",
                    detector="hardcoded_ips",
                    detector_version=_DETECTOR_VERSION,
                )
            )
    return findings


def count_hardcoded_ips(strings: list[str]) -> int:
    """Count strings that contain valid non-excluded IPv4 addresses."""
    return len(find_hardcoded_ips(strings))


def find_public_ips(strings: list[str]) -> list[SecurityFinding]:
    """Find strings containing hardcoded public (non-RFC-1918) IPv4 addresses.

    Excludes loopback, link-local, RFC-1918 private ranges, multicast and
    reserved/broadcast. Public IPs hardcoded in firmware are high-confidence
    indicators of C2 or telemetry endpoints.
    """
    findings: list[SecurityFinding] = []
    for s in strings:
        for m in _IPV4_RE.finditer(s):
            a, b, c, d = (int(g) for g in m.groups())
            if any(o > 255 for o in (a, b, c, d)):
                continue
            ip = f"{a}.{b}.{c}.{d}"
            if ip in _IP_EXCLUDES:
                continue
            if a == 127:
                continue
            if a == 10:
                continue
            if a == 172 and 16 <= b <= 31:
                continue
            if a == 192 and b == 168:
                continue
            if a == 169 and b == 254:
                continue
            if 224 <= a <= 239:
                continue
            if a >= 240:
                continue
            findings.append(
                SecurityFinding(
                    type="public_ip",
                    source=s,
                    context=f"public (non-RFC-1918) IPv4 address: {ip}",
                    confidence="high",
                    detector="public_ips",
                    detector_version=_DETECTOR_VERSION,
                )
            )
    return findings


def count_public_ips(strings: list[str]) -> int:
    """Count strings containing hardcoded public (non-RFC-1918) IPv4 addresses."""
    return len(find_public_ips(strings))


# ---------------------------------------------------------------------------
# Service / account patterns
# ---------------------------------------------------------------------------

_TELNETD_SUBSTR = "telnetd"
_DEBUG_ACCOUNT_RE = re.compile(r"\b(?:debug|guest|test)\b", re.IGNORECASE)


def find_telnetd(strings: list[str]) -> list[SecurityFinding]:
    """Find strings that contain the substring 'telnetd'."""
    return [
        SecurityFinding(
            type="exposed_service",
            source=s,
            context=f"{_TELNETD_SUBSTR!r} substring found",
            confidence="high",
            detector="telnetd",
            detector_version=_DETECTOR_VERSION,
        )
        for s in strings
        if _TELNETD_SUBSTR in s
    ]


def has_telnetd(strings: list[str]) -> bool:
    """Return True if any string contains the substring 'telnetd'."""
    return bool(find_telnetd(strings))


def find_debug_account(strings: list[str]) -> list[SecurityFinding]:
    """Find strings that contain a debug/guest/test account keyword."""
    findings: list[SecurityFinding] = []
    for s in strings:
        m = _DEBUG_ACCOUNT_RE.search(s)
        if m:
            findings.append(
                SecurityFinding(
                    type="debug_account",
                    source=s,
                    context=f"debug/guest/test keyword: {m.group(0)!r}",
                    confidence="low",
                    detector="debug_account",
                    detector_version=_DETECTOR_VERSION,
                )
            )
    return findings


def has_debug_account(strings: list[str]) -> bool:
    """Return True if any string contains a debug/guest/test account name."""
    return bool(find_debug_account(strings))


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


def _find_outdated_version(
    strings: list[str],
    pattern: re.Pattern[str],
    lib_name: str,
    detector: str,
) -> list[SecurityFinding]:
    """Shared scan used by the three outdated-library detectors below."""
    threshold = _VERSION_THRESHOLDS[lib_name]
    findings: list[SecurityFinding] = []
    for s in strings:
        m = pattern.search(s)
        if m:
            version = _parse_version(m.group(1))
            if version < threshold:
                findings.append(
                    SecurityFinding(
                        type="outdated_library",
                        source=s,
                        context=(
                            f"{lib_name} version {m.group(1)} "
                            f"below threshold {threshold}"
                        ),
                        confidence="medium",
                        detector=detector,
                        detector_version=_DETECTOR_VERSION,
                    )
                )
    return findings


def find_outdated_libssl(strings: list[str]) -> list[SecurityFinding]:
    """Find strings with an OpenSSL version string below threshold."""
    return _find_outdated_version(strings, _LIBSSL_RE, "libssl", "outdated_libssl")


def has_outdated_libssl(strings: list[str]) -> bool:
    """Return True if an OpenSSL version string below threshold is found."""
    return bool(find_outdated_libssl(strings))


def find_outdated_busybox(strings: list[str]) -> list[SecurityFinding]:
    """Find strings with a BusyBox version string below threshold."""
    return _find_outdated_version(strings, _BUSYBOX_RE, "busybox", "outdated_busybox")


def has_outdated_busybox(strings: list[str]) -> bool:
    """Return True if a BusyBox version string below threshold is found."""
    return bool(find_outdated_busybox(strings))


def find_outdated_dropbear(strings: list[str]) -> list[SecurityFinding]:
    """Find strings with a Dropbear version string below threshold."""
    return _find_outdated_version(
        strings, _DROPBEAR_RE, "dropbear", "outdated_dropbear"
    )


def has_outdated_dropbear(strings: list[str]) -> bool:
    """Return True if a Dropbear version string below threshold is found."""
    return bool(find_outdated_dropbear(strings))


# ---------------------------------------------------------------------------
# URL and token patterns
# ---------------------------------------------------------------------------

_URL_RE = re.compile(r"https?://[^\s\"'<>]+", re.IGNORECASE)
_API_TOKEN_RE = re.compile(
    r"(?<![A-Za-z0-9])(?:[0-9a-fA-F]{32,}|[A-Za-z0-9+/=_\-]{32,})(?![A-Za-z0-9])"
)


def find_urls(strings: list[str]) -> list[SecurityFinding]:
    """Find HTTP/HTTPS URLs across all strings."""
    findings: list[SecurityFinding] = []
    for s in strings:
        for m in _URL_RE.finditer(s):
            findings.append(
                SecurityFinding(
                    type="url",
                    source=s,
                    context=f"URL: {m.group(0)}",
                    confidence="low",
                    detector="urls",
                    detector_version=_DETECTOR_VERSION,
                )
            )
    return findings


def count_urls(strings: list[str]) -> int:
    """Count HTTP/HTTPS URLs found across all strings."""
    return len(find_urls(strings))


def find_api_tokens(strings: list[str]) -> list[SecurityFinding]:
    """Find long hex or base64-like tokens (32+ chars) across all strings."""
    findings: list[SecurityFinding] = []
    for s in strings:
        for m in _API_TOKEN_RE.finditer(s):
            findings.append(
                SecurityFinding(
                    type="api_token_candidate",
                    source=s,
                    context=f"long token: {m.group(0)[:12]}…",
                    confidence="low",
                    detector="api_tokens",
                    detector_version=_DETECTOR_VERSION,
                )
            )
    return findings


def count_api_tokens(strings: list[str]) -> int:
    """Count long hex or base64-like tokens (32+ chars) across all strings."""
    return len(find_api_tokens(strings))


# ---------------------------------------------------------------------------
# Aggregate scan: structured findings and flat counts
# ---------------------------------------------------------------------------

_COUNT_DETECTORS: dict[str, str] = {
    "hardcoded_passwords": "count_hardcoded_passwords",
    "credential_pairs": "count_credential_pairs",
    "hardcoded_ips": "count_hardcoded_ips",
    "public_ips": "count_public_ips",
    "urls": "count_urls",
    "api_tokens": "count_api_tokens",
}

_BOOL_DETECTORS: dict[str, str] = {
    "telnetd": "has_telnetd",
    "debug_account": "has_debug_account",
    "outdated_libssl": "has_outdated_libssl",
    "outdated_busybox": "has_outdated_busybox",
    "outdated_dropbear": "has_outdated_dropbear",
}


def scan_strings_findings(strings: list[str]) -> list[SecurityFinding]:
    """Run every detector over ``strings`` and return all findings.

    This is the auditable output: every match, with source/context/
    confidence, for manual review and per-detector precision/recall
    evaluation.
    """
    findings: list[SecurityFinding] = []
    findings.extend(find_hardcoded_passwords(strings))
    findings.extend(find_credential_pairs(strings))
    findings.extend(find_hardcoded_ips(strings))
    findings.extend(find_public_ips(strings))
    findings.extend(find_telnetd(strings))
    findings.extend(find_debug_account(strings))
    findings.extend(find_outdated_libssl(strings))
    findings.extend(find_outdated_busybox(strings))
    findings.extend(find_outdated_dropbear(strings))
    findings.extend(find_urls(strings))
    findings.extend(find_api_tokens(strings))
    return findings


def findings_to_counts(findings: list[SecurityFinding]) -> dict[str, int | bool]:
    """Reduce structured findings to the flat counts/flags used as features."""
    counts: dict[str, int | bool] = {key: 0 for key in _COUNT_DETECTORS.values()}
    counts.update({key: False for key in _BOOL_DETECTORS.values()})
    for finding in findings:
        if finding.detector in _COUNT_DETECTORS:
            key = _COUNT_DETECTORS[finding.detector]
            counts[key] = int(counts[key]) + 1
        elif finding.detector in _BOOL_DETECTORS:
            counts[_BOOL_DETECTORS[finding.detector]] = True
    return counts


def scan_strings(strings: list[str]) -> dict[str, int | bool]:
    """Run all pattern checks and return a flat feature dict.

    Backward-compatible view over ``scan_strings_findings`` +
    ``findings_to_counts`` — same keys/semantics as the pre-evidence-layer
    implementation. Keys returned:
        count_hardcoded_passwords, count_credential_pairs,
        count_hardcoded_ips, count_public_ips,
        has_telnetd, has_debug_account,
        has_outdated_libssl, has_outdated_busybox, has_outdated_dropbear,
        count_urls, count_api_tokens
    """
    return findings_to_counts(scan_strings_findings(strings))
