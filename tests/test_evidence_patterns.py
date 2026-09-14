from src.evidence.patterns import (
    count_credential_pairs,
    count_hardcoded_passwords,
    find_credential_pairs,
    find_hardcoded_passwords,
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
