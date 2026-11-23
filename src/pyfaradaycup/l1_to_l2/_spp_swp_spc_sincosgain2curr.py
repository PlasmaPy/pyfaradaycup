"""Port of ``spp_swp_spc_sincosgain2curr.pro``."""

from __future__ import annotations

__all__ = ["Current", "Currents", "spp_swp_spc_sincosgain2curr"]

import dataclasses
from typing import TYPE_CHECKING

import numpy as np

from pyfaradaycup.l1_to_l2._spp_swp_spc_get_gainoffsets import (
    SensorGainOffsets,
    spp_swp_spc_get_gainoffsets,
)
from pyfaradaycup.l1_to_l2._spp_swp_spc_get_gains import (
    SensorGains,
    spp_swp_spc_get_gains,
)

if TYPE_CHECKING:
    import os
    import pathlib

    from numpy.typing import ArrayLike

SENSORS = ("a", "b", "c", "d")
"""The names of the four sensor plates."""

_SIGN_BIT = 2047
"""Sine and cosine DN above this are negative 12-bit two's complement values."""

_TWOS_COMPLEMENT = np.float32(4096.0)
"""What is subtracted from negative 12-bit two's complement values."""

_UNITS_FACTOR = np.float32(20.0)
"""
The placeholder factor that "puts the units ROUGHLY in picoAmps",
according to the comment in the IDL code.
"""


@dataclasses.dataclass(frozen=True)
class Current:
    """
    The current on one sensor plate.

    This is the structure returned by ``spp_swp_spc_sincosgain2curr``.
    """

    dat: np.ndarray
    """The current of each sample, as ``float32``."""

    gain_calfile: pathlib.Path
    offset_calfile: pathlib.Path

    gain: np.ndarray
    """The gain stage (0 to 3) of each sample."""


@dataclasses.dataclass(frozen=True)
class Currents:
    """
    The currents on the four sensor plates.

    This is the structure returned by ``spp_swp_spc_apid35{1,3,4}_get_currents``.
    """

    a: Current
    b: Current
    c: Current
    d: Current


def spp_swp_spc_sincosgain2curr(  # ruff:ignore[PLR0913]
    s: ArrayLike,
    c: ArrayLike,  # ruff:ignore[ARG001]  # overwritten in IDL; see below
    gval: ArrayLike,
    it: ArrayLike,  # ruff:ignore[ARG001]  # unused in IDL
    sen: str,
    *,
    gain_table: SensorGains | None = None,
    offset_table: SensorGainOffsets | None = None,
    offset_calfile: str | os.PathLike[str] | None = None,
    gain_calfile: str | os.PathLike[str] | None = None,
) -> Current:
    """
    Convert the sine and cosine DN of a sensor plate into a current.

    The current is ``20 * (sqrt(s**2 + c**2) + offset[3 - g]) / gains[3 - g]``,
    where ``g`` is the gain stage of each sample. The ``gains`` are
    ``[g0 * g1 * g2, g0 * g1, g0, 1]`` from the three gain factors of the
    sensor plate, and the ``offset`` are the four offsets of the plate.
    The sine and cosine DN are 12-bit two's complement values.

    Parameters
    ----------
    s : array_like
        The sine DN.
    c : array_like
        The cosine DN, which are not used; see the notes.
    gval : array_like
        The gain stage (0 to 3) of each sample.
    it : array_like
        The integration time, which is not used, as in IDL.
    sen : {"a", "b", "c", "d"}
        The sensor plate.
    gain_table : SensorGains, optional
        The gain factors. By default, they are read with
        `~pyfaradaycup.l1_to_l2._spp_swp_spc_get_gains.spp_swp_spc_get_gains`.
    offset_table : SensorGainOffsets, optional
        The gain stage offsets. By default, they are read with
        `~pyfaradaycup.l1_to_l2._spp_swp_spc_get_gainoffsets.spp_swp_spc_get_gainoffsets`.
    offset_calfile : path-like, optional
        The gain stage offsets file, if ``offset_table`` is not given.
    gain_calfile : path-like, optional
        The gain factors file, if ``gain_table`` is not given.

    Returns
    -------
    Current
        The current of each sample, as ``float32``.

    Raises
    ------
    ValueError
        If ``sen`` is not one of the sensor plates.

    Notes
    -----
    In IDL, the cosine argument is overwritten by ``c = sen eq 'c'``,
    because IDL names are case-insensitive. So the cosine DN are never
    used: the "cosine" is 1 for sensor plate C and 0 for the others. This
    is reproduced here.

    Gain stages above 3 give a negative index, which IDL clips to 0.
    """
    if sen not in SENSORS:
        # IDL prints an error and returns -1
        msg = f"The sensor must be one of {SENSORS}, not {sen!r}"
        raise ValueError(msg)
    o = (
        offset_table
        if offset_table is not None
        else spp_swp_spc_get_gainoffsets(offset_calfile)
    )
    g = gain_table if gain_table is not None else spp_swp_spc_get_gains(gain_calfile)

    sensor_gains = getattr(g, f"{sen}gains")
    gains = np.array(
        [
            sensor_gains[0] * sensor_gains[1] * sensor_gains[2],
            sensor_gains[0] * sensor_gains[1],
            sensor_gains[0],
            1.0,
        ],
        dtype=np.float32,
    )
    offset = getattr(o, f"{sen}offsets")

    s0 = np.array(s, dtype=np.float32, ndmin=1)
    s0[s0 > _SIGN_BIT] -= _TWOS_COMPLEMENT
    # IDL overwrites the cosine argument with this flag (see the notes)
    c0 = np.float32(sen == "c")
    gain = np.asarray(gval)
    # The index is computed as a signed integer, and IDL clips
    # out-of-range subscripts of arrays to the bounds
    stage = np.clip(3 - gain.astype(np.int64), 0, 3)
    qflux = _UNITS_FACTOR * (np.sqrt(s0**2 + c0**2) + offset[stage]) / gains[stage]
    return Current(
        dat=qflux.astype(np.float32, copy=False),
        gain_calfile=g.calfile,
        offset_calfile=o.calfile,
        gain=gain,
    )
