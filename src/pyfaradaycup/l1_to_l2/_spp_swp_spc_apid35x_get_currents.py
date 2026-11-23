"""
Port of ``spp_swp_spc_apid351_get_currents.pro``,
``spp_swp_spc_apid353_get_currents.pro``, and
``spp_swp_spc_apid354_get_currents.pro``.

The three IDL files are short and nearly the same, so they are ported
in one module.
"""

from __future__ import annotations

__all__ = [
    "spp_swp_spc_apid351_get_currents",
    "spp_swp_spc_apid353_get_currents",
    "spp_swp_spc_apid354_get_currents",
]

import dataclasses
from typing import TYPE_CHECKING

import numpy as np

from pyfaradaycup.l1_to_l2._spp_swp_spc_sincosgain2curr import (
    SENSORS,
    Currents,
    spp_swp_spc_sincosgain2curr,
)

if TYPE_CHECKING:
    import os
    from collections.abc import Mapping

    from pyfaradaycup.l1_to_l2._spp_swp_spc_get_gainoffsets import SensorGainOffsets
    from pyfaradaycup.l1_to_l2._spp_swp_spc_get_gains import SensorGains

_GAIN_STAGES = 4
"""The number of gain stages of each sensor plate."""

_SQRT2 = np.sqrt(np.float32(2.0))
"""``sqrt(2.)`` in IDL, as ``float32``."""


def spp_swp_spc_apid351_get_currents(
    dat: Mapping[str, np.ndarray],
    *,
    gain_table: SensorGains | None = None,
    offset_table: SensorGainOffsets | None = None,
    offset_calfile: str | os.PathLike[str] | None = None,
    gain_calfile: str | os.PathLike[str] | None = None,
) -> Currents:
    """
    Return the currents from APID 351 (all-gain diagnostic) packets.

    Each packet has the sine and cosine DN of every gain stage of each
    sensor plate, such as ``A0S`` to ``A3S`` and ``A0C`` to ``A3C``. The
    gain stage to use for each plate is in ``GAIN_SEL``: bits 7–6 for A,
    5–4 for B, 3–2 for C, and 1–0 for D.

    Parameters
    ----------
    dat : mapping of str to numpy.ndarray
        The variables of an APID 351 L1 file, with lower-case names.
    gain_table, offset_table, offset_calfile, gain_calfile : optional
        Passed to `spp_swp_spc_sincosgain2curr`.

    Returns
    -------
    Currents
        The current on each sensor plate.
    """
    gain = np.asarray(dat["gain_sel"], dtype=np.uint8)
    # IDL formats each value as 8 binary digits and reads 2 digits for
    # each sensor plate, starting with A in the most significant bits
    stages = {
        sen: ((gain >> (6 - 2 * i)) & 3).astype(np.uint8)
        for i, sen in enumerate(SENSORS)
    }
    currents = {}
    for sen, stage in stages.items():
        # Select the values for the gain stage of each sample, like
        # (again eq 0)*dat.a0s.dat + (again eq 1)*dat.a1s.dat + ...
        sin = sum((stage == g) * dat[f"{sen}{g}s"] for g in range(_GAIN_STAGES))
        cos = sum((stage == g) * dat[f"{sen}{g}c"] for g in range(_GAIN_STAGES))
        currents[sen] = spp_swp_spc_sincosgain2curr(
            sin,
            cos,
            stage,
            dat["sw_spc_inttime"],
            sen,
            gain_table=gain_table,
            offset_table=offset_table,
            offset_calfile=offset_calfile,
            gain_calfile=gain_calfile,
        )
    return Currents(**currents)


def spp_swp_spc_apid353_get_currents(
    dat: Mapping[str, np.ndarray],
    *,
    gain_table: SensorGains | None = None,
    offset_table: SensorGainOffsets | None = None,
    offset_calfile: str | os.PathLike[str] | None = None,
    gain_calfile: str | os.PathLike[str] | None = None,
) -> Currents:
    """
    Return the currents from APID 353 (science) packets.

    The currents are multiplied by ``sqrt(2)``, which the IDL code
    describes as adjusting "for the firmware shortcut that allows RSS and
    components to fill the same 0-4096 numberspace" (2024-11-01).

    Parameters
    ----------
    dat : mapping of str to numpy.ndarray
        The variables of an APID 353 L1 file, with lower-case names.
    gain_table, offset_table, offset_calfile, gain_calfile : optional
        Passed to `spp_swp_spc_sincosgain2curr`.

    Returns
    -------
    Currents
        The current on each sensor plate.
    """
    currents = {}
    for sen in SENSORS:
        current = spp_swp_spc_sincosgain2curr(
            dat[f"{sen}sin"],
            dat[f"{sen}cos"],
            dat[f"{sen}gain"],
            dat["sw_spc_inttime"],
            sen,
            gain_table=gain_table,
            offset_table=offset_table,
            offset_calfile=offset_calfile,
            gain_calfile=gain_calfile,
        )
        currents[sen] = dataclasses.replace(current, dat=current.dat * _SQRT2)
    return Currents(**currents)


def spp_swp_spc_apid354_get_currents(
    dat: Mapping[str, np.ndarray],
    *,
    gain_table: SensorGains | None = None,
    offset_table: SensorGainOffsets | None = None,
    offset_calfile: str | os.PathLike[str] | None = None,
    gain_calfile: str | os.PathLike[str] | None = None,
) -> Currents:
    """
    Return the currents from APID 354 (SWEM RSS) packets.

    These packets have the root sum square of the sine and cosine DN,
    such as ``ARSS``, which is passed as the sine with a cosine of 0.

    Parameters
    ----------
    dat : mapping of str to numpy.ndarray
        The variables of an APID 354 L1 file, with lower-case names.
    gain_table, offset_table, offset_calfile, gain_calfile : optional
        Passed to `spp_swp_spc_sincosgain2curr`.

    Returns
    -------
    Currents
        The current on each sensor plate.
    """
    return Currents(
        **{
            sen: spp_swp_spc_sincosgain2curr(
                dat[f"{sen}rss"],
                0,
                dat[f"{sen}gain"],
                dat["sw_spc_inttime"],
                sen,
                gain_table=gain_table,
                offset_table=offset_table,
                offset_calfile=offset_calfile,
                gain_calfile=gain_calfile,
            )
            for sen in SENSORS
        }
    )
