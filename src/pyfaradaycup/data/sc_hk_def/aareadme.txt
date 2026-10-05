different flight software on the spacecraft means that packet definitions change over time.  Each time those packet definitions change, a new SC_HK.blk file is issued (which describes the layout of the packets), and a new SC_HK.qlf file is issued (which describes the conversion functions to get to engineering units).  The FSW version is contained in the 0x257 packet, which we must assume is never going to change its definition (or else the circular logic of: we would need to know which SC_HK.blk file to use to decommutate the 0x257 packet to figure out which FSW is in place to figure out which SC_HK.blk file to use).

The L1 file for APID 0x257 contains the times at which the FSW was incremented to a new version.  So for each other packet that ccsds_reader is trying to decommutate, it must look at the L1 0x257 text file and figure out which SC_HK file to use.

Files come from: http://www.gseos.com/DownloadSolarProbePlus.php (password protected zip files, get password from somebody at APL or Dave Curtis)

Note that some of the files in this directory have been modified from the original download:
--0x262 packet length not correct in: 05.01, 05.02, 05.03, 05.04, 05.05 (changed from 66 to 67)
