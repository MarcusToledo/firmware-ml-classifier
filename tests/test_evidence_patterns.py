import pytest

from src.evidence.patterns import (
    count_api_tokens,
    count_credential_pairs,
    count_hardcoded_passwords,
    count_non_public_ips,
    count_public_ips,
    count_urls,
    find_api_tokens,
    find_credential_pairs,
    find_debug_account,
    find_hardcoded_passwords,
    find_non_public_ips,
    find_outdated_libssl,
    find_public_ips,
    find_telnetd,
    find_urls,
    findings_to_counts,
    has_debug_account,
    has_outdated_busybox,
    has_outdated_dropbear,
    has_outdated_libssl,
    has_telnetd,
    scan_strings,
    scan_strings_findings,
)

# ---------------------------------------------------------------------------
# find_hardcoded_passwords / count_hardcoded_passwords
# ---------------------------------------------------------------------------


def test_passwords_empty() -> None:
    assert count_hardcoded_passwords([]) == 0
    assert find_hardcoded_passwords([]) == []


def test_passwords_kv_match() -> None:
    assert count_hardcoded_passwords(["password=secret123"]) == 1


def test_passwords_kv_colon() -> None:
    assert count_hardcoded_passwords(["passwd: admin"]) == 1


def test_passwords_kv_case_insensitive() -> None:
    assert count_hardcoded_passwords(["PASSWORD=abc"]) == 1


def test_passwords_default_token_without_context() -> None:
    assert count_hardcoded_passwords(["admin", "root", " -- System halted"]) == 0


def test_passwords_no_match() -> None:
    assert count_hardcoded_passwords(["network interface eth0"]) == 0


def test_passwords_multiple_strings() -> None:
    strings = ["password=abc", "some normal string", "pwd: toor"]
    assert count_hardcoded_passwords(strings) == 2


def test_passwords_finding_has_high_confidence_on_kv_match() -> None:
    findings = find_hardcoded_passwords(["password=secret123"])
    assert len(findings) == 1
    assert findings[0].confidence == "high"
    assert findings[0].detector == "hardcoded_passwords"
    assert findings[0].source == "password=secret123"


def test_passwords_finding_has_medium_confidence_on_default_token() -> None:
    findings = find_hardcoded_passwords(["default login admin"])
    assert len(findings) == 1
    assert findings[0].confidence == "medium"


# ---------------------------------------------------------------------------
# find_credential_pairs / count_credential_pairs
# ---------------------------------------------------------------------------


def test_cred_pairs_empty() -> None:
    assert count_credential_pairs([]) == 0
    assert find_credential_pairs([]) == []


def test_cred_pairs_admin_admin() -> None:
    assert count_credential_pairs(["admin:admin"]) == 1


def test_cred_pairs_root_1234() -> None:
    assert count_credential_pairs(["root:1234"]) == 1


def test_cred_pairs_non_weak_ignored() -> None:
    assert count_credential_pairs(["john:complexpassword"]) == 0


def test_cred_pairs_long_hash_ignored() -> None:
    assert count_credential_pairs(["sha256:deadbeefdeadbeefdeadbeef"]) == 0


def test_cred_pairs_multiple_strings() -> None:
    assert count_credential_pairs(["admin:admin", "root:root", "guest:guest"]) == 3


def test_cred_pairs_multiple_in_one_string_counts_once() -> None:
    assert count_credential_pairs(["admin:admin root:root"]) == 1


def test_cred_pairs_finding_has_high_confidence() -> None:
    findings = find_credential_pairs(["admin:admin"])
    assert len(findings) == 1
    assert findings[0].confidence == "high"
    assert findings[0].detector == "credential_pairs"


# ---------------------------------------------------------------------------
# find_non_public_ips / count_non_public_ips
# ---------------------------------------------------------------------------


def test_ips_empty() -> None:
    assert count_non_public_ips([]) == 0


def test_ips_valid_match() -> None:
    assert count_non_public_ips(["server at 192.168.1.1"]) == 1


def test_ips_rejects_hostname_suffix() -> None:
    assert count_non_public_ips(["https://8.8.8.8.example/"]) == 0
    assert count_non_public_ips(["ip 8.8.8.8.foo"]) == 0


def test_ips_multiple() -> None:
    assert count_non_public_ips(["ip 10.0.0.1 and 172.16.0.2"]) == 2


def test_ips_excludes_broadcast() -> None:
    assert count_non_public_ips(["255.255.255.255"]) == 0


def test_ips_excludes_all_zeros() -> None:
    assert count_non_public_ips(["0.0.0.0"]) == 0


def test_ips_excludes_loopback() -> None:
    assert count_non_public_ips(["127.0.0.1"]) == 0


def test_ips_invalid_octet() -> None:
    assert count_non_public_ips(["999.0.0.1"]) == 0


def test_ips_invalid_octet_256() -> None:
    assert count_non_public_ips(["192.168.1.256"]) == 0


def test_ips_no_match() -> None:
    assert count_non_public_ips(["version 1.2.3"]) == 0


def test_ips_finding_has_low_confidence() -> None:
    findings = find_non_public_ips(["host 192.168.1.1"])
    assert len(findings) == 1
    assert findings[0].confidence == "low"
    assert findings[0].detector == "non_public_ips"


@pytest.mark.parametrize(
    "text,non_public,public",
    [
        ("server 192.168.1.1", 1, 0),
        ("gateway 100.64.0.1", 1, 0),
        ("server 203.0.113.5", 1, 0),
        ("group 224.0.0.1:5353", 1, 0),
        ("dns 8.8.8.8", 0, 1),
        ("dns 8.8.8.8 gateway 10.0.0.1", 1, 1),
    ],
)
def test_non_public_and_public_ips_are_disjoint(
    text: str, non_public: int, public: int
) -> None:
    result = scan_strings([text])
    assert result["count_non_public_ips"] == non_public
    assert result["count_public_ips"] == public


# ---------------------------------------------------------------------------
# find_public_ips / count_public_ips
# ---------------------------------------------------------------------------


def test_public_ips_empty() -> None:
    assert count_public_ips([]) == 0


def test_public_ips_routable() -> None:
    assert count_public_ips(["dns server 8.8.8.8"]) == 1


def test_public_ips_accepts_sentence_period() -> None:
    assert count_public_ips(["connect to server 8.8.8.8."]) == 1


def test_public_ips_c2_candidate() -> None:
    assert count_public_ips(["remote 45.33.32.156"]) == 1


def test_public_ips_ignores_private_10() -> None:
    assert count_public_ips(["10.0.0.1"]) == 0


def test_public_ips_ignores_private_192_168() -> None:
    assert count_public_ips(["192.168.1.1"]) == 0


def test_public_ips_ignores_rfc1918_172() -> None:
    assert count_public_ips(["172.16.0.1", "172.31.255.255"]) == 0


def test_public_ips_172_32_is_public() -> None:
    assert count_public_ips(["host 172.32.0.1"]) == 1


def test_public_ips_ignores_link_local() -> None:
    assert count_public_ips(["169.254.1.1"]) == 0


def test_public_ips_ignores_multicast() -> None:
    assert count_public_ips(["224.0.0.1"]) == 0


def test_public_ips_ignores_cgnat_and_documentation() -> None:
    assert count_public_ips(["gateway 100.64.0.1"]) == 0
    assert count_public_ips(["server 203.0.113.5"]) == 0


def test_public_ips_multiple_in_one_string() -> None:
    assert count_public_ips(["dns server 8.8.8.8 and 1.1.1.1"]) == 2


def test_public_ips_finding_has_high_confidence() -> None:
    findings = find_public_ips(["dns 8.8.8.8"])
    assert len(findings) == 1
    assert findings[0].confidence == "high"
    assert findings[0].detector == "public_ips"


# ---------------------------------------------------------------------------
# find_telnetd / has_telnetd
# ---------------------------------------------------------------------------


def test_telnetd_empty() -> None:
    assert has_telnetd([]) is False


def test_telnetd_true() -> None:
    assert has_telnetd(["/usr/sbin/telnetd -l /bin/sh"]) is True


def test_telnetd_false() -> None:
    assert has_telnetd(["telnet 192.168.1.1"]) is False


def test_telnetd_substring() -> None:
    assert has_telnetd(["start_telnetd"]) is True


def test_telnetd_finding_has_high_confidence() -> None:
    findings = find_telnetd(["telnetd"])
    assert len(findings) == 1
    assert findings[0].confidence == "high"
    assert findings[0].detector == "telnetd"


# ---------------------------------------------------------------------------
# find_debug_account / has_debug_account
# ---------------------------------------------------------------------------


def test_debug_account_empty() -> None:
    assert has_debug_account([]) is False


@pytest.mark.parametrize("name", ["debug", "guest", "test", "DEBUG"])
def test_debug_account_requires_auth_context(name: str) -> None:
    assert has_debug_account([name, "mtest   - simple RAM test"]) is False
    assert has_debug_account([f"login: {name}"]) is True


def test_debug_account_no_partial_match() -> None:
    assert has_debug_account(["testuser"]) is False


def test_debug_account_no_match() -> None:
    assert has_debug_account(["admin root supervisor"]) is False


def test_debug_account_finding_has_low_confidence() -> None:
    findings = find_debug_account(["login: debug"])
    assert len(findings) == 1
    assert findings[0].confidence == "low"
    assert findings[0].detector == "debug_account"


# ---------------------------------------------------------------------------
# find_outdated_libssl / has_outdated_libssl
# ---------------------------------------------------------------------------


def test_libssl_empty() -> None:
    assert has_outdated_libssl([]) is False


def test_libssl_outdated() -> None:
    assert has_outdated_libssl(["OpenSSL 1.0.2k"]) is True


def test_libssl_outdated_1_1_0() -> None:
    assert has_outdated_libssl(["OpenSSL 1.1.0h"]) is True


def test_libssl_current() -> None:
    assert has_outdated_libssl(["OpenSSL 1.1.1n"]) is False


def test_libssl_newer() -> None:
    assert has_outdated_libssl(["OpenSSL 3.0.0"]) is False


def test_libssl_no_match() -> None:
    assert has_outdated_libssl(["libc version 2.31"]) is False


def test_libssl_slash_separator() -> None:
    assert has_outdated_libssl(["Apache/2.2.31 OpenSSL/1.0.2k"]) is True


def test_libssl_finding_has_medium_confidence() -> None:
    findings = find_outdated_libssl(["OpenSSL 1.0.2k"])
    assert len(findings) == 1
    assert findings[0].confidence == "medium"
    assert findings[0].detector == "outdated_libssl"


# ---------------------------------------------------------------------------
# find_outdated_busybox / has_outdated_busybox
# ---------------------------------------------------------------------------


def test_busybox_empty() -> None:
    assert has_outdated_busybox([]) is False


def test_busybox_outdated() -> None:
    assert has_outdated_busybox(["BusyBox v1.30.1"]) is True


def test_busybox_current() -> None:
    assert has_outdated_busybox(["BusyBox v1.33.0"]) is False


def test_busybox_newer() -> None:
    assert has_outdated_busybox(["BusyBox v1.36.1"]) is False


def test_busybox_no_match() -> None:
    assert has_outdated_busybox(["kernel 5.15.0"]) is False


def test_busybox_no_space_variant() -> None:
    assert has_outdated_busybox(["BusyBox1.19.4"]) is True


def test_busybox_underscore_separator() -> None:
    assert has_outdated_busybox(["busybox_1.19.4"]) is True


# ---------------------------------------------------------------------------
# find_outdated_dropbear / has_outdated_dropbear
# ---------------------------------------------------------------------------


def test_dropbear_empty() -> None:
    assert has_outdated_dropbear([]) is False


def test_dropbear_outdated() -> None:
    assert has_outdated_dropbear(["Dropbear SSH 2020.81"]) is True


def test_dropbear_current() -> None:
    assert has_outdated_dropbear(["Dropbear SSH 2022.82"]) is False


def test_dropbear_newer() -> None:
    assert has_outdated_dropbear(["Dropbear 2023.1"]) is False


def test_dropbear_no_match() -> None:
    assert has_outdated_dropbear(["openssh 8.9"]) is False


# ---------------------------------------------------------------------------
# find_urls / count_urls
# ---------------------------------------------------------------------------


def test_urls_empty() -> None:
    assert count_urls([]) == 0


def test_urls_http() -> None:
    assert count_urls(["http://example.com/path"]) == 1


def test_urls_https() -> None:
    assert count_urls(["https://secure.example.com"]) == 1


def test_urls_multiple_in_one_string() -> None:
    assert count_urls(["http://a.com https://b.com"]) == 2


def test_urls_no_match() -> None:
    assert count_urls(["ftp://example.com"]) == 0


def test_urls_finding_has_low_confidence() -> None:
    findings = find_urls(["http://example.com"])
    assert len(findings) == 1
    assert findings[0].confidence == "low"
    assert findings[0].detector == "urls"


# ---------------------------------------------------------------------------
# find_api_tokens / count_api_tokens
# ---------------------------------------------------------------------------


def test_tokens_empty() -> None:
    assert count_api_tokens([]) == 0


def test_tokens_hex_32_chars() -> None:
    assert count_api_tokens(["abc123" + "0" * 26]) == 1


def test_tokens_do_not_match_prefix_before_base64_suffix() -> None:
    assert find_api_tokens(["a" * 32 + "+x"]) == []
    assert find_api_tokens(["a" * 32 + "/Zk9"]) == []


def test_tokens_still_match_isolated_hex() -> None:
    assert len(find_api_tokens(["key " + "f3a9c1e07b5d2846" * 2])) == 1


def test_tokens_too_short() -> None:
    assert count_api_tokens(["a" * 31]) == 0


def test_tokens_no_match() -> None:
    assert count_api_tokens(["short string"]) == 0


_REPORT_PASSWORD_CASES = [
    ("password=%s", 0),
    ("password=%.*s", 0),
    ("password=${PASSWORD}", 0),
    ("password=$1", 0),
    ("password={{password}}", 0),
    ("password=<password>", 0),
    ("password=NULL", 0),
    ("password=None", 0),
    ("password=(null)", 0),
    ("password_length=8", 0),
    ("password_hash=5f4dcc3b5aa765d61d8327deb882cf99", 0),
    ("Password authentication failed", 0),
    ("setPassword", 0),
    ("/etc/passwd", 0),
    ("passwd.c", 0),
    ("confirm password", 0),
    ("wpa_psk=12345678", 1),
    ("wl0_wpa_psk=12345678", 1),
    ("ftp_pass=admin123", 1),
    ("adminPassword=admin123", 1),
    ("admin_password=admin123", 1),
    ("http://x/?mode=auto&password=admin", 1),
]


@pytest.mark.parametrize("text,expected", _REPORT_PASSWORD_CASES)
def test_password_regression(text: str, expected: int) -> None:
    assert count_hardcoded_passwords([text]) == expected


@pytest.mark.parametrize(
    "text,expected",
    [
        ("7.0.1.0", 0),
        ("version 7.0.1.0", 0),
        ("Linux-2.6.22.18", 0),
        ("255.255.255.0", 0),
        ("ip 0.0.0.1", 0),
        ("host 255.1.2.3", 0),
        ("ip 8.8.8.8-extra", 0),
        ("ip 8.8.8.8_abc", 0),
        ("ip 8.8.8.8.9", 0),
        ("dns server 8.8.8.8", 1),
        ("https://8.8.8.8/", 0),
        ("mirror https://example.com/ 8.8.8.8", 1),
        ("8.8.8.8:443", 1),
    ],
)
def test_ips_network_context_and_boundaries(text: str, expected: int) -> None:
    assert count_public_ips([text]) == expected


@pytest.mark.parametrize(
    "text,expected",
    [
        ("WLAN_ABandRegion0_ChannelselectItems_3", 0),
        ("0123456789abcdefghijklmnopqrstuvwxyz", 0),
        ("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/", 0),
        ("abc123" + "0" * 26, 1),
        ("Ab7kQr2mNz9pXv4tYw6sDc8hJf3lGp5uBa0e", 0),
        ("ObroVR5fBbnGbmPIoLZaZSvj9vfg2MZUI+yJ1N3KTcosfogr", 1),
    ],
)
def test_api_token_candidates(text: str, expected: int) -> None:
    assert count_api_tokens([text]) == expected


def test_password_kv_precedes_token_and_counts_once() -> None:
    finding = find_hardcoded_passwords(
        ["default login admin password=${PASS}&wifi_psk=s3cr3tKey"]
    )
    assert len(finding) == 1
    assert finding[0].confidence == "high"
    assert "wifi_psk=s3cr3tKey" in finding[0].context


def test_dropbear_legacy_and_current_versions() -> None:
    assert has_outdated_dropbear(["Dropbear v0.52", "Dropbear SSH v0.52.1"])
    assert not has_outdated_dropbear(["Dropbear v2022.83"])


# ---------------------------------------------------------------------------
# scan_strings_findings / findings_to_counts / scan_strings
# ---------------------------------------------------------------------------


def test_scan_strings_findings_returns_all_matches() -> None:
    strings = ["password=admin", "host 192.168.1.1", "/usr/sbin/telnetd"]
    findings = scan_strings_findings(strings)
    detectors = {f.detector for f in findings}
    assert "hardcoded_passwords" in detectors
    assert "non_public_ips" in detectors
    assert "telnetd" in detectors


def test_findings_to_counts_matches_scan_strings() -> None:
    strings = [
        "password=admin",
        "host 192.168.1.1",
        "/usr/sbin/telnetd",
        "OpenSSL 1.0.2k",
    ]
    via_findings = findings_to_counts(scan_strings_findings(strings))
    assert via_findings == scan_strings(strings)


def test_scan_strings_returns_all_keys() -> None:
    result = scan_strings([])
    expected_keys = {
        "count_hardcoded_passwords",
        "count_credential_pairs",
        "count_non_public_ips",
        "count_public_ips",
        "has_telnetd",
        "has_debug_account",
        "has_outdated_libssl",
        "has_outdated_busybox",
        "has_outdated_dropbear",
        "count_urls",
        "count_api_tokens",
    }
    assert set(result.keys()) == expected_keys


def test_scan_strings_empty_defaults() -> None:
    result = scan_strings([])
    assert result["count_hardcoded_passwords"] == 0
    assert result["count_non_public_ips"] == 0
    assert result["has_telnetd"] is False
    assert result["has_debug_account"] is False
    assert result["has_outdated_libssl"] is False
    assert result["has_outdated_busybox"] is False
    assert result["has_outdated_dropbear"] is False
    assert result["count_urls"] == 0
    assert result["count_api_tokens"] == 0


def test_scan_strings_detects_features() -> None:
    strings = [
        "password=admin",
        "host 192.168.1.1",
        "/usr/sbin/telnetd",
        "OpenSSL 1.0.2k",
        "https://example.com",
    ]
    result = scan_strings(strings)
    assert result["count_hardcoded_passwords"] >= 1
    assert result["count_non_public_ips"] == 1
    assert result["has_telnetd"] is True
    assert result["has_outdated_libssl"] is True
    assert result["count_urls"] == 1


def test_ip_inside_url_counts_only_as_url() -> None:
    for url in ("http://8.8.8.8/", "https://10.0.0.1:8080/cgi"):
        result = scan_strings([url])
        assert result["count_urls"] == 1
        assert result["count_non_public_ips"] == 0
        assert result["count_public_ips"] == 0


def test_ip_outside_url_still_counts_in_same_string() -> None:
    result = scan_strings(["fetch http://example.com/fw from dns 8.8.8.8"])
    assert result["count_urls"] == 1
    assert result["count_public_ips"] == 1
