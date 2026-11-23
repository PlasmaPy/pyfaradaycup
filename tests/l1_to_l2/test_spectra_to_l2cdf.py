"""Test writing spectra into L2 science CDF files, and the routines it uses."""

from __future__ import annotations

import dataclasses
import datetime
import re
from pathlib import Path
from typing import TYPE_CHECKING, Any

import cdflib.xarray
import numpy as np
import pytest
import pytest_check
import xarray
from scipy.io import readsav
from spacepy import pycdf

from pyfaradaycup.l1_to_l2._spp_swp_spc_crosstalk_correction_factor import (
    CROSSTALK_HISTORY,
    spp_swp_spc_crosstalk_correction_factor,
)
from pyfaradaycup.l1_to_l2._spp_swp_spc_get_effective_area import (
    EFFECTIVE_AREA_TABLE,
    spp_swp_spc_get_effective_area,
)
from pyfaradaycup.l1_to_l2._spp_swp_spc_get_startdate import spp_swp_spc_get_startdate
from pyfaradaycup.l1_to_l2._spp_swp_spc_moments import (
    DTOR,
    _at,
    _max_dim2,
    spp_swp_spc_moments,
)
from pyfaradaycup.l1_to_l2._spp_swp_spc_spectra_to_l2cdf import (
    spp_swp_spc_spectra_to_l2cdf,
)
from pyfaradaycup.l1_to_l2._spp_swp_spc_voltwin2kmswin import (
    spp_swp_spc_voltwin2kmswin,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from pyfaradaycup.l1_to_l2._spp_swp_spc_ivt_to_spectra import Spectra

repo_root = Path(__file__).parent.parent.parent
spc_dir = repo_root / "_psp" / "data" / "sci" / "sweap" / "spc"
expected_l2_file = spc_dir / "L2" / "2026" / "08" / "spp_swp_spc_l2_20260803_v00.cdf"
l2_name = Path("2026", "08", "spp_swp_spc_l2_20260803_v00.cdf")


def test_voltwin2kmswin_narrow_window() -> None:
    """
    Test that the average speed of a window of zero width is close to
    c sqrt(V), since E(0) = pi/2, and its amplitude is close to 0.

    The amplitude is sqrt(2 (c² V - <v>²)), which cancels. As in IDL,
    c, c², V, sqrt(V), c sqrt(V), and c² V are float32, so each of these 6
    roundings contributes up to 2**-24 of c² V to the difference.
    """
    window = spp_swp_spc_voltwin2kmswin(
        volt_hi=np.array([1000.0, 2000.0]), volt_lo=np.array([1000.0, 2000.0])
    )
    np.testing.assert_allclose(
        window.vkms_mid, 13.84177 * np.sqrt([1000.0, 2000.0]), rtol=1e-7
    )
    bound = np.sqrt(2 * 6 * 2.0**-24 * 13.84177**2 * np.array([1000.0, 2000.0]))
    assert (window.dvkms <= bound).all()
    assert window.volt_mid.dtype == np.float32
    assert window.vkms_mid.dtype == np.float64


def test_voltwin2kmswin_window() -> None:
    """Test that the speed window brackets the speeds of the voltages at its edges."""
    window = spp_swp_spc_voltwin2kmswin(
        volt_hi=np.array([1100.0]), volt_lo=np.array([900.0])
    )
    assert window.vkms_lo[0] < 13.84177 * np.sqrt(1000.0) < window.vkms_hi[0]
    assert window.vkms_lo[0] < window.vkms_mid[0] < window.vkms_hi[0]
    np.testing.assert_allclose(window.dvolt, 200.0)


def test_max_dim2() -> None:
    """
    Test that, like IDL's max(..., dim=2), NaNs are skipped and the index
    is a subscript into the whole array in column-major order.
    """
    array = np.array([[np.nan, 2.0, 5.0], [7.0, np.nan, 1.0], [np.nan, np.nan, np.nan]])
    value, subscript = _max_dim2(array)
    np.testing.assert_array_equal(value, [5.0, 7.0, np.nan])
    # row + column * nrows
    assert subscript.tolist() == [0 + 2 * 3, 1 + 0 * 3, 2 + 0 * 3]
    # so the next subscript is the next row, in the same column
    np.testing.assert_array_equal(_at(array, subscript[:2] + 1), [1.0, np.nan])
    # and subscripts beyond the array are clipped to its first and last elements
    values = np.arange(6.0).reshape(2, 3)
    assert _at(values, np.array([-5, 0, 1, 5, 99])).tolist() == [
        0.0,
        0.0,
        3.0,
        5.0,
        5.0,
    ]


def test_moments_skips_non_ion_spectra(spectra: Spectra) -> None:
    """Test that the flow angles are NaN for calibration, electron, and flux angle spectra."""
    angles = spp_swp_spc_moments(spectra)
    skipped = (spectra.cal == 1) | (spectra.emode == 1) | (spectra.famode == 1)
    assert skipped.any()
    assert np.isnan(angles.phi[skipped]).all()
    assert np.isnan(angles.theta[skipped]).all()
    assert np.isfinite(angles.phi[~skipped]).mean() > 0.9  # ruff:ignore[PLR2004]
    assert angles.phi.dtype == np.float32
    np.testing.assert_allclose(angles.ew_angle, angles.phi / DTOR)


def test_moments_too_few_spectra(spectra: Spectra) -> None:
    """Test that no flow angles are computed with one ion spectrum or none."""
    one = dataclasses.replace(spectra, cal=np.ones_like(spectra.cal))
    one.cal[0] = 0
    one.emode[:] = 0
    one.famode[:] = 0
    assert np.isnan(spp_swp_spc_moments(one).phi).all()


def test_get_effective_area() -> None:
    """
    Test that the effective area is interpolated in the cold column of
    the table, and is NaN for NaN angles.
    """
    save = readsav(str(EFFECTIVE_AREA_TABLE))
    cold = save["ea"][int(np.argmax(save["machnums"]))]
    alpha = save["alpha"]
    phi = np.radians(np.array([0.0, alpha[3], np.nan]), dtype=np.float64).astype(
        np.float32
    )
    area = spp_swp_spc_get_effective_area(phi, np.zeros(3, dtype=np.float32))
    assert area.dat.dtype == np.float32
    assert area.dat[0] == cold[0]
    np.testing.assert_allclose(area.dat[1], cold[3], rtol=1e-5)
    assert np.isnan(area.dat[2])
    # the incidence angle combines both angles
    both = spp_swp_spc_get_effective_area(phi[1:2], phi[1:2])
    assert both.dat[0] < area.dat[1]


def test_crosstalk_correction_factor(tt2000: Callable[..., int]) -> None:
    """
    Test that the factors are 1 before the history, the last factors
    after it, and interpolated between.
    """
    history = readsav(str(CROSSTALK_HISTORY))["spp_swp_spc_crosstalk_history"][0]
    epoch = history["EPOCH"]
    coupling = history["COUPLING"]
    valid = ~np.isnan(coupling["AA"])
    last = np.flatnonzero(valid)[-1]
    # the north-south factor uses cb twice, as in IDL
    ns_last = np.float32(1.0) / (
        np.float32(1.0)
        - (
            coupling["CA"][last]
            + coupling["DA"][last]
            + coupling["CB"][last]
            + coupling["CB"][last]
        )
    )
    times = np.array([epoch[0] - 1, tt2000(2026, 8, 3), epoch[valid][-1] + 1])
    ew, ns = spp_swp_spc_crosstalk_correction_factor(times)
    assert ew[0] == ns[0] == 1.0
    assert np.isfinite(ew).all()
    assert np.isfinite(ns).all()
    assert ns[2] == ns_last
    assert 0.5 < ew[1] < 2.0  # ruff:ignore[PLR2004]


def test_get_startdate(spectra: Spectra) -> None:
    """Test that the date is that of the earliest time that is not fill."""
    assert spp_swp_spc_get_startdate(spectra) == datetime.date(2026, 8, 3)
    with pytest.raises(ValueError, match="fill"):
        spp_swp_spc_get_startdate(
            dataclasses.replace(spectra, time=np.full_like(spectra.time, spectra.fill))
        )


@pytest.fixture(scope="module")
def l2_file(spectra: Spectra, tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Return the L2 file written from the spectra for 2026-08-03."""
    return spp_swp_spc_spectra_to_l2cdf(spectra, l2dir=tmp_path_factory.mktemp("L2"))


def test_spectra_to_l2cdf_name(l2_file: Path) -> None:
    """Test the name of the L2 file, and that no temporary files are left."""
    assert l2_file.parts[-3:] == l2_name.parts
    assert [path.name for path in l2_file.parent.iterdir()] == [l2_file.name]


def test_spectra_to_l2cdf_matches_idl(
    l2_file: Path, cdf_metadata: Callable[[str], dict[str, Any]]
) -> None:
    """
    Test that the L2 file is the same as the one made in production,
    apart from the time it was made: every value, including the flow
    angles and the differential charge flux density, and the metadata.
    """
    expected = cdflib.xarray.cdf_to_xarray(str(expected_l2_file))
    actual = cdflib.xarray.cdf_to_xarray(str(l2_file))
    for dataset in (expected, actual):
        del dataset.attrs["Generation_date"]
    xarray.testing.assert_identical(actual, expected)
    for name, variable in expected.variables.items():
        with pytest_check.check:
            assert actual[name].dtype == variable.dtype, name

    with (
        pycdf.CDF(str(expected_l2_file)) as cdf_expected,
        pycdf.CDF(str(l2_file)) as cdf_actual,
    ):
        for name in cdf_expected:
            with pytest_check.check:
                np.testing.assert_array_equal(
                    cdf_actual.raw_var(name)[...],
                    cdf_expected.raw_var(name)[...],
                    err_msg=name,
                )

    expected_metadata = cdf_metadata(str(expected_l2_file))
    actual_metadata = cdf_metadata(str(l2_file))
    for metadata in (expected_metadata, actual_metadata):
        ((_, generation_date, _),) = metadata["global_attributes"].pop(
            "Generation_date"
        )
        assert re.fullmatch(
            r"\w{3} \w{3} [ \d]\d \d\d:\d\d:\d\d \d{4}", generation_date
        )
    for key, value in expected_metadata.items():
        with pytest_check.check:
            assert actual_metadata[key] == value, key


def test_spectra_to_l2cdf_versions(spectra: Spectra, tmp_path: Path) -> None:
    """Test that each file for a date gets the next version, as in IDL."""
    month_dir = tmp_path / "2026" / "08"
    month_dir.mkdir(parents=True)
    (month_dir / "spp_swp_spc_l2_20260803_v04.cdf").touch()
    (month_dir / "spp_swp_spc_l2_20260802_v09.cdf").touch()
    first = spp_swp_spc_spectra_to_l2cdf(spectra, l2dir=tmp_path)
    assert first.name == "spp_swp_spc_l2_20260803_v05.cdf"
    second = spp_swp_spc_spectra_to_l2cdf(spectra, l2dir=tmp_path)
    assert second.name == "spp_swp_spc_l2_20260803_v06.cdf"


def test_spectra_to_l2cdf_savefile_exists(spectra: Spectra, tmp_path: Path) -> None:
    """Test that an existing savefile is not replaced."""
    savefile = tmp_path / "out.cdf"
    savefile.write_bytes(b"existing")
    with pytest.raises(FileExistsError):
        spp_swp_spc_spectra_to_l2cdf(spectra, l2dir=tmp_path, savefile=savefile)
    assert savefile.read_bytes() == b"existing"
