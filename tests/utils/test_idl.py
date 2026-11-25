"""Test the Python equivalents of IDL built-in functions."""

from __future__ import annotations

import datetime
from typing import TYPE_CHECKING

import numpy as np
import pytest
import scipy.linalg
import scipy.ndimage
import scipy.optimize

from pyfaradaycup.utils.idl import (
    cdf_epoch_tojuldays,
    fitcurve,
    interpol,
    interpolate,
    julday,
    label_region,
    median,
    median_filter,
    trisol,
    uniq,
    value_locate,
)

if TYPE_CHECKING:
    from collections.abc import Callable


def _julian_day_number(year: int, month: int, day: int) -> int:
    """
    Return the Julian day number at noon on a Gregorian date.

    This uses the algorithm of Fliegel & Van Flandern (1968),
    Communications of the ACM, 11, 657, to check `julday` independently.
    """
    # Integer division in the algorithm truncates toward zero
    a = int((month - 14) / 12)
    return (
        (1461 * (year + 4800 + a)) // 4
        + int((367 * (month - 2 - 12 * a)) / 12)
        - (3 * ((year + 4900 + a) // 100)) // 4
        + day
        - 32075
    )


@pytest.mark.parametrize(
    "date",
    [
        datetime.date(2000, 1, 1),
        datetime.date(2016, 12, 31),
        datetime.date(2024, 2, 29),
        datetime.date(2026, 8, 3),
    ],
)
def testjulday(date: datetime.date) -> None:
    """Test that `julday` is the Julian day of midnight at the start of the date."""
    assert julday(date) == _julian_day_number(date.year, date.month, date.day) - 0.5


def test_cdf_epoch_tojuldays_noon(tt2000: Callable[..., int]) -> None:
    """Test that noon UTC on 2000-01-01 is Julian day 2451545.0."""
    jd = cdf_epoch_tojuldays(np.array([tt2000(2000, 1, 1, 12)]))
    assert jd.dtype == np.float64
    assert jd[0] == 2451545.0  # ruff:ignore[PLR2004]


def test_cdf_epoch_tojuldays_midnight(tt2000: Callable[..., int]) -> None:
    """Test that midnight is exactly the start of the day."""
    date = datetime.date(2026, 8, 3)
    jd = cdf_epoch_tojuldays(
        np.array(
            [
                tt2000(2026, 8, 2, 23, 59, 59, 999000),
                tt2000(2026, 8, 3),
            ]
        )
    )
    assert jd[0] < julday(date)
    assert jd[1] == julday(date)


def test_cdf_epoch_tojuldays_leap_second(tt2000: Callable[..., int]) -> None:
    """
    Test that a time during the leap second at the end of 2016 is put in
    the next day, as the CDF library converts it.
    """
    before = tt2000(2016, 12, 31, 23, 59, 59, 500000)
    during = before + 1_000_000_000  # 2016-12-31T23:59:60.5
    jd = cdf_epoch_tojuldays(np.array([before, during]))
    assert jd[0] < julday(datetime.date(2017, 1, 1)) <= jd[1]


@pytest.mark.parametrize(
    ("values", "expected"),
    [
        ([], []),
        ([5], [0]),
        ([1, 1, 2, 2, 2, 3], [1, 4, 5]),
        ([3.0, 3.0, 3.0], [2]),
        ([1, 2, 1], [0, 1, 2]),
    ],
)
def test_uniq(values: list[float], expected: list[int]) -> None:
    """Test that `uniq` gives the last index of each run, like IDL's uniq."""
    assert uniq(np.array(values)).tolist() == expected


@pytest.mark.parametrize(
    ("vector", "values", "expected"),
    [
        ([10, 20, 30], [5, 10, 15, 20, 29, 30, 99], [-1, 0, 0, 1, 1, 2, 2]),
        ([10], [9, 10, 11], [-1, 0, 0]),
        ([1.5, 2.5], [2.0], [0]),
    ],
)
def test_value_locate(
    vector: list[float], values: list[float], expected: list[int]
) -> None:
    """
    Test that `value_locate` gives -1 below the first element and
    len(vector) - 1 at or above the last, like IDL.
    """
    assert value_locate(np.array(vector), np.array(values)).tolist() == expected


@pytest.mark.parametrize(
    ("data", "expected"),
    [
        ([], []),
        ([1], [0]),
        ([0, 1, 1, 0, 1, 0], [0, 1, 1, 0, 2, 0]),
        # Any nonzero value is part of a region
        ([0, 1, 2, 3, 0, 5, 0], [0, 1, 1, 1, 0, 2, 0]),
        # The first and last elements are treated as zero
        ([1, 1, 0, 1, 1], [0, 1, 0, 2, 0]),
    ],
)
def test_label_region(data: list[int], expected: list[int]) -> None:
    """Test that `label_region` numbers runs of nonzero elements, like IDL."""
    labels = label_region(np.array(data))
    assert labels.dtype == np.uint32
    assert labels.tolist() == expected


@pytest.mark.parametrize(
    ("values", "expected"),
    [
        ([3], 3),
        ([3, 1, 2], 2),
        ([4, 1, 3, 2], 3),  # the larger of the two middle values
        ([1.5, 0.5], 1.5),
    ],
)
def test_median(values: list[float], expected: float) -> None:
    """Test that `median` gives the upper middle value of an even number of elements."""
    assert median(np.array(values)) == expected


def test_median_keeps_type() -> None:
    """Test that `median` returns one of the elements, with their type."""
    assert median(np.array([7, 9], dtype=np.uint8)).dtype == np.uint8


def test_median_empty() -> None:
    """Test that the median of an empty array is an error."""
    with pytest.raises(ValueError, match="empty"):
        median(np.array([]))


@pytest.mark.parametrize(
    ("values", "expected"),
    [
        ([5.0, 1.0, 9.0, 2.0, 8.0], [5.0, 5.0, 2.0, 8.0, 8.0]),
        # NaNs are ignored, and the larger middle value of two is used
        ([1.0, np.nan, 3.0, 4.0], [1.0, 3.0, 4.0, 4.0]),
        ([np.nan, np.nan, np.nan], [np.nan, np.nan, np.nan]),
        ([2.0], [2.0]),
    ],
)
def test_median_filter(values: list[float], expected: list[float]) -> None:
    """Test the running median of width 3, which leaves the ends unchanged."""
    np.testing.assert_array_equal(median_filter(np.array(values), 3), expected)


def test_median_filter_width() -> None:
    """Test a running median of width 5, and that the width must be odd."""
    values = np.array([9.0, 1.0, 5.0, 2.0, 8.0, 3.0])
    assert median_filter(values, 5).tolist() == [9.0, 1.0, 5.0, 3.0, 8.0, 3.0]
    with pytest.raises(ValueError, match="odd"):
        median_filter(values, 2)


def test_interpol() -> None:
    """Test linear interpolation and extrapolation from the end intervals."""
    v = np.array([0.0, 10.0, 30.0])
    x = np.array([0.0, 1.0, 2.0])
    result = interpol(v, x, np.array([-1.0, 0.0, 0.25, 1.5, 2.0, 3.0]))
    np.testing.assert_array_equal(result, [-10.0, 0.0, 2.5, 20.0, 30.0, 50.0])


def test_interpol_types_and_nan() -> None:
    """
    Test that integer abscissas give the type of the values, as in IDL,
    and that NaN values are left out with nan=True.
    """
    v = np.array([1.0, np.nan, 3.0], dtype=np.float32)
    x = np.array([0, 10, 20], dtype=np.int64)
    result = interpol(v, x, np.array([5, 10]), nan=True)
    assert result.dtype == np.float32
    np.testing.assert_array_equal(result, [1.5, 2.0])


def _tridiagonal_system(n: int, seed: int = 0) -> tuple[np.ndarray, ...]:
    """Return a random, diagonally dominant tridiagonal system of size ``n``."""
    rng = np.random.default_rng(seed)
    a = rng.uniform(-1, 1, n)
    c = rng.uniform(-1, 1, n)
    b = 2 + rng.uniform(0, 1, n)
    r = rng.uniform(-10, 10, n)
    return a, b, c, r


def test_trisol_matches_solve_banded() -> None:
    """`trisol` agrees with `scipy.linalg.solve_banded` to rounding."""
    a, b, c, r = _tridiagonal_system(50)
    bands = np.zeros((3, a.size))
    bands[0, 1:] = c[:-1]
    bands[1] = b
    bands[2, :-1] = a[1:]
    expected = scipy.linalg.solve_banded((1, 1), bands, r)
    np.testing.assert_allclose(trisol(a, b, c, r), expected, rtol=1e-13, atol=1e-13)


def test_trisol_ignores_unused_elements() -> None:
    """``a[0]`` and ``c[-1]`` are not part of the matrix."""
    a, b, c, r = _tridiagonal_system(5)
    expected = trisol(a, b, c, r)
    a[0] = c[-1] = 1e30
    np.testing.assert_array_equal(trisol(a, b, c, r), expected)


@pytest.mark.parametrize(
    ("dtype", "double", "expected"),
    [
        (np.float32, False, np.float32),
        (np.float32, True, np.float64),
        (np.float64, False, np.float64),
        (np.int64, False, np.float32),
    ],
)
def test_trisol_type(dtype: type, double: bool, expected: type) -> None:  # ruff:ignore[FBT001]
    """The result is double precision with ``double`` or double precision inputs."""
    a, b, c, r = (np.asarray(x).astype(dtype) for x in _tridiagonal_system(4))
    b = b + 3
    assert trisol(a, b, c, r, double=double).dtype == expected


def test_trisol_mixed_precision() -> None:
    """A double precision input makes the computation double precision."""
    a, b, c, r = _tridiagonal_system(4)
    assert trisol(a.astype(np.float32), b, c, r).dtype == np.float64


def test_trisol_zero_pivot() -> None:
    """A zero pivot gives non-finite values rather than an error, as there is no pivoting."""
    result = trisol(
        np.array([0.0, 1.0]),
        np.array([0.0, 1.0]),
        np.array([1.0, 0.0]),
        np.array([1.0, 1.0]),
    )
    assert not np.all(np.isfinite(result))


def test_trisol_lengths() -> None:
    """The arguments must all have the same length."""
    with pytest.raises(ValueError, match="same length"):
        trisol(np.ones(3), np.ones(3), np.ones(2), np.ones(3))


def test_interpolate_2d_matches_map_coordinates() -> None:
    """Bilinear interpolation, with subscripts moved to the nearest edge."""
    rng = np.random.default_rng(1)
    p = rng.uniform(0, 100, (6, 9))
    x = rng.uniform(-2, 8, 200)
    y = rng.uniform(-2, 11, 200)
    expected = scipy.ndimage.map_coordinates(p, [x, y], order=1, mode="nearest")
    np.testing.assert_allclose(interpolate(p, x, y), expected, rtol=1e-13)


def test_interpolate_1d() -> None:
    """One-dimensional interpolation is like `numpy.interp` on the subscripts."""
    p = np.array([0.0, 10.0, 30.0, 70.0])
    x = np.array([-1.0, 0.0, 0.25, 1.5, 3.0, 4.0])
    expected = np.interp(x, np.arange(p.size), p)
    np.testing.assert_allclose(interpolate(p, x), expected, rtol=1e-15)


def test_interpolate_at_nodes() -> None:
    """Integer subscripts give the elements of the array exactly."""
    p = np.arange(12, dtype=np.float32).reshape(3, 4) ** 1.5
    i, j = np.meshgrid(np.arange(3), np.arange(4), indexing="ij")
    np.testing.assert_array_equal(interpolate(p, i.ravel(), j.ravel()), p.ravel())


@pytest.mark.parametrize(
    ("dtype", "expected"),
    [(np.float32, np.float32), (np.float64, np.float64), (np.int16, np.float32)],
)
def test_interpolate_type(dtype: type, expected: type) -> None:
    """The result is single precision unless the array is double precision."""
    p = np.arange(6).reshape(2, 3).astype(dtype)
    assert interpolate(p, np.array([0.5]), np.array([0.5])).dtype == expected


@pytest.mark.parametrize(
    ("shape", "with_y"),
    [((2, 2), False), ((4,), True), ((2, 2, 2), True), ((1, 4), True)],
)
def test_interpolate_errors(shape: tuple[int, ...], with_y: bool) -> None:  # ruff:ignore[FBT001]
    """Arrays and subscripts that are not supported raise `ValueError`."""
    p = np.zeros(shape)
    x = np.zeros(1)
    with pytest.raises(ValueError, match=r"interpolate|at least 2"):
        interpolate(p, x, x if with_y else None)


def _gfunct(x: np.ndarray, a: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """
    Return ``a[0] * exp(a[1] * x) + a[2]`` and its partial derivatives.

    This is the function of the example in NV5's documentation of
    ``CURVEFIT``.

    As in IDL, the arithmetic is double precision if ``a`` is, which
    NumPy < 2 does not do for a double precision scalar and a single
    precision array.
    """
    x = np.asarray(x, dtype=np.result_type(x, a))
    bx = np.exp(a[1] * x)
    pder = np.stack([bx, a[0] * x * bx, np.ones_like(x)], axis=1)
    return a[0] * bx + a[2], pder


#: The data of the example in NV5's documentation of ``CURVEFIT``.
_X = np.arange(10, dtype=np.float32)
_Y = np.array([12.0, 11.0, 10.2, 9.4, 8.7, 8.1, 7.5, 6.9, 6.5, 6.1], dtype=np.float32)
_WEIGHTS = np.float32(1) / _Y
_GUESS = np.array([10.0, -0.1, 2.0], dtype=np.float32)


def test_fitcurve_nv5_example() -> None:
    """
    `fitcurve` gives the parameters that IDL prints for the example in
    NV5's documentation of ``CURVEFIT``: 9.91120, -0.100883, and 2.07773.
    """
    result = fitcurve(_X, _Y, _WEIGHTS, _GUESS, _gfunct)
    assert result.status == 0
    assert result.a.dtype == np.float32
    # IDL prints single precision values with 6 significant digits
    assert [float(f"{value:.6g}") for value in result.a] == [9.9112, -0.100883, 2.07773]


def test_fitcurve_matches_curve_fit() -> None:
    """
    `scipy.optimize.curve_fit` gives the same parameters to about the
    tolerance, but larger uncertainties, since `fitcurve` computes them
    from the damped curvature matrix of the last step, like IDL.
    """
    result = fitcurve(_X, _Y, _WEIGHTS, _GUESS.astype(np.float64), _gfunct)
    popt, pcov = scipy.optimize.curve_fit(
        lambda x, a, b, c: a * np.exp(b * x) + c,
        _X.astype(np.float64),
        _Y.astype(np.float64),
        p0=_GUESS.astype(np.float64),
        sigma=np.sqrt(_Y.astype(np.float64)),
        absolute_sigma=True,
    )
    np.testing.assert_allclose(result.a, popt, rtol=1e-4)
    sigma = np.sqrt(np.diag(pcov))
    assert np.all(result.sigma < sigma)
    np.testing.assert_allclose(result.sigma, sigma, rtol=0.01)


def test_fitcurve_noderivative() -> None:
    """Forward differences give nearly the same fit as the partial derivatives."""
    exact = fitcurve(_X, _Y, _WEIGHTS, _GUESS.astype(np.float64), _gfunct)
    result = fitcurve(
        _X,
        _Y,
        _WEIGHTS,
        _GUESS.astype(np.float64),
        lambda x, a: _gfunct(x, a)[0],
        noderivative=True,
    )
    assert result.status == 0
    np.testing.assert_allclose(result.a, exact.a, rtol=1e-3)


def test_fitcurve_double() -> None:
    """The computation is double precision with ``double``."""
    result = fitcurve(_X, _Y, _WEIGHTS, _GUESS, _gfunct, double=True)
    assert result.a.dtype == np.float64
    assert result.sigma.dtype == np.float64


def test_fitcurve_no_weighting() -> None:
    """Without weights, the uncertainties are multiplied by ``sqrt(chisq)``."""
    unweighted = fitcurve(_X, _Y, None, _GUESS.astype(np.float64), _gfunct)
    ones = fitcurve(_X, _Y, np.ones(_Y.size), _GUESS.astype(np.float64), _gfunct)
    np.testing.assert_array_equal(unweighted.a, ones.a)
    np.testing.assert_allclose(unweighted.sigma, ones.sigma * np.sqrt(ones.chisq))


def test_fitcurve_fita() -> None:
    """Parameters with ``fita`` of 0 are kept fixed and get no uncertainty."""
    result = fitcurve(
        _X, _Y, _WEIGHTS, _GUESS.astype(np.float64), _gfunct, fita=np.array([1, 1, 0])
    )
    assert result.a[2] == _GUESS[2]
    assert result.sigma[2] == 0
    assert result.status == 0


def test_fitcurve_already_fit() -> None:
    """When the initial parameters fit, they are kept, and ``iter`` is 0."""
    a = np.array([2.0, 0.5])
    x = np.arange(5.0)
    result = fitcurve(
        x, a[0] * x + a[1], None, a, lambda x, a: a[0] * x + a[1], noderivative=True
    )
    np.testing.assert_array_equal(result.a, a)
    assert result.iter == 0
    assert result.status == 0


def test_fitcurve_not_converged() -> None:
    """When the fit does not converge, the status is 2 and ``iter`` is ``itmax + 1``."""
    result = fitcurve(_X, _Y, _WEIGHTS, np.array([1.0, -1.0, 0.0]), _gfunct, itmax=1)
    assert result.status == 2  # ruff:ignore[PLR2004]
    assert result.iter == 2  # ruff:ignore[PLR2004]


def test_fitcurve_chisq_not_finite() -> None:
    """When every step gives NaN, the status is 1 and the parameters are kept."""

    def function(x: np.ndarray, a: np.ndarray) -> np.ndarray:
        return x * a[0] if a[0] == 1 else np.full_like(x, np.nan)

    x = np.arange(1.0, 6.0)
    result = fitcurve(x, 2 * x, None, np.array([1.0]), function, noderivative=True)
    assert result.status == 1
    assert result.iter == 1
    assert result.a.tolist() == [1.0]
    np.testing.assert_array_equal(result.yfit, x)


@pytest.mark.parametrize(
    ("kwargs", "match"),
    [
        ({"fita": np.array([0, 0, 0])}, "at least one parameter"),
        ({"y": _Y[:3]}, "more values"),
    ],
)
def test_fitcurve_errors(kwargs: dict, match: str) -> None:
    """Fits without free parameters or degrees of freedom raise `ValueError`."""
    y = kwargs.pop("y", _Y)
    x = _X[: y.size]
    with pytest.raises(ValueError, match=match):
        fitcurve(x, y, None, _GUESS, _gfunct, **kwargs)


def test_fitcurve_wrong_shapes() -> None:
    """A function that returns arrays of the wrong shape raises `ValueError`."""
    with pytest.raises(ValueError, match="returned 9 values"):
        fitcurve(_X, _Y, None, _GUESS, lambda x, _a: x[1:], noderivative=True)
    with pytest.raises(ValueError, match="partial derivatives must have shape"):
        fitcurve(
            _X, _Y, None, _GUESS, lambda x, a: (_gfunct(x, a)[0], np.zeros((10, 2)))
        )
