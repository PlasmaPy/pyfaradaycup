"""Port of ``spp_swp_spc_ivt_to_spectra.pro``."""

from __future__ import annotations

__all__ = ["FILL", "MAX_WINDOWS", "Spectra", "spp_swp_spc_ivt_to_spectra"]

import dataclasses
from typing import TYPE_CHECKING

import numpy as np

from pyfaradaycup.l1_to_l2._spp_swp_spc_parse_cycles import spp_swp_spc_parse_cycles
from pyfaradaycup.utils.idl import label_region

if TYPE_CHECKING:
    import pathlib

    from pyfaradaycup.l1_to_l2._spp_swp_spc_apid35x_to_ivt import Ivt

FILL = -99999
"""The fill value of the spectra."""

MAX_WINDOWS = 128
"""The largest number of windows in a spectrum."""

_INT16 = np.int16
"""The type of IDL's ``indgen``."""


@dataclasses.dataclass(frozen=True)
class Spectra:
    """
    Spectra of current against modulator voltage: one row for each
    measurement cycle.

    This is the structure returned by ``spp_swp_spc_ivt_to_spectra`` in
    IDL, flattened: for example, ``spectra.mv_lo.dat`` becomes `mv_lo`.
    The two-dimensional arrays have the shape ``(nspec, nwin)``, which
    is ``[spec number, window number]`` in IDL, and windows without a
    sample are `FILL`.
    """

    emode: np.ndarray
    """The electron mode flag of each spectrum: 0 for ions and 1 for electrons."""

    time: np.ndarray
    """The ``CDF_TIME_TT2000`` time of each window, in ns."""

    mv_lo: np.ndarray
    """The lower modulator voltage of each window, in volts (``float32``)."""

    mv_hi: np.ndarray
    """The higher modulator voltage of each window, in volts (``float32``)."""

    current: np.ndarray
    """
    The currents of each window on the sensor plates A, B, C, and D, with
    shape ``(nspec, nwin, 4)``, as ``float64`` like IDL's ``dblarr``.
    """

    famode: np.ndarray
    """The flux angle mode flag of each spectrum."""

    fullscan: np.ndarray
    """The full scan flag of each spectrum."""

    cal: np.ndarray
    """The LV calibration mode flag of each spectrum."""

    voltage_calfile: pathlib.Path
    thermal_calfile: str
    gain_calfile: pathlib.Path
    crosstalk_calfile: pathlib.Path | str
    fill: int = FILL


def _indgen_increment(length: int) -> np.ndarray:
    """
    Return ``indgen(length)/128`` from IDL.

    ``indgen`` makes 16-bit integers, which wrap around above 32767, and
    IDL's integer division truncates toward zero.
    """
    index = np.arange(length).astype(_INT16).astype(np.int64)
    return np.sign(index) * (np.abs(index) // MAX_WINDOWS)


def _split_long_cycles(cyclenum: np.ndarray) -> np.ndarray:
    """
    Split each cycle that is longer than 128 samples, such as a flux
    angle dwell, into cycles of up to 128 samples.

    This is the ``while maxlen gt 128`` loop in IDL. The longest cycle is
    split first, and the cycles after it are renumbered. Like IDL, the
    samples of a cycle are assumed to be contiguous.
    """
    cyclenum = cyclenum.copy()
    h = np.bincount(cyclenum)
    longest_cycle = int(np.argmax(h))
    maxlen = h[longest_cycle]
    while maxlen > MAX_WINDOWS:
        thisc = np.flatnonzero(cyclenum == longest_cycle)
        cafter = np.flatnonzero(cyclenum > longest_cycle)
        increment = _indgen_increment(thisc.size)
        cyclenum[thisc] += increment
        if cafter.size > 0:
            cyclenum[cafter] += increment.max()
        else:
            # IDL checks "alen ge 0", which is always true, so with no
            # cycles after this one, where() gives the scalar -1, which
            # IDL takes as the last element
            cyclenum[-1] += increment.max()
        h = np.bincount(cyclenum)
        longest_cycle = int(np.argmax(h))
        maxlen = h[longest_cycle]
    return cyclenum


def spp_swp_spc_ivt_to_spectra(ivt: Ivt) -> Spectra:  # ruff:ignore[C901, PLR0915]
    """
    Divide a current–voltage–time series into spectra, one for each cycle.

    The cycles are numbered by `spp_swp_spc_parse_cycles` from the lower
    modulator voltages, and cycles longer than 128 samples are split.
    Row ``i`` of the spectra holds the samples of cycle ``i``, from its
    first sample to its last. Spectra with no valid times and voltages
    are removed. Each spectrum is flagged as electron mode, full scan, or
    calibration if any of its samples is. Flux angle mode is then
    flagged again for runs of full spectra (with at most one missing
    window) that overlap with spectra flagged as flux angle mode.

    Parameters
    ----------
    ivt : Ivt
        The merged current–voltage–time series.

    Returns
    -------
    Spectra
        The spectra.

    Raises
    ------
    ValueError
        If the samples of a cycle span more windows than the longest
        cycle has, or there are no valid spectra. IDL stops with a
        subscript error in the first case.
    IndexError
        If the last spectrum of a run of flux angle spectra is the last
        spectrum, as in IDL.

    Notes
    -----
    These behaviors of IDL are reproduced:

    - Cycles are numbered from 1, but the rows are for cycles ``0`` to
      ``max(cyclenum) - 1``, so the highest-numbered cycle is never
      stored. Row 0 holds the samples that keep the cycle number 0, if
      they fit, and is usually removed as empty.
    - The samples of a cycle are assumed to be contiguous: everything
      from its first sample to its last is copied, and a cycle that spans
      more than 129 samples is skipped.
    - Each flag is set if any sample in the span has the value 1.
    - When flagging flux angle spectra, ``label_region`` treats the first
      and last spectra as not in a region, so they get the same label,
      and the smallest label that overlaps with flux angle spectra is
      skipped, since it is usually 0, the label of spectra that are not
      full.
    """
    cyclenum = spp_swp_spc_parse_cycles(ivt.mv_lo, ivt.mode).astype(np.int64)
    cyclenum = _split_long_cycles(cyclenum)

    ncycles = int(cyclenum.max())
    h = np.bincount(cyclenum, minlength=ncycles + 1)
    maxlen = int(np.max(h))
    # The reverse indices of histogram() list the samples of each cycle in
    # order, so these are the first and last samples of each cycle
    order = np.argsort(cyclenum, kind="stable")
    ends = np.cumsum(h)
    starts = ends - h

    currents = np.full((ncycles, maxlen, 4), FILL, dtype=np.float64)
    mv_lo = np.full((ncycles, maxlen), FILL, dtype=np.float32)
    mv_hi = np.full((ncycles, maxlen), FILL, dtype=np.float32)
    time = np.full((ncycles, maxlen), FILL, dtype=np.int64)
    emode = np.zeros(ncycles, dtype=np.uint8)
    famode = np.zeros(ncycles, dtype=np.uint8)
    fullscan_flag = np.zeros(ncycles, dtype=np.uint8)
    cal_flag = np.zeros(ncycles, dtype=np.uint8)

    # store cycles in 2D arrays
    sensor_currents = (ivt.a, ivt.b, ivt.c, ivt.d)
    for i in range(ncycles):
        if h[i] == 0:
            continue
        first = order[starts[i]]
        last = order[ends[i] - 1]
        length = last - first
        if length > MAX_WINDOWS:
            continue
        span = slice(first, last + 1)
        if length + 1 > maxlen:
            msg = (
                f"The samples of cycle {i} span {length + 1} windows, which is "
                f"more than the {maxlen} windows of the longest cycle"
            )
            raise ValueError(msg)
        for k, current in enumerate(sensor_currents):
            currents[i, : length + 1, k] = current[span]
        mv_lo[i, : length + 1] = ivt.mv_lo[span]
        mv_hi[i, : length + 1] = ivt.mv_hi[span]
        time[i, : length + 1] = ivt.time[span]
        emode[i] = np.any(ivt.mode[span] == 1)
        famode[i] = np.any(ivt.famode[span] == 1)
        fullscan_flag[i] = np.any(ivt.fullscan_flag[span] == 1)
        cal_flag[i] = np.any(ivt.cal_flag[span] == 1)

    # remove empty or all-fill cycles
    check = (time != FILL) & (mv_lo != FILL)
    valid = np.flatnonzero(check.sum(axis=1) > 0)
    if valid.size == 0:
        msg = "There are no spectra with valid times and voltages"
        raise ValueError(msg)

    # Each region of full spectra (with at most one fill value of mv_lo)
    # that overlaps with spectra flagged as flux angle mode is flagged as
    # flux angle mode. The label 0 is for spectra that are not full.
    nondata = (mv_lo == FILL).sum(axis=1)
    full = (nondata <= 1).astype(np.uint8)
    if full.size > 1:
        full_label = (label_region(full) + 1) * full
    else:
        full_label = full.astype(np.uint32)
    flagged = full_label * famode
    fa_regions = np.unique(flagged)
    newflag = np.zeros(ncycles, dtype=np.int16)
    for region in fa_regions[1:]:
        this = np.flatnonzero(full_label == region)
        if this.size > 0:
            newflag[this] = 1
            # the spectrum at the end may not be full
            end = int(this[-1])  # this is in increasing order
            if end + 1 >= ncycles:
                msg = "A run of flux angle spectra ends at the last spectrum"
                raise IndexError(msg)
            if mv_lo[end, 0] == mv_lo[end + 1, 0]:
                newflag[end + 1] = 1

    return Spectra(
        emode=emode[valid],
        time=time[valid],
        mv_lo=mv_lo[valid],
        mv_hi=mv_hi[valid],
        current=currents[valid],
        famode=newflag[valid],
        fullscan=fullscan_flag[valid],
        cal=cal_flag[valid],
        voltage_calfile=ivt.voltage_calfile,
        thermal_calfile=ivt.thermal_calfile,
        gain_calfile=ivt.gain_calfile,
        crosstalk_calfile=ivt.crosstalk_calfile,
    )
