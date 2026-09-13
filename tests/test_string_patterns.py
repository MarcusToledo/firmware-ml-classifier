import pytest

from src.features.string_patterns import (
    count_api_tokens,
    count_credential_pairs,
    count_hardcoded_ips,
    count_hardcoded_passwords,
    count_public_ips,
    count_urls,
    has_debug_account,
    has_outdated_busybox,
    has_outdated_dropbear,
    has_outdated_libssl,
    has_telnetd,
    scan_strings,
)

# ---------------------------------------------------------------------------
# count_hardcoded_passwords
# ---------------------------------------------------------------------------


def test_passwords_empty() -> None:
    assert count_hardcoded_passwords([]) == 0


def test_passwords_kv_match() -> None:
    assert count_hardcoded_passwords(["password=secret123"]) == 1


def test_passwords_kv_colon() -> None:
    assert count_hardcoded_passwords(["passwd: admin"]) == 1


def test_passwords_kv_case_insensitive() -> None:
    assert count_hardcoded_passwords(["PASSWORD=abc"]) == 1


def test_passwords_rejects_format_specifier() -> None:
    assert count_hardcoded_passwords(["password=%s"]) == 0


def test_passwords_rejects_format_specifier_precision() -> None:
    assert count_hardcoded_passwords(["password=%.*s"]) == 0


def test_passwords_rejects_variable_reference() -> None:
    assert count_hardcoded_passwords(["password=${PASSWORD}"]) == 0


def test_passwords_rejects_variable_reference_positional() -> None:
    assert count_hardcoded_passwords(["password=$1"]) == 0


def test_passwords_rejects_template() -> None:
    assert count_hardcoded_passwords(["password={{password}}"]) == 0


def test_passwords_rejects_angle_template() -> None:
    assert count_hardcoded_passwords(["password=<password>"]) == 0


def test_passwords_rejects_null_literal() -> None:
    assert count_hardcoded_passwords(["password=NULL"]) == 0


def test_passwords_rejects_none_literal() -> None:
    assert count_hardcoded_passwords(["password=None"]) == 0


def test_passwords_rejects_parenthesized_null() -> None:
    assert count_hardcoded_passwords(["password=(null)"]) == 0


def test_passwords_rejects_metadata_key_length() -> None:
    assert count_hardcoded_passwords(["password_length=8"]) == 0


def test_passwords_rejects_metadata_key_hash() -> None:
    hash_val = "5f4dcc3b5aa765d61d8327deb882cf99"
    assert count_hardcoded_passwords([f"password_hash={hash_val}"]) == 0


def test_passwords_detects_compound_key_snake_case() -> None:
    assert count_hardcoded_passwords(["admin_password=admin123"]) == 1


def test_passwords_detects_compound_key_camel_case() -> None:
    assert count_hardcoded_passwords(["adminPassword=admin123"]) == 1


def test_passwords_detects_ftp_pass_alias() -> None:
    assert count_hardcoded_passwords(["ftp_pass=admin123"]) == 1


def test_passwords_detects_wpa_psk_alias() -> None:
    assert count_hardcoded_passwords(["wpa_psk=12345678"]) == 1


def test_passwords_detects_wl0_wpa_psk_alias() -> None:
    assert count_hardcoded_passwords(["wl0_wpa_psk=12345678"]) == 1


def test_passwords_query_string_after_rejected_key() -> None:
    # a rejected key=value earlier in the same (space-free) string must not
    # swallow a real credential later in the string
    assert count_hardcoded_passwords(["http://x/?mode=auto&password=admin"]) == 1


def test_passwords_default_token_without_context_not_flagged() -> None:
    # bare "admin" with zero surrounding context is too weak a signal on its
    # own (it's the false-positive source found in the first generated
    # sample) — no longer counted unless auth context is present nearby.
    assert count_hardcoded_passwords(["admin"]) == 0


def test_passwords_default_token_root_without_context_not_flagged() -> None:
    assert count_hardcoded_passwords(["root"]) == 0


def test_passwords_default_token_with_context() -> None:
    assert count_hardcoded_passwords(["default login: admin"]) == 1


def test_passwords_default_token_root_with_context() -> None:
    assert count_hardcoded_passwords(["login as root"]) == 1


def test_passwords_default_token_avoids_substring_trigger_match() -> None:
    # "auth" must not match as a substring of "authentication" — this exact
    # string is a required hard negative in the technical report (§9.3):
    # "password" is a default-password value, but this is a log message,
    # not a credential.
    assert count_hardcoded_passwords(["Password authentication failed"]) == 0


def test_passwords_no_match() -> None:
    assert count_hardcoded_passwords(["network interface eth0"]) == 0


def test_passwords_multiple_strings() -> None:
    strings = ["password=abc", "some normal string", "pwd: toor"]
    assert count_hardcoded_passwords(strings) == 2


# ---------------------------------------------------------------------------
# count_credential_pairs
# ---------------------------------------------------------------------------


def test_cred_pairs_empty() -> None:
    assert count_credential_pairs([]) == 0


def test_cred_pairs_admin_admin() -> None:
    assert count_credential_pairs(["admin:admin"]) == 1


def test_cred_pairs_root_1234() -> None:
    assert count_credential_pairs(["root:1234"]) == 1


def test_cred_pairs_non_weak_ignored() -> None:
    # neither side is in the weak set
    assert count_credential_pairs(["john:complexpassword"]) == 0


def test_cred_pairs_long_hash_ignored() -> None:
    # right side > 20 chars — excluded by {1,20} bound
    assert count_credential_pairs(["sha256:deadbeefdeadbeefdeadbeef"]) == 0


def test_cred_pairs_strong_password_with_known_username() -> None:
    # username is recognized; password is strong/unlisted — still a real pair
    assert count_credential_pairs(["admin:S3cur3Pass9"]) == 1


def test_cred_pairs_rejects_placeholder_password() -> None:
    assert count_credential_pairs(["admin:%s"]) == 0


def test_cred_pairs_url_userinfo() -> None:
    assert count_credential_pairs(["https://apiuser:Str0ngP4ss@iot.example.com/"]) == 1


def test_cred_pairs_url_userinfo_rejects_placeholder() -> None:
    assert count_credential_pairs(["https://user:%s@host/"]) == 0


def test_cred_pairs_url_userinfo_http() -> None:
    assert count_credential_pairs(["http://admin:admin@192.168.1.1/"]) == 1


def test_cred_pairs_multiple_strings() -> None:
    assert count_credential_pairs(["admin:admin", "root:root", "guest:guest"]) == 3


def test_cred_pairs_multiple_in_one_string_counts_once() -> None:
    # multiple weak pairs in a single string — counted once per string
    assert count_credential_pairs(["admin:admin root:root"]) == 1


# ---------------------------------------------------------------------------
# count_hardcoded_ips
# ---------------------------------------------------------------------------


def test_ips_empty() -> None:
    assert count_hardcoded_ips([]) == 0


def test_ips_valid_match() -> None:
    assert count_hardcoded_ips(["server at 192.168.1.1"]) == 1


def test_ips_multiple() -> None:
    assert count_hardcoded_ips(["10.0.0.1 and 172.16.0.2"]) == 2


def test_ips_excludes_broadcast() -> None:
    assert count_hardcoded_ips(["255.255.255.255"]) == 0


def test_ips_excludes_all_zeros() -> None:
    assert count_hardcoded_ips(["0.0.0.0"]) == 0


def test_ips_excludes_loopback() -> None:
    assert count_hardcoded_ips(["127.0.0.1"]) == 0


def test_ips_invalid_octet() -> None:
    assert count_hardcoded_ips(["999.0.0.1"]) == 0


def test_ips_invalid_octet_256() -> None:
    assert count_hardcoded_ips(["192.168.1.256"]) == 0


def test_ips_no_match() -> None:
    assert count_hardcoded_ips(["version 1.2.3"]) == 0


# ---------------------------------------------------------------------------
# count_public_ips
# ---------------------------------------------------------------------------


def test_public_ips_empty() -> None:
    assert count_public_ips([]) == 0


def test_public_ips_routable() -> None:
    assert count_public_ips(["8.8.8.8"]) == 1


def test_public_ips_c2_candidate() -> None:
    assert count_public_ips(["45.33.32.156"]) == 1


def test_public_ips_ignores_private_10() -> None:
    assert count_public_ips(["10.0.0.1"]) == 0


def test_public_ips_ignores_private_192_168() -> None:
    assert count_public_ips(["192.168.1.1"]) == 0


def test_public_ips_ignores_rfc1918_172() -> None:
    assert count_public_ips(["172.16.0.1", "172.31.255.255"]) == 0


def test_public_ips_172_32_is_public() -> None:
    # 172.32.x.x is outside the RFC-1918 /12 range
    assert count_public_ips(["172.32.0.1"]) == 1


def test_public_ips_ignores_link_local() -> None:
    assert count_public_ips(["169.254.1.1"]) == 0


def test_public_ips_ignores_multicast() -> None:
    assert count_public_ips(["224.0.0.1"]) == 0


def test_public_ips_multiple_in_one_string() -> None:
    assert count_public_ips(["8.8.8.8 and 1.1.1.1"]) == 2


# ---------------------------------------------------------------------------
# has_telnetd
# ---------------------------------------------------------------------------


def test_telnetd_empty() -> None:
    assert has_telnetd([]) is False


def test_telnetd_true() -> None:
    assert has_telnetd(["/usr/sbin/telnetd -l /bin/sh"]) is True


def test_telnetd_false() -> None:
    assert has_telnetd(["telnet 192.168.1.1"]) is False


def test_telnetd_substring() -> None:
    assert has_telnetd(["start_telnetd"]) is True


# ---------------------------------------------------------------------------
# has_debug_account
# ---------------------------------------------------------------------------


def test_debug_account_empty() -> None:
    assert has_debug_account([]) is False


def test_debug_account_debug() -> None:
    assert has_debug_account(["debug"]) is True


def test_debug_account_guest() -> None:
    assert has_debug_account(["guest"]) is True


def test_debug_account_test() -> None:
    assert has_debug_account(["test"]) is True


def test_debug_account_case_insensitive() -> None:
    assert has_debug_account(["DEBUG"]) is True


def test_debug_account_no_partial_match() -> None:
    # "testuser" contains "test" but not as a word boundary
    assert has_debug_account(["testuser"]) is False


def test_debug_account_no_match() -> None:
    assert has_debug_account(["admin root supervisor"]) is False


# ---------------------------------------------------------------------------
# has_outdated_libssl
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
    # HTTP server banner: "Apache/2.2.31 OpenSSL/1.0.2k"
    assert has_outdated_libssl(["Apache/2.2.31 OpenSSL/1.0.2k"]) is True


# ---------------------------------------------------------------------------
# has_outdated_busybox
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
# has_outdated_dropbear
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
# count_urls
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


# ---------------------------------------------------------------------------
# count_api_tokens
# ---------------------------------------------------------------------------


def test_tokens_empty() -> None:
    assert count_api_tokens([]) == 0


def test_tokens_hex_32_chars() -> None:
    assert count_api_tokens(["abc123" + "0" * 26]) == 1


def test_tokens_too_short() -> None:
    # 31 hex chars — below threshold
    assert count_api_tokens(["a" * 31]) == 0


def test_tokens_no_match() -> None:
    assert count_api_tokens(["short string"]) == 0


# ---------------------------------------------------------------------------
# scan_strings
# ---------------------------------------------------------------------------


def test_scan_strings_returns_all_keys() -> None:
    result = scan_strings([])
    expected_keys = {
        "count_hardcoded_passwords",
        "count_credential_pairs",
        "count_hardcoded_ips",
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
    assert result["count_hardcoded_ips"] == 0
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
        "192.168.1.1",
        "/usr/sbin/telnetd",
        "OpenSSL 1.0.2k",
        "https://example.com",
    ]
    result = scan_strings(strings)
    assert result["count_hardcoded_passwords"] >= 1
    assert result["count_hardcoded_ips"] == 1
    assert result["has_telnetd"] is True
    assert result["has_outdated_libssl"] is True
    assert result["count_urls"] == 1


# ---------------------------------------------------------------------------
# Regression sweep — hard negatives and boundary cases from
# docs/Relatorio_Tecnico_LLM_Deteccao_Credenciais_Firmware.pdf (§6.2, §9.3)
# ---------------------------------------------------------------------------

_REPORT_PASSWORD_CASES = [
    # (text, expected count_hardcoded_passwords)
    ("password=%s", 0),
    ("password=${PASSWORD}", 0),
    ("password=NULL", 0),
    ("password_length=8", 0),
    ("Password authentication failed", 0),
    ("setPassword", 0),
    ("/etc/passwd", 0),
    ("passwd.c", 0),
    ("confirm password", 0),
    ("wpa_psk=12345678", 1),
    ("ftp_pass=admin123", 1),
    ("adminPassword=admin123", 1),
]


@pytest.mark.parametrize("text,expected", _REPORT_PASSWORD_CASES)
def test_report_password_regression(text: str, expected: int) -> None:
    assert count_hardcoded_passwords([text]) == expected


_REPORT_PAIR_CASES = [
    # (text, expected count_credential_pairs)
    ("admin:admin123", 1),
    ("http://admin:admin@192.168.1.1/", 1),
]


@pytest.mark.parametrize("text,expected", _REPORT_PAIR_CASES)
def test_report_pair_regression(text: str, expected: int) -> None:
    assert count_credential_pairs([text]) == expected
