"""Test that boolean parameters in the decommutator are keyword-only."""

import inspect
from collections.abc import Callable
from types import ModuleType

import pytest

from pyfaradaycup.decommutator import (
    ccsds_reader_pipeline,
    main,
    swp_spc_l0_to_l05,
)


def _functions(module: ModuleType) -> list[Callable]:
    return [
        obj
        for _, obj in inspect.getmembers(module, inspect.isfunction)
        if obj.__module__ == module.__name__
    ]


functions = [
    func
    for module in (ccsds_reader_pipeline, main, swp_spc_l0_to_l05)
    for func in _functions(module)
]


@pytest.mark.parametrize("func", functions, ids=lambda func: func.__qualname__)
def test_bool_parameters_are_keyword_only(func: Callable) -> None:
    """Test that parameters annotated as `bool` are keyword-only."""
    signature = inspect.signature(func)
    positional_bools = [
        name
        for name, param in signature.parameters.items()
        if param.annotation in {bool, "bool"} and param.kind is not param.KEYWORD_ONLY
    ]
    assert not positional_bools
