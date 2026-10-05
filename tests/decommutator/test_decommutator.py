"""Test command line tools."""

from pathlib import Path

import cdflib.xarray
import pytest_check
import xarray
from click.testing import CliRunner

from pyfaradaycup.decommutator.main import pfc_decommutator

repo_root = Path(__file__).parent.parent.parent
data_dir = repo_root / "tests" / "data"
ssr_dir = data_dir / "sci" / "sweap" / "raw" / "ssr"
l05_dir = data_dir / "sci" / "sweap" / "spc" / "L05"


def test_pfc_decommutator(tmp_path: Path) -> None:
    """Test the level 0 to level 0.5 step using the click command line tool."""
    tag = "0523462910_4_EA"

    l0file = str(ssr_dir / "2026" / "215" / tag)
    l1dir = str(tmp_path)
    logdir = str(tmp_path)

    result = CliRunner().invoke(
        pfc_decommutator,
        [
            f"--l0file={l0file}",
            f"--l1dir={l1dir}",
            f"--logdir={logdir}",
            "-v",
        ],
        env={"PSP_DATA_DIR": str(data_dir)},
        catch_exceptions=False,
    )

    assert result.exit_code == 0, result.output

    apids = ["351", "352", "353", "354", "35E", "35F"]

    for apid in apids:
        cdf_file = f"{tag}_APID{apid}_L1.cdf"

        l05_cdf_expected = str(l05_dir / "2026" / "08" / f"APID{apid}" / cdf_file)
        l05_cdf_actual = str(tmp_path / cdf_file)

        # Use unix time so that time is given as a number rather than a datetime.
        expected = cdflib.xarray.cdf_to_xarray(l05_cdf_expected, to_unixtime=True)
        actual = cdflib.xarray.cdf_to_xarray(l05_cdf_actual, to_unixtime=True)

        with pytest_check.check:
            xarray.testing.assert_allclose(actual, expected, atol=0, rtol=0)
