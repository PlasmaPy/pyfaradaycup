"""Test merging current–voltage–time series."""

from __future__ import annotations

import datetime
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
import pytest

from pyfaradaycup.l1_to_l2._spp_swp_spc_merge_ivt import (
    NoValidTimesError,
    spp_swp_spc_merge_ivt,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from pyfaradaycup.l1_to_l2._spp_swp_spc_apid35x_to_ivt import Ivt


def test_merge_ivt_orders_and_keeps_last_duplicate(
    make_ivt: Callable[..., Ivt],
) -> None:
    """
    Test that the samples are put in time order, and of samples with the
    same time, the one from the second IVT is kept.
    """
    ivt0 = make_ivt([30, 10, 20], mv_lo=[3.0, 1.0, 2.0])
    ivt1 = make_ivt([25, 20], mv_lo=[2.5, 20.0])
    merged = spp_swp_spc_merge_ivt(ivt0, ivt1)
    assert merged.time.tolist() == [10, 20, 25, 30]
    assert merged.mv_lo.tolist() == [1.0, 20.0, 2.5, 3.0]
    # the currents are the index of each sample in its IVT
    assert merged.a.tolist() == [1.0, 1.0, 0.0, 0.0]
    assert merged.d.tolist() == [1.75, 1.75, 0.75, 0.75]


def test_merge_ivt_removes_invalid_times(make_ivt: Callable[..., Ivt]) -> None:
    """Test that samples with times that are not positive, like fill values, are removed."""
    fill = np.iinfo(np.int64).min
    merged = spp_swp_spc_merge_ivt(make_ivt([fill, 0, 5]), make_ivt([-3, 7]))
    assert merged.time.tolist() == [5, 7]


def test_merge_ivt_no_valid_times(make_ivt: Callable[..., Ivt]) -> None:
    """Test that an error is raised if no times are valid."""
    with pytest.raises(NoValidTimesError, match="valid timestamps"):
        spp_swp_spc_merge_ivt(make_ivt([0]), make_ivt([-1]))


def test_merge_ivt_metadata(make_ivt: Callable[..., Ivt]) -> None:
    """
    Test that the calibration files are from the first IVT, and that, like
    IDL, the merged IVT has no gain stages or gain offsets file.
    """
    ivt0 = make_ivt([1], a_gain=np.zeros(1), offset_calfile=Path("offsets.txt"))
    ivt1 = make_ivt([2], voltage_calfile=Path("other.txt"))
    merged = spp_swp_spc_merge_ivt(ivt0, ivt1)
    assert merged.voltage_calfile == Path("voltage.txt")
    assert merged.crosstalk_calfile == Path("crosstalk.txt")
    assert merged.a_gain is None
    assert merged.offset_calfile is None


def test_merge_ivt_without_second(make_ivt: Callable[..., Ivt]) -> None:
    """Test that the first IVT is returned if there is no second one, as in IDL."""
    ivt0 = make_ivt([2, 1])
    assert spp_swp_spc_merge_ivt(ivt0, None) is ivt0


def test_merge_ivt_date(
    make_ivt: Callable[..., Ivt], tt2000: Callable[..., int]
) -> None:
    """Test that only the samples on a date are kept when it is given."""
    times = [tt2000(2026, 8, 2, 23, 59, 59), tt2000(2026, 8, 3), tt2000(2026, 8, 4)]
    merged = spp_swp_spc_merge_ivt(
        make_ivt(times[:2]), make_ivt(times[2:]), date=datetime.date(2026, 8, 3)
    )
    assert merged.time.tolist() == [times[1]]
    with pytest.raises(NoValidTimesError, match="2026-08-05"):
        spp_swp_spc_merge_ivt(
            make_ivt(times[:2]), make_ivt(times[2:]), date=datetime.date(2026, 8, 5)
        )
