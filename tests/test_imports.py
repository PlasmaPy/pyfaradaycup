"""Test that modules can be imported."""

import importlib

import pytest


@pytest.mark.parametrize(
    "package_name",
    [
        "pyfaradaycup",
        "pyfaradaycup.utils",
        "pyfaradaycup.pipeline",
        "pyfaradaycup.pipeline.ccsds_reader_pipeline",
    ],
)
def test_import(package_name: str) -> None:
    """Test that the package, subpackage, and modules can be imported."""
    module = importlib.import_module(package_name)
    assert module is not None
