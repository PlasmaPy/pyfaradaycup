"""Test the Python equivalents of IDL built-in functions."""

from __future__ import annotations

import datetime
from typing import TYPE_CHECKING

import numpy as np
import pytest

from pyfaradaycup.utils.idl import (
    cdf_epoch_tojuldays,
    interpol,
    julday,
    label_region,
    median,
    median_filter,
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
