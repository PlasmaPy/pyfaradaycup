"""Port of ``spp_swp_spc_crosstalk_correct.pro``."""

from __future__ import annotations

__all__ = ["spp_swp_spc_crosstalk_correct"]

import dataclasses
from typing import TYPE_CHECKING

import numpy as np

from pyfaradaycup.l1_to_l2._spp_swp_spc_crosstalks import spp_swp_spc_crosstalks
from pyfaradaycup.l1_to_l2._spp_swp_spc_sincosgain2curr import (
    SENSORS,
    spp_swp_spc_sincosgain2curr,
)

if TYPE_CHECKING:
    import os

    from pyfaradaycup.l1_to_l2._spp_swp_spc_apid35x_to_ivt import Ivt


def spp_swp_spc_crosstalk_correct(
    ivt: Ivt, calfile: str | os.PathLike[str] | None = None
) -> Ivt:
    """
    Correct the currents for the crosstalk between the sensor plates.

    The corrected currents are ``M @ [A, B, C, D]``, with the matrix ``M``
    from `spp_swp_spc_crosstalks`. Since the correction is linear, it can
    overshoot, so each corrected current is raised to at least the
    current for a DN of 1 at gain stage 3 on that plate.

    Parameters
    ----------
    ivt : Ivt
        The current–voltage–time series.
    calfile : path-like, optional
        The sensor crosstalk file, passed to `spp_swp_spc_crosstalks`.

    Returns
    -------
    Ivt
        A copy of ``ivt`` with corrected currents and its
        ``crosstalk_calfile``. IDL changes ``ivt`` in place.

    Notes
    -----
    As in IDL, the smallest currents are computed from the default gain
    and gain offset files, even if ``ivt`` was made with other files.
    Because of the overwritten cosine in `spp_swp_spc_sincosgain2curr`,
    the smallest current on plate C is ``sqrt(2)`` times larger than
    for a DN of 1 alone.
    """
    coupling = spp_swp_spc_crosstalks(calfile)
    m = coupling.dat
    currents = [ivt.a, ivt.b, ivt.c, ivt.d]
    corrected = {}
    for i, sen in enumerate(SENSORS):
        # Summed in the same order as in IDL
        value = currents[0] * m[i, 0]
        for j in range(1, len(SENSORS)):
            value = value + currents[j] * m[i, j]
        current_min = spp_swp_spc_sincosgain2curr(1, 0, 3, 0, sen).dat[0]
        corrected[sen] = np.maximum(value, current_min)
    return dataclasses.replace(
        ivt, **corrected, crosstalk_calfile=coupling.crosstalk_calfile
    )
