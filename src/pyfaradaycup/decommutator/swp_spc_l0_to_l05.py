"""Contains the main function for the decommutator."""

# The original version of this file from /psp/code on fc was swp_spc_l02l1.py,
# which was run as a script.

# While the decommutator step goes from level 0 (L0) to level 0.5 (L05 or L0.5),
# the software and filenames have sometimes previously used level 1 (L1) in place
# of level 0.5. That has mostly been updated, but there are a few places that
# still use `L1` instead of `L05`.

# The following are relic comments from the original swp_spc_l02l1.py:

# Purpose: Convert binary "level-zero" or "ssr" files that come from the SWEM or Spacecraft
#         into L0.5 CDF files

# Requirements: Must have a reference to a skeleton file for the ApID that you wish to convert_one

# Input: path to a binary L0 file

# Output: saves a CDF file

# Revision History
# 	2020/02/03	-	Fix timing bug in 0x351 that arose when switching to spiceypy.  Add capability to produce 0x352 (time series) files.  Will require update to 0x352 (time series) skeleton also.  Update bug in naming of L1 files coming from gzip (spacecraft files, probably).  Remove versioning from skeleton files (since SVN is taking care of that).
# 	2020/01/29  -   Use spiceypy to adjust time of each measurement to SCET; remove unused command-line argument options
# 					Change method by which newest skeleton files are found; various other cleanups
# 	2019/08/27	-	Calling new ccsds_reader that separates out s/c from instr. packets
# 				-	Also, new ccsds_reader will use new packet finder (much faster), and does not scan through packets like before
# 	2019/08/23	-	Fixed bug that was reading in the oldest rather than newest skeleton file
# 				-	Added capability to read 0x081 and 0x262 packets from s/c hsk files.  Requires link to SC_HK.blk block definition file
# 				-	Added revision history


#  $URL: file:///psp/psp_swp_spc_code_repository/trunk/swp_spc_l02l1.py $
#  $LastChangedRevision: 97 $
#  $LastChangedDate: 2020-08-04 09:20:42 -0400 (Tue, 04 Aug 2020) $
#  $LastChangedBy: acase $

from __future__ import annotations

__all__ = [
    "main",
]

import datetime
import math
import pathlib
import warnings
from typing import TYPE_CHECKING, TextIO

import numpy as np
import spiceypy
from spacepy import pycdf

import pyfaradaycup.decommutator.ccsds_reader_pipeline as cc
from pyfaradaycup._paths import data_dir

if TYPE_CHECKING:
    import os

# The log file, which is opened by main
logfile: TextIO


def main(  # ruff:ignore[C901, PLR0912, PLR0913, PLR0915, PLR0917]
    l0file: str | os.PathLike[str],
    l05dir: str | os.PathLike[str] | None = None,
    logdir: str | os.PathLike[str] | None = None,
    spacecraft: bool = False,  # ruff:ignore[FBT001, FBT002]
    ptp: bool = False,  # ruff:ignore[FBT001, FBT002]
    gzip: bool = False,  # ruff:ignore[FBT001, FBT002]
    apidreq: int = 0,
    overwrite: bool = False,  # ruff:ignore[FBT001, FBT002]
    verbose: bool = False,  # ruff:ignore[FBT001, FBT002]
) -> None:
    """
    Convert one SPC L0 file into L0.5 CDF files, one per APID.

    Parameters
    ----------
    l0file : str or path-like
        Path to the L0 file to convert.

    l05dir : str or path-like, optional
        Directory for the L0.5 CDF files. If `None` (the default), the
        current directory is used. It is created if it does not exist.

    logdir : str or path-like, optional
        Directory for the log file. If `None` (the default), the current
        directory is used. It is created if it does not exist.

    spacecraft : bool, optional
        If `True`, read spacecraft housekeeping packets with
        `~pyfaradaycup.decommutator.ccsds_reader_pipeline.read_file_sc`.
        If `False`, read SWEAP instrument packets with
        `~pyfaradaycup.decommutator.ccsds_reader_pipeline.read_file`.

    ptp : bool, optional
        If `True`, the L0 file is a PTP file. Only used when
        ``spacecraft`` is `True`.

    gzip : bool, optional
        If `True`, read the L0 file as gzip-compressed.

    apidreq : int, optional
        Only create a CDF for this APID. If ``0``, create a CDF for
        every supported APID found in the file.

    overwrite : bool, optional
        If `True`, replace L0.5 CDF files that already exist. If `False`
        and a file already exists, a `FileExistsError` is raised.

    verbose : bool, optional
        If `True`, print messages to the screen as well as to the log
        file.

    Raises
    ------
    ValueError
        If ``l0file`` is not provided.

    FileExistsError
        If an L0.5 CDF file already exists and ``overwrite`` is `False`.

    RuntimeError
        If the log file cannot be opened, the SPICE kernels cannot be
        loaded, or the L0 file cannot be read.

    Notes
    -----
    Errors for a single APID do not stop the conversion. If the
    skeleton file cannot be read, the CDF cannot be created, or the CDF
    cannot be filled, the error is logged and the next APID is
    processed. A CDF that could not be filled may be left behind.
    """
    if not l0file:
        raise ValueError("Please supply l0file")  # ruff:ignore[EM101, TRY003]

    # Use the current directory for output files if no directory is given
    l0file = pathlib.Path(l0file)
    l05dir = pathlib.Path("." if l05dir is None else l05dir)
    logdir = pathlib.Path("." if logdir is None else logdir)

    # Get a version of filename with no extension
    l0file_noext = l0file.stem
    if l0file_noext[-3:] == "ptp":
        l0file_noext = pathlib.Path(l0file_noext).stem

    # Open a log file to write to
    nowdt = datetime.datetime.now()  # ruff:ignore[DTZ005]
    logpath = (
        logdir
        / f"swp_spc_l02l1_{nowdt.year:04.0f}{nowdt.month:02.0f}{nowdt.day:02.0f}{nowdt.hour:02.0f}{nowdt.minute:02.0f}{nowdt.second:02.0f}.log"
    )
    try:
        logdir.mkdir(parents=True, exist_ok=True)
        global logfile  # ruff:ignore[PLW0603]
        logfile = logpath.open("w")
    except Exception as exc:
        msg = f"Could not open log file: {logpath}"
        raise RuntimeError(msg) from exc
    # Write some information to the log file
    _statusmsg("filename = swp_spc_l0_to_l05.py", verbose=verbose)
    _statusmsg("timerun = " + nowdt.isoformat(), verbose=verbose)
    _statusmsg(f"l0file = {l0file}", verbose=verbose)
    _statusmsg(f"l05dir = {l05dir}", verbose=verbose)
    _statusmsg("spacecraft = " + repr(spacecraft), verbose=verbose)
    _statusmsg("ptp = " + repr(ptp), verbose=verbose)
    _statusmsg("gzip = " + repr(gzip), verbose=verbose)
    _statusmsg("apid = " + hex(apidreq), verbose=verbose)
    _statusmsg("overwrite = " + repr(overwrite), verbose=verbose)

    # Make sure the L0 file exists and is readable
    try:
        l0file.open().close()
        _statusmsg("L0 file exists and is readable")
    except OSError as exc:
        msg = f"Could not read L0 file: {l0file}"
        _statusmsg(
            f"***ERROR*** [swp_spc_l0_to_l05.py] {msg}...exiting",
            screen=True,
            verbose=verbose,
        )
        raise RuntimeError(msg) from exc

    # Load in Leap Second Kernel
    _statusmsg("***INFO*** [swp_spc_l0_to_l05.py] Finding newest leap second kernel...")
    tls_path = _get_newest_kernel(tls=True)
    if not tls_path:
        msg = "Could not find leap second kernel"
        _statusmsg(f"***ERROR*** [swp_spc_l0_to_l05.py] {msg}")
        raise RuntimeError(msg)
    else:  # ruff:ignore[RET506]
        try:
            _statusmsg(f"***INFO*** [swp_spc_l0_to_l05.py] Using: {tls_path}")
            spiceypy.furnsh(tls_path)
        except Exception as exc:
            msg = f"Could not load leap second kernel: {tls_path}"
            _statusmsg(f"***ERROR*** [swp_spc_l0_to_l05.py] {msg}")
            raise RuntimeError(msg) from exc

    # Load in S/C Clock Kernel
    _statusmsg("***INFO*** [swp_spc_l0_to_l05.py] Finding newest S/C clock kernel...")
    sclk_path = _get_newest_kernel(sclk=True)
    if not sclk_path:
        msg = "Could not find SCLK kernel"
        _statusmsg(f"***ERROR*** [swp_spc_l0_to_l05.py] {msg}")
        raise RuntimeError(msg)
    else:  # ruff:ignore[RET506]
        try:
            _statusmsg(f"***INFO*** [swp_spc_l0_to_l05.py] Using: {sclk_path}")
            spiceypy.furnsh(sclk_path)
        except Exception as exc:
            msg = f"Could not load SCLK kernel: {sclk_path}"
            _statusmsg(f"***ERROR*** [swp_spc_l0_to_l05.py] {msg}")
            raise RuntimeError(msg) from exc

    # Read in the L0 file into a python SPC data structure
    if spacecraft:
        _statusmsg("Event = Starting reading file: spacecraft")
        l0data = cc.read_file_sc(path=l0file, ptp=ptp, verbose=verbose, gzip=gzip)
    else:
        _statusmsg("Event = Starting reading file: non-spacecraft (instrument)")
        l0data = cc.read_file(path=l0file, verbose=verbose, gzip=gzip)
    _statusmsg("Event = Finished reading file")

    # Loop through the APIDs that we got
    for apid in l0data.keys():  # ruff:ignore[SIM118]
        _statusmsg(f"Event = Beginning APID: {hex(apid)}")

        if apid == 0x07B:  # ruff:ignore[PLR2004]
            _statusmsg(
                "***WARNING*** [swp_spc_l02l1] APID 0x07B CDFs not yet implemented",
                screen=True,
                verbose=verbose,
            )
            continue

        # Make sure we need to do this apid
        if len(l0data[apid][list(l0data[apid].keys())[0]]) == 0:  # ruff:ignore[RUF015]
            _statusmsg("No packets found for this apid.")
            continue  # skip this apid if there were no packets received
        if (apidreq != 0) & (apidreq != apid):
            _statusmsg("This apid not requested by user")
            continue  # skip this apid if user only wanted one apid and this isn't it

        # Filename for the L0.5 file we're about to write for this apid
        l1path = (
            l05dir / f"{l0file_noext}_APID{str(hex(apid)[2:].zfill(3)).upper()}_L1.cdf"  # ruff:ignore[FURB116]
        )
        _statusmsg(f"About to write: {l1path}")

        # Make sure the skeleton file exists and is readable
        try:
            skeleton_filename = _get_newest_skeleton(apid)
            pathlib.Path(skeleton_filename).open().close()
            _statusmsg("Skeleton to be used: " + skeleton_filename)
        except OSError:
            _statusmsg(
                "***ERROR*** [swp_spc_l0_to_l05.py] Skeleton file could not be read...moving to next apid",
                screen=True,
                verbose=verbose,
            )
            _statusmsg("Tried to use skeleton file: " + skeleton_filename)
            continue
        except TypeError:
            _statusmsg(
                f"***ERROR*** [swp_spc_l0_to_l05.py] Skeleton file for apid={hex(apid)} could not be found...moving to next apid",
                screen=True,
                verbose=verbose,
            )
            continue

        # See if the CDF file already exists
        try:
            # try to open and close it
            _statusmsg(f"Using L0.5 path: {l1path}", screen=True, verbose=verbose)
            l1path.open().close()

            # if we get here, this file already exists; so delete it, if desired
            _statusmsg(
                f"***INFO*** [swp_spc_l02l1] L0.5 CDF file ({l1path}) already exists",
                screen=True,
                verbose=verbose,
            )
            if overwrite:
                _statusmsg(
                    "***INFO*** [swp_spc_l0_to_l05] Overwriting existing L0.5 CDF",
                    screen=True,
                    verbose=verbose,
                )
                l1path.unlink()
            else:
                msg = (
                    f"L0.5 CDF already exists and overwrite was not requested: {l1path}"
                )
                _statusmsg(
                    f"***ERROR*** [swp_spc_l0_to_l05] {msg}",
                    screen=True,
                    verbose=verbose,
                )
                raise FileExistsError(msg)  # ruff:ignore[TRY301]
        except FileExistsError:
            raise
        except OSError:
            pass  # Apparently the file did not exist already
        except Exception as exc:
            msg = f"Could not check existence of or delete L0.5 CDF file: {l1path}"
            _statusmsg(
                f"***ERROR*** [swp_spc_l0_to_l05] {msg}",
                screen=True,
                verbose=verbose,
            )
            raise RuntimeError(msg) from exc

        # Create a new CDF file from the provided skeleton, creating the
        # L0.5 directory if it doesn't exist
        l1path.parent.mkdir(parents=True, exist_ok=True)
        try:
            cdf = pycdf.CDF(str(l1path), skeleton_filename)
        except pycdf.CDFError as exc:
            _statusmsg(
                f"***ERROR*** [swp_spc_l0_to_l05] Could not create new CDF (APID={hex(apid)}): {exc!r}...continuing to next APID",
                screen=True,
                verbose=verbose,
            )
            continue

        # Run a different procedure to put data into CDF file depending on APID
        cdfproc = {
            0x081: _cdf35e_35f,
            0x1DE: _cdf35e_35f,
            0x254: _cdf35e_35f,
            0x256: _cdf35e_35f,
            0x257: _cdf35e_35f,
            0x262: _cdf35e_35f,
            0x351: _cdf351_353_354,
            0x352: _cdf352,
            0x353: _cdf351_353_354,
            0x354: _cdf351_353_354,
            0x35E: _cdf35e_35f,
            0x35F: _cdf35e_35f,
        }
        try:
            cdfproc[apid](cdf, l0data[apid], verbose=verbose)
        except Exception as exc:  # ruff:ignore[BLE001]
            _statusmsg(
                f"***WARNING*** [swp_spc_l0_to_l05] CDF not processed for APID={hex(apid)}: {exc!r}",
                screen=True,
                verbose=verbose,
            )
            continue

        # Close the CDF. spacepy warns when a variable that the CDF
        # skeleton marks for compression does not get smaller when
        # compressed, which is harmless.
        with warnings.catch_warnings():
            warnings.filterwarnings(
                "ignore", message="DID_NOT_COMPRESS", category=pycdf.CDFWarning
            )
            cdf.close()

    _statusmsg(
        "***INFO*** [swp_spc_l02l1] Script complete.", screen=True, verbose=verbose
    )

    # Close the log file
    logfile.close()


def _cdf35e_35f(cdf: pycdf.CDF, dat: dict[str, list], verbose: bool = False) -> None:  # ruff:ignore[ARG001, C901, FBT001, FBT002]
    """
    Fill a CDF with housekeeping data, one row per packet.

    This handles SPC housekeeping packets (APIDs 0x35E and 0x35F) and
    the spacecraft housekeeping packets that `main` sends here
    (APIDs 0x081, 0x1DE, 0x254, 0x256, 0x257, and 0x262).

    Parameters
    ----------
    cdf : spacepy.pycdf.CDF
        The L0.5 CDF file to write the data into.

    dat : dict of str to list
        Decoded L0 data for one APID, with one entry per packet for
        each mnemonic.

    verbose : bool, optional
        Not currently used. Accepted so that `main` can call each CDF
        writer with the same arguments.

    Raises
    ------
    RuntimeError
        If a variable cannot be written to the CDF, such as when the
        data has the wrong shape or type for that variable.

    Notes
    -----
    Unlike `_cdf352` and `_cdf351_353_354`, the data is not expanded:
    each packet becomes one row in the CDF.

    ``"Epoch"`` (nanoseconds past J2000) is calculated from whichever
    MET fields ``dat`` contains: ``"CCSDS_MET"`` for SPC packets, or
    one of several ``*_TPSH_MET_SEC`` fields for spacecraft packets.
    If none are found, an error is logged and nothing is written.
    ``"Epoch"`` is also added to ``dat``.

    Each variable in the CDF is filled from the matching key in
    ``dat``. Variables with no matching key are filled with the
    variable's ``FILLVAL``.
    """
    # Calculate MET from the variables in the L0 data
    # MET of each NYS
    if "CCSDS_MET" in dat.keys():  # ruff:ignore[SIM118]
        scet = _secsubsec2scet(dat["CCSDS_MET"], dat["SW_SPC_SUBSEC"])
    elif "FSW_HK_HK_INST_TPSH_MET_SEC" in dat.keys():  # ruff:ignore[SIM118]
        scet = _secsubsec2scet(
            dat["FSW_HK_HK_INST_TPSH_MET_SEC"],
            dat["FSW_HK_HK_INST_TPSH_MET_SUBSEC"],
            spacecraft=True,
        )
    elif "PDU_PRIO94_TPSH_MET_SEC" in dat.keys():  # ruff:ignore[SIM118]
        scet = _secsubsec2scet(
            dat["PDU_PRIO94_TPSH_MET_SEC"],
            dat["PDU_PRIO94_TPSH_MET_SUBSEC"],
            spacecraft=True,
        )
    elif "HK_HIGH_TPSH_MET_SEC" in dat.keys():  # ruff:ignore[SIM118]
        scet = _secsubsec2scet(
            dat["HK_HIGH_TPSH_MET_SEC"], dat["HK_HIGH_TPSH_MET_SUBSEC"], spacecraft=True
        )
    elif "HK_FSWL_TPSH_MET_SEC" in dat.keys():  # ruff:ignore[SIM118]
        scet = _secsubsec2scet(
            dat["HK_FSWL_TPSH_MET_SEC"], dat["HK_FSWL_TPSH_MET_SUBSEC"], spacecraft=True
        )
    elif "HK_LOW_TPSH_MET_SEC" in dat.keys():  # ruff:ignore[SIM118]
        scet = _secsubsec2scet(
            dat["HK_LOW_TPSH_MET_SEC"], dat["HK_LOW_TPSH_MET_SUBSEC"], spacecraft=True
        )
    elif "RIU_DERIVED_TPSH_MET_SEC" in dat.keys():  # ruff:ignore[SIM118]
        scet = _secsubsec2scet(
            dat["RIU_DERIVED_TPSH_MET_SEC"],
            dat["RIU_DERIVED_TPSH_MET_SUBSEC"],
            spacecraft=True,
        )

    else:
        _statusmsg("Failed: could not create Epoch variable")
        return

    # Fill in values for each variable
    keys = cdf.keys()
    dat["Epoch"] = scet

    for key in keys:
        try:
            cdf[key] = dat[key]  # create variable and insert data
        except KeyError:  # ruff:ignore[PERF203]
            if key not in dat.keys():  # ruff:ignore[SIM118]
                cdf[key] = np.ones(len(dat["Epoch"])) * cdf[key].attrs["FILLVAL"]
        except (pycdf.CDFError, TypeError, ValueError) as exc:
            msg = f"Could not write variable {key!r} to the CDF: {exc}"
            raise RuntimeError(msg) from exc


def _cdf351_353_354(  # ruff:ignore[C901, PLR0912, PLR0915, RET503]
    cdf: pycdf.CDF,
    dat: dict[str, list],
    nocdf: bool = False,  # ruff:ignore[FBT001, FBT002]
    verbose: bool = False,  # ruff:ignore[FBT001, FBT002]
) -> dict[str, list] | None:
    """
    Expand SPC science packets (APIDs 0x351, 0x353, 0x354) and write them to a CDF.

    Each packet holds all the measurements from one NY second. This
    function gives every measurement its own timestamp and puts each
    variable into a flat array. APID 0x351 holds AllGain (ALL) data,
    0x353 holds SCI data, and 0x354 holds RSS data.

    Parameters
    ----------
    cdf : spacepy.pycdf.CDF
        The L0.5 CDF file to write the data into. Not used if ``nocdf``
        is `True`.

    dat : dict of str to list
        Decoded L0 data for one of these APIDs, with one entry per
        packet for each mnemonic. Must include ``"CCSDS_ApID"``,
        ``"CCSDS_MET"``, ``"SW_SPCSUBSEC"``, ``"SW_SPC_INTTIME"``,
        ``"SW_SPC_SERVTIME"``, ``"WINDOW"``, and the variable that
        sets the number of measurements (``"A1S"``, ``"ASIN"``, or
        ``"ARSS"``). APID 0x351 also needs ``"SW_SPC_PKTNUM"``.

    nocdf : bool, optional
        If `True`, return the expanded data instead of writing it to
        ``cdf``.

    verbose : bool, optional
        If `True`, print warnings and errors to the screen as well as
        to the log file.

    Returns
    -------
    dict of str to list or None
        If ``nocdf`` is `True`, the expanded data, with one value per
        measurement for each key. Otherwise, `None`.

    Raises
    ------
    RuntimeError
        If a variable in the CDF skeleton is not in the L0 data, or if
        a variable cannot be written to the CDF.

    Notes
    -----
    ``"Epoch"`` is in nanoseconds past J2000. Measurements are spaced
    by the integration time plus the settling time (IT + ST), in ticks
    of 1/1171.875 seconds (1024 ticks per NY second).
    """
    # Take data sorted by NYS, and produce one long variable with all data

    # APID of this packet
    apid = dat["CCSDS_ApID"][0]

    # Each different packet will require a different variable to calculate
    # The number of measurements each NYS
    if apid == 0x351:  # ruff:ignore[PLR2004]
        length_var = "A1S"
    elif apid == 0x353:  # ruff:ignore[PLR2004]
        length_var = "ASIN"
    elif apid == 0x354:  # ruff:ignore[PLR2004]
        length_var = "ARSS"

    # Calculate MET from the variables in the L0 data
    # MET of each NYS
    scet = _secsubsec2scet(dat["CCSDS_MET"], dat["SW_SPCSUBSEC"])

    # Same keys as original data dictionary, but will hold one variable per key
    # instead of one for every NYS for every key
    dat_exp = {}
    for key in dat.keys():  # ruff:ignore[SIM118]
        dat_exp[key] = []

    # Create the 'Epoch' variable in our data array
    dat_exp["Epoch"] = []

    # Loop through each NYS
    itst_warned = False
    for i in range(len(scet)):
        this_scet = scet[i]

        # Number of ticks each measurement takes (1024 ticks per NYS)
        ticks_per_meas = dat["SW_SPC_INTTIME"][i] + dat["SW_SPC_SERVTIME"][i]

        # Make sure ST and IT are allowed values
        if (math.log(ticks_per_meas, 2)) % 1 != 0:  # ruff:ignore[FURB163]
            # the SPC FPGA will default to IT=6, ST=2 (the power-on defaults) if a non-integer power of 2 IT+ST is requested
            ticks_per_meas = 8

            if not itst_warned:
                _statusmsg(
                    "***WARNING*** [swp_spc_l02l1] The reported IT+ST is not an even power of 2. Using IT=6,ST=2...",
                    screen=True,
                    verbose=verbose,
                )
                itst_warned = True

            # throw out packets if the IT and ST are different than both previous and next packets
            # this is almost surely an improperly identified packet that probably
            # isn't even an SPC packet, but got decommutated as such
            try:
                if (
                    (dat["SW_SPC_INTTIME"][i] != dat["SW_SPC_INTTIME"][i - 1])
                    & (dat["SW_SPC_INTTIME"][i] != dat["SW_SPC_INTTIME"][i + 1])
                    & (dat["SW_SPC_SERVTIME"][i] != dat["SW_SPC_SERVTIME"][i - 1])
                    & (dat["SW_SPC_SERVTIME"][i] != dat["SW_SPC_SERVTIME"][i + 1])
                ):
                    _statusmsg(
                        "***WARNING***IT+ST not 2^n, and not same as prev. and next values...so skipping this packet.",
                        screen=True,
                        verbose=verbose,
                    )
                    continue
            except IndexError:
                _statusmsg(
                    "***WARNING***IT+ST not 2^n, and not same as prev. and next values...so skipping this packet.",
                    screen=True,
                    verbose=verbose,
                )
                continue

        # Time that each measurement took this NYS
        tm_per_meas = (1.0 / 1171.875) * ticks_per_meas

        # Number of measurements this NYS
        nmeas = len(dat[length_var][i])

        # Expected number of measurements in a NYS
        exp_nmeas = 1024.0 / 1171.875 / tm_per_meas

        # Calculate the time array for this NYS
        add_time = np.arange(0, tm_per_meas * (nmeas - 0.1), tm_per_meas)

        # See if there were any times when we had retraces
        win = np.array(dat["WINDOW"][i])
        rtpix = (np.where((win[1:] - win[:-1]) < 0)[0]) + 1

        # Add on some time for each of the retraces
        # We don't need to do this if the expected number of measurements is equal to the number of measurements we received
        # This is because of the possibility that HV DAC tables were not loaded (probably only on the ground).
        # In that case, the FPGA does not actually take the time to do a retrace since it does not have to slew to a new DAC value
        # It doesn't matter that it is slewing to a new 'Window', since every window will have the same DAC value
        # There is a slight bug here in that the 'final' NYS after a HALT is sent, will likely be a partial packet
        #    so we might get tricked on our logical check here for the final packet when we do not have DAC tables loaded
        if nmeas != exp_nmeas:
            for thisrtpix in rtpix:
                add_time[thisrtpix:] += tm_per_meas

        # If we're in an AllGain packet, then the beginning of the packet might not be the beginning of the NYS (which is the time noted in the header)
        if apid == 0x351:  # ruff:ignore[PLR2004]
            pktnum = dat["SW_SPC_PKTNUM"][i]
            if pktnum != 0:
                if len(dat_exp["Epoch"]) == 0:
                    continue  # if file started on pktnum other than zero, then we can't know precise timing for the first 1-3 packets

                add_time += (dat_exp["Epoch"][-1] / 1e9 - this_scet / 1e9) + tm_per_meas

                # in case retrace was at end of last packet
                if (win[0] - dat_exp["WINDOW"][-1]) < 0:
                    add_time += tm_per_meas

        # Extend the new expanded dt
        dscet_extend = [this_scet + 1e9 * thisaddtime for thisaddtime in add_time]
        dat_exp["Epoch"].extend(dscet_extend)

        # Extend each of the data arrays
        for key in dat.keys():  # ruff:ignore[SIM118]
            try:
                dat_exp[key].extend(dat[key][i])
            except TypeError:  # ruff:ignore[PERF203]
                expanded = np.ones(nmeas) * dat[key][i]
                dat_exp[key].extend(expanded)

    if nocdf:
        return dat_exp
    # Fill in the CDF
    keys = list(cdf.keys())

    # Move 'Epoch' so that it is the first variable (so that we can be ISTP-compliant)
    if "Epoch" in keys:
        keys.remove("Epoch")
        keys.insert(0, "Epoch")

    for key in keys:
        try:
            # insert data
            cdf[key] = dat_exp[key]
        except KeyError as exc:  # ruff:ignore[PERF203]
            msg = f"The CDF skeleton has variable {key!r}, but the L0 data does not"
            _statusmsg(f"Failed : {msg}", screen=True, verbose=verbose)
            raise RuntimeError(msg) from exc
        except (pycdf.CDFError, TypeError, ValueError) as exc:
            msg = f"Could not write variable {key!r} to the CDF: {exc}"
            _statusmsg(f"Failed : {msg}", screen=True, verbose=verbose)
            raise RuntimeError(msg) from exc


def _cdf352(  # ruff:ignore[C901, PLR0912, PLR0915]
    cdf: pycdf.CDF,
    dat: dict[str, list],
    nocdf: bool = False,  # ruff:ignore[FBT001, FBT002]
    verbose: bool = False,  # ruff:ignore[FBT001, FBT002]
) -> dict[str, list] | tuple[()]:
    """
    Expand SPC time series (APID 0x352) packets into L0.5 data and write them to a CDF.

    Each 0x352 packet holds many fast measurements from one NY second,
    for four channels at a time. This function gives every measurement
    its own timestamp and puts each channel into a flat array.

    Parameters
    ----------
    cdf : spacepy.pycdf.CDF
        The L0.5 CDF file to write the data into. Not used if ``nocdf``
        is `True`.

    dat : dict of str to list
        Decoded L0 data for APID 0x352, with one entry per packet for
        each mnemonic. Must include ``"CCSDS_MET"``, ``"SW_SPCSUBSEC"``,
        ``"SPC_TIMESERCOLL"``, ``"SPC_TIMESERTICK"``, and the
        measurement arrays ``"G0_000"`` through ``"G3_000"``.

    nocdf : bool, optional
        If `True`, return the expanded data instead of writing it to
        ``cdf``.

    verbose : bool, optional
        If `True`, print error messages to the screen as well as to the
        log file.

    Returns
    -------
    dict of str to list or tuple
        If ``nocdf`` is `True`, the expanded data, with one value per
        measurement for each key. Otherwise, an empty tuple.

    Raises
    ------
    RuntimeError
        If an unexpected error occurs while expanding the packets.

    Notes
    -----
    ``"SPC_TIMESERCOLL"`` sets which four channels a packet contains:
    ``1``, ``2``, ``4``, and ``8`` for the A, B, C, and D collectors
    (channels 0-3), and ``16`` and ``32`` for two sets of housekeeping
    voltages. The values go into ``"VAR0"`` through ``"VAR3"``, and the
    channel names go into ``"VAR0_NAME"`` through ``"VAR3_NAME"``.
    Packets with any other value are logged as errors and skipped.

    Unlike `_cdf351_353_354`, if a variable cannot be written to the
    CDF, the error is logged and the remaining variables are still
    written.

    ``"Epoch"`` is in nanoseconds past J2000. Each measurement is
    spaced ``1 / (32 * 1171.875)`` seconds apart, starting at the
    packet's start tick. Values that appear once per packet are
    repeated for every measurement in that packet.
    """
    try:
        # Calculate SCET from the variables in the L0 data
        dt = _secsubsec2scet(dat["CCSDS_MET"], dat["SW_SPCSUBSEC"])

        # Same keys as original data dictionary, but will hold one variable per key
        # instead of one for every NYS for every key
        dat_exp = {}
        for key in dat.keys():  # ruff:ignore[SIM118]
            if key[-4:] == "_000":
                continue
            dat_exp[key] = []

        dat_exp["VAR0"] = []
        dat_exp["VAR1"] = []
        dat_exp["VAR2"] = []
        dat_exp["VAR3"] = []
        dat_exp["VAR0_NAME"] = []
        dat_exp["VAR1_NAME"] = []
        dat_exp["VAR2_NAME"] = []
        dat_exp["VAR3_NAME"] = []

        # Var names for each possible channel that might be contained in the packet
        avars = ["A0", "A1", "A2", "A3"]
        bvars = ["B0", "B1", "B2", "B3"]
        cvars = ["C0", "C1", "C2", "C3"]
        dvars = ["D0", "D1", "D2", "D3"]
        hk1vars = ["HV_DAC_IN", "P3p3_Vmon", "P12_Vmon", "N12_Vmon"]
        hk2vars = ["HV_Out", "Rail_Ctrl", "P5_Vmon", "N5_Vmon"]

        # To convert from the ID number in each packet header to the variables that
        # the packet actually contains values for
        coll2var = {1: avars, 2: bvars, 4: cvars, 8: dvars, 16: hk1vars, 32: hk2vars}

        # Create the 'Epoch' variable in our data array
        dat_exp["Epoch"] = []

        # Time that each measurement took this NYS
        tm_per_meas = 1.0 / 32.0 / 1171.875

        for i in range(len(dt)):
            # MET for this NY second
            thisdt = dt[i]

            # Collector (or HSK values) that are being used this NYS
            # An integer that references which variables are actually contained in the packet
            coll_used = dat["SPC_TIMESERCOLL"][i]

            # Number of measurements this NYS
            nmeas = len(dat["G0_000"][i])  # should always be 20*32=640

            # Packet start time
            pkt_start = dat["SPC_TIMESERTICK"][i] / 1171.875

            # Calculate the time array for this NYS
            add_time = pkt_start + np.arange(
                0, tm_per_meas * (nmeas - 0.1), tm_per_meas
            )

            try:
                if coll_used not in coll2var:
                    raise ValueError(  # ruff:ignore[TRY003, TRY301]
                        f"Value: {coll_used} not in coll2var.keys()"  # ruff:ignore[EM102]
                    )  # probably a corrupt packet

                dat_exp["VAR0_NAME"].extend(
                    [coll2var[coll_used][0] for foo in range(nmeas)]
                )
                dat_exp["VAR1_NAME"].extend(
                    [coll2var[coll_used][1] for foo in range(nmeas)]
                )
                dat_exp["VAR2_NAME"].extend(
                    [coll2var[coll_used][2] for foo in range(nmeas)]
                )
                dat_exp["VAR3_NAME"].extend(
                    [coll2var[coll_used][3] for foo in range(nmeas)]
                )

                dat_exp["VAR0"].extend(dat["G0_000"][i])
                dat_exp["VAR1"].extend(dat["G1_000"][i])
                dat_exp["VAR2"].extend(dat["G2_000"][i])
                dat_exp["VAR3"].extend(dat["G3_000"][i])

            except ValueError as exc:
                _statusmsg(
                    f"***ERROR*** Could not process 0x352 packet (probably it was a false positive ID of a 0x352 packet?): {exc}",
                    screen=True,
                    verbose=verbose,
                )
                continue

            # Extend the expanded dt
            dt_extend = [thisdt + sec * 1e9 for sec in add_time]
            dat_exp["Epoch"].extend(dt_extend)

            # Extend each of the data arrays
            for key in dat.keys():  # ruff:ignore[SIM118]
                if key[-4:] == "_000":
                    continue
                try:
                    dat_exp[key].extend(dat[key][i])
                except TypeError:
                    expanded = np.ones(nmeas) * dat[key][i]
                    dat_exp[key].extend(expanded)

        if nocdf:
            return dat_exp
        # Fill in the CDF
        keys = list(cdf.keys())

        # Move 'Epoch' so that it is the first variable (so that we can be ISTP-compliant)
        if "Epoch" in keys:
            keys.remove("Epoch")
            keys.insert(0, "Epoch")
        for key in keys:
            try:
                # insert data
                cdf[key] = dat_exp[key]
            except KeyError:  # ruff:ignore[PERF203]
                _statusmsg(
                    f"Failed : The CDF skeleton has variable {key!r}, but the L0 data does not",
                    screen=True,
                    verbose=verbose,
                )
            except (pycdf.CDFError, TypeError, ValueError) as exc:
                _statusmsg(
                    f"Failed : Could not write variable {key!r} to the CDF: {exc}",
                    screen=True,
                    verbose=verbose,
                )
    except Exception as exc:
        msg = "Could not process the APID 0x352 packets"
        raise RuntimeError(msg) from exc

    return ()


def _secsubsec2scet(
    sec: list[int],
    subsec: list[int],
    spacecraft: bool = False,  # ruff:ignore[FBT001, FBT002]
) -> list[float]:
    """
    Convert MET seconds and subseconds to ephemeris time in nanoseconds.

    The conversion uses the PSP spacecraft clock through SPICE.

    Parameters
    ----------
    sec : list of int
        MET whole seconds, from the first 4 bytes of the CCSDS time
        field.

    subsec : list of int
        MET subseconds, from the next 2 bytes of the CCSDS time field.

    spacecraft : bool, optional
        If `True`, ``subsec`` is in units of 1/256 second, as used in
        spacecraft packets. If `False`, ``subsec`` is in units of
        1/65536 second, as used in SWEAP packets.

    Returns
    -------
    list of float
        Ephemeris time for each input, in nanoseconds past J2000,
        rounded to the nearest nanosecond.

    Notes
    -----
    The subseconds are rescaled to the 1/50000 second ticks used by
    the PSP clock kernel, and each time is converted with
    ``spiceypy.scs2e`` using NAIF ID -96 (PSP). The PSP clock (SCLK)
    and leap second kernels must already be loaded.
    """
    sec_str = [f"{i:1.0f}" for i in sec]
    subsec_str_base50000 = [
        f"{int(i * 50000 / 65536):05.0f}" for i in subsec
    ]  # SWEAP has subseconds in 1/65536's of a second
    if spacecraft:
        subsec_str_base50000 = [
            f"{int(i * 50000 / 256):05.0f}" for i in subsec
        ]  # S/C has subseconds in 1/256's of a second

    ephem_sec_j2000 = [
        spiceypy.scs2e(-96, sec_str[i] + ":" + subsec_str_base50000[i])
        for i in range(len(sec_str))
    ]
    ephem_nanosec_j2000 = [np.round(1e9 * i) for i in ephem_sec_j2000]

    return ephem_nanosec_j2000  # ruff:ignore[RET504]


def _statusmsg(
    string: str,
    screen: bool = False,  # ruff:ignore[FBT001, FBT002]
    file: bool = True,  # ruff:ignore[FBT001, FBT002]
    verbose: bool = False,  # ruff:ignore[FBT001, FBT002]
) -> None:
    """
    Write a timestamped status message to the log file and/or the screen.

    Parameters
    ----------
    string : str
        The message to write.

    screen : bool, optional
        If `True`, also print the message to the screen, but only when
        ``verbose`` is also `True`.

    file : bool, optional
        If `True`, write the message to the log file.

    verbose : bool, optional
        Must be `True` for ``screen`` to have any effect.

    Notes
    -----
    Messages written to the log file start with the current local time
    in ISO format, followed by a comma. The log file is the global
    ``logfile`` opened by `main`, so this function only works after
    `main` has opened it.
    """
    nowdtstr = datetime.datetime.now().isoformat()  # ruff:ignore[DTZ005]
    if file:
        logfile.write(nowdtstr + ", " + string + "\n")
    if screen:  # ruff:ignore[SIM102]
        if verbose:
            print(string)  # ruff:ignore[T201]


def _get_newest_kernel(
    tls: bool = False,  # ruff:ignore[FBT001, FBT002]
    sclk: bool = False,  # ruff:ignore[FBT001, FBT002]
) -> str:
    """
    Find the newest NAIF leap second or PSP clock (SCLK) kernel file.

    Exactly one of ``tls`` or ``sclk`` must be `True`.

    Parameters
    ----------
    tls : bool, optional
        If `True`, find the newest leap second kernel
        (``naif00NN.tls``).

    sclk : bool, optional
        If `True`, find the newest PSP clock kernel
        (``spp_sclk_NNNN.tsc``).

    Returns
    -------
    str
        Path to the kernel file with the highest version number.

    Raises
    ------
    RuntimeError
        If both or neither of ``tls`` and ``sclk`` are `True`.

    Notes
    -----
    The kernels are searched for under ``moc_data_products/`` in the
    package data directory, ``src/pyfaradaycup/data/``. The version
    number is read from the digits at the end of the file name.
    """
    # Choose exactly one of the options
    if tls + sclk != 1:
        raise RuntimeError("Need exactly one of tls or sclk")  # ruff:ignore[EM101, TRY003]

    # TODO: make this less hardcoded to the directory  # ruff:ignore[FIX002, TD002, TD003]
    # Kristoff said that there's a spacepy(.pycdf?) command that regenerates
    # these files; we'll need to look into this.  This should be automated.

    # Search in the MOC data product directory for newest file
    if tls:
        globdir = data_dir / "moc_data_products" / "leap_second_kernel"
        globstr = "naif00[0-9][0-9].tls"
        ndigits = 2
    elif sclk:  # probably only the most recent one is needed?
        globdir = data_dir / "moc_data_products" / "operations_sclk_kernel"
        globstr = "spp_sclk_[0-9][0-9][0-9][0-9].tsc"
        ndigits = 4

    files = sorted(globdir.glob(globstr))

    # isolate version numbers from the file path and find newest
    if tls or sclk:
        versions = [int(file.stem[-ndigits:]) for file in files]
    try:
        maxind = np.argmax(versions)
    except ValueError as exc:
        msg = f"Could not find any kernel files matching {globstr} in {globdir}"
        _statusmsg(f"***ERROR*** {msg}")
        raise RuntimeError(msg) from exc

    # return path to newest file
    return str(files[maxind])


def _get_newest_skeleton(apid: int) -> str:
    """
    Return the path to the skeleton CDF file for an APID.

    Parameters
    ----------
    apid : int
        The APID of the skeleton file, such as ``0x352``.

    Returns
    -------
    str
        The path ``cdf_skeletons/psp_swp_spc_l1_<apid>_skeleton.cdf``
        inside the package data directory, ``src/pyfaradaycup/data/``,
        with the APID as three lowercase hexadecimal digits.

    Notes
    -----
    The function does not check that the file exists. Earlier versions
    searched for the newest versioned skeleton file; that code is
    kept below as comments.
    """
    # skeleton ≈ metadata schema in the form of an empty CDF file
    return str(
        data_dir
        / "cdf_skeletons"
        / f"psp_swp_spc_l1_{hex(apid)[2:].zfill(3)}_skeleton.cdf"  # ruff:ignore[FURB116]
    )
