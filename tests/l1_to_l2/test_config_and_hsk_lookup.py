"""Test looking up the scan settings and housekeeping values at each time."""

from __future__ import annotations

import datetime
import logging
import shutil
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
import pytest
from spacepy import pycdf

from pyfaradaycup.l1_to_l2._spp_swp_spc_config_and_hsk_lookup import (
    _lookup,
    _lookup_dates,
    spp_swp_spc_config_and_hsk_lookup,
)

if TYPE_CHECKING:
    from collections.abc import Callable


repo_root = Path(__file__).parent.parent.parent
spc_dir = repo_root / "_psp" / "data" / "sci" / "sweap" / "spc"
l1_dir = spc_dir / "L1"
l2_dir = spc_dir / "L2"


def _raw(path: Path, name: str) -> np.ndarray:
    with pycdf.CDF(str(path)) as cdf:
        return cdf.raw_var(name)[...]


hsk_0802 = l2_dir / "2026" / "08" / "spp_swp_spc_APID35Fl2hsk_20260802_v00.cdf"
hsk_0803 = l2_dir / "2026" / "08" / "spp_swp_spc_APID35Fl2hsk_20260803_v00.cdf"


def test_lookup_dates(tt2000: Callable[..., int]) -> None:
    """Test that the days before come first, and then the days, as in IDL."""
    dates = np.array(
        [tt2000(2026, 8, 3, 23), tt2000(2026, 8, 3, 1), tt2000(2026, 8, 4, 0, 0, 1)]
    )
    assert _lookup_dates(dates) == [
        datetime.date(2026, 8, 2),
        datetime.date(2026, 8, 3),
        datetime.date(2026, 8, 3),
        datetime.date(2026, 8, 4),
    ]


def test_config_and_hsk_lookup(
    tt2000: Callable[..., int], l1_file: Callable[..., Path]
) -> None:
    """
    Test that each time gets the values of the last record at or before
    it, including from the day before.
    """
    config_epoch = np.concatenate(
        [_raw(l1_file("35E", "20260802"), "Epoch"), _raw(l1_file("35E"), "Epoch")]
    )
    config_doublewidth = np.concatenate(
        [
            _raw(l1_file("35E", "20260802"), "SW_SPC_DOUBLEWIDTH"),
            _raw(l1_file("35E"), "SW_SPC_DOUBLEWIDTH"),
        ]
    )
    hsk_epoch = np.concatenate([_raw(hsk_0802, "Epoch"), _raw(hsk_0803, "Epoch")])
    hsk_lvtemp = np.concatenate(
        [_raw(hsk_0802, "SW_SPC_LVTEMP"), _raw(hsk_0803, "SW_SPC_LVTEMP")]
    )
    # Times on 2026-08-03 before, at, and after records of that day, so
    # that the earliest uses the last record from 2026-08-02
    first_0803 = _raw(l1_file("35E"), "Epoch")[0]
    dates = np.array(
        [tt2000(2026, 8, 3), first_0803, first_0803 + 1, tt2000(2026, 8, 3, 12)]
    )
    config = spp_swp_spc_config_and_hsk_lookup(dates, l1dir=l1_dir, l2dir=l2_dir)
    assert config.config_files == [l1_file("35E", "20260802"), l1_file("35E")]
    assert config.hsk_files == [hsk_0802, hsk_0803]
    cfg_index = np.searchsorted(config_epoch, dates, side="right") - 1
    hsk_index = np.searchsorted(hsk_epoch, dates, side="right") - 1
    np.testing.assert_array_equal(
        config.sw_spc_doublewidth, config_doublewidth[np.maximum(cfg_index, 0)]
    )
    np.testing.assert_array_equal(
        config.sw_spc_lvtemp, hsk_lvtemp[np.maximum(hsk_index, 0)]
    )
    assert config.sw_spc_lvtemp.dtype == np.float32


def test_config_and_hsk_lookup_default_files(
    tmp_path: Path,
    tt2000: Callable[..., int],
    caplog: pytest.LogCaptureFixture,
    l1_file: Callable[..., Path],
) -> None:
    """Test that the first files from 2018-08 are used if there are none for the days."""
    (tmp_path / "L1" / "2018" / "08" / "APID35E").mkdir(parents=True)
    (tmp_path / "L2" / "2018" / "08").mkdir(parents=True)
    l1_default = (
        tmp_path
        / "L1"
        / "2018"
        / "08"
        / "APID35E"
        / "spp_swp_spc_APID35EL1_20180801_v00.cdf"
    )
    l2_default = (
        tmp_path / "L2" / "2018" / "08" / "spp_swp_spc_APID35Fl2hsk_20180801_v00.cdf"
    )
    shutil.copy(l1_file("35E"), l1_default)
    shutil.copy(hsk_0803, l2_default)
    with caplog.at_level(logging.WARNING):
        config = spp_swp_spc_config_and_hsk_lookup(
            np.array([tt2000(2026, 9, 1)]), l1dir=tmp_path / "L1", l2dir=tmp_path / "L2"
        )
    assert config.config_files == [l1_default]
    assert config.hsk_files == [l2_default]
    assert "commissioning" in caplog.text


def test_config_and_hsk_lookup_no_files(
    tmp_path: Path, tt2000: Callable[..., int]
) -> None:
    """Test that an error is raised if there are no files at all."""
    with pytest.raises(FileNotFoundError, match="35E"):
        spp_swp_spc_config_and_hsk_lookup(
            np.array([tt2000(2026, 9, 1)]), l1dir=tmp_path, l2dir=tmp_path
        )


def test_config_and_hsk_lookup_two_days(
    tt2000: Callable[..., int], l1_file: Callable[..., Path]
) -> None:
    """
    Test that, as in IDL, the file for a day is read twice if it is both
    a day of the times and the day before one of them.
    """
    dates = np.array([tt2000(2026, 8, 2, 12), tt2000(2026, 8, 3, 12)])
    config = spp_swp_spc_config_and_hsk_lookup(dates, l1dir=l1_dir, l2dir=l2_dir)
    assert config.config_files == [
        l1_file("35E", "20260802"),
        l1_file("35E", "20260802"),
        l1_file("35E"),
    ]


def test_lookup_before_first_record() -> None:
    """Test that a time before the first record gets the first record, as IDL clips -1."""
    values = np.array([7, 8, 9])
    assert _lookup(values, np.array([-1, 0, 2])).tolist() == [7, 7, 9]
