"""Test converting windows into modulator voltages."""

from __future__ import annotations

from typing import Any

import numpy as np
import pytest

from pyfaradaycup.l1_to_l2._calibration import CALIBRATION_DIR, _read_ascii
from pyfaradaycup.l1_to_l2._spp_swp_spc_hvpsthermalcorrection import (
    spp_swp_spc_hvpsthermalcorrection,
)
from pyfaradaycup.l1_to_l2._spp_swp_spc_totalharmonicdistortion import (
    spp_swp_spc_totalharmonicdistortion,
)
from pyfaradaycup.l1_to_l2._spp_swp_spc_win2volt import spp_swp_spc_win2volt

_f = np.float32


def _arr(values: list[Any]) -> np.ndarray:
    return np.array(values, dtype=np.float32)


voltage_table = _read_ascii(
    CALIBRATION_DIR / "spp_swp_calfiles_spc_mvind2volt_20180801_v00.txt"
)


def test_hvpsthermalcorrection_regimes() -> None:
    """Test the undershoot model above and below 65 V, and at 0 V."""
    t_c = _f(-31.31)
    answer = spp_swp_spc_hvpsthermalcorrection(_arr([0.0, 30.0, 100.0]), t_c)
    dvu1 = _f(18.675209) * np.exp(_f(-0.014232420) * t_c)
    a = min(_f(-2.9385429) + _f(0.16528275) * t_c, _f(0.0))
    b = _f(3.5872333) * np.exp(_f(-0.027327427) * t_c)
    dvu2 = a + b * np.log(_f(30.0))
    assert answer.dvact.dtype == np.float32
    assert answer.dvact[0] == 0.0
    assert answer.dvact[1] == _f(30.0) - min(dvu2, _f(0.8) * _f(30.0))
    assert answer.dvact[2] == _f(100.0) - dvu1
    assert answer.thermal_calfile == "n/a (empirical model)"


def test_hvpsthermalcorrection_caps_undershoot() -> None:
    """
    Test that the undershoot is at most 80% of the requested width, which
    applies at 5 V, and that it is negative at 2 V, which widens the window.
    """
    answer = spp_swp_spc_hvpsthermalcorrection(_arr([5.0, 2.0]), _f(-31.31))
    assert answer.dvact[0] == _f(5.0) - _f(0.8) * _f(5.0)
    assert answer.dvact[1] > _f(2.0)


def test_hvpsthermalcorrection_fill_and_ideal() -> None:
    """Test fill values, and that the HVPS is ideal without a temperature."""
    answer = spp_swp_spc_hvpsthermalcorrection(_arr([-9999.0, 50.0]), _f(20.0))
    assert answer.dvact[0] == _f(-9999.0)
    ideal = spp_swp_spc_hvpsthermalcorrection(_arr([50.0]))
    assert ideal.dvact[0] == _f(50.0)


def test_hvpsthermalcorrection_temperature_shapes() -> None:
    """Test one temperature per window, per spectrum, and the wrong shape."""
    dvreq = np.full((2, 3), _f(30.0))
    per_spectrum = spp_swp_spc_hvpsthermalcorrection(dvreq, _arr([-30.0, 20.0]))
    per_window = spp_swp_spc_hvpsthermalcorrection(
        dvreq, np.repeat(_arr([[-30.0], [20.0]]), 3, axis=1)
    )
    np.testing.assert_array_equal(per_spectrum.dvact, per_window.dvact)
    assert per_spectrum.dvact[0, 0] != per_spectrum.dvact[1, 0]
    with pytest.raises(ValueError, match="same dimensions"):
        spp_swp_spc_hvpsthermalcorrection(_arr([1.0, 2.0, 3.0]), _arr([1.0, 2.0]))


@pytest.mark.parametrize(
    ("dv", "factor"),
    [(10.0, 0.5), (-10.0, 0.5), (30.0, 0.0135 * 30.0 + 0.27), (100.0, 0.85)],
)
def test_totalharmonicdistortion(dv: float, factor: float) -> None:
    """Test the piecewise linear distortion factor."""
    result = spp_swp_spc_totalharmonicdistortion(_arr([dv]))
    assert result.dtype == np.float32
    np.testing.assert_allclose(result, _f(dv) * _f(factor), rtol=1e-7)


def test_totalharmonicdistortion_fill() -> None:
    """Test that fill values are not changed."""
    assert spp_swp_spc_totalharmonicdistortion(_arr([-9999.0]))[0] == _f(-9999.0)


def test_win2volt_keeps_window_center() -> None:
    """
    Test that the voltages come from the ion or electron table, and the
    corrected window keeps the middle of the requested one.
    """
    win = np.array([10, 10], dtype=np.uint8)
    width = np.array([4, 4], dtype=np.int16)
    mode = np.array([0, 1], dtype=np.uint8)
    v = spp_swp_spc_win2volt(win, width, mode, t_c=_f(-31.31))
    for i, offset in enumerate((0, 256)):
        low, high = voltage_table[offset + 10], voltage_table[offset + 14]
        assert v.low[i] + v.high[i] == pytest.approx(low + high, rel=1e-6)
        assert abs(v.high[i] - v.low[i]) < abs(high - low)
    assert v.voltage_calfile.name == "spp_swp_calfiles_spc_mvind2volt_20180801_v00.txt"


def test_win2volt_clips_windows() -> None:
    """Test that windows above 255 use window 255, as IDL clips the subscripts."""
    v = spp_swp_spc_win2volt(
        np.array([250]), np.array([20]), np.array([0]), t_c=_f(-31.31)
    )
    w = spp_swp_spc_win2volt(
        np.array([250]), np.array([5]), np.array([0]), t_c=_f(-31.31)
    )
    assert v.low[0] == w.low[0]
    assert v.high[0] == w.high[0]


@pytest.mark.parametrize("t_c", [None, 0.0])
def test_win2volt_requires_temperature(t_c: float | None) -> None:
    """Test that a temperature is required, since IDL stops without one."""
    with pytest.raises(ValueError, match="No temperature"):
        spp_swp_spc_win2volt(np.array([1]), np.array([1]), np.array([0]), t_c=t_c)


def test_win2volt_thermal_calfile_not_supported() -> None:
    """Test that a thermal calibration file is not supported."""
    with pytest.raises(NotImplementedError):
        spp_swp_spc_win2volt(
            np.array([1]), np.array([1]), np.array([0]), t_c=1.0, thermal_calfile="x"
        )
