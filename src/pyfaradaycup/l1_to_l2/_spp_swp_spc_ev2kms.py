"""Port of ``spp_swp_spc_ev2kms.pro``."""

from __future__ import annotations

__all__ = ["spp_swp_spc_ev2kms"]

import numpy as np

Q0 = 1.6021892e-19
"""
The elementary charge in C, as hard-coded in IDL.

This is the CODATA 1973 value; CODATA 2018 has exactly 1.602176634e-19.
"""

MP = 1.67262178e-27
"""
The proton mass in kg, as hard-coded in IDL.

This is smaller than the 1.67262192369e-27 of CODATA 2018 by 9 parts in
10⁸.
"""


def spp_swp_spc_ev2kms(
    ev: np.ndarray | float, *, z: float | None = None, a: float | None = None
) -> np.ndarray:
    """
    Return the speed in km/s of an ion whose energy per charge is ``ev``.

    This is the nonrelativistic speed ``v = sqrt(2 * z * e * V / (a * m_p))``
    of an ion with charge ``z * e`` and mass ``a * m_p`` whose kinetic
    energy ``a * m_p * v**2 / 2`` equals ``z * e * V``.

    Parameters
    ----------
    ev : numpy.ndarray or float
        The energy per charge, in V (or eV for a singly charged ion).
    z : float, optional
        The charge number. Defaults to 1, and so does 0, since IDL uses
        ``keyword_set``.
    a : float, optional
        The mass in units of the proton mass. Defaults to 1, and so does
        0, since IDL uses ``keyword_set``.

    Returns
    -------
    numpy.ndarray
        The speed in km/s, in double precision.

    Notes
    -----
    The elementary charge `Q0` and proton mass `MP` are the values
    hard-coded in IDL rather than those of `astropy.constants`, so that
    the results are the same as in IDL. They differ from CODATA 2018 by
    8 parts in 10⁶ and 9 parts in 10⁸, respectively, so the speeds are
    larger by 4 parts in 10⁶.

    Examples
    --------
    >>> round(float(spp_swp_spc_ev2kms(1000.0)), 3)
    437.696
    """
    z = z or 1.0
    a = a or 1.0
    # As in IDL, z * ev * 2 has the type of ev, and the multiplication by
    # the double precision Q0 makes the rest double precision, which
    # NumPy only does for a single precision ev if it is cast first
    zev2 = np.asarray(z * np.asarray(ev) * 2.0, dtype=np.float64)
    return 1e-3 * np.sqrt(zev2 * Q0 / (a * MP))
