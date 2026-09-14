from src.evidence.patterns import (
    count_credential_pairs,
    count_hardcoded_ips,
    count_hardcoded_passwords,
    count_public_ips,
    find_credential_pairs,
    find_debug_account,
    find_hardcoded_ips,
    find_hardcoded_passwords,
    find_public_ips,
    find_telnetd,
    has_debug_account,
    has_telnetd,
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


def test_passwords_default_token() -> None:
    assert count_hardcoded_passwords(["admin"]) == 1


def test_passwords_default_token_root() -> None:
    assert count_hardcoded_passwords(["root"]) == 1


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
    findings = find_hardcoded_passwords(["admin"])
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
# find_hardcoded_ips / count_hardcoded_ips
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


def test_ips_finding_has_low_confidence() -> None:
    findings = find_hardcoded_ips(["192.168.1.1"])
    assert len(findings) == 1
    assert findings[0].confidence == "low"
    assert findings[0].detector == "hardcoded_ips"


# ---------------------------------------------------------------------------
# find_public_ips / count_public_ips
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
    assert count_public_ips(["172.32.0.1"]) == 1


def test_public_ips_ignores_link_local() -> None:
    assert count_public_ips(["169.254.1.1"]) == 0


def test_public_ips_ignores_multicast() -> None:
    assert count_public_ips(["224.0.0.1"]) == 0


def test_public_ips_multiple_in_one_string() -> None:
    assert count_public_ips(["8.8.8.8 and 1.1.1.1"]) == 2


def test_public_ips_finding_has_high_confidence() -> None:
    findings = find_public_ips(["8.8.8.8"])
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


def test_debug_account_debug() -> None:
    assert has_debug_account(["debug"]) is True


def test_debug_account_guest() -> None:
    assert has_debug_account(["guest"]) is True


def test_debug_account_test() -> None:
    assert has_debug_account(["test"]) is True


def test_debug_account_case_insensitive() -> None:
    assert has_debug_account(["DEBUG"]) is True


def test_debug_account_no_partial_match() -> None:
    assert has_debug_account(["testuser"]) is False


def test_debug_account_no_match() -> None:
    assert has_debug_account(["admin root supervisor"]) is False


def test_debug_account_finding_has_low_confidence() -> None:
    findings = find_debug_account(["debug"])
    assert len(findings) == 1
    assert findings[0].confidence == "low"
    assert findings[0].detector == "debug_account"
