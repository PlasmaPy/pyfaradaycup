"""Port of ``spp_swp_spc_zmoments.pro``, and of ``SIGN`` from CDAWlib."""

from __future__ import annotations

__all__ = ["ZMoments", "sign", "spp_swp_spc_zmoments"]

import dataclasses

import numpy as np

_ONE_THIRD = float(np.float32(1.0) / np.float32(3.0))
"""``1./3.`` in IDL, which is single precision: 0.3333333432674408."""


def _keyword_set(value: np.ndarray | float | None) -> bool:
    """
    Return whether ``value`` is set, like IDL's ``keyword_set``.

    That is true for an array of more than one element, and otherwise
    whether the value is nonzero.
    """
    if value is None:
        return False
    value = np.asarray(value)
    return value.size > 1 or bool(np.all(value != 0) and value.size == 1)


def sign(x: np.ndarray | float) -> np.ndarray:
    """
    Return -1, 0, or 1 for negative, zero, or positive ``x``.

    This is ``SIGN`` from CDAWlib (R. Sterner, JHU/APL), which returns
    ``fix(x gt 0.) - fix(x lt 0.)``, so NaN gives 0.

    Examples
    --------
    >>> import numpy as np
    >>> sign(np.array([-2.0, 0.0, 3.0, np.nan])).tolist()
    [-1, 0, 1, 0]
    """
    x = np.asarray(x)
    return (x > 0).astype(np.int16) - (x < 0).astype(np.int16)


@dataclasses.dataclass(frozen=True)
class ZMoments:
    """
    The moments from `spp_swp_spc_zmoments`.

    IDL returns ``moments`` and the keyword outputs ``SIGMA``,
    ``SKEWNESS``, and ``KURTOSIS``.
    """

    moments: np.ndarray
    """
    The zeroth moment, the mean of ``z``, and the second, third, and
    fourth central moments of ``z``, each as a root so that it has the
    units of ``z`` (for example, the RMS thermal speed).
    """

    sigma: np.ndarray
    """The propagated uncertainties of ``moments``."""

    skewness: float
    """The third central moment divided by the cube of the second root moment."""

    kurtosis: float
    """The fourth central moment divided by the square of the second central moment."""


def spp_swp_spc_zmoments(
    x: np.ndarray,
    px: np.ndarray,
    z: np.ndarray,
    *,
    measure_errors: np.ndarray | None = None,
) -> ZMoments:
    """
    Return the moments of ``z`` over a distribution ``px(x)``, with
    propagated uncertainties.

    With the centered spacing ``dx`` of ``x`` (half of each spacing at the
    ends), the moments are ``n = sum(px * dx)``, ``u = sum(px * dx * z) /
    n``, ``w = sqrt(sum(px * dx * (z - u)**2) / n)``, and the cube and
    fourth roots of the third and fourth central moments. When ``z`` is
    the speed, these are the density, bulk speed, and RMS thermal speed.

    Parameters
    ----------
    x : numpy.ndarray
        The points where ``px`` is evaluated, in increasing order, such as
        voltages.
    px : numpy.ndarray
        The distribution at ``x``.
    z : numpy.ndarray
        The quantity at ``x`` to take moments of, such as the speed.
    measure_errors : numpy.ndarray, optional
        The uncertainties of ``px``. Defaults to 0, and so does a scalar 0
        or an array of one 0, since IDL uses ``keyword_set``.

    Returns
    -------
    ZMoments
        The moments, their uncertainties, the skewness, and the kurtosis.

    Notes
    -----
    As in IDL:

    - The sums leave out NaNs (``total(..., /nan)``), except those for the
      fourth moment's uncertainty, which do not.
    - ``dx`` has the type of ``x``, so it is single precision for the 1 V
      grid of `~pyfaradaycup.l2_to_l3._spp_swp_spc_splineinvert.SplineModel`.
    - The exponent ``1./3.`` of the cube root is single precision.
    - The uncertainty of each root moment is propagated from that of the
      central moment as ``sigma(m) / (k * root**(k - 1))``.

    Division by zero gives infinite or NaN values without an error, as in
    IDL. IDL's ``TOTAL`` can add in a different order (with threads for
    large arrays), so sums can differ from IDL's in the last bits.
    """
    x = np.asarray(x)
    px = np.asarray(px)
    z = np.asarray(z)
    dpx = 0 * px if not _keyword_set(measure_errors) else np.asarray(measure_errors)

    with np.errstate(divide="ignore", invalid="ignore"):
        dxplus = np.maximum(np.roll(x, -1) - x, 0)
        dxminus = np.maximum(x - np.roll(x, 1), 0)
        dx = (dxplus + dxminus) / 2.0

        mom0 = np.nansum(px * dx) * 1.0
        dmom0 = np.sqrt(np.nansum((dx * dpx) ** 2))

        mom1 = np.nansum(px * dx * z) / mom0
        dmom1 = np.sqrt(
            np.nansum((dpx * dx * z / mom0) ** 2) + (mom1 * dmom0 / mom0) ** 2
        )

        # as in IDL, z - mom1 has the type of mom1 if that is double
        # precision, which NumPy < 2 does not do for a single precision z
        dz = z.astype(np.result_type(z.dtype, np.asarray(mom1).dtype)) - mom1
        mom2_sq = np.nansum(px * dx * dz**2) / mom0
        dmom2_sq = np.sqrt(
            np.nansum(((dx * dpx * dz**2) / mom0) ** 2)
            + np.nansum((dx * px * 2 * dz * dmom1 / mom0) ** 2)
            + (mom2_sq * dmom0 / mom0) ** 2
        )
        mom2 = np.sqrt(mom2_sq)
        dmom2 = dmom2_sq / (2 * mom2)

        mom3_cu = np.nansum(px * dx * dz**3) / mom0
        dmom3_cu = np.sqrt(
            np.nansum(((dpx * dx * dz**3) / mom0) ** 2)
            + np.nansum(((px * dx * 3.0 * dz**2) * dmom1 / mom0) ** 2)
            + (mom3_cu * dmom0 / mom0) ** 2
        )
        mom3 = sign(mom3_cu) * np.abs(mom3_cu) ** _ONE_THIRD
        dmom3 = _ONE_THIRD * dmom3_cu / (mom3**2)
        skewness = mom3_cu / (mom2**3)

        mom4_4 = np.nansum(px * dx * dz**4) / mom0
        dmom4_4 = np.sqrt(
            np.sum(((dpx * dx * dz**4) / mom0) ** 2)
            + np.sum(((px * dx * 4.0 * dz**3) * dmom1 / mom0) ** 2)
            + (mom4_4 * dmom0 / mom0) ** 2
        )
        mom4 = mom4_4**0.25
        dmom4 = 0.25 * dmom4_4 / (mom4**3)
        kurtosis = mom4_4 / (mom2_sq**2)

    return ZMoments(
        moments=np.array([mom0, mom1, mom2, mom3, mom4], dtype=np.float64),
        sigma=np.array([dmom0, dmom1, dmom2, dmom3, dmom4], dtype=np.float64),
        skewness=float(skewness),
        kurtosis=float(kurtosis),
    )
