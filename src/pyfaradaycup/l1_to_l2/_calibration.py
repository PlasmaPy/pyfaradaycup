"""
Find and read SPC calibration files.

The IDL routines find each calibration file by searching
``code_path + 'calibration/'`` and using the alphabetically last match,
which is the highest version, and read it with ``read_ascii``.
"""

from __future__ import annotations

import pathlib
from typing import TYPE_CHECKING

import numpy as np

from pyfaradaycup._paths import data_dir

if TYPE_CHECKING:
    import os

CALIBRATION_DIR = data_dir / "calibration"
"""The directory of the SPC calibration files in the package data."""


def _calfile(calfile: str | os.PathLike[str] | None, pattern: str) -> pathlib.Path:
    """
    Return ``calfile``, or else the last calibration file matching ``pattern``.

    Like IDL's ``file_search``, the matches are sorted case-sensitively,
    so the last one is the highest zero-padded version.

    Raises
    ------
    FileNotFoundError
        If ``calfile`` is `None` and no calibration file matches.
    """
    if calfile is not None:
        return pathlib.Path(calfile)
    calfiles = sorted(CALIBRATION_DIR.glob(pattern), key=str)
    if not calfiles:
        msg = f"No calibration file in {CALIBRATION_DIR} matches {pattern!r}"
        raise FileNotFoundError(msg)
    return calfiles[-1]


def _read_ascii(calfile: pathlib.Path) -> np.ndarray:
    """
    Read a calibration file that has one number on each line.

    This replaces ``read_ascii(calfile).field1`` in IDL, which reads the
    values as ``FLOAT``. Blank lines are skipped.
    """
    with calfile.open() as file:
        return np.array(
            [float(line) for line in file if line.strip()], dtype=np.float32
        )
