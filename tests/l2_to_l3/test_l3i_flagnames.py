"""Test the names of the data quality flags of the L3i files."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from spacepy import pycdf

from pyfaradaycup.l2_to_l3._spp_swp_spc_l3i_flagnames import (
    DEFAULT_FLAGNAMES,
    FLAGNAME_LENGTH,
    N_FLAGS,
    spp_swp_spc_l3i_flagnames,
)
from pyfaradaycup.utils._cdf import ignore_chararray_deprecation

if TYPE_CHECKING:
    from pathlib import Path


def test_flagnames_match_production(l3i_file: Path) -> None:
    """The default names are those in the L3i file made in production."""
    with pycdf.CDF(str(l3i_file)) as cdf, ignore_chararray_deprecation():
        expected = [str(name) for name in cdf["DQF_flagnames"][...]]
    assert spp_swp_spc_l3i_flagnames() == expected


def test_flagnames_default_count() -> None:
    """There are 32 default names."""
    assert len(DEFAULT_FLAGNAMES) == N_FLAGS


def test_flagnames_given() -> None:
    """Given names are padded or cut to 70 characters, and missing names are empty."""
    names = spp_swp_spc_l3i_flagnames(["short", "x" * 80])
    assert len(names) == N_FLAGS
    assert all(len(name) == FLAGNAME_LENGTH for name in names)
    assert names[0] == "short".ljust(FLAGNAME_LENGTH)
    assert names[1] == "x" * FLAGNAME_LENGTH
    assert names[2] == " " * FLAGNAME_LENGTH


def test_flagnames_too_many() -> None:
    """More than 32 names raise an error, where IDL stops with a subscript error."""
    with pytest.raises(ValueError, match="at most 32"):
        spp_swp_spc_l3i_flagnames(["x"] * (N_FLAGS + 1))
