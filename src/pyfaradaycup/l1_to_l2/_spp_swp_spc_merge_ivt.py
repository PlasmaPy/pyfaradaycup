"""Port of ``spp_swp_spc_merge_ivt.pro``."""

from __future__ import annotations

__all__ = ["NoValidTimesError", "spp_swp_spc_merge_ivt"]

import datetime
import logging

import numpy as np
from spacepy import pycdf

from pyfaradaycup.l1_to_l2._spp_swp_spc_apid35x_to_ivt import Ivt
from pyfaradaycup.utils.idl import uniq

logger = logging.getLogger(__name__)

_MERGED_FIELDS = (
    "time",
    "mv_lo",
    "mv_lo_index",
    "mv_hi",
    "mv_hi_index",
    "a",
    "b",
    "c",
    "d",
    "mode",
    "famode",
    "fullscan_flag",
    "cal_flag",
    "doublewide_flag",
)
"""The fields of the IVTs that are concatenated and kept in the merged IVT."""


class NoValidTimesError(ValueError):
    """Raised when merged IVTs have no samples with valid times."""


def spp_swp_spc_merge_ivt(
    ivt0: Ivt, ivt1: Ivt | None, date: datetime.date | None = None
) -> Ivt:
    """
    Merge two IVTs into one that is in time order, without duplicate times.

    The samples of the two IVTs are concatenated and sorted by time. Of
    the samples with the same time, the one that comes last (from
    ``ivt1``, if both have it) is kept. Samples with times that are not
    positive, such as fill values, are removed.

    Parameters
    ----------
    ivt0 : Ivt
        The first IVT, whose calibration files are kept.
    ivt1 : Ivt or None
        The second IVT. If it is `None`, ``ivt0`` is returned unchanged,
        like IDL when ``ivt1`` is not a structure.
    date : datetime.date, optional
        If given, only the samples on this date (in UTC) are kept. The
        L1 to L2 step does not use this.

    Returns
    -------
    Ivt
        The merged IVT. Like IDL, it has no gain stages or gain offsets
        file.

    Raises
    ------
    NoValidTimesError
        If no samples have valid times, or none are on ``date``. IDL
        prints an error message and returns ``-1``.

    Notes
    -----
    IDL sorts with ``sort(time, /l64)``, which is not stable, and then
    keeps the last of each run of equal times with ``uniq``. So which of
    two samples with the same time IDL keeps is not defined. Here, the
    sort is stable, so the sample that comes later in the concatenation
    is kept. When the IVTs of APIDs 351, 353, and 354 are merged in that
    order, this keeps the APID 354 samples at times that are also in
    APID 353, which is what the L2 file made in production for
    2026-08-03 has.
    """
    if ivt1 is None:
        return ivt0
    merged = {
        name: np.concatenate((getattr(ivt0, name), getattr(ivt1, name)))
        for name in _MERGED_FIELDS
    }
    time = merged["time"]

    # time order, and the subset of it without duplicates
    ord_ = np.argsort(time, kind="stable")
    tk = ord_[uniq(time[ord_])]

    # unselect any invalid times
    tk = tk[time[tk] > 0]
    if tk.size == 0:
        msg = "No data with valid timestamps"
        raise NoValidTimesError(msg)

    # if merging only to a particular date, then select the part on that date
    if date is not None:
        start = pycdf.lib.datetime_to_tt2000(
            datetime.datetime(date.year, date.month, date.day)  # ruff:ignore[DTZ001]  # UTC
        )
        stop = pycdf.lib.datetime_to_tt2000(
            datetime.datetime(date.year, date.month, date.day)  # ruff:ignore[DTZ001]  # UTC
            + datetime.timedelta(days=1)
        )
        tk = tk[(time[tk] >= start) & (time[tk] < stop)]
        if tk.size == 0:
            msg = f"No data on {date.isoformat()}"
            raise NoValidTimesError(msg)

    return Ivt(
        **{name: values[tk] for name, values in merged.items()},
        a_gain=None,
        b_gain=None,
        c_gain=None,
        d_gain=None,
        voltage_calfile=ivt0.voltage_calfile,
        thermal_calfile=ivt0.thermal_calfile,
        gain_calfile=ivt0.gain_calfile,
        offset_calfile=None,
        crosstalk_calfile=ivt0.crosstalk_calfile,
    )
