"""Test the response of SPC to a drifting Maxwellian, from ``spp_swp_spc_pmax_response``."""

from __future__ import annotations

import numpy as np
import pytest
from scipy.integrate import trapezoid
from scipy.special import erfc

from pyfaradaycup.l2_to_l3._spp_swp_spc_pmax_response import (
    E_PC_Q_OVER_M,
    EFFAREA_MM2,
    Q_OVER_M,
    spc_fluxfunction,
    spp_swp_spc_pmax_response,
    spp_swp_spc_pmax_response_normal_curvefit,
)
from pyfaradaycup.utils.idl import fitcurve

P = np.array([400.0, 40.0, 5.0])
"""The bulk speed (km/s), most probable thermal speed (km/s), and density (cm⁻³)."""

E_PC = E_PC_Q_OVER_M / Q_OVER_M
"""The elementary charge in pC that the constants hard-coded in IDL imply."""

MAX_SERIES_ERROR = 1e-6
"""
The largest error of the series of `spp_swp_spc_pmax_response`, relative
to the peak current, for windows up to 10% wide. The terms left out are
of order ``dx**8``, and are about 6e-8 of the peak for these windows.
"""


def _collected_current(volt: np.ndarray, p: np.ndarray = P) -> np.ndarray:
    """
    Return the current collected above ``volt``, in pA.

    For the distribution of `spc_fluxfunction`, the charge flux of the
    ions faster than ``v`` is ``e n (w / (2 sqrt(pi)) exp(-z**2) + (u / 2)
    erfc(z))``, with ``z = (v - u) / w``.
    """
    v = np.sqrt(2 * Q_OVER_M * volt)
    u, w, n = p[0] * 1e3, p[1] * 1e3, p[2] * 1e6
    z = (v - u) / w
    flux = E_PC * n * (w / (2 * np.sqrt(np.pi)) * np.exp(-(z**2)) + u / 2 * erfc(z))
    return EFFAREA_MM2 * 1e-6 * flux


def _fourier_amplitude(volt: np.ndarray, dvolt: np.ndarray) -> np.ndarray:
    """
    Return the first Fourier amplitude of the collected current with the
    voltage ``V + (dV / 2) sin(theta)``, without expanding in ``dV``.

    The trapezoid rule converges exponentially for periodic functions.
    """
    theta = np.linspace(0, 2 * np.pi, 4096, endpoint=False)
    voltage = volt[:, np.newaxis] + dvolt[:, np.newaxis] / 2 * np.sin(theta)
    return -2 * np.mean(_collected_current(voltage) * np.sin(theta), axis=1)


def test_fluxfunction_integral() -> None:
    """
    The flux function integrates over voltage to the charge flux ``e n u``,
    since ``dV`` is ``v dv / (e / m_p)``.
    """
    v = np.linspace(P[0] - 10 * P[1], P[0] + 10 * P[1], 20001) * 1e3
    volt = v**2 / (2 * Q_OVER_M)
    integral = trapezoid(spc_fluxfunction(volt, P), volt)
    np.testing.assert_allclose(integral, E_PC * P[2] * 1e6 * P[0] * 1e3, rtol=1e-9)


def test_fluxfunction_peak() -> None:
    """The flux function peaks where the speed is the bulk speed."""
    volt = np.linspace(500, 1200, 7001)
    peak = volt[np.argmax(spc_fluxfunction(volt, P))]
    np.testing.assert_allclose(peak, (P[0] * 1e3) ** 2 / (2 * Q_OVER_M), atol=0.1)


def test_fluxfunction_charge_and_mass() -> None:
    """
    For alpha particles (Z = 2, M = 4), the flux function is 4 / 4 = 1
    times that of protons at half the voltage, where they have the same
    speed.
    """
    volt = np.array([600.0, 800.0, 1000.0])
    np.testing.assert_allclose(
        spc_fluxfunction(2 * volt, P, charge=2, mass=4),
        spc_fluxfunction(volt, P),
        rtol=1e-14,
    )


@pytest.mark.parametrize("fraction", [0.02, 0.05, 0.1])
def test_pmax_response_fourier_amplitude(fraction: float) -> None:
    """
    The series is the first Fourier amplitude of the collected current with
    sinusoidal modulation, to much better than the zeroth order term alone.
    """
    volt = np.linspace(400, 1500, 45)
    dvolt = fraction * volt
    expected = _fourier_amplitude(volt, dvolt)
    result = spp_swp_spc_pmax_response(volt, dvolt, P)
    peak = expected.max()
    assert np.max(np.abs(result.current - expected)) < MAX_SERIES_ERROR * peak
    assert np.max(np.abs(result.i0 - expected)) > 1e-4 * peak


def test_pmax_response_terms() -> None:
    """The current is the sum of the terms, which get smaller with order."""
    volt = np.linspace(400, 1500, 45)
    result = spp_swp_spc_pmax_response(volt, 0.05 * volt, P)
    np.testing.assert_array_equal(
        result.current, result.i0 + result.i1 + result.i2 + result.i3
    )
    assert np.all(np.abs(result.i1) >= np.abs(result.i2))
    assert np.all(np.abs(result.i2) >= np.abs(result.i3))


def test_pmax_response_area_and_defaults() -> None:
    """The current is proportional to the area, and 0 gives the default area, as in IDL."""
    volt = np.array([700.0, 800.0])
    dvolt = np.array([30.0, 30.0])
    default = spp_swp_spc_pmax_response(volt, dvolt, P).current
    np.testing.assert_array_equal(
        spp_swp_spc_pmax_response(volt, dvolt, P, effarea_mm2=0).current, default
    )
    np.testing.assert_allclose(
        spp_swp_spc_pmax_response(volt, dvolt, P, effarea_mm2=2 * EFFAREA_MM2).current,
        2 * default,
        rtol=1e-15,
    )


def test_pmax_response_normal_curvefit() -> None:
    """The function for fitting takes the lower and upper voltages of the windows."""
    volt = np.linspace(600, 1000, 9, dtype=np.float32)
    dvolt = np.float32(0.05) * volt
    x = np.stack([volt - dvolt / 2, volt + dvolt / 2], axis=1)
    expected = spp_swp_spc_pmax_response(
        (x[:, 0] + x[:, 1]) / 2, x[:, 1] - x[:, 0], P
    ).current
    np.testing.assert_array_equal(
        spp_swp_spc_pmax_response_normal_curvefit(x, P), expected
    )


FIT_RTOL = 1e-4
"""
The relative tolerance of the fitted parameters.

`~pyfaradaycup.utils.idl.fitcurve` stops when chi-squared decreases by a
relative 1e-3 in an iteration, so the parameters are not found exactly.
"""


def test_pmax_response_fit() -> None:
    """Fitting the model currents with `fitcurve`, as IDL does, recovers the parameters."""
    volt = np.linspace(600, 1100, 26, dtype=np.float32)
    dvolt = np.float32(0.06) * volt
    x = np.stack([volt - dvolt / 2, volt + dvolt / 2], axis=1)
    current = spp_swp_spc_pmax_response_normal_curvefit(x, P)
    err = 0.04 * current + 0.1
    guess = P * np.array([1.03, 0.9, 1.1])
    result = fitcurve(
        x,
        current,
        1 / err,
        guess,
        spp_swp_spc_pmax_response_normal_curvefit,
        noderivative=True,
    )
    assert result.status == 0
    np.testing.assert_allclose(result.a, P, rtol=FIT_RTOL)
