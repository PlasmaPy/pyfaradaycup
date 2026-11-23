"""
Describe CDF skeleton files as text, so that changes to them can be reviewed.

The skeleton CDF files in ``pyfaradaycup/data/cdf_skeletons/`` are
binary, so ``git diff`` cannot show how they change. Each one has a
text description next to it, with the same name but a ``.txt``
extension, and the tests check that the two agree. After changing a
skeleton CDF file, regenerate the descriptions with::

    uv run python -m pyfaradaycup._cdf_description

The description includes what spacepy's public `~spacepy.pycdf` API
reports: the CDF version, majority, compression, and checksum of the
file; the global attributes; and each variable's data type, number of
elements, dimensions and their variances, record variance, sparseness,
compression, pad value, attributes, and any records. Values are written
as stored, so that ``CDF_TIME_TT2000`` values are int64 nanoseconds
rather than `~datetime.datetime` objects, which would lose precision.
It does not include settings that spacepy does not expose publicly,
such as the encoding and blocking factors.

The format is not the skeleton table (``.skt``) format written by the
``skeletontable`` tool in the CDF distribution, because that tool is
not available from Python.
"""

from __future__ import annotations

__all__ = ["describe_cdf", "description_path", "main"]

import json
import pathlib
import sys
import warnings
from typing import TYPE_CHECKING, Any

import numpy as np
from spacepy import pycdf

from pyfaradaycup._paths import data_dir

if TYPE_CHECKING:
    import os
    from collections.abc import Sequence

#: The directory of skeleton CDF files distributed with pyfaradaycup.
skeleton_dir = data_dir / "cdf_skeletons"

_INDENT = "  "

# CDF data types whose values pycdf converts to datetime.datetime objects
# unless the values are read raw.
_TIME_TYPES = frozenset(
    {
        pycdf.const.CDF_EPOCH.value,
        pycdf.const.CDF_EPOCH16.value,
        pycdf.const.CDF_TIME_TT2000.value,
    }
)


def description_path(cdf_path: str | os.PathLike[str]) -> pathlib.Path:
    """
    Return the path of the text description of a CDF file.

    Parameters
    ----------
    cdf_path : path-like
        The CDF file.

    Returns
    -------
    pathlib.Path
        The path with the extension changed to ``.txt``.

    Examples
    --------
    >>> from pyfaradaycup._cdf_description import description_path
    >>> description_path("cdf_skeletons/psp_swp_spc_l1_351_skeleton.cdf").name
    'psp_swp_spc_l1_351_skeleton.txt'
    """
    return pathlib.Path(cdf_path).with_suffix(".txt")


def _format_value(value: Any) -> str:  # noqa: ANN401
    """
    Format a value read from a CDF file as one line of text.

    Strings are written as JSON strings, so that the result is
    unambiguous. Floats are written with the fewest digits that identify
    the value at its own precision, so that a ``CDF_REAL4`` value of
    -1e31 is written as ``-1e+31`` rather than ``-9.999999848243207e+30``.
    Arrays are written as lists.
    """
    if isinstance(value, np.ndarray):
        value = value[()] if value.ndim == 0 else list(value)
    if isinstance(value, bytes):
        value = value.decode("ascii")
    if isinstance(value, str):
        return json.dumps(value)
    if isinstance(value, (list, tuple)):
        return "[" + ", ".join(_format_value(v) for v in value) + "]"
    if isinstance(value, (float, np.floating)) and np.isfinite(value):
        # Take the fewest digits that identify the value at its own
        # precision, and write them like Python's repr. NumPy's str of a
        # float32 depends on the version of NumPy: 1e6 is "1000000.0" with
        # NumPy 1.21 and "1e+06" with NumPy 2.5.
        return repr(float(np.format_float_scientific(value, unique=True)))
    if isinstance(value, (bool, np.bool_, int, np.integer, float, np.floating)):
        return str(value)
    msg = f"Cannot describe a value of type {type(value).__name__}: {value!r}"
    raise TypeError(msg)


def _type_name(cdf_type: int) -> str:
    """Return the name of a CDF data type, like ``CDF_UINT2``."""
    return pycdf.lib.cdftypenames[cdf_type]


def _compression(compression: tuple[Any, Any]) -> str:
    """
    Format the compression of a CDF file or variable.

    pycdf reports the compression as a ctypes constant and a parameter,
    like ``(c_long(5), 6)`` for GZIP compression at level 6.
    """
    names = {
        pycdf.const.NO_COMPRESSION.value: "none",
        pycdf.const.RLE_COMPRESSION.value: "RLE",
        pycdf.const.HUFF_COMPRESSION.value: "HUFF",
        pycdf.const.AHUFF_COMPRESSION.value: "AHUFF",
        pycdf.const.GZIP_COMPRESSION.value: "GZIP",
    }
    kind, parameter = compression
    kind = getattr(kind, "value", kind)
    name = names.get(kind, str(kind))
    if name == "none":
        return name
    return f"{name} {_format_value(parameter)}"


def _sparseness(sparseness: Any) -> str:  # noqa: ANN401
    """Format the sparse records mode of a variable."""
    names = {
        pycdf.const.NO_SPARSERECORDS.value: "none",
        pycdf.const.PAD_SPARSERECORDS.value: "pad",
        pycdf.const.PREV_SPARSERECORDS.value: "previous",
    }
    sparseness = getattr(sparseness, "value", sparseness)
    return names.get(sparseness, str(sparseness))


def _describe_global_attributes(cdf: pycdf.CDF) -> list[str]:
    """
    Describe the global attributes of a CDF file.

    Raises
    ------
    NotImplementedError
        If a global attribute has a time value. pycdf has no public way
        to read these values without converting them to
        `~datetime.datetime` objects, which would lose precision.
    """
    lines = ["global attributes:"]
    for name in cdf.attrs:
        attribute = cdf.attrs[name]
        lines.append(f"{_INDENT}{json.dumps(name)}:")
        for entry in range(attribute.max_idx() + 1):
            if not attribute.has_entry(entry):
                continue
            cdf_type = attribute.type(entry)
            if cdf_type in _TIME_TYPES:
                msg = (
                    f"Global attribute {name!r} has a time value of type "
                    f"{_type_name(cdf_type)}, which cannot be described."
                )
                raise NotImplementedError(msg)
            with warnings.catch_warnings():
                # spacepy 0.7.0 reads string attribute entries with
                # numpy.char.array, which NumPy 2.5 deprecates.
                warnings.filterwarnings(
                    "ignore", "The chararray class is deprecated", DeprecationWarning
                )
                value = _format_value(attribute[entry])
            lines.append(f"{_INDENT * 2}{entry}: {_type_name(cdf_type)} {value}")
    return lines


def _describe_variable(cdf: pycdf.CDF, name: str) -> list[str]:
    """Describe one variable of a CDF file, including its attributes."""
    # Raw values are as stored, without conversion to datetime or str.
    variable = cdf.raw_var(name)
    # For a record-varying variable, pycdf puts the number of records
    # first in the shape and indexes records first. A variable that does
    # not vary by record has at most one record, which is the whole
    # variable, so its shape is only its dimensions.
    if variable.rv():
        dimensions = variable.shape[1:]
        records = [variable[record] for record in range(len(variable))]
    else:
        dimensions = variable.shape
        records = [variable[...]] if len(variable) else []
    lines = [
        f"{_INDENT}{json.dumps(name)}:",
        f"{_INDENT * 2}type: {_type_name(variable.type())}",
        f"{_INDENT * 2}number of elements: {variable.nelems()}",
        f"{_INDENT * 2}dimensions: {_format_value(list(dimensions))}",
        f"{_INDENT * 2}dimension variances: {_format_value(variable.dv())}",
        f"{_INDENT * 2}record variance: {variable.rv()}",
        f"{_INDENT * 2}sparse records: {_sparseness(variable.sparse())}",
        f"{_INDENT * 2}compression: {_compression(variable.compress())}",
        f"{_INDENT * 2}pad value: {_format_value(variable.pad())}",
        f"{_INDENT * 2}attributes:",
    ]
    for attribute in variable.attrs:
        cdf_type = _type_name(variable.attrs.type(attribute))
        value = _format_value(variable.attrs[attribute])
        lines.append(f"{_INDENT * 3}{json.dumps(attribute)}: {cdf_type} {value}")
    lines.append(f"{_INDENT * 2}records: {len(records)}")
    lines.extend(
        f"{_INDENT * 3}{number}: {_format_value(record)}"
        for number, record in enumerate(records)
    )
    return lines


def describe_cdf(path: str | os.PathLike[str]) -> str:
    """
    Describe a CDF file as text.

    Parameters
    ----------
    path : path-like
        The CDF file.

    Returns
    -------
    str
        The description, which ends with a newline.

    Raises
    ------
    NotImplementedError
        If a global attribute has a time value, which pycdf cannot read
        without losing precision.
    """
    path = pathlib.Path(path)
    with pycdf.CDF(str(path)) as cdf:
        version = ".".join(str(number) for number in cdf.version())
        lines = [
            f"# Description of {path.name}, written by",
            "# `uv run python -m pyfaradaycup._cdf_description`. Do not edit.",
            "file:",
            f"{_INDENT}CDF version: {version}",
            f"{_INDENT}majority: {'column' if cdf.col_major() else 'row'}",
            f"{_INDENT}compression: {_compression(cdf.compress())}",
            f"{_INDENT}checksum: {cdf.checksum()}",
            *_describe_global_attributes(cdf),
            "variables:",
        ]
        for name in cdf:
            lines.extend(_describe_variable(cdf, name))
    return "\n".join(lines) + "\n"


def main(argv: Sequence[str] | None = None) -> None:
    """
    Write the text description of each CDF file.

    Parameters
    ----------
    argv : sequence of str, optional
        The CDF files to describe. By default, these are the skeleton CDF
        files distributed with pyfaradaycup.
    """
    if argv is None:
        argv = sys.argv[1:]
    paths = [pathlib.Path(arg) for arg in argv] or sorted(skeleton_dir.glob("*.cdf"))
    for path in paths:
        text = describe_cdf(path)
        # Path.write_text has no newline parameter before Python 3.10.
        with description_path(path).open("w", encoding="utf-8", newline="\n") as file:
            file.write(text)
        print(f"Wrote {description_path(path)}")  # noqa: T201


if __name__ == "__main__":
    main()
