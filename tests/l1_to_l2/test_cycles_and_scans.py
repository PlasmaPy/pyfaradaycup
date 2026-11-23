"""Test numbering measurement cycles and flagging full scans."""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
import pytest

from pyfaradaycup.l1_to_l2._spp_swp_spc_flagfullscanwindows import (
    spp_swp_spc_flagfullscanwindows,
    spp_swp_spc_fullscanseqlookup,
    spp_swp_spc_fullscanseqlookup_defaultkey,
)
from pyfaradaycup.l1_to_l2._spp_swp_spc_parse_cycles import spp_swp_spc_parse_cycles

if TYPE_CHECKING:
    from collections.abc import Callable


def test_parse_cycles_ion_scans() -> None:
    """
    Test that each ascending ion scan is a cycle, and the retrace before
    a scan gets the number of that scan.

    A retrace at the end of the array keeps the number 0, because each
    zero is filled from the sample after it, and IDL uses the last sample
    itself for the last sample.
    """
    w = np.array([0, 10, 20, 30, 40, 5, 10, 20, 30, 40, 5], dtype=np.uint8)
    cyclenum = spp_swp_spc_parse_cycles(w, np.zeros_like(w))
    assert cyclenum.dtype == np.uint32
    assert cyclenum.tolist() == [1, 1, 1, 1, 1, 2, 2, 2, 2, 2, 0]


def test_parse_cycles_does_not_change_input() -> None:
    """Test that the windows are not changed, as IDL restores them at the end."""
    w = np.array([5, 10, 20, 5, 10, 20], dtype=np.uint8)
    spp_swp_spc_parse_cycles(w, np.ones_like(w))
    assert w.tolist() == [5, 10, 20, 5, 10, 20]


def test_parse_cycles_electron_scans() -> None:
    """
    Test that electron windows given as positive numbers are made
    negative, so that ascending positive windows form descending cycles.

    Unlike for ions, the last sample is part of the last cycle, because
    IDL marks it as a step whenever it is greater than the sample before
    it, whatever the mode, and -1 > -30.
    """
    w = np.array([1, 10, 20, 30, 5, 10, 20, 30, 1], dtype=np.uint8)
    assert spp_swp_spc_parse_cycles(w, np.zeros_like(w)).tolist() == [
        1, 1, 1, 1, 2, 2, 2, 2, 0,
    ]  # fmt: skip
    assert spp_swp_spc_parse_cycles(w, np.ones_like(w)).tolist() == [
        1, 1, 1, 1, 2, 2, 2, 2, 2,
    ]  # fmt: skip


def test_parse_cycles_flux_angle_series() -> None:
    """
    Test that a run of more than 10 constant windows gets its own cycle
    number, between the cycles before and after it.
    """
    scan = [10, 20, 30, 40]
    w = np.array(scan + [25] * 12 + scan + [5], dtype=np.uint8)
    cyclenum = spp_swp_spc_parse_cycles(w, np.zeros_like(w))
    assert cyclenum.tolist() == [1] * 4 + [2] * 12 + [3] * 4 + [0]


def test_parse_cycles_short_flat_run_is_retrace() -> None:
    """
    Test that a run of 10 constant windows is filled in like a retrace,
    with the number of the next cycle.

    The 10 windows of 25 and the first window of the next scan, which is
    not a step up, are a run of 11 zeros. Only 10 passes are made to fill
    in zeros, one sample each, so the first sample of the run stays 0.
    """
    scan = [10, 20, 30, 40]
    w = np.array(scan + [25] * 10 + scan + [5], dtype=np.uint8)
    cyclenum = spp_swp_spc_parse_cycles(w, np.zeros_like(w))
    assert cyclenum.tolist() == [1] * 4 + [0] + [2] * 13 + [0]


def test_fullscanseqlookup(tt2000: Callable[..., int]) -> None:
    """Test that the default key is used from 2019-09-18, and is an error before."""
    key = spp_swp_spc_fullscanseqlookup(np.array([tt2000(2019, 9, 18)]))
    np.testing.assert_array_equal(key, spp_swp_spc_fullscanseqlookup_defaultkey())
    assert key.size == 31  # ruff:ignore[PLR2004]
    with pytest.raises(NotImplementedError, match="2019-09-18"):
        spp_swp_spc_fullscanseqlookup(np.array([tt2000(2019, 9, 17, 23, 59, 59)]))


def _dat(w: list[int], tt2000: Callable[..., int]) -> dict[str, np.ndarray]:
    start = tt2000(2026, 8, 3)
    return {
        "window": np.array(w, dtype=np.uint8),
        "epoch": start + np.arange(len(w), dtype=np.int64),
    }


def test_flagfullscanwindows(tt2000: Callable[..., int]) -> None:
    """Test that every sample in a run of 7 windows that matches the key is flagged."""
    key = spp_swp_spc_fullscanseqlookup_defaultkey().tolist()
    w = [1, 2, *key[5:12], 3, 4, *key[20:26], 5]
    flags = spp_swp_spc_flagfullscanwindows(_dat(w, tt2000))
    assert flags.dtype == np.uint8
    # Only the run of 7 matches; the run of 6 does not
    assert flags.tolist() == [0, 0] + [1] * 7 + [0] * 2 + [0] * 6 + [0]


def test_flagfullscanwindows_wraps_around(tt2000: Callable[..., int]) -> None:
    """Test that, as with IDL's shift, a run can continue from the end to the start."""
    key = spp_swp_spc_fullscanseqlookup_defaultkey().tolist()
    w = [*key[3:7], 1, 2, *key[0:3]]
    flags = spp_swp_spc_flagfullscanwindows(_dat(w, tt2000))
    assert flags.tolist() == [1, 1, 1, 1, 0, 0, 1, 1, 1]


def test_flagfullscanwindows_before_key(tt2000: Callable[..., int]) -> None:
    """Test that data before 2019-09-18 cannot be flagged, as in IDL."""
    dat = {
        "window": np.zeros(3, dtype=np.uint8),
        "epoch": np.full(3, tt2000(2019, 1, 1)),
    }
    with pytest.raises(NotImplementedError):
        spp_swp_spc_flagfullscanwindows(dat)
