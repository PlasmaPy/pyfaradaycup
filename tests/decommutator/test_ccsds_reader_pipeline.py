"""Tests of the private helper functions in ccsds_reader_pipeline."""

from __future__ import annotations

import struct

import pytest

from pyfaradaycup.decommutator.ccsds_reader_pipeline import _parse_ccsds_head

_FIELD_WIDTHS = {
    "CCSDS_Version": 3,
    "CCSDS_PacketType": 1,
    "CCSDS_SecHdrFlag": 1,
    "CCSDS_ApID": 11,
    "CCSDS_GroupFlags": 2,
    "CCSDS_SeqCnt": 14,
    "CCSDS_PacketLen": 16,
    "CCSDS_MET": 32,
}


def _make_ccsds_head(fields: dict[str, int]) -> bytes:
    """Encode CCSDS header fields into a 10-byte header."""
    word0 = (
        fields["CCSDS_Version"] << 13
        | fields["CCSDS_PacketType"] << 12
        | fields["CCSDS_SecHdrFlag"] << 11
        | fields["CCSDS_ApID"]
    )
    word1 = fields["CCSDS_GroupFlags"] << 14 | fields["CCSDS_SeqCnt"]
    return struct.pack(
        ">HHHI", word0, word1, fields["CCSDS_PacketLen"], fields["CCSDS_MET"]
    )


_typical_fields = {
    "CCSDS_Version": 0,
    "CCSDS_PacketType": 0,
    "CCSDS_SecHdrFlag": 1,
    "CCSDS_ApID": 0x352,
    "CCSDS_GroupFlags": 3,
    "CCSDS_SeqCnt": 0x1234,
    "CCSDS_PacketLen": 0x098D,
    "CCSDS_MET": 523462910,
}


@pytest.mark.parametrize(
    "fields",
    [
        _typical_fields,
        {**_typical_fields, "CCSDS_ApID": 0x081},
        {**_typical_fields, "CCSDS_ApID": 0x35E},
        {**_typical_fields, "CCSDS_ApID": 0x7FF},
        dict.fromkeys(_FIELD_WIDTHS, 0),
        {name: 2**width - 1 for name, width in _FIELD_WIDTHS.items()},
    ],
)
def test_parse_ccsds_head_round_trip(fields: dict[str, int]) -> None:
    """Test that decoding an encoded header recovers the original fields."""
    assert _parse_ccsds_head(_make_ccsds_head(fields)) == fields


@pytest.mark.parametrize("name", _FIELD_WIDTHS)
def test_parse_ccsds_head_field_isolation(name: str) -> None:
    """Test that setting every bit of one field does not leak into the others."""
    fields = dict.fromkeys(_FIELD_WIDTHS, 0)
    fields[name] = 2 ** _FIELD_WIDTHS[name] - 1
    assert _parse_ccsds_head(_make_ccsds_head(fields)) == fields


def test_parse_ccsds_head_ignores_extra_bytes() -> None:
    """Test that only the first 10 bytes are decoded."""
    header = _make_ccsds_head(_typical_fields)
    assert _parse_ccsds_head(header + b"\xff" * 20) == _typical_fields


@pytest.mark.parametrize("length", range(10))
def test_parse_ccsds_head_too_short(length: int) -> None:
    """Test that a header shorter than 10 bytes raises a ValueError."""
    header = _make_ccsds_head(_typical_fields)[:length]
    with pytest.raises(ValueError, match="not as long as expected"):
        _parse_ccsds_head(header)
