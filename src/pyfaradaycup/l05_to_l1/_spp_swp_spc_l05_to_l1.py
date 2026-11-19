"""
Convert SPC L0.5 CDF files into daily L1 CDF files.

This module is a port of the IDL files ``spp_swp_spc_l05_to_l1_dates.pro``,
``spp_swp_spc_l05_to_l1_date.pro``, and ``spp_swp_spc_which_apid.pro``.
"""

from __future__ import annotations

__all__ = [
    "SPC_L1_APIDS",
    "NoL05DataError",
    "spp_swp_spc_l05_to_l1_date",
    "spp_swp_spc_l05_to_l1_dates",
    "spp_swp_spc_which_apid",
]

import datetime
import functools
import logging
import os
import pathlib
from typing import TYPE_CHECKING

import numpy as np
from spacepy import pycdf

from pyfaradaycup._paths import data_dir
from pyfaradaycup.l05_to_l1.cdf_to_survey import _unique_dates, cdf_merge_to_daily
from pyfaradaycup.utils.idl import cdf_epoch_tojuldays

if TYPE_CHECKING:
    from collections.abc import Iterable

logger = logging.getLogger(__name__)

_ISO_DATE_LENGTH = 10
"""The length of a date in ISO 8601 format, like ``2026-08-03``."""

SPC_L1_APIDS: tuple[str, ...] = ("351", "353", "354", "35E", "35F")
"""The APIDs that L1 files are made for, in the order they are made."""


class NoL05DataError(ValueError):
    """
    Raised when there are no L0.5 files with SPC data for a date.

    Parameters
    ----------
    date : datetime.date
        The date that has no data.
    l05dir : pathlib.Path
        The L0.5 directory that was searched.
    """

    def __init__(self, date: datetime.date, l05dir: pathlib.Path) -> None:
        super().__init__(
            f"No L0.5 files in {l05dir} have SPC data for {date.isoformat()}"
        )
        self.date = date
        self.l05dir = l05dir

    def __reduce__(
        self,
    ) -> tuple[type[NoL05DataError], tuple[datetime.date, pathlib.Path]]:
        """Pickle with the arguments, which are not the exception's args."""
        return type(self), (self.date, self.l05dir)


def spp_swp_spc_which_apid(
    filenames: str | os.PathLike[str] | Iterable[str | os.PathLike[str]],
) -> list[str]:
    """
    Return the APID in the name of each file.

    Parameters
    ----------
    filenames : path-like or `~collections.abc.Iterable` of path-like
        File names, like ``0523462910_4_EA_APID351_L1.cdf``. Like in
        IDL, a single file name is treated as a list of one file name.

    Returns
    -------
    list of str
        The three characters after the first ``_APID`` in each file
        name, like ``"351"``, or ``""`` if there is no ``_APID``.

    Examples
    --------
    >>> spp_swp_spc_which_apid(["0523462910_4_EA_APID35E_L1.cdf", "other.cdf"])
    ['35E', '']
    >>> spp_swp_spc_which_apid("0523462910_4_EA_APID351_L1.cdf")
    ['351']
    """
    if isinstance(filenames, (str, os.PathLike)):
        filenames = [filenames]
    apids = []
    for filename in filenames:
        name = os.fspath(filename)
        position = name.find("_APID")
        apids.append(name[position + 5 : position + 8] if position >= 0 else "")
    return apids


def _parse_date(date: datetime.date | str) -> datetime.date:
    """
    Return a date given as a `datetime.date` or an ISO 8601 string.

    Like ``TIMESTAMPTOVALUES`` in IDL, only the date is used from a
    string like ``"2026-08-03T12:00:00Z"``. A `datetime.datetime` with a
    time zone is converted to UTC first, and one without a time zone is
    taken to be in UTC.

    Raises
    ------
    ValueError
        If ``date`` is a string that does not start with a date in the
        format ``YYYY-MM-DD``.
    """
    if isinstance(date, datetime.datetime):
        if date.utcoffset() is not None:
            date = date.astimezone(datetime.timezone.utc)
        return date.date()
    if isinstance(date, datetime.date):
        return date
    if len(date) < _ISO_DATE_LENGTH:
        msg = f"Invalid date {date!r}: it must be in ISO 8601 format, like 2026-08-03"
        raise ValueError(msg)
    return datetime.date.fromisoformat(date[:10])


def _months_around(date: datetime.date) -> list[tuple[int, int]]:
    """Return the ``(year, month)`` before, of, and after ``date``."""
    index = date.year * 12 + date.month - 1
    return [(i // 12, i % 12 + 1) for i in (index - 1, index, index + 1)]


@functools.lru_cache(maxsize=8192)
def _l05_file_dates(
    path: pathlib.Path,
    mtime_ns: int,  # ruff:ignore[ARG001]
    size: int,  # ruff:ignore[ARG001]
) -> frozenset[datetime.date]:
    """
    Return the dates (in UTC) of the records in an L0.5 file.

    This plays the part of the ``unique_dates`` of each raw file in the
    ``sdc_state`` registry in IDL, so that a file is opened only once
    when the L1 files for several dates are made. The modification time
    and size of the file are part of the key of the cache, so that a
    file is read again after it changes.

    Parameters
    ----------
    path : pathlib.Path
        The L0.5 CDF file.
    mtime_ns : int
        The modification time of the file, in nanoseconds.
    size : int
        The size of the file, in bytes.

    Returns
    -------
    frozenset of datetime.date
        The dates of the records, which is empty if the file has no
        ``Epoch`` variable.
    """
    with pycdf.CDF(str(path)) as cdf:
        if "Epoch" not in cdf:
            logger.debug("Skipping %s, which has no Epoch variable", path)
            return frozenset()
        epoch = np.asarray(cdf.raw_var("Epoch")[...])
    return frozenset(_unique_dates(cdf_epoch_tojuldays(epoch)))


def _l05_children(date: datetime.date, l05dir: pathlib.Path) -> list[pathlib.Path]:
    """
    Return the L0.5 files for ``SPC_L1_APIDS`` that have records on a date.

    In IDL, these files are looked up in the ``sdc_state`` registry from
    the ``unique_dates`` and ``l05_children`` of each raw file. Instead,
    the files in ``l05dir/YYYY/MM/APID*/`` are searched. L0.5 files are
    in the directory for the month of their raw file, which can differ
    from the month of their records, so the months before and after
    ``date`` are searched too.

    IDL selects the files for each APID from these files with
    `spp_swp_spc_which_apid`. Here, files for other APIDs are left out
    first, so that they are not opened. The files selected for each
    APID are the same.

    Parameters
    ----------
    date : datetime.date
        The date, in UTC.
    l05dir : pathlib.Path
        The top L0.5 directory, which has ``YYYY/MM/APID*/``
        subdirectories.

    Returns
    -------
    list of pathlib.Path
        The L0.5 CDF files for ``SPC_L1_APIDS`` with at least one record
        on ``date``, sorted.
    """
    paths = sorted(
        path
        for year, month in _months_around(date)
        for path in (l05dir / f"{year:04d}" / f"{month:02d}").glob("APID*/*.cdf")
        if path.is_file()
    )
    candidates = [
        path
        for path, apid in zip(paths, spp_swp_spc_which_apid(paths))
        if apid in SPC_L1_APIDS
    ]
    children = []
    for path in candidates:
        stat = path.stat()
        if date in _l05_file_dates(path, stat.st_mtime_ns, stat.st_size):
            children.append(path)
    logger.debug("L0.5 files with records on %s: %s", date, children)
    return children


def spp_swp_spc_l05_to_l1_date(
    date: datetime.date | str,
    *,
    l05dir: str | os.PathLike[str],
    l1dir: str | os.PathLike[str],
    overwrite: bool = False,
) -> list[pathlib.Path]:
    """
    Make the L1 files for one date from all L0.5 files with data on it.

    For each APID in ``SPC_L1_APIDS`` (351, 353, 354, 35E, and 35F), the
    L0.5 files with records on ``date`` are merged by
    `~pyfaradaycup.l05_to_l1.cdf_merge_to_daily` into
    ``l1dir/YYYY/MM/APID<apid>/spp_swp_spc_APID<apid>L1_YYYYMMDD_v00.cdf``.
    Every L0.5 file with records on the date is used, so the whole day's
    L1 file is rebuilt each time.

    Parameters
    ----------
    date : datetime.date or str
        The date, in UTC, as a date or an ISO 8601 string like
        ``"2026-08-03"``.
    l05dir : path-like
        The top L0.5 directory, which has ``YYYY/MM/APID*/``
        subdirectories.
    l1dir : path-like
        The top L1 directory, where ``YYYY/MM/APID*/`` subdirectories
        are created.
    overwrite : bool, default: False
        Whether to replace L1 files that already exist.

    Returns
    -------
    list of pathlib.Path
        The L1 files that were written.

    Raises
    ------
    NoL05DataError
        If no L0.5 files for any APID in ``SPC_L1_APIDS`` have records
        on ``date``.
    FileExistsError
        If an L1 file exists and ``overwrite`` is `False`.
    ValueError
        If ``date`` is not a valid date.
    """
    date = _parse_date(date)
    l05dir = pathlib.Path(l05dir)
    l1dir = pathlib.Path(l1dir)

    # Instead of the sdc_state registry, search the L0.5 directory
    l05files = _l05_children(date, l05dir)
    apids = spp_swp_spc_which_apid(l05files)
    if not set(apids) & set(SPC_L1_APIDS):
        raise NoL05DataError(date, l05dir)

    outfiles = []
    for apid in SPC_L1_APIDS:
        files_for_apid = [f for f, a in zip(l05files, apids) if a == apid]
        if not files_for_apid:
            continue
        outfiles += cdf_merge_to_daily(
            files_for_apid,
            skeletonfile=data_dir
            / "cdf_skeletons"
            / f"psp_swp_spc_l1_{apid.lower()}_skeleton.cdf",
            outname=f"spp_swp_spc_APID{apid}L1",
            outpath=l1dir / f"{date:%Y}" / f"{date:%m}" / f"APID{apid}",
            outdate=date,
            overwrite=overwrite,
        )
    return outfiles


def spp_swp_spc_l05_to_l1_dates(
    dates: datetime.date | str | Iterable[datetime.date | str],
    *,
    l05dir: str | os.PathLike[str],
    l1dir: str | os.PathLike[str],
    overwrite: bool = False,
) -> list[pathlib.Path]:
    """
    Make the L1 files for each of several dates.

    This calls `spp_swp_spc_l05_to_l1_date` for each date, in order,
    with duplicate dates removed. Dates with no L0.5 data are skipped
    with a warning.

    Parameters
    ----------
    dates : datetime.date, str, or `~collections.abc.Iterable` of datetime.date or str
        The dates, in UTC, as dates or ISO 8601 strings like
        ``"2026-08-03"``. Like in IDL, a single date is treated as a
        list of one date.
    l05dir : path-like
        The top L0.5 directory, which has ``YYYY/MM/APID*/``
        subdirectories.
    l1dir : path-like
        The top L1 directory, where ``YYYY/MM/APID*/`` subdirectories
        are created.
    overwrite : bool, default: False
        Whether to replace L1 files that already exist.

    Returns
    -------
    list of pathlib.Path
        The L1 files that were written, for all of the dates.

    Raises
    ------
    FileExistsError
        If an L1 file exists and ``overwrite`` is `False`.
    ValueError
        If a date is not a valid date.
    """
    if isinstance(dates, (str, datetime.date)):
        dates = [dates]
    unique_dates = sorted({_parse_date(date) for date in dates})
    l1file_array = []
    for date in unique_dates:
        try:
            l1file_array += spp_swp_spc_l05_to_l1_date(
                date, l05dir=l05dir, l1dir=l1dir, overwrite=overwrite
            )
        except NoL05DataError as exc:  # ruff:ignore[PERF203]
            logger.warning("%s; skipping this date", exc)
    return l1file_array
