"""
Port of the routines in ``spp_swp_spc_pmax_response.pro`` that the L2 to
L3 step uses: ``spc_fluxfunction``, ``spp_swp_spc_pmax_response``, and
``spp_swp_spc_pmax_response_normal_curvefit``.
"""

from __future__ import annotations

__all__ = [
    "PmaxResponse",
    "spc_fluxfunction",
    "spp_swp_spc_pmax_response",
    "spp_swp_spc_pmax_response_normal_curvefit",
]

import dataclasses

import numpy as np

Q_OVER_M = 9.58e7
"""
The charge to mass ratio of the proton in C/kg, as hard-coded in IDL.

This is larger than the 9.5788331e7 C/kg of CODATA 2018 by 1.2 parts in
10⁴.
"""

E_PC_Q_OVER_M = 15.348852
"""
The elementary charge in pC times `Q_OVER_M`, as hard-coded in IDL, in
pC C/kg.
"""

EFFAREA_MM2 = float(np.float32(131.78035))
"""
The effective area at normal incidence in the cold plasma limit, in mm²,
which is the default in IDL. It is a single precision literal in IDL.
"""

_SQRT2 = float(np.sqrt(np.float32(2)))
"""``sqrt(2.)`` in IDL, which is single precision."""

_S2M4 = float(np.float32(1) / np.float32(192))
"""``1./192.`` in IDL, which is single precision."""

_S3M6 = float(np.float32(1) / np.float32(9216))
"""``1./9216.`` in IDL, which is single precision."""


def _keyword_or_one(value: float | None) -> float:
    """Return ``value``, or 1 if it is not set, like IDL's ``keyword_set``."""
    return value or 1.0


def spc_fluxfunction(
    volt: np.ndarray,
    p: np.ndarray,
    *,
    charge: float | None = None,
    mass: float | None = None,
) -> np.ndarray:
    """
    Return the charge flux per unit voltage of a drifting Maxwellian.

    For ions of charge ``Z e`` and mass ``M m_p`` with the one-dimensional
    distribution ``f(v) = n / (sqrt(pi) w) exp(-((v - u) / w)**2)``, where
    ``w`` is the most probable thermal speed, the charge flux per unit
    energy per charge ``V`` is ``dJ/dV = Z e v f(v) dv/dV = (Z**2 / M) e
    (e / m_p) f(v)``, since ``M m_p v dv = Z e dV``. This is equation (21)
    of the SPC memo "FC response with sinusoidal modulation" (FCRSM),
    according to the IDL code; the memo is not in the snapshot of the IDL
    code.

    Parameters
    ----------
    volt : numpy.ndarray
        The energy per charge, in V.
    p : numpy.ndarray
        The bulk speed toward the sensor (``-v_z``) in km/s, the most
        probable thermal speed in km/s, and the density in cm⁻³.
    charge : float, optional
        The charge number ``Z``. Defaults to 1, and so does 0.
    mass : float, optional
        The mass number ``M``, in units of the proton mass. Defaults to 1,
        and so does 0.

    Returns
    -------
    numpy.ndarray
        The charge flux per unit voltage, in pA m⁻² V⁻¹.

    Notes
    -----
    The constants are those hard-coded in IDL: `E_PC_Q_OVER_M` for ``e
    (e / m_p)``, and `Q_OVER_M` for ``e / m_p`` in the speed ``v = sqrt(2
    (Z / M) (e / m_p) V)``.
    """
    charge = _keyword_or_one(charge)
    mass = _keyword_or_one(mass)
    n_si = p[2] * 1e6
    w_si = p[1] * 1e3
    um = p[0] / p[1]
    v_si = np.sqrt(2.0 * Q_OVER_M * np.asarray(volt, dtype=np.float64) * charge / mass)
    vm = v_si / w_si
    z = um - vm
    return (
        (charge * charge / mass)
        * E_PC_Q_OVER_M
        * (n_si / (w_si * np.sqrt(np.pi)))
        * np.exp(-(z**2))
    )


@dataclasses.dataclass(frozen=True)
class PmaxResponse:
    """
    The currents from `spp_swp_spc_pmax_response`.

    IDL returns ``current`` and the keyword outputs ``I0`` to ``I3``.
    """

    current: np.ndarray
    """The current in each window, ``i0 + i1 + i2 + i3``, in pA."""

    i0: np.ndarray
    """The current to zeroth order, ``A * phi(V) * dV / 2``."""

    i1: np.ndarray
    """The correction of order ``dx**2``."""

    i2: np.ndarray
    """The correction of order ``dx**4``."""

    i3: np.ndarray
    """The correction of order ``dx**6``."""


def spp_swp_spc_pmax_response(  # ruff:ignore[PLR0913]
    volt: np.ndarray,
    dvolt: np.ndarray,
    p: np.ndarray,
    *,
    effarea_mm2: float | None = None,
    mass: float | None = None,
    charge: float | None = None,
) -> PmaxResponse:
    """
    Return the response of SPC to a drifting Maxwellian.

    The current measured with sinusoidal modulation of amplitude ``dV / 2``
    around ``V`` is the first Fourier amplitude of the collected current.
    To zeroth order it is ``I0 = A * phi(V) * dV / 2``, with the flux
    function ``phi`` of `spc_fluxfunction`. The corrections to third order
    in the expansion parameter ``dx = (Z / M) (e / m_p) dV / (2 w_rms**2)``
    are ``I0 * s1 * dx**2``, ``I0 * s2 * dx**4``, and ``I0 * s3 * dx**6``,
    where ``s1``, ``s2``, and ``s3`` are polynomials in ``u / v`` and
    ``w_rms / v``, from the SPC memo "FC response with sinusoidal
    modulation" (FCRSM), which is not in the snapshot of the IDL code.

    Parameters
    ----------
    volt : numpy.ndarray
        The voltages at the centers of the windows, in V.
    dvolt : numpy.ndarray
        The widths (peak to peak) of the windows, in V.
    p : numpy.ndarray
        The bulk speed toward the sensor in km/s, the most probable
        thermal speed in km/s, and the density in cm⁻³.
    effarea_mm2 : float, optional
        The effective area in mm². Defaults to `EFFAREA_MM2`, and so does
        0.
    mass : float, optional
        The mass number. Defaults to 1, and so does 0.
    charge : float, optional
        The charge number. Defaults to 1, and so does 0.

    Returns
    -------
    PmaxResponse
        The currents in pA, and their terms.

    Notes
    -----
    As in IDL, ``p[1]`` is the most probable thermal speed, which is
    divided by the single precision ``sqrt(2.)`` to give the RMS thermal
    speed ``w_rms`` of the corrections, and the coefficients ``1./192.``
    and ``1./9216.`` of ``s2`` and ``s3`` are single precision.

    The default area of 131.78035 mm² differs from the 137.260 mm² that
    ``spp_swp_spc_get1rdf`` uses for the moments.
    """
    charge = _keyword_or_one(charge)
    mass = _keyword_or_one(mass)
    effarea_mm2 = effarea_mm2 or EFFAREA_MM2
    a_si = effarea_mm2 * 1e-6

    volt = np.asarray(volt, dtype=np.float64)
    dvolt = np.asarray(dvolt, dtype=np.float64)
    w_si = p[1] * 1e3 / _SQRT2
    u_si = p[0] * 1e3
    v_si = np.sqrt(2.0 * Q_OVER_M * volt * charge / mass)
    u_v = u_si / v_si
    w_v = w_si / v_si

    dx = 0.5 * Q_OVER_M * (charge / mass) * dvolt / (w_si**2)

    i0 = a_si * spc_fluxfunction(volt, p, charge=charge, mass=mass) * (dvolt / 2.0)

    s1m2 = (1.0 / 8.0) * (1.0 + u_v**2 - 2.0 * u_v - u_v * w_v**2)
    s2m4 = _S2M4 * (
        (u_v**4)
        - (u_v**3) * (4.0 + 6.0 * w_v**2)
        + 3.0 * (u_v**2) * (2.0 + 4.0 * w_v**2 + 5.0 * w_v**4)
        - u_v * (4.0 + 6.0 * w_v**2 + 12.0 * w_v**4 + 15.0 * w_v**6)
        + 1.0
    )
    s3m6 = _S3M6 * (
        (u_v**6)
        - 3.0 * (u_v**5) * (2.0 + 5.0 * w_v**2)
        + 15.0 * (u_v**4) * (1.0 + 4.0 * w_v**2 + 7.0 * w_v**4)
        - 10.0 * (u_v**3) * (2.0 + 9.0 * w_v**2 + 27.0 * w_v**4 + 42.0 * w_v**6)
        + 15.0
        * (u_v**2)
        * (1.0 + 4.0 * w_v**2 + 15.0 * w_v**4 + 42.0 * w_v**6 + 63.0 * w_v**8)
        - 3.0
        * u_v
        * (
            2.0
            + 5.0 * w_v**2
            + 20.0 * w_v**4
            + 75.0 * w_v**6
            + 210.0 * w_v**8
            + 315.0 * w_v**10
        )
        + 1.0
    )

    i1 = i0 * (s1m2 * dx**2)
    i2 = i0 * (s2m4 * dx**4)
    i3 = i0 * (s3m6 * dx**6)
    return PmaxResponse(current=i0 + i1 + i2 + i3, i0=i0, i1=i1, i2=i2, i3=i3)


def spp_swp_spc_pmax_response_normal_curvefit(
    x: np.ndarray, a: np.ndarray
) -> np.ndarray:
    """
    Return the response of SPC to a drifting Maxwellian, for fitting.

    This is the function that ``spp_swp_spc_get1rdf`` fits with IDL's
    ``CURVEFIT`` and ``/NODERIVATIVE``, so it is called as
    ``function(x, a)`` by `~pyfaradaycup.utils.idl.fitcurve` with
    ``noderivative=True``.

    Parameters
    ----------
    x : numpy.ndarray
        The lower and upper voltages of the windows, in V, with shape
        ``(n, 2)``, so that ``x[:, 0]`` is the lower voltages, as
        ``x[*, 0]`` is in IDL.
    a : numpy.ndarray
        The parameters of `spp_swp_spc_pmax_response`.

    Returns
    -------
    numpy.ndarray
        The current in each window, in pA.

    Notes
    -----
    As in IDL, the center and width of the windows are computed from the
    voltages in their type, so in single precision for the voltages of
    the L2 files.
    """
    x = np.asarray(x)
    vlo = x[:, 0]
    vhi = x[:, 1]
    volt = (vlo + vhi) / 2.0
    dvolt = vhi - vlo
    return spp_swp_spc_pmax_response(volt, dvolt, a).current
