"""Fixtures shared by the tests."""

from __future__ import annotations

import warnings
from typing import TYPE_CHECKING, Any

import numpy as np
import pytest
from spacepy import pycdf

if TYPE_CHECKING:
    from collections.abc import Callable


def _value(obj: Any) -> Any:  # ruff:ignore[ANN401]
    """Return a value that compares equal by value, converting ctypes and arrays."""
    if hasattr(obj, "value"):  # ctypes values, like c_long, compare by identity
        return obj.value
    if isinstance(obj, tuple):
        return tuple(_value(item) for item in obj)
    return np.asarray(obj).tolist()


def _cdf_metadata(path: str) -> dict[str, Any]:
    """
    Return the metadata of a CDF file that is lost when it is converted to
    xarray, so that it can be compared between two files.

    The CDF version is not included, because it is the version of the CDF
    library that wrote the file and so differs between environments.
    Variable attributes are read from raw variables so that time values
    keep the full precision of ``CDF_TIME_TT2000``.
    """
    with warnings.catch_warnings(), pycdf.CDF(path) as cdf:
        # spacepy 0.7.0 reads string attribute entries with numpy.char.array,
        # which NumPy 2.5 deprecates.
        warnings.filterwarnings(
            "ignore", "The chararray class is deprecated", DeprecationWarning
        )
        global_attributes = {
            name: [
                (i, _value(attr[i]), attr.type(i))
                for i in range(attr.max_idx() + 1)
                if attr.has_entry(i)
            ]
            for name, attr in cdf.attrs.items()
        }
        variables = {}
        for name in cdf:
            var = cdf.raw_var(name)
            variables[name] = {
                "type": var.type(),
                "nelems": var.nelems(),
                "shape": var.shape,
                "rv": var.rv(),
                "dv": var.dv(),
                "sparse": _value(var.sparse()),
                "pad": _value(var.pad()),
                "compress": _value(var.compress()),
                "attrs": {
                    attr: (_value(var.attrs[attr]), var.attrs.type(attr))
                    for attr in var.attrs
                },
            }
        return {
            "col_major": cdf.col_major(),
            "compress": _value(cdf.compress()),
            "checksum": cdf.checksum(),
            "global_attributes": global_attributes,
            "variables": variables,
        }


@pytest.fixture
def cdf_metadata() -> Callable[[str], dict[str, Any]]:
    """
    Return a function that returns the metadata of a CDF file that is
    lost when it is converted to xarray.
    """
    return _cdf_metadata
