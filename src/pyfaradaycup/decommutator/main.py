"""Command line tool for converting SPC L0 files into L0.5 CDF files."""

from __future__ import annotations

__all__ = ["pfc_decommutator"]

import datetime
import logging
import pathlib

import click

from pyfaradaycup._logging import configure_logging
from pyfaradaycup.decommutator import swp_spc_l0_to_l05

logger = logging.getLogger(__name__)


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


def _warn_about_ineffective_options(
    *,
    batch: bool,
    recursive: bool,
    l0dir: pathlib.Path | None,
    ptp: bool,
    spacecraft: bool,
) -> None:
    """Log a warning for each option that has little or no effect."""
    warnings = []
    if batch:
        warnings.append(
            "-b/--batch is not implemented; only --l0file will be converted"
        )
    if recursive:
        warnings.append(
            "-r/--recursive is not implemented; only --l0file will be converted"
        )
    if l0dir is not None:
        warnings.append(
            "-d/--l0dir is not implemented; no files in it will be converted"
        )
    if ptp and not spacecraft:
        warnings.append("-p/--ptp is ignored unless -sc/--spacecraft is also given")

    for warning in warnings:
        logger.warning(warning)


def _console_level(*, verbose: int, quiet: bool) -> int:
    """Return the minimum level of messages to print to standard error."""
    if quiet:
        return logging.ERROR
    if verbose == 0:
        return logging.WARNING
    if verbose == 1:
        return logging.INFO
    return logging.DEBUG


def _log_file_path(logdir: pathlib.Path | None, l0file: pathlib.Path) -> pathlib.Path:
    """
    Return the path of the log file for converting ``l0file``.

    The name contains the name of the L0 file and the current UTC time,
    like ``swp_spc_l0_to_l05_0523462910_4_EA_20261029T142301Z.log``.
    """
    now = datetime.datetime.now(datetime.timezone.utc)
    name = f"swp_spc_l0_to_l05_{l0file.stem}_{now:%Y%m%dT%H%M%SZ}.log"
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
    "-b",
    "--batch",
    is_flag=True,
    help=(
        "Convert all L0 files in same directory as selected. "
        "Not implemented: only --l0file is converted."
    ),
)
@click.option(
    "-r",
    "--recursive",
    is_flag=True,
    help=(
        "Convert all L0 files in given directory and in all subdirectories. "
        "Not implemented: only --l0file is converted."
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
    "-l0",
    "--l0file",
    type=click.Path(dir_okay=False, path_type=pathlib.Path),
    help="Input L0 File. Required.",
)
@click.option(
    "-d",
    "--l0dir",
    type=click.Path(file_okay=False, path_type=pathlib.Path),
    help=(
        "Input L0 Directory (for use with -b or -r). "
        "Not implemented: no files in it are converted."
    ),
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
def pfc_decommutator(  # ruff:ignore[PLR0913]
    *,
    verbose: int,
    quiet: bool,
    gzip: bool,
    spacecraft: bool,
    batch: bool,
    recursive: bool,
    ptp: bool,
    overwrite: bool,
    stcorrect: bool,
    apid: int,
    l0file: pathlib.Path | None,
    l0dir: pathlib.Path | None,
    l05dir: pathlib.Path | None,
    logdir: pathlib.Path | None,
) -> None:
    """
    Convert one SPC L0 file into L0.5 CDF files, one per APID.

    To convert the L0 file 0523462910_4_EA, printing progress messages
    to the screen:

    \b
        pfc_decommutator \\
            --l0file=/path/to/0523462910_4_EA \\
            --l05dir=/path/to/l05dir \\
            --logdir=/path/to/logdir \\
            -v

    This writes one L0.5 CDF file for each APID found in the L0 file, such
    as 0523462910_4_EA_APID351_L1.cdf, into the directory given by
    --l05dir, and a log file, such as
    swp_spc_l0_to_l05_0523462910_4_EA_20261029T142301Z.log, into the
    directory given by --logdir. If --l05dir or --logdir is not given,
    the current directory is used. The log file has every message, with
    timestamps in UTC.
    """  # ruff:ignore[D301]
    # Make sure we got a good argument set. Because -b and -r are not
    # implemented, --l0file is needed even when they are given.
    if (batch or recursive) and l0dir is None:
        raise click.UsageError(  # ruff:ignore[TRY003]
            "You must provide --l0dir if using -b or -r"  # ruff:ignore[EM101]
        )
    if l0file is None:
        raise click.UsageError(  # ruff:ignore[TRY003]
            "You must provide --l0file"  # ruff:ignore[EM101]
        )
    if verbose and quiet:
        raise click.UsageError(  # ruff:ignore[TRY003]
            "-v/--verbose and -q/--quiet cannot be used together"  # ruff:ignore[EM101]
        )

    if stcorrect:
        raise RuntimeError("--stcorrect has not been implemented.")  # ruff:ignore[EM101, TRY003]

    log_file = _log_file_path(logdir, l0file)
    with configure_logging(
        level=_console_level(verbose=verbose, quiet=quiet),
        log_file=log_file,
        file_mode="x",
        capture_warnings=True,
    ):
        logger.info("Writing log file %s", log_file)
        _warn_about_ineffective_options(
            batch=batch,
            recursive=recursive,
            l0dir=l0dir,
            ptp=ptp,
            spacecraft=spacecraft,
        )
        try:
            swp_spc_l0_to_l05.main(
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
            raise SystemExit(1) from None


if __name__ == "__main__":
    pfc_decommutator()
