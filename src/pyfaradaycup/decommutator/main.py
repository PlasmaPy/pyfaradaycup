"""Command line tool for converting SPC L0 files into L0.5 CDF files."""

from __future__ import annotations

__all__ = ["pfc_decommutator"]

import datetime
import logging
import pathlib

import click

from pyfaradaycup._logging import configure_logging
from pyfaradaycup.decommutator._l0_to_l05 import l0_to_l05

logger = logging.getLogger(__name__)

L0_FILE_SUFFIX = "_EA"
"""The end of the names of the L0 files that are converted in a directory."""


def _parse_apid(
    ctx: click.Context,  # ruff:ignore[ARG001]
    param: click.Parameter,  # ruff:ignore[ARG001]
    value: str,
) -> int:
    """Convert an APID given as a hexadecimal string, with or without ``0x``."""
    try:
        return int(value, 16)
    except ValueError:
        raise click.BadParameter(  # ruff:ignore[B904, TRY003]
            f"{value!r} is not a hexadecimal integer"  # ruff:ignore[EM102]
        )


def _warn_about_ineffective_options(*, recursive: bool) -> None:
    """
    Log a warning for each option that has no effect.

    Options that are passed on to `~pyfaradaycup.decommutator.l0_to_l05`,
    like ``--ptp``, are checked there instead.
    """
    if recursive:
        logger.warning(
            "-r/--recursive is not implemented; subdirectories will not be searched"
        )


def _console_level(*, verbose: int, quiet: bool) -> int:
    """Return the minimum level of messages to print to standard error."""
    if quiet:
        return logging.ERROR
    if verbose == 0:
        return logging.WARNING
    if verbose == 1:
        return logging.INFO
    return logging.DEBUG


def _l0_files(l0path: pathlib.Path) -> list[pathlib.Path]:
    """
    Return the L0 files to convert for ``l0path``.

    Parameters
    ----------
    l0path : pathlib.Path
        An L0 file, or a directory of L0 files.

    Returns
    -------
    list of pathlib.Path
        ``[l0path]`` if ``l0path`` is not a directory. Otherwise, the
        files directly in ``l0path`` whose names end with ``_EA``, sorted
        by name. Subdirectories are not searched.

    Raises
    ------
    click.ClickException
        If ``l0path`` is a directory with no files ending with ``_EA``.
    """
    if not l0path.is_dir():
        return [l0path]
    l0files = sorted(
        path
        for path in l0path.iterdir()
        if path.name.endswith(L0_FILE_SUFFIX) and path.is_file()
    )
    if not l0files:
        msg = f"No L0 files ending with {L0_FILE_SUFFIX} in directory {l0path}"
        raise click.ClickException(msg)
    return l0files


def _log_file_path(logdir: pathlib.Path | None, l0file: pathlib.Path) -> pathlib.Path:
    """
    Return the path of the log file for converting ``l0file``.

    The name contains the name of the L0 file and the current UTC time,
    like ``l0_to_l05_0523462910_4_EA_20261029T142301Z.log``.
    """
    now = datetime.datetime.now(datetime.timezone.utc)
    name = f"l0_to_l05_{l0file.stem}_{now:%Y%m%dT%H%M%SZ}.log"
    return pathlib.Path("." if logdir is None else logdir) / name


@click.command(name="pfc_decommutator")
@click.version_option(package_name="pyfaradaycup")
@click.option(
    "-v",
    "--verbose",
    count=True,
    help=(
        "Print more messages to the screen: -v for progress, and -vv for "
        "details. Without it, only warnings and errors are printed. The log "
        "file always has every message."
    ),
)
@click.option(
    "-q",
    "--quiet",
    is_flag=True,
    help="Only print errors to the screen.",
)
@click.option("-gz", "--gzip", is_flag=True, help="Read in L0 file as gzip")
@click.option(
    "-sc",
    "--spacecraft",
    is_flag=True,
    help="Look for S/C housekeeping packets instead of SWEAP instrument packets",
)
@click.option(
    "-r",
    "--recursive",
    is_flag=True,
    help=(
        "Convert all L0 files in given directory and in all subdirectories. "
        "Not implemented: subdirectories of L0PATH are not searched."
    ),
)
@click.option(
    "-p",
    "--ptp",
    is_flag=True,
    help="Indicate that input L0 file is a PTP file. Ignored unless -sc is given.",
)
@click.option(
    "-o",
    "--overwrite",
    is_flag=True,
    help=(
        "Overwrite existing L0.5 CDF files. Without this, the tool exits "
        "if an L0.5 CDF file already exists."
    ),
)
@click.option(
    "-stc",
    "--stcorrect",
    is_flag=True,
    help=(
        "If ST is wrong (FPGA bug if ST set higher than 2), then try to "
        "correct it. Not implemented: raises an error if given."
    ),
)
@click.option(
    "-a",
    "--apid",
    default="0",
    show_default=True,
    callback=_parse_apid,
    help="APID to create L0.5 CDF file for, in hexadecimal (e.g., 35E) [0==all]",
)
@click.option(
    "-dl05",
    "--l05dir",
    type=click.Path(file_okay=False, path_type=pathlib.Path),
    help="Output L0.5 Directory. Defaults to the current directory. Created if it does not exist.",
)
@click.option(
    "-dlog",
    "--logdir",
    type=click.Path(file_okay=False, path_type=pathlib.Path),
    help="Output for Log Files. Defaults to the current directory. Created if it does not exist.",
)
@click.argument(
    "l0path",
    metavar="L0PATH",
    type=click.Path(path_type=pathlib.Path),
)
def pfc_decommutator(  # ruff:ignore[PLR0913]
    *,
    verbose: int,
    quiet: bool,
    gzip: bool,
    spacecraft: bool,
    recursive: bool,
    ptp: bool,
    overwrite: bool,
    stcorrect: bool,
    apid: int,
    l0path: pathlib.Path,
    l05dir: pathlib.Path | None,
    logdir: pathlib.Path | None,
) -> None:
    """
    Convert SPC L0 files into L0.5 CDF files, one per APID.

    L0PATH is an L0 file, or a directory of L0 files. For a directory,
    every file directly in it whose name ends with _EA is converted, in
    order of name, and subdirectories are not searched.

    To convert the L0 file 0523462910_4_EA, printing progress messages
    to the screen:

    \b
        pfc_decommutator \\
            --l05dir=/path/to/l05dir \\
            --logdir=/path/to/logdir \\
            -v \\
            /path/to/0523462910_4_EA

    This writes one L0.5 CDF file for each APID found in the L0 file, such
    as APID351/0523462910_4_EA_APID351_L1.cdf, into a subdirectory named
    after the APID in the directory given by --l05dir, and a log file,
    such as
    l0_to_l05_0523462910_4_EA_20261029T142301Z.log, into the
    directory given by --logdir. If --l05dir or --logdir is not given,
    the current directory is used. The log file has every message, with
    timestamps in UTC. Each L0 file gets its own log file.

    The exit code is 1 if any APID of any L0 file could not be converted.
    When converting a directory, an L0 file that could not be converted
    does not stop the remaining L0 files from being converted.
    """  # ruff:ignore[D301]
    if verbose and quiet:
        raise click.UsageError(  # ruff:ignore[TRY003]
            "-v/--verbose and -q/--quiet cannot be used together"  # ruff:ignore[EM101]
        )

    if stcorrect:
        raise RuntimeError("--stcorrect has not been implemented.")  # ruff:ignore[EM101, TRY003]

    succeeded = True
    for l0file in _l0_files(l0path):
        succeeded &= _convert(
            l0file,
            verbose=verbose,
            quiet=quiet,
            recursive=recursive,
            logdir=logdir,
            l05dir=l05dir,
            spacecraft=spacecraft,
            ptp=ptp,
            gzip=gzip,
            apid=apid,
            overwrite=overwrite,
        )
    if not succeeded:
        raise SystemExit(1)


def _convert(  # ruff:ignore[PLR0913]
    l0file: pathlib.Path,
    *,
    verbose: int,
    quiet: bool,
    recursive: bool,
    logdir: pathlib.Path | None,
    l05dir: pathlib.Path | None,
    spacecraft: bool,
    ptp: bool,
    gzip: bool,
    apid: int,
    overwrite: bool,
) -> bool:
    """
    Convert one L0 file, with its own log file.

    Returns
    -------
    bool
        Whether every APID was converted.
    """
    log_file = _log_file_path(logdir, l0file)
    with configure_logging(
        level=_console_level(verbose=verbose, quiet=quiet),
        log_file=log_file,
        file_mode="exclusive",
        capture_warnings=True,
    ):
        ctx = click.get_current_context()
        logger.info("Running %s with options %s", ctx.command_path, ctx.params)
        logger.info("Writing log file %s", log_file)
        _warn_about_ineffective_options(recursive=recursive)
        try:
            result = l0_to_l05(
                l0file=l0file,
                l05dir=l05dir,
                spacecraft=spacecraft,
                ptp=ptp,
                gzip=gzip,
                apidreq=apid,
                overwrite=overwrite,
            )
        except Exception:
            # Record the traceback in the log file as well as on the screen
            logger.exception("Could not convert %s", l0file)
            return False

        return result.succeeded


if __name__ == "__main__":
    pfc_decommutator()
