"""Port of ``spp_swp_spc_get_gains.pro``."""

from __future__ import annotations

__all__ = ["SensorGains", "spp_swp_spc_get_gains"]

import dataclasses
from typing import TYPE_CHECKING

from pyfaradaycup.l1_to_l2._calibration import _calfile, _read_ascii

if TYPE_CHECKING:
    import os
    import pathlib

    import numpy as np

_NGAINS = 3
"""The number of gain factors for each sensor in a sensor gains file."""


@dataclasses.dataclass(frozen=True)
class SensorGains:
    """
    The gain factors of the gain stages of each sensor plate.

    This is the structure returned by ``spp_swp_spc_get_gains`` in IDL.
    Each array has 3 ``float32`` values.
    """

    agains: np.ndarray
    bgains: np.ndarray
    cgains: np.ndarray
    dgains: np.ndarray
    calfile: pathlib.Path


def spp_swp_spc_get_gains(
    calfile: str | os.PathLike[str] | None = None,
) -> SensorGains:
    """
    Read the gain factors of the sensor plates from a calibration file.

    Parameters
    ----------
    calfile : path-like, optional
        The sensor gains file, which has 12 numbers: 3 for each of the
        sensor plates A, B, C, and D. By default, the last
        ``spp_swp_calfiles_spc_sensorgains_*.txt`` in the calibration
        directory is used.

    Returns
    -------
    SensorGains
        The gain factors.

    Raises
    ------
    FileNotFoundError
        If ``calfile`` is not given and there is no sensor gains file.
    """
    path = _calfile(calfile, "spp_swp_calfiles_spc_sensorgains_*.txt")
    gaindat = _read_ascii(path)
    return SensorGains(
        *(gaindat[i * _NGAINS : (i + 1) * _NGAINS] for i in range(4)), calfile=path
    )
