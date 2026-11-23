"""
Port of ``spp_swp_spc_flagfullscanwindows.pro``, which also defines
``spp_swp_spc_fullscanseqlookup`` and
``spp_swp_spc_fullscanseqlookup_defaultkey``.
"""

from __future__ import annotations

__all__ = [
    "spp_swp_spc_flagfullscanwindows",
    "spp_swp_spc_fullscanseqlookup",
    "spp_swp_spc_fullscanseqlookup_defaultkey",
]

import datetime
from typing import TYPE_CHECKING

import numpy as np
from spacepy import pycdf

from pyfaradaycup.utils.idl import median

if TYPE_CHECKING:
    from collections.abc import Mapping

_MATCH_LENGTH = 7
"""The number of consecutive windows that must match the full scan key."""

_FULLSCAN_KEY_START = datetime.datetime(2019, 9, 18)  # ruff:ignore[DTZ001]  # UTC
"""The first time that the default full scan key is known to apply."""


def spp_swp_spc_fullscanseqlookup_defaultkey() -> np.ndarray:
    """
    Return the default sequence of windows in a full scan.

    Returns
    -------
    numpy.ndarray
        The 31 windows (of dtype ``uint8``) of a full scan.
    """
    return np.array(
        [8, 8, 8, 16, 24, 32, 40, 48, 56, 64, 72, 80, 88, 96, 104, 112, 124,
         136, 148, 154, 160, 166, 172, 178, 184, 190, 196, 202, 208, 214, 220],
        dtype=np.uint8,
    )  # fmt: skip


def spp_swp_spc_fullscanseqlookup(epoch: np.ndarray) -> np.ndarray:
    """
    Return the sequence of windows in a full scan at the times ``epoch``.

    Parameters
    ----------
    epoch : numpy.ndarray
        ``CDF_TIME_TT2000`` values.

    Returns
    -------
    numpy.ndarray
        The windows (of dtype ``uint8``) of a full scan.

    Raises
    ------
    NotImplementedError
        If the median time is before 2019-09-18, for which the full scan
        sequence is not known. IDL stops with an error message.
    """
    ref_epoch = pycdf.lib.datetime_to_tt2000(_FULLSCAN_KEY_START)
    if median(np.asarray(epoch, dtype=np.int64)) >= ref_epoch:
        return spp_swp_spc_fullscanseqlookup_defaultkey()
    msg = "The full scan sequence is not yet implemented for times before 2019-09-18"
    raise NotImplementedError(msg)


def spp_swp_spc_flagfullscanwindows(
    dat: Mapping[str, np.ndarray],
    sw_spc_doublewidth: np.ndarray | None = None,  # ruff:ignore[ARG001]  # unused in IDL
) -> np.ndarray:
    """
    Flag the samples that are part of a full scan sequence of windows.

    A sample is flagged if it is in any run of 7 consecutive windows
    that matches 7 consecutive windows of the full scan key from
    `spp_swp_spc_fullscanseqlookup`.

    Parameters
    ----------
    dat : mapping of str to numpy.ndarray
        The variables of an APID 351, 353, or 354 L1 file, with
        lower-case names.
    sw_spc_doublewidth : numpy.ndarray, optional
        Not used, as in IDL.

    Returns
    -------
    numpy.ndarray
        The flag (of dtype ``uint8``) of each sample.

    Notes
    -----
    As in IDL, `numpy.roll` (IDL's ``shift``) wraps around, so a run can
    continue from the end of the array to its start. IDL also computes
    several quantities that are not used, such as jumps in time, which
    are not ported.
    """
    fseq = spp_swp_spc_fullscanseqlookup(dat["epoch"])
    w = np.asarray(dat["window"])
    shifted = [np.roll(w, -k) for k in range(_MATCH_LENGTH)]
    match = np.zeros(w.shape, dtype=np.int64)
    for i in range(fseq.size - _MATCH_LENGTH + 1):
        is_match = np.ones(w.shape, dtype=bool)
        for k in range(_MATCH_LENGTH):
            is_match &= shifted[k] == fseq[i + k]
        match += is_match
    # flag the 7 samples of each match
    flagged = match.copy()
    for k in range(1, _MATCH_LENGTH):
        flagged += np.roll(match, k)
    return (flagged > 0).astype(np.uint8)
