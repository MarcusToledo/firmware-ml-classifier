import pytest

from src.features.strings import (
    DocumentBuilder,
    extract_ascii_strings,
    iter_ascii_strings,
    limit_strings,
    strings_to_document,
    tokenize_document,
)


def test_extract_ascii_strings_min_len() -> None:
    payload = b"abc\x00defg"

    assert extract_ascii_strings(payload, min_len=4) == ["defg"]


def test_extract_ascii_strings_min_len_normalizes() -> None:
    payload = b"a\x00b"

    assert extract_ascii_strings(payload, min_len=0) == ["a", "b"]


def test_extract_ascii_strings_max_string_len_truncates() -> None:
    payload = b"abcdef"

    assert extract_ascii_strings(payload, max_string_len=3) == ["abc"]


def test_extract_ascii_strings_max_string_len_normalizes() -> None:
    payload = b"abcd"

    assert extract_ascii_strings(payload, max_string_len=0) == ["a"]


def test_limit_strings_truncates() -> None:
    strings = ["a", "b", "c"]

    assert limit_strings(strings, max_strings=2) == ["a", "b"]


def test_limit_strings_zero_returns_empty() -> None:
    strings = ["a", "b"]

    assert limit_strings(strings, max_strings=0) == []


def test_strings_to_document_truncates() -> None:
    strings = ["abc", "def"]

    assert strings_to_document(strings, max_doc_chars=5) == "abc\nd"


def test_strings_to_document_zero_returns_empty() -> None:
    strings = ["abc"]

    assert strings_to_document(strings, max_doc_chars=0) == ""


def test_tokenize_document_basic() -> None:
    doc = "hello  world\nfirmware"

    assert tokenize_document(doc) == ["hello", "world", "firmware"]


@pytest.mark.parametrize("width", [1, 3, 7, 64])
def test_ascii_stream_matches_whole_payload(width: int) -> None:
    """Mantém cortes e fronteiras idênticos à extração sobre bytes contíguos."""
    payload = b"foo\x00ABCDEF" * 9 + b"\xff" + b"z" * 200 + b"\x00END"
    chunks = [payload[index : index + width] for index in range(0, len(payload), width)]
    assert list(iter_ascii_strings(chunks, 4, 17)) == extract_ascii_strings(
        payload, 4, 17
    )


def test_document_deduplicates_then_truncates() -> None:
    """Mantém a primeira ocorrência e corta apenas documento, nunca detectores."""
    builder = DocumentBuilder(max_strings=2, max_doc_chars=8)
    for value in ["admin", "admin", "guest", "password"]:
        builder.add(value)
    assert builder.document() == "admin\ngu"
    assert builder.truncated is True
