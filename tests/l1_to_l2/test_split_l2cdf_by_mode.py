"""Test splitting L2 science files by mode, and the CDF tools it uses."""

from __future__ import annotations

import re
import shutil
from pathlib import Path
from typing import TYPE_CHECKING, Any

import cdflib.xarray
import numpy as np
import pytest
import pytest_check
import xarray
from spacepy import pycdf

from pyfaradaycup.l05_to_l1.cdf_to_survey import (
    _format_like_skeletontable,
    cdf_operate_on,
    cdf_subset,
    make_temp_cdfskeleton,
)
from pyfaradaycup.l1_to_l2._spp_swp_spc_split_l2cdf_by_mode import (
    spp_swp_spc_split_l2cdf_by_mode,
)
from pyfaradaycup.utils._cdf import close_cdf

if TYPE_CHECKING:
    from collections.abc import Callable

repo_root = Path(__file__).parent.parent.parent
l2_month = repo_root / "_psp" / "data" / "sci" / "sweap" / "spc" / "L2" / "2026" / "08"
master = l2_month / "spp_swp_spc_l2_20260803_v00.cdf"
FILL = np.float32(-1e31)

# spacepy 0.7.0 reads string attributes with numpy.char.array, which NumPy
# 2.5 deprecates
pytestmark = pytest.mark.filterwarnings(
    "ignore:The chararray class is deprecated:DeprecationWarning"
)


@pytest.fixture
def l2file(tmp_path: Path) -> Path:
    """Return a copy of the L2 file made in production for 2026-08-03."""
    return Path(shutil.copy(master, tmp_path))


def _set(path: Path, name: str, values: np.ndarray) -> None:
    """Replace the raw values of a variable."""
    cdf = pycdf.CDF(str(path))
    try:
        cdf.readonly(False)  # ruff:ignore[FBT003]
        cdf.raw_var(name)[...] = values
    finally:
        close_cdf(cdf)


def _raw(path: Path, name: str) -> np.ndarray:
    with pycdf.CDF(str(path)) as cdf:
        return np.asarray(cdf.raw_var(name)[...])


@pytest.mark.parametrize(
    ("value", "fmt", "expected"),
    [
        (np.float32(1.5707964), "E7.2", np.float32(1.57)),
        (np.float32(-1e31), "E12.2", np.float32(-1e31)),
        (np.float64(1234.5678), "F8.2", np.float64(1234.57)),
        (np.float32(8000.0), "E8.2", np.float32(8000.0)),
        (np.float32(1.5707964), "I5", np.float32(1.5707964)),
    ],
)
def test_format_like_skeletontable(value: Any, fmt: str, expected: Any) -> None:  # ruff:ignore[ANN401]
    """Test that floats are rounded to Fortran E and F formats, and others are unchanged."""
    result = _format_like_skeletontable(value, fmt)
    assert result == expected
    assert result.dtype == value.dtype


def test_format_like_skeletontable_array() -> None:
    """Test that arrays are rounded element by element."""
    result = _format_like_skeletontable(
        np.array([-1.5707964, 0.0], dtype=np.float32), "E7.2"
    )
    np.testing.assert_array_equal(result, np.array([-1.57, 0.0], dtype=np.float32))


def test_make_temp_cdfskeleton(l2file: Path, tmp_path: Path) -> None:
    """
    Test that the skeleton has no records, keeps variables that are not
    record-varying, and has the changes of a round trip through
    skeletontable and skeletoncdf.
    """
    skeleton = make_temp_cdfskeleton(l2file, tmp_path / "skeleton.cdf")
    with pycdf.CDF(str(skeleton)) as cdf:
        assert len(cdf["Epoch"]) == 0
        assert len(cdf["a_current"]) == 0
        assert cdf["SPC_FRAME"][...].tolist() == ["azimuth   ", "elevation "]
        assert cdf.raw_var("SPC_FRAME").pad() == b" "
        assert "\n" not in cdf["MODE_FLAG"].attrs["VAR_NOTES"]
        assert (
            "0 - ion peak tracking 1 - ion full scan"
            in cdf["MODE_FLAG"].attrs["VAR_NOTES"]
        )
        np.testing.assert_array_equal(
            cdf["flow_angle"].attrs["VALIDMAX"],
            np.array([1.57, 1.57], dtype=np.float32),
        )
        assert cdf["flow_angle"].attrs.type("VALIDMAX") == pycdf.const.CDF_REAL4.value
        assert cdf["mv_lo"].attrs["VALIDMIN"] == np.float32(-8000.0)


def test_cdf_subset(l2file: Path, tmp_path: Path) -> None:
    """Test that the records with values in a range, inclusive, are written."""
    mode = _raw(l2file, "MODE_FLAG")
    outfile = cdf_subset(l2file, "mode_flag", [1, 3], outfile=tmp_path / "out.cdf")
    assert outfile == tmp_path / "out.cdf"
    keep = (mode >= 1) & (mode <= 3)  # ruff:ignore[PLR2004]
    np.testing.assert_array_equal(_raw(outfile, "Epoch"), _raw(l2file, "Epoch")[keep])
    np.testing.assert_array_equal(
        _raw(outfile, "a_current"), _raw(l2file, "a_current")[keep]
    )
    np.testing.assert_array_equal(_raw(outfile, "mv_index"), _raw(l2file, "mv_index"))
    with pycdf.CDF(str(outfile)) as cdf:
        assert cdf.attrs["Logical_file_id"][0] == "out"


def test_cdf_subset_default_name_and_no_records(l2file: Path) -> None:
    """Test the default name, and that no file is written if no records are selected."""
    assert cdf_subset(l2file, "MODE_FLAG", 3) == l2file.with_name(
        "spp_swp_spc_l2_20260803_v00_subset.cdf"
    )
    assert (
        cdf_subset(l2file, "MODE_FLAG", 7, outfile=l2file.with_name("none.cdf")) is None
    )
    assert not l2file.with_name("none.cdf").exists()
    with pytest.raises(KeyError, match="no_such"):
        cdf_subset(l2file, "no_such", 0)


def test_cdf_operate_on(l2file: Path) -> None:
    """Test that the function is applied in place to values that are not fill."""
    mv_lo = _raw(l2file, "mv_lo")
    negative = np.where(mv_lo == FILL, FILL, -mv_lo)
    _set(l2file, "mv_lo", negative)
    assert cdf_operate_on(l2file, "MV_LO", "abs") == l2file
    np.testing.assert_array_equal(_raw(l2file, "mv_lo"), mv_lo)
    assert (mv_lo == FILL).any()
    np.testing.assert_array_equal(_raw(l2file, "mv_hi"), _raw(master, "mv_hi"))
    with pytest.raises(ValueError, match="abs"):
        cdf_operate_on(l2file, "mv_lo", "sqrt")


def test_cdf_operate_on_all_fill(l2file: Path, tmp_path: Path) -> None:
    """Test that no file is written if every value is fill."""
    _set(l2file, "mv_lo", np.full_like(_raw(l2file, "mv_lo"), FILL))
    assert cdf_operate_on(l2file, "mv_lo", "abs", outfile=tmp_path / "out.cdf") is None
    assert not (tmp_path / "out.cdf").exists()


@pytest.fixture(scope="module")
def split_files(tmp_path_factory: pytest.TempPathFactory) -> list[Path]:
    """Return the files that the L2 file for 2026-08-03 is split into."""
    l2file = Path(shutil.copy(master, tmp_path_factory.mktemp("L2")))
    return spp_swp_spc_split_l2cdf_by_mode(l2file)


def test_split_names(split_files: list[Path]) -> None:
    """Test that 2026-08-03, with ion peak tracking, full scan, and calibration spectra, is split into l2i, l2ifs, and l2ical."""
    assert [path.name for path in split_files] == [
        "spp_swp_spc_l2i_20260803_v00.cdf",
        "spp_swp_spc_l2ifs_20260803_v00.cdf",
        "spp_swp_spc_l2ical_20260803_v00.cdf",
    ]


@pytest.mark.parametrize("index", [0, 1, 2])
def test_split_matches_idl(
    index: int, split_files: list[Path], cdf_metadata: Callable[[str], dict[str, Any]]
) -> None:
    """
    Test that each split file is the same as the one made in production,
    apart from the time it was made, including its metadata.
    """
    actual_file = split_files[index]
    expected_file = l2_month / actual_file.name
    expected = cdflib.xarray.cdf_to_xarray(str(expected_file))
    actual = cdflib.xarray.cdf_to_xarray(str(actual_file))
    for dataset in (expected, actual):
        del dataset.attrs["Generation_date"]
    xarray.testing.assert_identical(actual, expected)

    expected_metadata = cdf_metadata(str(expected_file))
    actual_metadata = cdf_metadata(str(actual_file))
    for metadata in (expected_metadata, actual_metadata):
        ((_, generation_date, _),) = metadata["global_attributes"].pop(
            "Generation_date"
        )
        assert re.fullmatch(
            r"\w{3} \w{3} [ \d]\d \d\d:\d\d:\d\d \d{4}", generation_date
        )
    for key, value in expected_metadata.items():
        with pytest_check.check:
            assert actual_metadata[key] == value, key


def _electron_file(l2file: Path, modes: list[int]) -> Path:
    """Make the first spectra of an L2 file electron spectra with negative voltages."""
    mode = _raw(l2file, "MODE_FLAG").copy()
    mode[: len(modes)] = modes
    _set(l2file, "MODE_FLAG", mode)
    for name in ("mv_lo", "mv_hi"):
        values = _raw(l2file, name)
        _set(l2file, name, np.where(values == FILL, FILL, -values))
    return l2file


def test_split_electrons(l2file: Path) -> None:
    """
    Test that electron spectra are split into l2e and l2efa files with
    positive voltages, and that, as in IDL, the l2ecal file is only
    written when there are electron flux angle spectra.
    """
    _electron_file(l2file, [4, 5, 6, 7])
    outfiles = {
        path.name.split("_")[3]: path
        for path in spp_swp_spc_split_l2cdf_by_mode(l2file)
    }
    assert list(outfiles)[:3] == ["l2e", "l2efa", "l2ecal"]
    assert _raw(outfiles["l2e"], "MODE_FLAG").tolist() == [4, 5]
    assert _raw(outfiles["l2ecal"], "MODE_FLAG").tolist() == [7]
    mv_lo = _raw(outfiles["l2e"], "mv_lo")
    assert (mv_lo[mv_lo != FILL] > 0).all()
    # the ion files still have negative voltages, since only electron
    # files are changed
    assert (_raw(outfiles["l2i"], "mv_lo")[:2] != FILL).any()


def test_split_ecal_gated_on_efa(l2file: Path) -> None:
    """Test that there is no l2ecal file without electron flux angle spectra, as in IDL."""
    _electron_file(l2file, [7, 4])
    names = [path.name for path in spp_swp_spc_split_l2cdf_by_mode(l2file)]
    assert "spp_swp_spc_l2e_20260803_v00.cdf" in names
    assert "spp_swp_spc_l2ecal_20260803_v00.cdf" not in names


def test_split_one_spectrum(tmp_path: Path) -> None:
    """Test that a file with one spectrum is not split, as in IDL."""
    l2file = cdf_subset(
        master,
        "Epoch",
        _raw(master, "Epoch")[0],
        outfile=tmp_path / "spp_swp_spc_l2_20260803_v00.cdf",
    )
    assert l2file is not None
    assert len(_raw(l2file, "Epoch")) == 1
    assert spp_swp_spc_split_l2cdf_by_mode(l2file) == []
