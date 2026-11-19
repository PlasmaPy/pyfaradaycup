"""Tests for `pyfaradaycup.utils._cdf`."""

from __future__ import annotations

import warnings
from pathlib import Path

import pytest
from spacepy import pycdf

from pyfaradaycup.utils._cdf import close_cdf, temporary_path


class _WarningCDF:
    """A stand-in for a CDF whose ``close`` method warns."""

    def __init__(self, message: str) -> None:
        self.message = message
        self.closed = False

    def close(self) -> None:
        self.closed = True
        warnings.warn(self.message, pycdf.CDFWarning, stacklevel=2)


def test_close_cdf_hides_did_not_compress() -> None:
    """Test that the harmless DID_NOT_COMPRESS warning is not shown."""
    cdf = _WarningCDF("DID_NOT_COMPRESS: Did not compress")
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        close_cdf(cdf)  # ty: ignore[invalid-argument-type]
    assert cdf.closed


def test_close_cdf_shows_other_warnings() -> None:
    """Test that other warnings from closing a CDF are still shown."""
    cdf = _WarningCDF("SOME_OTHER_WARNING")
    with pytest.warns(pycdf.CDFWarning, match="SOME_OTHER_WARNING"):
        close_cdf(cdf)  # ty: ignore[invalid-argument-type]
    assert cdf.closed


def test_temporary_path() -> None:
    """
    Test that a temporary path is hidden, next to the final path, ends
    with .cdf, and is different each time.
    """
    path = Path("L05/APID352/0523462910_4_EA_APID352_L1.cdf")
    first = temporary_path(path)
    assert first.parent == path.parent
    assert first.name.startswith(".0523462910_4_EA_APID352_L1.")
    assert first.suffix == ".cdf"
    assert first != temporary_path(path)
