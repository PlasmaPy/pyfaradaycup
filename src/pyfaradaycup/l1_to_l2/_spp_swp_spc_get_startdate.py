"""Port of ``spp_swp_spc_get_startdate.pro``."""

from __future__ import annotations

__all__ = ["spp_swp_spc_get_startdate"]

import datetime
from typing import TYPE_CHECKING

import numpy as np

from pyfaradaycup.utils.idl import cdf_epoch_tojuldays

if TYPE_CHECKING:
    from pyfaradaycup.l1_to_l2._spp_swp_spc_ivt_to_spectra import Spectra

_JDN_OF_ORDINAL_ZERO = 1721425
"""The Julian day number of the day before 0001-01-01."""


def spp_swp_spc_get_startdate(spectra: Spectra) -> datetime.date:
    """
    Return the date (in UTC) of the earliest time in the spectra.

    Parameters
    ----------
    spectra : Spectra
        The spectra.

    Returns
    -------
    datetime.date
        The date of the earliest time that is not fill.

    Raises
    ------
    ValueError
        If every time is fill.
    """
    ok = spectra.time > spectra.fill
    if not ok.any():
        msg = "Every time in the spectra is fill"
        raise ValueError(msg)
    jd = cdf_epoch_tojuldays(spectra.time[ok]).min()
    return datetime.date.fromordinal(int(np.floor(jd + 0.5)) - _JDN_OF_ORDINAL_ZERO)
