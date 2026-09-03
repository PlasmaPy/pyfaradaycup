"""
#  $URL: file:///psp/psp_swp_spc_code_repository/trunk/ccsds_reader_pipeline.py $
#  $LastChangedRevision: 103 $
#  $LastChangedDate: 2020-08-13 08:42:52 -0400 (Thu, 13 Aug 2020) $
#  $LastChangedBy: acase $
"""

import datetime
import os
import re
import struct
import sys
import time

import dateutil.parser
import numpy as np

# import Tkinter
# import tkFileDialog


#########################################
def read_stdin(ptp=False, verbose=False):
    """Parse binary stream on stdin"""


#########################################
def file2bytestr(path="", verbose=False, gzip=False):
    try:
        if gzip:
            import gzip

            with gzip.open(path, "rb") as f:
                bytestr = f.read()
            return bytestr
        with open(path, "rb") as f:
            bytestr = f.read()
        return bytestr

    except:
        print("***ERROR*** [ccsds_reader_pipeline] Could not read in file...exiting")
        print(sys.exc_info())
        import pdb

        pdb.set_trace()
        sys.exit()


#########################################
def choose_file(path="", ptp=False, verbose=False):
    # make sure file exists
    try:
        open(path).close()
    except:
        print("***ERROR*** File can not be read...will give option to choose file")
        path = ""

    # pop up a dialog to choose a file if path==''
    # path = 'C:\\Users\\comra_000\\SWEAP\\SPC\\FEU\\Testing\\20150228_UCB_SPC_FEU_LVPS_PTP_data\\PTP_data.dat'
    if path == "":
        print("***ERROR*** Must define a file path")
        # root = Tkinter.Tk()
        # root.withdraw()
        # path = tkFileDialog.askopenfilename()

    return path


#########################################
def wrapper_status(path="", verbose=False, gzip=False, spconly=False):

    # get a filename if not specified
    path = choose_file(path)

    # convert file to a hex string
    bytestr = file2bytestr(path, gzip=gzip)

    # define the apids that are ok
    wrapper_apids = range(0x348, 0x351)
    if spconly:
        ok_apids = [0x351, 0x352, 0x353, 0x354, 0x35E, 0x35F]
    else:
        ok_apids = range(0x351, 0x3A0, 1)

    # create a dictionary that we can store data in
    data = {
        "wrap_met": [],
        "wrap_apid": [],
        "data_met": [],
        "data_apid": [],
        "wrap_seq": [],
        "data_seq": [],
    }

    # Define a pattern that will match a SWEM wrapper header and an SPC instrument header
    pattern = struct.pack("1B", 0x0B)
    pattern += b"["
    for wrap_ap in wrapper_apids:  # allowable wrapper apids
        pattern += struct.pack("1B", wrap_ap & 255)
    pattern += b"]"
    pattern += b"." * 10
    pattern += struct.pack("1B", 0x0B)
    pattern += b"["
    for inst_ap in ok_apids:  # allowable SPC instrument apids
        pattern += struct.pack("1B", inst_ap & 255)
    pattern += b"]"

    # Find all occurrences of the beginning of a packet
    pkt_inds = np.array(
        [(m.start(0), m.end(0)) for m in re.finditer(pattern, bytestr, re.DOTALL)]
    )
    try:
        pkt_starts = pkt_inds[:, 0]
    except:
        return data

    npackets = len(pkt_starts)

    # Loop through each packet beginning and decommutate it
    for i_pointer, pointer in enumerate(pkt_starts):
        wrap_cchead = parse_ccsds_head(bytestr[pointer : pointer + 10])
        data_cchead = parse_ccsds_head(bytestr[pointer + 12 : pointer + 22])
        data["wrap_met"].append(wrap_cchead["CCSDS_MET"])
        data["wrap_apid"].append(wrap_cchead["CCSDS_ApID"])
        data["wrap_seq"].append(wrap_cchead["CCSDS_SeqCnt"])
        data["data_met"].append(data_cchead["CCSDS_MET"])
        data["data_apid"].append(data_cchead["CCSDS_ApID"])
        data["data_seq"].append(data_cchead["CCSDS_SeqCnt"])

    return data


#########################################
def read_file(path="", verbose=False, gzip=False):
    """Read a CCSDS File and return data structure"""
    # get a filename if not specified
    path = choose_file(path)

    # convert file to a hex string
    bytestr = file2bytestr(path, gzip=gzip)

    # define the apids that are ok
    wrapper_apids = range(0x348, 0x351)
    ok_apids = [0x351, 0x352, 0x353, 0x354, 0x35E, 0x35F]

    # create a dictionary that we can store data in
    data = {}

    # store the format for each apid in a dictionary
    apidformat = {}
    for apid in ok_apids:
        apidformat[apid] = get_layout(apid, verbose=verbose)
        if apidformat[apid]:
            data[apid] = {}
            for name in apidformat[apid].names:
                data[apid][name] = []

    # create a list of two dictionaries that can keep track of
    # the count of good packets found and bad packets found
    goodcnt = {}
    for thisap in data:
        goodcnt[thisap] = 0
    errcnt = {}
    pktcnt = [goodcnt, errcnt]

    # Define a pattern that will match a SWEM wrapper header and an SPC instrument header
    # 0x348 through 0x350 is a SWEM wrapper apid, 0x351,0x352,0x353,0x354,0x35e,0x35f are SPC APIDs
    pattern = struct.pack("1B", 0x0B)
    pattern += b"["
    for wrap_ap in wrapper_apids:  # allowable wrapper apids
        pattern += struct.pack("1B", wrap_ap & 255)
    pattern += b"]"
    pattern += b"." * 10
    pattern += struct.pack("1B", 0x0B)
    pattern += b"["
    for inst_ap in ok_apids:  # allowable SPC instrument apids
        pattern += struct.pack("1B", inst_ap & 255)
    pattern += b"]"

    # Find all occurrences of the beginning of a packet
    pkt_inds = np.array(
        [(m.start(0), m.end(0)) for m in re.finditer(pattern, bytestr, re.DOTALL)]
    )
    try:
        pkt_starts = pkt_inds[:, 0]
    except:
        return data

    npackets = len(pkt_starts)

    # Some variables so we can display progress
    updatetime = 0.0
    starttime = time.time()

    # Loop through each packet beginning and decommutate it
    for i_pointer, pointer in enumerate(pkt_starts):
        foo = read_bytestr(
            bytestr, pointer + 12, data, apidformat, pktcnt, verbose=verbose
        )

        # Update status
        nowtime = time.time()
        if (nowtime - updatetime) > 0.5:
            sys.stdout.write(
                "\b" * 40
                + f"{(np.double(i_pointer)) / npackets * 100.0:5.1f}% Complete.  ET={nowtime - starttime:6.2f} sec."
            )
            updatetime = nowtime

    # write out a summary of how things went
    nowtime = time.time()
    sys.stdout.write(
        "\b" * 40 + f"{100.0:5.1f}% Complete.  ET={nowtime - starttime:6.2f} sec.\n\n"
    )
    sys.stdout.write("Packet Summary\n")
    for thisapid in pktcnt[0].keys():
        sys.stdout.write(
            f"\tAPID {hex(thisapid)}: found {pktcnt[0][thisapid]:7.0f} packets\n"
        )
    sys.stdout.write("\n")

    return data


#########################################
def read_file_sc(path="", verbose=False, ptp=False, gzip=False):
    """Read a CCSDS File and return data structure"""
    # get a filename if not specified
    path = choose_file(path)

    # convert file to a hex string
    bytestr = file2bytestr(path, gzip=gzip)

    # We'll need to find which apid dictionary to use,
    # based on which version of FSW was running
    # Those versions (and respective dates) are listed in the L1 APID257 file
    # That file is created via psp_sc_hsk_257_l052l1.py
    # Corresponding SC_HK files that we will read in are in ./sc_hk_def/
    with open("/psp/data/sc_hsk/L1/APID257_combined.txt") as f:
        lines = f.readlines()
    vers_dt = np.array([dateutil.parser.isoparse(line.split(",")[0]) for line in lines])
    versions = np.array([line.split(",")[1].strip() for line in lines])

    # And we have to hardwire how to relate a particular version number to a SC_HK.blk filename
    # This will have to be manually updated every time they update FSW
    sc_hk_filenames = {
        "05.01.01": "SPP.SC.HK.05.01.01_G01.blk",
        "05.04.00": "SPP.SC.HK.05.04.00_G04.blk",
        "05.05.01": "SPP.SC.HK.05.05.01_G02.blk",
        "05.06.00": "SPP.SC.HK.05.06.02_G06.blk",
    }

    # get the first packet header in the file and see what the date/time is
    # and thus which SC_HK.blk file to use
    # we'll assume the first bytes in the file are a header
    try:
        if ptp:
            cchead = parse_ccsds_head(bytestr[17:])
        else:
            cchead = parse_ccsds_head(bytestr)
        if (
            (cchead["CCSDS_Version"] != 0)
            | (cchead["CCSDS_PacketType"] != 0)
            | (cchead["CCSDS_SecHdrFlag"] != 1)
        ):
            raise ValueError("CCSDS header values not as expected")
        file_dt = datetime.datetime(2010, 1, 1) + datetime.timedelta(
            seconds=cchead["CCSDS_MET"]
        )
        try:
            good_time = np.where(vers_dt < file_dt)[0][-1]
        except IndexError:
            good_time = 0
        sc_hk_filename = sc_hk_filenames[versions[good_time]]
    except:
        print(sys.exc_info())
        print("Could not find which SC_HK file to use based on packet header")
        print("Attempting to find correct date based on filename/path")
        try:
            match = re.search(
                os.path.sep
                + "20[1-5][0-9]"
                + os.path.sep
                + "[0-9][0-9][0-9]"
                + os.path.sep,
                path,
            ).span()
            file_dt = datetime.datetime(
                int(path[match[0] + 1 : match[0] + 5]), 1, 1
            ) + datetime.timedelta(days=int(path[match[0] + 6 : match[0] + 9]) - 1)
            try:
                good_time = np.where(vers_dt < file_dt)[0][-1]
            except IndexError:
                good_time = 0
            sc_hk_filename = sc_hk_filenames[versions[good_time]]
        except:
            print(
                "***WARNING*** Could not find date based on filename...using most recent"
            )
            sc_hk_filename = sc_hk_filenames[-1]

    # define the apids that are ok
    ok_apids = [0x081, 0x262, 0x07B, 0x254, 0x257, 0x256]
    lengths = {}  # store the length of each apid that we'll find in the sc_hk file

    # create a dictionary that we can store data in
    data = {}
    # store the format for each apid in a dictionary
    apidformat = {}
    for apid in ok_apids:
        apidformat[apid], lengths[apid] = get_layout_sc(
            apid, verbose=verbose, filename=os.path.join("sc_hk_def", sc_hk_filename)
        )
        if apidformat[apid]:
            data[apid] = {}
            for name in apidformat[apid].names:
                data[apid][name] = []

    # since sc_hk file lists total length, but we search for length in apid header (total length - 7)
    # Also, packets need to be multiples of 2 bytes, so actual packet length will be rounded up to nearest multiple of 2
    for key, val in lengths.items():
        lengths[key] = 2 * np.ceil((val) / 2.0).astype(int) - 7

    # create a list of two dictionaries that can keep track of
    # the count of good packets found and bad packets found
    goodcnt = {}
    for thisap in data:
        goodcnt[thisap] = 0
    errcnt = {}
    pktcnt = [goodcnt, errcnt]

    if ptp:
        pattern = struct.pack(
            "3B", 0x03, 0x00, 0xBB
        )  # 2,3,4,5,6th bytes (start from zero) of PTP header
        pattern += b"." * 12
        pattern += b"("
        for inst_ap in ok_apids:  # allowable SPC instrument apids
            pattern += struct.pack(
                "2B", (2048 + inst_ap & 0xFF00) >> 8, 2048 + inst_ap & 0x00FF
            )
            pattern += b"|"
        pattern = pattern[:-1]  # get rid of that last "|"
        pattern += b")"

        offset_bytes = 15  # since we searched before 2 bytes into the PTP header, we need to offset the rest of the PTP header
    else:
        pattern = b"("
        for inst_ap in ok_apids:  # allowable SPC instrument apids
            pattern += struct.pack(
                "2B", (2048 + inst_ap & 0xFF00) >> 8, 2048 + inst_ap & 0x00FF
            )
            pattern += b".."
            if inst_ap == 0x256:
                # because the length shown in SPP.SC.HK.XX.YY.ZZ_GWW.blk doesn't correspond to packet length
                # we just hard-code the length
                # As of 2020/06/08 there were only two different possible sizes of 0x256 packets 0x098d and 0x0a91
                pattern += b"(\x09\x8d|\x0a\x91)"
            else:
                pattern += struct.pack(
                    "2B", (lengths[inst_ap] & 0xFF00) >> 8, lengths[inst_ap] & 0x00FF
                )
            pattern += b"|"
        pattern = pattern[:-1]  # get rid of that last "|"
        pattern += b")"

        offset_bytes = (
            0  # we searched for beginning of CCSDS packets, so no offset necessary
        )
    # import pdb; pdb.set_trace()

    # Find all occurrences of the beginning of a packet
    pkt_inds = np.array(
        [(m.start(0), m.end(0)) for m in re.finditer(pattern, bytestr, re.DOTALL)]
    )
    try:
        pkt_starts = pkt_inds[:, 0]
    except:
        return data
    npackets = len(pkt_starts)

    # Some variables so we can display progress
    updatetime = 0.0
    starttime = time.time()

    # Loop through each packet beginning and decommutate it
    for i_pointer, pointer in enumerate(pkt_starts):
        foo = read_bytestr(
            bytestr, pointer + offset_bytes, data, apidformat, pktcnt, verbose=verbose
        )

        # Update status
        nowtime = time.time()
        if (nowtime - updatetime) > 0.5:
            sys.stdout.write(
                "\b" * 40
                + f"{(np.double(i_pointer)) / npackets * 100.0:5.1f}% Complete.  ET={nowtime - starttime:6.2f} sec."
            )
            updatetime = nowtime

    # write out a summary of how things went
    nowtime = time.time()
    sys.stdout.write(
        "\b" * 40 + f"{100.0:5.1f}% Complete.  ET={nowtime - starttime:6.2f} sec.\n\n"
    )
    sys.stdout.write("Packet Summary\n")
    for thisapid in pktcnt[0].keys():
        sys.stdout.write(
            f"\tAPID {hex(thisapid)}: found {pktcnt[0][thisapid]:7.0f} packets\n"
        )
    sys.stdout.write("\n")

    return data


#########################################
def read_bytestr(bytestr, pointer, data, apidformat, pktcnt, verbose=False):
    """Take a hex string and find packets"""
    # Parse the CCSDS header
    try:
        ccsds_head = parse_ccsds_head(bytestr[pointer : pointer + 10])
    except ValueError:
        if verbose:
            print("Full CCSDS Header Not Present")
        return ()
    apid = ccsds_head["CCSDS_ApID"]
    pkt_len = ccsds_head["CCSDS_PacketLen"]

    # Verify that the CCSDS header is valid
    if ccsds_head["CCSDS_Version"] != 0:
        if verbose:
            print("CCSDS Version is invalid")
        return ()

    if ccsds_head["CCSDS_PacketType"] != 0:
        if verbose:
            print("CCSDS Type is invalid")
        return ()

    if ccsds_head["CCSDS_SecHdrFlag"] != 1:
        if verbose:
            print("CCSDS Secondary Header flag is invalid")
        return ()

    # Make sure the full packet is here
    if pointer + pkt_len + 7 > len(bytestr):
        if verbose:
            print("Full CCSDS packet not available at end of bytestr")
        return ()

    # This packet only (no PTP header and no wrapper header (if they existed))
    thispkt = bytestr[pointer : pointer + pkt_len + 7]

    # make sure we know how to decom this packet
    if apid in apidformat.keys():
        # count this as a good packet
        pktcnt[0][apid] += 1

        # parse the packet and add decommed values to data variable
        parse_pkt(
            thispkt, data, apidformat, apid, ccsds_head
        )  # could send this off to a parallel task?  Might try that if too slow this way

    elif apid in pktcnt[1].keys():
        pktcnt[1][apid] += 1
    else:
        pktcnt[1][apid] = 1

    return ()

    # we shouldn't make it here
    import pdb

    pdb.set_trace()


#########################################
def parse_ccsds_head(bytestr, verbose=False):
    bytearr = struct.unpack("B" * len(bytestr), bytestr)

    exp_length = 10
    if len(bytearr) < exp_length:
        raise ValueError("CCSDS header is not as long as expected")

    head = {}
    head["CCSDS_Version"] = bytearr[0] >> 5
    head["CCSDS_PacketType"] = (bytearr[0] & 0b00010000) >> 4
    head["CCSDS_SecHdrFlag"] = (bytearr[0] & 0b00001000) >> 3
    head["CCSDS_ApID"] = 256 * (bytearr[0] & 0b00000111) + bytearr[1]
    head["CCSDS_GroupFlags"] = bytearr[2] >> 6
    head["CCSDS_SeqCnt"] = 256 * (bytearr[2] & 0b00111111) + bytearr[3]
    head["CCSDS_PacketLen"] = 256 * bytearr[4] + bytearr[5]
    head["CCSDS_MET"] = (
        2**24 * bytearr[6] + 2**16 * bytearr[7] + 2**8 * bytearr[8] + bytearr[9]
    )

    # return the dictionary
    return head


#########################################
def parse_pkt(bytestr, data, apidformat, apid, ccsds_head, verbose=False):
    """Parse one CCSDS packet"""
    # The format for this APIDs packet list
    form = apidformat[apid]
    thisdat = data[apid]

    # Convert to a bit string
    bytearr = struct.unpack("B" * len(bytestr), bytestr)
    str_bin = "".join([bin(i)[2:].zfill(8) for i in bytearr])

    # For SWEAP packets, we just have each mnemonic listed and each bit length
    # So we have to step through them in order
    # Take care of the variables in sw_data (the repeating bit of the packet) separately
    pointer = 0
    if hasattr(form, "sw_data_vars"):
        sw_data_vars_len = len(form.sw_data_vars)
    else:
        sw_data_vars_len = 0

    """
	#This *might* be a faster way to parse values?
	#This will work for the non sw_data_vars variables, 
	#but I haven't written anything for the sw_data_vars yet
	
	for i_bit, bit in enumerate(form.bits[0:len(form.bits)-sw_data_vars_len]):
	
		bytes = bytearr[form.bytestart[i_bit]:form.byteend[i_bit]+1] #the bytes that contain the value for this mnemonic
		valint = sum([bytes[len(bytes)-1-i]<<i*8 for i in range(len(bytes))]) #those bytes combined into single integer
		mask = 2**form.bits[i_bit]-1 << (7-form.bitend[i_bit])
		thisval = (valint & mask) >> (7-form.bitend[i_bit])

		#store in our data variable
		thisname = form.names[i_bit]
		thisdat[thisname].append(thisval)
	"""

    # SC packets are defined in a different format than SWEAP packets
    # Each mnemonic has a start byte, start bit, and length
    # Loop through each name
    if apid in [0x081, 0x262, 0x07B, 0x254, 0x257, 0x256]:
        for i_name, thisname in enumerate(form.names):
            startbit = 8 * form.startbyte[i_name] + (7 - form.startbit[i_name])
            endbit = startbit + form.bits[i_name]
            thisbin = str_bin[startbit:endbit]
            try:
                thisval = int(thisbin, 2)
            except:
                # print(sys.exc_info())
                thisval = -999
            thisdat[thisname].append(thisval)
        return

    # If the full packet isn't here, then don't bother parsing
    if len(bytearr) * 8.0 < sum(form.bits):
        print(f"short packet: {hex(apid)}")
        return

    for i_bit, bit in enumerate(form.bits[0 : len(form.bits) - sw_data_vars_len]):
        thisbin = str_bin[pointer : pointer + bit]
        try:
            thisval = int(thisbin, 2)
        except:
            import pdb

            pdb.set_trace()
            thisval = -999
        thisname = form.names[i_bit]

        # store in our data variable
        thisdat[thisname].append(thisval)

        # advance the pointer
        pointer += bit

    # Read in the portion of the packet that repeats over and over (the data)
    if hasattr(form, "sw_data_vars"):
        # A dictionary to store the lists for this packet
        # Which will get appended to the lists from previous packets
        newdat = {}
        for key in form.sw_data_vars:
            newdat[key] = []

        n_vars = len(form.sw_data_vars)
        total_sw_data_length = np.sum(form.bits[-n_vars:])

        while (pointer + total_sw_data_length) <= len(str_bin):
            for i in range(n_vars):
                thisbin = str_bin[pointer : pointer + form.bits[-n_vars + i]]
                try:
                    thisval = int(thisbin, 2)
                except ValueError:
                    import pdb

                    pdb.set_trace()
                    thisval = -999

                thisname = form.sw_data_vars[i]
                newdat[thisname].append(thisval)
                pointer += form.bits[-n_vars + i]

        for key in form.sw_data_vars:
            thisdat[key].append(newdat[key])


#########################################
class apid_obj:
    def __init__(self):
        self.names = []
        self.bits = []
        self.bytestart = []
        self.bitstart = []
        self.byteend = []
        self.bitend = []
        self.data = {}
        self.startbyte = []
        self.startbit = []


#########################################
def get_layout(apid, verbose=False):
    try:
        file = open("sweap_tlm.blk")
    except:
        if verbose:
            print(
                "***INFO*** No local 'sweap_tlm.blk' found...using the one near ccsds_reader_pipeline.py"
            )
        try:
            thisdir = os.path.realpath(__file__)
            thisdir = "\\".join(thisdir.split("\\")[0:-1])
            file = open(thisdir + "\\sweap_tlm.blk")
        except:
            print(sys.exc_info())
            import pdb

            pdb.set_trace()
    lines = file.readlines()
    for i, line in enumerate(lines):
        if line[0:8] == f"APID_{hex(apid)[2:].zfill(3)}".upper():
            if verbose:
                print(f"APID {hex(apid)[2:]} Format Found".upper())
            thisapid = apid_obj()
            thisapid.apid = apid
            line = ""  # so that the while loop will start out ok
            while line[0:4] != "APID":
                i += 1
                line = lines[i]
                try:
                    if line.strip()[0] not in ["(", "{", "}", ")"]:
                        pieces = re.split(",|;", line.strip())
                        thisapid.names.append(pieces[0].strip())
                        thisapid.bits.append(int(pieces[3].strip()))
                        thisapid.data[pieces[0].strip()] = []
                        if hasattr(thisapid, "sw_data_vars"):
                            thisapid.sw_data_vars.append(thisapid.names[-1])
                    elif (line.strip()[0:9] == "( SW_DATA") | (
                        line.strip()[0:12] == "( SW_SPC_SCI"
                    ):
                        thisapid.sw_data_vars = []
                except IndexError:
                    break
                except:
                    print(sys.exc_info())
                    import pdb

                    pdb.set_trace()

            start = np.array(
                [0] + [sum(thisapid.bits[0:i]) for i in range(1, len(thisapid.bits))]
            )
            length = np.array(thisapid.bits) - 1
            thisapid.bytestart = np.floor(start / 8.0).astype(int)
            thisapid.bitstart = start - 8 * thisapid.bytestart.astype(int)
            endbits = start + length
            thisapid.byteend = np.floor(endbits / 8.0).astype(int)
            thisapid.bitend = endbits - 8 * thisapid.byteend.astype(int)

            return thisapid

    # if we didn't find that APID
    print(
        f"***ERROR*** [ccsds_reader_pipeline] Did not find APID {hex(apid)[2:]}".upper()
    )
    return None


#########################################
def get_layout_sc(apid, verbose=False, filename=""):
    try:
        file = open(filename)
        print(f"using sc_hk file: {filename}")
    except:
        print("could not open SC HK BLK file")
        print(sys.exc_info())
        import pdb

        pdb.set_trace()

    lines = file.readlines()
    for i, line in enumerate(lines):
        if line[0:11] == f"SC_HK_0x{hex(apid)[2:].zfill(3).upper()}":
            if verbose:
                print(f"APID {hex(apid)[2:]} Format Found".upper())
            thisapid = apid_obj()
            thisapid.apid = apid

            line = ""
            while line[0:4] != "SC_H":
                i += 1
                line = lines[i].strip()
                if line[0:8] == "( Block[":
                    length = int(line.split("[")[1].split("]")[0])
                try:
                    if line[0] not in ["(", "{", "}", ")"]:
                        pieces = re.split(",|;", line)
                        # for some reason packet definitions with many bytes look like "mnemonic[32], x, y, z (for 32 byte long packet), rather than having the bit length actually show 8*32 bits
                        if pieces[0][-1] == "]":
                            bitlength = 8 * int(pieces[0].split("[")[1].split("]")[0])
                            pieces[3] = str(bitlength)
                            pieces[0] = pieces[0].split("[")[0]
                        thisapid.names.append(pieces[0].strip())
                        thisapid.startbyte.append(int(pieces[1].strip()))
                        thisapid.startbit.append(int(pieces[2].strip()))
                        thisapid.bits.append(int(pieces[3].strip()))
                except IndexError:
                    break
                except:
                    print(sys.exc_info())
                    import pdb

                    pdb.set_trace()
            return (thisapid, length)
    # if we didn't find that APID
    print(
        f"***ERROR*** [ccsds_reader_pipeline] Did not find APID {hex(apid)[2:]}".upper()
    )
    return None


if __name__ == "__main__":
    read_file(ptp=False, verbose=True)
