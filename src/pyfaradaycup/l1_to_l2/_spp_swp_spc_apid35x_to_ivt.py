"""Port of ``spp_swp_spc_apid35x_to_ivt.pro``."""

from __future__ import annotations

__all__ = ["Ivt", "spp_swp_spc_apid35x_to_ivt"]

import dataclasses
from typing import TYPE_CHECKING

import numpy as np

from pyfaradaycup.l1_to_l2._spp_swp_spc_apid35x_get_currents import (
    spp_swp_spc_apid351_get_currents,
    spp_swp_spc_apid353_get_currents,
    spp_swp_spc_apid354_get_currents,
)
from pyfaradaycup.l1_to_l2._spp_swp_spc_config_and_hsk_lookup import (
    spp_swp_spc_config_and_hsk_lookup,
)
from pyfaradaycup.l1_to_l2._spp_swp_spc_crosstalk_correct import (
    spp_swp_spc_crosstalk_correct,
)
from pyfaradaycup.l1_to_l2._spp_swp_spc_flagfullscanwindows import (
    spp_swp_spc_flagfullscanwindows,
)
from pyfaradaycup.l1_to_l2._spp_swp_spc_parse_cycles import spp_swp_spc_parse_cycles
from pyfaradaycup.l1_to_l2._spp_swp_spc_win2volt import spp_swp_spc_win2volt
from pyfaradaycup.utils.idl import median, uniq

if TYPE_CHECKING:
    import os
    import pathlib
    from collections.abc import Mapping

DEFAULT_TEMPERATURE = np.float32(-31.31)
"""
The default LV temperature, in °C, which is the average temperature when
the survival heater is cycling, as in cruise.
"""

_WINWIDTH_BITS = 16
"""The window width is 4 bits, so it rolls over at 16."""


@dataclasses.dataclass(frozen=True)
class Ivt:
    """
    A current–voltage–time series: one sample for each window.

    This is the structure returned by ``spp_swp_spc_apid35x_to_ivt`` in
    IDL, flattened. For example, ``ivt.mv_lo.dat`` becomes `mv_lo`,
    ``ivt.mv_lo.index`` becomes `mv_lo_index`, and ``ivt.a.gain``
    becomes `a_gain`. Each array has one value for each sample.
    """

    time: np.ndarray
    """The ``CDF_TIME_TT2000`` time of each sample, in ns."""

    mv_lo: np.ndarray
    """The lower modulator voltage of the window, in volts."""

    mv_lo_index: np.ndarray
    """The window number of the lower voltage."""

    mv_hi: np.ndarray
    """The higher modulator voltage of the window, in volts."""

    mv_hi_index: np.ndarray
    """The window number of the higher voltage."""

    a: np.ndarray
    """The current on sensor plate A."""

    b: np.ndarray
    """The current on sensor plate B."""

    c: np.ndarray
    """The current on sensor plate C."""

    d: np.ndarray
    """The current on sensor plate D."""

    a_gain: np.ndarray
    """The gain stage of sensor plate A."""

    b_gain: np.ndarray
    """The gain stage of sensor plate B."""

    c_gain: np.ndarray
    """The gain stage of sensor plate C."""

    d_gain: np.ndarray
    """The gain stage of sensor plate D."""

    mode: np.ndarray
    """The SPC electron mode flag: 0 for ions and 1 for electrons."""

    famode: np.ndarray
    """The flux angle mode flag."""

    fullscan_flag: np.ndarray
    """The full scan measurement cycle flag."""

    cal_flag: np.ndarray
    """The LV calibration mode flag, ``SW_SPC_CALFLAG``."""

    doublewide_flag: np.ndarray
    """The double-width window flag."""

    voltage_calfile: pathlib.Path
    thermal_calfile: str
    gain_calfile: pathlib.Path
    offset_calfile: pathlib.Path
    crosstalk_calfile: pathlib.Path | str = "none"


def _cycle_samples(
    cyclenum: np.ndarray, cycles: np.ndarray, counts: np.ndarray
) -> np.ndarray:
    """
    Return the indices of the samples of each cycle in ``cycles``.

    IDL loops over the cycles, using the reverse indices of
    ``ch = histogram(cyclenum, min=0, max=max(cyclenum), binsize=1,
    reverse_indices=cr)``, and uses the samples of cycle ``k`` only if
    ``n_elements(cr) gt cr[k]+1`` and ``cr[k] ne cr[k+1]``. The second
    condition is that the cycle has samples. The first is that some
    sample is in a cycle numbered below ``k``, or there is more than one
    sample in cycles ``k`` and above. So a highest-numbered cycle with
    only one sample is skipped.

    Parameters
    ----------
    cyclenum : numpy.ndarray
        The cycle number of each sample.
    cycles : numpy.ndarray
        The cycle numbers to select.
    counts : numpy.ndarray
        ``ch``, the number of samples in each cycle.
    """
    before = np.cumsum(counts) - counts
    usable = cycles[(counts[cycles] > 0) & (before[cycles] < cyclenum.size - 1)]
    return np.flatnonzero(np.isin(cyclenum, usable))


def _uniq_sorted(values: np.ndarray) -> np.ndarray:
    """
    Return ``uniq(values, sort(values))``: the index of one element of
    each distinct value.

    IDL's ``sort`` is not stable, so which index IDL returns for a value
    that occurs more than once is not defined. Here, the sort is stable,
    so it is the index of the last occurrence.
    """
    order = np.argsort(values, kind="stable")
    return order[uniq(values[order])]


def spp_swp_spc_apid35x_to_ivt(  # ruff:ignore[C901, PLR0913, PLR0915]
    dat: Mapping[str, np.ndarray],
    *,
    l1dir: str | os.PathLike[str],
    l2dir: str | os.PathLike[str],
    hv_calfile: str | os.PathLike[str] | None = None,
    gain_calfile: str | os.PathLike[str] | None = None,
    offset_calfile: str | os.PathLike[str] | None = None,
    crosstalk_calfile: str | os.PathLike[str] | None = None,
    nocorrect: bool = False,
    thermal_correct: bool = False,
    default_temperature: float | None = None,
) -> Ivt:
    """
    Convert the packets of an SPC science L1 file into a current–voltage–time series.

    The currents on the sensor plates come from the sine and cosine DN
    in the packets. The measurement cycles are numbered, and full scans
    and flux angle cycles are flagged, using the scan settings and
    housekeeping values from `spp_swp_spc_config_and_hsk_lookup`. The
    window widths are corrected for double-width windows in full scans
    and for flux angle cycles, and then converted into modulator voltages
    with `spp_swp_spc_win2volt`. Finally, the currents are corrected for
    crosstalk between the sensor plates.

    Parameters
    ----------
    dat : mapping of str to numpy.ndarray
        The variables of an APID 351, 353, or 354 L1 file, with
        lower-case names. The APID is found from the variables: ``arss``
        for 354, ``asin`` for 353, and ``a0s`` for 351.
    l1dir : path-like
        The L1 directory, with ``YYYY/MM/APID*/`` subdirectories, for the
        APID 35E (config) files.
    l2dir : path-like
        The L2 directory, with ``YYYY/MM/`` subdirectories, for the L2
        housekeeping files.
    hv_calfile : path-like, optional
        The voltage table, passed to `spp_swp_spc_win2volt` as ``calfile``.
    gain_calfile : path-like, optional
        The sensor gains file.
    offset_calfile : path-like, optional
        The sensor gain offsets file.
    crosstalk_calfile : path-like, optional
        The sensor crosstalk file.
    nocorrect : bool, default: False
        Whether to skip the crosstalk correction.
    thermal_correct : bool, default: False
        Whether to correct the window widths with the measured LV
        temperature, ``SW_SPC_LVTEMP``, rather than ``default_temperature``.
    default_temperature : float, optional
        The LV temperature to use without ``thermal_correct``, in °C.
        Defaults to `DEFAULT_TEMPERATURE` (-31.31 °C).

    Returns
    -------
    Ivt
        The current–voltage–time series.

    Raises
    ------
    ValueError
        If ``dat`` is not from one of APIDs 351, 353, and 354. IDL stops
        with an error message.

    Notes
    -----
    The ``control`` structure of the IDL function is not supported; its
    tags are keyword arguments instead. IDL also computes several
    quantities that are not used, such as guesses of the highest and
    lowest windows, which are not ported.

    The full scan candidates are the cycles in both
    ``cyclenum[uniq(has_dble, sort(has_dble))]`` and
    ``cyclenum[uniq(has_fseq, sort(has_fseq))]``. For the value 0 of
    ``has_dble`` or ``has_fseq``, this selects the cycle number of an
    arbitrary sample, which depends on how IDL's ``sort`` orders ties.
    Here, it is the cycle number of the last such sample. Depending on
    that cycle, a cycle can be flagged as a full scan, or not, unlike
    in IDL.
    """
    temperature = default_temperature or DEFAULT_TEMPERATURE

    is_rss = "arss" in dat  # RSS packet from SWEM (APID 354)
    is_sci = "asin" in dat  # science packet from SPC (APID 353)
    is_ag = "a0s" in dat  # all-gain diagnostic packet from SPC (APID 351)
    if is_rss + is_sci + is_ag != 1:
        msg = "No data or incorrectly formatted data"
        raise ValueError(msg)
    if is_rss:
        get_currents = spp_swp_spc_apid354_get_currents
    elif is_sci:
        get_currents = spp_swp_spc_apid353_get_currents
    else:
        get_currents = spp_swp_spc_apid351_get_currents
    qflux = get_currents(dat, gain_calfile=gain_calfile, offset_calfile=offset_calfile)

    w = np.asarray(dat["window"])
    dw = np.asarray(dat["spc_winwidth"])
    el = np.asarray(dat["spc_elecmode"])
    cflag = np.asarray(dat["sw_spc_calflag"])
    epoch = np.asarray(dat["epoch"], dtype=np.int64)

    # Look up the control and housekeeping variables
    config = spp_swp_spc_config_and_hsk_lookup(epoch, l1dir=l1dir, l2dir=l2dir)

    fs_screen = spp_swp_spc_flagfullscanwindows(dat, config.sw_spc_doublewidth)
    is_doublewide = ((fs_screen == 1) & (w <= config.sw_spc_doublewidth)).astype(
        np.uint8
    )

    cyclenum = spp_swp_spc_parse_cycles(w, el)

    is_notfa = (config.sw_spc_fa == 0).astype(np.uint8)

    # Find the cycle numbers of full scan candidates
    has_dble = cyclenum * is_doublewide * is_notfa
    has_fseq = cyclenum * fs_screen * is_notfa
    cand1 = cyclenum[_uniq_sorted(has_dble)]
    cand2 = cyclenum[_uniq_sorted(has_fseq)]
    max_cycle = int(cyclenum.max())
    nbins = max_cycle + 1
    h = np.bincount(np.concatenate((cand1, cand2)), minlength=nbins)
    fs_candidates = np.flatnonzero(h == 2)  # ruff:ignore[PLR2004]

    # Flag the full scans
    fullscan_flag = np.zeros(w.shape, dtype=np.uint8)
    ch = np.bincount(cyclenum, minlength=nbins)
    if fs_candidates.size > 0 and max_cycle > 1:
        fullscan_flag[_cycle_samples(cyclenum, fs_candidates, ch)] = 1

    # Also identify likely flux angle modes, which should show up as very
    # long cycles confirmed by housekeeping
    fa_flag = np.zeros(w.shape, dtype=np.int16)
    fa_cycles = cyclenum * config.sw_spc_fa
    # Like histogram(..., min=0, max=max(cyclenum)), which leaves out
    # values above the maximum
    fh = np.bincount(fa_cycles[fa_cycles <= max_cycle], minlength=nbins)
    fa_cand = np.flatnonzero((ch > median(ch)) & (fh > 1))
    if fa_cand.size > 0 and max_cycle > 1:
        fa_flag[_cycle_samples(cyclenum, fa_cand, ch)] = 1

    # Correct the window widths in flux angle mode, using the largest
    # flux angle window width from the config files in each cycle
    mask = config.spc_fawinwidth * config.sw_spc_fa * fa_flag
    fawinwidth = np.zeros(mask.shape, dtype=mask.dtype)
    if fa_cand.size > 0:
        before = np.cumsum(ch) - ch
        for k in fa_cand:
            if ch[k] > 0 and before[k] < cyclenum.size - 1:
                members = cyclenum == k
                fawinwidth[members] = mask[members].max()

    # Where fawinwidth is nonzero, substitute it for dw
    dw = dw * (fawinwidth == 0) + fawinwidth

    # The double-width threshold for full scans, and 0 elsewhere
    doublewidth_guess = np.zeros(w.shape, dtype=np.int16)
    for mode in (1, 0):
        selected = (el == mode) & (fullscan_flag == 1)
        if selected.any():
            doublewidth_guess[selected] = median(config.sw_spc_doublewidth[selected])

    # Correct the double-wide windows. The window width is 4 bits, so it
    # rolls over above 15, as it did when commanded to in Encounter 2.
    dw_corr = (dw + dw * (w <= doublewidth_guess)) % _WINWIDTH_BITS

    # Get the modulator voltages
    t_c = config.sw_spc_lvtemp if thermal_correct else temperature
    v = spp_swp_spc_win2volt(w, dw_corr, el, calfile=hv_calfile, t_c=t_c)

    ivt = Ivt(
        time=epoch,
        mv_lo=v.low,
        mv_lo_index=w,
        mv_hi=v.high,
        mv_hi_index=w + dw_corr,
        a=qflux.a.dat,
        b=qflux.b.dat,
        c=qflux.c.dat,
        d=qflux.d.dat,
        a_gain=qflux.a.gain,
        b_gain=qflux.b.gain,
        c_gain=qflux.c.gain,
        d_gain=qflux.d.gain,
        mode=el.astype(np.uint8),
        famode=fa_flag,
        fullscan_flag=fullscan_flag,
        cal_flag=cflag,
        doublewide_flag=is_doublewide,
        voltage_calfile=v.voltage_calfile,
        thermal_calfile=v.thermal_calfile,
        gain_calfile=qflux.a.gain_calfile,
        offset_calfile=qflux.a.offset_calfile,
    )
    # Correct for the crosstalk between the sensor plates
    if not nocorrect:
        ivt = spp_swp_spc_crosstalk_correct(ivt, calfile=crosstalk_calfile)
    return ivt
