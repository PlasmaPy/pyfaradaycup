"""Command line tool for converting SPC L0 files into L1 CDF files."""

from __future__ import annotations

__all__ = ["pfc_decommutator"]

import os
import pathlib

import click

from pyfaradaycup.decommutator import swp_spc_l02l1


def _parse_apid(
    ctx: click.Context,  # ruff:ignore[ARG001]
    param: click.Parameter,  # ruff:ignore[ARG001]
    value: str,
) -> int:
    """Convert an APID given as a decimal or ``0x``-prefixed hexadecimal string."""
    base = 16 if value[0:2] == "0x" else 10
    try:
        return int(value, base)
    except ValueError:
        raise click.BadParameter(  # ruff:ignore[B904, TRY003]
            f"{value!r} is not a decimal or 0x-prefixed hexadecimal integer"  # ruff:ignore[EM102]
        )


def _warn_about_ineffective_options(
    *, batch: bool, recursive: bool, l0dir: str, ptp: bool, spacecraft: bool
) -> None:
    """Print a warning to standard error for each option that has little or no effect."""
    warnings = []
    if batch:
        warnings.append(
            "-b/--batch is not implemented; only --l0file will be converted"
        )
    if recursive:
        warnings.append(
            "-r/--recursive is not implemented; only --l0file will be converted"
        )
    if l0dir:
        warnings.append(
            "-d/--l0dir is not implemented; no files in it will be converted"
        )
    if ptp and not spacecraft:
        warnings.append("-p/--ptp is ignored unless -sc/--spacecraft is also given")

    for warning in warnings:
        click.echo(f"Warning: {warning}", err=True)


@click.command(name="pfc_decommutator")
@click.version_option(package_name="pyfaradaycup")
@click.option(
    "-v",
    "--verbose",
    is_flag=True,
    help="Print messages to the screen as well as to the log file",
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
        "Overwrite existing L1 CDF files. Without this, the tool exits "
        "if an L1 CDF file already exists."
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
    help="APID to create L1 file for [0==all]",
)
@click.option("-l0", "--l0file", default="", help="Input L0 File. Required.")
@click.option(
    "-d",
    "--l0dir",
    default="",
    help=(
        "Input L0 Directory (for use with -b or -r). "
        "Not implemented: no files in it are converted."
    ),
)
@click.option("-dl1", "--l1dir", default="", help="Output L1 Directory. Required.")
@click.option(
    "-dlog",
    "--logdir",
    default="",
    help="Output for Log Files. Required. Created if it does not exist.",
)
def pfc_decommutator(  # ruff:ignore[PLR0913]
    *,
    verbose: bool,
    gzip: bool,
    spacecraft: bool,
    batch: bool,
    recursive: bool,
    ptp: bool,
    overwrite: bool,
    stcorrect: bool,
    apid: int,
    l0file: str,
    l0dir: str,
    l1dir: str,
    logdir: str,
) -> None:
    """
    Convert one SPC L0 file into L1 CDF files, one per APID.

    The PSP_DATA_DIR environment variable must be set to the path of an
    existing data directory.

    To convert the L0 file 0523462910_4_EA, printing messages to the
    screen as well as to the log file:

    \b
        export PSP_DATA_DIR=/path/to/data
        pfc_decommutator \\
            --l0file=/path/to/0523462910_4_EA \\
            --l1dir=/path/to/l1dir \\
            --logdir=/path/to/logdir \\
            -v

    This writes one L1 CDF file for each APID found in the L0 file, such
    as 0523462910_4_EA_APID351_L1.cdf, into the directory given by
    --l1dir, and a log file into the directory given by --logdir.
    """  # ruff:ignore[D301]
    _warn_about_ineffective_options(
        batch=batch,
        recursive=recursive,
        l0dir=l0dir,
        ptp=ptp,
        spacecraft=spacecraft,
    )

    # Make sure we got a good argument set
    if not batch and not recursive:
        if not l0file:
            raise click.UsageError(  # ruff:ignore[TRY003]
                "You must provide --l0file, if not using -b or -r"  # ruff:ignore[EM101]
            )
    elif not l0dir:
        raise click.UsageError(  # ruff:ignore[TRY003]
            "You must provide --l0dir if using -b or -r"  # ruff:ignore[EM101]
        )

    # Make sure the environmental variable reference to the data directory is set and readable
    datadir = os.environ.get("PSP_DATA_DIR")
    if datadir is None:
        raise click.ClickException(  # ruff:ignore[TRY003]
            "Environmental variable PSP_DATA_DIR could not be found...you must specify path to data directory using that environmental variable"  # ruff:ignore[EM101]
        )
    if not pathlib.Path(datadir).exists():
        raise click.ClickException(  # ruff:ignore[TRY003]
            "Directory specified in env. variable PSP_DATA_DIR does not exist"  # ruff:ignore[EM101]
        )

    if stcorrect:
        raise RuntimeError("--stcorrect has not been implemented.")  # ruff:ignore[EM101, TRY003]

    swp_spc_l02l1.main(
        l0file=l0file,
        l1dir=l1dir,
        logdir=logdir,
        spacecraft=spacecraft,
        ptp=ptp,
        gzip=gzip,
        apidreq=apid,
        overwrite=overwrite,
        verbose=verbose,
    )


if __name__ == "__main__":
    pfc_decommutator()
