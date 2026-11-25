"""Test reading L2i files with ``spp_swp_spc_load_l2``."""

from __future__ import annotations

import datetime
import shutil
from typing import TYPE_CHECKING

import numpy as np
import pytest
from spacepy import pycdf

from pyfaradaycup.l2_to_l3._spp_swp_spc_load_l2 import (
    _l2i_file,
    spp_swp_spc_load_l2,
)

if TYPE_CHECKING:
    from pathlib import Path

DATE = datetime.date(2026, 8, 3)


def test_load_l2_reads_production_file(l2_dir: Path, l2i_file: Path) -> None:
    """Every variable of the L2i file is read, with lower-case names."""
    l2i = spp_swp_spc_load_l2(DATE, l2dir=l2_dir)
    assert l2i is not None
    assert l2i.file == l2i_file
    with pycdf.CDF(str(l2i_file)) as cdf:
        assert list(l2i.variables) == [name.lower() for name in cdf]
        for name in cdf:
            raw = cdf.raw_var(name)
            np.testing.assert_array_equal(l2i[name].dat, raw[...])
            assert l2i[name].fillval == raw.attrs.get("FILLVAL")


def test_load_l2_raw_values(l2_dir: Path) -> None:
    """Times are raw TT2000 values, and fill values are raw too."""
    l2i = spp_swp_spc_load_l2("2026-08-03", l2dir=l2_dir)
    assert l2i is not None
    assert l2i["Epoch"].dat.dtype == np.int64
    assert l2i["epoch"].fillval == np.iinfo(np.int64).min
    assert l2i["mv_lo"].dat.shape == (1627, 128)


def test_load_l2_missing(tmp_path: Path) -> None:
    """`None` is returned when there is no L2i file, where IDL returns ``-1``."""
    assert spp_swp_spc_load_l2(DATE, l2dir=tmp_path) is None


@pytest.mark.parametrize(
    ("names", "expected"),
    [
        # the highest version
        (
            ["spp_swp_spc_l2i_20260803_v00.cdf", "spp_swp_spc_l2i_20260803_v01.cdf"],
            "spp_swp_spc_l2i_20260803_v01.cdf",
        ),
        # files split by mode other than l2i don't match _l2i_
        (
            [
                "spp_swp_spc_l2i_20260803_v00.cdf",
                "spp_swp_spc_l2ical_20260803_v03.cdf",
                "spp_swp_spc_l2ifa_20260803_v03.cdf",
                "spp_swp_spc_l2ifs_20260803_v03.cdf",
            ],
            "spp_swp_spc_l2i_20260803_v00.cdf",
        ),
        # release files start with psp_ and sort before spp_
        (
            ["psp_swp_spc_l2i_20260803_v02.cdf", "spp_swp_spc_l2i_20260803_v00.cdf"],
            "spp_swp_spc_l2i_20260803_v00.cdf",
        ),
        (["spp_swp_spc_l2i_20260802_v00.cdf"], None),
        (["spp_swp_spc_l2_20260803_v00.cdf"], None),
    ],
)
def test_l2i_file(tmp_path: Path, names: list[str], expected: str | None) -> None:
    """The alphabetically last ``*_l2i_*YYYYMMDD*.cdf`` file is chosen, as in IDL."""
    month_dir = tmp_path / "2026" / "08"
    month_dir.mkdir(parents=True)
    for name in names:
        (month_dir / name).touch()
    result = _l2i_file(DATE, tmp_path)
    assert result == (None if expected is None else month_dir / expected)


def test_load_l2_reads_last_version(tmp_path: Path, l2i_file: Path) -> None:
    """The highest version is read when there are several."""
    month_dir = tmp_path / "2026" / "08"
    month_dir.mkdir(parents=True)
    shutil.copy(l2i_file, month_dir / "spp_swp_spc_l2i_20260803_v00.cdf")
    shutil.copy(l2i_file, month_dir / "spp_swp_spc_l2i_20260803_v01.cdf")
    l2i = spp_swp_spc_load_l2(DATE, l2dir=tmp_path)
    assert l2i is not None
    assert l2i.file.name == "spp_swp_spc_l2i_20260803_v01.cdf"
