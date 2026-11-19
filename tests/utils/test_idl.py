"""Test the Python equivalents of IDL built-in functions."""

from __future__ import annotations

import datetime
from typing import TYPE_CHECKING

import numpy as np
import pytest

from pyfaradaycup.utils.idl import cdf_epoch_tojuldays, julday, uniq

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
