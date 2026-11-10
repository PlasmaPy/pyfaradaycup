"""Test command line tools."""

import hashlib
import logging
import re
from pathlib import Path
from typing import Any

import cdflib.xarray
import click
import pytest
import pytest_check
import spiceypy
import xarray
from click.testing import CliRunner

from pyfaradaycup.decommutator import l0_to_l05
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
            f"--l05dir={l05dir}",
            f"--logdir={logdir}",
            "-v",
            l0file,
        ],
        catch_exceptions=False,
    )

    assert result.exit_code == 0, result.output

    apids = ["351", "352", "353", "354", "35E", "35F"]

    # With -v, progress is printed to the screen as well as the log file
    assert "INFO: Wrote" in result.output
    (log_file,) = tmp_path.glob("*.log")
    assert re.fullmatch(rf"l0_to_l05_{tag}_\d{{8}}T\d{{6}}Z\.log", log_file.name)
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
        [f"--l05dir={tmp_path}", f"--logdir={tmp_path}", str(missing_file)],
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
    result = CliRunner().invoke(pfc_decommutator, ["-v", "-q", str(tmp_path / "l0")])
    assert result.exit_code == click.UsageError.exit_code
    assert "cannot be used together" in result.output
    assert not list(tmp_path.glob("*.log"))


def test_pfc_decommutator_missing_l0file(tmp_path: Path) -> None:
    """Test that L0FILE is a required positional argument."""
    result = CliRunner().invoke(pfc_decommutator, [f"--logdir={tmp_path}"])
    assert result.exit_code == click.UsageError.exit_code
    assert "Missing argument 'L0FILE'" in result.output
    assert not list(tmp_path.glob("*.log"))


def test_pfc_decommutator_l0file_option_removed(tmp_path: Path) -> None:
    """Test that the L0 file can no longer be given with --l0file."""
    result = CliRunner().invoke(
        pfc_decommutator, [f"--logdir={tmp_path}", f"--l0file={l0file}"]
    )
    assert result.exit_code == click.UsageError.exit_code
    # The message is "No such option: --l0file" for click < 8.2
    assert re.search(r"No such option:? '?--l0file", result.output)
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
        _warn_about_ineffective_options(recursive=True, ptp=True, spacecraft=False)
    assert caplog.messages == [
        "-r/--recursive is not implemented; only L0FILE will be converted",
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
    result = l0_to_l05.main(l0file, tmp_path / "l05")

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


def test_main_overwrite_messages(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """
    Test that a CDF file that is written for the first time gets an INFO
    message that it was written, and that an overwritten CDF file gets an
    INFO message that it is being overwritten, but the message that it
    was written is logged only at the DEBUG level.
    """
    result = l0_to_l05.main(l0file, tmp_path, apidreq=0x352)
    (cdf_file,) = result.cdf_files.values()
    with caplog.at_level(logging.DEBUG, logger="pyfaradaycup"):
        l0_to_l05.main(l0file, tmp_path, apidreq=0x352, overwrite=True)

    def messages(level: int) -> list[str]:
        return [r.getMessage() for r in caplog.records if r.levelno == level]

    assert f"Overwriting existing L0.5 CDF file {cdf_file}" in messages(logging.INFO)
    assert f"Wrote {cdf_file}" not in messages(logging.INFO)
    assert f"Wrote {cdf_file}" in messages(logging.DEBUG)

    caplog.clear()
    cdf_file.unlink()
    with caplog.at_level(logging.DEBUG, logger="pyfaradaycup"):
        l0_to_l05.main(l0file, tmp_path, apidreq=0x352, overwrite=True)
    assert f"Wrote {cdf_file}" in messages(logging.INFO)
    assert not [m for m in caplog.messages if m.startswith("Overwriting")]


def test_pfc_decommutator_failed_apid(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    Test that an APID that cannot be converted is recorded as a failure,
    and gives an exit code of 1.
    """
    missing_skeleton = str(tmp_path / "missing_skeleton.cdf")
    monkeypatch.setattr(
        l0_to_l05, "_get_newest_skeleton", lambda _apid: missing_skeleton
    )
    result = CliRunner().invoke(
        pfc_decommutator,
        [
            f"--l05dir={tmp_path}",
            f"--logdir={tmp_path}",
            "--apid=352",
            str(l0file),
        ],
        catch_exceptions=False,
    )
    assert result.exit_code == 1
    assert f"ERROR: Could not read skeleton file {missing_skeleton}" in result.output
    assert "WARNING: Could not convert 1 APIDs: 0x352" in result.output
    assert not list(tmp_path.glob("*.cdf"))


def _loaded_kernels() -> list[str]:
    """Return the SPICE kernel files that are loaded, in the order loaded."""
    return [spiceypy.kdata(i, "ALL")[0] for i in range(spiceypy.ktotal("ALL"))]


def test_main_unloads_kernels(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Test that the SPICE kernels are loaded while the L0 file is converted,
    and unloaded afterward, so that repeated calls do not add to them.
    """
    loaded_while_reading = []
    read_file = l0_to_l05._read_file

    def spy(**kwargs: Any) -> object:  # ruff:ignore[ANN401]
        loaded_while_reading.extend(_loaded_kernels())
        return read_file(**kwargs)

    monkeypatch.setattr(l0_to_l05, "_read_file", spy)
    before = _loaded_kernels()
    l0_to_l05.main(l0file, tmp_path, apidreq=0x352, overwrite=True)
    l0_to_l05.main(l0file, tmp_path, apidreq=0x352, overwrite=True)

    assert {Path(kernel).suffix for kernel in loaded_while_reading} == {".tls", ".tsc"}
    assert _loaded_kernels() == before


def test_main_unloads_kernels_after_error(tmp_path: Path) -> None:
    """Test that the SPICE kernels are unloaded when the conversion raises."""
    l0_to_l05.main(l0file, tmp_path, apidreq=0x352)
    before = _loaded_kernels()
    with pytest.raises(FileExistsError):
        l0_to_l05.main(l0file, tmp_path, apidreq=0x352)
    assert _loaded_kernels() == before


def test_main_keeps_kernels_loaded_by_caller(tmp_path: Path) -> None:
    """
    Test that a SPICE kernel that the caller loaded stays loaded, even
    though the conversion loads and unloads another copy of it.
    """
    tls = l0_to_l05._get_newest_kernel(tls=True)
    spiceypy.furnsh(tls)
    try:
        before = _loaded_kernels()
        l0_to_l05.main(l0file, tmp_path, apidreq=0x352)
        assert _loaded_kernels() == before
        assert tls in before
    finally:
        spiceypy.unload(tls)
