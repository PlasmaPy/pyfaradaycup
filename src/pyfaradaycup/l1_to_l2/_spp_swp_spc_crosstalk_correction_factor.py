"""Port of ``spp_swp_spc_crosstalk_correction_factor.pro``."""

from __future__ import annotations

__all__ = ["CROSSTALK_HISTORY", "spp_swp_spc_crosstalk_correction_factor"]

import datetime
import pathlib
from typing import TYPE_CHECKING

import numpy as np
from scipy.io import readsav
from spacepy import pycdf

from pyfaradaycup.l1_to_l2._calibration import CALIBRATION_DIR
from pyfaradaycup.utils.idl import interpol, value_locate

if TYPE_CHECKING:
    import os

CROSSTALK_HISTORY = CALIBRATION_DIR / "spp_swp_calfiles_spc_crosstalk_history.idl"
"""The default history of the crosstalk coupling coefficients, an IDL save file."""

_TRANSITIONS = [
    datetime.datetime(*time)  # ruff:ignore[DTZ001]  # UTC
    for time in (
        (2020, 9, 29, 23, 0),
        (2020, 9, 29, 23, 10),
        (2021, 1, 15, 15, 0),
        (2021, 1, 15, 15, 30),
        (2021, 1, 19, 21, 0),
        (2021, 1, 19, 21, 12),
        (2021, 4, 26, 19, 30),
        (2021, 4, 26, 20, 0),
    )
]
"""
The start and end of each known coupling or decoupling transition, which
are hard-coded in IDL.
"""


def spp_swp_spc_crosstalk_correction_factor(
    this_epoch: np.ndarray, file: str | os.PathLike[str] | None = None
) -> tuple[np.ndarray, np.ndarray]:
    """
    Return the correction factors for the crosstalk between the sensor plates.

    The factors for the east–west and north–south plate ratios are
    ``1 / (1 - (ac + dc + ab + db))`` and ``1 / (1 - (ca + da + cb + cb))``
    from the coupling coefficients in the history, interpolated linearly
    in time. Points are added at the hard-coded start and end of known
    coupling transitions. Times before the history get factors of 1, and
    times after it get the last factors.

    Parameters
    ----------
    this_epoch : numpy.ndarray
        ``CDF_TIME_TT2000`` values.
    file : path-like, optional
        The IDL save file of the coupling history. Defaults to
        `CROSSTALK_HISTORY`.

    Returns
    -------
    ew : numpy.ndarray
        The correction factor for the east–west ratio ``(A + D - B - C) / I``.
    ns : numpy.ndarray
        The correction factor for the north–south ratio ``(C + D - A - B) / I``.

    Notes
    -----
    As in IDL, the north–south factor uses ``cb`` twice and not ``db``.

    IDL sorts the history with the added points with ``sort``, which is
    not stable, so if an added time equals a time in the history, the
    order of their factors is not defined. Here, the sort is stable.
    """
    path = pathlib.Path(file) if file is not None else CROSSTALK_HISTORY
    history = readsav(str(path))["spp_swp_spc_crosstalk_history"][0]
    coupling = history["COUPLING"]
    cepoch = np.asarray(history["EPOCH"], dtype=np.int64)
    valid = ~np.isnan(coupling["AA"])
    c = {
        name.lower(): np.asarray(coupling[name])[valid] for name in coupling.dtype.names
    }
    cepoch = cepoch[valid]

    one = np.float32(1.0)
    ewfac = one / (one - (c["ac"] + c["dc"] + c["ab"] + c["db"]))
    nsfac = one / (one - (c["ca"] + c["da"] + c["cb"] + c["cb"]))

    add_epoch = np.array(
        [pycdf.lib.datetime_to_tt2000(time) for time in _TRANSITIONS], dtype=np.int64
    )
    loc = value_locate(cepoch, add_epoch)
    # extrapolate the end of each transition forward rather than back
    loc[1::2] += 1
    loc = np.clip(loc, 0, cepoch.size - 1)
    new_cepoch = np.concatenate((cepoch, add_epoch))
    order = np.argsort(new_cepoch, kind="stable")
    new_cepoch = new_cepoch[order]
    new_ewfac = np.concatenate((ewfac, ewfac[loc]))[order]
    new_nsfac = np.concatenate((nsfac, nsfac[loc]))[order]

    this_epoch = np.asarray(this_epoch, dtype=np.int64)
    loc = value_locate(new_cepoch, this_epoch)
    ew = interpol(new_ewfac, new_cepoch, this_epoch, nan=True)
    ns = interpol(new_nsfac, new_cepoch, this_epoch, nan=True)
    first = loc < 0
    last = loc == new_cepoch.size - 1
    ew[first] = 1.0
    ns[first] = 1.0
    ew[last] = new_ewfac[-1]
    ns[last] = new_nsfac[-1]
    return ew, ns
