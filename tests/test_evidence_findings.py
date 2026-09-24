from src.evidence.findings import SecurityFinding


def test_security_finding_holds_all_fields() -> None:
    finding = SecurityFinding(
        type="credential_candidate",
        source="password=admin",
        context="key=value assignment: 'password=admin'",
        confidence="high",
        detector="hardcoded_passwords",
        detector_version="1.0",
    )
    assert finding.type == "credential_candidate"
    assert finding.source == "password=admin"
    assert finding.confidence == "high"
    assert finding.detector == "hardcoded_passwords"
    assert finding.detector_version == "1.0"


def test_security_finding_is_frozen() -> None:
    finding = SecurityFinding(
        type="url",
        source="http://example.com",
        context="URL: http://example.com",
        confidence="low",
        detector="urls",
        detector_version="1.0",
    )
    try:
        finding.type = "other"  # type: ignore[misc]
        raised = False
    except AttributeError:
        raised = True
    assert raised is True
