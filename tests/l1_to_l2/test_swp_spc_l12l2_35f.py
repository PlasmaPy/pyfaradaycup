"""Test converting SPC housekeeping L1 files (APID 35F) into L2 files."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import TYPE_CHECKING, Any

import cdflib.xarray
import numpy as np
import pytest
import pytest_check
import xarray
from spacepy import pycdf

from pyfaradaycup.l1_to_l2 import swp_spc_l12l2_35f
from pyfaradaycup.l1_to_l2.swp_spc_l12l2_35f import (
    SKELETON_35F,
    _compile_formula,
    convert_one,
    hk_dn2eng,
)
from pyfaradaycup.utils._cdf import close_cdf

if TYPE_CHECKING:
    from collections.abc import Callable

repo_root = Path(__file__).parent.parent.parent
spc_dir = repo_root / "_psp" / "data" / "sci" / "sweap" / "spc"
l1file = (
    spc_dir
    / "L1"
    / "2026"
    / "08"
    / "APID35F"
    / "spp_swp_spc_APID35FL1_20260803_v00.cdf"
)
expected_l2file = (
    spc_dir / "L2" / "2026" / "08" / "spp_swp_spc_APID35Fl2hsk_20260803_v00.cdf"
)
l2name = "spp_swp_spc_APID35Fl2hsk_20260803_v00.cdf"


def _l1_keys() -> list[str]:
    with pycdf.CDF(str(l1file)) as cdf:
        return list(cdf)


def test_hk_dn2eng_finds_formulas() -> None:
    """
    Test that the 35F variables with formulas in conversion_formulas.qlf
    get conversion functions, and the others do not.
    """
    conv_fxns = hk_dn2eng([*_l1_keys(), "SW_SPC_DEN"])
    assert len(conv_fxns) == 26  # ruff:ignore[PLR2004]
    assert "SW_SPC_LVTEMP" in conv_fxns
    for key in (
        "Epoch",
        "SW_SPC_MINVOLT",
        "SW_SPC_MAXVOLT",
        "SW_SPC_FA",
        "SW_SPC_MODE",
    ):
        assert key not in conv_fxns
    raw = np.array([0.0, 1000.0])
    np.testing.assert_array_equal(conv_fxns["SW_SPC_DEN"](raw), raw)
    np.testing.assert_array_equal(
        conv_fxns["SW_SPC_HVOUT"](raw), (5.0 * raw**0) + (-0.002442002442002 * raw)
    )


def test_hk_dn2eng_last_match_wins(tmp_path: Path) -> None:
    """Test that the last line with a formula for a variable is used."""
    fxn_path = tmp_path / "formulas.qlf"
    fxn_path.write_text(
        'EU(Raw="APID_35F.X") := (2.0 * Raw)\n'
        'EU(Raw="APID_35F.XY") := (5.0 * Raw)\n'
        'EU(Raw="APID_35F.X") := (3.0 * Raw)\n'
    )
    conv_fxns = hk_dn2eng(["X", "Y"], fxn_path)
    assert list(conv_fxns) == ["X"]
    assert conv_fxns["X"](np.array([1.0]))[0] == 3.0  # ruff:ignore[PLR2004]


@pytest.mark.parametrize(
    "formula",
    [
        "__import__('os')",
        "a.real",
        "b * 2",
        "abs(a)",
        "'1' * a",
        "True * a",
        "[a][0]",
    ],
)
def test_compile_formula_rejects_non_arithmetic(formula: str) -> None:
    """Test that formulas other than arithmetic on Raw are not evaluated."""
    with pytest.raises(ValueError, match="is not arithmetic on Raw"):
        _compile_formula(formula)


def test_compile_formula_matches_eval() -> None:
    """Test that a compiled formula gives exactly what eval gives in the original script."""
    formula = "(173.8 * a ** 0) + (-1.44 * a) + (0.0087 * a ** 2) - (3.2e-05 * a ** 3)"
    raw = np.linspace(0.0, 4095.0, 101)
    expected = eval("lambda a: " + formula)(raw)  # ruff:ignore[S307]
    np.testing.assert_array_equal(_compile_formula(formula)(raw), expected)


@pytest.fixture(scope="module")
def l2file(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Return the L2 housekeeping file made from the L1 file for 2026-08-03."""
    return convert_one(l1file, tmp_path_factory.mktemp("l2"))


def test_convert_one_name(l2file: Path) -> None:
    """Test that the L2 file is named by replacing L1 with l2hsk."""
    assert l2file.name == l2name
    assert not list(l2file.parent.glob(".*"))  # no temporary files are left


def test_convert_one_matches_original(
    l2file: Path, cdf_metadata: Callable[[str], dict[str, Any]]
) -> None:
    """
    Test that the data and the CDF metadata, apart from variable
    attributes, match the L2 file made by the original script.
    """
    # Keep times as datetime64[ns] so that the full nanosecond precision of
    # CDF_TIME_TT2000 is compared
    expected = cdflib.xarray.cdf_to_xarray(str(expected_l2file))
    actual = cdflib.xarray.cdf_to_xarray(str(l2file))
    xarray.testing.assert_equal(actual, expected)
    assert actual.attrs == expected.attrs
    for name, variable in expected.variables.items():
        with pytest_check.check:
            assert actual[name].dtype == variable.dtype, name

    expected_metadata = cdf_metadata(str(expected_l2file))
    actual_metadata = cdf_metadata(str(l2file))
    for metadata in (expected_metadata, actual_metadata):
        for variable in metadata["variables"].values():
            del variable["attrs"]
    for key, value in expected_metadata.items():
        with pytest_check.check:
            assert actual_metadata[key] == value, key


@pytest.mark.xfail(
    reason=(
        "The packaged psp_swp_spc_l2_35f_skeleton.cdf gives the converted "
        "variables engineering-unit attributes, while the L2 file made in "
        "production has the DN attributes of the L1 variables, so production "
        "used a different skeleton."
    ),
    strict=True,
)
def test_convert_one_variable_attributes_match_original(
    l2file: Path, cdf_metadata: Callable[[str], dict[str, Any]]
) -> None:
    """Test that the variable attributes match the L2 file made by the original script."""
    expected = cdf_metadata(str(expected_l2file))["variables"]
    actual = cdf_metadata(str(l2file))["variables"]
    assert {name: var["attrs"] for name, var in actual.items()} == {
        name: var["attrs"] for name, var in expected.items()
    }


def test_convert_one_rounds_epoch_to_microseconds(l2file: Path) -> None:
    """
    Test that Epoch is rounded to the nearest microsecond, like the
    original script, which reads it as datetime values.
    """
    with pycdf.CDF(str(l1file)) as l1, pycdf.CDF(str(l2file)) as l2:
        l1_epoch = l1.raw_var("Epoch")[...]
        l2_epoch = l2.raw_var("Epoch")[...]
    assert np.all(l2_epoch % 1000 == 0)
    assert np.abs(l2_epoch - l1_epoch).max() <= 500  # ruff:ignore[PLR2004]


def test_convert_one_default_l2dir(tmp_path: Path) -> None:
    """Test that the L2 file is written next to the L1 file by default."""
    copied = shutil.copy(l1file, tmp_path)
    assert convert_one(copied) == tmp_path / l2name


def test_convert_one_exists(tmp_path: Path) -> None:
    """
    Test that an existing L2 file is only replaced with overwrite, and is
    left unchanged otherwise.
    """
    existing = tmp_path / l2name
    existing.write_bytes(b"existing")
    with pytest.raises(FileExistsError, match="already exists"):
        convert_one(l1file, tmp_path)
    assert existing.read_bytes() == b"existing"

    assert convert_one(l1file, tmp_path, overwrite=True) == existing
    with pycdf.CDF(str(existing)) as cdf:
        assert len(cdf["Epoch"]) > 0


def test_convert_one_keeps_existing_file_on_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test that an existing L2 file is kept, and no partial file is left, if writing fails."""
    existing = tmp_path / l2name
    existing.write_bytes(b"existing")

    def fail(keys: object) -> None:  # ruff:ignore[ARG001]
        raise RuntimeError("failed")  # ruff:ignore[EM101]

    monkeypatch.setattr(swp_spc_l12l2_35f, "hk_dn2eng", fail)
    with pytest.raises(RuntimeError, match="failed"):
        convert_one(l1file, tmp_path, overwrite=True)
    assert existing.read_bytes() == b"existing"
    assert [path.name for path in tmp_path.iterdir()] == [l2name]


def test_convert_one_name_without_l1(tmp_path: Path) -> None:
    """Test that an error is raised for an L1 file whose name does not contain L1."""
    with pytest.raises(ValueError, match="does not contain 'L1'"):
        convert_one(tmp_path / "spp_swp_spc_APID35F_20260803.cdf", tmp_path)


def test_convert_one_missing_file(tmp_path: Path) -> None:
    """Test that an error is raised for an L1 file that does not exist."""
    with pytest.raises(FileNotFoundError, match="was not found"):
        convert_one(tmp_path / "spp_swp_spc_APID35FL1_20260803_v00.cdf", tmp_path)


def test_convert_one_extra_variable(tmp_path: Path) -> None:
    """Test that an error is raised for an L1 file with a variable not in the skeleton."""
    path = tmp_path / "spp_swp_spc_APID35FL1_20260803_v00.cdf"
    cdf = pycdf.CDF(str(path), str(SKELETON_35F))
    try:
        cdf.new("EXTRA", data=np.zeros(1, dtype=np.int16))
    finally:
        close_cdf(cdf)
    with pytest.raises(ValueError, match=r"not in .*: \['EXTRA'\]"):
        convert_one(path, tmp_path / "L2")
