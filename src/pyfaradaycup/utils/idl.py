"""
Python equivalents of IDL built-in functions.

These give the same results as the IDL functions of the same names, so
that code ported from IDL can be compared with the original. IDL names
are case-insensitive, so ``CDF_EPOCH_TOJULDAYS`` becomes
`cdf_epoch_tojuldays`. The exception is `fitcurve`, the equivalent of
IDL's ``CURVEFIT``, which is named so that it is not confused with
`scipy.optimize.curve_fit`.
"""

from __future__ import annotations

__all__ = [
    "FitCurveResult",
    "cdf_epoch_tojuldays",
    "fitcurve",
    "interpol",
    "interpolate",
    "julday",
    "label_region",
    "median",
    "median_filter",
    "trisol",
    "uniq",
    "value_locate",
]

import dataclasses
import itertools

# Callable is imported at run time so that Sphinx can evaluate the
# annotations of fitcurve, and link their types
from collections.abc import Callable  # ruff:ignore[TC003]
from typing import TYPE_CHECKING, Any

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


def trisol(
    a: np.ndarray, b: np.ndarray, c: np.ndarray, r: np.ndarray, *, double: bool = False
) -> np.ndarray:
    """
    Solve a tridiagonal system of linear equations, like ``TRISOL`` in IDL.

    The equations are ``a[i] * u[i - 1] + b[i] * u[i] + c[i] * u[i + 1]
    = r[i]``, where ``a[0]`` and ``c[-1]`` are not used. NV5 documents
    ``TRISOL`` as based on ``tridag`` of section 2.4 of *Numerical
    Recipes*, so this uses the same algorithm, which is Gaussian
    elimination without pivoting (the Thomas algorithm).

    Parameters
    ----------
    a : numpy.ndarray
        The subdiagonal, of length ``n``; ``a[0]`` is not used.
    b : numpy.ndarray
        The diagonal, of length ``n``.
    c : numpy.ndarray
        The superdiagonal, of length ``n``; ``c[-1]`` is not used.
    r : numpy.ndarray
        The right-hand side, of length ``n``.
    double : bool, default: False
        Whether to compute in double precision, like IDL's ``/DOUBLE``.
        Otherwise, the computation is in double precision only if any
        input is double precision, and is in single precision if not.

    Returns
    -------
    numpy.ndarray
        The solution ``u``.

    Raises
    ------
    ValueError
        If the inputs do not all have the same length.

    See Also
    --------
    scipy.linalg.solve_banded : Solve a banded system, with ``(l, u) =
        (1, 1)`` for a tridiagonal one. It uses LAPACK with partial
        pivoting, so it can differ from `trisol` in the last bits, and
        it raises an error for a singular matrix.

    Notes
    -----
    As there is no pivoting, a zero pivot gives infinite or NaN values,
    rather than an error.

    Examples
    --------
    >>> import numpy as np
    >>> u = trisol(
    ...     np.array([0.0, 1.0, 1.0]),
    ...     np.array([2.0, 2.0, 2.0]),
    ...     np.array([1.0, 1.0, 0.0]),
    ...     np.array([3.0, 4.0, 3.0]),
    ... )
    >>> np.round(u, 12).tolist()
    [1.0, 1.0, 1.0]
    """
    arrays = [np.asarray(value) for value in (a, b, c, r)]
    n = arrays[1].size
    if any(array.size != n for array in arrays):
        msg = "The arguments of trisol must all have the same length"
        raise ValueError(msg)
    if double or any(array.dtype == np.float64 for array in arrays):
        dtype = np.dtype(np.float64)
    else:
        dtype = np.dtype(np.float32)
    a, b, c, r = (array.astype(dtype).ravel() for array in arrays)
    u = np.empty(n, dtype=dtype)
    gam = np.empty(n, dtype=dtype)
    with np.errstate(divide="ignore", invalid="ignore"):
        bet = b[0]
        u[0] = r[0] / bet
        for j in range(1, n):
            gam[j] = c[j - 1] / bet
            bet = b[j] - a[j] * gam[j]
            u[j] = (r[j] - a[j] * u[j - 1]) / bet
        for j in range(n - 2, -1, -1):
            u[j] -= gam[j + 1] * u[j + 1]
    return u


def _interpolation_weights(
    coordinate: np.ndarray, size: int, dtype: np.dtype
) -> tuple[np.ndarray, np.ndarray]:
    """
    Return the lower index and the fraction toward the upper index for
    each coordinate, after clamping the coordinates to ``[0, size - 1]``.
    """
    coordinate = np.clip(np.asarray(coordinate, dtype=dtype), 0, size - 1)
    # NaN subscripts get index 0 here, and a NaN fraction, so the result is NaN
    index = np.minimum(np.floor(np.nan_to_num(coordinate)).astype(np.intp), size - 2)
    return index, coordinate - index.astype(dtype)


def interpolate(
    p: np.ndarray, x: np.ndarray, y: np.ndarray | None = None
) -> np.ndarray:
    """
    Interpolate an array linearly at fractional subscripts, like
    ``INTERPOLATE`` in IDL.

    For a two-dimensional ``p``, this is bilinear interpolation at the
    points ``(x[k], y[k])``, like ``interpolate(p, x, y)`` without
    ``/GRID``. As in IDL without ``MISSING``, subscripts outside the
    array are moved to its nearest edge.

    Parameters
    ----------
    p : numpy.ndarray
        A one- or two-dimensional array, with IDL's order of dimensions,
        so that ``p[i, j]`` here is ``p[i, j]`` in IDL.
    x : numpy.ndarray
        The fractional subscripts along the first dimension.
    y : numpy.ndarray, optional
        The fractional subscripts along the second dimension, of the same
        shape as ``x``, if ``p`` is two-dimensional.

    Returns
    -------
    numpy.ndarray
        The interpolated values, with the shape of ``x``. They are single
        precision unless ``p`` is double precision.

    Raises
    ------
    ValueError
        If ``p`` is not one- or two-dimensional, if ``y`` is not given for
        a two-dimensional ``p`` or is given for a one-dimensional one, or
        if a dimension of ``p`` has fewer than 2 elements.

    See Also
    --------
    scipy.ndimage.map_coordinates : With ``order=1`` and
        ``mode="nearest"``, the same interpolation, computed in double
        precision.

    Notes
    -----
    A NaN subscript gives NaN, which NV5 does not document for IDL.

    IDL's ``/GRID``, ``CUBIC``, and ``MISSING`` are not ported. The order
    in which IDL does the arithmetic is not documented, so results in
    single precision can differ from IDL's in the last bit.

    Examples
    --------
    >>> import numpy as np
    >>> p = np.array([[0.0, 1.0], [2.0, 3.0]])
    >>> interpolate(p, np.array([0.5, 2.0]), np.array([0.5, -1.0])).tolist()
    [1.5, 2.0]
    """
    p = np.asarray(p)
    dtype = p.dtype if p.dtype == np.float64 else np.dtype(np.float32)
    if p.ndim not in {1, 2} or (y is None) != (p.ndim == 1):
        msg = "interpolate needs a 1-D array with x, or a 2-D array with x and y"
        raise ValueError(msg)
    if min(p.shape) < 2:  # ruff:ignore[PLR2004]
        msg = "Each dimension of the array must have at least 2 elements"
        raise ValueError(msg)
    p = p.astype(dtype)
    one = dtype.type(1)
    i, fx = _interpolation_weights(x, p.shape[0], dtype)
    if y is None:
        return (one - fx) * p[i] + fx * p[i + 1]
    j, fy = _interpolation_weights(y, p.shape[1], dtype)
    return (one - fy) * ((one - fx) * p[i, j] + fx * p[i + 1, j]) + fy * (
        (one - fx) * p[i, j + 1] + fx * p[i + 1, j + 1]
    )


@dataclasses.dataclass(frozen=True)
class FitCurveResult:
    """The results of `fitcurve`, which IDL's ``CURVEFIT`` returns in its arguments."""

    yfit: np.ndarray
    """The fitted function at ``x``, which is what ``CURVEFIT`` returns."""

    a: np.ndarray
    """The fitted parameters, which ``CURVEFIT`` returns in ``A``."""

    sigma: np.ndarray
    """The standard deviations of the parameters (``SIGMA``)."""

    chisq: float
    """The reduced chi-squared (``CHISQ``)."""

    iter: int
    """The number of iterations (``ITER``)."""

    status: int
    """
    ``0`` if the fit converged, ``1`` if chi-squared increased without
    bound, and ``2`` if the fit did not converge within ``itmax``
    iterations (``STATUS``).
    """

    yerror: float
    """The standard error between ``yfit`` and ``y`` (``YERROR``)."""


@dataclasses.dataclass(frozen=True)
class _CurveFit:
    """The data and settings of a fit with `fitcurve`, and its steps."""

    x: Any
    y: np.ndarray
    w: np.ndarray
    function: Callable[..., Any]
    noderivative: bool
    iparam: np.ndarray
    nfree: int
    dtype: np.dtype

    def evaluate(self, a: np.ndarray) -> np.ndarray:
        """Return the function at ``x`` for the parameters ``a``."""
        f = self.function(self.x, a)
        if not self.noderivative:
            f = f[0]
        return self._check(np.asarray(f))

    def _check(self, f: np.ndarray) -> np.ndarray:
        """Check that ``f`` has one value for each value of ``y``."""
        if f.size != self.y.size:
            msg = f"The function returned {f.size} values, but y has {self.y.size}"
            raise ValueError(msg)
        return f.ravel()

    def chisq(self, yfit: np.ndarray) -> Any:  # ruff:ignore[ANN401]
        """Return the reduced chi-squared of ``yfit``."""
        return np.sum(self.w * (self.y - yfit) ** 2) / self.nfree

    def curvature(self, a: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Return the function at ``a``, the curvature matrix ``alpha``, and
        the gradient vector ``beta`` of the fitted parameters.
        """
        pder = np.zeros((self.y.size, a.size), dtype=self.dtype)
        if self.noderivative:
            yfit = self.evaluate(a)
            eps = np.sqrt(np.finfo(self.dtype).eps)
            # forward differences
            for term in range(a.size):
                p = a.copy()
                inc = eps * abs(p[term])
                if inc == 0:
                    inc = eps
                p[term] = p[term] + inc
                pder[:, term] = (self.evaluate(p) - yfit) / inc
        else:
            f, derivatives = self.function(self.x, a)
            yfit = self._check(np.asarray(f))
            pder = np.asarray(derivatives)
            if pder.shape != (self.y.size, a.size):
                msg = (
                    f"The partial derivatives must have shape {(self.y.size, a.size)}, "
                    f"not {pder.shape}"
                )
                raise ValueError(msg)
        free = pder[:, self.iparam]
        beta = ((self.y - yfit) * self.w) @ free
        alpha = free.T @ (self.w[:, np.newaxis] * free)
        return yfit, alpha, beta

    def step(
        self,
        a: np.ndarray,
        alpha: np.ndarray,
        beta: np.ndarray,
        chisq1: Any,  # ruff:ignore[ANN401]
        flambda: Any,  # ruff:ignore[ANN401]
    ) -> tuple[np.ndarray, np.ndarray, Any, np.ndarray, Any] | None:
        """
        Increase the damping ``flambda`` until a step lowers chi-squared.

        Returns
        -------
        tuple or None
            The new parameters, function, chi-squared, standard deviations
            of the fitted parameters, and damping, or `None` if the step is
            rejected because chi-squared is not finite, or is not lower
            after 31 tries.
        """
        alpha_diag = np.diag(alpha)
        c = np.sqrt(alpha_diag)
        c = np.outer(c, c)
        for lambda_count in itertools.count(1):
            array = alpha / c
            np.fill_diagonal(array, np.diag(array) * (1.0 + flambda))
            array = 1.0 / array if array.size == 1 else np.linalg.inv(array)
            b = a.copy()
            b[self.iparam] = a[self.iparam] + (array / c) @ beta
            yfit = self.evaluate(b)
            chisq = self.chisq(yfit)
            sigma = np.sqrt(np.diag(array) / alpha_diag)
            if not np.isfinite(chisq) or (
                lambda_count > 30 and chisq >= chisq1  # ruff:ignore[PLR2004]
            ):
                return None
            flambda = flambda * self.dtype.type(10)
            if chisq <= chisq1:
                return b, yfit, chisq, sigma, flambda / self.dtype.type(100)
        raise AssertionError  # pragma: no cover


def fitcurve(  # ruff:ignore[PLR0913]
    x: Any,  # ruff:ignore[ANN401]
    y: np.ndarray,
    weights: np.ndarray | None,
    a: np.ndarray,
    function: Callable[..., Any],
    *,
    fita: np.ndarray | None = None,
    itmax: int = 20,
    tol: float | None = None,
    noderivative: bool = False,
    double: bool | None = None,
) -> FitCurveResult:
    """
    Fit a nonlinear function by least squares, like ``CURVEFIT`` in IDL.

    This is the gradient-expansion (Levenberg–Marquardt) algorithm of
    ``CURFIT`` in Bevington, *Data Reduction and Error Analysis for the
    Physical Sciences*, which IDL's ``curvefit.pro`` is adapted from,
    with the same steps, defaults, and results as ``curvefit.pro``.

    Parameters
    ----------
    x : object
        The independent variable, which is only passed to ``function``.
    y : numpy.ndarray
        The values to fit.
    weights : numpy.ndarray or None
        The weight of each value, such as ``1 / sigma**2`` for Gaussian
        errors ``sigma``, or `None` for no weighting. Without weighting,
        ``sigma`` of the result is multiplied by ``sqrt(chisq)``.
    a : numpy.ndarray
        The initial parameters. The computation is in double precision
        if they are, and in single precision otherwise.
    function : callable
        The function to fit, called as ``function(x, a)``. It returns the
        values at ``x`` if ``noderivative`` is true, and otherwise a tuple
        of those and the partial derivatives, of shape ``(len(y),
        len(a))``. This replaces the procedure given by IDL's
        ``FUNCTION_NAME``.
    fita : numpy.ndarray, optional
        ``0`` for each parameter to keep fixed, and nonzero for each one
        to fit. Defaults to fitting every parameter.
    itmax : int, default: 20
        The maximum number of iterations.
    tol : float, optional
        The fit has converged when the relative decrease in chi-squared
        in an iteration is at most ``tol``. Defaults to ``1e-3``.
    noderivative : bool, default: False
        Whether to estimate the partial derivatives by forward
        differences, rather than from ``function``, like IDL's
        ``/NODERIVATIVE``.
    double : bool, optional
        Whether to compute in double precision. Defaults to whether ``a``
        is double precision.

    Returns
    -------
    FitCurveResult
        The fitted function, the parameters and their standard
        deviations, the reduced chi-squared, the number of iterations,
        the status, and the standard error.

    Raises
    ------
    ValueError
        If no parameter is fitted, if there are not more values than
        fitted parameters, or if ``function`` returns arrays of the wrong
        size.
    numpy.linalg.LinAlgError
        If the curvature matrix is singular. IDL's ``INVERT`` prints a
        message and returns a result instead.

    See Also
    --------
    scipy.optimize.curve_fit, scipy.optimize.least_squares : These use
        MINPACK's Levenberg–Marquardt algorithm (with ``method="lm"``),
        which has a different damping schedule and convergence test, so
        their parameters differ from those of `fitcurve` by up to about
        the tolerance, and their uncertainties are computed differently.

    Notes
    -----
    These behaviors of ``curvefit.pro`` are reproduced:

    - The partial derivatives are estimated with a step of
      ``sqrt(eps) * abs(a[k])``, or ``sqrt(eps)`` if ``a[k]`` is 0, where
      ``eps`` is the machine precision of the computation.
    - When the fit converges, or reaches ``itmax`` iterations,
      ``sigma`` is computed from the inverse of the curvature matrix
      with the damped diagonal of the last step, not from the undamped
      matrix.
    - When chi-squared is not finite, or still not lower after 31 tries
      of the damping, the step is rejected, the parameters of the
      previous iteration are kept, and the status is 1.
    - When chi-squared is below ``sum(abs(y)) / 1e7`` before a step, the
      fit stops without changing the parameters, and ``iter`` is one less
      than the iteration it stopped in, so 0 if the initial parameters
      already fit.
    - When the fit does not converge, ``iter`` is ``itmax + 1``, which is
      the value of IDL's loop variable after the loop.

    Floating-point errors, such as division by zero, are ignored, as IDL
    continues after them.

    Examples
    --------
    >>> import numpy as np
    >>> x = np.arange(10.0)
    >>> result = fitcurve(
    ...     x,
    ...     3.0 * x + 1.0,
    ...     None,
    ...     np.array([1.0, 0.0]),
    ...     lambda x, a: a[0] * x + a[1],
    ...     noderivative=True,
    ... )
    >>> np.round(result.a, 3).tolist(), result.status
    ([3.0, 1.0], 0)
    """
    if double is None:
        double = np.asarray(a).dtype == np.float64
    dtype = np.dtype(np.float64 if double else np.float32)
    a = np.array(a, dtype=dtype).ravel()
    y = np.asarray(y).ravel()
    tolerance = dtype.type(1e-3 if tol is None else tol)

    if fita is None or len(fita) != a.size:
        fita = np.ones(a.size, dtype=int)
    iparam = np.flatnonzero(np.asarray(fita))
    if iparam.size == 0:
        msg = "fita must have at least one parameter to fit"
        raise ValueError(msg)
    nfree = y.size - iparam.size
    if nfree <= 0:
        msg = "There must be more values in y than parameters to fit"
        raise ValueError(msg)

    fit = _CurveFit(
        x=x,
        y=y,
        w=np.ones(y.size, dtype=np.float32) if weights is None else np.ravel(weights),
        function=function,
        noderivative=noderivative,
        iparam=iparam,
        nfree=nfree,
        dtype=dtype,
    )
    flambda = dtype.type(0.001)
    sigma = np.zeros(a.size, dtype=dtype)
    status = 2
    iteration = itmax + 1
    with np.errstate(all="ignore"):
        for i in range(1, itmax + 1):
            yfit, alpha, beta = fit.curvature(a)
            sigma[iparam] = np.sqrt(1.0 / np.diag(alpha))
            chisq1 = fit.chisq(yfit)
            chisq = chisq1
            if chisq1 < np.sum(np.abs(y)) / 1e7 / nfree:
                # the parameters already fit
                status, iteration = 0, i - 1
                break
            step = fit.step(a, alpha, beta, chisq1, flambda)
            if step is None:
                status, iteration = 1, i
                break
            b, yfit, chisq, sigma[iparam], flambda = step
            a[iparam] = b[iparam]
            if (chisq1 - chisq) / chisq1 <= tolerance:
                status, iteration = 0, i
                break
        if weights is None:
            sigma = sigma * np.sqrt(chisq)
        var = np.sum((yfit - y) ** 2) / nfree if y.size > a.size else 0.0
        yerror = float(np.sqrt(var))
    return FitCurveResult(
        yfit=yfit,
        a=a,
        sigma=sigma,
        chisq=float(chisq),
        iter=iteration,
        status=status,
        yerror=yerror,
    )
