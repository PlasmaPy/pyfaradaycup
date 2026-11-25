"""Test converting L1 files into L2 files, from Python and the command line."""

from __future__ import annotations

import logging
import re
import shutil
from pathlib import Path
from typing import TYPE_CHECKING, Any

import cdflib.xarray
import numpy as np
import pytest
import pytest_check
import xarray
from click.testing import CliRunner
from spacepy import pycdf

from pyfaradaycup.l1_to_l2 import spp_swp_spc_l1_to_l2_date
from pyfaradaycup.l1_to_l2.main import EXIT_FAILURE, EXIT_NO_DATA, l1_to_l2

if TYPE_CHECKING:
    from collections.abc import Callable

repo_root = Path(__file__).parent.parent.parent
spc_dir = repo_root / "_psp" / "data" / "sci" / "sweap" / "spc"
l1_dir = spc_dir / "L1"
l2_dir = spc_dir / "L2"
month = Path("2026", "08")

HSK_0802 = "spp_swp_spc_APID35Fl2hsk_20260802_v00.cdf"

OUTPUTS = (
    "spp_swp_spc_APID35Fl2hsk_20260803_v00.cdf",
    "spp_swp_spc_l2_20260803_v00.cdf",
    "spp_swp_spc_l2i_20260803_v00.cdf",
    "spp_swp_spc_l2ifs_20260803_v00.cdf",
    "spp_swp_spc_l2ical_20260803_v00.cdf",
)
"""The L2 files made in production for 2026-08-03."""


def _new_l2dir(path: Path) -> Path:
    """
    Return an L2 directory with the L2 housekeeping file for 2026-08-02.

    The science step reads the L2 housekeeping files of each date and the
    day before it, and in production the file for 2026-08-02 was made the
    day before.
    """
    (path / month).mkdir(parents=True)
    shutil.copy(l2_dir / month / HSK_0802, path / month)
    return path


def _invoke(*args: str) -> Any:  # ruff:ignore[ANN401]
    return CliRunner().invoke(l1_to_l2, list(args), catch_exceptions=False)


@pytest.fixture(scope="module")
def l2_from_cli(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Return the L2 directory made by the command line tool for 2026-08-03."""
    tmp_path = tmp_path_factory.mktemp("l1_to_l2")
    l2dir = _new_l2dir(tmp_path / "L2")
    result = _invoke(
        f"--l1dir={l1_dir}",
        f"--l2dir={l2dir}",
        f"--logdir={tmp_path / 'logs'}",
        "2026-08-03",
    )
    assert result.exit_code == 0, result.output
    return l2dir


def test_l1_to_l2_files(l2_from_cli: Path) -> None:
    """Test that the same L2 files are made as in production, and nothing else."""
    names = sorted(path.name for path in (l2_from_cli / month).iterdir())
    assert names == sorted([HSK_0802, *OUTPUTS])


@pytest.mark.parametrize("name", OUTPUTS)
def test_l1_to_l2_matches_idl(
    name: str, l2_from_cli: Path, cdf_metadata: Callable[[str], dict[str, Any]]
) -> None:
    """
    Test that each L2 file is the same as the one made in production,
    apart from the time it was made, including its CDF metadata.
    """
    expected_file = str(l2_dir / month / name)
    actual_file = str(l2_from_cli / month / name)
    expected = cdflib.xarray.cdf_to_xarray(expected_file)
    actual = cdflib.xarray.cdf_to_xarray(actual_file)
    for dataset in (expected, actual):
        dataset.attrs.pop("Generation_date", None)
    xarray.testing.assert_identical(actual, expected)
    with pycdf.CDF(expected_file) as cdf_expected, pycdf.CDF(actual_file) as cdf_actual:
        for variable in cdf_expected:
            with pytest_check.check:
                np.testing.assert_array_equal(
                    cdf_actual.raw_var(variable)[...],
                    cdf_expected.raw_var(variable)[...],
                    err_msg=variable,
                )

    expected_metadata = cdf_metadata(expected_file)
    actual_metadata = cdf_metadata(actual_file)
    for metadata in (expected_metadata, actual_metadata):
        metadata["global_attributes"].pop("Generation_date", None)
    for key, value in expected_metadata.items():
        with pytest_check.check:
            assert actual_metadata[key] == value, key


def test_l1_to_l2_log_file(l2_from_cli: Path) -> None:
    """Test that each date gets a log file with the date and the time it was made."""
    (log_file,) = (l2_from_cli.parent / "logs").iterdir()
    assert re.fullmatch(r"l1_to_l2_20260803_\d{8}T\d{6}Z\.log", log_file.name)
    assert "Wrote 1710 spectra" in log_file.read_text()


def test_l1_to_l2_new_versions(tmp_path: Path) -> None:
    """
    Test that running again makes a new version of the science files, as
    in IDL, and replaces the housekeeping file.
    """
    l2dir = _new_l2dir(tmp_path / "L2")
    for _ in range(2):
        result = _invoke(
            f"--l1dir={l1_dir}",
            f"--l2dir={l2dir}",
            f"--logdir={tmp_path}",
            "2026-08-03",
        )
        assert result.exit_code == 0, result.output
    names = {path.name for path in (l2dir / month).iterdir()}
    assert "spp_swp_spc_l2_20260803_v01.cdf" in names
    assert "spp_swp_spc_l2i_20260803_v01.cdf" in names
    assert "spp_swp_spc_APID35Fl2hsk_20260803_v01.cdf" not in names


def test_spp_swp_spc_l1_to_l2_date(tmp_path: Path) -> None:
    """Test that the Python function makes the main L2 science file, which it returns."""
    l2dir = _new_l2dir(tmp_path)
    l2files = spp_swp_spc_l1_to_l2_date("2026-08-03", l1dir=l1_dir, l2dir=l2dir)
    assert l2files == [l2dir / month / "spp_swp_spc_l2_20260803_v00.cdf"]
    # like IDL, the science files are not split here
    assert not (l2dir / month / "spp_swp_spc_l2i_20260803_v00.cdf").exists()


def test_spp_swp_spc_l1_to_l2_date_hsk_only(tmp_path: Path) -> None:
    """Test that only the L2 housekeeping file is made with hsk_only."""
    assert (
        spp_swp_spc_l1_to_l2_date(
            ["2026-08-03"], l1dir=l1_dir, l2dir=tmp_path, hsk_only=True
        )
        == []
    )
    assert [path.name for path in (tmp_path / month).iterdir()] == [OUTPUTS[0]]


def test_spp_swp_spc_l1_to_l2_date_sci_only(tmp_path: Path) -> None:
    """Test that the existing L2 housekeeping files are used with sci_only."""
    l2dir = _new_l2dir(tmp_path)
    shutil.copy(l2_dir / month / OUTPUTS[0], l2dir / month)
    before = (l2dir / month / OUTPUTS[0]).stat().st_mtime_ns
    l2files = spp_swp_spc_l1_to_l2_date(
        "2026-08-03", l1dir=l1_dir, l2dir=l2dir, sci_only=True
    )
    assert [path.name for path in l2files] == [OUTPUTS[1]]
    assert (l2dir / month / OUTPUTS[0]).stat().st_mtime_ns == before


def test_spp_swp_spc_l1_to_l2_date_no_data(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """Test that a date without L1 files is skipped with a warning."""
    with caplog.at_level(logging.WARNING):
        assert (
            spp_swp_spc_l1_to_l2_date("2026-08-04", l1dir=l1_dir, l2dir=tmp_path) == []
        )
    assert "2026-08-04" in caplog.text


def test_l1_to_l2_no_data(tmp_path: Path) -> None:
    """Test the exit code for a date without L1 files."""
    result = _invoke(
        f"--l1dir={l1_dir}", f"--l2dir={tmp_path}", f"--logdir={tmp_path}", "2026-08-04"
    )
    assert result.exit_code == EXIT_NO_DATA


def test_l1_to_l2_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that a failure is logged, and takes precedence over a date without data."""
    from pyfaradaycup.l1_to_l2 import main  # ruff:ignore[PLC0415]

    def fail(*args: object, **kwargs: object) -> None:  # ruff:ignore[ARG001]
        raise RuntimeError("failed")  # ruff:ignore[EM101]

    monkeypatch.setattr(main, "spp_swp_spc_l1_to_l2_date", fail)
    result = _invoke(
        f"--l1dir={l1_dir}",
        f"--l2dir={tmp_path}",
        f"--logdir={tmp_path}",
        "2026-08-03",
        "2026-08-04",
    )
    assert result.exit_code == EXIT_FAILURE
    log_text = "".join(
        path.read_text() for path in tmp_path.glob("l1_to_l2_20260803_*.log")
    )
    assert "RuntimeError: failed" in log_text


@pytest.mark.parametrize(
    ("options", "message"),
    [
        (["--hsk-only", "--sci-only"], "cannot be used together"),
        (["-v", "-q"], "cannot be used together"),
    ],
)
def test_l1_to_l2_usage_errors(options: list[str], message: str) -> None:
    """Test that incompatible options are rejected."""
    result = CliRunner().invoke(l1_to_l2, [f"--l1dir={l1_dir}", *options, "2026-08-03"])
    assert result.exit_code == 2  # ruff:ignore[PLR2004]
    assert message in result.output


def test_l1_to_l2_invalid_date() -> None:
    """Test that an invalid date is rejected."""
    result = CliRunner().invoke(l1_to_l2, [f"--l1dir={l1_dir}", "2026-13-01"])
    assert result.exit_code == 2  # ruff:ignore[PLR2004]
    assert "is not a date" in result.output
