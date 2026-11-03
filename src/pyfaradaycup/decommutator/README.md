# Decommutator

This directory contains the code that converts Parker Solar Probe SPC L0 files into L0.5 CDF files.
For historical reasons, the output files are named `*_L1.cdf`.

- `main.py` defines the `pfc_decommutator` command line tool.
- `swp_spc_l0_to_l05.py` defines `main`, which does the conversion for one L0 file.
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

### Test more thoroughly

- **Add a test that converts a spacecraft L0 file with `--spacecraft`.**
  The only end-to-end test converts an instrument L0 file, so `_read_file_sc`, `_get_layout_sc`, and the code that writes the spacecraft housekeeping CDFs are never run.
  Add a spacecraft L0 file to `tests/data`, along with the expected L0.5 CDF files, and compare them as the existing test does.
  Include a file for which the flight software version cannot be found from the packet header, so that the fallback to the file path, and then to the newest definition file, is also tested.
- **Compare the attributes of the CDF files as well as the data.**
  The end-to-end test compares the CDF files with `xarray.testing.assert_allclose`, which ignores the global and variable attributes.
  A change to the attributes, such as a wrong unit or a missing `FILLVAL`, would not cause the test to fail.
  Also compare the `attrs` of each dataset and each variable, for example with `xarray.testing.assert_identical`.

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
