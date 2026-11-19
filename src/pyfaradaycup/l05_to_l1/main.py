"""Command line tool for converting SPC L0.5 CDF files into daily L1 CDF files."""

from __future__ import annotations

__all__ = ["l05_to_l1"]

import datetime
import logging
import pathlib

import click

from pyfaradaycup._logging import configure_logging, console_level
from pyfaradaycup.l05_to_l1._spp_swp_spc_l05_to_l1 import (
    NoL05DataError,
    _parse_date,
    spp_swp_spc_l05_to_l1_date,
)

logger = logging.getLogger(__name__)

EXIT_FAILURE = 1
"""The exit code when the L1 files for a date could not be made."""

EXIT_NO_DATA = 65
"""
The exit code when no L0.5 files have SPC data for a date.

This is ``EX_DATAERR`` from ``sysexits.h``, which is also the exit code
of ``pfc_decommutator`` for an L0 file with no packets.
"""


def _parse_dates(
    ctx: click.Context,  # ruff:ignore[ARG001]
    param: click.Parameter,  # ruff:ignore[ARG001]
    value: tuple[str, ...],
) -> list[datetime.date]:
    """Convert dates given as ISO 8601 strings, removing duplicates and sorting them."""
    dates = set()
    for string in value:
        try:
            dates.add(_parse_date(string))
        except ValueError:  # ruff:ignore[PERF203]
            raise click.BadParameter(  # ruff:ignore[B904, TRY003]
                f"{string!r} is not a date like 2026-08-03"  # ruff:ignore[EM102]
            )
    return sorted(dates)


def _log_file_path(logdir: pathlib.Path | None, date: datetime.date) -> pathlib.Path:
    """
    Return the path of the log file for making the L1 files for ``date``.

    The name contains the date and the current UTC time, like
    ``l05_to_l1_20260803_20261029T142301Z.log``.
    """
    now = datetime.datetime.now(datetime.timezone.utc)
    name = f"l05_to_l1_{date:%Y%m%d}_{now:%Y%m%dT%H%M%SZ}.log"
    return pathlib.Path("." if logdir is None else logdir) / name


@click.command(name="l05_to_l1")
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
@click.option(
    "-o",
    "--overwrite",
    is_flag=True,
    help=(
        "Overwrite existing L1 CDF files. Without this, a date fails, and "
        "none of its L1 CDF files are written, if any of them already exist."
    ),
)
@click.option(
    "--l05dir",
    required=True,
    type=click.Path(exists=True, file_okay=False, path_type=pathlib.Path),
    help="Input L0.5 directory, with YYYY/MM/APID*/ subdirectories.",
)
@click.option(
    "--l1dir",
    type=click.Path(file_okay=False, path_type=pathlib.Path),
    help=(
        "Output L1 directory, where YYYY/MM/APID*/ subdirectories are created. "
        "Defaults to the current directory."
    ),
)
@click.option(
    "--logdir",
    type=click.Path(file_okay=False, path_type=pathlib.Path),
    help="Output for Log Files. Defaults to the current directory. Created if it does not exist.",
)
@click.argument(
    "dates",
    metavar="DATE...",
    nargs=-1,
    required=True,
    callback=_parse_dates,
)
def l05_to_l1(  # ruff:ignore[PLR0913]
    *,
    verbose: int,
    quiet: bool,
    overwrite: bool,
    l05dir: pathlib.Path,
    l1dir: pathlib.Path | None,
    logdir: pathlib.Path | None,
    dates: list[datetime.date],
) -> None:
    """
    Make daily SPC L1 CDF files from L0.5 CDF files, one per APID.

    Each DATE is a date in UTC, like 2026-08-03. For each date, the L0.5
    files in --l05dir with records on that date are found in the
    YYYY/MM/APID*/ subdirectories for that month and the months before
    and after it. For each of the APIDs 351, 353, 354, 35E, and 35F, the
    records on that date are merged, sorted by time, and de-duplicated
    into one L1 file. All of the L0.5 files for the date are used, so the
    whole day's L1 files are rebuilt.

    To make the L1 files for 2026-08-03, printing progress messages to the
    screen:

    \b
        l05_to_l1 \\
            --l05dir=/path/to/L05 \\
            --l1dir=/path/to/L1 \\
            --logdir=/path/to/logdir \\
            -v \\
            2026-08-03

    This writes files such as
    2026/08/APID351/spp_swp_spc_APID351L1_20260803_v00.cdf into the
    directory given by --l1dir, and a log file, such as
    l05_to_l1_20260803_20261029T142301Z.log, into the directory given by
    --logdir. If --l1dir or --logdir is not given, the current directory
    is used. Each date gets its own log file.

    The exit code is 1 if the L1 files for any date could not be made.
    Otherwise, the exit code is 65 (EX_DATAERR from sysexits.h) if no
    L0.5 files have SPC data for any one of the dates. A date that fails
    does not stop the remaining dates from being converted.
    """  # ruff:ignore[D301]
    if verbose and quiet:
        raise click.UsageError(  # ruff:ignore[TRY003]
            "-v/--verbose and -q/--quiet cannot be used together"  # ruff:ignore[EM101]
        )

    exit_codes = {
        _convert(
            date,
            verbose=verbose,
            quiet=quiet,
            l05dir=l05dir,
            l1dir=l1dir,
            logdir=logdir,
            overwrite=overwrite,
        )
        for date in dates
    }
    # A failure to convert takes precedence over a date with no data,
    # since it is more likely to need investigating
    for exit_code in (EXIT_FAILURE, EXIT_NO_DATA):
        if exit_code in exit_codes:
            raise SystemExit(exit_code)


def _convert(  # ruff:ignore[PLR0913]
    date: datetime.date,
    *,
    verbose: int,
    quiet: bool,
    l05dir: pathlib.Path,
    l1dir: pathlib.Path | None,
    logdir: pathlib.Path | None,
    overwrite: bool,
) -> int:
    """
    Make the L1 files for one date, with its own log file.

    Returns
    -------
    int
        ``0`` if the L1 files were made, `EXIT_NO_DATA` if no L0.5 files
        have SPC data for the date, and `EXIT_FAILURE` otherwise.
    """
    log_file = _log_file_path(logdir, date)
    with configure_logging(
        level=console_level(verbose=verbose, quiet=quiet),
        log_file=log_file,
        file_mode="exclusive",
        capture_warnings=True,
    ):
        ctx = click.get_current_context()
        logger.info("Running %s with options %s", ctx.command_path, ctx.params)
        logger.info("Writing log file %s", log_file)
        try:
            l1files = spp_swp_spc_l05_to_l1_date(
                date,
                l05dir=l05dir,
                l1dir="." if l1dir is None else l1dir,
                overwrite=overwrite,
            )
        except NoL05DataError as exc:
            # This is a problem with the input data rather than a bug, so
            # the traceback is not needed
            logger.error("Could not make L1 files for %s: %s", date, exc)  # ruff:ignore[TRY400]
            return EXIT_NO_DATA
        except Exception:
            # Record the traceback in the log file as well as on the screen
            logger.exception("Could not make L1 files for %s", date)
            return EXIT_FAILURE
        logger.info("Wrote %d L1 CDF files for %s", len(l1files), date)
        return 0


if __name__ == "__main__":
    l05_to_l1()
