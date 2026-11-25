"""Port of ``spp_swp_spc_spectra_to_l2cdf.pro``."""

from __future__ import annotations

__all__ = ["L2_SKELETON", "spp_swp_spc_spectra_to_l2cdf"]

import datetime
import logging
import pathlib
import re
from typing import TYPE_CHECKING, Any

import numpy as np
from spacepy import pycdf

from pyfaradaycup._paths import data_dir
from pyfaradaycup.l1_to_l2._spp_swp_spc_crosstalk_correction_factor import (
    spp_swp_spc_crosstalk_correction_factor,
)
from pyfaradaycup.l1_to_l2._spp_swp_spc_get_effective_area import (
    spp_swp_spc_get_effective_area,
)
from pyfaradaycup.l1_to_l2._spp_swp_spc_get_startdate import spp_swp_spc_get_startdate
from pyfaradaycup.l1_to_l2._spp_swp_spc_ivt_to_spectra import MAX_WINDOWS
from pyfaradaycup.l1_to_l2._spp_swp_spc_moments import spp_swp_spc_moments
from pyfaradaycup.utils._cdf import temporary_path
from pyfaradaycup.utils.cdf_to_survey import (
    _read_master_cdf,
    _write_data_to_cdf,
)

if TYPE_CHECKING:
    import os

    from pyfaradaycup.l1_to_l2._spp_swp_spc_ivt_to_spectra import Spectra

logger = logging.getLogger(__name__)

_SKELETON_DIR = data_dir / "cdf_skeletons"

L2_SKELETON = _SKELETON_DIR / "psp_l2_spc_00000000_v04.cdf"
"""The skeleton of the L2 science files, the last ``psp_l2_spc_000*.cdf``."""

_PREFIX = "spp_swp_spc_l2_"

_f = np.float32
_MV_DELTA_FACTOR = _f(0.01)
"""The placeholder uncertainty of the voltages, as a fraction."""

_CURRENT_DELTA_FACTOR = np.float64(_f(0.04))
"""The placeholder uncertainty of the currents, as a fraction."""

_FLOW_ANGLE_DELTA = _f(0.04)
"""The placeholder uncertainty of the flow angles, in radians."""

_MAX_MODE_FLAG = 7


def _raw_attr(cdf: pycdf.CDF, name: str, attr: str) -> Any:  # ruff:ignore[ANN401]
    """Return a variable attribute of a CDF, with ``CDF_TIME_TT2000`` values as integers."""
    value = cdf[name].attrs[attr]
    if isinstance(value, datetime.datetime):
        return np.int64(pycdf.lib.datetime_to_tt2000(value))
    return value


def _next_savefile(l2dir: pathlib.Path, date: datetime.date) -> pathlib.Path:
    """
    Return the next version of the L2 file for ``date``.

    Like IDL, the version is one more than the highest version of the
    existing files for the date, or 0 if there are none.
    """
    savepath = l2dir / f"{date:%Y}" / f"{date:%m}"
    stem = f"{_PREFIX}{date:%Y%m%d}"
    versions = [
        int(match.group(1))
        for path in savepath.glob(f"{stem}_*.cdf")
        if (match := re.search(r"(\d\d)\.cdf$", path.name))
    ]
    version = max(versions) + 1 if versions else 0
    return savepath / f"{stem}_v{version:02d}.cdf"


def _pad(values: np.ndarray, fillval: Any, dtype: type) -> np.ndarray:  # ruff:ignore[ANN401]
    """Return ``values`` in an array with 128 windows, padded with ``fillval``."""
    padded = np.full((values.shape[0], MAX_WINDOWS), fillval, dtype=dtype)
    padded[:, : values.shape[1]] = values
    return padded


def spp_swp_spc_spectra_to_l2cdf(  # ruff:ignore[PLR0913, PLR0915]
    spectra: Spectra,
    *,
    l2dir: str | os.PathLike[str],
    skeletonfile: str | os.PathLike[str] | None = None,
    savefile: str | os.PathLike[str] | None = None,
    coupling_history_file: str | os.PathLike[str] | None = None,
    ew_timedep_correct: bool = False,
    ns_timedep_correct: bool = False,
) -> pathlib.Path:
    """
    Write spectra into an L2 science CDF file.

    The file is created from the skeleton and has, for each spectrum,
    ``Epoch`` (the earliest time), the time of each window after window 0
    (``measurement_time``), the window voltages, the currents on the four
    sensor plates, the flow angles, the differential charge flux density,
    their placeholder uncertainties, and ``MODE_FLAG``. The arrays have
    128 windows, padded with fill values, and values outside the valid
    range of the skeleton are fill.

    Parameters
    ----------
    spectra : Spectra
        The spectra.
    l2dir : path-like
        The L2 directory. The file is written in its ``YYYY/MM/``
        subdirectory for the date of the earliest time, which is created
        if it does not exist, as ``spp_swp_spc_l2_YYYYMMDD_vNN.cdf``.
    skeletonfile : path-like, optional
        The skeleton. Defaults to `L2_SKELETON`.
    savefile : path-like, optional
        The file to write instead, which must not exist.
    coupling_history_file : path-like, optional
        The crosstalk coupling history, passed to
        `spp_swp_spc_crosstalk_correction_factor`.
    ew_timedep_correct, ns_timedep_correct : bool, default: False
        Whether to correct the east–west and north–south flow angles with
        the time-dependent crosstalk correction factors.

    Returns
    -------
    pathlib.Path
        The file that was written.

    Raises
    ------
    FileExistsError
        If ``savefile`` exists.

    Notes
    -----
    Like IDL, the version ``NN`` is one more than the highest version of
    the existing files for the date, so each run writes a new file. The
    file is written at a temporary path and renamed when it is complete.

    The types of IDL are kept, so the results are the same:

    - ``measurement_time`` is computed in ``float64`` from the
      ``CDF_TIME_TT2000`` times, which rounds them to multiples of 128 ns
      before the time of window 0 is subtracted, because the fill value of
      ``measurement_time`` in the skeleton is ``CDF_REAL8``.
    - The currents, their uncertainties, and the differential charge
      flux density are ``float64`` until they are written as ``CDF_REAL4``,
      because the spectra currents are ``float64``.
    - The voltages and flow angles are ``float32``.

    IDL also converts ``Epoch`` to calendar values and back with
    ``CDF_TT2000``, as a check, which does not change it and is not
    ported. The time-dependent crosstalk correction factors are always
    computed, as in IDL, so the coupling history must exist, but they are
    only used if ``ew_timedep_correct`` or ``ns_timedep_correct`` is set.
    """
    skeletonfile = (
        pathlib.Path(skeletonfile) if skeletonfile is not None else L2_SKELETON
    )
    if savefile is None:
        savefile = _next_savefile(
            pathlib.Path(l2dir), spp_swp_spc_get_startdate(spectra)
        )
    savefile = pathlib.Path(savefile)
    if savefile.exists():
        msg = f"{savefile} already exists"
        raise FileExistsError(msg)

    moments = spp_swp_spc_moments(spectra)

    with pycdf.CDF(str(skeletonfile)) as ref:
        attrs = {
            name: {
                attr: _raw_attr(ref, name, attr)
                for attr in ("FILLVAL", "VALIDMIN", "VALIDMAX")
                if attr in ref[name].attrs
            }
            for name in ref
        }
    nspec, nwin = spectra.time.shape
    fill = spectra.fill
    buffer: dict[str, np.ndarray] = {}

    with np.errstate(invalid="ignore", divide="ignore"):
        # Epoch: the earliest valid time of each spectrum
        epoch_attrs = attrs["Epoch"]
        temp = spectra.time.copy()
        time_fill = (
            (temp == fill)
            | (temp < 0)
            | (temp < epoch_attrs["VALIDMIN"])
            | (temp > epoch_attrs["VALIDMAX"])
        )
        if time_fill.any():
            # manipulate the array for ordering with min()
            temp[time_fill] = temp.max() + 99999
        epoch = temp.min(axis=1)
        epoch[
            (epoch < 0)
            | (epoch < epoch_attrs["VALIDMIN"])
            | (epoch > epoch_attrs["VALIDMAX"])
        ] = epoch_attrs["FILLVAL"]
        buffer["Epoch"] = epoch

        # measurement_time: the time of each window after that of window 0
        mt_fillval = attrs["measurement_time"]["FILLVAL"]
        if time_fill.any():
            # IDL assigns the double fill value to the int64 array
            temp[time_fill] = np.iinfo(np.int64).min
        temp1 = np.full((nspec, MAX_WINDOWS), mt_fillval, dtype=np.float64)
        temp1[:, :nwin] = temp
        mt_fill = (temp1 < 0) | (temp1 == fill) | ~np.isfinite(temp1)
        temp1 = temp1 - temp1[:, :1]
        temp1[mt_fill] = mt_fillval
        buffer["measurement_time"] = temp1

        # mv_hi and mv_lo, with placeholder uncertainties of 1%
        mv: dict[str, np.ndarray] = {}
        for name in ("mv_hi", "mv_lo"):
            a = attrs[name]
            temp = _pad(getattr(spectra, name), a["FILLVAL"], np.float32)
            mv_fill = (
                (temp < a["VALIDMIN"])
                | (temp > a["VALIDMAX"])
                | (temp == fill)
                | ~np.isfinite(temp)
            )
            temp[mv_fill] = a["FILLVAL"]
            mv[name] = temp
            buffer[name] = temp
            delta = _pad(
                _MV_DELTA_FACTOR * getattr(spectra, name),
                attrs[f"{name}_DELTA_VAR"]["FILLVAL"],
                np.float32,
            )
            delta[mv_fill] = attrs[f"{name}_DELTA_VAR"]["FILLVAL"]
            buffer[f"{name}_DELTA_VAR"] = delta

        # currents, with placeholder uncertainties of 4%
        currents = []
        deltas = []
        for k, sen in enumerate("abcd"):
            name = f"{sen}_current"
            a = attrs[name]
            temp = _pad(spectra.current[:, :, k], a["FILLVAL"], np.float64)
            current_fill = (
                (temp < a["VALIDMIN"])
                | (temp > a["VALIDMAX"])
                | (temp == fill)
                | (mv["mv_lo"] == attrs["mv_lo"]["FILLVAL"])
                | (mv["mv_hi"] == attrs["mv_hi"]["FILLVAL"])
                | ~np.isfinite(temp)
            )
            temp[current_fill] = a["FILLVAL"]
            currents.append(temp)
            buffer[name] = temp

            delta_fillval = attrs[f"{name}_DELTA_VAR"]["FILLVAL"]
            delta = _pad(
                _CURRENT_DELTA_FACTOR * spectra.current[:, :, k],
                delta_fillval,
                np.float64,
            )
            delta[current_fill] = delta_fillval
            delta[(delta < 0) | (delta == fill)] = delta_fillval
            deltas.append(delta)
            buffer[f"{name}_DELTA_VAR"] = delta

        # Correct the flow angles for the time-dependent crosstalk, if asked
        get_kew, get_kns = spp_swp_spc_crosstalk_correction_factor(
            epoch, file=coupling_history_file
        )
        kew = get_kew if ew_timedep_correct else _f(1.0)
        kns = get_kns if ns_timedep_correct else _f(1.0)
        phi = moments.phi * kew
        theta = moments.theta * kns
        effareas = spp_swp_spc_get_effective_area(phi, theta)

        # flow_angle, with a placeholder uncertainty of 0.04 rad
        a = attrs["flow_angle"]
        temp = np.stack((phi, theta), axis=1)
        angle_fill = (
            (temp < a["VALIDMIN"][0]) | (temp > a["VALIDMAX"][0]) | np.isnan(temp)
        )
        temp[angle_fill] = a["FILLVAL"]
        temp2 = spectra.current[:, :, 0].max(axis=1)
        row_fill = (temp2 == fill) | ~np.isfinite(temp2)
        temp[row_fill, :] = a["FILLVAL"]
        buffer["flow_angle"] = temp
        delta_fillval = attrs["flow_angle_DELTA_VAR"]["FILLVAL"]
        delta = np.full(temp.shape, _FLOW_ANGLE_DELTA, dtype=np.float32)
        delta[angle_fill] = delta_fillval
        delta[row_fill, :] = delta_fillval
        buffer["flow_angle_DELTA_VAR"] = delta

        # diff_charge_flux_density: the total current per effective area in cm²
        ea_cm2 = effareas.dat / _f(100.0)
        itot = currents[0] + currents[1] + currents[2] + currents[3]
        ditot = deltas[0] + deltas[1] + deltas[2] + deltas[3]
        dcfd = itot / ea_cm2[:, np.newaxis]
        dcfd_sigma = ditot / ea_cm2[:, np.newaxis]
        dcfd_fill = (currents[0] == attrs["a_current"]["FILLVAL"]) | ~np.isfinite(dcfd)
        dcfd[dcfd_fill] = attrs["diff_charge_flux_density"]["FILLVAL"]
        dcfd_sigma[dcfd_fill] = attrs["diff_charge_flux_density_DELTA_VAR"]["FILLVAL"]
        buffer["diff_charge_flux_density"] = dcfd
        buffer["diff_charge_flux_density_DELTA_VAR"] = dcfd_sigma

    # MODE_FLAG: 0-3 are ion peak tracking, full scan, flux angle, and
    # calibration, and 4-7 are the same for electrons
    fa = spectra.famode.astype(np.int16)
    fs = spectra.fullscan.astype(np.int16)
    cal = spectra.cal.astype(np.int16)
    flag = fs + 2 * fa + 3 * cal + 4 * spectra.emode.astype(np.int16)
    flag[(flag > _MAX_MODE_FLAG) | ((fa + fs + cal) > 1)] = attrs["MODE_FLAG"][
        "FILLVAL"
    ]
    buffer["MODE_FLAG"] = flag

    # Write the values with the types of the skeleton
    savefile.parent.mkdir(parents=True, exist_ok=True)
    tmp_file = temporary_path(savefile)
    try:
        _read_master_cdf(skeletonfile, tmp_file)
        with pycdf.CDF(str(tmp_file)) as cdf:
            dtypes = {
                name: pycdf.lib.numpytypedict[cdf.raw_var(name).type()]
                for name in buffer
            }
        _write_data_to_cdf(
            tmp_file,
            {name: values.astype(dtypes[name]) for name, values in buffer.items()},
            logical_file_id=savefile.stem,
        )
        tmp_file.replace(savefile)
    except BaseException:
        tmp_file.unlink(missing_ok=True)
        raise
    logger.info("Wrote %d spectra to %s", nspec, savefile)
    return savefile
