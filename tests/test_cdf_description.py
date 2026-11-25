"""Tests of the text descriptions of the skeleton CDF files."""

from __future__ import annotations

import datetime
import shutil
from typing import TYPE_CHECKING, Any

import numpy as np
import pytest
from spacepy import pycdf

from pyfaradaycup import _cdf_description
from pyfaradaycup._cdf_description import describe_cdf, description_path, skeleton_dir

if TYPE_CHECKING:
    import pathlib

SKELETONS = sorted(skeleton_dir.glob("*.cdf"))

REGENERATE = "uv run python -m pyfaradaycup._cdf_description"

#: The number of skeleton CDF files in ``pyfaradaycup/data/cdf_skeletons/``.
N_SKELETONS = 20


def test_skeletons_found() -> None:
    """Test that the skeleton CDF files are found."""
    assert len(SKELETONS) == N_SKELETONS


@pytest.mark.parametrize("skeleton", SKELETONS, ids=lambda path: path.name)
def test_description_matches_skeleton(skeleton: pathlib.Path) -> None:
    """Test that each skeleton CDF file agrees with its text description."""
    description = description_path(skeleton)
    assert description.exists(), f"{description.name} is missing; run {REGENERATE}"
    expected = description.read_text(encoding="utf-8")
    assert describe_cdf(skeleton) == expected, (
        f"{description.name} does not describe {skeleton.name}; run {REGENERATE}"
    )


def test_no_descriptions_without_skeletons() -> None:
    """Test that each text description has a skeleton CDF file."""
    orphans = [
        path.name
        for path in skeleton_dir.glob("*.txt")
        if not path.with_suffix(".cdf").exists()
    ]
    assert not orphans


@pytest.fixture
def skeleton_copy(tmp_path: pathlib.Path) -> pathlib.Path:
    """Return a writable copy of a skeleton CDF file."""
    path = tmp_path / "skeleton.cdf"
    shutil.copy(skeleton_dir / "psp_swp_spc_l1_351_skeleton.cdf", path)
    path.chmod(0o644)
    return path


def test_description_shows_changes(skeleton_copy: pathlib.Path) -> None:
    """Test that changes to a skeleton CDF file change its description."""
    before = describe_cdf(skeleton_copy)
    with pycdf.CDF(str(skeleton_copy), readonly=False) as cdf:
        cdf.attrs["Data_version"][0] = "02"
        cdf["Epoch"].attrs["UNITS"] = "s"
    after = describe_cdf(skeleton_copy)
    assert '0: CDF_CHAR "01"' in before
    assert '0: CDF_CHAR "02"' in after
    assert '"UNITS": CDF_CHAR "ns"' in before
    assert '"UNITS": CDF_CHAR "s"' in after


def test_description_of_records(tmp_path: pathlib.Path) -> None:
    """Test the description of record-varying and non-record-varying data."""
    path = tmp_path / "records.cdf"
    with pycdf.CDF(str(path), "") as cdf:
        cdf.new(
            "Epoch",
            data=np.array([0, 1], dtype=np.int64),
            type=pycdf.const.CDF_TIME_TT2000,
        )
        cdf.new("counts", data=np.array([[1, 2], [3, 4]], dtype=np.uint16))
        cdf.new("labels", data=["x", "yz"], recVary=False)
    description = describe_cdf(path)
    assert (
        '  "Epoch":\n'
        "    type: CDF_TIME_TT2000\n"
        "    number of elements: 1\n"
        "    dimensions: []\n"
        "    dimension variances: []\n"
        "    record variance: True\n"
    ) in description
    assert "    records: 2\n      0: 0\n      1: 1\n" in description
    assert "    dimensions: [2]\n" in description
    assert "    records: 2\n      0: [1, 2]\n      1: [3, 4]\n" in description
    assert (
        "    number of elements: 2\n"
        "    dimensions: [2]\n"
        "    dimension variances: [True]\n"
        "    record variance: False\n"
    ) in description
    assert '    records: 1\n      0: ["x", "yz"]\n' in description


def test_global_time_attribute_raises(tmp_path: pathlib.Path) -> None:
    """Test that a global attribute with a time value is not described."""
    path = tmp_path / "time_attribute.cdf"
    with pycdf.CDF(str(path), "") as cdf:
        cdf.attrs.new(
            "Start_time",
            data=datetime.datetime(2026, 8, 3),  # noqa: DTZ001
            type=pycdf.const.CDF_TIME_TT2000,
        )
    with pytest.raises(NotImplementedError, match="Start_time"):
        describe_cdf(path)


def test_main_writes_description(skeleton_copy: pathlib.Path) -> None:
    """Test that main writes the description next to the CDF file."""
    _cdf_description.main([str(skeleton_copy)])
    description = description_path(skeleton_copy)
    assert description.read_bytes() == describe_cdf(skeleton_copy).encode()


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("Epoch", '"Epoch"'),
        (b"x_HCI", '"x_HCI"'),
        ('say "hi"', '"say \\"hi\\""'),
        (np.float32(-1e31), "-1e+31"),
        # the same with every version of NumPy, unlike str()
        (np.float32(1e6), "1000000.0"),
        (np.float32(1.5707964), "1.5707964"),
        (np.float32(np.nan), "nan"),
        (np.float64(0.1), "0.1"),
        (np.int64(-9223372036854775808), "-9223372036854775808"),
        (np.uint8(254), "254"),
        (np.array(3, dtype=np.int16), "3"),
        (np.array([[1, 2], [3, 4]], dtype=np.uint16), "[[1, 2], [3, 4]]"),
        ([True, False], "[True, False]"),
    ],
)
def test_format_value(value: Any, expected: str) -> None:  # noqa: ANN401
    """Test how values are formatted."""
    assert _cdf_description._format_value(value) == expected


def test_format_value_unknown_type() -> None:
    """Test that a value of an unknown type raises TypeError."""
    with pytest.raises(TypeError, match="dict"):
        _cdf_description._format_value({})
