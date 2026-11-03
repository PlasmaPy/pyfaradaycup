"""Test the conversion of L0 packets into L0.5 data."""

import logging
from typing import TYPE_CHECKING, cast

import pytest

from pyfaradaycup.decommutator import l0_to_l05

if TYPE_CHECKING:
    from spacepy import pycdf

# With nocdf=True, the expanded data are returned instead of written to a
# CDF, so no CDF is needed.
NO_CDF = cast("pycdf.CDF", None)


def _packets(itst: list[tuple[int, int]]) -> dict[str, list]:
    """
    Return the data of APID 0x353 packets with the given integration and
    settling times, each with four measurements.
    """
    n = len(itst)
    return {
        "CCSDS_ApID": [0x353] * n,
        "CCSDS_MET": list(range(n)),
        "SW_SPCSUBSEC": [0] * n,
        "SW_SPC_INTTIME": [it for it, _ in itst],
        "SW_SPC_SERVTIME": [st for _, st in itst],
        "WINDOW": [[0, 1, 2, 3]] * n,
        "ASIN": [[10, 11, 12, 13]] * n,
    }


@pytest.fixture
def fake_scet(monkeypatch: pytest.MonkeyPatch) -> None:
    """Convert MET to ephemeris time without SPICE kernels."""
    monkeypatch.setattr(
        l0_to_l05,
        "_secsubsec2scet",
        lambda sec, _subsec: [1e9 * s for s in sec],
    )


@pytest.mark.usefixtures("fake_scet")
def test_invalid_itst_warning(caplog: pytest.LogCaptureFixture) -> None:
    """
    Test that packets whose IT+ST is not a power of 2 are timed with the
    default IT and ST, and that one warning says how many packets were
    affected, what they reported, and that the CDF keeps what they
    reported.
    """
    dat = _packets([(5, 2), (5, 2), (4, 1), (4, 1), (6, 2)])
    with caplog.at_level(logging.WARNING, logger="pyfaradaycup"):
        result = l0_to_l05._cdf351_353_354(NO_CDF, dat, nocdf=True)

    assert result is not None
    # Every measurement is spaced by the default IT+ST of 8 ticks.
    epoch = result["Epoch"]
    spacing = 8 / 1171.875 * 1e9
    assert epoch[1] - epoch[0] == pytest.approx(spacing)
    assert result["SW_SPC_INTTIME"][:16] == [5] * 8 + [4] * 8

    (message,) = caplog.messages
    assert message == (
        "4 APID 0x353 packets report an invalid IT+ST that is not a power of 2 "
        "(IT/ST: 4/1, 5/2), so the FPGA should have used its defaults. Their "
        "times assume IT=6, ST=2; the CDF keeps the reported values."
    )


@pytest.mark.usefixtures("fake_scet")
def test_valid_itst_no_warning(caplog: pytest.LogCaptureFixture) -> None:
    """Test that packets whose IT+ST is a power of 2 give no warning."""
    dat = _packets([(6, 2), (6, 2), (12, 4)])
    with caplog.at_level(logging.WARNING, logger="pyfaradaycup"):
        l0_to_l05._cdf351_353_354(NO_CDF, dat, nocdf=True)
    assert caplog.messages == []
