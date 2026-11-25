"""Port of ``spp_swp_spc_split_l2cdf_by_mode.pro``."""

from __future__ import annotations

__all__ = ["SPLITS", "spp_swp_spc_split_l2cdf_by_mode"]

import logging
import pathlib
from typing import TYPE_CHECKING, NamedTuple

import numpy as np
from spacepy import pycdf

from pyfaradaycup.utils.cdf_to_survey import cdf_operate_on, cdf_subset

if TYPE_CHECKING:
    import os

logger = logging.getLogger(__name__)


class _Split(NamedTuple):
    """A file that the L2 file is split into."""

    suffix: str
    """What ``spc_l2_`` is replaced with in the name of the file, after ``spc_l2``."""

    modes: tuple[int, ...]
    """The values of ``MODE_FLAG`` in the file."""

    gate: tuple[int, ...]
    """The values of ``MODE_FLAG``, any of which must be present to write the file."""

    electron: bool
    """Whether the voltages are made positive, for electron modes."""


SPLITS = (
    _Split("e", (4, 5), (4, 5), electron=True),
    _Split("efa", (6,), (6,), electron=True),
    # IDL writes the electron calibration file if there are electron flux
    # angle spectra (mode 6), not electron calibration spectra (mode 7)
    _Split("ecal", (7,), (6,), electron=True),
    _Split("i", (0, 1), (0, 1), electron=False),
    _Split("ifa", (2,), (2,), electron=False),
    _Split("ifs", (1,), (1,), electron=False),
    _Split("ical", (3,), (3,), electron=False),
)
"""
The files that an L2 file is split into, in the order IDL writes them.

``MODE_FLAG`` is 0–3 for ion peak tracking, full scan, flux angle, and
calibration spectra, and 4–7 for the same electron spectra.
"""


def _split_name(l2file: pathlib.Path, suffix: str) -> pathlib.Path:
    """Return the name of a split file, replacing ``spc_l2_`` with ``spc_l2<suffix>_``."""
    return l2file.with_name(l2file.name.replace("spc_l2_", f"spc_l2{suffix}_"))


def spp_swp_spc_split_l2cdf_by_mode(
    l2file: str | os.PathLike[str],
) -> list[pathlib.Path]:
    """
    Split an L2 science file into files for each mode.

    The files are written next to ``l2file``, with ``spc_l2_`` in its name
    replaced by ``spc_l2i_`` (ion peak tracking and full scans),
    ``spc_l2ifa_`` (ion flux angle), ``spc_l2ifs_`` (ion full scans),
    ``spc_l2ical_`` (ion calibration), ``spc_l2e_``, ``spc_l2efa_``, or
    ``spc_l2ecal_`` (the same for electrons). Each file has the spectra of
    its modes, made with `~pyfaradaycup.utils.cdf_to_survey.cdf_subset`.
    In the electron files, the voltages ``mv_lo`` and ``mv_hi`` are made
    positive with `~pyfaradaycup.utils.cdf_to_survey.cdf_operate_on`.

    Parameters
    ----------
    l2file : path-like
        The L2 science file, such as ``spp_swp_spc_l2_20260803_v00.cdf``.

    Returns
    -------
    list of pathlib.Path
        The files that were written, which is empty if ``l2file`` has only
        one spectrum.

    Notes
    -----
    These behaviors of IDL are reproduced:

    - A file with only one spectrum is not split.
    - The electron calibration file is written only if there are electron
      flux angle spectra, since IDL checks the number of those rather
      than of electron calibration spectra. If there are none in that
      case, `~pyfaradaycup.utils.cdf_to_survey.cdf_subset` writes no
      file, and the voltages of the electron calibration file are not
      changed.
    - Ion full scans are in both the ``l2i`` and ``l2ifs`` files.

    Unlike IDL, which replaces ``spc_l2_`` anywhere in the path, only the
    name of the file is changed.
    """
    l2file = pathlib.Path(l2file)
    with pycdf.CDF(str(l2file)) as cdf:
        mode = np.asarray(cdf.raw_var("MODE_FLAG")[...])
    outfiles: list[pathlib.Path] = []
    if mode.size == 1:
        return outfiles
    for split in SPLITS:
        if not np.isin(mode, split.gate).any():
            continue
        outfile = _split_name(l2file, split.suffix)
        written = cdf_subset(l2file, "mode_flag", split.modes, outfile=outfile)
        if written is None:
            continue
        if split.electron:
            # flip the modulator voltages to their absolute values
            cdf_operate_on(written, "mv_lo", "abs")
            cdf_operate_on(written, "mv_hi", "abs")
        outfiles.append(written)
    logger.info("Split %s into %s", l2file, [path.name for path in outfiles])
    return outfiles
