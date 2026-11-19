"""
Python equivalents of IDL built-in functions.

These give the same results as the IDL functions of the same names, so
that code ported from IDL can be compared with the original. IDL names
are case-insensitive, so ``CDF_EPOCH_TOJULDAYS`` becomes
`cdf_epoch_tojuldays`.
"""

from __future__ import annotations

__all__ = ["cdf_epoch_tojuldays", "julday", "uniq"]

from typing import TYPE_CHECKING

import numpy as np
from spacepy import pycdf

if TYPE_CHECKING:
    import datetime

_JD_OF_CDF_EPOCH_ZERO = 1721059.5
"""
The Julian day of 0000-01-01T00:00:00, which is where ``CDF_EPOCH``
(milliseconds since that time) is zero.
"""

_JD_OF_ORDINAL_ZERO = 1721424.5
"""
The Julian day of midnight on the day before 0001-01-01, which is day
1 of `datetime.date.toordinal`.
"""

_MS_PER_DAY = 86_400_000.0


def julday(date: datetime.date) -> float:
    """
    Return the Julian day of midnight at the start of ``date``.

    This is the same as ``julday(month, day, year, 0, 0, 0)`` in IDL.

    Parameters
    ----------
    date : datetime.date
        A calendar date in the proleptic Gregorian calendar.

    Returns
    -------
    float
        The Julian day, which ends in ``.5`` because Julian days start
        at noon.

    Examples
    --------
    >>> import datetime
    >>> julday(datetime.date(2000, 1, 1))
    2451544.5
    """
    return date.toordinal() + _JD_OF_ORDINAL_ZERO


def cdf_epoch_tojuldays(epoch: np.ndarray) -> np.ndarray:
    """
    Convert ``CDF_TIME_TT2000`` values to Julian days in UTC.

    This replaces the IDL built-in function ``CDF_EPOCH_TOJULDAYS``.
    The times are first converted to ``CDF_EPOCH`` (milliseconds since
    0000-01-01 in UTC, without leap seconds) with the CDF library.

    Parameters
    ----------
    epoch : numpy.ndarray
        Nanoseconds since J2000, including leap seconds, as stored in a
        ``CDF_TIME_TT2000`` variable. The values are converted to
        ``int64``.

    Returns
    -------
    numpy.ndarray
        The Julian day of each time, as ``float64``. Near the present,
        consecutive ``float64`` values differ by about 40 µs.

    Notes
    -----
    The documentation of ``CDF_EPOCH_TOJULDAYS`` does not say how it
    handles leap seconds or exactly how it calculates the result, so
    the result may differ from IDL in the last bits. The CDF library
    puts times during a leap second, like 2016-12-31T23:59:60.5, in the
    first second of the next day.
    """
    cdf_epoch = pycdf.lib.v_tt2000_to_epoch(np.asarray(epoch, dtype=np.int64))
    return np.asarray(cdf_epoch, dtype=np.float64) / _MS_PER_DAY + _JD_OF_CDF_EPOCH_ZERO


def uniq(values: np.ndarray) -> np.ndarray:
    """
    Return the index of the last element of each run of equal values.

    This is the same as ``uniq(values)`` in IDL. For sorted values,
    the result selects one of each value.

    Parameters
    ----------
    values : numpy.ndarray
        A one-dimensional array, which is usually sorted.

    Returns
    -------
    numpy.ndarray
        The indices (of dtype ``intp``) of the last element of each run
        of equal values.

    Examples
    --------
    >>> import numpy as np
    >>> uniq(np.array([1, 1, 2, 2, 2, 3])).tolist()
    [1, 4, 5]
    """
    values = np.asarray(values)
    if values.size == 0:
        return np.array([], dtype=np.intp)
    is_last = np.append(values[1:] != values[:-1], True)
    return np.flatnonzero(is_last)
