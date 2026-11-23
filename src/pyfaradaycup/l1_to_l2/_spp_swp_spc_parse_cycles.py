"""Port of ``spp_swp_spc_parse_cycles.pro``."""

from __future__ import annotations

__all__ = ["spp_swp_spc_parse_cycles"]

import numpy as np

from pyfaradaycup.utils.idl import label_region, median

_NRT = 10
"""
The longest retrace that is expected, in samples. Longer runs of
constant voltage are flux angle series, which get their own cycle
number. It is also the number of passes made to fill in retraces.
"""


def _label_padded(data: np.ndarray) -> np.ndarray:
    """Return ``label_region([0, data, 0], /ulong)`` without the padding."""
    return label_region(np.concatenate(([0], data, [0])))[1:-1]


def spp_swp_spc_parse_cycles(v: np.ndarray, mode: np.ndarray) -> np.ndarray:
    """
    Assign a number to each measurement cycle in a series of windows.

    A cycle is a run of ascending positive windows in ion mode, or of
    descending negative windows in electron mode, where electron-mode
    windows given as positive numbers are made negative first. Each run
    of constant windows that is longer than 10 samples, as in a flux
    angle series, also gets its own cycle number. The samples between
    cycles, such as retraces, get the number of the cycle after them.

    Parameters
    ----------
    v : numpy.ndarray
        The window of each sample.
    mode : numpy.ndarray
        The mode of each sample: 0 for ions and 1 for electrons.

    Returns
    -------
    numpy.ndarray
        The cycle number (of dtype ``uint32``, starting at 1) of each
        sample. Samples that are still 0 after 10 passes of filling in
        retraces keep the number 0.

    Notes
    -----
    As in IDL, `numpy.roll` (IDL's ``shift``) wraps around, so the first
    and last samples are compared with each other.
    """
    mode = np.asarray(mode)
    v = np.asarray(v)
    rect = (mode == 1) & (v > 0)
    sign = np.where(rect, np.float32(-1.0), np.float32(1.0))
    v = v.astype(np.float32) * sign

    # group ascending positive segments (ion mode): either a step up, or
    # the last step of a retrace
    prev = np.roll(v, 1)
    nxt = np.roll(v, -1)
    ascending = ((v > prev) & (nxt != v)) | ((v == prev) & (nxt > v))
    ascending &= (mode == 0) & (v > 0)

    # group descending negative segments (electron mode)
    descending = ((v < prev) & (nxt != v)) | ((v == prev) & (nxt < v))
    descending &= (mode == 1) & (v < 0)

    stepping = ascending.astype(np.uint8) + descending.astype(np.uint8)
    last = v.size - 1
    if v[last] > v[last - 1]:
        stepping[last] = 1

    # assign each group a cycle number (padding the array first)
    cyclenum = _label_padded(stepping)

    # A retrace has the same value as the first step of the series after
    # it, while a flux angle series does not
    zgrp = _label_padded(cyclenum == 0)
    nzgrp = int(zgrp.max(initial=0))
    # The number of samples in each zero region, like
    # histogram(zgrp, min=1, max=max(zgrp), binsize=1)
    counts = np.bincount(zgrp, minlength=nzgrp + 1)[1:]
    long_groups = np.flatnonzero(counts > _NRT) + 1
    for group in long_groups:
        thisregion = zgrp == group
        # isolate the flux angle value, since a retrace could be attached
        targval = median(v[thisregion])
        flatregion = np.flatnonzero(thisregion & (v == targval))
        if flatregion.size > _NRT:
            # give the flat region a new cycle number after the one before it
            lower_cn = cyclenum[: flatregion[0] + 1].max()
            cyclenum = cyclenum + (cyclenum > lower_cn).astype(np.uint32)
            cyclenum[flatregion] = lower_cn + 1

    # fill in retraces and other zeros with the next cycle number, with
    # all of the zeros in each pass filled at once
    n = cyclenum.size
    tk = np.flatnonzero(cyclenum == 0)
    rt = 0
    while tk.size > 0 and rt < _NRT:
        cyclenum[tk] = cyclenum[np.minimum(tk + 1, n - 1)]
        tk = np.flatnonzero(cyclenum == 0)
        rt += 1
    return cyclenum
