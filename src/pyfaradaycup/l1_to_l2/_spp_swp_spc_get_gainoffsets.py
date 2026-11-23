"""Port of ``spp_swp_spc_get_gainoffsets.pro``."""

from __future__ import annotations

__all__ = ["SensorGainOffsets", "spp_swp_spc_get_gainoffsets"]

import dataclasses
from typing import TYPE_CHECKING

from pyfaradaycup.l1_to_l2._calibration import _calfile, _read_ascii

if TYPE_CHECKING:
    import os
    import pathlib

    import numpy as np

_NOFFSETS = 4
"""The number of offsets for each sensor in a sensor gain offsets file."""


@dataclasses.dataclass(frozen=True)
class SensorGainOffsets:
    """
    The offsets of the gain stages of each sensor plate.

    This is the structure returned by ``spp_swp_spc_get_gainoffsets`` in
    IDL. Each array has 4 ``float32`` values, one for each gain stage.
    """

    aoffsets: np.ndarray
    boffsets: np.ndarray
    coffsets: np.ndarray
    doffsets: np.ndarray
    calfile: pathlib.Path


def spp_swp_spc_get_gainoffsets(
    calfile: str | os.PathLike[str] | None = None,
) -> SensorGainOffsets:
    """
    Read the gain stage offsets of the sensor plates from a calibration file.

    Parameters
    ----------
    calfile : path-like, optional
        The sensor gain offsets file, which has 16 numbers: 4 for each of
        the sensor plates A, B, C, and D. By default, the last
        ``spp_swp_calfiles_spc_sensorgainoffsets_*.txt`` in the
        calibration directory is used.

    Returns
    -------
    SensorGainOffsets
        The offsets.

    Raises
    ------
    FileNotFoundError
        If ``calfile`` is not given and there is no sensor gain offsets file.
    """
    path = _calfile(calfile, "spp_swp_calfiles_spc_sensorgainoffsets_*.txt")
    offsetdat = _read_ascii(path)
    return SensorGainOffsets(
        *(offsetdat[i * _NOFFSETS : (i + 1) * _NOFFSETS] for i in range(4)),
        calfile=path,
    )
