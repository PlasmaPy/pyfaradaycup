"""Test finding the flux function with ``spp_swp_spc_splineinvert``."""

from __future__ import annotations

import numpy as np
import pytest
from scipy.special import erfc

from pyfaradaycup.l2_to_l3._spp_swp_spc_splineinvert import spp_swp_spc_splineinvert


def _windows(
    n: int = 40, start: float = 400.0, step: float = 20.0
) -> tuple[np.ndarray, ...]:
    """Return the centers and widths of ``n`` evenly spaced voltage windows."""
    volt = start + step * np.arange(n)
    dvolt = np.full(n, 1.5 * step)
    return volt, dvolt


def _currents(p: np.ndarray, p2: np.ndarray, dvolt: np.ndarray) -> np.ndarray:
    """
    Return the currents for a flux function ``p`` with second derivative
    ``p2``, from ``I = (dV / 2) * (P + P'' * dV**2 / 32)``, the response to
    second order with sinusoidal modulation that the spline inverts.

    This is the first Fourier amplitude of the collected current to
    third order in ``dV`` (see `_fourier_currents`), and the IDL code
    subtracts it as ``dV**2 * b / 16``, with the quadratic coefficient
    ``b = P'' / 2`` of the spline.
    """
    return 0.5 * dvolt * (p + p2 * dvolt**2 / 32)


def test_splineinvert_linear() -> None:
    """A linear flux function, which has no curvature, is found exactly."""
    volt, dvolt = _windows()
    p = 3.0 + 0.01 * volt
    result = spp_swp_spc_splineinvert(
        volt, dvolt, _currents(p, 0 * p, dvolt), calcmodel=True
    )
    np.testing.assert_allclose(result.result, p, rtol=1e-13)
    assert result.model is not None
    # the model is single precision, between the first and last windows
    inside = result.model.v >= volt[0]
    np.testing.assert_allclose(
        result.model.phi_v[inside], 3.0 + 0.01 * result.model.v[inside], rtol=1e-6
    )


MAX_SPLINE_ERROR = 1e-4
"""The largest error of the spline for the Gaussian flux function, which has a peak of 1."""


def test_splineinvert_gaussian() -> None:
    """
    For a smooth flux function, the spline recovers ``P`` at the windows
    much better than ``2 * I / dV``, which leaves out the curvature.
    """
    volt, dvolt = _windows(n=60, start=300.0, step=10.0)
    v0, width = 600.0, 80.0
    p = np.exp(-(((volt - v0) / width) ** 2))
    p2 = p * (4 * (volt - v0) ** 2 / width**4 - 2 / width**2)
    current = _currents(p, p2, dvolt)
    result = spp_swp_spc_splineinvert(volt, dvolt, current, nofilter=True)
    naive = 2 * current / dvolt
    interior = slice(5, -5)
    spline_error = np.max(np.abs(result.result - p)[interior])
    naive_error = np.max(np.abs(naive - p)[interior])
    assert spline_error < MAX_SPLINE_ERROR
    assert spline_error < naive_error / 20


def test_splineinvert_lowpass() -> None:
    """Where the curvature term dominates, ``P`` is ``2 * I / dV`` and the segment is constant."""
    volt, dvolt = _windows(n=10)
    current = np.array([1.0, -1.0] * 5) * 100 + 1.0
    result = spp_swp_spc_splineinvert(volt, dvolt, current)
    unfiltered = spp_swp_spc_splineinvert(volt, dvolt, current, nofilter=True)
    # b is 0 at the ends of a natural spline, so use where the filter changed it
    filtered = (result.coeffs[1] == 0) & (unfiltered.coeffs[1] != 0)
    assert np.any(filtered)
    np.testing.assert_allclose(
        result.result[filtered], (2 * current / dvolt)[filtered], rtol=1e-6
    )
    assert np.all(result.coeffs[0][filtered] == 0)
    assert np.all(result.coeffs[2][filtered] == 0)


def test_splineinvert_repeated_voltage() -> None:
    """Of repeated voltages, the last is used, like IDL's ``uniq``."""
    volt, dvolt = _windows(n=10)
    current = 1.0 + 0.1 * np.arange(10)
    volt_repeated = np.insert(volt, 3, volt[3])
    dvolt_repeated = np.insert(dvolt, 3, dvolt[3])
    current_repeated = np.insert(current, 3, 99.0)
    expected = spp_swp_spc_splineinvert(volt, dvolt, current)
    result = spp_swp_spc_splineinvert(volt_repeated, dvolt_repeated, current_repeated)
    # the first of the repeated windows is not used, and stays 0
    assert result.result[3] == 0
    np.testing.assert_array_equal(np.delete(result.result, 3), expected.result)


def test_splineinvert_scalar() -> None:
    """A scalar current is used for every window, as IDL does by clipping subscripts."""
    volt, dvolt = _windows(n=12)
    scalar = spp_swp_spc_splineinvert(volt, dvolt, np.float32(2.5), calcmodel=True)
    array = spp_swp_spc_splineinvert(
        volt, dvolt, np.full(12, 2.5, np.float32), calcmodel=True
    )
    assert scalar.model is not None
    assert array.model is not None
    np.testing.assert_array_equal(scalar.model.phi_v, array.model.phi_v)
    assert scalar.result.shape == ()
    assert scalar.result == array.result[-1]


def test_splineinvert_types() -> None:
    """The result has the type of the currents, and the coefficients and model are single precision."""
    volt, dvolt = (x.astype(np.float32) for x in _windows(n=12))
    current = np.linspace(1, 2, 12, dtype=np.float32)
    result = spp_swp_spc_splineinvert(volt, dvolt, current, calcmodel=True)
    assert result.result.dtype == np.float32
    assert result.coeffs.dtype == np.float32
    assert result.coeffs.shape == (4, 12)
    assert result.model is not None
    assert result.model.v.dtype == np.float32
    assert result.model.phi_v.dtype == np.float32


def test_splineinvert_model_grid() -> None:
    """
    The model is on a 1 V grid of ``floor(max - min)`` points from
    ``fix(min)``, and a point below the first window uses the last
    segment, which is linear, as in IDL.
    """
    volt = np.array([100.5, 120.25, 140.0, 165.75, 190.0])
    dvolt = np.full(5, 15.0)
    current = np.array([1.0, 2.0, 4.0, 3.0, 1.5])
    result = spp_swp_spc_splineinvert(volt, dvolt, current, calcmodel=True)
    assert result.model is not None
    np.testing.assert_array_equal(result.model.v, 100.0 + np.arange(89))
    a, b, c, d = result.coeffs[:, -1].astype(np.float64)
    assert a == 0
    assert b == 0
    expected = np.float32(d + c * (100.0 - volt[-1]))
    np.testing.assert_allclose(result.model.phi_v[0], expected, rtol=1e-6)


def test_splineinvert_too_few_voltages() -> None:
    """Fewer than 3 distinct voltages raise `ValueError`, where IDL has a subscript error."""
    with pytest.raises(ValueError, match="at least 3"):
        spp_swp_spc_splineinvert(np.array([1.0, 2.0, 2.0]), np.ones(3), np.ones(3))


def _fourier_currents(
    volt: np.ndarray, dvolt: np.ndarray, v0: float, width: float
) -> np.ndarray:
    """
    Return the currents for the flux function ``P(V) = exp(-((V - v0) /
    width)**2)`` with sinusoidal modulation, without expanding in ``dV``.

    The collected current at ``V`` is ``Q(V) = sqrt(pi) * width / 2 *
    erfc((V - v0) / width)``, the integral of ``P`` from ``V`` to infinity.
    With the voltage ``V + (dV / 2) sin(theta)``, the measured current is
    the first Fourier amplitude ``-(1 / pi) * integral of Q sin(theta)
    dtheta`` over a period, which is computed here with the trapezoid
    rule, which converges exponentially for periodic functions.
    """
    theta = np.linspace(0, 2 * np.pi, 1024, endpoint=False)
    voltage = volt[:, np.newaxis] + dvolt[:, np.newaxis] / 2 * np.sin(theta)
    collected = np.sqrt(np.pi) * width / 2 * erfc((voltage - v0) / width)
    return -2 * np.mean(collected * np.sin(theta), axis=1)


def test_splineinvert_fourier_amplitude() -> None:
    """
    The spline recovers ``P`` from currents computed from the modulation
    without approximation, which checks the normalization of the
    curvature term.
    """
    volt, dvolt = _windows(n=60, start=300.0, step=10.0)
    v0, width = 600.0, 80.0
    p = np.exp(-(((volt - v0) / width) ** 2))
    current = _fourier_currents(volt, dvolt, v0, width)
    result = spp_swp_spc_splineinvert(volt, dvolt, current, nofilter=True)
    interior = slice(5, -5)
    spline_error = np.max(np.abs(result.result - p)[interior])
    naive_error = np.max(np.abs(2 * current / dvolt - p)[interior])
    assert spline_error < MAX_SPLINE_ERROR
    assert spline_error < naive_error / 20
    # with a curvature term twice as large, the spline would be worse
    doubled = current + (current - 0.5 * dvolt * p)
    assert (
        np.max(
            np.abs(
                spp_swp_spc_splineinvert(volt, dvolt, doubled, nofilter=True).result - p
            )[interior]
        )
        > 5 * spline_error
    )
