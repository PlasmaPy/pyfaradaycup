"""Test converting sine and cosine DN into currents on the sensor plates."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pytest

from pyfaradaycup.l1_to_l2._spp_swp_spc_apid35x_get_currents import (
    spp_swp_spc_apid351_get_currents,
    spp_swp_spc_apid353_get_currents,
    spp_swp_spc_apid354_get_currents,
)
from pyfaradaycup.l1_to_l2._spp_swp_spc_get_gainoffsets import SensorGainOffsets
from pyfaradaycup.l1_to_l2._spp_swp_spc_get_gains import SensorGains
from pyfaradaycup.l1_to_l2._spp_swp_spc_sincosgain2curr import (
    SENSORS,
    spp_swp_spc_sincosgain2curr,
)

_f = np.float32


def _arr(values: list[Any]) -> np.ndarray:
    return np.array(values, dtype=np.float32)


# Gain factors of 2, 3, and 5 for each plate, so gains = [30, 6, 2, 1],
# and offsets that differ by plate
gain_table = SensorGains(
    *([np.array([2.0, 3.0, 5.0], dtype=np.float32)] * 4), calfile=Path("gains.txt")
)
offset_table = SensorGainOffsets(
    aoffsets=np.array([1.0, 2.0, 3.0, 4.0], dtype=np.float32),
    boffsets=np.array([0.0, 0.0, 0.0, 0.0], dtype=np.float32),
    coffsets=np.array([0.0, 0.0, 0.0, 0.0], dtype=np.float32),
    doffsets=np.array([0.0, 0.0, 0.0, 0.0], dtype=np.float32),
    calfile=Path("offsets.txt"),
)


@pytest.mark.parametrize(
    ("gval", "gain", "offset"),
    [(0, 1.0, 4.0), (1, 2.0, 3.0), (2, 6.0, 2.0), (3, 30.0, 1.0)],
)
def test_sincosgain2curr_gain_stages(gval: int, gain: float, offset: float) -> None:
    """Test the gain and offset used for each gain stage."""
    current = spp_swp_spc_sincosgain2curr(
        [100], 0, [gval], 0, "a", gain_table=gain_table, offset_table=offset_table
    )
    expected = _f(20.0) * (_f(100.0) + _f(offset)) / _f(gain)
    assert current.dat.dtype == np.float32
    assert current.dat[0] == expected
    assert current.gain_calfile == Path("gains.txt")
    assert current.offset_calfile == Path("offsets.txt")


def test_sincosgain2curr_twos_complement() -> None:
    """Test that DN above 2047 are negative 12-bit two's complement values."""
    current = spp_swp_spc_sincosgain2curr(
        [2047, 2048, 4095],
        0,
        [0, 0, 0],
        0,
        "b",
        gain_table=gain_table,
        offset_table=offset_table,
    )
    np.testing.assert_array_equal(current.dat, _f(20.0) * _arr([2047.0, 2048.0, 1.0]))


@pytest.mark.parametrize("sen", SENSORS)
def test_sincosgain2curr_ignores_cosine(sen: str) -> None:
    """
    Test that the cosine DN are not used, and the cosine is 1 for plate C
    and 0 for the others, because IDL overwrites the cosine argument.
    """
    current = spp_swp_spc_sincosgain2curr(
        [3], [4000], [0], 0, sen, gain_table=gain_table, offset_table=offset_table
    )
    cosine = 1.0 if sen == "c" else 0.0
    offset = 4.0 if sen == "a" else 0.0
    expected = _f(20.0) * (np.sqrt(_f(9.0) + _f(cosine)) + _f(offset))
    assert current.dat[0] == expected


def test_sincosgain2curr_clips_gain_stage() -> None:
    """Test that gain stages above 3 use stage 3, as IDL clips the negative index."""
    stage3 = spp_swp_spc_sincosgain2curr(
        [10], 0, [3], 0, "a", gain_table=gain_table, offset_table=offset_table
    )
    stage7 = spp_swp_spc_sincosgain2curr(
        [10], 0, [7], 0, "a", gain_table=gain_table, offset_table=offset_table
    )
    assert stage7.dat[0] == stage3.dat[0]


def test_sincosgain2curr_invalid_sensor() -> None:
    """Test that an error is raised for an unknown sensor plate."""
    with pytest.raises(ValueError, match="must be one of"):
        spp_swp_spc_sincosgain2curr(
            [1], 0, [0], 0, "e", gain_table=gain_table, offset_table=offset_table
        )


def _dat(**values: list[int]) -> dict[str, np.ndarray]:
    return {"sw_spc_inttime": np.zeros(1, dtype=np.uint16)} | {
        name: np.array(value, dtype=np.uint16) for name, value in values.items()
    }


def test_apid351_get_currents_gain_bits() -> None:
    """
    Test that the gain stage of each plate comes from 2 bits of GAIN_SEL,
    starting with A in the most significant bits.
    """
    dat = _dat(
        **{
            f"{sen}{g}{sc}": [100 * g + 10 * i + 1]
            for i, sen in enumerate(SENSORS)
            for g in range(4)
            for sc in "sc"
        }
    )
    dat["gain_sel"] = np.array([0b11_10_01_00], dtype=np.uint8)
    currents = spp_swp_spc_apid351_get_currents(
        dat, gain_table=gain_table, offset_table=offset_table
    )
    for sen, stage in zip(SENSORS, (3, 2, 1, 0)):
        current = getattr(currents, sen)
        assert current.gain.tolist() == [stage]
        i = SENSORS.index(sen)
        expected = spp_swp_spc_sincosgain2curr(
            [100 * stage + 10 * i + 1],
            0,
            [stage],
            0,
            sen,
            gain_table=gain_table,
            offset_table=offset_table,
        )
        assert current.dat[0] == expected.dat[0]


def test_apid353_get_currents_sqrt2() -> None:
    """Test that the APID 353 currents are multiplied by sqrt(2)."""
    dat = _dat(**{f"{sen}{x}": [50] for sen in SENSORS for x in ("sin", "cos", "gain")})
    currents = spp_swp_spc_apid353_get_currents(
        dat, gain_table=gain_table, offset_table=offset_table
    )
    rss = spp_swp_spc_apid354_get_currents(
        _dat(**{f"{sen}{x}": [50] for sen in SENSORS for x in ("rss", "gain")}),
        gain_table=gain_table,
        offset_table=offset_table,
    )
    for sen in SENSORS:
        assert getattr(currents, sen).dat[0] == getattr(rss, sen).dat[0] * np.sqrt(
            _f(2.0)
        )
