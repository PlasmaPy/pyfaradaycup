
"""Tests for `pyfaradaycup.pipeline.ccsds_reader_pipeline.file2bytestr`."""

import gzip
from pathlib import Path

from pyfaradaycup.pipeline.ccsds_reader_pipeline import file2bytestr

CONTENTS = b"\x08\x52\xc0\x05\x00\x63 some packet bytes"


def test_file2bytestr(tmp_path: Path) -> None:
    """Test that an uncompressed file is read back byte for byte."""
    path = tmp_path / "packets.bin"
    path.write_bytes(CONTENTS)

    result = file2bytestr(str(path))

    assert result == CONTENTS


def test_file2bytestr_gzip(tmp_path: Path) -> None:
    """Test that a gzip-compressed file is decompressed when gzip=True."""
    path = tmp_path / "packets.bin.gz"
    path.write_bytes(gzip.compress(CONTENTS))

    result = file2bytestr(str(path), gzip=True)

    assert result == CONTENTS