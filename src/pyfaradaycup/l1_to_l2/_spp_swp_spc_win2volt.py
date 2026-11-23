"""Port of ``spp_swp_spc_win2volt.pro``."""

from __future__ import annotations

__all__ = ["WinVolt", "spp_swp_spc_win2volt"]

import dataclasses
from typing import TYPE_CHECKING

import numpy as np

from pyfaradaycup.l1_to_l2._calibration import _calfile, _read_ascii
from pyfaradaycup.l1_to_l2._spp_swp_spc_hvpsthermalcorrection import (
    spp_swp_spc_hvpsthermalcorrection,
)
from pyfaradaycup.l1_to_l2._spp_swp_spc_totalharmonicdistortion import (
    spp_swp_spc_totalharmonicdistortion,
)

if TYPE_CHECKING:
    import os
    import pathlib

    from numpy.typing import ArrayLike

_NWINDOWS = 256
"""The number of windows in each of the ion and electron voltage tables."""


@dataclasses.dataclass(frozen=True)
class WinVolt:
    """The structure returned by ``spp_swp_spc_win2volt``."""

    low: np.ndarray
    """The lower voltage of each window, as ``float32``."""

    high: np.ndarray
    """The higher voltage of each window, as ``float32``."""

    voltage_calfile: pathlib.Path
    thermal_calfile: str


def spp_swp_spc_win2volt(  # ruff:ignore[PLR0913]
    win: ArrayLike,
    winwidth: ArrayLike,
    elecmode: ArrayLike,
    *,
    t_c: ArrayLike | None,
    calfile: str | os.PathLike[str] | None = None,
    thermal_calfile: str | os.PathLike[str] | None = None,
    thd_calfile: str | os.PathLike[str] | None = None,
) -> WinVolt:
    """
    Return the modulator voltages of the edges of each window.

    The voltages of windows ``win`` and ``win + winwidth`` are looked up
    in the voltage table, for ions or electrons. The width of the window
    is then corrected for the thermal response of the HVPS
    (`spp_swp_spc_hvpsthermalcorrection`) and for the total harmonic
    distortion of the waveform (`spp_swp_spc_totalharmonicdistortion`),
    keeping the middle of the window fixed.

    Parameters
    ----------
    win : array_like
        The window of each sample.
    winwidth : array_like
        The width of each window, in window numbers.
    elecmode : array_like
        The mode of each sample: 0 for ions and 1 for electrons.
    t_c : array_like
        The LV temperature, in °C.
    calfile : path-like, optional
        The voltage table, which has 512 numbers: the voltages of the 256
        ion windows and then of the 256 electron windows. By default, the
        last ``spp_swp_calfiles_spc_mvind2volt_*.txt`` in the calibration
        directory is used.
    thermal_calfile : path-like, optional
        A table of thermal corrections, which is not supported; see the
        notes. The L1 to L2 step does not use it.
    thd_calfile : path-like, optional
        Passed to `spp_swp_spc_totalharmonicdistortion`.

    Returns
    -------
    WinVolt
        The voltages of the edges of each window.

    Raises
    ------
    ValueError
        If ``t_c`` is not given or is 0. IDL stops with an error message.
    NotImplementedError
        If ``thermal_calfile`` is given.
    FileNotFoundError
        If ``calfile`` is not given and there is no voltage table.

    Notes
    -----
    Like IDL, window numbers above 255 are clipped to 255, because IDL
    clips out-of-range subscripts of arrays to the bounds.

    IDL can also correct the window widths by interpolating in a table
    of measured corrections, ``thermal_calfile``, but this is not ported,
    because the L1 to L2 step never passes one.
    """
    if thermal_calfile:
        msg = "Thermal corrections from a calibration file are not supported"
        raise NotImplementedError(msg)
    voltage_calfile = _calfile(calfile, "spp_swp_calfiles_spc_mvind2volt_*.txt")
    read1 = _read_ascii(voltage_calfile)
    # IDL: voltages = [[iv], [ev]], indexed as voltages[win, elecmode]
    voltages = np.stack((read1[0:_NWINDOWS], read1[_NWINDOWS : 2 * _NWINDOWS]), axis=1)
    win = np.asarray(win).astype(np.int64)
    winwidth = np.asarray(winwidth).astype(np.int64)
    mode = np.clip(np.asarray(elecmode).astype(np.int64), 0, 1)
    low = voltages[np.clip(win, 0, _NWINDOWS - 1), mode]
    high = voltages[np.clip(win + winwidth, 0, _NWINDOWS - 1), mode]
    mid = (low + high) / np.float32(2.0)
    dvreq = np.abs(high - low)

    # IDL uses keyword_set(T_C), which is false for 0
    t_c_values = None if t_c is None else np.asarray(t_c)
    if t_c_values is None or (t_c_values.size == 1 and t_c_values.item() == 0):
        msg = "No temperature was given for the thermal correction of the HVPS"
        raise ValueError(msg)

    answer = spp_swp_spc_hvpsthermalcorrection(dvreq, t_c_values)
    # account for harmonic distortion of the waveform as well
    dvactual = spp_swp_spc_totalharmonicdistortion(
        answer.dvact, thd_calfile=thd_calfile
    )

    # re-calculate the voltage window ranges
    half = dvactual / np.float32(2.0)
    return WinVolt(
        low=mid - half,
        high=mid + half,
        voltage_calfile=voltage_calfile,
        thermal_calfile=answer.thermal_calfile,
    )
