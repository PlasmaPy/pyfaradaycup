"""Port of ``spp_swp_spc_splineinvert.pro``."""

from __future__ import annotations

__all__ = ["SplineInvert", "SplineModel", "spp_swp_spc_splineinvert"]

import dataclasses

import numpy as np

from pyfaradaycup.utils.idl import trisol, uniq

_BELOW = 9999999.0
"""
The offset that IDL adds to ``V - x`` for the knots ``x`` above ``V``, so
that the minimum picks the nearest knot at or below ``V``.
"""

_MIN_KNOTS = 3
"""The fewest distinct voltages for which IDL can make the spline."""


@dataclasses.dataclass(frozen=True)
class SplineModel:
    """
    The flux function on a 1 V grid, which IDL returns in ``model``.

    Both arrays are single precision, as in IDL.
    """

    v: np.ndarray
    """The voltages of the grid, in V (``model.V``)."""

    phi_v: np.ndarray
    """The flux function ``P(V)`` at ``v``, in pA/V (``model.phi_V``)."""


@dataclasses.dataclass(frozen=True)
class SplineInvert:
    """The results of `spp_swp_spc_splineinvert`."""

    result: np.ndarray
    """
    The flux function at the window voltages, in pA/V, which is what IDL
    returns. It has the type and shape of ``meas``.
    """

    coeffs: np.ndarray
    """
    The single precision polynomial coefficients ``[a, b, c, d]`` of each
    spline segment, with shape ``(4, n)`` (``coeffs`` in IDL, with the
    same subscripts).
    """

    model: SplineModel | None
    """The flux function on a 1 V grid, if ``calcmodel`` is true."""


def _model(
    x: np.ndarray, a: np.ndarray, b: np.ndarray, c: np.ndarray, d: np.ndarray
) -> SplineModel:
    """
    Evaluate the spline on a 1 V grid from ``fix(min(x))``, like the
    ``/calcmodel`` part of IDL.

    There are ``floor(max(x) - min(x))`` points. Each point uses the
    segment of the nearest knot at or below it, or, for a point below
    every knot, the segment of the last knot, as IDL's offset gives.
    """
    # fix() truncates toward zero, and findgen() truncates its argument
    start = np.int16(np.trunc(x.min()))
    vv = (start + np.arange(int(x.max() - x.min()), dtype=np.float32)).astype(
        np.float32
    )
    offset = vv[:, np.newaxis] - x + np.float32(_BELOW) * (vv[:, np.newaxis] < x)
    j = np.argmin(offset, axis=1)
    lv = vv - x[j]
    ff = a[j] * (lv * lv * lv) + b[j] * (lv * lv) + c[j] * lv + d[j]
    return SplineModel(v=vv, phi_v=ff.astype(np.float32))


def spp_swp_spc_splineinvert(
    volt: np.ndarray,
    dvolt: np.ndarray,
    meas: np.ndarray | np.floating | float,
    *,
    nofilter: bool = False,
    calcmodel: bool = False,
) -> SplineInvert:
    """
    Find the flux function ``P(V)`` from currents measured with sinusoidal
    modulation, as a spline.

    The current in a voltage window of width ``dV`` centered at ``V`` is
    ``I = (dV / 2) * (P(V) + b * dV**2 / 16)`` to second order,
    where ``b = P''(V) / 2`` is the quadratic coefficient of the spline at
    ``V``, so a natural cubic spline of ``P`` gives the tridiagonal system
    that is solved here. This is from the SPC memo "FC response with sinusoidal
    modulation" (M. L. Stevens, 2018-12-21, revised 2019-01-15, sections 2
    and 5), which is not in the snapshot of the IDL code.

    Parameters
    ----------
    volt : numpy.ndarray
        The voltages at the centers of the windows, in V, in increasing
        order.
    dvolt : numpy.ndarray
        The widths (peak to peak) of the windows, in V.
    meas : numpy.ndarray or float
        The currents, in pA. A scalar is used for every window, since IDL
        clips the subscripts of a scalar.
    nofilter : bool, default: False
        Whether not to apply the low pass filter. By default, where the
        curvature term ``dV**2 * b / 16`` is at least as large as
        ``2 * I / dV``, ``P`` is ``2 * I / dV`` and the other coefficients
        of the segment are 0.
    calcmodel : bool, default: False
        Whether to evaluate the spline on a 1 V grid.

    Returns
    -------
    SplineInvert
        The flux function at ``volt``, the spline coefficients, and, with
        ``calcmodel``, the flux function on a 1 V grid.

    Raises
    ------
    ValueError
        If there are fewer than 3 distinct voltages, where IDL stops with
        a subscript error.

    Notes
    -----
    The curvature term follows from the modulation. With the voltage
    ``V + (dV / 2) sin(theta)``, the current is the first Fourier
    amplitude of the collected current ``Q(V) = integral of P from V to
    infinity``, and expanding ``Q`` to third order gives ``I = (dV / 2) *
    (P + P'' * dV**2 / 32)``, since the average of ``sin(theta)**4`` is
    3/8. This is the ``b * dV**2 / 16`` of the IDL code, with ``b = P'' /
    2``. The header of ``spp_swp_spc_splineinvert.pro`` writes the term as
    ``(1/16) * (P") * dvolt^2``, which is right if ``P"`` means ``b``.

    As in IDL:

    - Of repeated adjacent voltages, the last is used (``uniq``).
    - The spline is computed in double precision, and the coefficients
      and the model are single precision.
    - The model starts at ``fix(min(volt))``, which is below the first
      window if its voltage is not an integer. Each point of the model
      uses the segment that starts at the nearest window at or below it,
      or, below the first window, the linear last segment.
    - Division by zero, such as of the coefficients of the last segment,
      gives infinite or NaN values without an error.

    IDL computes integer powers such as ``l^3``, which this does by
    multiplication; whether IDL does the same is not documented, so the
    model can differ from IDL's in the last bit.
    """
    volt = np.asarray(volt)
    dvolt = np.asarray(dvolt)
    meas_array = np.asarray(meas)
    sig = uniq(volt)
    x = volt[sig].astype(np.float64)
    dx = dvolt[sig].astype(np.float64)
    meas_values = (
        np.broadcast_to(meas_array, volt.shape) if meas_array.ndim == 0 else meas_array
    )
    s = meas_values[sig].astype(np.float64)
    nsig = s.size
    if nsig < _MIN_KNOTS:
        msg = f"The spline needs at least {_MIN_KNOTS} distinct voltages, not {nsig}"
        raise ValueError(msg)
    last = nsig - 1

    with np.errstate(divide="ignore", invalid="ignore"):
        h = np.roll(x, -1) - x
        h[last] = 0.0
        i = np.arange(last - 1)
        a2 = h[i + 1] / 3.0 + (1.0 * dx[i + 2] ** 2) / (16.0 * h[i + 1])
        a1 = (
            2.0 * h[i] / 3.0
            + 2.0 * h[i + 1] / 3.0
            - (1.0 / 16.0) * (dx[i + 1] ** 2) * (1.0 / h[i + 1] + 1.0 / h[i])
        )
        a0 = 1.0 * h[i] / 3.0 + (1.0 / 16.0) * (dx[i] ** 2) / h[i]
        y = (2.0 / h[i + 1]) * (s[i + 2] / dx[i + 2] - s[i + 1] / dx[i + 1]) - (
            2.0 / h[i]
        ) * (s[i + 1] / dx[i + 1] - s[i] / dx[i])
        # b[0] and b[last] are 0 for a natural spline, so row i is the
        # equation for b[i + 1]
        a0[0] = 0.0
        a2[-1] = 0.0
        b = np.concatenate(([0.0], trisol(a0, a1, a2, y, double=True), [0.0]))

        # the coefficients of P = a * l**3 + b * l**2 + c * l + d, where
        # l = V - x[i] in segment i
        a = (np.roll(b, -1) - b) / (3.0 * h)
        a[last] = 0.0
        d = 2.0 * s / dx - (1.0 / 16.0) * (dx**2) * b
        c = (np.roll(d, -1) - (a * (h * h * h) + b * (h * h) + d)) / h
        c[last] = (
            3.0 * a[last - 1] * h[last - 1] ** 2
            + 2.0 * b[last - 1] * h[last - 1]
            + c[last - 1]
        )

        if not nofilter:
            lowpass = np.abs((1.0 / 16.0) * (dx**2) * b) < np.abs(2.0 * s / dx)
            d = d * lowpass + (2.0 * s / dx) * ~lowpass
            c = c * lowpass
            b = b * lowpass
            a = a * lowpass

        model = _model(x, a, b, c, d) if calcmodel else None

    coeffs = np.stack([a, b, c, d]).astype(np.float32)
    result_dtype = (
        meas_array.dtype if meas_array.dtype.kind == "f" else np.dtype(np.float32)
    )
    if meas_array.ndim == 0:
        # IDL assigns every value to the only element of a scalar, so the
        # last one is kept
        result = np.asarray(d[-1], dtype=result_dtype)
    else:
        result = np.zeros(meas_array.shape, dtype=result_dtype)
        result[sig] = d
    return SplineInvert(result=result, coeffs=coeffs, model=model)
