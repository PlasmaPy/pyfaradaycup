"""Test the moments of a distribution from ``spp_swp_spc_zmoments``."""

from __future__ import annotations

import numpy as np
import pytest

from pyfaradaycup.l2_to_l3._spp_swp_spc_zmoments import (
    _keyword_set,
    sign,
    spp_swp_spc_zmoments,
)

N, U, W = 7.0, 400.0, 30.0
"""The density, bulk speed, and most probable thermal speed of the test distribution."""


def _maxwellian(z: np.ndarray) -> np.ndarray:
    """Return a one-dimensional drifting Maxwellian in ``z``."""
    return N / (np.sqrt(np.pi) * W) * np.exp(-(((z - U) / W) ** 2))


def test_zmoments_maxwellian() -> None:
    """
    The moments of a drifting Maxwellian are its density, bulk speed, and
    RMS thermal speed ``W / sqrt(2)``. Its central third moment is 0, and
    its fourth moment is ``3 * sigma**4``, so the kurtosis is 3.
    """
    z = np.linspace(U - 10 * W, U + 10 * W, 4001)
    result = spp_swp_spc_zmoments(z, _maxwellian(z), z)
    sigma = W / np.sqrt(2)
    n, u, w, skew, kurt = result.moments
    np.testing.assert_allclose([n, u, w], [N, U, sigma], rtol=1e-10)
    assert abs(skew) < 1e-4 * sigma
    np.testing.assert_allclose(kurt, 3**0.25 * sigma, rtol=1e-10)
    np.testing.assert_allclose(result.kurtosis, 3, rtol=1e-10)
    np.testing.assert_allclose(result.skewness, 0, atol=1e-10)
    # without measure_errors, there is no uncertainty
    np.testing.assert_array_equal(result.sigma[:3], 0)


def test_zmoments_uniform_spacing_ends() -> None:
    """The spacing is centered, and half a step at each end."""
    x = np.array([0.0, 1.0, 2.0, 4.0])
    result = spp_swp_spc_zmoments(x, np.ones(4), x)
    dx = np.array([0.5, 1.0, 1.5, 1.0])
    np.testing.assert_allclose(result.moments[0], dx.sum())
    np.testing.assert_allclose(result.moments[1], (dx * x).sum() / dx.sum())


def test_zmoments_errors() -> None:
    """The uncertainties of the zeroth and first moments are propagated linearly."""
    z = np.linspace(U - 10 * W, U + 10 * W, 401)
    px = _maxwellian(z)
    dpx = 0.01 * px + 1e-4
    result = spp_swp_spc_zmoments(z, px, z, measure_errors=dpx)
    dx = np.gradient(z)
    dx[[0, -1]] /= 2
    n = (px * dx).sum()
    u = (px * dx * z).sum() / n
    dn = np.sqrt(((dx * dpx) ** 2).sum())
    du = np.sqrt(((dpx * dx * z / n) ** 2).sum() + (u * dn / n) ** 2)
    np.testing.assert_allclose(result.sigma[:2], [dn, du], rtol=1e-10)


def test_zmoments_nan() -> None:
    """NaNs in the distribution are left out of the sums."""
    z = np.linspace(U - 10 * W, U + 10 * W, 401)
    px = _maxwellian(z)
    px_nan = px.copy()
    px_nan[0] = np.nan
    expected = px.copy()
    expected[0] = 0
    np.testing.assert_allclose(
        spp_swp_spc_zmoments(z, px_nan, z).moments[:3],
        spp_swp_spc_zmoments(z, expected, z).moments[:3],
        rtol=1e-14,
    )


def test_zmoments_single_precision_grid() -> None:
    """With a single precision grid, the moments are still double precision."""
    z = np.linspace(U - 10 * W, U + 10 * W, 401)
    result = spp_swp_spc_zmoments(
        z.astype(np.float32), _maxwellian(z), z.astype(np.float32)
    )
    assert result.moments.dtype == np.float64
    np.testing.assert_allclose(result.moments[1], U, rtol=1e-6)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, False),
        (0.0, False),
        (np.array([0.0]), False),
        (np.array([2.0]), True),
        (np.zeros(3), True),
        (1.5, True),
    ],
)
def test_keyword_set(value: np.ndarray | float | None, expected: bool) -> None:  # ruff:ignore[FBT001]
    """Arrays of more than one element are set, and other values when nonzero."""
    assert _keyword_set(value) is expected


def test_sign() -> None:
    """``sign`` gives -1, 0, and 1, and 0 for NaN, like CDAWlib's ``SIGN``."""
    assert sign(np.array([-0.5, 0.0, 2.0, np.nan])).tolist() == [-1, 0, 1, 0]
