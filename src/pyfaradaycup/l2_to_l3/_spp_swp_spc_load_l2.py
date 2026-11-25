"""Port of ``spp_swp_spc_load_l2.pro``."""

from __future__ import annotations

__all__ = ["L2Variable", "L2i", "spp_swp_spc_load_l2"]

import dataclasses
import logging
import pathlib
from typing import TYPE_CHECKING, Any

import numpy as np
from spacepy import pycdf

from pyfaradaycup.l05_to_l1._spp_swp_spc_l05_to_l1 import _parse_date

if TYPE_CHECKING:
    import datetime
    import os

logger = logging.getLogger(__name__)


@dataclasses.dataclass(frozen=True)
class L2Variable:
    """
    The values and fill value of a variable of an L2 file.

    This is the part of the structure for each variable from
    ``read_myCDF`` that L3 uses: ``.dat`` and ``.fillval``.
    """

    dat: np.ndarray
    """The raw values, with records along the first axis."""

    fillval: Any
    """The raw ``FILLVAL`` attribute, or `None` if there is none."""


@dataclasses.dataclass(frozen=True)
class L2i:
    """
    The variables of an L2i file, as read by ``spp_swp_spc_load_l2``.

    The variable names are lower case, since IDL tag names are
    case-insensitive.
    """

    file: pathlib.Path
    """The L2i file that was read."""

    variables: dict[str, L2Variable]
    """The variables, by lower-case name."""

    def __getitem__(self, name: str) -> L2Variable:
        """Return the variable called ``name``, in any case."""
        return self.variables[name.lower()]


def _l2i_file(date: datetime.date, l2dir: pathlib.Path) -> pathlib.Path | None:
    """
    Return the L2i file for ``date``, like ``file_search`` in IDL.

    This is the last of ``l2dir/YYYY/MM/*_l2i_*YYYYMMDD*.cdf``, sorted
    case-sensitively, which is the highest version. The pattern does not
    match the ``l2ifa``, ``l2ifs``, or ``l2ical`` files.
    """
    month_dir = l2dir / f"{date:%Y}" / f"{date:%m}"
    files = sorted(month_dir.glob(f"*_l2i_*{date:%Y%m%d}*.cdf"), key=str)
    return files[-1] if files else None


def _read_variables(file: pathlib.Path) -> dict[str, L2Variable]:
    """Read every variable of a CDF file, like ``read_myCDF(..., /all)``."""
    with pycdf.CDF(str(file)) as cdf:
        variables = {}
        for name in cdf:
            raw = cdf.raw_var(name)
            fillval = raw.attrs.get("FILLVAL", None)
            variables[name.lower()] = L2Variable(
                dat=np.asarray(raw[...]), fillval=fillval
            )
    return variables


def spp_swp_spc_load_l2(
    date: datetime.date | str, *, l2dir: str | os.PathLike[str]
) -> L2i | None:
    """
    Read the L2i file for a date.

    Parameters
    ----------
    date : datetime.date or str
        The date, or an ISO 8601 string such as ``"2026-08-03"``. Only
        the date is used from a `datetime.datetime`, after converting it
        to UTC.
    l2dir : path-like
        The L2 directory, with ``YYYY/MM/`` subdirectories. This replaces
        ``l2_path`` from the ``spp_swp_spc_paths`` COMMON block in IDL.

    Returns
    -------
    L2i or None
        The variables of the last ``l2dir/YYYY/MM/*_l2i_*YYYYMMDD*.cdf``
        file, which is the highest version, or `None` if there is no
        such file (where IDL returns ``-1``).
    """
    date = _parse_date(date)
    file = _l2i_file(date, pathlib.Path(l2dir))
    if file is None:
        logger.info("No L2i file for %s in %s", date, l2dir)
        return None
    logger.info("Reading %s", file)
    return L2i(file=file, variables=_read_variables(file))
