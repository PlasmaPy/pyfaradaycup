"""Tests for `pyfaradaycup.pipeline.ccsds_reader_pipeline.parse_ccsds_head`."""

import struct

import pytest

from pyfaradaycup.pipeline.ccsds_reader_pipeline import parse_ccsds_head


def make_header(apid: int, seq_count: int, packet_length: int, met: int) -> bytes:
    """Build a 10-byte CCSDS header: 6-byte primary header plus 4-byte MET."""
    word1 = (1 << 11) | apid  # version 0, type 0, secondary header flag 1
    word2 = (3 << 14) | seq_count  # group flags 3 (unsegmented)
    return struct.pack(">HHHI", word1, word2, packet_length, met)


def test_parse_ccsds_head() -> None:
    """Test that each header field is decoded from known bytes."""
    header = make_header(apid=0x352, seq_count=5, packet_length=99, met=123456789)

    result = parse_ccsds_head(header)

    assert result == {
        "CCSDS_Version": 0,
        "CCSDS_PacketType": 0,
        "CCSDS_SecHdrFlag": 1,
        "CCSDS_ApID": 0x352,
        "CCSDS_GroupFlags": 3,
        "CCSDS_SeqCnt": 5,
        "CCSDS_PacketLen": 99,
        "CCSDS_MET": 123456789,
    }


def test_parse_ccsds_head_too_short() -> None:
    """Test that a header shorter than 10 bytes raises a ValueError."""
    header = make_header(apid=0x352, seq_count=5, packet_length=99, met=123456789)

    with pytest.raises(ValueError, match="not as long as expected"):
        parse_ccsds_head(header[:9])
