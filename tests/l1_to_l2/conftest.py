"""Fixtures for testing the conversion of L1 files into L2 files."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

import numpy as np
import pytest

from pyfaradaycup.l1_to_l2._spp_swp_spc_apid35x_to_ivt import (
    Ivt,
    spp_swp_spc_apid35x_to_ivt,
)
from pyfaradaycup.l1_to_l2._spp_swp_spc_config_and_hsk_lookup import _read_lowercase
from pyfaradaycup.l1_to_l2._spp_swp_spc_ivt_to_spectra import (
    Spectra,
    spp_swp_spc_ivt_to_spectra,
)
from pyfaradaycup.l1_to_l2._spp_swp_spc_merge_ivt import spp_swp_spc_merge_ivt

if TYPE_CHECKING:
    from collections.abc import Callable

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


def make_ivt(time: list[int], mv_lo: list[float] | None = None, **fields: Any) -> Ivt:  # ruff:ignore[ANN401]
    """
    Return a small IVT for tests.

    The lower voltages default to ``1, 2, 3, ...`` V, and each other field
    defaults to zeros, apart from the higher voltages, which are 1 V above
    the lower ones, and the currents, which are the index of each sample.
    """
    n = len(time)
    lo = (
        np.arange(1, n + 1, dtype=np.float32)
        if mv_lo is None
        else np.array(mv_lo, dtype=np.float32)
    )
    index = np.arange(n, dtype=np.float32)
    values: dict[str, Any] = {
        "time": np.array(time, dtype=np.int64),
        "mv_lo": lo,
        "mv_lo_index": np.zeros(n, dtype=np.uint8),
        "mv_hi": lo + np.float32(1.0),
        "mv_hi_index": np.zeros(n, dtype=np.int16),
        "a": index,
        "b": index + np.float32(0.25),
        "c": index + np.float32(0.5),
        "d": index + np.float32(0.75),
        "a_gain": None,
        "b_gain": None,
        "c_gain": None,
        "d_gain": None,
        "mode": np.zeros(n, dtype=np.uint8),
        "famode": np.zeros(n, dtype=np.int16),
        "fullscan_flag": np.zeros(n, dtype=np.uint8),
        "cal_flag": np.zeros(n, dtype=np.uint8),
        "doublewide_flag": np.zeros(n, dtype=np.uint8),
        "voltage_calfile": Path("voltage.txt"),
        "thermal_calfile": "n/a (empirical model)",
        "gain_calfile": Path("gains.txt"),
        "offset_calfile": None,
        "crosstalk_calfile": Path("crosstalk.txt"),
    }
    for name, value in fields.items():
        values[name] = (
            np.asarray(value, dtype=np.asarray(values[name]).dtype)
            if isinstance(values[name], np.ndarray)
            else value
        )
    return Ivt(**values)


@pytest.fixture(name="make_ivt")
def make_ivt_fixture() -> Callable[..., Ivt]:
    """Return `make_ivt`, for making small IVTs."""
    return make_ivt


@pytest.fixture(scope="session")
def spectra(l1_data: dict[str, dict[str, np.ndarray]]) -> Spectra:
    """Return the spectra for 2026-08-03, merging the IVTs in the order IDL does."""
    ivt = None
    for apid in ("351", "353", "354"):
        this = spp_swp_spc_apid35x_to_ivt(l1_data[apid], l1dir=l1_dir, l2dir=l2_dir)
        ivt = this if ivt is None else spp_swp_spc_merge_ivt(ivt, this)
    if ivt is None:  # for type checkers
        raise AssertionError
    return spp_swp_spc_ivt_to_spectra(ivt)
