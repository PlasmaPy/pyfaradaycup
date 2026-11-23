"""Test reading the SPC calibration files used to convert L1 files into L2 files."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from pyfaradaycup.l1_to_l2 import _calibration
from pyfaradaycup.l1_to_l2._calibration import CALIBRATION_DIR, _calfile, _read_ascii
from pyfaradaycup.l1_to_l2._spp_swp_spc_crosstalks import spp_swp_spc_crosstalks
from pyfaradaycup.l1_to_l2._spp_swp_spc_get_gainoffsets import (
    spp_swp_spc_get_gainoffsets,
)
from pyfaradaycup.l1_to_l2._spp_swp_spc_get_gains import spp_swp_spc_get_gains


def test_calfile_uses_last_match(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test that the alphabetically last match, the highest version, is used by default."""
    for name in ("x_20190505_v01.txt", "x_20211124_v00.txt", "x_20190505_v00.txt"):
        (tmp_path / name).touch()
    monkeypatch.setattr(_calibration, "CALIBRATION_DIR", tmp_path)
    assert _calfile(None, "x_*.txt") == tmp_path / "x_20211124_v00.txt"
    assert _calfile("other.txt", "x_*.txt") == Path("other.txt")
    with pytest.raises(FileNotFoundError, match="No calibration file"):
        _calfile(None, "y_*.txt")


def test_read_ascii(tmp_path: Path) -> None:
    """Test that one number is read from each line as float32, skipping blank lines."""
    path = tmp_path / "cal.txt"
    path.write_text("16.\n -28. \n\n  1.00576\n")
    values = _read_ascii(path)
    assert values.dtype == np.float32
    np.testing.assert_array_equal(
        values, np.array([16.0, -28.0, 1.00576], dtype=np.float32)
    )


def test_spp_swp_spc_get_gains() -> None:
    """Test that the gains file has 3 gain factors for each sensor plate."""
    gains = spp_swp_spc_get_gains()
    assert (
        gains.calfile
        == CALIBRATION_DIR / "spp_swp_calfiles_spc_sensorgains_20171010_v00.txt"
    )
    for values in (gains.agains, gains.bgains, gains.cgains, gains.dgains):
        np.testing.assert_array_equal(
            values, np.array([16.0, 16.0, 16.0], dtype=np.float32)
        )


def test_spp_swp_spc_get_gainoffsets() -> None:
    """Test that the offsets file has 4 offsets for each sensor plate."""
    offsets = spp_swp_spc_get_gainoffsets()
    assert (
        offsets.calfile.name
        == "spp_swp_calfiles_spc_sensorgainoffsets_20211124_v00.txt"
    )
    for values in (
        offsets.aoffsets,
        offsets.boffsets,
        offsets.coffsets,
        offsets.doffsets,
    ):
        np.testing.assert_array_equal(
            values, np.array([0.0, -28.0, 0.0, 0.0], dtype=np.float32)
        )


def test_spp_swp_spc_crosstalks(tmp_path: Path) -> None:
    """
    Test that the crosstalk matrix is read one row after another, like
    transpose(reform(values, 4, 4)) indexed as [row, column] in IDL.
    """
    path = tmp_path / "crosstalk.txt"
    path.write_text("\n".join(str(i) for i in range(16)))
    crosstalks = spp_swp_spc_crosstalks(path)
    assert crosstalks.dat[0].tolist() == [0, 1, 2, 3]
    assert crosstalks.dat[:, 0].tolist() == [0, 4, 8, 12]
    assert crosstalks.crosstalk_calfile == path

    default = spp_swp_spc_crosstalks()
    assert (
        default.crosstalk_calfile.name
        == "spp_swp_calfiles_spc_sensorcrosstalk_20190210_v00.txt"
    )
    assert default.dat[0, 0] == np.float32(1.00576)
    assert default.dat[0, 1] == np.float32(-0.0286852)
