"""Test command line tools."""

import os
import subprocess
import sys


from collections.abc import Generator
from pathlib import Path

import cdflib.xarray
import xarray

repo_root = Path(__file__).parent.parent.parent
data_dir = repo_root / "tests" / "data"
ssr_dir = data_dir / "sci" / "sweap" / "raw" / "ssr"
l05_dir = data_dir / "sci" / "sweap" / "spc" / "L05"

l0_l05_executable = str(
    repo_root / "src" / "pyfaradaycup" / "pipeline" / "swp_spc_l02l1.py"
)


def test_l0_l05(tmp_path: Path) -> None:  # noqa: ANN001
    """Test the level 0 to level 0.5 step."""
    tag = "0523462910_4_EA"
    apid = "351"

    l0file = str(ssr_dir / "2026" / "215" / tag)
    l1dir = str(tmp_path)
    logdir = str(tmp_path)

    subprocess.run(  # noqa: S603
        [
            sys.executable,
            l0_l05_executable,
            f"--l0file={l0file}",
            f"--l1dir={l1dir}",
            f"--logdir={logdir}",
            "-v",
        ],
        env={**os.environ, "PSP_DATA_DIR": str(data_dir)},
        check=True,
    )

    cdf_file = f"{tag}_APID{apid}_L1.cdf"

    l05_cdf_expected = str(l05_dir / "2026" / "08" / f"APID{apid}" / cdf_file)
    l05_cdf_actual = str(tmp_path / cdf_file)

    # Use unix time so that time is given as a number rather than a datetime.
    expected = cdflib.xarray.cdf_to_xarray(l05_cdf_expected, to_unixtime=True)
    actual = cdflib.xarray.cdf_to_xarray(l05_cdf_actual, to_unixtime=True)

    # Set rtol > 0 because of a 100 μs discrepancy for the epoch.
    xarray.testing.assert_allclose(actual, expected, atol=0, rtol=1e-13)
