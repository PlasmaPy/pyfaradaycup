"""Test reading the flow angle lookup table."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

import numpy as np
import pytest
from scipy.io import readsav

from pyfaradaycup.l2_to_l3._spp_swp_spc_get_angle_table import (
    CALIBRATION_DIR_ENV,
    AngleTable,
    spp_swp_spc_get_angle_table,
)

if TYPE_CHECKING:
    from pathlib import Path

MAX_ANGLE = 90
"""The largest magnitude of the angles in the table, in degrees."""


def test_angle_table_shapes(angle_table: AngleTable) -> None:
    """The arrays have IDL's order of dimensions."""
    nmach = angle_table.machnum.size
    assert angle_table.phi.shape == angle_table.theta.shape
    assert angle_table.u.shape == (*angle_table.phi.shape, nmach)
    assert angle_table.v.shape == angle_table.u.shape


def test_angle_table_machnum_increasing(angle_table: AngleTable) -> None:
    """The Mach numbers increase, as ``value_locate`` needs."""
    assert np.all(np.diff(angle_table.machnum) > 0)


def test_angle_table_idl_order(angle_table: AngleTable, angle_table_file: Path) -> None:
    """``u[i, j, m]`` is the element of the save file with IDL subscripts ``[i, j, m]``."""
    raw = readsav(str(angle_table_file))["table"][0]
    # different subscripts, at a point on the table where u is not NaN
    i, j, m = 300, 410, 7
    assert np.isfinite(angle_table.u[i, j, m])
    assert angle_table.u[i, j, m] == raw["U"][m, j, i]
    assert angle_table.u[i, j, m] != angle_table.u[j, i, m]
    assert angle_table.phi[i, j] == raw["PHI"][j, i]
    # a one-dimensional IDL subscript follows Fortran order
    loc = i + j * angle_table.phi.shape[0]
    idl_subscripts = np.unravel_index(loc, angle_table.phi.shape, order="F")
    assert angle_table.phi[idl_subscripts] == angle_table.phi[i, j]


def test_angle_table_angles(angle_table: AngleTable) -> None:
    """The angles vary along the expected dimensions, within ±90°."""
    assert np.all(np.abs(angle_table.phi) <= MAX_ANGLE)
    assert np.all(np.abs(angle_table.theta) <= MAX_ANGLE)
    # phi varies along the first dimension, and theta along the second
    assert np.all(angle_table.phi == angle_table.phi[:, :1])
    assert np.all(angle_table.theta == angle_table.theta[:1, :])
    assert np.all(np.diff(angle_table.phi[:, 0]) > 0)
    assert np.all(np.diff(angle_table.theta[0, :]) > 0)


def test_angle_table_no_default(monkeypatch: pytest.MonkeyPatch) -> None:
    """Without a file or the environment variable, the error says how to give it."""
    monkeypatch.delenv(CALIBRATION_DIR_ENV, raising=False)
    with pytest.raises(FileNotFoundError, match=CALIBRATION_DIR_ENV):
        spp_swp_spc_get_angle_table()


def test_angle_table_missing_file(tmp_path: Path) -> None:
    """A file that does not exist raises `FileNotFoundError`."""
    with pytest.raises(FileNotFoundError, match="does not exist"):
        spp_swp_spc_get_angle_table(tmp_path / "missing.idl")


def test_angle_table_default_from_environment(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The default file is looked for in the directory given by the environment variable."""
    monkeypatch.setenv(CALIBRATION_DIR_ENV, str(tmp_path))
    with pytest.raises(FileNotFoundError, match=re.escape(str(tmp_path))):
        spp_swp_spc_get_angle_table()
