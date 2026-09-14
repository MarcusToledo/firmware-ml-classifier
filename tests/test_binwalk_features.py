from src.features.binwalk import (
    count_filesystems,
    detect_compression_type,
    detect_fs_type,
)

# -- count_filesystems -------------------------------------------------------


def test_count_filesystems_empty() -> None:
    assert count_filesystems([]) == 0


def test_count_filesystems_matches() -> None:
    descriptions = [
        "Squashfs filesystem, little endian, version 4.0",
        "JFFS2 filesystem data",
        "gzip compressed data",
    ]
    assert count_filesystems(descriptions) == 2


def test_count_filesystems_case_insensitive() -> None:
    assert count_filesystems(["CRAMFS filesystem"]) == 1


# -- detect_fs_type ----------------------------------------------------------


def test_detect_fs_type_none_on_empty() -> None:
    assert detect_fs_type([]) is None


def test_detect_fs_type_returns_most_common() -> None:
    descriptions = [
        "Squashfs filesystem, version 4.0",
        "JFFS2 filesystem data",
        "Squashfs filesystem, version 3.0",
    ]
    assert detect_fs_type(descriptions) == "squashfs"


def test_detect_fs_type_single_match() -> None:
    assert detect_fs_type(["UBIFS superblock"]) == "ubifs"


def test_detect_fs_type_no_fs() -> None:
    assert detect_fs_type(["gzip compressed data"]) is None


# -- detect_compression_type -------------------------------------------------


def test_detect_compression_none_on_empty() -> None:
    assert detect_compression_type([]) is None


def test_detect_compression_first_match() -> None:
    descriptions = [
        "LZMA compressed data",
        "gzip compressed data",
    ]
    assert detect_compression_type(descriptions) == "lzma"


def test_detect_compression_gzip() -> None:
    assert detect_compression_type(["gzip compressed data, from Unix"]) == "gzip"


def test_detect_compression_no_match() -> None:
    assert detect_compression_type(["Squashfs filesystem"]) is None
