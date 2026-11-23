"""Port of ``spp_swp_spc_l1_to_l2_date.pro``."""

from __future__ import annotations

__all__ = ["SCIENCE_APIDS", "spp_swp_spc_l1_to_l2_date"]

import datetime
import logging
import pathlib
from typing import TYPE_CHECKING

from pyfaradaycup.l05_to_l1._spp_swp_spc_l05_to_l1 import (
    _parse_date,
    spp_swp_spc_which_apid,
)
from pyfaradaycup.l1_to_l2._spp_swp_spc_apid35x_to_ivt import spp_swp_spc_apid35x_to_ivt
from pyfaradaycup.l1_to_l2._spp_swp_spc_config_and_hsk_lookup import _read_lowercase
from pyfaradaycup.l1_to_l2._spp_swp_spc_ivt_to_spectra import spp_swp_spc_ivt_to_spectra
from pyfaradaycup.l1_to_l2._spp_swp_spc_merge_ivt import spp_swp_spc_merge_ivt
from pyfaradaycup.l1_to_l2._spp_swp_spc_spectra_to_l2cdf import (
    spp_swp_spc_spectra_to_l2cdf,
)
from pyfaradaycup.l1_to_l2.swp_spc_l12l2_35f import convert_one

if TYPE_CHECKING:
    import os
    from collections.abc import Iterable

logger = logging.getLogger(__name__)

HSK_APID = "35F"
"""The APID of the housekeeping L1 files."""

SCIENCE_APIDS = ("351", "353", "354")
"""The APIDs of the science L1 files."""


def _l1_files(date: datetime.date, l1dir: pathlib.Path) -> list[pathlib.Path]:
    """
    Return the L1 files for ``date``, like ``file_search`` in IDL.

    These are ``l1dir/YYYY/MM/APID*/*L1*_YYYYMMDD*.cdf``, sorted
    case-sensitively.
    """
    month_dir = l1dir / f"{date:%Y}" / f"{date:%m}"
    return sorted(month_dir.glob(f"APID*/*L1*_{date:%Y%m%d}*.cdf"), key=str)


def spp_swp_spc_l1_to_l2_date(
    dates: datetime.date | str | Iterable[datetime.date | str],
    *,
    l1dir: str | os.PathLike[str],
    l2dir: str | os.PathLike[str],
    hsk_only: bool = False,
    sci_only: bool = False,
) -> list[pathlib.Path]:
    """
    Make the L2 files for each date from the L1 files.

    For each date, the L1 files in ``l1dir/YYYY/MM/APID*/`` are found.

    1. Each housekeeping file (APID 35F) is converted into an L2
       housekeeping file in ``l2dir/YYYY/MM/`` with
       `~pyfaradaycup.l1_to_l2.swp_spc_l12l2_35f.convert_one`, replacing
       an existing file. This comes first, because the science step reads
       the L2 housekeeping files.
    2. The science files (APIDs 351, 353, and 354) are each converted
       into a current–voltage–time series, which are merged in the order
       of the files, divided into spectra, and written into a new version
       of the L2 science file with ``spp_swp_spc_spectra_to_l2cdf``.

    Parameters
    ----------
    dates : datetime.date, str, or `~collections.abc.Iterable` of datetime.date or str
        The dates, in UTC, as dates or ISO 8601 strings like
        ``"2026-08-03"``. Like in IDL, a single date is treated as a
        list of one date. Unlike IDL, duplicates are removed and the
        dates are sorted.
    l1dir : path-like
        The top L1 directory, which has ``YYYY/MM/APID*/`` subdirectories.
    l2dir : path-like
        The top L2 directory, where ``YYYY/MM/`` subdirectories are made.
        The L2 housekeeping files of each date and the day before are read
        from it.
    hsk_only : bool, default: False
        Whether to make only the L2 housekeeping files.
    sci_only : bool, default: False
        Whether to make only the L2 science files.

    Returns
    -------
    list of pathlib.Path
        The L2 science files that were written, for all of the dates. Like
        IDL, the L2 housekeeping files are not included.

    Raises
    ------
    ValueError
        If a date is not a valid date.

    Notes
    -----
    The IDL function takes the L1 and L2 directories from the
    ``spp_swp_spc_paths`` COMMON block, and spawns the Python script
    ``swp_spc_l12l2_35f.py`` for each housekeeping file. Its ``sdc_state``
    argument is not used, and its ``control`` structure is not supported
    here. A date without L1 files is skipped with a warning, where IDL
    skips it silently. The L2 science files are not split by mode here,
    as in IDL; see `spp_swp_spc_split_l2cdf_by_mode`.
    """
    if isinstance(dates, (str, datetime.date)):
        dates = [dates]
    l1dir = pathlib.Path(l1dir)
    l2dir = pathlib.Path(l2dir)
    new_l2files: list[pathlib.Path] = []
    for date in sorted({_parse_date(date) for date in dates}):
        datafiles = _l1_files(date, l1dir)
        if not datafiles:
            logger.warning("No L1 files in %s are for %s; skipping it", l1dir, date)
            continue
        apids = spp_swp_spc_which_apid(datafiles)

        # Housekeeping first, since the science step reads the L2
        # housekeeping files
        if not sci_only:
            for hskfile in (f for f, apid in zip(datafiles, apids) if apid == HSK_APID):
                convert_one(
                    hskfile, l2dir / f"{date:%Y}" / f"{date:%m}", overwrite=True
                )

        # Science: load each file, convert it into an I-V time series,
        # merge them, and divide them into spectra
        science = [f for f, apid in zip(datafiles, apids) if apid in SCIENCE_APIDS]
        if science and not hsk_only:
            ivt = None
            for datafile in science:
                this = spp_swp_spc_apid35x_to_ivt(
                    _read_lowercase([datafile]), l1dir=l1dir, l2dir=l2dir
                )
                ivt = this if ivt is None else spp_swp_spc_merge_ivt(ivt, this)
            if ivt is None:  # for type checkers; science is not empty
                raise AssertionError
            spectra = spp_swp_spc_ivt_to_spectra(ivt)
            new_l2files.append(spp_swp_spc_spectra_to_l2cdf(spectra, l2dir=l2dir))
    logger.info("Generated the following L2 files: %s", [str(f) for f in new_l2files])
    return new_l2files
