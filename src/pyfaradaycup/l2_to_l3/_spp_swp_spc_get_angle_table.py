"""Port of ``spp_swp_spc_get_angle_table.pro``."""

from __future__ import annotations

__all__ = [
    "ANGLE_TABLE_NAME",
    "CALIBRATION_DIR_ENV",
    "AngleTable",
    "spp_swp_spc_get_angle_table",
]

import dataclasses
import logging
import os
import pathlib

import numpy as np
from scipy.io import readsav

logger = logging.getLogger(__name__)

ANGLE_TABLE_NAME = "spp_swp_spc_calfiles_spc_uvphithetalookup_20190819.idl"
"""The name of the flow angle lookup table that IDL uses by default."""

CALIBRATION_DIR_ENV = "PYFARADAYCUP_CALIBRATION_DIR"
"""
The environment variable for the directory with the flow angle lookup table.

The table is 138 MB, so it is not in the package data.
"""


@dataclasses.dataclass(frozen=True)
class AngleTable:
    """
    The lookup table from sensor plate ratios to flow angles.

    This is the ``table`` structure in the IDL save file. The arrays have
    IDL's order of dimensions, so that ``u[i, j, m]`` here is
    ``table.u[i, j, m]`` in IDL, and a one-dimensional IDL subscript
    ``loc`` into ``phi`` is ``np.unravel_index(loc, phi.shape, order="F")``.
    """

    u: np.ndarray
    """
    The north–south ratio ``((C + D) - (A + B)) / I`` for each ``phi``,
    ``theta``, and Mach number, with shape ``(nphi, ntheta, nmach)``.
    """

    v: np.ndarray
    """
    The east–west ratio ``((A + D) - (B + C)) / I`` for each ``phi``,
    ``theta``, and Mach number, with shape ``(nphi, ntheta, nmach)``.
    """

    phi: np.ndarray
    """The deflection angle from the east–west ratio, in degrees, ``(nphi, ntheta)``."""

    theta: np.ndarray
    """The deflection angle from the north–south ratio, in degrees, ``(nphi, ntheta)``."""

    machnum: np.ndarray
    """The Mach numbers of the slices of ``u`` and ``v``, in increasing order."""

    file: pathlib.Path
    """The IDL save file that the table was read from."""


def _default_table_file() -> pathlib.Path:
    """
    Return the default flow angle lookup table, `ANGLE_TABLE_NAME`, in
    the directory given by the `CALIBRATION_DIR_ENV` environment variable.

    Raises
    ------
    FileNotFoundError
        If the environment variable is not set.
    """
    calibration_dir = os.environ.get(CALIBRATION_DIR_ENV)
    if not calibration_dir:
        msg = (
            f"The flow angle lookup table {ANGLE_TABLE_NAME} is not distributed "
            f"with pyfaradaycup. Give its path, or set the {CALIBRATION_DIR_ENV} "
            "environment variable to the directory that contains it."
        )
        raise FileNotFoundError(msg)
    return pathlib.Path(calibration_dir) / ANGLE_TABLE_NAME


def spp_swp_spc_get_angle_table(
    table_file: str | os.PathLike[str] | None = None,
) -> AngleTable:
    """
    Read the lookup table from sensor plate ratios to flow angles.

    Parameters
    ----------
    table_file : path-like, optional
        The IDL save file of the table. Defaults to `ANGLE_TABLE_NAME` in
        the directory given by the ``PYFARADAYCUP_CALIBRATION_DIR``
        environment variable, while IDL uses the same file in
        ``code_path + 'calibration/'``.

    Returns
    -------
    AngleTable
        The table.

    Raises
    ------
    FileNotFoundError
        If ``table_file`` is not given and ``PYFARADAYCUP_CALIBRATION_DIR``
        is not set, or if the file does not exist.
    """
    path = pathlib.Path(table_file) if table_file is not None else _default_table_file()
    if not path.is_file():
        msg = f"The flow angle lookup table {path} does not exist"
        raise FileNotFoundError(msg)
    logger.info("Reading the flow angle lookup table %s", path)
    table = readsav(str(path))["table"][0]
    # scipy.io.readsav reverses IDL's order of dimensions; transposing
    # (which makes views, not copies) restores it
    return AngleTable(
        u=np.asarray(table["U"]).T,
        v=np.asarray(table["V"]).T,
        phi=np.asarray(table["PHI"]).T,
        theta=np.asarray(table["THETA"]).T,
        machnum=np.asarray(table["MACHNUM"]),
        file=path,
    )
