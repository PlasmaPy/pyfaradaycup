"""Test looking up flow angles with ``spp_swp_spc_get_angles``."""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
import pytest

from pyfaradaycup.l1_to_l2._spp_swp_spc_moments import DTOR
from pyfaradaycup.l2_to_l3._spp_swp_spc_get_angles import _at, spp_swp_spc_get_angles

if TYPE_CHECKING:
    from pyfaradaycup.l2_to_l3._spp_swp_spc_get_angle_table import AngleTable

MACH_INDEX = 12
"""The slice of the table for a Mach number of 10."""


def _node(table: AngleTable, phi: float, theta: float) -> tuple[int, int]:
    """Return the subscripts of the cell of the table at ``phi`` and ``theta``."""
    i = int(np.flatnonzero(table.phi[:, 0] == phi)[0])
    j = int(np.flatnonzero(table.theta[0, :] == theta)[0])
    return i, j


def _ratios(
    table: AngleTable, i: int, j: int, m: int = MACH_INDEX
) -> tuple[np.ndarray, ...]:
    """Return the ratios ``u`` and ``v`` of a cell of the table, as arrays."""
    return np.array([table.u[i, j, m]]), np.array([table.v[i, j, m]])


@pytest.mark.parametrize(("phi", "theta"), [(5.0, -3.0), (0.0, 0.0), (-20.0, 12.5)])
def test_get_angles_at_nodes(angle_table: AngleTable, phi: float, theta: float) -> None:
    """The ratios of a cell give its angles exactly, in radians."""
    i, j = _node(angle_table, phi, theta)
    us, vs = _ratios(angle_table, i, j)
    angles = spp_swp_spc_get_angles(us=us, vs=vs, machnum=10.0, table=angle_table)
    assert angles.phi[0] == np.float32(phi) * DTOR
    assert angles.theta[0] == np.float32(theta) * DTOR
    assert angles.off_table_flag[0] == 0
    assert angles.phi.dtype == np.float32


def test_get_angles_between_nodes(angle_table: AngleTable) -> None:
    """Between two cells, the gradient correction gives an angle between theirs."""
    i, j = _node(angle_table, 5.0, -3.0)
    m = MACH_INDEX
    us = np.array([(angle_table.u[i, j, m] + angle_table.u[i + 1, j, m]) / 2])
    vs = np.array([(angle_table.v[i, j, m] + angle_table.v[i + 1, j, m]) / 2])
    angles = spp_swp_spc_get_angles(us=us, vs=vs, machnum=10.0, table=angle_table)
    phi = angles.phi[0] / DTOR
    assert 5.0 < phi < 5.25  # ruff:ignore[PLR2004]


def test_get_angles_mach_slice_below(angle_table: AngleTable) -> None:
    """The slice at or below the Mach number is used, not the nearest one."""
    i, j = _node(angle_table, 5.0, -3.0)
    us, vs = _ratios(angle_table, i, j)
    angles = spp_swp_spc_get_angles(us=us, vs=vs, machnum=10.9, table=angle_table)
    assert angles.phi[0] == np.float32(5.0) * DTOR


def test_get_angles_hot_and_nan(angle_table: AngleTable) -> None:
    """A Mach number below the table, or NaN, gives NaN angles."""
    i, j = _node(angle_table, 5.0, -3.0)
    us, vs = _ratios(angle_table, i, j)
    angles = spp_swp_spc_get_angles(
        us=np.repeat(us, 2),
        vs=np.repeat(vs, 2),
        machnum=np.array([0.1, np.nan]),
        table=angle_table,
    )
    assert np.all(np.isnan(angles.phi))
    assert np.all(np.isnan(angles.theta))
    assert np.all(angles.off_table_flag == 0)


def test_get_angles_off_table(angle_table: AngleTable) -> None:
    """Ratios outside the slice are flagged, and get the nearest cell in the field of view."""
    angles = spp_swp_spc_get_angles(
        us=np.array([5.0]), vs=np.array([0.0]), machnum=10.0, table=angle_table
    )
    assert angles.off_table_flag[0] == 1
    assert np.hypot(angles.phi[0], angles.theta[0]) / DTOR <= angles.max_fov_degrees


def test_at_raises_out_of_range() -> None:
    """
    Subscripts beyond the edge raise `IndexError`, as IDL does for scalar
    subscripts, rather than wrapping around as NumPy does for -1.

    With the default table this cannot happen, since its ratios are NaN
    beyond about 50°, so the closest cell is never on the edge.
    """
    array = np.arange(12.0).reshape(3, 4)
    assert _at(array, 2, 3) == array[2, 3]
    for i, j in [(-1, 0), (0, -1), (3, 0), (0, 4)]:
        with pytest.raises(IndexError, match="out of range"):
            _at(array, i, j)


def test_get_angles_never_at_edge(angle_table: AngleTable) -> None:
    """The ratios of the table are NaN on its edges, so no lookup uses an edge cell."""
    for m in range(angle_table.machnum.size):
        u = angle_table.u[:, :, m]
        assert not np.isfinite(u[[0, -1], :]).any()
        assert not np.isfinite(u[:, [0, -1]]).any()


def test_get_angles_crosstalk_factors(angle_table: AngleTable) -> None:
    """``kew`` and ``kns`` multiply the east–west and north–south ratios."""
    i, j = _node(angle_table, 5.0, -3.0)
    us, vs = _ratios(angle_table, i, j)
    angles = spp_swp_spc_get_angles(
        us=us / 2, vs=vs / 4, machnum=10.0, table=angle_table, kns=2.0, kew=4.0
    )
    assert angles.phi[0] == np.float32(5.0) * DTOR
    assert angles.theta[0] == np.float32(-3.0) * DTOR


COLD_LINEAR_RTOL = 0.01
"""
The agreement of the table with the cold linear approximation of the L1 to
L2 step, ``theta = u / 0.035`` degrees, for small angles at Mach 100.
"""


@pytest.mark.parametrize("theta", [1.0, 2.0, 3.0])
def test_get_angles_cold_linear(angle_table: AngleTable, theta: float) -> None:
    """At a high Mach number and small angles, the table agrees with the cold linear approximation."""
    i, j = _node(angle_table, 0.0, theta)
    u = angle_table.u[i, j, -1]
    np.testing.assert_allclose(u / 0.035, theta, rtol=COLD_LINEAR_RTOL)
