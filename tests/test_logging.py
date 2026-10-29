"""Tests of how pyfaradaycup sets up logging."""

import importlib
import logging

import pytest

import pyfaradaycup


def test_package_logger_has_only_null_handler() -> None:
    """Test that importing pyfaradaycup adds only a NullHandler."""
    handlers = logging.getLogger(pyfaradaycup.__name__).handlers
    assert len(handlers) == 1
    assert isinstance(handlers[0], logging.NullHandler)


@pytest.mark.parametrize(
    "module_name",
    [
        "pyfaradaycup.decommutator.ccsds_reader_pipeline",
        "pyfaradaycup.decommutator.main",
        "pyfaradaycup.decommutator.swp_spc_l0_to_l05",
    ],
)
def test_module_logger(module_name: str) -> None:
    """Test that each module has a logger named after it with no handlers."""
    module = importlib.import_module(module_name)
    assert module.logger is logging.getLogger(module_name)
    assert not module.logger.handlers
    assert module.logger.propagate
