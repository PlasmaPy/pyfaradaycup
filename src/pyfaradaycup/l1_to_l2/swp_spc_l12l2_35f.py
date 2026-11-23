"""
Convert SPC housekeeping L1 CDF files (APID 35F) into L2 CDF files.

This module is a port of the Python script ``swp_spc_l12l2_35f.py``,
which ``spp_swp_spc_l1_to_l2_date.pro`` spawns for each APID 35F L1
file before it makes the L2 science files. The raw values (DN) of
each housekeeping variable are converted into engineering units with
the formulas in ``conversion_formulas.qlf`` from GSEOS, and variables
without a formula are copied unchanged. The functions keep the names
of the functions in the script.
"""

from __future__ import annotations

__all__ = ["convert_one", "hk_dn2eng"]

import ast
import contextlib
import logging
import pathlib
import warnings
from typing import TYPE_CHECKING, cast

import numpy as np
from spacepy import pycdf

from pyfaradaycup._paths import data_dir
from pyfaradaycup.l05_to_l1.cdf_to_survey import _temporary_path
from pyfaradaycup.utils._cdf import close_cdf

if TYPE_CHECKING:
    import os
    from collections.abc import Callable, Generator, Iterable

logger = logging.getLogger(__name__)

CONVERSION_FORMULAS = data_dir / "conversion_formulas.qlf"
"""The GSEOS file with the formulas that convert DN into engineering units."""

SKELETON_35F = data_dir / "cdf_skeletons" / "psp_swp_spc_l2_35f_skeleton.cdf"
"""The skeleton CDF file for the L2 housekeeping files."""

_ALLOWED_NODES = (
    ast.Expression,
    ast.BinOp,
    ast.UnaryOp,
    ast.Add,
    ast.Sub,
    ast.Mult,
    ast.Div,
    ast.Pow,
    ast.USub,
    ast.UAdd,
    ast.Constant,
    ast.Name,
    ast.Load,
)
"""The syntax that a conversion formula may use."""


def _compile_formula(formula: str) -> Callable[[np.ndarray], np.ndarray]:
    """
    Return a function of ``a`` that evaluates a conversion formula.

    The original script evaluates ``"lambda a: " + formula`` with `eval`,
    after replacing ``Raw`` with ``a``. Here, the formula is checked to be
    arithmetic on ``a`` and numbers before it is compiled, and it is then
    evaluated as the same Python expression, so the results are the same.

    Raises
    ------
    ValueError
        If the formula is not arithmetic on ``a`` and numbers.
    """
    tree = ast.parse(formula, mode="eval")
    for node in ast.walk(tree):
        if (
            not isinstance(node, _ALLOWED_NODES)
            or (isinstance(node, ast.Name) and node.id != "a")
            or (
                isinstance(node, ast.Constant)
                and (
                    isinstance(node.value, bool)
                    or not isinstance(node.value, (int, float))
                )
            )
        ):
            msg = f"Conversion formula {formula!r} is not arithmetic on Raw"
            raise ValueError(msg)
    code = compile(tree, "<conversion formula>", "eval")

    def conversion(a: np.ndarray) -> np.ndarray:
        return eval(code, {"__builtins__": {}}, {"a": a})  # ruff:ignore[S307]  # checked above

    return conversion


def hk_dn2eng(
    keys: Iterable[str], fxn_path: str | os.PathLike[str] = CONVERSION_FORMULAS
) -> dict[str, Callable[[np.ndarray], np.ndarray]]:
    """
    Return functions that convert APID 35F variables from DN into
    engineering units.

    For each variable, the formula is on a line of ``fxn_path`` that
    starts with ``EU(Raw="APID_35F.<key>")``, after ``:=``. If several
    lines match, the last one is used, as in the original script.

    Parameters
    ----------
    keys : iterable of str
        The names of the variables in an APID 35F L1 file.
    fxn_path : path-like, optional
        The GSEOS file of conversion formulas. Defaults to the copy of
        ``conversion_formulas.qlf`` in the package data.

    Returns
    -------
    dict of str to callable
        For each variable that has a formula, a function that converts
        an array of float64 DN into engineering units. Variables without
        a formula are left out.

    Raises
    ------
    ValueError
        If a formula is not arithmetic on ``Raw`` and numbers.
    """
    with pathlib.Path(fxn_path).open() as fxn_file:
        fxn_lines = fxn_file.readlines()

    conv_fxns = {}
    for key in keys:
        # Each line for an SPC 0x35F variable starts with this pattern
        pattern = f'EU(Raw="APID_35F.{key}"'
        for line in fxn_lines:
            if line.startswith(pattern):
                conv_str = line.split(":=")[1].strip()
                conv_fxns[key] = _compile_formula(conv_str.replace("Raw", "a"))
    return conv_fxns


@contextlib.contextmanager
def _ignore_chararray_deprecation() -> Generator[None, None, None]:
    """
    Do not show the deprecation warning for `numpy.char.array`.

    spacepy 0.7.0 reads and copies string attributes with
    `numpy.char.array`, which NumPy 2.5 deprecates.
    """
    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore", "The chararray class is deprecated", DeprecationWarning
        )
        yield


def _l2filename(l1filename: str) -> str:
    """
    Return the name of the L2 file for an L1 file, replacing ``L1`` with
    ``l2hsk``.

    Raises
    ------
    ValueError
        If the name does not contain ``L1``.
    """
    # The original script names the file l1filename + "_L2" + extension,
    # without a dot, when "L1" is not in the name. Since the IDL code only
    # passes files whose names contain "L1", this raises an error instead.
    if "L1" not in l1filename:
        msg = f"The name of the L1 file {l1filename!r} does not contain 'L1'"
        raise ValueError(msg)
    return l1filename.replace("L1", "l2hsk")


def convert_one(
    l1file: str | os.PathLike[str],
    l2dir: str | os.PathLike[str] | None = None,
    *,
    overwrite: bool = False,
) -> pathlib.Path:
    """
    Convert an SPC housekeeping L1 file (APID 35F) into an L2 file.

    The L2 file is created from the skeleton
    ``psp_swp_spc_l2_35f_skeleton.cdf``. Its name is the name of the L1
    file with every ``L1`` replaced by ``l2hsk``, like
    ``spp_swp_spc_APID35Fl2hsk_20260803_v00.cdf``. Each variable that has
    a formula in ``conversion_formulas.qlf`` is converted from DN into
    engineering units as float64 values, and then stored as the type in
    the skeleton. The other variables are copied unchanged.

    Parameters
    ----------
    l1file : path-like
        The APID 35F L1 file.
    l2dir : path-like, optional
        The directory to write the L2 file into, which is created if it
        does not exist. Defaults to the directory of ``l1file``.
    overwrite : bool, default: False
        Whether to replace the L2 file if it already exists. The file is
        written at a temporary path and renamed when it is complete, so
        an existing file is left unchanged if writing fails.

    Returns
    -------
    pathlib.Path
        The L2 file.

    Raises
    ------
    FileNotFoundError
        If ``l1file`` does not exist.
    FileExistsError
        If the L2 file exists and ``overwrite`` is `False`.
    ValueError
        If the name of ``l1file`` does not contain ``L1``, or the L1 file
        has a variable that is not in the skeleton.

    Notes
    -----
    Like the original script, ``Epoch`` is copied by reading it as
    `datetime.datetime` values, which spacepy rounds to the nearest
    microsecond, so the ``CDF_TIME_TT2000`` values in the L2 file can
    differ from the L1 file by up to 500 ns.

    Also like the original script, each converted variable gets the
    attributes of the L1 variable, such as a ``UNITS`` of ``DN`` and a
    ``FILLVAL`` of the L1 type, rather than the attributes in the
    skeleton. The other variables keep the attributes in the skeleton.
    """
    l1file = pathlib.Path(l1file)
    l2dir = l1file.parent if l2dir is None else pathlib.Path(l2dir)
    l2file = l2dir / _l2filename(l1file.name)
    if not l1file.is_file():
        msg = f"Input L1 file {l1file} was not found"
        raise FileNotFoundError(msg)
    exists = l2file.exists()
    if exists and not overwrite:
        msg = f"{l2file} already exists; use overwrite to replace it"
        raise FileExistsError(msg)

    with pycdf.CDF(str(l1file)) as l1data, pycdf.CDF(str(SKELETON_35F)) as skeleton:
        # The original script would add variables that are not in the
        # skeleton to the L2 file, but they are not part of the L2 product.
        extra = [key for key in l1data if key not in skeleton]
        if extra:
            msg = f"{l1file} has variables that are not in {SKELETON_35F}: {extra}"
            raise ValueError(msg)
        conv_fxns = hk_dn2eng(l1data.keys())

        # Unlike the original script, which deletes an existing file before
        # writing the new one, the file is written at a temporary path and
        # then renamed, so that an existing file is only replaced by a
        # complete one.
        l2dir.mkdir(parents=True, exist_ok=True)
        tmp_file = _temporary_path(l2file)
        try:
            l2cdf = pycdf.CDF(str(tmp_file), str(SKELETON_35F))
            try:
                with _ignore_chararray_deprecation():
                    for key in l1data:
                        if key in conv_fxns:
                            # As in the original script, the values are a
                            # spacepy VarCopy, which keeps the attributes of
                            # the L1 variable through the arithmetic. When it
                            # is assigned, spacepy replaces the attributes from
                            # the skeleton with them.
                            dn = cast("pycdf.VarCopy", np.double(l1data[key].copy()))
                            l2cdf[key] = conv_fxns[key](dn)
                        else:
                            # np.array drops the attributes, so the ones from
                            # the skeleton are kept
                            l2cdf[key] = np.array(l1data[key].copy())
            finally:
                close_cdf(l2cdf)
            tmp_file.replace(l2file)
        except BaseException:
            tmp_file.unlink(missing_ok=True)
            raise
    logger.info("Wrote %s%s", l2file, ", replacing the existing file" if exists else "")
    return l2file
