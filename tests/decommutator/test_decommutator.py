"""Test command line tools."""

import hashlib
import logging
import re
from pathlib import Path

import cdflib.xarray
import click
import pytest
import pytest_check
import xarray
from click.testing import CliRunner

from pyfaradaycup.decommutator import swp_spc_l0_to_l05
from pyfaradaycup.decommutator.main import (
    _console_level,
    _warn_about_ineffective_options,
    pfc_decommutator,
)

repo_root = Path(__file__).parent.parent.parent
data_dir = repo_root / "tests" / "data"
ssr_dir = data_dir / "sci" / "sweap" / "raw" / "ssr"
l05_dir = data_dir / "sci" / "sweap" / "spc" / "L05"
l0file = ssr_dir / "2026" / "215" / "0523462910_4_EA"


def _sha256(path: Path) -> str:
    """Return the SHA-256 checksum of a file, computed independently of the package."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_pfc_decommutator(tmp_path: Path) -> None:
    """Test the level 0 to level 0.5 step using the click command line tool."""
    tag = "0523462910_4_EA"

    l0file = str(ssr_dir / "2026" / "215" / tag)
    l05dir = str(tmp_path)
    logdir = str(tmp_path)

    result = CliRunner().invoke(
        pfc_decommutator,
        [
            f"--l0file={l0file}",
            f"--l05dir={l05dir}",
            f"--logdir={logdir}",
            "-v",
        ],
        catch_exceptions=False,
    )

    assert result.exit_code == 0, result.output

    apids = ["351", "352", "353", "354", "35E", "35F"]

    # With -v, progress is printed to the screen as well as the log file
    assert "INFO: Wrote" in result.output
    (log_file,) = tmp_path.glob("*.log")
    assert re.fullmatch(
        rf"swp_spc_l0_to_l05_{tag}_\d{{8}}T\d{{6}}Z\.log", log_file.name
    )
    log = log_file.read_text(encoding="utf-8")
    for apid in apids:
        assert f"_APID{apid}_L1.cdf" in log
    assert "Running pfc_decommutator with options" in log
    assert f"SHA-256 {_sha256(ssr_dir / '2026' / '215' / tag)}" in log
    assert "Wrote 6 L0.5 CDF files" in log

    for apid in apids:
        cdf_file = f"{tag}_APID{apid}_L1.cdf"

        l05_cdf_expected = str(l05_dir / "2026" / "08" / f"APID{apid}" / cdf_file)
        l05_cdf_actual = str(tmp_path / cdf_file)

        # Use unix time so that time is given as a number rather than a datetime.
        expected = cdflib.xarray.cdf_to_xarray(l05_cdf_expected, to_unixtime=True)
        actual = cdflib.xarray.cdf_to_xarray(l05_cdf_actual, to_unixtime=True)

        with pytest_check.check:
            xarray.testing.assert_allclose(actual, expected, atol=0, rtol=0)


def test_pfc_decommutator_logs_exception(tmp_path: Path) -> None:
    """
    Test that an error is logged with its traceback, and that the exit
    code is nonzero.
    """
    missing_file = tmp_path / "missing_l0_file"
    result = CliRunner().invoke(
        pfc_decommutator,
        [f"--l0file={missing_file}", f"--l05dir={tmp_path}", f"--logdir={tmp_path}"],
        catch_exceptions=False,
    )
    assert result.exit_code == 1
    assert f"ERROR: Could not convert {missing_file}" in result.output
    (log_file,) = tmp_path.glob("*.log")
    log = log_file.read_text(encoding="utf-8")
    assert "Traceback" in log
    assert "RuntimeError: Could not read L0 file" in log


def test_pfc_decommutator_verbose_and_quiet(tmp_path: Path) -> None:
    """Test that -v and -q cannot be used together."""
    result = CliRunner().invoke(
        pfc_decommutator, [f"--l0file={tmp_path / 'l0'}", "-v", "-q"]
    )
    assert result.exit_code == click.UsageError.exit_code
    assert "cannot be used together" in result.output
    assert not list(tmp_path.glob("*.log"))


@pytest.mark.parametrize(
    ("verbose", "quiet", "expected"),
    [
        (0, False, logging.WARNING),
        (1, False, logging.INFO),
        (2, False, logging.DEBUG),
        (3, False, logging.DEBUG),
        (0, True, logging.ERROR),
    ],
)
def test_console_level(*, verbose: int, quiet: bool, expected: int) -> None:
    """Test the console level for each combination of -v and -q."""
    assert _console_level(verbose=verbose, quiet=quiet) == expected


def test_warn_about_ineffective_options(caplog: pytest.LogCaptureFixture) -> None:
    """Test that options with no effect are logged as warnings."""
    with caplog.at_level(logging.WARNING, logger="pyfaradaycup"):
        _warn_about_ineffective_options(
            batch=True, recursive=False, l0dir=None, ptp=True, spacecraft=False
        )
    assert caplog.messages == [
        "-b/--batch is not implemented; only --l0file will be converted",
        "-p/--ptp is ignored unless -sc/--spacecraft is also given",
    ]


def test_main_returns_result(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """
    Test that converting from Python returns what was written and the
    inputs used, and that nothing is printed and no log file is written
    when logging is not configured.
    """
    monkeypatch.chdir(tmp_path)
    result = swp_spc_l0_to_l05.main(l0file, tmp_path / "l05")

    assert capsys.readouterr() == ("", "")
    assert not list(tmp_path.rglob("*.log"))

    apids = {0x351, 0x352, 0x353, 0x354, 0x35E, 0x35F}
    assert result.succeeded
    assert result.failures == {}
    assert set(result.cdf_files) == apids
    assert all(path.is_file() for path in result.cdf_files.values())
    assert set(result.skeletons) == apids
    assert all(result.packet_counts[apid] > 0 for apid in apids)
    assert result.l0file == l0file
    assert result.l0file_sha256 == _sha256(l0file)
    assert [path.suffix for path in result.kernels] == [".tls", ".tsc"]
    assert set(result.software_versions) == {
        "Python",
        "pyfaradaycup",
        "numpy",
        "spacepy",
        "spiceypy",
    }
    assert result.elapsed > 0


def test_pfc_decommutator_failed_apid(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    Test that an APID that cannot be converted is recorded as a failure,
    and gives an exit code of 1.
    """
    missing_skeleton = str(tmp_path / "missing_skeleton.cdf")
    monkeypatch.setattr(
        swp_spc_l0_to_l05, "_get_newest_skeleton", lambda _apid: missing_skeleton
    )
    result = CliRunner().invoke(
        pfc_decommutator,
        [
            f"--l0file={l0file}",
            f"--l05dir={tmp_path}",
            f"--logdir={tmp_path}",
            "--apid=352",
        ],
        catch_exceptions=False,
    )
    assert result.exit_code == 1
    assert f"ERROR: Could not read skeleton file {missing_skeleton}" in result.output
    assert "WARNING: Could not convert 1 APIDs: 0x352" in result.output
    assert not list(tmp_path.glob("*.cdf"))
