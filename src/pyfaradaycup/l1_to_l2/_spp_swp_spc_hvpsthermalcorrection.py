"""Port of ``spp_swp_spc_hvpsthermalcorrection.pro``."""

from __future__ import annotations

__all__ = ["HvpsThermalCorrection", "spp_swp_spc_hvpsthermalcorrection"]

import dataclasses
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from numpy.typing import ArrayLike

_f = np.float32

_DEFAULT_FILLVAL = _f(-9999.0)


@dataclasses.dataclass(frozen=True)
class HvpsThermalCorrection:
    """The structure returned by ``spp_swp_spc_hvpsthermalcorrection``."""

    dvreq: np.ndarray
    """The requested window widths, in volts."""

    dvact: np.ndarray
    """The actual window widths, in volts."""

    thermal_calfile: str = "n/a (empirical model)"


def spp_swp_spc_hvpsthermalcorrection(
    dvreq: ArrayLike, t_c: ArrayLike | None = None, fillval: float | None = None
) -> HvpsThermalCorrection:
    """
    Correct the voltage window widths for the thermal response of the HVPS.

    When the requested AC amplitude is small and the instrument is cold,
    the high voltage power supply (HVPS) undershoots the requested
    window width ``dvreq`` by ``dvu``, so the actual width is
    ``dvreq - dvu``. This uses J. C. Kasper's six-parameter empirical
    model, fitted to laboratory measurements with a 500 MΩ load:

    - ``dvu = 18.675209 * exp(-0.014232420 * T_C)`` for ``dvreq > 65`` V,
    - ``dvu = A + B * ln(dvreq)`` for ``dvreq <= 65`` V, where
      ``A = min(-2.9385429 + 0.16528275 * T_C, 0)`` and
      ``B = 3.5872333 * exp(-0.027327427 * T_C)``,

    with ``dvu`` capped at ``0.8 * dvreq``.

    Parameters
    ----------
    dvreq : array_like
        The requested window widths, in volts.
    t_c : array_like, optional
        The LV temperature, in °C: one value, one for each window width,
        or, for a two-dimensional ``dvreq``, one for each row. If it is not
        given, the HVPS is treated as ideal.
    fillval : float, optional
        Window widths with this value are treated as fill, and so are
        their actual widths. Defaults to ``-9999.``.

    Returns
    -------
    HvpsThermalCorrection
        The requested and actual window widths, as ``float32``. Window
        widths of 0 give actual widths of 0.

    Raises
    ------
    ValueError
        If ``t_c`` does not have one value or the same shape as ``dvreq``.
        IDL stops with an error message.

    Notes
    -----
    The model is from an email by J. C. Kasper to the PSP calibration
    working group on 2019-01-06, quoted in the IDL source, which says that
    it is not expected to be fully correct. There is no published
    reference. The constants are ``float32``, as in IDL.

    IDL returns ``dvreq`` itself, rather than a structure, if ``t_c`` is
    not given.
    """
    dvreq = np.asarray(dvreq, dtype=np.float32)
    if t_c is None:
        return HvpsThermalCorrection(dvreq=dvreq, dvact=dvreq)
    t_c = np.asarray(t_c, dtype=np.float32)
    if t_c.size == 1:
        t_c = t_c.reshape(()) + _f(0.0) * dvreq
    elif t_c.ndim == 1 and dvreq.ndim == 2 and t_c.size == dvreq.shape[0]:  # ruff:ignore[PLR2004]
        # one temperature per spectrum (row)
        t_c = np.broadcast_to(t_c[:, np.newaxis], dvreq.shape)
    if t_c.size != dvreq.size:
        msg = "dvreq and t_c must have the same dimensions"
        raise ValueError(msg)
    fill = _f(fillval) if fillval else _DEFAULT_FILLVAL

    with np.errstate(divide="ignore", invalid="ignore"):
        dvu1 = _f(18.675209) * np.exp(_f(-0.014232420) * t_c)
        a = np.minimum(_f(-2.9385429) + _f(0.16528275) * t_c, _f(0.0))
        b = _f(3.5872333) * np.exp(_f(-0.027327427) * t_c)
        dvu2 = a + b * np.log(dvreq)
        dvu = dvu1 * (dvreq > _f(65.0)) + dvu2 * (dvreq <= _f(65.0))
        dvu = np.minimum(dvu, _f(0.8) * dvreq)
        dvact = dvreq - dvu
    dvact[dvreq == fill] = fill
    dvact[dvreq == _f(0.0)] = 0.0
    return HvpsThermalCorrection(dvreq=dvreq, dvact=dvact)
