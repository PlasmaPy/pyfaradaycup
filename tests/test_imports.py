"""Test that modules can be imported."""

import importlib

import pytest

from pyfaradaycup.decommutator import (
    DecommutationError,
    DecommutationResult,
    _l0_to_l05,
    l0_to_l05,
)


@pytest.mark.parametrize(
    "package_name",
    [
        "pyfaradaycup",
        "pyfaradaycup.decommutator",
        "pyfaradaycup.decommutator.ccsds_reader_pipeline",
    ],
)
def test_import(package_name: str) -> None:
    """Test that the package, subpackage, and modules can be imported."""
    module = importlib.import_module(package_name)
    assert module is not None


def test_decommutator_exports() -> None:
    """
    Test that the function for converting L0 files, its result, and its
    exception can be imported from the subpackage, and are the ones in
    ``_l0_to_l05``.
    """
    assert l0_to_l05 is _l0_to_l05.l0_to_l05
    assert DecommutationResult is _l0_to_l05.DecommutationResult
    assert DecommutationError is _l0_to_l05.DecommutationError
