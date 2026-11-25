"""Port of the table lookup in ``spp_swp_spc_get_angles.pro``."""

from __future__ import annotations

__all__ = ["Angles", "spp_swp_spc_get_angles"]

import dataclasses
from typing import TYPE_CHECKING

import numpy as np

from pyfaradaycup.l1_to_l2._spp_swp_spc_moments import DTOR
from pyfaradaycup.utils.idl import value_locate

if TYPE_CHECKING:
    import pathlib

    from pyfaradaycup.l2_to_l3._spp_swp_spc_get_angle_table import AngleTable

FOV = np.float32(80.0)
"""
The default field of view in degrees. Table cells farther than this from
normal incidence are not used, since the table is rough there.
"""

MACHNUM = np.float32(13.0)
"""The Mach number that IDL uses when none is given."""

MAX_CORRECTION = np.float32(0.25)
"""
The largest correction from the local gradient, in degrees, which is the
resolution of the table. Larger corrections are taken to have failed.
"""


@dataclasses.dataclass(frozen=True)
class Angles:
    """
    The flow angles from `spp_swp_spc_get_angles`.

    This is the structure returned by ``spp_swp_spc_get_angles`` in IDL,
    with ``phi.dat`` as ``phi`` and ``off_table_flag.dat`` as
    ``off_table_flag``.
    """

    phi: np.ndarray
    """
    The deflection angle from the east–west ratio ``(A + D) - (B + C)``,
    in radians (single precision).
    """

    theta: np.ndarray
    """
    The deflection angle from the north–south ratio ``(C + D) - (A + B)``,
    in radians (single precision).
    """

    machnum: np.ndarray
    """The Mach number for each lookup."""

    calfile: pathlib.Path
    """The flow angle lookup table."""

    max_fov_degrees: float
    """The field of view, in degrees."""

    off_table_flag: np.ndarray
    """
    1 where the ratios are outside the range of the slice of the table, and
    0 otherwise (``uint8``). The angles are then those of the nearest cell.
    """


def _at(array: np.ndarray, i: int, j: int) -> np.floating:
    """
    Return ``array[i, j]``, raising `IndexError` for subscripts that are
    out of range, as IDL does for scalar subscripts.

    NumPy would instead take a subscript of -1 as the last element.
    """
    if not (0 <= i < array.shape[0] and 0 <= j < array.shape[1]):
        msg = f"Subscripts [{i}, {j}] are out of range for an array of shape {array.shape}"
        raise IndexError(msg)
    return array[i, j]


def _lookup(
    table: AngleTable,
    fov_mask: np.ndarray,
    mindex: int,
    thisu: np.floating,
    thisv: np.floating,
) -> tuple[np.float32, np.float32, bool]:
    """
    Return the angles in degrees and the off table flag for one pair of
    ratios, from the slice ``mindex`` of the table.
    """
    utable = table.u[:, :, mindex]
    vtable = table.v[:, :, mindex]
    resid = fov_mask + (utable - thisu) ** 2 + (vtable - thisv) ** 2

    # IDL's max and min skip NaNs
    off_table = bool(
        (thisu > np.nanmax(utable))
        or (thisu < np.nanmin(utable))
        or (thisv > np.nanmax(vtable))
        or (thisv < np.nanmin(vtable))
    )

    # the first discrete minimum in IDL's order of elements
    flat = resid.ravel(order="F")
    if np.all(np.isnan(flat)):
        return np.float32(np.nan), np.float32(np.nan), off_table
    loc = int(np.nanargmin(flat))
    li, lj = (int(index) for index in np.unravel_index(loc, resid.shape, order="F"))
    phiguess = table.phi[li, lj]
    thetaguess = table.theta[li, lj]
    if abs(phiguess) > 90:  # ruff:ignore[PLR2004]
        phiguess = np.float32(np.nan)
    if abs(thetaguess) > 90:  # ruff:ignore[PLR2004]
        thetaguess = np.float32(np.nan)

    # first order correction from the local gradient
    dtdu = (_at(table.theta, li, lj + 1) - _at(table.theta, li, lj - 1)) / (
        _at(utable, li, lj + 1) - _at(utable, li, lj - 1)
    )
    dpdv = (_at(table.phi, li + 1, lj) - _at(table.phi, li - 1, lj)) / (
        _at(vtable, li + 1, lj) - _at(vtable, li - 1, lj)
    )
    dt = (thisu - utable[li, lj]) * dtdu
    dp = (thisv - vtable[li, lj]) * dpdv
    if not np.isfinite(dt) or abs(dt) > MAX_CORRECTION:
        dt = np.float32(0)
    if not np.isfinite(dp) or abs(dp) > MAX_CORRECTION:
        dp = np.float32(0)
    return np.float32(phiguess + dp), np.float32(thetaguess + dt), off_table


def spp_swp_spc_get_angles(  # ruff:ignore[PLR0913]
    *,
    us: np.ndarray,
    vs: np.ndarray,
    table: AngleTable,
    machnum: np.ndarray | float | None = None,
    fov: float | None = None,
    kew: float | None = None,
    kns: float | None = None,
) -> Angles:
    """
    Look up the flow angles for the ratios of the currents on the sensor
    plates.

    For each pair of ratios, the slice of the table for the Mach number
    at or below ``machnum`` is used. The angles are those of the cell
    whose ratios are closest to ``(u, v)``, among the cells within the
    field of view, with a first order correction from the local gradient
    of the table of at most 0.25°.

    Parameters
    ----------
    us : numpy.ndarray
        The north–south ratios ``((C + D) - (A + B)) / I``.
    vs : numpy.ndarray
        The east–west ratios ``((A + D) - (B + C)) / I``.
    table : AngleTable
        The flow angle lookup table, from
        `~pyfaradaycup.l2_to_l3._spp_swp_spc_get_angle_table.spp_swp_spc_get_angle_table`.
        This replaces IDL's ``table_pointer``.
    machnum : numpy.ndarray or float, optional
        The Mach number of each lookup, or one for all of them. Defaults
        to 13.
    fov : float, optional
        The field of view in degrees. Defaults to 80, and so does 0.
    kew, kns : float, optional
        Factors for the east–west and north–south ratios, which correct
        for crosstalk. Default to 1, and so does 0.

    Returns
    -------
    Angles
        The angles in radians, the Mach numbers, and the off table flags.

    Raises
    ------
    IndexError
        If the closest cell is on the edge of the table, so that its
        gradient cannot be computed, where IDL stops with a subscript
        error. This does not happen with the default table, whose ratios
        are NaN beyond about 50°.

    Notes
    -----
    As in IDL:

    - The Mach number picks the slice at or below it (``value_locate``),
      not the nearest one. Where it is below the first slice of the table,
      or is not finite, the angles are NaN.
    - Cells outside the field of view are excluded by adding NaN to their
      residuals, and the minimum skips NaNs. Of equal residuals, the first
      in IDL's order of elements is used.
    - The off table flag compares the ratios with the range of the slice,
      skipping NaNs, as IDL's ``max`` and ``min`` do.
    - The angles are single precision.

    If every residual is NaN, as for NaN ratios, the angles are NaN here.
    What IDL's ``min(..., /nan)`` returns for its subscript in that case is
    not documented.

    The cold linear approximation (``/cold_linear``), the currents ``as``,
    ``bs``, ``cs``, and ``ds`` instead of ratios, reading the table from a
    file, and the time-dependent crosstalk correction with ``epoch`` are
    not ported, since the L2 to L3 step does not use them.
    """
    kew = kew or 1.0
    kns = kns or 1.0
    fov32 = np.float32(fov) if fov else FOV
    us = kns * np.asarray(us)
    vs = kew * np.asarray(vs)

    machnum_array = np.asarray(MACHNUM if machnum is None else machnum)
    ms = machnum_array if machnum_array.size > 1 else machnum_array + 0 * vs
    mindices = value_locate(table.machnum, ms)

    phi = np.zeros(vs.size, dtype=np.float32)
    theta = np.zeros(vs.size, dtype=np.float32)
    off_table_flag = np.zeros(vs.size, dtype=np.uint8)

    with np.errstate(invalid="ignore", divide="ignore"):
        # sqrt(-1) is NaN outside the field of view, and 0 inside it
        fov_mask = np.sqrt(
            np.float32(-1) * (np.sqrt(table.phi**2 + table.theta**2) > fov32)
        ).astype(np.float32)
        for i in range(vs.size):
            if mindices[i] < 0 or not np.isfinite(ms[i]):
                phi[i] = theta[i] = np.nan
                continue
            phi[i], theta[i], off_table_flag[i] = _lookup(
                table, fov_mask, int(mindices[i]), us[i], vs[i]
            )

    return Angles(
        phi=phi * DTOR,
        theta=theta * DTOR,
        machnum=ms,
        calfile=table.file,
        max_fov_degrees=float(fov32),
        off_table_flag=off_table_flag,
    )
