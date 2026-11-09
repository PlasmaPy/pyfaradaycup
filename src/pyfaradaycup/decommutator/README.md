# Decommutator

This directory contains the code that converts Parker Solar Probe SPC L0 files into L0.5 CDF files.
For historical reasons, the output files are named `*_L1.cdf`.

- `main.py` defines the `pfc_decommutator` command line tool.
- `l0_to_l05.py` defines `main`, which does the conversion for one L0 file.
- `ccsds_reader_pipeline.py` reads the CCSDS packets from an L0 file.

> [!NOTE]
> This file was generated with Claude.

## Changes needed for use in a Dagster pipeline

`pfc_decommutator` can be run from Dagster as it is, but retries and parallel runs are not safe.
The changes below are listed with the most important first.

### Report every failure as a failure

Dagster decides whether a step succeeded from the exit code of a subprocess, or from whether a Python call raised an exception.

- **Decide whether `main` should raise when an APID fails.**
  When a skeleton file is missing, when a CDF cannot be created or filled, or when the APID is 0x07B, `main` logs an error, records it in the `failures` attribute of the `DecommutationResult` it returns, and moves to the next APID.
  `pfc_decommutator` then exits with a code of 1, but a Dagster asset that calls `main` must check `result.succeeded` itself.
  A CDF that could not be filled is left behind without being closed.

### Make retries and parallel runs safe

- **Write each CDF to a temporary file, and rename it when it is complete.**
  CDF files are currently written in place, so a run that stops part way leaves an incomplete CDF file behind.
- **Decide what a retry should do.**
  Without `--overwrite`, a retry stops at the first L0.5 CDF file that already exists.
  A Dagster step should either always overwrite, or skip files that are already complete.
- **Remove the global state.**
  SPICE kernels are loaded with `spiceypy.furnsh` on every call and are never unloaded.
  This is safe when each step runs in its own process, but not when `main` is called more than once in the same process.
  Unload the kernels when the conversion finishes.

### Make it callable from Python

Calling the conversion as a function is better suited to Dagster than starting a subprocess, since Dagster can then capture exceptions, log messages, and return values.

- **Keep `pfc_decommutator` as a thin wrapper.**
  A click command ends the Python process when it finishes, so it should not be called from an asset or op.
  All checks that matter should be in the function that the asset calls.

### Make the inputs configurable

- **Allow the kernel, skeleton, and housekeeping definition files to be chosen.**
  The leap second kernel, SCLK kernel, CDF skeletons, and `sweap_tlm.blk` are read from the `data` directory of the installed package, and the newest kernel is chosen from the file name.
  With `--spacecraft`, the list of flight software versions (`sc_hsk/L1/APID257_combined.txt`) and the spacecraft housekeeping definitions (`sc_hk_def/`) are read from there too.
  These are copies of files on the server used to process the data, so they go out of date when the server's files are updated.
  A new SCLK kernel or flight software version therefore needs a new installation of the package, and Dagster cannot treat these files as inputs.
  Add arguments for these paths, with the packaged files as the default.

### Record provenance in the CDF files

- **Write the provenance into the global attributes of each CDF.**
  `main` logs the software versions, host, SHA-256 checksum of the L0 file, and the kernels and skeletons used, and returns them in a `DecommutationResult`, but none of this is written to the CDF files.
  A CDF file that is separated from its log file therefore cannot be traced back to how it was made.
  Add global attributes such as `Parents` (the L0 file and its checksum), `Software_version`, and `Generation_date`, following the ISTP guidelines.
  This changes the contents of the CDF files, so the expected CDF files in `tests/data` would need to be regenerated.

### Improve the log messages

- **Log the header length message from `_parse_ccsds_head` at the `DEBUG` level.**
  When a CCSDS header is longer than expected, `_parse_ccsds_head` issues a `UserWarning` with `warnings.warn`.
  If this is normal, as the comment above it suggests, then it should be a `DEBUG` message from the logger, so that it does not appear on the console.
  If it is not normal, then it should stay a warning.
- **Tag each message with the L0 file and APID being processed.**
  Messages from the CDF writers do not all say which L0 file or APID they are about.
  When the log files from many Dagster steps are combined, this makes messages hard to attribute.
  A `logging.Filter` or `logging.LoggerAdapter` could add the L0 file and APID to every record, and the file format could include them.
- **Add an option to write the log file as JSON Lines.**
  A log file with one JSON object per line, with fields such as the time, level, logger, message, L0 file, and APID, could be searched and loaded without parsing text.
  This could be a `log_format` argument to `configure_logging`, along with an option for `pfc_decommutator`.
- **Allow logging from more than one process.**
  If L0 files are ever converted in parallel within one Python program, for example with `concurrent.futures.ProcessPoolExecutor`, several processes writing to the same log file can interleave their lines.
  `logging.handlers.QueueHandler` and `logging.handlers.QueueListener` let each worker send its records to one process that writes them.
  This setup belongs in `pyfaradaycup/_logging.py`, since handlers may only be created there.
  It is not needed while Dagster runs each step in its own process with its own log file.

### Remove options that do nothing

- `--batch`, `--recursive`, and `--l0dir` do not convert any additional files, and `--stcorrect` raises an error.
  Dagster should start one step for each L0 file, for example with partitions, so batch processing is not needed in this tool.
- `--ptp` only has an effect together with `--spacecraft`.

## Tests to add

The end-to-end test in `tests/decommutator/test_decommutator.py` converts one instrument L0 file (`tests/data/sci/sweap/raw/ssr/2026/215/0523462910_4_EA`) and compares the L0.5 CDF files with the expected ones, with no tolerance.
This protects the usual path for SPC instrument packets, but about a third of the code in this directory is never run by the tests.
Most of it is in the spacecraft housekeeping path, in the handling of unusual packets, and in the handling of errors.
The tests below are listed with the most important first.

### Spacecraft housekeeping files

None of the code used with `--spacecraft` is tested, so a change could alter the CDF files for APIDs 0x081, 0x1DE, 0x254, 0x256, 0x257, and 0x262 without any test failing.

- **Add a test that converts a spacecraft L0 file.**
  Add a spacecraft L0 file to `tests/data`, along with the expected L0.5 CDF files, and compare them as the existing test does.
  If `--ptp` is needed, also add a PTP file.
- **Test how the flight software version is chosen.**
  `_read_file_sc` chooses a spacecraft housekeeping definition file from the MET in the first packet header, by comparing it with the dates in `sc_hsk/L1/APID257_combined.txt`.
  If that fails, it uses the date in the file path, and then the newest definition file.
  Test files with times just before and just after a change of flight software version, a file whose first bytes are not a valid header, and a file with no `<year>/<day of year>` in its path.
- **Test `_get_layout_sc` with small definition files.**
  Include a field written as `mnemonic[N]`, which is treated as `N` bytes long.
  If the section for an APID has no `( Block[...]` line, `length` is never assigned, so the function raises `UnboundLocalError`.
  If an APID is not in the file, `_get_layout_sc` returns `None`, and `_read_file_sc` then raises `TypeError` when it unpacks the result.
  A test should decide what each of these cases should do.

### Conversion to time

- **Test `_secsubsec2scet` against known pairs of spacecraft clock and ephemeris times.**
  Test both SWEAP packets (subseconds in units of 1/65536 s) and spacecraft packets (`spacecraft=True`, subseconds in units of 1/256 s).
  The spacecraft case is not run by any test.
  The subseconds are converted to the 1/50000 s ticks of the PSP clock kernel with `int`, which truncates rather than rounds, so a time can be early by up to 20 µs.
  A test would show whether this is intended.

### Expanding packets into measurements

`_cdf351_353_354` and `_cdf352` turn each packet into one row per measurement and calculate the time of each measurement.
A mistake in these functions gives wrong times rather than an error, so it is worth testing them on their own.
Both accept `nocdf=True`, which returns the expanded data without writing a CDF file, so they can be tested with small dictionaries of made-up packet data.

- **Test integration and settling times that are not a power of 2.**
  `_cdf351_353_354` then uses the power-on defaults (IT=6, ST=2), warns once, and skips a packet whose times differ from both the packet before and the packet after it.
  Include such a packet at the start and at the end of the data, where the comparison with its neighbors raises `IndexError`.
- **Test AllGain (APID 0x351) packets that do not start a NYS.**
  When `SW_SPC_PKTNUM` is not 0, the times continue from the end of the previous packet, with an extra step if the retrace was at the end of that packet.
  Packets with a nonzero `SW_SPC_PKTNUM` at the start of a file are dropped.
- **Test packets with fewer measurements than expected**, which happens when the DAC tables are not loaded.
- **Test that `_cdf352` skips corrupt packets.**
  A packet with an unknown collection should be skipped and counted, without shifting the times or data of the packets around it.

### Failures that are logged but not reported

- **Decide what should happen when `_cdf35e_35f` cannot calculate `Epoch`.**
  If none of the expected MET fields are present, `_cdf35e_35f` logs an error and returns without writing any data.
  `main` then reports the CDF file as written, and the APID is not included in `failures`.
- **Decide what should happen when the CDF skeleton has a variable that the data does not.**
  `_cdf351_353_354` raises `RuntimeError`, but `_cdf352` only logs a warning.
  A test for each function would show whether this difference is intended.

### Errors in `main`

Most of these can be tested with `monkeypatch`, without new data files.

- **An L0.5 CDF file that already exists without `overwrite`** should raise `FileExistsError` and leave the file unchanged.
- **A leap second or SCLK kernel that is missing or cannot be loaded** should raise `RuntimeError`.
- **A CDF file that cannot be created or filled** should be recorded in `failures`, and the remaining APIDs should still be converted.
- **APID 0x07B, an APID with no packets, and an APID other than the one requested with `apidreq`** should each be skipped.

### Reading files

- **Test that a gzip-compressed L0 file (`--gzip`) gives the same CDF files** as the uncompressed file.
- **Test that a compressed PTP file name** (such as `*.ptp.gz`) gives CDF file names without `.ptp` in them.
  `main` removes a second extension only when the first one leaves a name ending in `ptp`.
- **Test that `_get_layout` raises `RuntimeError`** for a line in `sweap_tlm.blk` that cannot be parsed, and returns `None` for an APID that is not in the file.
- **Test that `_get_newest_kernel` raises `RuntimeError`** when no kernel files match, and when both or neither of `tls` and `sclk` are `True`.

### Command line options

- **Test the usage errors from `pfc_decommutator`**: an `--apid` that is not hexadecimal, `-b` or `-r` without `--l0dir`, and `--stcorrect`.

### Comparing CDF files

- **Compare the attributes of the CDF files as well as the data.**
  The end-to-end test compares the CDF files with `xarray.testing.assert_allclose`, which ignores the global and variable attributes.
  A change to the attributes, such as a wrong unit or a missing `FILLVAL`, would not cause the test to fail.
  Also compare the `attrs` of each dataset and each variable, for example with `xarray.testing.assert_identical`.

### Code that may not be needed

- `_wrapper_status` in `ccsds_reader_pipeline.py` is not called anywhere.
  Either remove it, or test it if it is meant to be used.
- `_cdf351_353_354` raises `UnboundLocalError` for an APID other than 0x351, 0x353, or 0x354.
  `main` never calls it with another APID, so a test is not needed unless it becomes public.
