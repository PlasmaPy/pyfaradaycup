"""Test the effective area of SPC from ``spp_swp_spc_get_effective_area``."""

from __future__ import annotations

import numpy as np
import pytest
from scipy.io import readsav

from pyfaradaycup.l1_to_l2._spp_swp_spc_get_effective_area import (
    A0,
    EFFECTIVE_AREA_TABLE,
    spp_swp_spc_get_effective_area,
)
from pyfaradaycup.l1_to_l2._spp_swp_spc_moments import DTOR


@pytest.fixture(scope="module")
def table() -> dict[str, np.ndarray]:
    """Return the effective area table, with ``ea`` in IDL's order ``[alpha, mach]``."""
    save = readsav(str(EFFECTIVE_AREA_TABLE))
    return {"ea": save["ea"].T, "alpha": save["alpha"], "machnums": save["machnums"]}


def test_approx_normal_incidence() -> None:
    """The analytic approximation at normal incidence is ``A0``, as ``spp_swp_spc_get1rdf`` uses it."""
    area = spp_swp_spc_get_effective_area(0.0, 0.0, approx=True, units="degrees")
    assert area.dat == A0
    assert area.dat.dtype == np.float32


def test_approx_radians() -> None:
    """
    For angles in radians, the analytic approximation is ``A0 * (1 - 1.17
    alpha)``, since IDL's ``ac`` is 24.35 rather than ``24.35 * rad``.
    """
    phi = np.array([0.1, 0.3], dtype=np.float32)
    area = spp_swp_spc_get_effective_area(phi, np.zeros(2, np.float32), approx=True)
    np.testing.assert_allclose(area.dat, A0 * (1 - np.float32(1.17) * phi), rtol=1e-6)


def test_approx_degrees_limit() -> None:
    """For angles in degrees, the analytic approximation is 0 at 45° and beyond."""
    area = spp_swp_spc_get_effective_area(
        np.array([44.0, 46.0], np.float32),
        np.zeros(2, np.float32),
        approx=True,
        units="deg",
    )
    assert area.dat[0] > 0
    assert area.dat[1] == 0


def test_warm_at_nodes(table: dict[str, np.ndarray]) -> None:
    """At the angles and Mach numbers of the table, the warm area is the table's."""
    alpha = np.array([0.0, 10.0, 30.0], dtype=np.float32)
    mach = np.array([2.0, 5.0, 20.0])
    area = spp_swp_spc_get_effective_area(
        alpha, np.zeros(3, np.float32), machnum=mach, units="degrees"
    )
    i = [int(np.flatnonzero(table["alpha"] == a)[0]) for a in alpha]
    m = [int(np.flatnonzero(table["machnums"] == x)[0]) for x in mach]
    np.testing.assert_allclose(area.dat, table["ea"][i, m], rtol=1e-6)


def test_warm_between_machnums(table: dict[str, np.ndarray]) -> None:
    """Between two Mach numbers, the area is interpolated linearly."""
    alpha = np.float32(20.0)
    area = spp_swp_spc_get_effective_area(
        alpha, np.float32(0.0), machnum=np.array([4.25]), units="degrees"
    )
    i = int(np.flatnonzero(table["alpha"] == alpha)[0])
    expected = 0.75 * table["ea"][i, 4] + 0.25 * table["ea"][i, 5]
    np.testing.assert_allclose(area.dat, expected, rtol=1e-6)


def test_warm_scalar_machnum_and_units() -> None:
    """A single Mach number applies to every angle, and radians and degrees agree."""
    phi_deg = np.array([3.0, 7.0], dtype=np.float32)
    degrees = spp_swp_spc_get_effective_area(
        phi_deg, np.zeros(2, np.float32), machnum=8.0, units="degrees"
    )
    radians = spp_swp_spc_get_effective_area(
        phi_deg * DTOR, np.zeros(2, np.float32), machnum=8.0
    )
    np.testing.assert_allclose(degrees.dat, radians.dat, rtol=1e-5)


def test_warm_nan_is_edge(table: dict[str, np.ndarray]) -> None:
    """
    In the warm case, a NaN angle is taken as 90°, since IDL's ``<``
    ignores a NaN operand, so the area is that at the edge of the table.
    """
    area = spp_swp_spc_get_effective_area(
        np.array([np.nan], np.float32),
        np.zeros(1, np.float32),
        machnum=5.0,
        units="degrees",
    )
    assert area.dat[0] == table["ea"][-1, 5]


def test_cold_matches_warm_at_largest_machnum() -> None:
    """The cold limit is the warm area at the largest Mach number of the table."""
    phi = np.linspace(0, 0.5, 11, dtype=np.float32)
    theta = np.full(11, 0.05, dtype=np.float32)
    cold = spp_swp_spc_get_effective_area(phi, theta)
    warm = spp_swp_spc_get_effective_area(phi, theta, machnum=1e6)
    np.testing.assert_allclose(warm.dat, cold.dat, rtol=1e-6)


def test_machnum_zero_is_cold() -> None:
    """A Mach number of 0 is taken as no Mach number, as IDL uses ``keyword_set``."""
    phi = np.array([0.1, 0.2], dtype=np.float32)
    theta = np.zeros(2, np.float32)
    np.testing.assert_array_equal(
        spp_swp_spc_get_effective_area(phi, theta, machnum=0).dat,
        spp_swp_spc_get_effective_area(phi, theta).dat,
    )
