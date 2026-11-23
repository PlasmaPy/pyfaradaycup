"""Test command line tools."""

from __future__ import annotations

import gzip
import hashlib
import json
import logging
import pickle
import re
import shutil
from pathlib import Path
from typing import TYPE_CHECKING, Any

import cdflib.xarray
import click
import pytest
import pytest_check
import spiceypy
import xarray
from click.testing import CliRunner
from spacepy import pycdf

from pyfaradaycup.decommutator import (
    DecommutationError,
    DecommutationResult,
    NoPacketsError,
    _l0_to_l05,
    l0_to_l05,
    main,
)
from pyfaradaycup.decommutator.main import (
    EXIT_FAILURE,
    EXIT_NO_PACKETS,
    _l0_files,
    _warn_about_ineffective_options,
    pfc_decommutator,
)

if TYPE_CHECKING:
    from collections.abc import Callable

repo_root = Path(__file__).parent.parent.parent
data_dir = repo_root / "_psp" / "data"
ssr_dir = data_dir / "sci" / "sweap" / "raw" / "ssr"
l05_dir = data_dir / "sci" / "sweap" / "spc" / "L05"
l0file = ssr_dir / "2026" / "215" / "0523462910_4_EA"


def _sha256(path: Path) -> str:
    """Return the SHA-256 checksum of a file, computed independently of the package."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_pfc_decommutator(
    tmp_path: Path, cdf_metadata: Callable[[str], dict[str, Any]]
) -> None:
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
        l05_cdf_actual = str(tmp_path / f"APID{apid}" / cdf_file)

        # Keep times as datetime64[ns] rather than converting to unix time,
        # which cdflib rounds to the nearest microsecond, so that the full
        # nanosecond precision of CDF_TIME_TT2000 is compared.
        expected = cdflib.xarray.cdf_to_xarray(l05_cdf_expected)
        actual = cdflib.xarray.cdf_to_xarray(l05_cdf_actual)

        with pytest_check.check:
            xarray.testing.assert_allclose(actual, expected, atol=0, rtol=0)

        # assert_allclose ignores attributes, which hold the CDF global and
        # variable attributes, and neither assertion compares dtypes.
        with pytest_check.check:
            xarray.testing.assert_identical(actual, expected)
        for name, variable in expected.variables.items():
            with pytest_check.check:
                assert actual[name].dtype == variable.dtype, (apid, name)

        # Compare the CDF metadata that is lost in the conversion to xarray.
        expected_metadata = cdf_metadata(l05_cdf_expected)
        actual_metadata = cdf_metadata(l05_cdf_actual)
        for key, value in expected_metadata.items():
            with pytest_check.check:
                assert actual_metadata[key] == value, (apid, key)


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


def test_pfc_decommutator_directory(tmp_path: Path) -> None:
    """
    Test that every L0 file directly in a directory is
    converted, each with its own log file, and that other files and
    subdirectories are skipped.
    """
    indir = tmp_path / "l0"
    (indir / "subdir").mkdir(parents=True)
    tags = ["0523462910_4_EA", "0523462910_5_EA"]
    for tag in tags:
        shutil.copy(l0file, indir / tag)
    shutil.copy(l0file, indir / "0523462910_6_EA.bak")
    shutil.copy(l0file, indir / "subdir" / "0523462910_7_EA")
    (indir / "0523462910_8_EA").mkdir()

    l05dir = tmp_path / "l05"
    logdir = tmp_path / "logs"
    result = CliRunner().invoke(
        pfc_decommutator,
        [f"--l05dir={l05dir}", f"--logdir={logdir}", "--apid=352", str(indir)],
        catch_exceptions=False,
    )

    assert result.exit_code == 0, result.output
    assert sorted(path.name for path in l05dir.rglob("*.cdf")) == [
        f"{tag}_APID352_L1.cdf" for tag in tags
    ]
    log_files = sorted(logdir.glob("*.log"))
    assert [path.name.rsplit("_", 1)[0] for path in log_files] == [
        f"l0_to_l05_{tag}" for tag in tags
    ]


def test_pfc_decommutator_directory_continues_after_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    Test that an L0 file in a directory that cannot be converted does
    not stop the next one from being converted, and that the exit code
    is nonzero.
    """
    indir = tmp_path / "l0"
    indir.mkdir()
    bad_file = indir / "0000000000_0_EA"
    shutil.copy(l0file, bad_file)
    shutil.copy(l0file, indir / l0file.name)

    def fail_for_bad_file(l0file: Path, **kwargs: Any) -> DecommutationResult:  # ruff:ignore[ANN401]
        if l0file == bad_file:
            msg = "made-up error while converting"
            raise RuntimeError(msg)
        return l0_to_l05(l0file, **kwargs)

    monkeypatch.setattr(main, "l0_to_l05", fail_for_bad_file)

    result = CliRunner().invoke(
        pfc_decommutator,
        [f"--l05dir={tmp_path}", f"--logdir={tmp_path}", "--apid=352", str(indir)],
        catch_exceptions=False,
    )

    assert result.exit_code == EXIT_FAILURE
    assert f"Could not convert {bad_file}" in result.output
    assert [path.name for path in tmp_path.rglob("*.cdf")] == [
        f"{l0file.name}_APID352_L1.cdf"
    ]
    log_files = sorted(path.name for path in tmp_path.glob("*.log"))
    assert [name.rsplit("_", 1)[0] for name in log_files] == [
        "l0_to_l05_0000000000_0_EA",
        f"l0_to_l05_{l0file.name}",
    ]


@pytest.mark.parametrize(
    ("with_failure", "expected_exit_code"),
    [(False, EXIT_NO_PACKETS), (True, EXIT_FAILURE)],
)
def test_pfc_decommutator_directory_no_packets(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    with_failure: bool,
    expected_exit_code: int,
) -> None:
    """
    Test that an L0 file with no packets in a directory does not stop the
    other L0 files from being converted, and that the exit code is
    EXIT_NO_PACKETS, unless another L0 file could not be converted, in
    which case it is EXIT_FAILURE.
    """
    indir = tmp_path / "l0"
    indir.mkdir()
    (indir / "0000000000_0_EA").write_bytes(b"not an L0 file")
    shutil.copy(l0file, indir / l0file.name)
    if with_failure:
        bad_file = indir / "0000000000_1_EA"
        shutil.copy(l0file, bad_file)

        def fail_for_bad_file(l0file: Path, **kwargs: Any) -> DecommutationResult:  # ruff:ignore[ANN401]
            if l0file == bad_file:
                msg = "made-up error while converting"
                raise RuntimeError(msg)
            return l0_to_l05(l0file, **kwargs)

        monkeypatch.setattr(main, "l0_to_l05", fail_for_bad_file)

    result = CliRunner().invoke(
        pfc_decommutator,
        [f"--l05dir={tmp_path}", f"--logdir={tmp_path}", "--apid=352", str(indir)],
        catch_exceptions=False,
    )

    assert result.exit_code == expected_exit_code, result.output
    assert "No packets for any supported APID" in result.output
    assert [path.name for path in tmp_path.rglob("*.cdf")] == [
        f"{l0file.name}_APID352_L1.cdf"
    ]


def test_pfc_decommutator_directory_without_l0_files(tmp_path: Path) -> None:
    """Test that a directory with no L0 files is an error."""
    (tmp_path / "README.md").write_text("Not an L0 file", encoding="utf-8")
    (tmp_path / "31f_531_EA").write_text("Not an L0 file", encoding="utf-8")
    result = CliRunner().invoke(
        pfc_decommutator, [f"--logdir={tmp_path}", str(tmp_path)]
    )
    assert result.exit_code == click.ClickException.exit_code
    assert "No L0 files with names like 0523462910_4_EA" in result.output
    assert f"in directory {tmp_path}" in result.output
    assert not list(tmp_path.glob("*.log"))


def test_l0_files_names(tmp_path: Path) -> None:
    """
    Test that only files whose whole names are digits, an underscore,
    digits, an underscore, and two capital letters are found in a directory.
    """
    matching = ["13531_53_EA", "0523462910_4_EA", "0523462910_4_FG", "1_2_ZZ"]
    not_matching = [
        "31f_531_EA",
        "351_3EA",
        "_53_EA",
        "13531__EA",
        "13531_53_ea",
        "13531_53_Ea",
        "13531_53_E",
        "13531_53_E1",
        "13531_53_\N{LATIN CAPITAL LETTER E WITH ACUTE}A",
        "13531_53_EA.gz",
        "13531_53_EAX",
        "x13531_53_EA",
        "13531_53_1_EA",
        "\N{ARABIC-INDIC DIGIT ONE}_53_EA",
    ]
    for name in matching + not_matching:
        (tmp_path / name).touch()
    assert _l0_files(tmp_path) == sorted(tmp_path / name for name in matching)


def test_l0_files_single_file(tmp_path: Path) -> None:
    """Test that a path that is not a directory is returned as is, whatever its name."""
    path = tmp_path / "not_an_l0_name.dat"
    assert _l0_files(path) == [path]


def test_pfc_decommutator_verbose_and_quiet(tmp_path: Path) -> None:
    """Test that -v and -q cannot be used together."""
    result = CliRunner().invoke(pfc_decommutator, ["-v", "-q", str(tmp_path / "l0")])
    assert result.exit_code == click.UsageError.exit_code
    assert "cannot be used together" in result.output
    assert not list(tmp_path.glob("*.log"))


def test_pfc_decommutator_missing_l0file(tmp_path: Path) -> None:
    """Test that L0PATH is a required positional argument."""
    result = CliRunner().invoke(pfc_decommutator, [f"--logdir={tmp_path}"])
    assert result.exit_code == click.UsageError.exit_code
    assert "Missing argument 'L0PATH'" in result.output
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


def test_warn_about_ineffective_options(caplog: pytest.LogCaptureFixture) -> None:
    """Test that options with no effect are logged as warnings."""
    with caplog.at_level(logging.WARNING, logger="pyfaradaycup"):
        _warn_about_ineffective_options(recursive=True)
    assert caplog.messages == [
        "-r/--recursive is not implemented; subdirectories will not be searched",
    ]


@pytest.mark.parametrize("ptp", [True, False])
def test_l0_to_l05_warns_about_ptp(
    tmp_path: Path, caplog: pytest.LogCaptureFixture, *, ptp: bool
) -> None:
    """
    Test that ``ptp=True`` without ``spacecraft=True`` is logged as a
    warning when converting from Python, since it has no effect.
    """
    message = "ptp=True is ignored unless spacecraft=True"
    with caplog.at_level(logging.WARNING, logger="pyfaradaycup"):
        l0_to_l05(l0file, l05dir=tmp_path, ptp=ptp, apidreq=0x352)
    assert (message in caplog.messages) is ptp


def test_l0_to_l05_returns_result(
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
    result = l0_to_l05(l0file, l05dir=tmp_path / "l05")

    assert capsys.readouterr() == ("", "")
    assert not list(tmp_path.rglob("*.log"))

    apids = {0x351, 0x352, 0x353, 0x354, 0x35E, 0x35F}
    assert result.succeeded
    assert result.failures == {}
    assert set(result.cdf_files) == apids
    assert all(path.is_file() for path in result.cdf_files.values())
    for apid, path in result.cdf_files.items():
        assert path == (
            tmp_path
            / "l05"
            / f"APID{apid:03X}"
            / f"{l0file.name}_APID{apid:03X}_L1.cdf"
        )
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
    json.dumps(result.to_metadata())


def test_l0_to_l05_overwrite_messages(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """
    Test that a CDF file that is written for the first time gets an INFO
    message that it was written, and that an overwritten CDF file gets an
    INFO message that it is being overwritten, but the message that it
    was written is logged only at the DEBUG level.
    """
    result = l0_to_l05(l0file, l05dir=tmp_path, apidreq=0x352)
    (cdf_file,) = result.cdf_files.values()
    with caplog.at_level(logging.DEBUG, logger="pyfaradaycup"):
        l0_to_l05(l0file, l05dir=tmp_path, apidreq=0x352, overwrite=True)

    def messages(level: int) -> list[str]:
        return [r.getMessage() for r in caplog.records if r.levelno == level]

    assert f"Overwriting existing L0.5 CDF file {cdf_file}" in messages(logging.INFO)
    assert f"Wrote {cdf_file}" not in messages(logging.INFO)
    assert f"Wrote {cdf_file}" in messages(logging.DEBUG)

    caplog.clear()
    cdf_file.unlink()
    with caplog.at_level(logging.DEBUG, logger="pyfaradaycup"):
        l0_to_l05(l0file, l05dir=tmp_path, apidreq=0x352, overwrite=True)
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
        _l0_to_l05, "_get_newest_skeleton", lambda _apid: missing_skeleton
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


def _result(**changes: object) -> DecommutationResult:
    """Return a `DecommutationResult` made up for testing, with ``changes``."""
    fields = {
        "l0file": Path("/l0/0523462910_4_EA"),
        "l0file_sha256": "0123abcd",
        "cdf_files": {0x352: Path("/l05/0523462910_4_EA_APID352_L1.cdf")},
        "failures": {},
        "packet_counts": {0x352: 7, 0x35E: 3},
        "kernels": (Path("/k/naif0012.tls"), Path("/k/spp_sclk.tsc")),
        "skeletons": {0x352: Path("/s/apid352.cdf")},
        "software_versions": {"Python": "3.14.0", "pyfaradaycup": "0.1.0"},
        "hostname": "example",
        "elapsed": 1.5,
    }
    fields.update(changes)
    return DecommutationResult(**fields)


def test_raise_for_failures_when_succeeded() -> None:
    """Test that a result with no failures does not raise."""
    _result().raise_for_failures()


def test_raise_for_failures() -> None:
    """
    Test that a result with failures raises an exception that lists each
    failed APID with its reason, and keeps the result.
    """
    result = _result(failures={0x35E: "Could not find skeleton file"})
    with pytest.raises(DecommutationError) as excinfo:
        result.raise_for_failures()
    assert str(excinfo.value) == (
        f"Could not convert 1 APIDs from {result.l0file}: "
        "0x35E: Could not find skeleton file"
    )
    assert excinfo.value.result is result
    assert isinstance(excinfo.value, RuntimeError)


def test_decommutation_error_pickle() -> None:
    """
    Test that the exception survives being pickled, as when it is sent
    from a worker process.
    """
    error = DecommutationError(_result(failures={0x352: "reason"}))
    unpickled = pickle.loads(pickle.dumps(error))  # ruff:ignore[S301]
    assert str(unpickled) == str(error)
    assert unpickled.result == error.result


def test_no_packets_error_pickle() -> None:
    """Test that NoPacketsError survives being pickled."""
    error = NoPacketsError(Path("/l0/0523462910_4_EA"), {0x352: 0})
    unpickled = pickle.loads(pickle.dumps(error))  # ruff:ignore[S301]
    assert str(unpickled) == str(error)
    assert unpickled.l0file == error.l0file
    assert unpickled.packet_counts == error.packet_counts


@pytest.mark.parametrize("contents", [b"", b"not an L0 file" * 100])
def test_l0_to_l05_no_packets(tmp_path: Path, contents: bytes) -> None:
    """
    Test that an L0 file with no packets raises NoPacketsError, writes
    no CDF files, and unloads the SPICE kernels.
    """
    bad_file = tmp_path / "0000000000_0_EA"
    bad_file.write_bytes(contents)
    l05dir = tmp_path / "l05"
    with pytest.raises(NoPacketsError, match="No packets for any supported APID") as e:
        l0_to_l05(bad_file, l05dir=l05dir)
    assert e.value.l0file == bad_file
    assert not any(e.value.packet_counts.values())
    assert not l05dir.exists()
    assert _loaded_kernels() == []


def test_l0_to_l05_only_unsupported_packets(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    Test that an L0 file whose only packets are for APIDs that have no
    CDF procedure, like 0x07B, raises NoPacketsError.
    """
    l0data = {0x07B: {"MET": [1, 2, 3]}, 0x352: {"MET": []}}
    monkeypatch.setattr(_l0_to_l05, "_read_file", lambda **_: l0data)
    with pytest.raises(NoPacketsError) as e:
        l0_to_l05(l0file, l05dir=tmp_path)
    assert e.value.packet_counts == {0x07B: 3, 0x352: 0}
    assert not list(tmp_path.rglob("*.cdf"))


def test_pfc_decommutator_no_packets(tmp_path: Path) -> None:
    """
    Test that the command line tool exits with EXIT_NO_PACKETS, and logs
    the error without a traceback, when the L0 file has no packets.
    """
    bad_file = tmp_path / "0000000000_0_EA"
    bad_file.write_bytes(b"not an L0 file")
    result = CliRunner().invoke(
        pfc_decommutator,
        [f"--l05dir={tmp_path}", f"--logdir={tmp_path}", str(bad_file)],
        catch_exceptions=False,
    )
    # The value is documented, so check it rather than only the constant
    assert result.exit_code == EXIT_NO_PACKETS == 65  # ruff:ignore[PLR2004]
    assert (
        f"ERROR: Could not convert {bad_file}: No packets for any supported "
        f"APID in L0 file {bad_file}"
    ) in result.output
    (log_file,) = tmp_path.glob("*.log")
    log = log_file.read_text(encoding="utf-8")
    assert "No packets for any supported APID" in log
    assert "Traceback" not in log
    assert not list(tmp_path.rglob("*.cdf"))


def test_to_metadata() -> None:
    """
    Test that the metadata has strings in place of paths and APIDs, and
    can be serialized as JSON.

    Paths are compared with ``str(Path(...))`` because the separator
    depends on the operating system.
    """
    metadata = _result(failures={0x35E: "reason"}).to_metadata()
    assert json.loads(json.dumps(metadata)) == {
        "l0file": str(Path("/l0/0523462910_4_EA")),
        "l0file_sha256": "0123abcd",
        "succeeded": False,
        "cdf_files": {"0x352": str(Path("/l05/0523462910_4_EA_APID352_L1.cdf"))},
        "failures": {"0x35E": "reason"},
        "packet_counts": {"0x352": 7, "0x35E": 3},
        "kernels": [str(Path("/k/naif0012.tls")), str(Path("/k/spp_sclk.tsc"))],
        "skeletons": {"0x352": str(Path("/s/apid352.cdf"))},
        "software_versions": {"Python": "3.14.0", "pyfaradaycup": "0.1.0"},
        "hostname": "example",
        "elapsed": 1.5,
    }


@pytest.mark.parametrize("raise_on_failure", [True, False])
def test_l0_to_l05_raise_on_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, raise_on_failure: bool
) -> None:
    """
    Test that an APID that cannot be converted raises an exception only
    with ``raise_on_failure=True``.
    """
    monkeypatch.setattr(
        _l0_to_l05, "_get_newest_skeleton", lambda _apid: str(tmp_path / "missing")
    )
    if raise_on_failure:
        with pytest.raises(DecommutationError, match="0x352: Could not read skeleton"):
            l0_to_l05(l0file, l05dir=tmp_path, apidreq=0x352, raise_on_failure=True)
    else:
        result = l0_to_l05(l0file, l05dir=tmp_path, apidreq=0x352)
        assert set(result.failures) == {0x352}


def test_l0_to_l05_keyword_only() -> None:
    """Test that only the L0 file can be given by position."""
    with pytest.raises(TypeError):
        l0_to_l05(l0file, ".")  # ty: ignore[too-many-positional-arguments]


def test_pfc_decommutator_matches_l0_to_l05(tmp_path: Path) -> None:
    """
    Test that the command line tool and the function write identical CDF
    files, so that a check or default that differs between them is caught.
    """
    cli_dir = tmp_path / "cli"
    python_dir = tmp_path / "python"
    result = CliRunner().invoke(
        pfc_decommutator,
        [f"--l05dir={cli_dir}", f"--logdir={tmp_path}", str(l0file)],
        catch_exceptions=False,
    )
    assert result.exit_code == 0, result.output
    l0_to_l05(l0file, l05dir=python_dir)

    cli_files = sorted(path.relative_to(cli_dir) for path in cli_dir.rglob("*.cdf"))
    assert cli_files
    assert cli_files == sorted(
        path.relative_to(python_dir) for path in python_dir.rglob("*.cdf")
    )
    for name in cli_files:
        with pytest_check.check:
            assert (cli_dir / name).read_bytes() == (python_dir / name).read_bytes()


def test_pfc_decommutator_gzip(tmp_path: Path) -> None:
    """
    Test that converting a gzipped L0 file with --gzip writes the same
    CDF files, with the same names, as converting the uncompressed file.
    """
    gzipped_l0file = tmp_path / f"{l0file.name}.gz"
    gzipped_l0file.write_bytes(gzip.compress(l0file.read_bytes(), mtime=0))

    # Each run gets its own directories, since the log files would
    # otherwise have the same name if both runs start in the same second.
    plain_dir = tmp_path / "plain"
    gzip_dir = tmp_path / "gzip"
    for outdir, args in (
        (plain_dir, [str(l0file)]),
        (gzip_dir, ["--gzip", str(gzipped_l0file)]),
    ):
        result = CliRunner().invoke(
            pfc_decommutator,
            [f"--l05dir={outdir}", f"--logdir={outdir}", *args],
            catch_exceptions=False,
        )
        assert result.exit_code == 0, result.output

    plain_files = sorted(
        path.relative_to(plain_dir) for path in plain_dir.rglob("*.cdf")
    )
    assert [path.name for path in plain_files] == [
        f"{l0file.name}_APID{apid}_L1.cdf"
        for apid in ["351", "352", "353", "354", "35E", "35F"]
    ]
    assert plain_files == sorted(
        path.relative_to(gzip_dir) for path in gzip_dir.rglob("*.cdf")
    )
    for path in plain_files:
        with pytest_check.check:
            assert (gzip_dir / path).read_bytes() == (plain_dir / path).read_bytes()


def _loaded_kernels() -> list[str]:
    """Return the SPICE kernel files that are loaded, in the order loaded."""
    return [spiceypy.kdata(i, "ALL")[0] for i in range(spiceypy.ktotal("ALL"))]


def test_l0_to_l05_unloads_kernels(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    Test that the SPICE kernels are loaded while the L0 file is converted,
    and unloaded afterward, so that repeated calls do not add to them.
    """
    loaded_while_reading = []
    read_file = _l0_to_l05._read_file

    def spy(**kwargs: Any) -> object:  # ruff:ignore[ANN401]
        loaded_while_reading.extend(_loaded_kernels())
        return read_file(**kwargs)

    monkeypatch.setattr(_l0_to_l05, "_read_file", spy)
    before = _loaded_kernels()
    l0_to_l05(l0file, l05dir=tmp_path, apidreq=0x352, overwrite=True)
    l0_to_l05(l0file, l05dir=tmp_path, apidreq=0x352, overwrite=True)

    assert {Path(kernel).suffix for kernel in loaded_while_reading} == {".tls", ".tsc"}
    assert _loaded_kernels() == before


def test_l0_to_l05_unloads_kernels_after_error(tmp_path: Path) -> None:
    """Test that the SPICE kernels are unloaded when the conversion raises."""
    l0_to_l05(l0file, l05dir=tmp_path, apidreq=0x352)
    before = _loaded_kernels()
    with pytest.raises(FileExistsError):
        l0_to_l05(l0file, l05dir=tmp_path, apidreq=0x352)
    assert _loaded_kernels() == before


def test_l0_to_l05_keeps_kernels_loaded_by_caller(tmp_path: Path) -> None:
    """
    Test that a SPICE kernel that the caller loaded stays loaded, even
    though the conversion loads and unloads another copy of it.
    """
    tls = _l0_to_l05._get_newest_kernel(tls=True)
    spiceypy.furnsh(tls)
    try:
        before = _loaded_kernels()
        l0_to_l05(l0file, l05dir=tmp_path, apidreq=0x352)
        assert _loaded_kernels() == before
        assert tls in before
    finally:
        spiceypy.unload(tls)


def _fail_to_fill(cdf: pycdf.CDF, _dat: object) -> None:
    """Write a global attribute to a CDF, and then fail to fill it."""
    cdf.attrs["Partial"] = "yes"
    msg = "made-up error while filling"
    raise ValueError(msg)


def test_l0_to_l05_deletes_cdf_that_could_not_be_filled(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    Test that a CDF that could not be filled is recorded as a failure
    and deleted, so that a retry without ``overwrite`` converts the APID.
    """
    l1path = tmp_path / "APID352" / "0523462910_4_EA_APID352_L1.cdf"
    with monkeypatch.context() as patch:
        patch.setattr(_l0_to_l05, "_cdf352", _fail_to_fill)
        result = l0_to_l05(l0file, l05dir=tmp_path, apidreq=0x352)

    assert result.failures[0x352].startswith(f"Could not fill {l1path}: ")
    assert "made-up error while filling" in result.failures[0x352]
    assert set(result.cdf_files) == set()
    assert list(l1path.parent.iterdir()) == []

    retry = l0_to_l05(l0file, l05dir=tmp_path, apidreq=0x352)
    assert retry.succeeded
    assert retry.cdf_files == {0x352: l1path}


def test_l0_to_l05_close_error_keeps_fill_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """
    Test that an error from closing a CDF that could not be filled is
    logged, and does not replace the error from filling it.
    """

    def fail_to_close(cdf: pycdf.CDF) -> None:
        cdf.close()
        raise pycdf.CDFError(pycdf.const.CDF_INTERNAL_ERROR)

    monkeypatch.setattr(_l0_to_l05, "_cdf352", _fail_to_fill)
    monkeypatch.setattr(_l0_to_l05, "close_cdf", fail_to_close)
    with caplog.at_level(logging.WARNING, logger=_l0_to_l05.__name__):
        result = l0_to_l05(l0file, l05dir=tmp_path, apidreq=0x352)

    assert "made-up error while filling" in result.failures[0x352]
    assert any(
        record.getMessage().startswith("Could not close") for record in caplog.records
    )
    assert list((tmp_path / "APID352").iterdir()) == []


def _interrupt_filling(cdf: pycdf.CDF, _dat: object) -> None:
    """Write a global attribute to a CDF, and then interrupt filling it."""
    cdf.attrs["Partial"] = "yes"
    raise KeyboardInterrupt


@pytest.mark.parametrize("fill", [_fail_to_fill, _interrupt_filling])
def test_l0_to_l05_overwrite_failure_keeps_cdf(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fill: Callable[..., None]
) -> None:
    """
    Test that when a CDF cannot be filled or is interrupted with
    ``overwrite``, the existing CDF is left unchanged, and the partial
    one is deleted.
    """
    (l1path,) = l0_to_l05(l0file, l05dir=tmp_path, apidreq=0x352).cdf_files.values()
    contents = l1path.read_bytes()
    monkeypatch.setattr(_l0_to_l05, "_cdf352", fill)
    try:
        result = l0_to_l05(l0file, l05dir=tmp_path, apidreq=0x352, overwrite=True)
    except KeyboardInterrupt:
        assert fill is _interrupt_filling
    else:
        assert fill is _fail_to_fill
        assert "made-up error while filling" in result.failures[0x352]
    assert l1path.read_bytes() == contents
    assert list(l1path.parent.iterdir()) == [l1path]


def test_l0_to_l05_overwrite_leaves_only_cdf(tmp_path: Path) -> None:
    """Test that overwriting a CDF leaves no temporary files behind."""
    l0_to_l05(l0file, l05dir=tmp_path, apidreq=0x352)
    result = l0_to_l05(l0file, l05dir=tmp_path, apidreq=0x352, overwrite=True)
    (l1path,) = result.cdf_files.values()
    assert list(l1path.parent.iterdir()) == [l1path]


def test_l0_to_l05_create_failure_skips_apid(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    Test that when a CDF for one APID cannot be created, that APID is
    recorded as a failure, the existing CDF for it is left unchanged,
    and the other APIDs are still converted.
    """
    (l1path,) = l0_to_l05(l0file, l05dir=tmp_path, apidreq=0x352).cdf_files.values()
    contents = l1path.read_bytes()
    original_cdf = pycdf.CDF

    def fail_for_apid352(path: str, *args: object, **kwargs: object) -> pycdf.CDF:
        if Path(path).parent == l1path.parent:
            raise pycdf.CDFError(pycdf.const.CDF_INTERNAL_ERROR)
        return original_cdf(path, *args, **kwargs)

    monkeypatch.setattr(_l0_to_l05.pycdf, "CDF", fail_for_apid352)
    result = l0_to_l05(l0file, l05dir=tmp_path, overwrite=True)

    assert result.failures[0x352].startswith(f"Could not create {l1path}: ")
    assert l1path not in result.cdf_files.values()
    assert result.cdf_files, "the other APIDs should still be converted"
    assert l1path.read_bytes() == contents
    assert list(l1path.parent.iterdir()) == [l1path]


def test_l0_to_l05_close_failure_keeps_cdf(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    Test that an error from closing a completely filled CDF is raised,
    the existing CDF is left unchanged, and the new one is deleted.
    """
    (l1path,) = l0_to_l05(l0file, l05dir=tmp_path, apidreq=0x352).cdf_files.values()
    contents = l1path.read_bytes()

    def fail_to_close(cdf: pycdf.CDF) -> None:
        cdf.close()
        raise pycdf.CDFError(pycdf.const.CDF_INTERNAL_ERROR)

    monkeypatch.setattr(_l0_to_l05, "close_cdf", fail_to_close)
    with pytest.raises(pycdf.CDFError):
        l0_to_l05(l0file, l05dir=tmp_path, apidreq=0x352, overwrite=True)

    assert l1path.read_bytes() == contents
    assert list(l1path.parent.iterdir()) == [l1path]


def test_l0_to_l05_rename_failure_keeps_cdf(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    Test that an error from renaming a complete CDF to its final path is
    raised, the existing CDF is left unchanged, and the new one is
    deleted.
    """
    (l1path,) = l0_to_l05(l0file, l05dir=tmp_path, apidreq=0x352).cdf_files.values()
    contents = l1path.read_bytes()

    def fail_to_replace(_self: Path, _target: object) -> Path:
        msg = "made-up error while renaming"
        raise OSError(msg)

    monkeypatch.setattr(Path, "replace", fail_to_replace)
    with pytest.raises(OSError, match="made-up error while renaming"):
        l0_to_l05(l0file, l05dir=tmp_path, apidreq=0x352, overwrite=True)

    assert l1path.read_bytes() == contents
    assert list(l1path.parent.iterdir()) == [l1path]


def test_discard_partial_cdf_logs_delete_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """
    Test that an error from deleting a partial CDF is logged as a warning
    rather than raised.
    """
    tmp_cdf = tmp_path / ".partial.tmp.cdf"
    tmp_cdf.touch()

    def fail_to_unlink(_self: Path, **_kwargs: object) -> None:
        msg = "made-up error while deleting"
        raise OSError(msg)

    monkeypatch.setattr(Path, "unlink", fail_to_unlink)
    with caplog.at_level(logging.WARNING, logger=_l0_to_l05.__name__):
        _l0_to_l05._discard_partial_cdf(None, tmp_cdf)

    assert [r.getMessage() for r in caplog.records] == [f"Could not delete {tmp_cdf}"]
    assert tmp_cdf.exists()
