"""Fixtures for testing the conversion of L2 files into L3 files."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from pyfaradaycup.l2_to_l3._spp_swp_spc_get_angle_table import (
    ANGLE_TABLE_NAME,
    CALIBRATION_DIR_ENV,
)

repo_root = Path(__file__).parent.parent.parent
spc_dir = repo_root / "_psp" / "data" / "sci" / "sweap" / "spc"
l2_dir = spc_dir / "L2"
l3_dir = spc_dir / "L3"

L2I_FILE = l2_dir / "2026" / "08" / "spp_swp_spc_l2i_20260803_v00.cdf"
"""The L2i file made in production for 2026-08-03."""

L3I_FILE = l3_dir / "2026" / "08" / "spp_swp_spc_l3i_20260803_v00.cdf"
"""The L3i file made in production for 2026-08-03."""


@pytest.fixture(scope="session")
def angle_table_file() -> Path:
    """
    Return the path of the flow angle lookup table.

    The table is not in the repository, so tests that use it are skipped
    unless the ``PYFARADAYCUP_CALIBRATION_DIR`` environment variable is
    set to the directory that contains it.
    """
    calibration_dir = os.environ.get(CALIBRATION_DIR_ENV)
    if not calibration_dir:
        pytest.skip(f"{CALIBRATION_DIR_ENV} is not set")
    path = Path(calibration_dir) / ANGLE_TABLE_NAME
    if not path.is_file():
        pytest.skip(f"{path} does not exist")
    return path


@pytest.fixture(name="l2_dir")
def l2_dir_fixture() -> Path:
    """Return the L2 directory in ``_psp/``."""
    return l2_dir


@pytest.fixture
def l2i_file() -> Path:
    """Return the L2i file made in production for 2026-08-03."""
    return L2I_FILE


@pytest.fixture
def l3i_file() -> Path:
    """Return the L3i file made in production for 2026-08-03."""
    return L3I_FILE
