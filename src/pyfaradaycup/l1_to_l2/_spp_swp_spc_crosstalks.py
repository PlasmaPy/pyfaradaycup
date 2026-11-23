"""Port of ``spp_swp_spc_crosstalks.pro``."""

from __future__ import annotations

__all__ = ["Crosstalks", "spp_swp_spc_crosstalks"]

import dataclasses
from typing import TYPE_CHECKING

from pyfaradaycup.l1_to_l2._calibration import _calfile, _read_ascii

if TYPE_CHECKING:
    import os
    import pathlib

    import numpy as np

_NSENSORS = 4


@dataclasses.dataclass(frozen=True)
class Crosstalks:
    """The structure returned by ``spp_swp_spc_crosstalks``."""

    dat: np.ndarray
    """
    The ``(4, 4)`` matrix ``M`` (as ``float32``) that corrects the
    currents for crosstalk: ``[A, B, C, D]_corrected = M @ [A, B, C, D]``.
    """

    crosstalk_calfile: pathlib.Path


def spp_swp_spc_crosstalks(
    calfile: str | os.PathLike[str] | None = None,
) -> Crosstalks:
    """
    Read the matrix that corrects for crosstalk between the sensor plates.

    Parameters
    ----------
    calfile : path-like, optional
        The sensor crosstalk file, which has the 16 elements of the
        matrix, one row after another. By default, the last
        ``spp_swp_calfiles_spc_sensorcrosstalk_*.txt`` in the calibration
        directory is used.

    Returns
    -------
    Crosstalks
        The matrix.

    Raises
    ------
    FileNotFoundError
        If ``calfile`` is not given and there is no sensor crosstalk file.

    Notes
    -----
    IDL stores the matrix as ``transpose(reform(values, 4, 4))``, so that
    its element ``[i, j]`` (column ``i`` and row ``j`` in IDL's order) is
    ``values[4 * i + j]``. Here, ``dat[i, j]`` is the same element.
    """
    path = _calfile(calfile, "spp_swp_calfiles_spc_sensorcrosstalk_*.txt")
    values = _read_ascii(path)
    return Crosstalks(dat=values.reshape(_NSENSORS, _NSENSORS), crosstalk_calfile=path)
