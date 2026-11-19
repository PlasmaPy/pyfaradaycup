"""Test merging CDF files into daily CDF files."""

from __future__ import annotations

import datetime
import logging
import time
import warnings
from typing import TYPE_CHECKING

import numpy as np
import pytest
from spacepy import pycdf

from pyfaradaycup._paths import data_dir
from pyfaradaycup.l05_to_l1 import cdf_merge_to_daily
from pyfaradaycup.l05_to_l1.cdf_to_survey import _unique_dates
from pyfaradaycup.utils.idl import cdf_epoch_tojuldays

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

skeleton_353 = data_dir / "cdf_skeletons" / "psp_swp_spc_l1_353_skeleton.cdf"
skeleton_351 = data_dir / "cdf_skeletons" / "psp_swp_spc_l1_351_skeleton.cdf"

TT2000_FILL = -9223372036854775808
TT2000_PAD = -9223372036854775807


def test_unique_dates_at_midnight(tt2000: Callable[..., int]) -> None:
    """Test that a record at midnight is on the new day."""
    epoch = np.array([tt2000(2026, 8, 2, 23, 59, 59, 999000), tt2000(2026, 8, 3)])
    assert _unique_dates(cdf_epoch_tojuldays(epoch)) == [
        datetime.date(2026, 8, 2),
        datetime.date(2026, 8, 3),
    ]


def test_unique_dates_leap_second(tt2000: Callable[..., int]) -> None:
    """
    Test that a time during the leap second at the end of 2016 is put in
    the next day, as the CDF library converts it.
    """
    before = tt2000(2016, 12, 31, 23, 59, 59, 500000)
    during = before + 1_000_000_000  # 2016-12-31T23:59:60.5
    jd = cdf_epoch_tojuldays(np.array([before, during]))
    assert _unique_dates(jd[:1]) == [datetime.date(2016, 12, 31)]
    assert _unique_dates(jd[1:]) == [datetime.date(2017, 1, 1)]


def test_unique_dates_skips_fill_and_pad_values(tt2000: Callable[..., int]) -> None:
    """Test that fill and pad values of Epoch are not dates."""
    epoch = np.array([TT2000_FILL, TT2000_PAD, tt2000(2026, 8, 3, 12)])
    assert _unique_dates(cdf_epoch_tojuldays(epoch)) == [datetime.date(2026, 8, 3)]


def _global_attribute(path: Path, name: str) -> str:
    """Return the first entry of a global attribute of a CDF file."""
    with warnings.catch_warnings(), pycdf.CDF(str(path)) as cdf:
        # spacepy 0.7.0 reads string attribute entries with numpy.char.array,
        # which NumPy 2.5 deprecates.
        warnings.filterwarnings(
            "ignore", "The chararray class is deprecated", DeprecationWarning
        )
        return str(cdf.attrs[name][0])


def _merge(  # ruff:ignore[PLR0913]
    infiles: list[Path],
    tmp_path: Path,
    *,
    skeletonfile: Path = skeleton_353,
    outdate: datetime.date | None = datetime.date(2026, 8, 3),
    outversion: int = 0,
    overwrite: bool = False,
) -> list[Path]:
    """Merge files into ``tmp_path / "out"``, by default for 2026-08-03."""
    return cdf_merge_to_daily(
        infiles,
        skeletonfile=skeletonfile,
        outname="merged",
        outpath=tmp_path / "out",
        outdate=outdate,
        outversion=outversion,
        overwrite=overwrite,
    )


def test_cdf_merge_to_daily_sorts_and_selects_day(
    tmp_path: Path,
    l05_file: Callable[..., Path],
    tt2000: Callable[..., int],
    read_raw: Callable[[Path, str], np.ndarray],
) -> None:
    """
    Test that records from several files are sorted by time, and that
    records on other days are left out.
    """
    file1 = l05_file(
        tmp_path / "a.cdf",
        [tt2000(2026, 8, 3, 12), tt2000(2026, 8, 3, 1), tt2000(2026, 8, 4)],
        [10, 11, 12],
    )
    file2 = l05_file(
        tmp_path / "b.cdf",
        [tt2000(2026, 8, 2, 23, 59, 59), tt2000(2026, 8, 3), tt2000(2026, 8, 3, 6)],
        [20, 21, 22],
    )
    (outfile,) = _merge([file1, file2], tmp_path)
    assert outfile == tmp_path / "out" / "merged_20260803_v00.cdf"
    assert read_raw(outfile, "CCSDS_SeqCnt").tolist() == [21, 11, 22, 10]
    epoch = read_raw(outfile, "Epoch")
    assert np.all(np.diff(epoch) > 0)
    assert epoch.dtype == np.int64


def test_cdf_merge_to_daily_keeps_last_duplicate(
    tmp_path: Path,
    l05_file: Callable[..., Path],
    tt2000: Callable[..., int],
    read_raw: Callable[[Path, str], np.ndarray],
) -> None:
    """
    Test that, of records with the same time, the one that comes last in
    the order of the input files is kept, as IDL's uniq keeps the last.
    """
    times = [tt2000(2026, 8, 3, 1), tt2000(2026, 8, 3, 2)]
    file1 = l05_file(tmp_path / "a.cdf", times, [10, 11])
    file2 = l05_file(tmp_path / "b.cdf", times, [20, 21])
    (outfile,) = _merge([file1, file2], tmp_path)
    assert read_raw(outfile, "CCSDS_SeqCnt").tolist() == [20, 21]


def test_cdf_merge_to_daily_merges_near_duplicates(
    tmp_path: Path,
    l05_file: Callable[..., Path],
    tt2000: Callable[..., int],
    read_raw: Callable[[Path, str], np.ndarray],
) -> None:
    """
    Test that records less than about 40 µs apart are treated as
    duplicates, as in IDL, which compares float64 Julian days, while
    records 1 ms apart are not.

    When duplicates are removed based on the exact TT2000 values
    instead, this test should be changed.
    """
    t0 = tt2000(2026, 8, 3, 1)
    file1 = l05_file(
        tmp_path / "a.cdf",
        [t0, t0 + 1_000, t0 + 1_000_000],  # 0, 1 µs, and 1 ms later
        [10, 11, 12],
    )
    (outfile,) = _merge([file1], tmp_path)
    assert read_raw(outfile, "CCSDS_SeqCnt").tolist() == [11, 12]
    assert read_raw(outfile, "Epoch").tolist() == [t0 + 1_000, t0 + 1_000_000]


def test_cdf_merge_to_daily_single_record(
    tmp_path: Path,
    l05_file: Callable[..., Path],
    tt2000: Callable[..., int],
    read_raw: Callable[[Path, str], np.ndarray],
) -> None:
    """Test a day with only one record."""
    file1 = l05_file(tmp_path / "a.cdf", [tt2000(2026, 8, 3, 5)], [7])
    (outfile,) = _merge([file1], tmp_path)
    assert read_raw(outfile, "CCSDS_SeqCnt").tolist() == [7]


def test_cdf_merge_to_daily_attributes(
    tmp_path: Path,
    l05_file: Callable[..., Path],
    tt2000: Callable[..., int],
) -> None:
    """
    Test that Logical_file_id is the name of the file and that
    Generation_date is the current time in the format of IDL's systime().
    """
    file1 = l05_file(tmp_path / "a.cdf", [tt2000(2026, 8, 3, 5)])
    before = time.time()
    (outfile,) = _merge([file1], tmp_path, outversion=3)
    assert outfile.name == "merged_20260803_v03.cdf"
    assert _global_attribute(outfile, "Logical_file_id") == "merged_20260803_v03"
    generation_date = _global_attribute(outfile, "Generation_date")
    parsed = time.mktime(time.strptime(generation_date, "%a %b %d %H:%M:%S %Y"))
    assert before - 1 <= parsed <= time.time()


def test_cdf_merge_to_daily_no_records_on_outdate(
    tmp_path: Path,
    l05_file: Callable[..., Path],
    tt2000: Callable[..., int],
) -> None:
    """Test that nothing is written when no records are on ``outdate``."""
    file1 = l05_file(tmp_path / "a.cdf", [tt2000(2026, 8, 4, 5)])
    assert _merge([file1], tmp_path) == []
    assert not (tmp_path / "out").exists()


def test_cdf_merge_to_daily_every_date(
    tmp_path: Path,
    l05_file: Callable[..., Path],
    tt2000: Callable[..., int],
    read_raw: Callable[[Path, str], np.ndarray],
) -> None:
    """Test that a file is written for every day when ``outdate`` is None."""
    file1 = l05_file(
        tmp_path / "a.cdf",
        [tt2000(2026, 8, 4, 5), tt2000(2026, 8, 3, 5), tt2000(2026, 8, 4, 1)],
        [10, 11, 12],
    )
    outfiles = _merge([file1], tmp_path, outdate=None)
    assert [f.name for f in outfiles] == [
        "merged_20260803_v00.cdf",
        "merged_20260804_v00.cdf",
    ]
    assert read_raw(outfiles[0], "CCSDS_SeqCnt").tolist() == [11]
    assert read_raw(outfiles[1], "CCSDS_SeqCnt").tolist() == [12, 10]


def test_cdf_merge_to_daily_missing_file(
    tmp_path: Path,
    l05_file: Callable[..., Path],
    tt2000: Callable[..., int],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that an input file that does not exist is skipped with a warning."""
    missing = tmp_path / "missing.cdf"
    file1 = l05_file(tmp_path / "a.cdf", [tt2000(2026, 8, 3, 5)])
    with caplog.at_level(logging.WARNING, logger="pyfaradaycup"):
        outfiles = _merge([missing, file1], tmp_path)
    assert len(outfiles) == 1
    assert f"{missing} was not found" in caplog.text


def test_cdf_merge_to_daily_all_files_missing(tmp_path: Path) -> None:
    """Test that an error is raised when none of the input files exist."""
    with pytest.raises(FileNotFoundError, match="None of the input files"):
        _merge([tmp_path / "missing.cdf"], tmp_path)


def test_cdf_merge_to_daily_overwrite(
    tmp_path: Path,
    l05_file: Callable[..., Path],
    tt2000: Callable[..., int],
    read_raw: Callable[[Path, str], np.ndarray],
) -> None:
    """
    Test that an existing output file is replaced only when
    ``overwrite`` is True.
    """
    file1 = l05_file(tmp_path / "a.cdf", [tt2000(2026, 8, 3, 5)], [1])
    file2 = l05_file(tmp_path / "b.cdf", [tt2000(2026, 8, 3, 6)], [2])
    (outfile,) = _merge([file1], tmp_path)
    with pytest.raises(FileExistsError, match="already exists"):
        _merge([file2], tmp_path)
    assert read_raw(outfile, "CCSDS_SeqCnt").tolist() == [1]
    _merge([file2], tmp_path, overwrite=True)
    assert read_raw(outfile, "CCSDS_SeqCnt").tolist() == [2]


def test_cdf_merge_to_daily_skeleton_mismatch(
    tmp_path: Path,
    l05_file: Callable[..., Path],
    tt2000: Callable[..., int],
) -> None:
    """
    Test that an error is raised, and no output file is written, when
    the skeleton does not have the same variables as the input files.
    """
    file1 = l05_file(tmp_path / "a.cdf", [tt2000(2026, 8, 3, 5)])
    with pytest.raises(ValueError, match="are not the same"):
        _merge([file1], tmp_path, skeletonfile=skeleton_351)
    assert not (tmp_path / "out").exists()


def test_cdf_merge_to_daily_matches_variables_by_name(
    tmp_path: Path,
    l05_file: Callable[..., Path],
    tt2000: Callable[..., int],
    read_raw: Callable[[Path, str], np.ndarray],
) -> None:
    """
    Test that the variables in the input files are matched with those in
    the skeleton by name, so they can be in a different order.
    """
    original = l05_file(
        tmp_path / "original.cdf", [tt2000(2026, 8, 3, 5), tt2000(2026, 8, 3, 6)]
    )
    reordered = tmp_path / "reordered.cdf"
    with pycdf.CDF(str(original)) as source, pycdf.CDF(str(reordered), "") as cdf:
        names = list(source)
        for name in reversed(names):
            cdf.new(name, type=source[name].type(), recVary=source[name].rv())
            cdf.raw_var(name)[...] = source.raw_var(name)[...]
        assert list(cdf) == names[::-1]
    (outfile,) = _merge([reordered], tmp_path)
    for name in names:
        np.testing.assert_array_equal(
            read_raw(outfile, name), read_raw(original, name), err_msg=name
        )


def test_cdf_merge_to_daily_input_mismatch(
    tmp_path: Path,
    l05_file: Callable[..., Path],
    tt2000: Callable[..., int],
) -> None:
    """Test that an error is raised when input files have different variables."""
    file1 = l05_file(tmp_path / "a.cdf", [tt2000(2026, 8, 3, 5)])
    file2 = l05_file(tmp_path / "b.cdf", [tt2000(2026, 8, 3, 6)], skeleton=skeleton_351)
    with pytest.raises(ValueError, match="has variables"):
        _merge([file1, file2], tmp_path)
