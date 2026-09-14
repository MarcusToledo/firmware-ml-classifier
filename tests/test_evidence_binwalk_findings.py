from src.evidence.binwalk_findings import (
    count_crypto_signatures,
    find_crypto_signatures,
    find_encrypted_sections,
    has_encrypted_sections,
)

# -- count_crypto_signatures / find_crypto_signatures -------------------------


def test_count_crypto_signatures_empty() -> None:
    assert count_crypto_signatures([]) == 0


def test_count_crypto_signatures_matches() -> None:
    descriptions = [
        "AES encrypted data",
        "RSA public key",
        "private key",
        "Squashfs filesystem",
    ]
    assert count_crypto_signatures(descriptions) == 3


def test_count_crypto_signatures_certificate() -> None:
    assert count_crypto_signatures(["X.509 certificate"]) == 1


def test_crypto_signature_finding_has_medium_confidence() -> None:
    findings = find_crypto_signatures(["AES encrypted data"])
    assert len(findings) == 1
    assert findings[0].confidence == "medium"
    assert findings[0].detector == "crypto_signatures"


# -- has_encrypted_sections / find_encrypted_sections --------------------------


def test_has_encrypted_false_empty() -> None:
    assert has_encrypted_sections([]) is False


def test_has_encrypted_true() -> None:
    assert has_encrypted_sections(["AES-128 encrypted block"]) is True


def test_has_encrypted_cipher() -> None:
    assert has_encrypted_sections(["cipher suite TLS"]) is True


def test_has_encrypted_false_no_match() -> None:
    assert has_encrypted_sections(["Squashfs filesystem"]) is False


def test_encrypted_section_finding_has_medium_confidence() -> None:
    findings = find_encrypted_sections(["AES-128 encrypted block"])
    assert len(findings) == 1
    assert findings[0].confidence == "medium"
    assert findings[0].detector == "encrypted_sections"
