"""
Tests of the private helper functions in ccsds_reader_pipeline.

The end-to-end test in ``test_decommutator.py`` checks that a whole L0
file is converted to the expected L05 CDF files, but when it fails it
does not show which step went wrong. The tests here check individual
functions so that a failure points to the function responsible.
"""

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
    """
    Encode CCSDS header fields into a 10-byte header.

    This is the inverse of `_parse_ccsds_head`. It is written with
    `struct.pack` and bit shifts rather than by reusing any code from
    the package, so that a mistake in the decoder is not repeated in
    the encoder and hidden from the tests.

    Parameters
    ----------
    fields : dict of str to int
        The header fields, with the same keys that `_parse_ccsds_head`
        returns.

    Returns
    -------
    bytes
        The 6-byte CCSDS primary header followed by the 4-byte MET.
    """
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
    """
    Test that decoding an encoded header recovers the original fields.

    Every packet that the decommutator reads is identified and sized
    from its header, so a wrong field here means packets are skipped,
    assigned to the wrong APID, or given wrong times. The cases include
    the SPC and spacecraft APIDs that the decommutator looks for, the
    largest 11-bit APID (to check that the top 3 APID bits, which share
    a byte with the version and flags, are decoded), and headers with
    every field at its minimum or maximum value.
    """
    assert _parse_ccsds_head(_make_ccsds_head(fields)) == fields


@pytest.mark.parametrize("name", _FIELD_WIDTHS)
def test_parse_ccsds_head_field_isolation(name: str) -> None:
    """
    Test that setting every bit of one field does not leak into the others.

    Several fields share a byte, so a mask or shift that is off by one
    bit would move a bit from one field into its neighbor. Round-trip
    tests with typical values can miss this, because the bits next to a
    field boundary are often zero. Setting one field to its maximum and
    the rest to zero makes any such leak show up as a nonzero value in
    a field that should be zero, or a smaller value in the field
    being tested.
    """
    fields = dict.fromkeys(_FIELD_WIDTHS, 0)
    fields[name] = 2 ** _FIELD_WIDTHS[name] - 1
    assert _parse_ccsds_head(_make_ccsds_head(fields)) == fields


def test_parse_ccsds_head_ignores_extra_bytes() -> None:
    """
    Test that only the first 10 bytes are decoded.

    Callers do not always pass exactly 10 bytes: ``read_file_sc`` passes
    the contents of the whole file to read the first header. The bytes
    after the header must not change the result.
    """
    header = _make_ccsds_head(_typical_fields)
    assert _parse_ccsds_head(header + b"\xff" * 20) == _typical_fields


@pytest.mark.parametrize("length", range(10))
def test_parse_ccsds_head_too_short(length: int) -> None:
    """
    Test that a header shorter than 10 bytes raises a ValueError.

    A packet can be cut off at the end of an L0 file. ``_read_bytestr``
    and ``read_file_sc`` catch `ValueError` to skip such a packet, so a
    short header must raise `ValueError` rather than another exception
    or a header with missing fields.
    """
    header = _make_ccsds_head(_typical_fields)[:length]
    with pytest.raises(ValueError, match="not as long as expected"):
        _parse_ccsds_head(header)
