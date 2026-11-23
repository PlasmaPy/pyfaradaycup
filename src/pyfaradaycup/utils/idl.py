"""
Python equivalents of IDL built-in functions.

These give the same results as the IDL functions of the same names, so
that code ported from IDL can be compared with the original. IDL names
are case-insensitive, so ``CDF_EPOCH_TOJULDAYS`` becomes
`cdf_epoch_tojuldays`.
"""

from __future__ import annotations

__all__ = [
    "cdf_epoch_tojuldays",
    "interpol",
    "julday",
    "label_region",
    "median",
    "median_filter",
    "uniq",
    "value_locate",
]

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


def value_locate(vector: np.ndarray, value: np.ndarray) -> np.ndarray:
    """
    Return the index of the interval of a monotonically increasing
    vector that contains each value.

    This is the same as ``value_locate(vector, value)`` in IDL for a
    monotonically increasing ``vector``: each index ``i`` is such that
    ``vector[i] <= value < vector[i + 1]``. The index is ``-1`` for
    values below ``vector[0]``, and ``len(vector) - 1`` for values at or
    above ``vector[-1]``.

    Parameters
    ----------
    vector : numpy.ndarray
        A one-dimensional, monotonically increasing array.
    value : numpy.ndarray
        The values to locate.

    Returns
    -------
    numpy.ndarray
        The index (of dtype ``intp``) for each value.

    Notes
    -----
    IDL also accepts a monotonically decreasing ``vector``, which is not
    supported here.

    Examples
    --------
    >>> import numpy as np
    >>> value_locate(np.array([10, 20, 30]), np.array([5, 10, 25, 30, 99])).tolist()
    [-1, 0, 1, 2, 2]
    """
    return np.searchsorted(np.asarray(vector), np.asarray(value), side="right") - 1


def label_region(data: np.ndarray) -> np.ndarray:
    """
    Label each run of nonzero elements of a one-dimensional array.

    This is the same as ``label_region(data, /ulong)`` in IDL for a
    one-dimensional array. The runs are numbered ``1, 2, 3, ...`` from
    the start of the array, and zero elements are labeled 0. Like IDL,
    the first and last elements are treated as zero, so callers usually
    pad the array with a zero at each end.

    Parameters
    ----------
    data : numpy.ndarray
        A one-dimensional array.

    Returns
    -------
    numpy.ndarray
        The label (of dtype ``uint32``) of each element.

    Examples
    --------
    >>> import numpy as np
    >>> label_region(np.array([0, 1, 1, 0, 2, 0, 1, 1, 0])).tolist()
    [0, 1, 1, 0, 2, 0, 3, 3, 0]
    >>> label_region(np.array([1, 1, 0, 1, 1])).tolist()
    [0, 1, 0, 2, 0]
    """
    nonzero = np.asarray(data) != 0
    if nonzero.size == 0:
        return np.zeros(0, dtype=np.uint32)
    nonzero[0] = False
    nonzero[-1] = False
    starts = nonzero & ~np.concatenate(([False], nonzero[:-1]))
    return (np.cumsum(starts) * nonzero).astype(np.uint32)


def median(array: np.ndarray) -> np.generic:
    """
    Return the median of an array, like IDL's ``median`` without ``/EVEN``.

    For an even number of elements, IDL returns the larger of the two
    middle values rather than their mean, so the result is always one of
    the elements and keeps their type.

    Parameters
    ----------
    array : numpy.ndarray
        A nonempty array without NaNs.

    Returns
    -------
    numpy.generic
        The median.

    Raises
    ------
    ValueError
        If ``array`` is empty.

    Notes
    -----
    The documentation of IDL's ``median`` does not say whether it keeps
    the type of integer input. Here, it does.

    Examples
    --------
    >>> import numpy as np
    >>> int(median(np.array([4, 1, 3, 2])))
    3
    >>> int(median(np.array([3, 1, 2])))
    2
    """
    values = np.ravel(array)
    if values.size == 0:
        msg = "The median of an empty array is not defined"
        raise ValueError(msg)
    return np.sort(values)[values.size // 2]


def median_filter(array: np.ndarray, width: int) -> np.ndarray:
    """
    Apply a running median to a one-dimensional array, like ``median(array, width)`` in IDL.

    Each element is replaced by the median of the ``width`` elements
    centered on it, ignoring NaNs. For an even number of values that are
    not NaN, the larger of the two middle values is used, as in
    `median`. The ``(width - 1) // 2`` elements at each end are not
    changed, and an element whose neighborhood is all NaN becomes NaN.

    Parameters
    ----------
    array : numpy.ndarray
        A one-dimensional array.
    width : int
        The odd width of the neighborhood.

    Returns
    -------
    numpy.ndarray
        The filtered array, with the type of ``array``.

    Raises
    ------
    ValueError
        If ``width`` is not a positive odd integer.

    Notes
    -----
    The documentation of IDL's ``median`` does not say how it treats the
    ends of the array or NaNs. This behavior reproduces the flow angles
    in an L2 file made by IDL with ``width = 3``, which is the only width
    that has been checked.

    Examples
    --------
    >>> import numpy as np
    >>> median_filter(np.array([5.0, 1.0, 9.0, 2.0, 8.0]), 3).tolist()
    [5.0, 5.0, 2.0, 8.0, 8.0]
    >>> median_filter(np.array([1.0, np.nan, 3.0, 4.0]), 3).tolist()
    [1.0, 3.0, 4.0, 4.0]
    """
    if width < 1 or width % 2 == 0:
        msg = f"The width must be a positive odd integer, not {width}"
        raise ValueError(msg)
    values = np.asarray(array)
    result = values.copy()
    half = (width - 1) // 2
    for i in range(half, values.size - half):
        window = values[i - half : i + half + 1]
        window = np.sort(window[~np.isnan(window)])
        result[i] = window[window.size // 2] if window.size else np.nan
    return result


def interpol(
    v: np.ndarray, x: np.ndarray, u: np.ndarray, *, nan: bool = False
) -> np.ndarray:
    """
    Linearly interpolate ``v(x)`` at ``u``, like ``interpol(v, x, u)`` in IDL.

    This uses the same arithmetic as IDL's ``interpol.pro``::

        s = value_locate(x, u) clipped to [0, len(x) - 2]
        p = (u - x[s]) * (v[s + 1] - v[s]) / (x[s + 1] - x[s]) + v[s]

    so values of ``u`` outside ``x`` are extrapolated from the first or
    last interval. As in IDL, an integer difference that is combined with
    floating-point values takes their type.

    Parameters
    ----------
    v : numpy.ndarray
        The values to interpolate.
    x : numpy.ndarray
        The monotonically increasing abscissas of ``v``.
    u : numpy.ndarray
        The abscissas to interpolate at.
    nan : bool, default: False
        Whether to leave out the points where ``v`` or ``x`` is NaN, like
        IDL's ``/NAN``.

    Returns
    -------
    numpy.ndarray
        The interpolated values.

    Examples
    --------
    >>> import numpy as np
    >>> interpol(
    ...     np.array([0.0, 10.0, 30.0]),
    ...     np.array([0.0, 1.0, 2.0]),
    ...     np.array([0.5, 1.5, 3.0]),
    ... ).tolist()
    [5.0, 20.0, 50.0]
    """
    v = np.asarray(v)
    x = np.asarray(x)
    u = np.asarray(u)
    if nan:
        keep = ~np.isnan(v)
        if np.issubdtype(x.dtype, np.floating):
            keep &= ~np.isnan(x)
        v = v[keep]
        x = x[keep]
    s = np.clip(value_locate(x, u), 0, x.size - 2)
    du = u - x[s]
    dx = x[s + 1] - x[s]
    if np.issubdtype(v.dtype, np.floating):
        if np.issubdtype(du.dtype, np.integer):
            du = du.astype(v.dtype)
        if np.issubdtype(dx.dtype, np.integer):
            dx = dx.astype(v.dtype)
    return du * (v[s + 1] - v[s]) / dx + v[s]
