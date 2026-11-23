"""
Merge, subset, and change CDF files.

This module is a port of ``CDF_merge_to_daily``, ``CDF_subset``,
``CDF_operate_on``, and ``make_temp_CDFskeleton`` from the IDL file
``idllib/CDF_to_survey.pro`` by Michael L. Stevens, along with the parts
of CDAWlib (``read_myCDF.pro`` and ``IDLmakecdf.pro``) that they call.
Only the parts needed to convert L0.5 files into L1 files, and to split
L2 files by mode, are ported. IDL names are case-insensitive, so
``CDF_merge_to_daily`` becomes `cdf_merge_to_daily`.
"""

from __future__ import annotations

__all__ = [
    "cdf_merge_to_daily",
    "cdf_operate_on",
    "cdf_subset",
    "make_temp_cdfskeleton",
]

import datetime
import logging
import pathlib
import re
import secrets
import shutil
import tempfile
import time
from typing import TYPE_CHECKING, Any

import numpy as np
from spacepy import pycdf

from pyfaradaycup.utils._cdf import close_cdf, ignore_chararray_deprecation
from pyfaradaycup.utils.idl import (
    _JD_OF_ORDINAL_ZERO,
    cdf_epoch_tojuldays,
    julday,
    uniq,
)

if TYPE_CHECKING:
    import os
    from collections.abc import Callable, Sequence

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


_FORTRAN_FORMAT = re.compile(r"^\s*\d*([EFG])(\d+)\.(\d+)\s*$", re.IGNORECASE)
"""A Fortran ``FORMAT`` attribute like ``E12.2``, ``F7.3``, or ``G10.4``."""

_REAL_TYPES = (
    pycdf.const.CDF_REAL4.value,
    pycdf.const.CDF_FLOAT.value,
    pycdf.const.CDF_REAL8.value,
    pycdf.const.CDF_DOUBLE.value,
)

_OPERATIONS: dict[str, Callable[[np.ndarray], np.ndarray]] = {"abs": np.abs}
"""The IDL functions that `cdf_operate_on` can apply, by name."""


def _format_like_skeletontable(value: Any, fmt: str) -> Any:  # ruff:ignore[ANN401]
    """
    Round a floating-point attribute value to its Fortran ``FORMAT``.

    ``skeletontable`` writes attribute values with the ``FORMAT`` of the
    variable, so ``1.5707964`` with ``E7.2`` becomes ``1.57``.
    """
    match = _FORTRAN_FORMAT.match(fmt)
    if match is None:
        return value
    kind, _, digits = match.group(1).upper(), match.group(2), int(match.group(3))
    code = "f" if kind == "F" else "E"

    def rounded(x: Any) -> float:  # ruff:ignore[ANN401]
        return float(f"{float(x):.{digits}{code}}")

    array = np.asarray(value)
    result = np.vectorize(rounded, otypes=[np.float64])(array).astype(array.dtype)
    return result if array.ndim else result[()]


def make_temp_cdfskeleton(
    cdffile: str | os.PathLike[str], skeletonfile: str | os.PathLike[str]
) -> pathlib.Path:
    """
    Make a skeleton CDF file from a CDF file.

    This replaces ``make_temp_CDFskeleton`` in IDL, which copies the file
    into a hard-coded temporary directory, and converts it into a
    skeleton table and back into a CDF file with the CDF command line
    tools ``skeletontable`` and ``skeletoncdf``. Here, the file is copied
    and the records of its record-varying variables are deleted. The
    changes that the round trip through a skeleton table makes, as seen
    in the L2 files split by IDL, are made too:

    - newlines in the string attributes of variables become spaces,
    - floating-point attributes of variables are rounded to the
      ``FORMAT`` of the variable, such as ``E7.2``, and
    - the pad value of each ``CDF_CHAR`` or ``CDF_UCHAR`` variable
      becomes one space.

    Parameters
    ----------
    cdffile : path-like
        The CDF file.
    skeletonfile : path-like
        The skeleton CDF file to make, which must not exist.

    Returns
    -------
    pathlib.Path
        ``skeletonfile``.
    """
    skeletonfile = pathlib.Path(skeletonfile)
    shutil.copyfile(cdffile, skeletonfile)
    cdf = pycdf.CDF(str(skeletonfile))
    try:
        cdf.readonly(False)  # ruff:ignore[FBT003]
        with ignore_chararray_deprecation():
            for name in cdf:
                var = cdf.raw_var(name)
                if var.rv() and len(var) > 0:
                    del cdf[name][...]
                if var.type() in (
                    pycdf.const.CDF_CHAR.value,
                    pycdf.const.CDF_UCHAR.value,
                ):
                    var.pad(" ")
                attrs = var.attrs
                fmt = attrs.get("FORMAT")
                if isinstance(fmt, bytes):
                    fmt = fmt.decode("ascii")
                for attr in list(attrs):
                    value = attrs[attr]
                    attr_type = attrs.type(attr)
                    if isinstance(value, (str, bytes)):
                        text = (
                            value.decode("ascii") if isinstance(value, bytes) else value
                        )
                        if "\n" in text:
                            attrs[attr] = text.replace("\n", " ")
                            attrs.type(attr, attr_type)
                    elif fmt is not None and attr_type in _REAL_TYPES:
                        attrs[attr] = _format_like_skeletontable(value, fmt)
                        attrs.type(attr, attr_type)
    finally:
        close_cdf(cdf)
    return skeletonfile


def _variable_types(path: pathlib.Path) -> dict[str, str]:
    """Return the ``VAR_TYPE`` attribute of each variable, in lower case."""
    with pycdf.CDF(str(path)) as cdf, ignore_chararray_deprecation():
        return {name: str(cdf[name].attrs.get("VAR_TYPE", "")).lower() for name in cdf}


def _write_from_skeleton(
    infile: pathlib.Path, out_cdf: pathlib.Path, buffer: dict[str, np.ndarray]
) -> None:
    """
    Write ``buffer`` into ``out_cdf``, with a skeleton made from ``infile``.

    Like `cdf_merge_to_daily`, the file is written at a temporary path and
    then renamed, so ``out_cdf`` can be ``infile``.
    """
    with tempfile.TemporaryDirectory() as tempdir:
        skeletonfile = make_temp_cdfskeleton(
            infile, pathlib.Path(tempdir) / "skeleton.cdf"
        )
        tmp_cdf = _temporary_path(out_cdf)
        try:
            _read_master_cdf(skeletonfile, tmp_cdf)
            _write_data_to_cdf(tmp_cdf, buffer, logical_file_id=out_cdf.stem)
            tmp_cdf.replace(out_cdf)
        except BaseException:
            tmp_cdf.unlink(missing_ok=True)
            raise


def _find_variable(odata: dict[str, np.ndarray], tag: str) -> str:
    """
    Return the name of the variable called ``tag``, ignoring case like IDL.

    Raises
    ------
    KeyError
        If there is no such variable.
    """
    for name in odata:
        if name.upper() == tag.upper():
            return name
    msg = f"No variable named {tag!r}"
    raise KeyError(msg)


def cdf_subset(
    infile: str | os.PathLike[str],
    tag: str,
    value_range: float | Sequence[float],
    outfile: str | os.PathLike[str] | None = None,
) -> pathlib.Path | None:
    """
    Write the records of a CDF file where a variable is in a range.

    The records in which the variable ``tag`` is between the smallest and
    largest of ``value_range``, inclusive, are written into a new file,
    whose skeleton is made from ``infile`` with `make_temp_cdfskeleton`.
    Variables that are not record-varying are copied unchanged.

    Parameters
    ----------
    infile : path-like
        The CDF file, which must have a variable named ``Epoch``.
    tag : str
        The name of the record-varying variable to select on, in any case.
    value_range : float or `~collections.abc.Sequence` of float
        The value, or the range of values, to select.
    outfile : path-like, optional
        The file to write. Defaults to the name of ``infile`` with
        ``_subset`` added before ``.cdf``.

    Returns
    -------
    pathlib.Path or None
        The file that was written, or `None` if no records are selected,
        in which case no file is written, as in IDL.

    Raises
    ------
    KeyError
        If there is no variable named ``tag``.
    ValueError
        If there is no ``Epoch`` variable.

    Notes
    -----
    IDL matches the variables of the file and the skeleton by position,
    and selects each variable along its first dimension with as many
    elements as ``Epoch`` has records. Here, variables are selected along
    their record dimension, which is the first, if they are
    record-varying. These are the same for the L2 files.
    """
    infile = pathlib.Path(infile)
    out_cdf = (
        infile.with_name(f"{infile.stem}_subset.cdf")
        if outfile is None
        else pathlib.Path(outfile)
    )
    odata, record_varying = _read_mycdf([infile])
    if "Epoch" not in odata:
        msg = f"No Epoch variable in {infile}"
        raise ValueError(msg)
    values = odata[_find_variable(odata, tag)]
    sel = np.flatnonzero(
        (values >= np.min(value_range)) & (values <= np.max(value_range))
    )
    if sel.size == 0:
        logger.info("No records of %s have %s in %s", infile, tag, value_range)
        return None
    buffer = {
        name: data[sel] if record_varying[name] else data
        for name, data in odata.items()
    }
    _write_from_skeleton(infile, out_cdf, buffer)
    logger.info("Wrote %d records of %s to %s", sel.size, infile, out_cdf)
    return out_cdf


def cdf_operate_on(
    infile: str | os.PathLike[str],
    tag: str,
    func: str,
    outfile: str | os.PathLike[str] | None = None,
) -> pathlib.Path | None:
    """
    Apply a function to the values of a variable of a CDF file that are not fill.

    The file is rewritten with a skeleton made from ``infile`` with
    `make_temp_cdfskeleton`. Like IDL, only the variables whose
    ``VAR_TYPE`` is ``data`` or ``support_data`` are written, so others
    keep the values in the skeleton.

    Parameters
    ----------
    infile : path-like
        The CDF file.
    tag : str
        The name of the variable to change, in any case.
    func : {"abs"}
        The name of the IDL function to apply.
    outfile : path-like, optional
        The file to write. Defaults to ``infile``, which is replaced.

    Returns
    -------
    pathlib.Path or None
        The file that was written, or `None` if every value is fill, in
        which case no file is written, as in IDL.

    Raises
    ------
    KeyError
        If there is no variable named ``tag``.
    ValueError
        If ``func`` is not supported.
    """
    if func not in _OPERATIONS:
        msg = f"The function must be one of {sorted(_OPERATIONS)}, not {func!r}"
        raise ValueError(msg)
    infile = pathlib.Path(infile)
    out_cdf = infile if outfile is None else pathlib.Path(outfile)
    odata, _ = _read_mycdf([infile])
    name = _find_variable(odata, tag)
    with pycdf.CDF(str(infile)) as cdf, ignore_chararray_deprecation():
        fillval = cdf[name].attrs["FILLVAL"]
    values = odata[name].copy()
    sel = values != fillval
    if not sel.any():
        logger.info("Every value of %s in %s is fill", tag, infile)
        return None
    values[sel] = _OPERATIONS[func](values[sel])
    odata[name] = values
    var_types = _variable_types(infile)
    buffer = {
        name: data
        for name, data in odata.items()
        if var_types[name] in ("data", "support_data")
    }
    _write_from_skeleton(infile, out_cdf, buffer)
    logger.info("Applied %s to %s in %s", func, tag, out_cdf)
    return out_cdf
