"""Port of ``spp_swp_spc_totalharmonicdistortion.pro``."""

from __future__ import annotations

__all__ = ["spp_swp_spc_totalharmonicdistortion"]

import logging
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    import os

    from numpy.typing import ArrayLike

logger = logging.getLogger(__name__)

_f = np.float32

_DEFAULT_FILLVAL = _f(-9999.0)


def spp_swp_spc_totalharmonicdistortion(
    dvreq: ArrayLike,
    thd_calfile: str | os.PathLike[str] | None = None,
    fillval: float | None = None,
) -> np.ndarray:
    """
    Correct the effective window widths for the total harmonic distortion
    of the high voltage waveform.

    The effective width is ``dvreq * clip(0.0135 * |dvreq| + 0.27, 0.5, 0.85)``:
    a 15% deficit for windows wider than about 43 V, a 50% deficit for
    windows narrower than about 17 V, and a linear function of the width
    between them.

    Parameters
    ----------
    dvreq : array_like
        The window widths, in volts.
    thd_calfile : path-like, optional
        A calibration file for the correction, which is not implemented,
        as in IDL. If it is given, a message is logged and the empirical
        formula is used.
    fillval : float, optional
        Window widths with this value are treated as fill and are not
        changed. Defaults to ``-9999.``.

    Returns
    -------
    numpy.ndarray
        The effective window widths, as ``float32``.

    Notes
    -----
    The correction is from M. L. Stevens (2019-02-26), described in the
    IDL source and the email thread "[psp-wg-calibration] Initial go at
    correction to SPC HVPS". It attributes the deficit in SPC signal
    found by comparing with the FIELDS electron plasma frequency
    entirely to harmonic distortion. There is no published reference.
    """
    if thd_calfile:
        logger.info(
            "Table-based correction for total harmonic distortion is not yet "
            "implemented; using the empirical formula"
        )
    fill = _f(fillval) if fillval else _DEFAULT_FILLVAL
    dvreq = np.asarray(dvreq, dtype=np.float32)
    # IDL: ((0.0135*abs(dvreq)+0.27) < 0.85) > 0.5
    distortion_factor = np.maximum(
        np.minimum(_f(0.0135) * np.abs(dvreq) + _f(0.27), _f(0.85)), _f(0.5)
    )
    distortion_factor[dvreq == fill] = 1.0
    return dvreq * distortion_factor
