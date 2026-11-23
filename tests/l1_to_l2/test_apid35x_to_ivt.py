"""Test converting SPC science L1 packets into current–voltage–time series."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
import pytest
from spacepy import pycdf

from pyfaradaycup.l1_to_l2._spp_swp_spc_apid35x_to_ivt import (
    Ivt,
    _cycle_samples,
    _uniq_sorted,
    spp_swp_spc_apid35x_to_ivt,
)
from pyfaradaycup.l1_to_l2._spp_swp_spc_crosstalk_correct import (
    spp_swp_spc_crosstalk_correct,
)
from pyfaradaycup.l1_to_l2._spp_swp_spc_crosstalks import spp_swp_spc_crosstalks
from pyfaradaycup.l1_to_l2._spp_swp_spc_sincosgain2curr import (
    SENSORS,
    spp_swp_spc_sincosgain2curr,
)

if TYPE_CHECKING:
    from collections.abc import Mapping

repo_root = Path(__file__).parent.parent.parent
spc_dir = repo_root / "_psp" / "data" / "sci" / "sweap" / "spc"
l1_dir = spc_dir / "L1"
l2_dir = spc_dir / "L2"
l2_file = l2_dir / "2026" / "08" / "spp_swp_spc_l2_20260803_v00.cdf"


def test_cycle_samples_skips_last_single_sample_cycle() -> None:
    """
    Test that, as with IDL's reverse indices check, a highest-numbered
    cycle with only one sample is skipped, but other cycles are not.
    """
    cyclenum = np.array([1, 1, 2, 3], dtype=np.uint32)
    counts = np.bincount(cyclenum, minlength=4)
    assert _cycle_samples(cyclenum, np.array([1, 2, 3]), counts).tolist() == [0, 1, 2]
    cyclenum = np.array([1, 1, 2, 3, 3], dtype=np.uint32)
    counts = np.bincount(cyclenum, minlength=4)
    assert _cycle_samples(cyclenum, np.array([3]), counts).tolist() == [3, 4]


def test_uniq_sorted() -> None:
    """Test that one index of each value is returned: the last, for repeated values."""
    values = np.array([3, 0, 2, 0, 3])
    assert _uniq_sorted(values).tolist() == [3, 2, 4]


@pytest.fixture(scope="module")
def ivts(l1_data: Mapping[str, Mapping[str, np.ndarray]]) -> dict[str, Ivt]:
    """Return the IVT of each science L1 file for 2026-08-03."""
    return {
        apid: spp_swp_spc_apid35x_to_ivt(dat, l1dir=l1_dir, l2dir=l2_dir)
        for apid, dat in l1_data.items()
    }


def _l2_samples() -> dict[str, np.ndarray]:
    """
    Return the values of each window in the L2 file made in production,
    keyed by the time of the window.
    """
    with pycdf.CDF(str(l2_file)) as cdf:
        epoch = cdf.raw_var("Epoch")[...]
        measurement_time = cdf.raw_var("measurement_time")[...]
        valid = (measurement_time != cdf["measurement_time"].attrs["FILLVAL"]) & (
            cdf.raw_var("mv_lo")[...] != cdf["mv_lo"].attrs["FILLVAL"]
        )
        # Epoch is the time of window 0 of each spectrum, and
        # measurement_time is the time of each window after it
        times = epoch[:, np.newaxis] + np.where(valid, measurement_time, 0).astype(
            np.int64
        )
        samples = {"time": times[valid]}
        for name in (
            "mv_lo",
            "mv_hi",
            "a_current",
            "b_current",
            "c_current",
            "d_current",
        ):
            samples[name] = cdf.raw_var(name)[...][valid]
    return samples


@pytest.mark.parametrize("apid", ["351", "353", "354"])
def test_ivt_matches_idl_l2(apid: str, ivts: Mapping[str, Ivt]) -> None:
    """
    Test that the voltages and crosstalk-corrected currents of each
    sample are exactly the same as in the L2 file made in production.

    Only the samples that are in the L2 file are compared. At times that
    are in both APID 353 and APID 354, the L2 file has the APID 354 sample,
    so the APID 353 samples at those times are left out.
    """
    samples = _l2_samples()
    ivt = ivts[apid]
    keep = np.isin(ivt.time, samples["time"])
    if apid == "353":
        keep &= ~np.isin(ivt.time, ivts["354"].time)
    assert keep.sum() > 0
    order = np.argsort(samples["time"])
    index = order[np.searchsorted(samples["time"], ivt.time[keep], sorter=order)]
    np.testing.assert_array_equal(samples["time"][index], ivt.time[keep])
    for l2_name, ivt_name in [
        ("mv_lo", "mv_lo"),
        ("mv_hi", "mv_hi"),
        ("a_current", "a"),
        ("b_current", "b"),
        ("c_current", "c"),
        ("d_current", "d"),
    ]:
        np.testing.assert_array_equal(
            getattr(ivt, ivt_name)[keep], samples[l2_name][index], err_msg=l2_name
        )


def test_ivt_has_every_l2_sample(ivts: Mapping[str, Ivt]) -> None:
    """Test that every window in the L2 file made in production is a sample of an IVT."""
    times = np.concatenate([ivt.time for ivt in ivts.values()])
    assert np.isin(_l2_samples()["time"], times).all()


def test_ivt_flags(ivts: Mapping[str, Ivt]) -> None:
    """Test the flags and types of the IVTs for 2026-08-03, which has no electron or FA data."""
    for ivt in ivts.values():
        assert ivt.a.dtype == ivt.mv_lo.dtype == np.float32
        assert not ivt.mode.any()
        assert not ivt.famode.any()
        assert ivt.crosstalk_calfile != "none"
    assert ivts["354"].fullscan_flag.any()
    assert not ivts["351"].fullscan_flag.any()


def test_ivt_nocorrect(
    l1_data: Mapping[str, Mapping[str, np.ndarray]], ivts: Mapping[str, Ivt]
) -> None:
    """Test that the crosstalk correction can be skipped, and applied afterward."""
    uncorrected = spp_swp_spc_apid35x_to_ivt(
        l1_data["353"], l1dir=l1_dir, l2dir=l2_dir, nocorrect=True
    )
    assert uncorrected.crosstalk_calfile == "none"
    corrected = spp_swp_spc_crosstalk_correct(uncorrected)
    for sen in SENSORS:
        np.testing.assert_array_equal(
            getattr(corrected, sen), getattr(ivts["353"], sen)
        )


def test_crosstalk_correct_floor(ivts: Mapping[str, Ivt]) -> None:
    """Test that each corrected current is at least the current for DN 1 at gain stage 3."""
    ivt = ivts["354"]
    for sen in SENSORS:
        current_min = spp_swp_spc_sincosgain2curr(1, 0, 3, 0, sen).dat[0]
        assert getattr(ivt, sen).min() >= current_min
    m = spp_swp_spc_crosstalks().dat
    assert m.shape == (4, 4)


def test_apid35x_to_ivt_unknown_packet() -> None:
    """Test that an error is raised for data that is not from APID 351, 353, or 354."""
    with pytest.raises(ValueError, match="incorrectly formatted"):
        spp_swp_spc_apid35x_to_ivt({"epoch": np.zeros(1)}, l1dir=l1_dir, l2dir=l2_dir)
