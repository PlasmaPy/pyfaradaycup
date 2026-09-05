"""
#  $URL: file:///psp/psp_swp_spc_code_repository/trunk/swp_spc_l02l1.py $
#  $LastChangedRevision: 97 $
#  $LastChangedDate: 2020-08-04 09:20:42 -0400 (Tue, 04 Aug 2020) $
#  $LastChangedBy: acase $
"""  # noqa: D400

__all__ = [
    "cdf35e_35f",
    "cdf351_353_354",
    "cdf352",
    "get_newest_kernel",
    "get_newest_skeleton",
    "main",
    "secsubsec2scet",
    "setup",
    "statusmsg",
]

import argparse
import datetime
import glob
import math
import os
import sys

import numpy as np

try:
    from spacepy import pycdf
except:  # noqa: E722
    # TODO: If we are using newer version of SpacePy (>= 0.3, give or take)
    # then we don't need this.
    print(sys.exc_info())  # noqa: T201
    print("***ERROR*** Could not import pycdf from spacepy")  # noqa: T201
    print(  # noqa: T201
        "\t You must have the environmental variable CDF_LIB set, perhaps to /opt/cdf/lib?"
    )
    sys.exit()

import distutils.dir_util

import spiceypy

import pyfaradaycup.pipeline.ccsds_reader_pipeline as cc

# Purpose: Convert binary "level-zero" or "ssr" files that come from the SWEM or Spacecraft
#         into L0.5 or L1 CDF files

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


def main(  # noqa: ANN201, C901, PLR0912, PLR0913, PLR0915, PLR0917
    l0file="",  # noqa: ANN001
    l1dir="",  # noqa: ANN001
    logdir="",  # noqa: ANN001
    spacecraft=False,  # noqa: ANN001, FBT002
    ptp=False,  # noqa: ANN001, FBT002
    gzip=False,  # noqa: ANN001, FBT002
    apidreq=0,  # noqa: ANN001
    overwrite=False,  # noqa: ANN001, FBT002
    verbose=False,  # noqa: ANN001, FBT002
):
    """Convert a single L0 file to L1"""  # noqa: D400
    # Try to create a filename for the new CDF that we're going to create
    l0dirname = os.path.dirname(l0file)  # noqa: PTH120
    l0basename = os.path.basename(l0file)  # noqa: PTH119
    if l1dir == "":
        l1dir = (
            l0dirname  # use input L0 directory for L1 files, if nothing else specified
        )

    # Get a version of filename with no extension
    l0file_noext = os.path.splitext(l0basename)[0]  # noqa: PTH122
    if l0file_noext[-3:] == "ptp":
        l0file_noext = os.path.splitext(l0file_noext)[0]  # noqa: PTH122

    # Open a log file to write to
    nowdt = datetime.datetime.now()  # noqa: DTZ005
    if logdir == "":
        logdir = l1dir  # use L1 file output directory for log file, if nothing else specified
    distutils.dir_util.mkpath(
        logdir
    )  # in case the directory doesn't exist, this will create it
    logpath = os.path.join(  # noqa: PTH118
        logdir,
        f"swp_spc_l02l1_{nowdt.year:04.0f}{nowdt.month:02.0f}{nowdt.day:02.0f}{nowdt.hour:02.0f}{nowdt.minute:02.0f}{nowdt.second:02.0f}.log",
    )
    try:
        global logfile  # noqa: PLW0603
        logfile = open(logpath, "w")  # noqa: PTH123, SIM115
    except:  # noqa: E722
        print("\n***ERROR*** Could not open log file!\n")  # noqa: T201
        sys.exit(1)

    # Write some information to the log file
    statusmsg("scriptname = swp_spc_l02l1.py", verbose=verbose)
    statusmsg("timerun = " + nowdt.isoformat(), verbose=verbose)
    statusmsg("l0file = " + l0file, verbose=verbose)
    statusmsg("l1dir = " + l1dir, verbose=verbose)
    statusmsg("spacecraft = " + repr(spacecraft), verbose=verbose)
    statusmsg("ptp = " + repr(ptp), verbose=verbose)
    statusmsg("gzip = " + repr(gzip), verbose=verbose)
    statusmsg("apid = " + hex(apidreq), verbose=verbose)
    statusmsg("overwrite = " + repr(overwrite), verbose=verbose)

    # Make sure the L0 file exists and is readable
    try:
        foo = open(l0file)  # noqa: PTH123, SIM115
        foo.close()
        statusmsg("L0 file exists and is readable")
    except OSError:
        statusmsg(
            "***ERROR*** [swp_spc_l02l1.py] Input L0 file could not be read...exiting",
            screen=True,
            verbose=verbose,
        )
        import pdb  # noqa: PLC0415, T100

        pdb.set_trace()  # noqa: T100
        sys.exit()

    # Load in Leap Second Kernel
    statusmsg("***INFO*** [swp_spc_l02l1.py] Finding newest leap second kernel...")
    tls_path = get_newest_kernel(tls=True)
    if not tls_path:
        statusmsg(
            "***ERROR*** [swp_spc_l02l1.py] Could not find leap second kernel...exiting"
        )
        sys.exit()
    else:
        try:
            statusmsg(f"***INFO*** [swp_spc_l02l1.py] Using: {tls_path}")
            spiceypy.furnsh(tls_path)
        except:  # noqa: E722
            statusmsg(
                "***ERROR*** [swp_spc_l02l1.py] Could not furnsh leap second kernel...exiting"
            )
            sys.exit()

    # Load in S/C Clock Kernel
    statusmsg("***INFO*** [swp_spc_l02l1.py] Finding newest S/C clock kernel...")
    sclk_path = get_newest_kernel(sclk=True)
    if not sclk_path:
        statusmsg("***ERROR*** [swp_spc_l02l1.py] Could not find SCLK kernel...exiting")
        sys.exit()
    else:
        try:
            statusmsg(f"***INFO*** [swp_spc_l02l1.py] Using: {sclk_path}")
            spiceypy.furnsh(sclk_path)
        except:  # noqa: E722
            statusmsg(
                "***ERROR*** [swp_spc_l02l1.py] Could not furnsh SCLK kernel...exiting"
            )
            sys.exit()

    # Read in the L0 file into a python SPC data structure
    if spacecraft:
        statusmsg("Event = Starting reading file: spacecraft")
        l0data = cc.read_file_sc(path=l0file, ptp=ptp, verbose=verbose, gzip=gzip)
    else:
        statusmsg("Event = Starting reading file: non-spacecraft (instrument)")
        l0data = cc.read_file(path=l0file, verbose=verbose, gzip=gzip)
    statusmsg("Event = Finished reading file")

    # Loop through the APIDs that we got
    for apid in l0data.keys():  # noqa: SIM118
        statusmsg(f"Event = Beginning APID: {hex(apid)}")

        if apid == 0x07B:  # noqa: PLR2004
            statusmsg(
                "***WARNING*** [swp_spc_l02l1] APID 0x07B CDFs not yet implemented",
                screen=True,
                verbose=verbose,
            )
            continue

        # Make sure we need to do this apid
        if len(l0data[apid][list(l0data[apid].keys())[0]]) == 0:  # noqa: RUF015
            statusmsg("No packets found for this apid.")
            continue  # skip this apid if there were no packets received
        if (apidreq != 0) & (apidreq != apid):
            statusmsg("This apid not requested by user")
            continue  # skip this apid if user only wanted one apid and this isn't it

        # Filename for the L1 file we're about to write for this apid
        l1path = os.path.join(  # noqa: PTH118
            l1dir,
            l0file_noext + f"_APID{str(hex(apid)[2:].zfill(3)).upper()}_L1.cdf",  # noqa: FURB116
        )
        statusmsg("About to write: " + l1path)

        # Make sure the skeleton file exists and is readable
        try:
            skeleton_filename = get_newest_skeleton(apid)
            foo = open(skeleton_filename)  # noqa: PTH123, SIM115
            foo.close()
            statusmsg("Skeleton to be used: " + skeleton_filename)
        except OSError:
            statusmsg(
                "***ERROR*** [swp_spc_l02l1.py] Skeleton file could not be read...moving to next apid",
                screen=True,
                verbose=verbose,
            )
            statusmsg("Tried to use skeleton file: " + skeleton_filename)
            continue
        except TypeError:
            statusmsg(
                f"***ERROR*** [swp_spc_l02l1.py] Skeleton file for apid={hex(apid)} could not be found...moving to next apid",
                screen=True,
                verbose=verbose,
            )
            continue

        # See if the CDF file already exists
        try:
            # try to open and close it
            statusmsg("Using L1 path: " + l1path, screen=True, verbose=verbose)
            foo = open(l1path)  # noqa: PTH123, SIM115
            foo.close()

            # if we get here, this file already exists; so delete it, if desired
            statusmsg(
                f"***INFO*** [swp_spc_l02l1] L1 CDF file ({l1path}) already exists",
                screen=True,
                verbose=verbose,
            )
            if overwrite:
                statusmsg(
                    "***INFO*** [swp_spc_l02l1] Overwriting existing L1 CDF",
                    screen=True,
                    verbose=verbose,
                )
                os.remove(l1path)  # noqa: PTH107
            else:
                statusmsg(
                    "***ERROR*** [swp_spc_l02l1] L1 CDF already exists, and overwrite (-o option) was not requested...exiting.",
                    screen=True,
                    verbose=verbose,
                )
                raise (SystemExit)  # noqa: TRY301
        except SystemExit:
            sys.exit()
        except OSError:
            pass  # Apparently the file did not exist already
        except:  # noqa: E722
            statusmsg(repr(sys.exc_info()), screen=True, verbose=verbose)
            statusmsg(
                "\n***ERROR*** [swp_spc_l02l1] Could not check existence/delete L1 CDF file path. Exiting...\n",
                screen=True,
                verbose=verbose,
            )
            sys.exit()

        # Create a new CDF file from the provided skeleton
        try:
            cdf = pycdf.CDF(l1path, skeleton_filename)
        except "CDFError":  # noqa: B030
            statusmsg(
                f"\n***ERROR*** [swp_spc_l02l1] Could not create new CDF (APID={apid})...continuing to next APID\n).",
                screen=True,
                verbose=verbose,
            )
            statusmsg(sys.exc_info(), screen=True, verbose=verbose)
            continue

        # Run a different procedure to put data into CDF file depending on APID
        cdfproc = {
            0x081: cdf35e_35f,
            0x1DE: cdf35e_35f,
            0x254: cdf35e_35f,
            0x256: cdf35e_35f,
            0x257: cdf35e_35f,
            0x262: cdf35e_35f,
            0x351: cdf351_353_354,
            0x352: cdf352,
            0x353: cdf351_353_354,
            0x354: cdf351_353_354,
            0x35E: cdf35e_35f,
            0x35F: cdf35e_35f,
        }
        try:
            cdfproc[apid](cdf, l0data[apid], verbose=verbose)
        except:  # noqa: E722
            statusmsg(repr(sys.exc_info()), screen=True, verbose=verbose)
            statusmsg(
                f"***WARNING*** [swp_spc_l02l1] CDF not processed for APID={hex(apid)}",
                screen=True,
                verbose=verbose,
            )
            continue

        # Close the CDF
        # import pdb; pdb.set_trace()
        cdf.close()

    statusmsg(
        "***INFO*** [swp_spc_l02l1] Script complete.", screen=True, verbose=verbose
    )

    # Close the log file
    logfile.close()


def cdf35e_35f(cdf, dat, verbose=False):  # noqa: ANN001, FBT002
    """Fill up a CDF with data from an SPC HSK (0x35E or 0x35F) packet or S/C HSK packet"""  # noqa: D400
    # Calculate MET from the variables in the L0 data
    # MET of each NYS
    if "CCSDS_MET" in dat.keys():  # noqa: SIM118
        scet = secsubsec2scet(dat["CCSDS_MET"], dat["SW_SPC_SUBSEC"])
    elif "FSW_HK_HK_INST_TPSH_MET_SEC" in dat.keys():  # noqa: SIM118
        scet = secsubsec2scet(
            dat["FSW_HK_HK_INST_TPSH_MET_SEC"],
            dat["FSW_HK_HK_INST_TPSH_MET_SUBSEC"],
            spacecraft=True,
        )
    elif "PDU_PRIO94_TPSH_MET_SEC" in dat.keys():  # noqa: SIM118
        scet = secsubsec2scet(
            dat["PDU_PRIO94_TPSH_MET_SEC"],
            dat["PDU_PRIO94_TPSH_MET_SUBSEC"],
            spacecraft=True,
        )
    elif "HK_HIGH_TPSH_MET_SEC" in dat.keys():  # noqa: SIM118
        scet = secsubsec2scet(
            dat["HK_HIGH_TPSH_MET_SEC"], dat["HK_HIGH_TPSH_MET_SUBSEC"], spacecraft=True
        )
    elif "HK_FSWL_TPSH_MET_SEC" in dat.keys():  # noqa: SIM118
        scet = secsubsec2scet(
            dat["HK_FSWL_TPSH_MET_SEC"], dat["HK_FSWL_TPSH_MET_SUBSEC"], spacecraft=True
        )
    elif "HK_LOW_TPSH_MET_SEC" in dat.keys():  # noqa: SIM118
        scet = secsubsec2scet(
            dat["HK_LOW_TPSH_MET_SEC"], dat["HK_LOW_TPSH_MET_SUBSEC"], spacecraft=True
        )
    elif "RIU_DERIVED_TPSH_MET_SEC" in dat.keys():  # noqa: SIM118
        scet = secsubsec2scet(
            dat["RIU_DERIVED_TPSH_MET_SEC"],
            dat["RIU_DERIVED_TPSH_MET_SUBSEC"],
            spacecraft=True,
        )

    else:
        statusmsg("Failed: could not create Epoch variable")
        return

    # Fill in values for each variable
    keys = cdf.keys()
    dat["Epoch"] = scet

    for key in keys:
        try:
            cdf[key] = dat[key]  # create variable and insert data
        except KeyError:  # noqa: PERF203
            if key not in dat.keys():  # noqa: SIM118
                cdf[key] = np.ones(len(dat["Epoch"])) * cdf[key].attrs["FILLVAL"]
        except:  # noqa: E722
            import pdb  # noqa: PLC0415, T100

            pdb.set_trace()  # noqa: T100
            statusmsg(
                f"Failed : Key:{key} failed insert into CDF",
                screen=True,
                verbose=verbose,
            )
            statusmsg(sys.exc_info())


#####################################################
##
#####################################################
def cdf351_353_354(cdf, dat, nocdf=False, verbose=False):  # noqa: ANN001, ANN201, C901, FBT002, PLR0912, PLR0915, RET503
    """Fill up a CDF with SCI, ALL, or RSS data."""
    # Take data sorted by NYS, and produce one long variable with all data

    # APID of this packet
    apid = dat["CCSDS_ApID"][0]

    # Each different packet will require a different variable to calculate
    # The number of measurements each NYS
    if apid == 0x351:  # noqa: PLR2004
        length_var = "A1S"
    elif apid == 0x353:  # noqa: PLR2004
        length_var = "ASIN"
    elif apid == 0x354:  # noqa: PLR2004
        length_var = "ARSS"

    # Calculate MET from the variables in the L0 data
    # MET of each NYS
    scet = secsubsec2scet(dat["CCSDS_MET"], dat["SW_SPCSUBSEC"])

    # MET of each measurement (to be filled in in the future)
    scet_exp = []  # noqa: F841

    # Same keys as original data dictionary, but will hold one variable per key
    # instead of one for every NYS for every key
    dat_exp = {}
    for key in dat.keys():  # noqa: SIM118
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
        if (math.log(ticks_per_meas, 2)) % 1 != 0:  # noqa: FURB163
            # the SPC FPGA will default to IT=6, ST=2 (the power-on defaults) if a non-integer power of 2 IT+ST is requested
            ticks_per_meas = 8

            if not itst_warned:
                statusmsg(
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
                    statusmsg(
                        "***WARNING***IT+ST not 2^n, and not same as prev. and next values...so skipping this packet.",
                        screen=True,
                        verbose=verbose,
                    )
                    continue
            except IndexError:
                statusmsg(
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
        if apid == 0x351:  # noqa: PLR2004
            pktnum = dat["SW_SPC_PKTNUM"][i]
            # if pktnum==0: import pdb; pdb.set_trace()
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
        for key in dat.keys():  # noqa: SIM118
            try:
                dat_exp[key].extend(dat[key][i])
            except TypeError:  # noqa: PERF203
                expanded = np.ones(nmeas) * dat[key][i]
                dat_exp[key].extend(expanded)

    if nocdf:
        return dat_exp
    # Fill in the CDF
    keys = cdf.keys()

    # Move 'Epoch' so that it is the first variable (so that we can be ISTP-compliant)
    epochloc = np.where(np.array(keys) == "Epoch")[0]
    if len(epochloc) != 0:
        keys.pop(epochloc[0])
        keys.insert(0, "Epoch")

    for key in keys:
        try:
            # insert data
            cdf[key] = dat_exp[key]
        except:  # noqa: E722, PERF203
            statusmsg(
                f"Failed : Key:{key} failed insert into CDF",
                screen=True,
                verbose=verbose,
            )
            statusmsg(repr(sys.exc_info()), screen=True, verbose=verbose)
            import pdb  # noqa: PLC0415, T100

            pdb.set_trace()  # noqa: T100


def cdf352(cdf, dat, nocdf=False, verbose=False):  # noqa: ANN001, FBT002
    try:
        # Calculate SCET from the variables in the L0 data
        dt = secsubsec2scet(dat["CCSDS_MET"], dat["SW_SPCSUBSEC"])

        # Same keys as original data dictionary, but will hold one variable per key
        # instead of one for every NYS for every key
        dat_exp = {}
        for key in dat.keys():  # noqa: SIM118
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
                    raise ValueError(  # noqa: TRY003
                        f"Value: {coll_used} not in coll2var.keys()"  # noqa: EM102
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

            except:  # noqa: E722
                statusmsg(
                    "***ERROR*** Could not process 0x352 packet (probably it was a false positive ID of a 0x352 packet?)"
                )
                statusmsg(repr(sys.exc_info()), screen=True, verbose=verbose)
                continue

            # Extend the expanded dt
            dt_extend = [thisdt + sec * 1e9 for sec in add_time]
            dat_exp["Epoch"].extend(dt_extend)

            # Extend each of the data arrays
            for key in dat.keys():  # noqa: SIM118
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
        keys = cdf.keys()

        # Move 'Epoch' so that it is the first variable (so that we can be ISTP-compliant)
        epochloc = np.where(np.array(keys) == "Epoch")[0]
        if len(epochloc) != 0:
            keys.pop(epochloc[0])
            keys.insert(0, "Epoch")
        for key in keys:
            try:
                # insert data
                cdf[key] = dat_exp[key]
            except:  # noqa: E722, PERF203
                statusmsg(
                    f"Failed : Key:{key} failed insert into CDF",
                    screen=True,
                    verbose=verbose,
                )
                statusmsg(repr(sys.exc_info()), screen=True, verbose=verbose)
    except:  # noqa: E722
        print(sys.exc_info())  # noqa: T201
        import pdb  # noqa: PLC0415, T100

        pdb.set_trace()  # noqa: T100

    return ()


def secsubsec2scet(sec, subsec, spacecraft=False, verbose=False):  # noqa: ANN001, ANN201, ARG001, FBT002
    """Parse a fairly standard CCSDS time structure into decimal MET: first 4 bytes=MET seconds, second 2 bytes = MET subseconds"""  # noqa: D400
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

    return ephem_nanosec_j2000  # noqa: RET504


def statusmsg(string, screen=False, file=True, verbose=False):  # noqa: ANN001, ANN201, FBT002
    """Output status message to screen or logfile (default to file, but not screen)"""  # noqa: D400
    nowdtstr = datetime.datetime.now().isoformat()  # noqa: DTZ005
    if file:
        logfile.write(nowdtstr + ", " + string + "\n")
    if screen:  # noqa: SIM102
        if verbose:
            print(string)  # noqa: T201


def get_newest_kernel(tls=False, sclk=False, verbose=False):  # noqa: ANN001, ANN201, ARG001, FBT002
    """Find the path to the newest NAIF TLS (leap second) kernel file"""  # noqa: D400
    # Make sure we chose exactly one of the options
    if tls + sclk != 1:
        return False

    # Search in the MOC data product directory for newest file
    if tls:
        globdir = "/psp/data/moc_data_products/leap_second_kernel/"
        globstr = globdir + "naif00[0-9][0-9].tls"
        ndigits = 2
    elif sclk:
        globdir = "/psp/data/moc_data_products/operations_sclk_kernel/"
        globstr = globdir + "spp_sclk_[0-9][0-9][0-9][0-9].tsc"
        ndigits = 4

    files = glob.glob(globstr)  # noqa: PTH207

    # isolate version numbers from the file path and find newest
    if tls or sclk:
        versions = [int(i[-4 - ndigits : -4]) for i in files]
    try:
        maxind = np.argmax(versions)
    except ValueError:
        statusmsg("***ERROR*** Could not find kernel versions")
        print(sys.exc_info())  # noqa: T201
        import pdb  # noqa: PLC0415, T100

        pdb.set_trace()  # noqa: T100
        return False

    # return path to newest file
    path = files[maxind]
    return path  # noqa: RET504


def get_newest_skeleton(apid, verbose=False):  # noqa: ANN001, ANN201, ARG001, FBT002
    """Find the path to the newest skeleton CDF file"""  # noqa: D400
    return f"cdf_skeletons/psp_swp_spc_l1_{hex(apid)[2:].zfill(3)}_skeleton.cdf"  # noqa: FURB116

    # The remaining code in this function is from when we used skeleton file numbers with a version # in them
    # and we had to search for the most recent (highest) version

    # Search for newest file
    # globstr = 'cdf_skeletons/spp_apid_{:}_sweap_00000000t000000_v[0-9][0-9].cdf'.format(hex(apid)[2:].zfill(3))
    # ndigits = 2

    # files = glob.glob(globstr)

    # isolate version numbers from the file path and find newest
    # versions = [int(i[-4-ndigits:-4]) for i in files]

    # try:
    # maxind = np.argmax(versions)
    # except ValueError:
    # statusmsg('***ERROR*** Could not find skeleton versions')
    # return(False)

    # return path to newest file
    # path = files[maxind]

    # return(path)


#####################################################
###
#####################################################
def setup():  # noqa: ANN201
    """Get user command-line input and set things up"""  # noqa: D400
    # defaults
    l0file_default = ""
    l0dir_default = ""
    l1dir_default = ""
    logdir_default = ""
    apid_default = "0"

    # Get User Input
    parser = argparse.ArgumentParser(description="")
    parser.add_argument(
        "-v",
        "--verbose",
        default=False,
        action="store_true",
        help="Increase verbosity",
        required=False,
    )
    parser.add_argument(
        "-gz",
        "--gzip",
        default=False,
        action="store_true",
        help="Read in L0 file as gzip",
        required=False,
    )
    parser.add_argument(
        "-sc",
        "--spacecraft",
        default=False,
        action="store_true",
        help="Look for S/C packets",
        required=False,
    )
    parser.add_argument(
        "-b",
        "--batch",
        default=False,
        action="store_true",
        help="Convert all L0 files in same directory as selected",
        required=False,
    )
    parser.add_argument(
        "-r",
        "--recursive",
        default=False,
        action="store_true",
        help="Convert all L0 files in given directory and in all subdirectories",
        required=False,
    )
    parser.add_argument(
        "-p",
        "--ptp",
        default=False,
        action="store_true",
        help="Indicate that input L0 file is a PTP file",
        required=False,
    )
    parser.add_argument(
        "-o",
        "--overwrite",
        default=False,
        action="store_true",
        help="Overwrite existing L1 CDF file, if necessary",
        required=False,
    )
    parser.add_argument(
        "-stc",
        "--stcorrect",
        default=False,
        action="store_true",
        help="If ST is wrong (FPGA bug if ST set higher than 2), then try to correct it)",
        required=False,
    )
    parser.add_argument(
        "-a",
        "--apid",
        help=f"APID to create L1 file for [0==all] [default={apid_default}]",
        required=False,
        default=apid_default,
        type=str,
    )
    parser.add_argument(
        "-l0",
        "--l0file",
        help=f"Input L0 File [default={l0file_default}]",
        required=False,
        default=l0file_default,
    )
    parser.add_argument(
        "-d",
        "--l0dir",
        help=f"Input L0 Directory (for use with -b or -r [default={l0dir_default}]",
        required=False,
        default=l0dir_default,
    )
    parser.add_argument(
        "-dl1",
        "--l1dir",
        help=f"Output L1 Directory [default={l1dir_default}]",
        required=False,
        default=l1dir_default,
    )
    parser.add_argument(
        "-dlog",
        "--logdir",
        help=f"Output for Log Files [default={logdir_default}]",
        required=False,
        default=logdir_default,
    )

    # Read in the arguments
    args = parser.parse_args()

    # Version of the data product
    args.version = 2

    # Make sure we got a good argument set
    if (args.batch == 0) & (args.recursive == 0):
        if args.l0file == "":
            statusmsg(
                "***ERROR*** You must provide --l0file, if not using -b or -r",
                screen=True,
                verbose=verbose,  # noqa: F821
            )
    elif args.l0dir == "":
        statusmsg(
            "***ERROR*** You must provide --l0dir if using -b or -r",
            screen=True,
            verbose=verbose,  # noqa: F821
        )

    # Convert APID to an integer (it is read as a string from the command line)
    try:
        if args.apid[0:2] == "0x":  # noqa: SIM108
            base = 16
        else:
            base = 10
        args.apid = int(args.apid, base)
    except TypeError:
        statusmsg(
            "Trouble parsing desired APID....exiting.",
            screen=True,
            verbose=verbose,  # noqa: F821
        )
        statusmsg(sys.exc_info(), screen=True, verbose=verbose)  # noqa: F821
        sys.exit()

    # Make sure the environmental variable reference to the data directory is set and readable
    try:
        datadir = os.environ["PSP_DATA_DIR"]
    except:  # noqa: E722
        raise KeyError(  # noqa: B904, TRY003
            "Environmental variable PSP_DATA_DIR could not be found...you must specify path to data directory using that environmental variable"  # noqa: EM101
        )

    if not os.path.exists(datadir):  # noqa: PTH110
        raise ValueError(  # noqa: TRY003
            "Directory specified in env. variable PSP_DATA_DIR does not exist"  # noqa: EM101
        )

    # Return to main routine
    return args


############################################
####
############################################
if __name__ == "__main__":
    args = setup()
    main(
        l0file=args.l0file,
        l1dir=args.l1dir,
        logdir=args.logdir,
        spacecraft=args.spacecraft,
        ptp=args.ptp,
        gzip=args.gzip,
        apidreq=args.apid,
        overwrite=args.overwrite,
        verbose=args.verbose,
    )
