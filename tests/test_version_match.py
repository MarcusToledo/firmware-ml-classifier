from __future__ import annotations

import pytest

from src.labeling.version_match import VersionRange, parse_version, version_in_range


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("1.2.3", (1, 2, 3)),
        ("7.10(ABTG.4)C0", (7, 10)),
        ("5", (5,)),
        ("ABTG", None),
        ("", None),
        ("   ", None),
        ("v1.2.3", None),
    ],
)
def test_parse_version_extracts_leading_numeric_segments(
    raw: str, expected: tuple[int, ...] | None
) -> None:
    assert parse_version(raw) == expected


@pytest.mark.parametrize(
    ("version", "bounds", "expected"),
    [
        ((1, 0), VersionRange(), True),
        ((1, 5), VersionRange(start_including=(1, 0), end_including=(2, 0)), True),
        ((1, 0), VersionRange(start_including=(1, 0)), True),
        ((2, 0), VersionRange(end_including=(2, 0)), True),
        ((1, 0), VersionRange(start_excluding=(1, 0)), False),
        ((2, 0), VersionRange(end_excluding=(2, 0)), False),
        ((0, 9), VersionRange(start_including=(1, 0)), False),
        ((1, 2, 4), VersionRange(end_excluding=(1, 2, 3)), False),
        ((1, 2, 2), VersionRange(end_excluding=(1, 2, 3)), True),
        (
            (7, 10),
            VersionRange(start_including=(7, 10, 0), end_including=(7, 10, 0)),
            True,
        ),
    ],
)
def test_version_in_range_respects_boundaries(
    version: tuple[int, ...], bounds: VersionRange, expected: bool
) -> None:
    assert version_in_range(version, bounds) is expected
