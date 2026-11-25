"""Port of ``spp_swp_spc_get_effective_area.pro``."""

from __future__ import annotations

__all__ = [
    "A0",
    "EFFECTIVE_AREA_TABLE",
    "EffectiveArea",
    "spp_swp_spc_get_effective_area",
]

import dataclasses
import pathlib
from typing import TYPE_CHECKING

import numpy as np
from scipy.io import readsav

from pyfaradaycup.l1_to_l2._calibration import CALIBRATION_DIR
from pyfaradaycup.l1_to_l2._spp_swp_spc_moments import DTOR
from pyfaradaycup.utils.idl import interpol, interpolate

if TYPE_CHECKING:
    import os

EFFECTIVE_AREA_TABLE = (
    CALIBRATION_DIR / "spp_swp_calfiles_spc_effectiveAreaTable_v0.idl"
)
"""The default table of effective areas, an IDL save file."""

A0 = np.float32(131.783)
"""
The effective area at normal incidence of the analytic approximation, in
mm², a single precision literal in IDL.

Its comment in IDL says that 137.260 mm² is the area at normal incidence
in the cold plasma limit, revised on 2020-05-13, but 131.783 mm² is used.
"""

_DEGREE_UNITS = frozenset({"degrees", "degree", "deg", "o", "^o", "!uo!n"})
"""The units that IDL takes to be degrees; any others are taken to be radians."""

_APPROX_M1 = np.float32(4.55)
_APPROX_M2 = np.float32(1.17)
_APPROX_AC = np.float32(24.35)
"""
The angle ``ac`` of the analytic approximation. IDL first sets it to
``24.35 * rad`` and then to ``24.35``, so it is compared with angles in
radians as if it were in radians.
"""


@dataclasses.dataclass(frozen=True)
class EffectiveArea:
    """The structure returned by ``spp_swp_spc_get_effective_area``."""

    dat: np.ndarray
    """The effective area, in mm²."""

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


def _idl_function(function: np.ufunc, x: np.ndarray) -> np.ndarray:
    """
    Evaluate a function in the precision of ``x``, as IDL does: double
    precision for double precision ``x``, and otherwise correctly rounded
    single precision.
    """
    x = np.asarray(x)
    if x.dtype == np.float64:
        return function(x)
    return _float32_function(function, x)


def _angle(value: np.ndarray | np.floating | float) -> np.ndarray:
    """
    Return an angle as an array, with a Python number taken to be single
    precision, like a literal such as ``0.`` in IDL.
    """
    if isinstance(value, (np.ndarray, np.generic)):
        return np.asarray(value)
    return np.asarray(value, dtype=np.float32)


def _incidence(
    phi: np.ndarray, theta: np.ndarray, rad: np.floating | float
) -> np.ndarray:
    """Return ``atan(sqrt(tan(phi * rad)^2 + tan(theta * rad)^2))``, in radians."""
    tan_phi = _idl_function(np.tan, phi * rad)
    tan_theta = _idl_function(np.tan, theta * rad)
    # squares are products, since with NumPy < 2, x**2 is double precision
    # for a single precision scalar x
    return _idl_function(
        np.arctan, _idl_function(np.sqrt, tan_phi * tan_phi + tan_theta * tan_theta)
    )


def _is_set(machnum: np.ndarray | float | None) -> bool:
    """Return whether ``machnum`` is set, like IDL's ``keyword_set``."""
    if machnum is None:
        return False
    value = np.asarray(machnum)
    return value.size > 1 or (value.size == 1 and bool(np.all(value != 0)))


def spp_swp_spc_get_effective_area(  # ruff:ignore[PLR0913]
    phi: np.ndarray | np.floating | float,
    theta: np.ndarray | np.floating | float,
    *,
    machnum: np.ndarray | float | None = None,
    approx: bool = False,
    table: str | os.PathLike[str] | None = None,
    units: str = "radian",
) -> EffectiveArea:
    """
    Return the effective area of the SPC sensor.

    The incidence angle is ``alpha = atan(sqrt(tan²(phi) + tan²(theta)))``.
    There are three ways to find the area, as in IDL:

    - With ``approx``, the analytic approximation ``min(A0 * (1 - 4.55 *
      (alpha - ac)), A0 * (1 - 1.17 * alpha))`` for ``alpha`` below 45°,
      and 0 otherwise, with ``A0`` = 131.783 mm².
    - With a Mach number, the area is interpolated bilinearly in the table
      at ``alpha`` (in degrees, at most 90°) and the Mach number (the
      warm plasma case).
    - Otherwise, the area is interpolated linearly in ``alpha`` in the
      column of the table for the largest Mach number (the cold plasma
      limit).

    Parameters
    ----------
    phi, theta : numpy.ndarray or float
        The flow angles, in the units given by ``units``. Python numbers
        are single precision, like literals in IDL.
    machnum : numpy.ndarray or float, optional
        The Mach number for the warm plasma case. A scalar 0 is taken as
        no Mach number, since IDL uses ``keyword_set``.
    approx : bool, default: False
        Whether to use the analytic approximation.
    table : path-like, optional
        The IDL save file with the table, which has ``ea[alpha, mach]``
        (mm²), ``alpha`` (degrees), and ``machnums``. Defaults to
        `EFFECTIVE_AREA_TABLE`.
    units : str, default: "radian"
        The units of the angles. As in IDL, ``"degrees"``, ``"degree"``,
        ``"deg"``, ``"o"``, ``"^o"``, and ``"!uo!n"`` are degrees, and any
        other units are radians. IDL takes the units from the ``units`` of
        a structure, and takes a plain array to be in degrees.

    Returns
    -------
    EffectiveArea
        The effective area for each pair of angles, in mm². Except in the
        warm plasma case, it is NaN where an angle is NaN.

    Notes
    -----
    The arithmetic has the precision of the angles, as in IDL. For single
    precision angles, ``tan``, ``sqrt``, and ``atan`` are correctly
    rounded. With these, the differential charge flux density of the L2
    file made in production for 2026-08-03 is reproduced exactly.

    These behaviors of IDL are reproduced:

    - In the analytic approximation, ``ac`` is first set to ``24.35 *
      rad`` and then to ``24.35``, so ``alpha - ac`` is about -24 for
      angles in radians, and the first term is never the smaller one.
      The 45° limit is ``45 * rad``, which is 45 for angles in radians, so
      it never applies to them.
    - In the warm plasma case, the fractional subscript of the Mach number
      is limited to the largest Mach number, rather than to the last
      subscript, so it is not limited; `~pyfaradaycup.utils.idl.interpolate`
      then moves it to the edge of the table.
    - IDL's ``<`` operator ignores a NaN operand, so in the warm plasma
      case a NaN angle is taken as 90°, and a NaN Mach number as the
      largest one; the area is then that at the edge of the table, rather
      than NaN.

    The structures with ``dat`` and ``units`` that IDL accepts are
    replaced by the ``units`` argument. The ``nometa`` keyword, a missing
    second angle (taken as 0 in IDL), and the case with no angles are not
    ported.
    """
    rad = DTOR if units in _DEGREE_UNITS else 1.0
    phi = _angle(phi)
    theta = _angle(theta)

    with np.errstate(invalid="ignore"):
        if approx:
            alpha = _incidence(phi, theta, rad)
            one = np.float32(1)
            # IDL's < operator ignores a NaN operand, like numpy.fmin
            area_mm2 = np.fmin(
                A0 * (one - _APPROX_M1 * (alpha - _APPROX_AC)),
                A0 * (one - _APPROX_M2 * alpha),
            ) * (alpha < np.float32(45) * rad)
            return EffectiveArea(
                dat=area_mm2,
                desc="Effective Area of SPC sensor, analytic approximation applied.",
            )

        save = readsav(
            str(pathlib.Path(table) if table is not None else EFFECTIVE_AREA_TABLE)
        )
        alpha_table = np.asarray(save["alpha"], dtype=np.float32)
        machnums = np.asarray(save["machnums"], dtype=np.float32)
        # readsav reverses IDL's order of dimensions, so this is ea[alpha, mach]
        ea = np.asarray(save["ea"], dtype=np.float32).T

        alpha_targ = _incidence(phi, theta, rad)
        if not _is_set(machnum):
            cold_ea = ea[:, int(np.argmax(machnums))]
            area_mm2 = interpol(cold_ea, alpha_table, alpha_targ / DTOR)
            return EffectiveArea(dat=area_mm2)

        mach = np.asarray(machnum)
        mach_targ = mach + 0 * phi if mach.size == 1 else mach
        # IDL's < operator ignores a NaN operand, like numpy.fmin, so a
        # NaN angle or Mach number becomes the limit
        minterp = np.fmin(
            interpol(np.arange(machnums.size, dtype=np.float32), machnums, mach_targ),
            machnums.max(),
        )
        ainterp = interpol(
            np.arange(alpha_table.size, dtype=np.float32),
            alpha_table,
            np.fmin(alpha_targ / DTOR, np.float32(90)),
        )
        area_mm2 = interpolate(ea, ainterp, minterp)
    return EffectiveArea(
        dat=area_mm2, desc="Effective Area of SPC sensor, warm plasma numerical method"
    )
