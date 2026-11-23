"""Port of the cold plasma part of ``spp_swp_spc_get_effective_area.pro``."""

from __future__ import annotations

__all__ = ["EffectiveArea", "spp_swp_spc_get_effective_area"]

import dataclasses
import pathlib
from typing import TYPE_CHECKING

import numpy as np
from scipy.io import readsav

from pyfaradaycup.l1_to_l2._calibration import CALIBRATION_DIR
from pyfaradaycup.l1_to_l2._spp_swp_spc_moments import DTOR
from pyfaradaycup.utils.idl import interpol

if TYPE_CHECKING:
    import os

EFFECTIVE_AREA_TABLE = (
    CALIBRATION_DIR / "spp_swp_calfiles_spc_effectiveAreaTable_v0.idl"
)
"""The default table of effective areas, an IDL save file."""


@dataclasses.dataclass(frozen=True)
class EffectiveArea:
    """The structure returned by ``spp_swp_spc_get_effective_area``."""

    dat: np.ndarray
    """The effective area, in mm² (``float32``)."""

    units: str = "mm^2"
    desc: str = "Effective Area of SPC sensor. Cold plasma limit"


def _float32_function(function: np.ufunc, x: np.ndarray) -> np.ndarray:
    """
    Evaluate a function of ``float32`` values with a correctly rounded
    ``float32`` result.

    NumPy's ``float32`` versions of some functions, such as `numpy.tan`,
    are not always correctly rounded, unlike those IDL uses, so the
    function is evaluated in ``float64`` and rounded.
    """
    return function(np.asarray(x, dtype=np.float32).astype(np.float64)).astype(
        np.float32
    )


def spp_swp_spc_get_effective_area(
    phi: np.ndarray,
    theta: np.ndarray,
    *,
    table: str | os.PathLike[str] | None = None,
) -> EffectiveArea:
    """
    Return the effective area of the SPC sensor in the cold plasma limit.

    The incidence angle is ``alpha = atan(sqrt(tan²(phi) + tan²(theta)))``,
    and the area is interpolated linearly in ``alpha`` (in degrees) in the
    column of the table for the largest Mach number.

    Parameters
    ----------
    phi, theta : numpy.ndarray
        The flow angles, in radians.
    table : path-like, optional
        The IDL save file with the table, which has ``ea[alpha, mach]``
        (mm²), ``alpha`` (degrees), and ``machnums``. Defaults to
        `EFFECTIVE_AREA_TABLE`.

    Returns
    -------
    EffectiveArea
        The effective area for each pair of angles, which is NaN where
        either angle is NaN.

    Notes
    -----
    Only the cold plasma limit with angles in radians is ported, since
    that is what the L1 to L2 step uses. The IDL function also supports
    angles in degrees, a Mach number for warm plasma, and an analytic
    approximation.

    The arithmetic is ``float32``, as in IDL, with correctly rounded
    ``tan``, ``sqrt``, and ``atan``. With these, the differential charge
    flux density of the L2 file made in production for 2026-08-03 is
    reproduced exactly.
    """
    save = readsav(
        str(pathlib.Path(table) if table is not None else EFFECTIVE_AREA_TABLE)
    )
    alpha = np.asarray(save["alpha"], dtype=np.float32)
    # ea[*, loc] in IDL, where loc is the index of the largest Mach number
    cold_ea = np.asarray(save["ea"][int(np.argmax(save["machnums"]))], dtype=np.float32)

    with np.errstate(invalid="ignore"):
        tan_phi = _float32_function(np.tan, phi)
        tan_theta = _float32_function(np.tan, theta)
        alpha_targ = _float32_function(
            np.arctan, _float32_function(np.sqrt, tan_phi**2 + tan_theta**2)
        )
        area_mm2 = interpol(cold_ea, alpha, alpha_targ / DTOR)
    return EffectiveArea(dat=area_mm2)
