"""Test converting L0.5 files into L1 files, from Python and the command line."""

from __future__ import annotations

import datetime
import logging
import os
import pickle
import re
import types
from pathlib import Path
from typing import TYPE_CHECKING, Any

import cdflib.xarray
import numpy as np
import pytest
import pytest_check
import xarray
from click.testing import CliRunner

from pyfaradaycup.l05_to_l1 import (
    SPC_L1_APIDS,
    NoL05DataError,
    _spp_swp_spc_l05_to_l1,
    spp_swp_spc_l05_to_l1_date,
    spp_swp_spc_l05_to_l1_dates,
    spp_swp_spc_which_apid,
)
from pyfaradaycup.l05_to_l1._spp_swp_spc_l05_to_l1 import (
    _l05_children,
    _months_around,
    _parse_date,
)
from pyfaradaycup.l05_to_l1.main import EXIT_FAILURE, EXIT_NO_DATA, l05_to_l1

if TYPE_CHECKING:
    from collections.abc import Callable

    from spacepy import pycdf

repo_root = Path(__file__).parent.parent.parent
spc_dir = repo_root / "_psp" / "data" / "sci" / "sweap" / "spc"
l05_dir = spc_dir / "L05"
l1_dir = spc_dir / "L1"

date = datetime.date(2026, 8, 3)


@pytest.mark.parametrize(
    ("filenames", "expected"),
    [
        (["0523462910_4_EA_APID351_L1.cdf"], ["351"]),
        ([Path("L05/2026/08/APID35E/0523462910_4_EA_APID35E_L1.cdf")], ["35E"]),
        (["no_apid.cdf", "x_APID353_L1.cdf"], ["", "353"]),
        ([], []),
        ("0523462910_4_EA_APID351_L1.cdf", ["351"]),
        ("/data/spc_APID_l05/2026/08/APID353/x_APID353_L1.cdf", ["353"]),
        (Path("spc_APID_l05/no_apid.cdf"), [""]),
        ("_APID351_L1.cdf", [""]),
        (Path("L05/2026/08/APID35E/0523462910_4_EA_APID35E_L1.cdf"), ["35E"]),
    ],
)
def test_spp_swp_spc_which_apid(filenames: list[Any], expected: list[str]) -> None:
    """
    Test that the APID is the three characters after the first _APID in
    the name of the file, not counting one at the start of the name.
    """
    assert spp_swp_spc_which_apid(filenames) == expected


@pytest.mark.parametrize(
    "value",
    [
        date,
        datetime.datetime(2026, 8, 3, 12, tzinfo=datetime.timezone.utc),
        datetime.datetime(2026, 8, 3, 23),  # ruff:ignore[DTZ001]
        datetime.datetime(
            2026, 8, 2, 21, tzinfo=datetime.timezone(datetime.timedelta(hours=-4))
        ),
        datetime.datetime(
            2026, 8, 4, 2, tzinfo=datetime.timezone(datetime.timedelta(hours=4))
        ),
        "2026-08-03",
        "2026-08-03T12:34:56Z",
    ],
)
def test_parse_date(value: datetime.date | str) -> None:
    """
    Test that dates can be given as dates, datetimes, and ISO 8601
    strings, and that datetimes with time zones are converted to UTC.
    """
    assert _parse_date(value) == date


@pytest.mark.parametrize("value", ["2026-8-3", "20260803", "2026-13-01"])
def test_parse_date_invalid(value: str) -> None:
    """Test that a string that does not start with a valid date is an error."""
    with pytest.raises(ValueError):  # ruff:ignore[PT011]
        _parse_date(value)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (date, [(2026, 7), (2026, 8), (2026, 9)]),
        (datetime.date(2026, 1, 1), [(2025, 12), (2026, 1), (2026, 2)]),
        (datetime.date(2026, 12, 31), [(2026, 11), (2026, 12), (2027, 1)]),
    ],
)
def test_months_around(value: datetime.date, expected: list[tuple[int, int]]) -> None:
    """Test that the months before, of, and after a date are found."""
    assert _months_around(value) == expected


def test_l05_children(
    tmp_path: Path,
    l05_file: Callable[..., Path],
    tt2000: Callable[..., int],
) -> None:
    """
    Test that L0.5 files with records on a date are found in the
    directories for the month of the date and the months before and
    after it, and that other files are not.
    """
    on_date = tt2000(2026, 8, 3, 12)
    expected = [
        l05_file(tmp_path / "2026/07/APID353/a_APID353_L1.cdf", [on_date]),
        l05_file(tmp_path / "2026/08/APID353/b_APID353_L1.cdf", [on_date]),
        l05_file(tmp_path / "2026/08/APID35E/c_APID35E_L1.cdf", [on_date]),
        l05_file(tmp_path / "2026/09/APID353/d_APID353_L1.cdf", [on_date]),
    ]
    # Files with no records on the date, or not in a searched directory
    l05_file(tmp_path / "2026/08/APID353/e_APID353_L1.cdf", [tt2000(2026, 8, 4)])
    l05_file(tmp_path / "2026/06/APID353/f_APID353_L1.cdf", [on_date])
    l05_file(tmp_path / "2026/08/g_APID353_L1.cdf", [on_date])
    assert _l05_children(date, tmp_path) == expected


def test_l05_children_skips_other_apids(
    tmp_path: Path,
    l05_file: Callable[..., Path],
    tt2000: Callable[..., int],
) -> None:
    """
    Test that L0.5 files for APIDs that have no L1 files are not opened,
    so that a file for one of them that cannot be read is not an error.
    """
    expected = [
        l05_file(tmp_path / "2026/08/APID353/a_APID353_L1.cdf", [tt2000(2026, 8, 3)])
    ]
    unreadable = tmp_path / "2026/08/APID352/b_APID352_L1.cdf"
    unreadable.parent.mkdir(parents=True)
    unreadable.write_bytes(b"not a CDF file")
    assert _l05_children(date, tmp_path) == expected


def test_l05_children_skips_unreadable_files(
    tmp_path: Path,
    l05_file: Callable[..., Path],
    tt2000: Callable[..., int],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """
    Test that an L0.5 file that cannot be read is skipped with a
    warning, and that the other files are still found.
    """
    expected = [
        l05_file(tmp_path / "2026/08/APID353/a_APID353_L1.cdf", [tt2000(2026, 8, 3)])
    ]
    unreadable = tmp_path / "2026/08/APID353/b_APID353_L1.cdf"
    unreadable.write_bytes(b"not a CDF file")
    with caplog.at_level(logging.WARNING, logger="pyfaradaycup"):
        assert _l05_children(date, tmp_path) == expected
    assert f"Could not read {unreadable}" in caplog.text


def test_l05_children_reads_each_file_once(
    tmp_path: Path,
    l05_file: Callable[..., Path],
    tt2000: Callable[..., int],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Test that the dates in an L0.5 file are read once for several
    dates, and read again after the file changes.
    """
    path = l05_file(tmp_path / "2026/08/APID353/a_APID353_L1.cdf", [tt2000(2026, 8, 3)])
    opened: list[str] = []
    cdf_class = _spp_swp_spc_l05_to_l1.pycdf.CDF

    def counting_cdf(name: str) -> pycdf.CDF:
        opened.append(name)
        return cdf_class(name)

    monkeypatch.setattr(
        _spp_swp_spc_l05_to_l1, "pycdf", types.SimpleNamespace(CDF=counting_cdf)
    )
    assert _l05_children(date, tmp_path) == [path]
    assert _l05_children(datetime.date(2026, 8, 4), tmp_path) == []
    assert opened == [str(path)]

    path.unlink()
    l05_file(path, [tt2000(2026, 8, 4)])
    stat = path.stat()
    os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns + 1_000_000_000))
    assert _l05_children(datetime.date(2026, 8, 4), tmp_path) == [path]
    assert opened == [str(path), str(path)]


def test_spp_swp_spc_l05_to_l1_date_skips_apid352(tmp_path: Path) -> None:
    """
    Test that an L1 file is made for each APID except 352, which has no
    L1 files.
    """
    l1files = spp_swp_spc_l05_to_l1_date(date, l05dir=l05_dir, l1dir=tmp_path)
    assert l1files == [
        tmp_path
        / "2026"
        / "08"
        / f"APID{apid}"
        / f"spp_swp_spc_APID{apid}L1_20260803_v00.cdf"
        for apid in SPC_L1_APIDS
    ]
    assert "352" not in SPC_L1_APIDS
    assert (l05_dir / "2026" / "08" / "APID352").is_dir()


def test_spp_swp_spc_l05_to_l1_date_no_data(tmp_path: Path) -> None:
    """Test that an error is raised when no L0.5 files have data for the date."""
    with pytest.raises(NoL05DataError, match="have SPC data for 2026-08-04") as excinfo:
        spp_swp_spc_l05_to_l1_date("2026-08-04", l05dir=l05_dir, l1dir=tmp_path / "L1")
    assert excinfo.value.date == datetime.date(2026, 8, 4)
    assert excinfo.value.l05dir == l05_dir
    assert not (tmp_path / "L1").exists()


def test_spp_swp_spc_l05_to_l1_date_writes_none_if_one_exists(tmp_path: Path) -> None:
    """
    Test that without overwrite, no L1 files are written for a date if
    the L1 file for any APID already exists, even a later one.
    """
    l1files = spp_swp_spc_l05_to_l1_date(date, l05dir=l05_dir, l1dir=tmp_path)
    *removed, kept = l1files
    for path in removed:
        path.unlink()
    with pytest.raises(FileExistsError, match="none were written") as excinfo:
        spp_swp_spc_l05_to_l1_date(date, l05dir=l05_dir, l1dir=tmp_path)
    assert str(kept) in str(excinfo.value)
    assert not any(path.exists() for path in removed)


def test_no_l05_data_error_pickle() -> None:
    """Test that NoL05DataError can be pickled, as is needed by multiprocessing."""
    error = NoL05DataError(date, l05_dir)
    unpickled = pickle.loads(pickle.dumps(error))  # ruff:ignore[S301]
    assert str(unpickled) == str(error)
    assert unpickled.date == date
    assert unpickled.l05dir == l05_dir


def test_spp_swp_spc_l05_to_l1_dates(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """
    Test that duplicate dates are converted once, and that dates with no
    data are skipped with a warning.
    """
    with caplog.at_level(logging.WARNING, logger="pyfaradaycup"):
        l1files = spp_swp_spc_l05_to_l1_dates(
            ["2026-08-04", date, "2026-08-03"], l05dir=l05_dir, l1dir=tmp_path
        )
    assert len(l1files) == len(SPC_L1_APIDS)
    assert "2026-08-04; skipping this date" in caplog.text


@pytest.mark.parametrize("value", [date, "2026-08-03"])
def test_spp_swp_spc_l05_to_l1_dates_one_date(
    tmp_path: Path, value: datetime.date | str
) -> None:
    """Test that a single date is treated as a list of one date, like in IDL."""
    l1files = spp_swp_spc_l05_to_l1_dates(value, l05dir=l05_dir, l1dir=tmp_path)
    assert l1files == spp_swp_spc_l05_to_l1_dates(
        [date], l05dir=l05_dir, l1dir=tmp_path, overwrite=True
    )


def test_l05_to_l1(tmp_path: Path) -> None:
    """Test that the command line tool writes the L1 files and a log file."""
    result = CliRunner().invoke(
        l05_to_l1,
        [
            f"--l05dir={l05_dir}",
            f"--l1dir={tmp_path / 'L1'}",
            f"--logdir={tmp_path}",
            "-v",
            "2026-08-03",
        ],
        catch_exceptions=False,
    )
    assert result.exit_code == 0, result.output
    assert "INFO: Wrote 5 L1 CDF files for 2026-08-03" in result.output
    (log_file,) = tmp_path.glob("*.log")
    assert re.fullmatch(r"l05_to_l1_20260803_\d{8}T\d{6}Z\.log", log_file.name)
    log = log_file.read_text(encoding="utf-8")
    assert "Running l05_to_l1 with options" in log
    for apid in SPC_L1_APIDS:
        assert f"spp_swp_spc_APID{apid}L1_20260803_v00.cdf" in log
        assert (
            tmp_path
            / "L1"
            / "2026"
            / "08"
            / f"APID{apid}"
            / f"spp_swp_spc_APID{apid}L1_20260803_v00.cdf"
        ).is_file()


def test_l05_to_l1_no_data(tmp_path: Path) -> None:
    """
    Test that the exit code is 65 when a date has no data, and that the
    other dates are still converted.
    """
    result = CliRunner().invoke(
        l05_to_l1,
        [
            f"--l05dir={l05_dir}",
            f"--l1dir={tmp_path / 'L1'}",
            f"--logdir={tmp_path}",
            "2026-08-04",
            "2026-08-03",
        ],
    )
    assert result.exit_code == EXIT_NO_DATA == 65  # ruff:ignore[PLR2004]
    assert "No L0.5 files" in result.output
    assert len(list((tmp_path / "L1").rglob("*.cdf"))) == len(SPC_L1_APIDS)
    assert len(list(tmp_path.glob("*.log"))) == 2  # ruff:ignore[PLR2004]


def test_l05_to_l1_overwrite(tmp_path: Path) -> None:
    """
    Test that the exit code is 1 when an L1 file already exists, and
    that it is replaced with -o.
    """

    def invoke(run: int, *options: str) -> Any:  # ruff:ignore[ANN401]
        # Log files are named to the second, so each run gets its own
        # log directory to keep the log files from having the same name
        args = [
            f"--l05dir={l05_dir}",
            f"--l1dir={tmp_path / 'L1'}",
            f"--logdir={tmp_path / f'log{run}'}",
        ]
        return CliRunner().invoke(l05_to_l1, [*args, *options, "2026-08-03"])

    assert invoke(1).exit_code == 0

    result = invoke(2)
    assert result.exit_code == EXIT_FAILURE
    assert "already exist" in result.output

    result = invoke(3, "-o")
    assert result.exit_code == 0, result.output


def test_l05_to_l1_failure_takes_precedence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    Test that the exit code is 1 when one date fails and another has no
    data.
    """
    from pyfaradaycup.l05_to_l1 import main  # ruff:ignore[PLC0415]

    def fail(date: datetime.date, **kwargs: Any) -> list[Path]:  # ruff:ignore[ANN401]
        if date == datetime.date(2026, 8, 3):
            msg = "test failure"
            raise RuntimeError(msg)
        raise NoL05DataError(date, kwargs["l05dir"])

    monkeypatch.setattr(main, "spp_swp_spc_l05_to_l1_date", fail)
    result = CliRunner().invoke(
        l05_to_l1,
        [f"--l05dir={l05_dir}", f"--logdir={tmp_path}", "2026-08-03", "2026-08-04"],
    )
    assert result.exit_code == EXIT_FAILURE
    assert "test failure" in result.output


@pytest.mark.parametrize("value", ["2026-8-3", "yesterday"])
def test_l05_to_l1_invalid_date(tmp_path: Path, value: str) -> None:
    """Test that an invalid date is a usage error."""
    result = CliRunner().invoke(l05_to_l1, [f"--l05dir={l05_dir}", value])
    assert result.exit_code == 2  # ruff:ignore[PLR2004]
    assert "is not a date like 2026-08-03" in result.output
    assert not list(tmp_path.iterdir())


def test_l05_to_l1_requires_date() -> None:
    """Test that at least one date is required."""
    result = CliRunner().invoke(l05_to_l1, [f"--l05dir={l05_dir}"])
    assert result.exit_code == 2  # ruff:ignore[PLR2004]
    assert "Missing argument 'DATE...'" in result.output


def test_l05_to_l1_verbose_and_quiet() -> None:
    """Test that -v and -q cannot be used together."""
    result = CliRunner().invoke(
        l05_to_l1, [f"--l05dir={l05_dir}", "-v", "-q", "2026-08-03"]
    )
    assert result.exit_code == 2  # ruff:ignore[PLR2004]
    assert "cannot be used together" in result.output


@pytest.fixture(scope="module")
def l1_from_cli(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Return the L1 directory made by the command line tool for 2026-08-03."""
    tmp_path = tmp_path_factory.mktemp("l05_to_l1")
    result = CliRunner().invoke(
        l05_to_l1,
        [
            f"--l05dir={l05_dir}",
            f"--l1dir={tmp_path / 'L1'}",
            f"--logdir={tmp_path}",
            "2026-08-03",
        ],
        catch_exceptions=False,
    )
    assert result.exit_code == 0, result.output
    return tmp_path / "L1"


def _l1_name(apid: str) -> Path:
    """Return the path of an L1 file for 2026-08-03 relative to the L1 directory."""
    return Path(
        "2026", "08", f"APID{apid}", f"spp_swp_spc_APID{apid}L1_20260803_v00.cdf"
    )


@pytest.mark.parametrize("apid", SPC_L1_APIDS)
def test_l1_matches_idl(
    apid: str,
    l1_from_cli: Path,
    cdf_metadata: Callable[[str], dict[str, Any]],
) -> None:
    """
    Test that the L1 files match the ones made by IDL, apart from the
    time they were made.
    """
    expected_file = str(l1_dir / _l1_name(apid))
    actual_file = str(l1_from_cli / _l1_name(apid))

    # Keep times as datetime64[ns] so that the full nanosecond precision of
    # CDF_TIME_TT2000 is compared
    expected = cdflib.xarray.cdf_to_xarray(expected_file)
    actual = cdflib.xarray.cdf_to_xarray(actual_file)
    for dataset in (expected, actual):
        del dataset.attrs["Generation_date"]
    xarray.testing.assert_identical(actual, expected)
    for name, variable in expected.variables.items():
        with pytest_check.check:
            assert actual[name].dtype == variable.dtype, name

    # Compare the CDF metadata that is lost in the conversion to xarray
    expected_metadata = cdf_metadata(expected_file)
    actual_metadata = cdf_metadata(actual_file)
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


@pytest.mark.parametrize("apid", SPC_L1_APIDS)
def test_l1_records_are_in_idl_l1(apid: str, l1_from_cli: Path) -> None:
    """
    Test that every record in each L1 file is in the L1 file made by
    IDL with the same values.
    """
    expected = cdflib.xarray.cdf_to_xarray(str(l1_dir / _l1_name(apid)))
    actual = cdflib.xarray.cdf_to_xarray(str(l1_from_cli / _l1_name(apid)))
    assert list(actual.variables) == list(expected.variables)
    (record_dim,) = actual["Epoch"].dims
    epoch = actual["Epoch"].values
    assert epoch.size > 0
    assert np.all(np.diff(epoch) > np.timedelta64(0, "ns"))
    expected_subset = expected.isel(
        {record_dim: np.isin(expected["Epoch"].values, epoch)}
    )
    # assert_equal does not compare attributes, which differ in Generation_date
    xarray.testing.assert_equal(actual, expected_subset)


def test_l1_api_matches_cli(tmp_path: Path, l1_from_cli: Path) -> None:
    """Test that calling the Python function gives the same files as the command line tool."""
    l1files = spp_swp_spc_l05_to_l1_date(date, l05dir=l05_dir, l1dir=tmp_path)
    for apid, l1file in zip(SPC_L1_APIDS, l1files):
        assert l1file == tmp_path / _l1_name(apid)
        expected = cdflib.xarray.cdf_to_xarray(str(l1_from_cli / _l1_name(apid)))
        actual = cdflib.xarray.cdf_to_xarray(str(l1file))
        for dataset in (expected, actual):
            del dataset.attrs["Generation_date"]
        xarray.testing.assert_identical(actual, expected)
