"""Test dividing current–voltage–time series into spectra."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
import pytest
from spacepy import pycdf

from pyfaradaycup.l1_to_l2._spp_swp_spc_ivt_to_spectra import (
    FILL,
    MAX_WINDOWS,
    Spectra,
    _indgen_increment,
    _split_long_cycles,
    spp_swp_spc_ivt_to_spectra,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from pyfaradaycup.l1_to_l2._spp_swp_spc_apid35x_to_ivt import Ivt

repo_root = Path(__file__).parent.parent.parent
spc_dir = repo_root / "_psp" / "data" / "sci" / "sweap" / "spc"
l1_dir = spc_dir / "L1"
l2_dir = spc_dir / "L2"
l2_file = l2_dir / "2026" / "08" / "spp_swp_spc_l2_20260803_v00.cdf"


def test_indgen_increment() -> None:
    """
    Test that the increments are 0 for 128 samples, then 1, and so on,
    with IDL's 16-bit indgen wrapping above 32767 and division
    truncating toward zero.
    """
    increment = _indgen_increment(300)
    assert increment[:128].tolist() == [0] * 128
    assert increment[128:256].tolist() == [1] * 128
    assert increment[256:].tolist() == [2] * 44
    wrapped = _indgen_increment(32770)
    assert wrapped[32767] == 255  # ruff:ignore[PLR2004]
    assert wrapped[32768] == -256  # ruff:ignore[PLR2004]  # -32768 / 128


def test_split_long_cycles() -> None:
    """Test that a cycle longer than 128 samples is split, and later cycles are renumbered."""
    cyclenum = np.array([1] * 5 + [2] * 300 + [3] * 5, dtype=np.int64)
    split = _split_long_cycles(cyclenum)
    assert np.bincount(split).tolist() == [0, 5, 128, 128, 44, 5]
    assert cyclenum[5] == 2  # the input is not changed  # ruff:ignore[PLR2004]


def test_split_long_cycles_last_cycle() -> None:
    """
    Test that, as in IDL, when the longest cycle is the last one, the last
    sample is incremented again, since IDL's where() gives -1.
    """
    split = _split_long_cycles(np.array([1] * 5 + [2] * 200, dtype=np.int64))
    assert np.bincount(split).tolist() == [0, 5, 128, 71, 1]
    assert split[-1] == 4  # ruff:ignore[PLR2004]


def _scans(*lengths: int) -> list[float]:
    """Return ascending ion scans of the given lengths, starting at 1 V."""
    return [float(v) for n in lengths for v in range(1, n + 1)]


def test_ivt_to_spectra_rows(make_ivt: Callable[..., Ivt]) -> None:
    """
    Test that each cycle is a row, padded with fill values, and the
    highest-numbered cycle is not stored, as in IDL.
    """
    mv_lo = _scans(3, 5, 4)
    spectra = spp_swp_spc_ivt_to_spectra(make_ivt(list(range(1, 13)), mv_lo=mv_lo))
    # Cycle 1 (3 samples) is row 1 and cycle 2 (5) is row 2; row 0 is
    # empty and removed; cycle 3 (4) is not stored
    assert spectra.mv_lo.shape == (2, 5)
    assert spectra.mv_lo.tolist() == [[1, 2, 3, FILL, FILL], [1, 2, 3, 4, 5]]
    assert spectra.time.tolist() == [[1, 2, 3, FILL, FILL], [4, 5, 6, 7, 8]]
    assert spectra.current.dtype == np.float64
    assert spectra.current[1, :, 0].tolist() == [3, 4, 5, 6, 7]
    assert spectra.current[1, :, 3].tolist() == [3.75, 4.75, 5.75, 6.75, 7.75]
    assert spectra.mv_hi[0, 0] == 2.0  # ruff:ignore[PLR2004]


def test_ivt_to_spectra_flags(make_ivt: Callable[..., Ivt]) -> None:
    """Test that a spectrum is flagged if any of its samples is flagged with 1."""
    mv_lo = _scans(3, 3, 3, 3)
    n = len(mv_lo)
    fullscan = np.zeros(n)
    fullscan[4] = 1
    cal = np.zeros(n)
    cal[6] = 2  # only the value 1 counts
    cal[7] = 1
    mode = np.zeros(n)
    mode[0] = 1
    spectra = spp_swp_spc_ivt_to_spectra(
        make_ivt(
            list(range(1, n + 1)),
            mv_lo=mv_lo,
            fullscan_flag=fullscan,
            cal_flag=cal,
            mode=mode,
        )
    )
    assert spectra.fullscan.tolist() == [0, 1, 0]
    assert spectra.cal.tolist() == [0, 0, 1]
    assert spectra.emode.tolist() == [1, 0, 0]


def test_ivt_to_spectra_famode(make_ivt: Callable[..., Ivt]) -> None:
    """
    Test that flux angle mode is flagged for each run of full spectra that
    overlaps with a flux angle sample, and for the spectrum after the run
    if its first voltage is the same, even if it is not full.
    """
    # 6 cycles of 4 windows, then a cycle of 2, then a last cycle, which
    # is not stored
    mv_lo = _scans(4, 4, 4, 4, 4, 4, 2, 4)
    n = len(mv_lo)
    famode = np.zeros(n)
    famode[9] = 1  # in the third cycle
    spectra = spp_swp_spc_ivt_to_spectra(
        make_ivt(list(range(1, n + 1)), mv_lo=mv_lo, famode=famode)
    )
    # The 6 full spectra are a region that overlaps the flux angle sample.
    # The 7th spectrum, with 2 windows, is flagged after it.
    assert spectra.mv_lo.shape == (7, 4)
    assert spectra.famode.tolist() == [1] * 7
    # Without the flux angle sample, nothing is flagged
    unflagged = spp_swp_spc_ivt_to_spectra(make_ivt(list(range(1, n + 1)), mv_lo=mv_lo))
    assert unflagged.famode.tolist() == [0] * 7


def test_ivt_to_spectra_non_contiguous_cycle(make_ivt: Callable[..., Ivt]) -> None:
    """
    Test that an error is raised when a cycle spans more windows than the
    longest cycle, where IDL stops with a subscript error.
    """
    # As in the parse_cycles tests, the first of 11 zeros and the trailing
    # retrace keep the cycle number 0, so cycle 0 spans 15 windows, while
    # the longest cycle has 13
    mv_lo = [10.0, 20.0, 30.0, 40.0] + [25.0] * 10 + [10.0, 20.0, 30.0, 40.0, 5.0]
    with pytest.raises(ValueError, match="span 15 windows"):
        spp_swp_spc_ivt_to_spectra(
            make_ivt(list(range(1, len(mv_lo) + 1)), mv_lo=mv_lo)
        )


def test_spectra_match_idl_l2(spectra: Spectra) -> None:
    """
    Test that the spectra are exactly the same as in the L2 file made in
    production: the times, voltages, currents, and the flags that make up
    MODE_FLAG.
    """
    with pycdf.CDF(str(l2_file)) as cdf:
        expected = {name: cdf.raw_var(name)[...] for name in cdf}
        fillval = {name: cdf[name].attrs.get("FILLVAL") for name in cdf}
    nspec, nwin = spectra.time.shape
    assert nwin <= MAX_WINDOWS
    assert nspec == expected["Epoch"].size

    # Epoch is the earliest time in each spectrum
    valid_time = spectra.time != FILL
    epoch = np.where(valid_time, spectra.time, np.iinfo(np.int64).max).min(axis=1)
    np.testing.assert_array_equal(epoch, expected["Epoch"])
    # measurement_time is the time of each window after that of window 0
    measurement_time = np.where(
        valid_time, spectra.time - spectra.time[:, :1], fillval["measurement_time"]
    )
    np.testing.assert_array_equal(
        measurement_time, expected["measurement_time"][:, :nwin]
    )

    for name in ("mv_lo", "mv_hi"):
        values = np.where(
            getattr(spectra, name) == FILL, fillval[name], getattr(spectra, name)
        )
        np.testing.assert_array_equal(values, expected[name][:, :nwin], err_msg=name)
        assert (expected[name][:, nwin:] == fillval[name]).all()
    for k, sen in enumerate("abcd"):
        name = f"{sen}_current"
        current = np.where(
            spectra.current[:, :, k] == FILL, fillval[name], spectra.current[:, :, k]
        ).astype(np.float32)
        np.testing.assert_array_equal(current, expected[name][:, :nwin], err_msg=name)

    mode_flag = (
        spectra.fullscan + 2 * spectra.famode + 3 * spectra.cal + 4 * spectra.emode
    )
    np.testing.assert_array_equal(mode_flag, expected["MODE_FLAG"])
