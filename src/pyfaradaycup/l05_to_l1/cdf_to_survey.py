"""
Merge CDF files into daily CDF files.

This module is a port of ``CDF_merge_to_daily`` from the IDL file
``idllib/CDF_to_survey.pro`` by Michael L. Stevens, along with the parts
of CDAWlib (``read_myCDF.pro`` and ``IDLmakecdf.pro``) that it calls.
Only the parts needed to convert L0.5 files into L1 files are ported.
IDL names are case-insensitive, so ``CDF_merge_to_daily`` becomes
`cdf_merge_to_daily`.
"""

from __future__ import annotations

__all__ = ["cdf_merge_to_daily"]

import datetime
import logging
import pathlib
import secrets
import time
from typing import TYPE_CHECKING

import numpy as np
from spacepy import pycdf

from pyfaradaycup.utils._cdf import close_cdf
from pyfaradaycup.utils.idl import (
    _JD_OF_ORDINAL_ZERO,
    cdf_epoch_tojuldays,
    julday,
    uniq,
)

if TYPE_CHECKING:
    import os
    from collections.abc import Sequence

logger = logging.getLogger(__name__)


def _unique_dates(jd: np.ndarray) -> list[datetime.date]:
    """
    Return the sorted calendar dates (in UTC) of Julian days.

    Julian days before 0001-01-01, such as those from fill values or pad
    values of ``Epoch``, are skipped.
    """
    ordinals = np.unique(np.floor(jd[np.isfinite(jd)] - _JD_OF_ORDINAL_ZERO))
    max_ordinal = datetime.date.max.toordinal()
    return [
        datetime.date.fromordinal(int(ordinal))
        for ordinal in ordinals
        if 1 <= ordinal <= max_ordinal
    ]


def _outfile(
    outpath: pathlib.Path, outname: str, date: datetime.date, outversion: int = 0
) -> pathlib.Path:
    """Return the path of the daily file for ``date``."""
    return outpath / f"{outname}_{date:%Y%m%d}_v{outversion:02d}.cdf"


def _read_mycdf(
    infiles: Sequence[pathlib.Path],
) -> tuple[dict[str, np.ndarray], dict[str, bool]]:
    """
    Read every variable from CDF files, concatenating their records.

    This replaces ``read_myCDF(vars, infiles, /all)`` from CDAWlib.

    Parameters
    ----------
    infiles : sequence of pathlib.Path
        CDF files that have the same variables.

    Returns
    -------
    data : dict of str to numpy.ndarray
        The raw values of each variable, in the order of the variables
        in the first file. The records of record-varying variables are
        concatenated in the order of ``infiles``. Variables that are not
        record-varying are taken from the first file.
    record_varying : dict of str to bool
        Whether each variable is record-varying.

    Raises
    ------
    ValueError
        If the files do not all have the same variables.
    """
    chunks: dict[str, list[np.ndarray]] = {}
    record_varying: dict[str, bool] = {}
    for infile in infiles:
        with pycdf.CDF(str(infile)) as cdf:
            names = list(cdf)
            if not chunks:
                chunks = {name: [] for name in names}
                record_varying = {name: cdf[name].rv() for name in names}
            elif set(names) != set(chunks):
                msg = (
                    f"{infile} has variables {sorted(names)}, but "
                    f"{infiles[0]} has variables {sorted(chunks)}"
                )
                raise ValueError(msg)
            for name in names:
                if record_varying[name] or not chunks[name]:
                    chunks[name].append(np.asarray(cdf.raw_var(name)[...]))
    data = {
        name: np.concatenate(values) if record_varying[name] else values[0]
        for name, values in chunks.items()
    }
    return data, record_varying


def _read_master_cdf(skeletonfile: pathlib.Path, out_cdf: pathlib.Path) -> None:
    """
    Create a CDF file from a skeleton CDF file.

    This replaces ``read_master_cdf`` from CDAWlib, which copies the
    skeleton over the output file. Here, the file is created at a
    temporary path chosen by `cdf_merge_to_daily`, which must not exist.

    Parameters
    ----------
    skeletonfile : pathlib.Path
        The skeleton CDF file, which has the variables and attributes,
        but no records.
    out_cdf : pathlib.Path
        The CDF file to create.
    """
    with pycdf.CDF(str(out_cdf), str(skeletonfile)):
        pass


def _temporary_path(out_cdf: pathlib.Path) -> pathlib.Path:
    """
    Return a new path, next to ``out_cdf``, to write it to first.

    The name starts with ``.`` so that it is hidden, and ends with
    ``.cdf``, because the CDF library adds ``.cdf`` to names that do not
    end with it.
    """
    return out_cdf.with_name(f".{out_cdf.stem}.{secrets.token_hex(8)}.tmp.cdf")


def _write_data_to_cdf(
    out_cdf: pathlib.Path, buffer: dict[str, np.ndarray], *, logical_file_id: str
) -> None:
    """
    Write data into a CDF file created by `_read_master_cdf`.

    This replaces ``write_data_to_cdf`` from CDAWlib. Like it, the
    ``Logical_file_id`` global attribute is set to the name of the file
    without ``.cdf``, which is given by ``logical_file_id`` because the
    file is written at a temporary path first. The ``Generation_date``
    global attribute is set to the current local time in the format of
    IDL's ``systime()``, like ``Fri Aug 14 11:38:16 2026``. Each is set
    only if the skeleton has it.

    Parameters
    ----------
    out_cdf : pathlib.Path
        The CDF file to write into.
    buffer : dict of str to numpy.ndarray
        The raw values to write into each variable.
    logical_file_id : str
        The name of the final file without ``.cdf``.
    """
    cdf = pycdf.CDF(str(out_cdf))
    try:
        cdf.readonly(False)  # ruff:ignore[FBT003]
        if "Logical_file_id" in cdf.attrs:
            cdf.attrs["Logical_file_id"][0] = logical_file_id
        if "Generation_date" in cdf.attrs:
            cdf.attrs["Generation_date"][0] = time.ctime()
        for name, values in buffer.items():
            cdf.raw_var(name)[...] = values
    finally:
        close_cdf(cdf)


def cdf_merge_to_daily(  # ruff:ignore[PLR0913]
    infiles: Sequence[str | os.PathLike[str]],
    *,
    skeletonfile: str | os.PathLike[str],
    outname: str,
    outpath: str | os.PathLike[str],
    outdate: datetime.date | None = None,
    outversion: int = 0,
    overwrite: bool = False,
) -> list[pathlib.Path]:
    """
    Merge CDF files into one CDF file for each calendar day.

    The records from all of the files are combined, sorted by time, and
    de-duplicated, and the records for each day are written into a new
    CDF file created from ``skeletonfile``. The data values are not
    changed.

    Parameters
    ----------
    infiles : `~collections.abc.Sequence` of path-like
        The CDF files to merge. They must have the same variables as
        each other and as ``skeletonfile``, including a
        ``CDF_TIME_TT2000`` variable named ``Epoch``. Files that do not
        exist are skipped with a warning.
    skeletonfile : path-like
        The skeleton CDF file for the output files.
    outname : str
        The start of the name of each output file. The full name is
        ``f"{outname}_{YYYYMMDD}_v{outversion:02d}.cdf"``.
    outpath : path-like
        The directory to write the output files into, which is created
        if it does not exist.
    outdate : datetime.date, optional
        The only day to write a file for. Records on other days are
        ignored. By default, a file is written for every day (in UTC)
        that has records.
    outversion : int, default: 0
        The version number in the name of each output file.
    overwrite : bool, default: False
        Whether to replace output files that already exist. Each file
        is written at a temporary path and renamed when it is complete,
        so an existing file is left unchanged if writing fails.

    Returns
    -------
    list of pathlib.Path
        The files that were written, which is empty if ``outdate`` is
        given and no records are on that day.

    Raises
    ------
    FileNotFoundError
        If none of ``infiles`` exist.
    FileExistsError
        If an output file exists and ``overwrite`` is `False`.
    ValueError
        If the input files have no ``Epoch`` variable, or do not have
        the same variables as each other and as ``skeletonfile``.

    Notes
    -----
    For now, this mimics IDL, except where noted in the code:

    - Records are selected for a day by converting ``Epoch`` to UTC
      Julian days as float64 values, which differ by about 40 µs.
    - Duplicates are records with equal float64 Julian days, so records
      that are less than about 40 µs apart can be treated as duplicates.
      Of each set of duplicates, the one that comes last in the order of
      ``infiles`` is kept. IDL's ``sort`` is not stable, so which
      duplicate IDL keeps is not defined.
    """
    infiles = [pathlib.Path(infile) for infile in infiles]
    skeletonfile = pathlib.Path(skeletonfile)
    outpath = pathlib.Path(outpath)

    # Make sure that the input files exist. Unlike IDL, which checks the
    # count from only the last file, the warning is about every file.
    missing = [infile for infile in infiles if not infile.is_file()]
    for infile in missing:
        logger.warning("Input file %s was not found; skipping it", infile)
    infiles = [infile for infile in infiles if infile not in missing]
    if not infiles:
        msg = "None of the input files were found"
        raise FileNotFoundError(msg)

    # Read the input data, like read_myCDF(vars, infiles, /all)
    odata, record_varying = _read_mycdf(infiles)
    if "Epoch" not in odata:
        msg = f"No Epoch variable in {infiles[0]}"
        raise ValueError(msg)
    epoch = odata["Epoch"]

    # IDL matches variables by their position in the skeleton and the
    # input files. Instead, they are matched by name, so the skeleton
    # and the input files are checked to have the same variables, in
    # any order.
    with pycdf.CDF(str(skeletonfile)) as skeleton:
        varnames = list(skeleton)
    if set(varnames) != set(odata):
        msg = (
            f"The variables in {skeletonfile} ({varnames}) are not the "
            f"same as in the input files ({list(odata)})"
        )
        raise ValueError(msg)

    # For ease of computation, convert to Julian days, and also compute
    # the calendar dates
    jd = cdf_epoch_tojuldays(epoch)
    uniquedates = _unique_dates(jd)

    # If a particular output date is given, look only for that
    if outdate is not None:
        if outdate not in uniquedates:
            logger.info("No records on %s in %s", outdate, infiles)
            return []
        uniquedates = [outdate]

    outpath.mkdir(parents=True, exist_ok=True)
    outfiles = []
    for thisdate in uniquedates:
        jd_start = julday(thisdate)
        jd_stop = jd_start + 1.0
        all_thisday = np.flatnonzero((jd >= jd_start) & (jd < jd_stop))

        # Indices for a time-ordered, duplicate-free selection.
        # IDL sorts with sort(..., /l64), which is not stable.
        # TODO: Remove duplicates based on the exact int64 TT2000 values  # ruff:ignore[FIX002, TD002, TD003]
        # in Epoch, rather than float64 Julian days, which can treat
        # records less than about 40 µs apart as duplicates.
        o = np.argsort(jd[all_thisday], kind="stable")
        u = uniq(jd[all_thisday[o]])
        ind = all_thisday[o[u]]

        out_cdf = _outfile(outpath, outname, thisdate, outversion)
        exists = out_cdf.exists()
        if exists and not overwrite:
            msg = f"{out_cdf} already exists; use overwrite to replace it"
            raise FileExistsError(msg)

        # Unlike IDL, which copies the skeleton over the output file, the
        # file is written at a temporary path and then renamed, so that
        # an existing file is only replaced by a complete one.
        tmp_cdf = _temporary_path(out_cdf)
        try:
            _read_master_cdf(skeletonfile, tmp_cdf)
            # For each variable, select the content for this day. IDL
            # uses the first dimension with the same length as Epoch as
            # the record dimension, which ARRAY_CHUNK selects from.
            # Instead, record-varying variables are selected along their
            # record dimension, which is the first dimension. For the
            # skeletons used for L1 files, these are the same.
            buffer = {
                name: values[ind] if record_varying[name] else values
                for name, values in odata.items()
            }
            _write_data_to_cdf(tmp_cdf, buffer, logical_file_id=out_cdf.stem)
            tmp_cdf.replace(out_cdf)
        except BaseException:
            # Delete the partial CDF, and leave any existing file alone
            tmp_cdf.unlink(missing_ok=True)
            raise
        logger.info(
            "Wrote %d records to %s%s",
            ind.size,
            out_cdf,
            ", replacing the existing file" if exists else "",
        )
        outfiles.append(out_cdf)
    return outfiles
