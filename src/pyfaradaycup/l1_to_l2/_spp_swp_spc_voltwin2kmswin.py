"""Port of ``spp_swp_spc_voltwin2kmswin.pro``."""

from __future__ import annotations

__all__ = ["KmsWindow", "spp_swp_spc_voltwin2kmswin"]

import dataclasses

import numpy as np

_C = np.float32(13.84177)
"""
``c = sqrt(2 e / m_p)`` in km s⁻¹ V^-½, hard-coded as a ``float32`` in
IDL. It is kept rather than computed with `astropy.constants`, so that
the results are the same as in IDL.
"""

# Coefficients of Hastings' polynomial approximation to the complete
# elliptic integral of the second kind, as in IDL
_A = (0.44325141463, 0.06260601220, 0.04757383546, 0.01736506451)
_B = (0.24998368310, 0.09200180037, 0.04069697526, 0.00526449639)


@dataclasses.dataclass(frozen=True)
class KmsWindow:
    """The outputs of ``spp_swp_spc_voltwin2kmswin``."""

    volt_mid: np.ndarray
    """The middle voltage of each window, in volts (``float32``)."""

    dvolt: np.ndarray
    """The width of each window, in volts (``float32``)."""

    vkms_mid: np.ndarray
    """The average proton speed over each window, in km/s (``float64``)."""

    dvkms: np.ndarray
    """The speed amplitude of each window, in km/s (``float64``)."""

    @property
    def vkms_lo(self) -> np.ndarray:
        """The lower speed of each window, in km/s."""
        return self.vkms_mid - self.dvkms

    @property
    def vkms_hi(self) -> np.ndarray:
        """The higher speed of each window, in km/s."""
        return self.vkms_mid + self.dvkms


def spp_swp_spc_voltwin2kmswin(volt_hi: np.ndarray, volt_lo: np.ndarray) -> KmsWindow:
    """
    Convert sinusoidal voltage windows into proton speed windows.

    Writing the voltage as ``V(t) = A (1 - m sin²(ωt))``, the average
    proton speed over the window is ``<v> = c sqrt(A) E(m) / (π/2)``,
    where ``E`` is the complete elliptic integral of the second kind,
    evaluated with Hastings' polynomial approximation, and the speed
    amplitude is ``sqrt(2 (c² V_mid - <v>²))``.

    Parameters
    ----------
    volt_hi : numpy.ndarray
        The higher voltage of each window, in volts.
    volt_lo : numpy.ndarray
        The lower voltage of each window, in volts.

    Returns
    -------
    KmsWindow
        The middle voltages, widths, average speeds, and speed amplitudes.

    Notes
    -----
    Only the ``volt_hi`` and ``volt_lo`` inputs of the IDL procedure are
    supported, since the L1 to L2 step does not use the others.

    Hastings' approximation to ``E(m)`` is from C. Hastings, *Approximations
    for Digital Computers* (Princeton University Press, 1955), as tabulated
    in Abramowitz & Stegun (1964), eq. 17.3.36, with ``m1 = 1 - m``. The
    IDL source does not cite it. As in IDL, ``A`` is the larger of the two
    voltages and ``m = |V_hi - V_lo| / A``.

    The types are those of IDL: the voltages are ``float32``, ``m1`` and
    the elliptic integral are ``float64``, and ``c * sqrt(A)`` is
    ``float32`` before it is multiplied by them.
    """
    volt_hi = np.asarray(volt_hi, dtype=np.float32)
    volt_lo = np.asarray(volt_lo, dtype=np.float32)
    volt_mid = (volt_hi + volt_lo) / np.float32(2.0)
    dvolt = np.abs(volt_hi - volt_lo)
    with np.errstate(invalid="ignore", divide="ignore"):
        # IDL's > operator ignores a NaN operand
        a = np.fmax(volt_hi, volt_lo)
        m = dvolt / a
        m1 = 1.0 - m.astype(np.float64)
        ee1 = 1.0 + m1 * (_A[0] + m1 * (_A[1] + m1 * (_A[2] + m1 * _A[3])))
        ee2 = m1 * (_B[0] + m1 * (_B[1] + m1 * (_B[2] + m1 * _B[3]))) * np.log(1.0 / m1)
        ellec = ee1 + ee2
        vkms_mid = (_C * np.sqrt(a)).astype(np.float64) * ellec / (np.pi / 2.0)
        dvkms = np.sqrt(2.0 * ((_C**2 * volt_mid).astype(np.float64) - vkms_mid**2))
    return KmsWindow(volt_mid=volt_mid, dvolt=dvolt, vkms_mid=vkms_mid, dvkms=dvkms)
