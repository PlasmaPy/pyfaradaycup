"""Test converting energy per charge into speed with ``spp_swp_spc_ev2kms``."""

from __future__ import annotations

import numpy as np
import scipy.constants

from pyfaradaycup.l1_to_l2._spp_swp_spc_ev2kms import spp_swp_spc_ev2kms


def test_ev2kms_proton() -> None:
    """
    The speed is ``sqrt(2 e V / m_p)``. The elementary charge hard-coded
    in IDL is larger than that of CODATA 2018 by 8 parts in 10⁶, so the
    speeds are larger by 4 parts in 10⁶.
    """
    ev = np.array([10.0, 1000.0, 8000.0])
    expected = 1e-3 * np.sqrt(2 * scipy.constants.e * ev / scipy.constants.m_p)
    np.testing.assert_allclose(spp_swp_spc_ev2kms(ev), expected, rtol=4.5e-6)
    assert np.all(spp_swp_spc_ev2kms(ev) > expected)


def test_ev2kms_alpha() -> None:
    """An alpha particle (z = 2, a = 4) is slower than a proton by ``sqrt(2)``."""
    np.testing.assert_allclose(
        spp_swp_spc_ev2kms(1000.0, z=2, a=4),
        spp_swp_spc_ev2kms(1000.0) / np.sqrt(2),
        rtol=1e-15,
    )


def test_ev2kms_zero_keywords() -> None:
    """``z`` and ``a`` of 0 are taken as 1, since IDL uses ``keyword_set``."""
    assert spp_swp_spc_ev2kms(500.0, z=0, a=0) == spp_swp_spc_ev2kms(500.0)


def test_ev2kms_single_precision() -> None:
    """Single precision voltages give the same double precision speeds as in IDL."""
    ev = np.array([123.4, 5678.9], dtype=np.float32)
    result = spp_swp_spc_ev2kms(ev)
    assert result.dtype == np.float64
    np.testing.assert_array_equal(result, spp_swp_spc_ev2kms(ev.astype(np.float64)))
