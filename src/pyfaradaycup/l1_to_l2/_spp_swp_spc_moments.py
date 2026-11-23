"""
Port of the flow angle part of ``spp_swp_spc_moments.pro``.

The IDL function also makes rough estimates of the proton density,
speed, and temperature, but the L1 to L2 step only uses the flow angles,
so only they are ported.
"""

from __future__ import annotations

__all__ = ["FlowAngles", "spp_swp_spc_moments"]

import dataclasses
from typing import TYPE_CHECKING

import numpy as np

from pyfaradaycup.l1_to_l2._spp_swp_spc_voltwin2kmswin import spp_swp_spc_voltwin2kmswin
from pyfaradaycup.utils.idl import median_filter

if TYPE_CHECKING:
    from pyfaradaycup.l1_to_l2._spp_swp_spc_ivt_to_spectra import Spectra

DTOR = np.float32(np.pi / 180.0)
"""IDL's ``!DTOR``, which is single precision."""

_COLD_LINEAR = np.float32(0.035)
"""
The plate current ratio per degree of flow angle in the cold linear
approximation, as a ``float32`` literal in IDL.
"""

_CAP = (0, 1, 2, -1, -2, -3, 3)
"""The offsets of the cap around the peak, in the order IDL sums them."""

_CAP_SEG = (0, 1, 2, -1, -2, 3, -3)
"""The offsets in the order IDL sums the denominator of the cap."""


@dataclasses.dataclass(frozen=True)
class FlowAngles:
    """The flow angles from ``spp_swp_spc_moments``, which are NaN where not computed."""

    phi: np.ndarray
    """The east–west flow angle of each spectrum, in radians (``float32``)."""

    theta: np.ndarray
    """The north–south flow angle of each spectrum, in radians (``float32``)."""

    @property
    def ew_angle(self) -> np.ndarray:
        """The east–west flow angle, in degrees."""
        return self.phi / DTOR

    @property
    def ns_angle(self) -> np.ndarray:
        """The north–south flow angle, in degrees."""
        return self.theta / DTOR


def _max_dim2(array: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """
    Return ``max(array, loc, dim=2)`` from IDL for a two-dimensional array.

    IDL skips NaNs, and the index of the first maximum of each row is
    returned as a subscript into the whole array, in IDL's column-major
    order: ``i + j * nrows`` for row ``i`` and column ``j``. Rows that are
    all NaN give NaN and column 0.
    """
    nrows = array.shape[0]
    filled = np.where(np.isnan(array), -np.inf, array)
    column = np.argmax(filled, axis=1)
    value = filled[np.arange(nrows), column]
    all_nan = np.isnan(array).all(axis=1)
    value[all_nan] = np.nan
    column[all_nan] = 0
    return value, np.arange(nrows) + column * nrows


def _at(array: np.ndarray, subscripts: np.ndarray) -> np.ndarray:
    """
    Index a two-dimensional array with IDL's one-dimensional subscripts,
    which IDL clips to the bounds of the array.
    """
    flat = array.T.ravel()
    return flat[np.clip(subscripts, 0, flat.size - 1)]


def spp_swp_spc_moments(spectra: Spectra) -> FlowAngles:
    """
    Estimate the flow angles of the ion spectra.

    Only ion spectra that are not flux angle or calibration spectra are
    used; the others get NaN. In each spectrum, window 0, windows whose
    lower voltage is the same as in the window before, and windows with a
    fill current are left out. The reduced distribution ``ftot`` is the
    background-subtracted total current divided by ``v * dv``, kept only
    above twice the background and above half the peak current. The
    angles are averages of the plate ratios ``(A + D - B - C) / I`` and
    ``(C + D - A - B) / I``, weighted by ``ftot * dv`` over 7 elements
    around the peak of ``ftot``, divided by 0.035 per degree (the cold
    linear approximation), and then filtered with a running median of 3.

    Parameters
    ----------
    spectra : Spectra
        The spectra.

    Returns
    -------
    FlowAngles
        The flow angles of each spectrum.

    Notes
    -----
    These behaviors of IDL are reproduced. They were checked by
    reproducing the flow angles of the L2 file made in production for
    2026-08-03 exactly, since the IDL documentation does not cover them.

    - IDL's ``max`` without ``/NAN`` skips NaNs, and its ``<`` operator
      ignores a NaN operand.
    - The index of the peak from ``max(..., dim=2)`` is a subscript into
      the whole array, in column-major order, so the 7 elements around
      it are the peak windows of 7 consecutive spectra, not 7 windows of
      the same spectrum. Subscripts beyond the array are clipped.
    - The numerator and denominator of the average are summed in
      different orders.
    - The running median ignores NaNs and leaves the first and last
      spectra unchanged; the smoothing of width 0 that follows does not
      change anything.
    - ``!DTOR`` and the float literals are ``float32``.
    """
    nspec = spectra.emode.size
    phi = np.full(nspec, np.nan, dtype=np.float32)
    theta = np.full(nspec, np.nan, dtype=np.float32)
    ok = np.flatnonzero(
        (spectra.emode == 0) & (spectra.famode == 0) & (spectra.cal == 0)
    )
    if ok.size <= 1:
        return FlowAngles(phi=phi, theta=theta)

    mv_lo = spectra.mv_lo[ok].copy()
    mv_hi = spectra.mv_hi[ok].copy()
    a_s, b_s, c_s, d_s = (spectra.current[ok, :, k].copy() for k in range(4))

    # leave out window 0, repeated voltages, and fill currents
    rt = mv_lo == np.roll(mv_lo, 1, axis=1)
    rt[:, 0] = True
    tk = rt
    for current in (a_s, b_s, c_s, d_s):
        tk = tk | (current == spectra.fill)
    for values in (mv_lo, mv_hi, a_s, b_s, c_s, d_s):
        values[tk] = np.nan

    window = spp_swp_spc_voltwin2kmswin(volt_hi=mv_hi, volt_lo=mv_lo)
    vkms = window.vkms_mid
    dvkms = window.dvkms

    with np.errstate(invalid="ignore", divide="ignore"):
        itot = a_s + b_s + c_s + d_s
        ipeak, _ = _max_dim2(itot)
        inoise = np.fmin(itot[:, 3], itot[:, -1])
        isig = ipeak[:, np.newaxis]
        ibck = inoise[:, np.newaxis]

        ftot = (
            (np.sqrt(np.fmax(itot**2 - ibck**2, 0.0)) / (vkms * dvkms))
            * (itot > 2.0 * ibck)
            * (itot > isig / 2.0)
        )
        lr = (a_s + d_s - b_s - c_s) / itot
        ud = (d_s + c_s - a_s - b_s) / itot

        _, fpkloc = _max_dim2(ftot)
        dv = np.roll(vkms, -1, axis=1) - vkms
        fseg = ftot * dv
        lrw = lr * ftot * dv
        udw = ud * ftot * dv

        def cap(weights: np.ndarray, offsets: tuple[int, ...]) -> np.ndarray:
            total = _at(weights, fpkloc + offsets[0])
            for offset in offsets[1:]:
                total = total + _at(weights, fpkloc + offset)
            return total

        seg = cap(fseg, _CAP_SEG)
        spc_fcap_lr = cap(lrw, _CAP) / seg
        spc_fcap_ud = cap(udw, _CAP) / seg

    # IDL divides by the float literal 0.035, promoted to double
    anglephi = spc_fcap_lr / np.float64(_COLD_LINEAR)
    angletheta = spc_fcap_ud / np.float64(_COLD_LINEAR)
    phi[ok] = median_filter(anglephi, 3)
    theta[ok] = median_filter(angletheta, 3)
    return FlowAngles(phi=phi * DTOR, theta=theta * DTOR)
