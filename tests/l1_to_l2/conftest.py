"""Fixtures for testing the conversion of L1 files into L2 files."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from pyfaradaycup.l1_to_l2._spp_swp_spc_config_and_hsk_lookup import _read_lowercase

if TYPE_CHECKING:
    from collections.abc import Callable

    import numpy as np

repo_root = Path(__file__).parent.parent.parent
spc_dir = repo_root / "_psp" / "data" / "sci" / "sweap" / "spc"
l1_dir = spc_dir / "L1"
l2_dir = spc_dir / "L2"


def l1_file(apid: str, date: str = "20260803") -> Path:
    """Return the path of an L1 file in ``_psp/``."""
    return (
        l1_dir
        / date[:4]
        / date[4:6]
        / f"APID{apid}"
        / f"spp_swp_spc_APID{apid}L1_{date}_v00.cdf"
    )


@pytest.fixture(name="l1_file")
def l1_file_fixture() -> Callable[..., Path]:
    """Return `l1_file`, for the paths of L1 files in ``_psp/``."""
    return l1_file


@pytest.fixture(scope="session")
def l1_data() -> dict[str, dict[str, np.ndarray]]:
    """Return the variables of the science L1 files for 2026-08-03, by APID."""
    return {apid: _read_lowercase([l1_file(apid)]) for apid in ("351", "353", "354")}
