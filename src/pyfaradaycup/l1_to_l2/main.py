"""Command line tool for converting SPC L1 CDF files into L2 CDF files."""

from __future__ import annotations

__all__ = ["l1_to_l2"]

import datetime
import logging
import pathlib

import click

from pyfaradaycup._logging import configure_logging, console_level
from pyfaradaycup.l05_to_l1.main import _parse_dates
from pyfaradaycup.l1_to_l2._spp_swp_spc_l1_to_l2_date import (
    _l1_files,
    spp_swp_spc_l1_to_l2_date,
)
from pyfaradaycup.l1_to_l2._spp_swp_spc_split_l2cdf_by_mode import (
    spp_swp_spc_split_l2cdf_by_mode,
)

logger = logging.getLogger(__name__)

EXIT_FAILURE = 1
"""The exit code when the L2 files for a date could not be made."""

EXIT_NO_DATA = 65
"""
The exit code when there are no L1 files for a date.

This is ``EX_DATAERR`` from ``sysexits.h``, as for ``l05_to_l1``.
"""


def _log_file_path(logdir: pathlib.Path | None, date: datetime.date) -> pathlib.Path:
    """
    Return the path of the log file for making the L2 files for ``date``.

    The name contains the date and the current UTC time, like
    ``l1_to_l2_20260803_20261124T142301Z.log``.
    """
    now = datetime.datetime.now(datetime.timezone.utc)
    name = f"l1_to_l2_{date:%Y%m%d}_{now:%Y%m%dT%H%M%SZ}.log"
    return pathlib.Path("." if logdir is None else logdir) / name


@click.command(name="l1_to_l2")
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
    "--l1dir",
    required=True,
    type=click.Path(exists=True, file_okay=False, path_type=pathlib.Path),
    help="Input L1 directory, with YYYY/MM/APID*/ subdirectories.",
)
@click.option(
    "--l2dir",
    type=click.Path(file_okay=False, path_type=pathlib.Path),
    help=(
        "Output L2 directory, where YYYY/MM/ subdirectories are created. "
        "The L2 housekeeping files of the day before each date are read "
        "from it. Defaults to the current directory."
    ),
)
@click.option(
    "--logdir",
    type=click.Path(file_okay=False, path_type=pathlib.Path),
    help="Output for log files. Defaults to the current directory. Created if it does not exist.",
)
@click.option(
    "--hsk-only",
    is_flag=True,
    help="Only make the L2 housekeeping files.",
)
@click.option(
    "--sci-only",
    is_flag=True,
    help="Only make the L2 science files, using L2 housekeeping files that already exist.",
)
@click.argument(
    "dates",
    metavar="DATE...",
    nargs=-1,
    required=True,
    callback=_parse_dates,
)
def l1_to_l2(  # ruff:ignore[PLR0913]
    *,
    verbose: int,
    quiet: bool,
    l1dir: pathlib.Path,
    l2dir: pathlib.Path | None,
    logdir: pathlib.Path | None,
    hsk_only: bool,
    sci_only: bool,
    dates: list[datetime.date],
) -> None:
    """
    Make SPC L2 CDF files from daily L1 CDF files.

    Each DATE is a date in UTC, like 2026-08-03. For each date, the L1
    files in the YYYY/MM/APID*/ subdirectories of --l1dir are used:

    \b
    1. The housekeeping file (APID 35F) is converted into engineering
       units, replacing any existing L2 housekeeping file.
    2. The science files (APIDs 351, 353, and 354) are made into spectra
       and written into a new version of the main L2 science file.
    3. The main L2 science file is split into a file for each mode that
       it has.

    To make the L2 files for 2026-08-03, printing progress messages to
    the screen:

    \b
        l1_to_l2 \\
            --l1dir=/path/to/L1 \\
            --l2dir=/path/to/L2 \\
            --logdir=/path/to/logdir \\
            -v \\
            2026-08-03

    This writes files such as 2026/08/spp_swp_spc_APID35Fl2hsk_20260803_v00.cdf,
    2026/08/spp_swp_spc_l2_20260803_v00.cdf, and
    2026/08/spp_swp_spc_l2i_20260803_v00.cdf into the directory given by
    --l2dir, and a log file, such as l1_to_l2_20260803_20261124T142301Z.log,
    into the directory given by --logdir. Each date gets its own log
    file. Since the science step reads the L2 housekeeping files of each
    date and the day before it, process dates in order.

    The exit code is 1 if the L2 files for any date could not be made.
    Otherwise, the exit code is 65 (EX_DATAERR from sysexits.h) if there
    are no L1 files for any one of the dates. A date that fails does not
    stop the remaining dates from being converted.
    """  # ruff:ignore[D301]
    if verbose and quiet:
        raise click.UsageError(  # ruff:ignore[TRY003]
            "-v/--verbose and -q/--quiet cannot be used together"  # ruff:ignore[EM101]
        )
    if hsk_only and sci_only:
        raise click.UsageError(  # ruff:ignore[TRY003]
            "--hsk-only and --sci-only cannot be used together"  # ruff:ignore[EM101]
        )

    exit_codes = {
        _convert(
            date,
            verbose=verbose,
            quiet=quiet,
            l1dir=l1dir,
            l2dir=pathlib.Path() if l2dir is None else l2dir,
            logdir=logdir,
            hsk_only=hsk_only,
            sci_only=sci_only,
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
    l1dir: pathlib.Path,
    l2dir: pathlib.Path,
    logdir: pathlib.Path | None,
    hsk_only: bool,
    sci_only: bool,
) -> int:
    """
    Make the L2 files for one date, with its own log file.

    Like step 5 of the IDL script ``spp_swp_spc_soc_L0L2_processing_idlscript``,
    this calls `spp_swp_spc_l1_to_l2_date` and then
    `spp_swp_spc_split_l2cdf_by_mode` for each L2 science file.

    Returns
    -------
    int
        ``0`` if the L2 files were made, `EXIT_NO_DATA` if there are no L1
        files for the date, and `EXIT_FAILURE` otherwise.
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
        if not _l1_files(date, l1dir):
            logger.error(
                "Could not make L2 files for %s: there are no L1 files in %s",
                date,
                l1dir,
            )
            return EXIT_NO_DATA
        try:
            l2files = spp_swp_spc_l1_to_l2_date(
                date, l1dir=l1dir, l2dir=l2dir, hsk_only=hsk_only, sci_only=sci_only
            )
            split_files = [
                split_file
                for l2file in l2files
                for split_file in spp_swp_spc_split_l2cdf_by_mode(l2file)
            ]
        except Exception:
            # Record the traceback in the log file as well as on the screen
            logger.exception("Could not make L2 files for %s", date)
            return EXIT_FAILURE
        logger.info(
            "Wrote %d L2 science files and %d split files for %s",
            len(l2files),
            len(split_files),
            date,
        )
        return 0


if __name__ == "__main__":
    l1_to_l2()
