"""Port of ``spp_swp_spc_config_and_hsk_lookup.pro``."""

from __future__ import annotations

__all__ = ["ConfigAndHsk", "spp_swp_spc_config_and_hsk_lookup"]

import dataclasses
import datetime
import logging
import pathlib
from typing import TYPE_CHECKING

import numpy as np

from pyfaradaycup.l05_to_l1.cdf_to_survey import _read_mycdf
from pyfaradaycup.utils.idl import cdf_epoch_tojuldays, value_locate

if TYPE_CHECKING:
    import os

logger = logging.getLogger(__name__)

_JDN_OF_ORDINAL_ZERO = 1721425
"""
The Julian day number of the day before 0001-01-01, which is day 1 of
`datetime.date.toordinal`.
"""

_DEFAULT_YEAR_MONTH = ("2018", "08")
"""The year and month of the default files from commissioning."""


@dataclasses.dataclass(frozen=True)
class ConfigAndHsk:
    """
    The last-known scan settings (APID 35E) and housekeeping values
    (APID 35F) at each time.

    This is the structure returned by ``spp_swp_spc_config_and_hsk_lookup``
    in IDL. Each array has one value for each time in ``epoch``.
    """

    epoch: np.ndarray
    sw_spc_doublewidth: np.ndarray
    spc_fawinwidth: np.ndarray
    spc_winwidth: np.ndarray
    sw_spc_fa: np.ndarray
    sw_spc_mode: np.ndarray
    sw_spc_elec: np.ndarray
    sw_spc_peakoffhi: np.ndarray
    sw_spc_peakofflow: np.ndarray
    sw_spc_minvolt: np.ndarray
    sw_spc_maxvolt: np.ndarray
    sw_spc_lvtemp: np.ndarray
    config_files: list[pathlib.Path]
    hsk_files: list[pathlib.Path]


def _lookup_dates(dates: np.ndarray) -> list[datetime.date]:
    """
    Return the days before and the days of ``dates``, in the order IDL
    searches for files.

    IDL breaks each time into a UTC date with ``cdf_tt2000, /BREAK``,
    and makes the list ``[ujd - 1, ujd]`` from the unique Julian day
    numbers ``ujd``: first every day before, and then every day. A date
    can be in the list twice, in which case its file is read twice.
    Times before 0001-01-01, such as fill values, are skipped.
    """
    jd = cdf_epoch_tojuldays(dates)
    jdn = np.floor(jd[np.isfinite(jd)] + 0.5).astype(np.int64)
    ujd = np.unique(jdn)
    ordinals = np.concatenate((ujd - 1, ujd)) - _JDN_OF_ORDINAL_ZERO
    max_ordinal = datetime.date.max.toordinal()
    return [
        datetime.date.fromordinal(int(ordinal))
        for ordinal in ordinals
        if 1 <= ordinal <= max_ordinal
    ]


def _last_match(directory: pathlib.Path, pattern: str) -> pathlib.Path | None:
    """Return the alphabetically last file in ``directory`` that matches ``pattern``."""
    matches = sorted(directory.glob(pattern), key=str)
    return matches[-1] if matches else None


def _read_lowercase(files: list[pathlib.Path]) -> dict[str, np.ndarray]:
    """Read CDF files like ``read_myCDF``, with lower-case variable names."""
    data, _ = _read_mycdf(files)
    return {name.lower(): values for name, values in data.items()}


def _lookup(values: np.ndarray, index: np.ndarray) -> np.ndarray:
    """
    Index ``values`` like IDL, which clips out-of-range subscripts to the bounds.

    `~pyfaradaycup.utils.idl.value_locate` gives ``-1`` for times before
    the first record, which IDL clips to ``0``.
    """
    return values[np.clip(index, 0, values.size - 1)]


def spp_swp_spc_config_and_hsk_lookup(
    dates: np.ndarray,
    *,
    l1dir: str | os.PathLike[str],
    l2dir: str | os.PathLike[str],
) -> ConfigAndHsk:
    """
    Look up the scan settings and housekeeping values at each time.

    For each day of ``dates`` and the day before it, the last APID 35E
    L1 file (scan settings) is read from ``l1dir/YYYY/MM/APID35E*/`` and
    the last L2 housekeeping file (``l2hsk``, APID 35F) is read from
    ``l2dir/YYYY/MM/``. Each time gets the values of the last record at
    or before it, or of the first record if it is before all of them.

    Parameters
    ----------
    dates : numpy.ndarray
        ``CDF_TIME_TT2000`` values.
    l1dir : path-like
        The L1 directory, with ``YYYY/MM/APID*/`` subdirectories.
    l2dir : path-like
        The L2 directory, with ``YYYY/MM/`` subdirectories.

    Returns
    -------
    ConfigAndHsk
        The values at each time, and the files that were read.

    Raises
    ------
    FileNotFoundError
        If there are no files for these days, and no default files from
        2018-08 either.

    Notes
    -----
    Like IDL, if no files are found for these days, the first file from
    2018-08 (commissioning) is used instead, with a warning.
    """
    l1dir = pathlib.Path(l1dir)
    l2dir = pathlib.Path(l2dir)
    dates = np.asarray(dates, dtype=np.int64)
    days = _lookup_dates(dates)

    # (1) get the APID 35E (config) files to cover this time period
    config_files = []
    for day in days:
        match = _last_match(
            l1dir / f"{day:%Y}" / f"{day:%m}", f"APID35E*/*L1*_{day:%Y%m%d}*.cdf"
        )
        if match is not None:
            config_files.append(match)
    if not config_files:
        logger.warning(
            "No APID 35E (config) L1 files were found for %s; using the first "
            "file from commissioning",
            sorted(set(days)),
        )
        matches = sorted(
            (l1dir / _DEFAULT_YEAR_MONTH[0] / _DEFAULT_YEAR_MONTH[1]).glob(
                "APID35E*/*L1*_*.cdf"
            ),
            key=str,
        )
        if not matches:
            msg = f"No APID 35E (config) L1 files were found in {l1dir}"
            raise FileNotFoundError(msg)
        config_files = matches[:1]
    config = _read_lowercase(config_files)
    cfg_lookup = value_locate(config["epoch"], dates)

    # (2) also load the 35F (HSK) L2 files for this time period
    hsk_files = []
    for day in days:
        month_dir = l2dir / f"{day:%Y}" / f"{day:%m}"
        match = _last_match(month_dir, f"*APID35Fl2hsk*_{day:%Y%m%d}*.cdf")
        if match is None:
            match = _last_match(month_dir, f"*l2hsk*_{day:%Y%m%d}*.cdf")
        if match is not None:
            hsk_files.append(match)
    if not hsk_files:
        logger.warning(
            "No L2 housekeeping files were found for %s; using the first "
            "file from commissioning",
            sorted(set(days)),
        )
        matches = sorted(
            (l2dir / _DEFAULT_YEAR_MONTH[0] / _DEFAULT_YEAR_MONTH[1]).glob(
                "*l2hsk*_*.cdf"
            ),
            key=str,
        )
        if not matches:
            msg = f"No L2 housekeeping files were found in {l2dir}"
            raise FileNotFoundError(msg)
        hsk_files = matches[:1]
    hsk = _read_lowercase(hsk_files)
    hsk_lookup = value_locate(hsk["epoch"], dates)

    return ConfigAndHsk(
        epoch=dates,
        sw_spc_doublewidth=_lookup(config["sw_spc_doublewidth"], cfg_lookup),
        spc_fawinwidth=_lookup(config["spc_fawinwidth"], cfg_lookup),
        spc_winwidth=_lookup(config["spc_winwidth"], cfg_lookup),
        sw_spc_fa=_lookup(hsk["sw_spc_fa"], hsk_lookup),
        sw_spc_mode=_lookup(hsk["sw_spc_mode"], hsk_lookup),
        sw_spc_elec=_lookup(hsk["sw_spc_elec"], hsk_lookup),
        sw_spc_peakoffhi=_lookup(config["sw_spc_peakoffhi"], cfg_lookup),
        sw_spc_peakofflow=_lookup(config["sw_spc_peakofflow"], cfg_lookup),
        sw_spc_minvolt=_lookup(hsk["sw_spc_minvolt"], hsk_lookup),
        sw_spc_maxvolt=_lookup(hsk["sw_spc_maxvolt"], hsk_lookup),
        sw_spc_lvtemp=_lookup(hsk["sw_spc_lvtemp"], hsk_lookup),
        config_files=config_files,
        hsk_files=hsk_files,
    )
