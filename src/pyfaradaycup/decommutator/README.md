# Decommutator

This directory contains the code that converts Parker Solar Probe SPC L0 files into L1 CDF files.

- `main.py` defines the `pfc_decommutator` command line tool.
- `swp_spc_l02l1.py` defines `main`, which does the conversion for one L0 file.
- `ccsds_reader_pipeline.py` reads the CCSDS packets from an L0 file.

> [!NOTE]
> This file was generated with Claude.

## Changes needed for use in a Dagster pipeline

`pfc_decommutator` can be run from Dagster as it is, but a step that fails can be reported as a success, and retries and parallel runs are not safe.
The changes below are listed with the most important first.

### Report every failure as a failure

Dagster decides whether a step succeeded from the exit code of a subprocess, or from whether a Python call raised an exception.

- **Replace the bare `sys.exit()` calls in `swp_spc_l02l1.main` with exceptions.**
  A bare `sys.exit()` gives an exit code of 0.
  It is currently used when a leap second or SCLK kernel cannot be found or loaded, and when an L1 CDF file already exists and `--overwrite` was not given.
- **Stop skipping APIDs that fail.**
  When a skeleton file is missing, or when writing a CDF fails, `main` logs a message and moves to the next APID, and the run still ends with "Script complete".
  Collect these failures and raise an exception at the end if there were any.
- **Remove the bare `except:` blocks**, or narrow them to the exceptions that are expected.
  Several of them hide the original error.
- **Raise exceptions with messages.**
  For example, an unreadable L0 file currently gives a `RuntimeError` with no message.

### Return what was written

`swp_spc_l02l1.main` returns `None`.
It should return the paths of the L1 CDF files it wrote, and the path of the log file, so that a Dagster asset can check its outputs and attach them as metadata without searching the output directory.
It would also be useful to return the kernels and skeleton files that were used.

### Make retries and parallel runs safe

- **Write each CDF to a temporary file, and rename it when it is complete.**
  CDF files are currently written in place, so a run that stops part way leaves an incomplete CDF file behind.
- **Decide what a retry should do.**
  Without `--overwrite`, a retry stops at the first L1 file that already exists.
  A Dagster step should either always overwrite, or skip files that are already complete.
- **Give each run its own log file name.**
  The log file name contains the time to the nearest second, and the file is opened for writing.
  Two runs that start in the same second with the same `--logdir` write to the same file.
  Including the name of the L0 file in the log file name would fix this.
- **Remove the global state.**
  The log file is the module-level global `logfile`, which `statusmsg` writes to.
  SPICE kernels are loaded with `spiceypy.furnsh` on every call and are never unloaded.
  This is safe when each step runs in its own process, but not when `main` is called more than once in the same process.
  Pass the log file as an argument, and unload the kernels when the conversion finishes.

### Make it callable from Python

Calling the conversion as a function is better suited to Dagster than starting a subprocess, since Dagster can then capture exceptions, log messages, and return values.

- **Use the `logging` module instead of `statusmsg` and `print`.**
  Dagster can then show the messages with their levels in its own logs.
  The warnings that `pfc_decommutator` prints for options that have no effect should use `logging` too.
- **Keep `pfc_decommutator` as a thin wrapper.**
  A click command ends the Python process when it finishes, so it should not be called from an asset or op.
  All checks that matter should be in the function that the asset calls.

### Make the inputs configurable

- **Remove the `PSP_DATA_DIR` check, or use the value.**
  The environment variable must be set to an existing directory, but its value is never read.
- **Allow the kernel and skeleton directories to be chosen.**
  The leap second kernel, SCLK kernel, CDF skeletons, and `sweap_tlm.blk` are read from the `data` directory of the installed package, and the newest kernel is chosen from the file name.
  A new SCLK kernel therefore needs a new installation of the package, and Dagster cannot treat the kernel as an input.
  Add arguments for these paths, with the packaged files as the default.
- **Remove the hard-coded path used by `--spacecraft`.**
  `read_file_sc` reads `/psp/data/sc_hsk/L1/APID257_combined.txt`, so this option only works on a computer that has that file.
- **Make `--l0file`, `--l1dir`, and `--logdir` required options in click.**
  Leaving out `--l1dir` or `--logdir` currently gives a `ValueError` from `main` instead of a usage message.

### Remove options that do nothing

- `--batch`, `--recursive`, and `--l0dir` do not convert any additional files, and `--stcorrect` raises an error.
  Dagster should start one step for each L0 file, for example with partitions, so batch processing is not needed in this tool.
- `--ptp` only has an effect together with `--spacecraft`.
