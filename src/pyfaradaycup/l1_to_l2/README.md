# L1 to L2

This directory contains the code that converts Parker Solar Probe SPC L1 CDF files into L2 CDF files.
In the IDL pipeline, this is step (5) of `scripts/spp_swp_spc_soc_L0L2_processing_idlscript`, which calls `spp_swp_spc_l1_to_l2_date` and then `spp_swp_spc_split_l2cdf_by_mode`.
It makes two kinds of L2 file for each day:

- a housekeeping file (APID 35F), such as `spp_swp_spc_APID35Fl2hsk_20260803_v00.cdf`, in which the raw values (DN) are converted into engineering units, and
- a science file of current spectra from APIDs 351, 353, and 354, such as `spp_swp_spc_l2_20260803_v00.cdf`, which is then split into a file for each mode, such as `spp_swp_spc_l2i_20260803_v00.cdf`.

The whole step is ported, and the `l1_to_l2` command line tool runs it for each date:

1. converting the housekeeping L1 file into an L2 housekeeping file, with `swp_spc_l12l2_35f.convert_one`,
1. converting the packets of each science L1 file into a current–voltage–time (IVT) series, with `spp_swp_spc_apid35x_to_ivt`,
1. merging the IVTs, with `spp_swp_spc_merge_ivt`,
1. dividing the merged IVT into spectra, with `spp_swp_spc_ivt_to_spectra`,
1. writing the spectra, flow angles, and differential charge flux density into the main L2 science file, with `spp_swp_spc_spectra_to_l2cdf`, and
1. splitting the main L2 science file into a file for each mode, with `spp_swp_spc_split_l2cdf_by_mode`.

`spp_swp_spc_l1_to_l2_date` does steps 1 to 5, like the IDL function of the same name.

For 2026-08-03, `l1_to_l2` makes exactly the same five L2 files as were made in production (`l2hsk`, `l2`, `l2i`, `l2ifs`, and `l2ical`), in every value and in the CDF metadata, apart from `Generation_date`.

The code is a port of IDL and Python code, and keeps the names of the IDL routines and Python functions where possible.

| Python                                                                                          | Original                                                                                                                                                           |
| ----------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `main.py`: the `l1_to_l2` command line tool                                                     | step 5 of `scripts/spp_swp_spc_soc_L0L2_processing_idlscript`, which calls `spp_swp_spc_l1_to_l2_date` and then `spp_swp_spc_split_l2cdf_by_mode` for each L2 file |
| `_spp_swp_spc_l1_to_l2_date.py`: `spp_swp_spc_l1_to_l2_date`                                    | `spp_swp_spc_l1_to_l2_date.pro`                                                                                                                                    |
| `swp_spc_l12l2_35f.py`: `convert_one`                                                           | `convert_one` in `swp_spc_l12l2_35f.py`, spawned by `spp_swp_spc_l1_to_l2_date`                                                                                    |
| `swp_spc_l12l2_35f.py`: `hk_dn2eng`                                                             | `hk_dn2eng` in `swp_spc_l12l2_35f.py`                                                                                                                              |
| `_spp_swp_spc_apid35x_to_ivt.py`: `spp_swp_spc_apid35x_to_ivt`, `Ivt`                           | `spp_swp_spc_apid35x_to_ivt.pro` and the structure it returns                                                                                                      |
| `_spp_swp_spc_apid35x_get_currents.py`                                                          | `spp_swp_spc_apid351_get_currents.pro`, `spp_swp_spc_apid353_get_currents.pro`, and `spp_swp_spc_apid354_get_currents.pro`                                         |
| `_spp_swp_spc_sincosgain2curr.py`                                                               | `spp_swp_spc_sincosgain2curr.pro`                                                                                                                                  |
| `_spp_swp_spc_get_gains.py`, `_spp_swp_spc_get_gainoffsets.py`                                  | `spp_swp_spc_get_gains.pro`, `spp_swp_spc_get_gainoffsets.pro`                                                                                                     |
| `_spp_swp_spc_config_and_hsk_lookup.py`                                                         | `spp_swp_spc_config_and_hsk_lookup.pro`                                                                                                                            |
| `_spp_swp_spc_flagfullscanwindows.py`                                                           | `spp_swp_spc_flagfullscanwindows.pro`, which also defines `spp_swp_spc_fullscanseqlookup` and `spp_swp_spc_fullscanseqlookup_defaultkey`                           |
| `_spp_swp_spc_parse_cycles.py`                                                                  | `spp_swp_spc_parse_cycles.pro`                                                                                                                                     |
| `_spp_swp_spc_win2volt.py`                                                                      | `spp_swp_spc_win2volt.pro`                                                                                                                                         |
| `_spp_swp_spc_hvpsthermalcorrection.py`                                                         | `spp_swp_spc_hvpsthermalcorrection.pro`                                                                                                                            |
| `_spp_swp_spc_totalharmonicdistortion.py`                                                       | `spp_swp_spc_totalharmonicdistortion.pro`                                                                                                                          |
| `_spp_swp_spc_crosstalk_correct.py`, `_spp_swp_spc_crosstalks.py`                               | `spp_swp_spc_crosstalk_correct.pro`, `spp_swp_spc_crosstalks.pro`                                                                                                  |
| `_spp_swp_spc_merge_ivt.py`: `spp_swp_spc_merge_ivt`                                            | `spp_swp_spc_merge_ivt.pro`                                                                                                                                        |
| `_spp_swp_spc_ivt_to_spectra.py`: `spp_swp_spc_ivt_to_spectra`, `Spectra`                       | `spp_swp_spc_ivt_to_spectra.pro` and the structure it returns                                                                                                      |
| `_spp_swp_spc_spectra_to_l2cdf.py`: `spp_swp_spc_spectra_to_l2cdf`                              | `spp_swp_spc_spectra_to_l2cdf.pro`                                                                                                                                 |
| `_spp_swp_spc_get_startdate.py`                                                                 | `spp_swp_spc_get_startdate.pro`                                                                                                                                    |
| `_spp_swp_spc_moments.py`                                                                       | the flow angle part of `spp_swp_spc_moments.pro`                                                                                                                   |
| `_spp_swp_spc_voltwin2kmswin.py`                                                                | `spp_swp_spc_voltwin2kmswin.pro`                                                                                                                                   |
| `_spp_swp_spc_get_effective_area.py`                                                            | the cold plasma part of `spp_swp_spc_get_effective_area.pro`                                                                                                       |
| `_spp_swp_spc_crosstalk_correction_factor.py`                                                   | `spp_swp_spc_crosstalk_correction_factor.pro`                                                                                                                      |
| `_spp_swp_spc_split_l2cdf_by_mode.py`: `spp_swp_spc_split_l2cdf_by_mode`                        | `spp_swp_spc_split_l2cdf_by_mode.pro`                                                                                                                              |
| `_calibration.py`                                                                               | finding the last calibration file with `file_search`, and reading it with `read_ascii`                                                                             |
| `pyfaradaycup.utils.idl`: `interpol`, `label_region`, `median`, `median_filter`, `value_locate` | the IDL functions `INTERPOL` (linear), `LABEL_REGION` (for 1-D arrays), `MEDIAN` (without `/EVEN`, and with a width), and `VALUE_LOCATE`                           |

> [!NOTE]
> This file was generated with Claude.

## Differences from the original code

### The command line tool and driver (`main.py` and `spp_swp_spc_l1_to_l2_date`)

- The L1 and L2 directories are options, rather than the `l1_path` and `l2_path` of the `spp_swp_spc_paths` COMMON block, and log files are written for each date into the directory given by `--logdir`.
- The housekeeping files are converted by calling a Python function, rather than by spawning `swp_spc_l12l2_35f.py`.
- A date without L1 files is skipped with a warning, and `l1_to_l2` exits with code 65, while IDL skips it silently.
- The dates are sorted and duplicates are removed.
- The `sdc_state` argument, which IDL does not use, and the `control` structure are not supported.
- Like IDL, the L2 housekeeping file is replaced on each run, while a new version of the science files is written.
  Also like IDL, the science step reads the L2 housekeeping files of each date and the day before it, so dates should be processed in order.

### Housekeeping (`swp_spc_l12l2_35f.py`)

- The conversion is a function called from Python, rather than a script that IDL spawns.
  Messages are logged with `logging` rather than written into a log file by the script.
- The formulas in `conversion_formulas.qlf` are checked to be arithmetic on `Raw` and numbers before they are evaluated.
  They are then evaluated as the same Python expressions as in the original script, so the results are the same.
- An existing L2 file is replaced only with `overwrite`.
  The L2 file is written at a temporary path and renamed when it is complete, so an existing file is left unchanged if writing the new one fails.
  The original script deletes the existing file first, and without `-o`, it stops at a `pdb` prompt when the file exists.
- An error is raised if the name of the L1 file does not contain `L1`, rather than naming the L2 file `<name>.cdf_L2cdf`.
- An error is raised if the L1 file has a variable that is not in the skeleton, rather than adding the variable to the L2 file.
- The L1 file is opened read-only.
- The batch (`-b`) and recursive (`-r`) modes, the unused `-sb` and `-eb` options, and the unused `get_hv` function are not ported, because the IDL pipeline does not use them.
- The skeleton and `conversion_formulas.qlf` are read from the package data, rather than from paths relative to the working directory.

### Current–voltage–time series (`spp_swp_spc_apid35x_to_ivt` and the routines it calls)

The IVTs keep IDL's types and arithmetic, such as `float32` currents and voltages and wrapping `uint8` products, so that the results are the same as in IDL.

- The IDL structures are dataclasses, and the IVT structure is flattened: for example, `ivt.mv_lo.dat` becomes `ivt.mv_lo`, `ivt.mv_lo.index` becomes `ivt.mv_lo_index`, and `ivt.a.gain` becomes `ivt.a_gain`.
  The variables of an L1 file are a mapping with lower-case names, since IDL tag names are case-insensitive.
- `spp_swp_spc_crosstalk_correct` returns a corrected copy of the IVT, rather than changing it in place.
- The `control` structure is not supported; its tags are keyword arguments instead.
  The L1 and L2 directories, which IDL gets from the `spp_swp_spc_paths` COMMON block, are keyword arguments too.
- Calibration files are read from `pyfaradaycup/data/calibration/`, which has the files that IDL uses by default.
- Where IDL calls `stop` or `message`, an exception is raised: for data before 2019-09-18 (`NotImplementedError`, since the full scan sequence is not known), for a temperature of 0 or none in `spp_swp_spc_win2volt`, for temperatures of the wrong shape in `spp_swp_spc_hvpsthermalcorrection`, and for data that are not from APID 351, 353, or 354.
- Quantities that IDL computes but does not use, such as guesses of the highest and lowest windows and jumps in time, are not ported.
- The table-based thermal correction in `spp_swp_spc_win2volt` (`thermal_calfile`) is not ported, since the L1 to L2 step never uses it.
- `spp_swp_spc_parse_cycles` skips the search for flux angle series if there are no zeros to search, rather than calling IDL's `histogram` with `max` less than `min`.

Behaviors of IDL that are reproduced, and could be changed later:

- In `spp_swp_spc_sincosgain2curr`, the cosine argument is overwritten by `c = sen eq 'c'`, because IDL names are case-insensitive.
  So the cosine DN of APIDs 351 and 353 are never used, and the "cosine" is 1 for sensor plate C and 0 for the others.
- A highest-numbered cycle with only one sample is never flagged as a full scan or flux angle cycle, because of how IDL checks the reverse indices of `histogram`.
- In `spp_swp_spc_parse_cycles`, a retrace at the end of the array keeps the cycle number 0, and only 10 passes are made to fill in retraces.

### Merging and spectra (`spp_swp_spc_merge_ivt` and `spp_swp_spc_ivt_to_spectra`)

- Of samples with the same time, the one from the IVT merged later is kept, because the sort is stable.
  IDL's sort is not stable, so which sample it keeps is not defined.
  The IVTs are merged in the order of APIDs 351, 353, and 354, so this keeps the APID 354 samples at times that are also in APID 353, which is what the L2 file made in production for 2026-08-03 has.
- The spectra structure is flattened like the IVT: for example, `spectra.mv_lo.dat` becomes `spectra.mv_lo`.
- Where IDL would print an error and return `-1`, or stop with a subscript error, an exception is raised: for merged IVTs with no valid times, a cycle that spans more windows than the longest cycle, no valid spectra, and a run of flux angle spectra that ends at the last spectrum.

Behaviors of IDL that are reproduced, and could be changed later:

- The highest-numbered cycle is never stored, because the rows are for cycles 0 to `max(cyclenum) - 1`.
- The samples of a cycle are assumed to be contiguous: everything from its first sample to its last is copied into its spectrum.
- When a cycle longer than 128 samples is split and no cycles come after it, the last sample is incremented again, because IDL checks `alen ge 0`, which is always true, and `where` gives `-1`, which IDL takes as the last element.
- When flagging flux angle spectra, the smallest region label that overlaps with flux angle samples is skipped, since it is usually 0, and `label_region` gives the first and last spectra the same label as spectra outside the regions.

### The L2 file (`spp_swp_spc_spectra_to_l2cdf` and the routines it calls)

- Only the flow angles of `spp_swp_spc_moments` are ported, since the rough density, speed, and temperature that it also computes are not used for L2.
  Likewise, only the cold plasma limit of `spp_swp_spc_get_effective_area` is ported, and `spp_swp_spc_get_angles` and `spp_swp_spc_ev2kms`, whose results L2 does not use, are not.
- The skeleton is `psp_l2_spc_00000000_v04.cdf` in the package data, which is the last `psp_l2_spc_000*.cdf` in `/psp/code/cdf_skeletons/`, and the calibration files are in the package data.
- The L2 directory is an argument, rather than the `l2_path` of the `spp_swp_spc_paths` COMMON block, and the `control` structure is replaced by keyword arguments.
- A given `savefile` is not replaced if it exists, and each file is written at a temporary path and renamed when it is complete.
- IDL converts `Epoch` to calendar values and back with `CDF_TT2000` as a check, which is not ported.
- When a spectrum has fewer than 128 windows, IDL subtracts arrays of different sizes when it computes `measurement_time`, which makes the array smaller.
  Here, the array keeps 128 windows, padded with fill values.
  The spectra for 2026-08-03 have 128 windows, so this does not affect them.

These behaviors of IDL are reproduced. NV5 does not document them, and they were found by reproducing the L2 file made in production for 2026-08-03:

- In `spp_swp_spc_moments`, IDL's `max` without `/NAN` skips NaNs, its `<` and `>` operators ignore a NaN operand, and `median(x, 3)` ignores NaNs and leaves the ends unchanged.
- The index of the peak from `max(..., dim=2)` is a subscript into the whole array, so the 7-element cap around the peak of each spectrum is the peak window of 7 consecutive spectra.
- `!DTOR` and float literals such as `0.035` are single precision.
- `measurement_time` is computed in `float64` from the `CDF_TIME_TT2000` times, which rounds them to multiples of 128 ns, because the fill value of `measurement_time` is `CDF_REAL8`.
  The window times for 2026-08-03 differ by multiples of 128 ns, so this does not change them.
- The currents, their uncertainties, and the differential charge flux density are `float64` until they are written, because the currents of the spectra are `float64`, while the effective area is `float32`, with correctly rounded `tan`, `sqrt`, and `atan`.
- `spp_swp_spc_crosstalk_correction_factor` uses `cb` twice and not `db` in the north–south factor.
  Its factors are always computed, but are only applied with `ew_timedep_correct` or `ns_timedep_correct`, which the L1 to L2 step does not set.

Like the original script, `Epoch` is copied by reading it as `datetime.datetime` values, which spacepy rounds to the nearest microsecond.
So the `CDF_TIME_TT2000` values in the L2 file can differ from the L1 file by up to 500 ns.

### Splitting by mode (`spp_swp_spc_split_l2cdf_by_mode`)

- `cdf_subset` and `cdf_operate_on` in `pyfaradaycup.utils.cdf_to_survey` make their skeleton with `make_temp_cdfskeleton`, which does not run the CDF command line tools `skeletontable` and `skeletoncdf`, or use the hard-coded directory `/home/mstevens/temp/`.
  Instead, it copies the file, deletes its records, and makes the changes that the round trip through a skeleton table makes, as seen in the files split in production:
  newlines in the string attributes of variables become spaces, floating-point attributes are rounded to the `FORMAT` of the variable (so the `VALIDMIN` and `VALIDMAX` of `flow_angle`, with `E7.2`, become ±1.57), and the pad value of each character variable becomes one space.
- Variables are matched by name rather than by position, and selected along their record dimension rather than along their first dimension with as many elements as there are records.
- Only the name of the file is changed to name the split files, while IDL replaces `spc_l2_` anywhere in the path.
- When there are electron flux angle spectra but no electron calibration spectra, IDL tries to make the voltages of the missing `l2ecal` file positive and lists it among the files it wrote. Here, the file is skipped.

Behaviors of IDL that are reproduced, and could be changed later:

- The `l2ecal` file is only written when there are electron flux angle spectra (mode 6), since IDL checks the number of those rather than of electron calibration spectra (mode 7).
- A main L2 file with only one spectrum is not split.

## To do

These items come from porting the code and from the code reviews of #153, #155, #156, #157, #158, and #159.
Items marked with ⚠️ would change the numerical results, so the L2 files would no longer match the ones made in production exactly.

### Behaviors inherited from IDL

- [ ] **Give the converted housekeeping variables the attributes in the skeleton.**
  Like the original script, each variable converted into engineering units gets the attributes of the L1 variable, such as a `UNITS` of `DN`, a `UINT2` `FILLVAL`, and a `VALIDMAX` in DN, because spacepy copies the attributes of the `VarCopy` that is assigned to it.
  The skeleton `psp_swp_spc_l2_35f_skeleton.cdf`, which is the same as the copy in `/psp/code/cdf_skeletons/`, has engineering-unit attributes for these variables, which are not used.
  `test_convert_one_attributes` will need to be changed.
- [ ] **Choose the full scan candidates deterministically, or as intended.** ⚠️
  `spp_swp_spc_apid35x_to_ivt` takes `cyclenum[uniq(has_dble, sort(has_dble))]`, which indexes `cyclenum` rather than `has_dble`.
  For the many samples where `has_dble` is 0, this selects the cycle number of an arbitrary sample, which depends on how IDL's unstable `sort` orders ties; the same applies to `has_fseq`.
  That cycle gets an extra count, so it can be flagged as a full scan when it is not one, or not flagged when it is.
  Here, the sort is stable, so it is the cycle of the last such sample.
  This gives the same results as IDL for 2026-08-03.
- [ ] **Average the flow angles over the windows around the peak of each spectrum, as intended.** ⚠️
  `spp_swp_spc_moments` averages the peak windows of 7 consecutive spectra instead, because of how IDL's `max(..., dim=2)` returns subscripts.
  This would change the flow angles and the differential charge flux density.
- [ ] **Check whether using `cb` twice in the north–south crosstalk correction factor is a bug, and fix it if so (#160).** ⚠️
  `spp_swp_spc_crosstalk_correction_factor` uses `ca + da + cb + cb`, rather than `db`, as in IDL.
  If this is a bug, determine the size of the error, and whether fixing it changes the results appreciably.
  The factor is only applied with `ns_timedep_correct` in `spp_swp_spc_spectra_to_l2cdf`, which the L1 to L2 step does not set (#157).
- [ ] **Write the `l2ecal` file when there are electron calibration spectra.**
  `spp_swp_spc_split_l2cdf_by_mode` checks for electron flux angle spectra instead, as IDL does.
- [ ] **Check whether the overwritten cosine in `spp_swp_spc_sincosgain2curr` is intentional, and handle it cleanly.** ⚠️
  IDL's `c = sen eq 'c'` overwrites the cosine argument, so the cosine DN of APIDs 351 and 353 are never used.
  If that is intended, remove the `c` argument; if not, use the cosine DN, which would change the currents of APIDs 351 and 353 (#155).
- [ ] **Decide whether to keep rounding `Epoch` of the L2 housekeeping files to the nearest microsecond.**
  Like the original script, `swp_spc_l12l2_35f` reads `Epoch` as `datetime.datetime` values, which spacepy rounds to the nearest microsecond, while the current–voltage–time series keep nanoseconds.
  Check whether a few hundred nanoseconds matter, compared with the time between measurements (#153, #155).
  `test_convert_one_rounds_epoch_to_microseconds` will need to be changed if `Epoch` is not rounded.
- [ ] **Check whether never storing the highest-numbered cycle in `spp_swp_spc_ivt_to_spectra` is intended, or a bug.** ⚠️
  The rows of the spectra are for cycles 0 to `max(cyclenum) - 1`, so the last cycle of each day is dropped (#156, #157).
- [ ] **Check that a main L2 file with only one spectrum should not be split** by `spp_swp_spc_split_l2cdf_by_mode` (#158).
- [ ] **Decide whether to implement the full scan sequence for data before 2019-09-18.**
  `spp_swp_spc_fullscanseqlookup` raises `NotImplementedError` for these dates, where IDL stops.
  Also document what a full scan sequence of windows is (#155).
- [ ] **Decide whether to implement the `sw_spc_doublewidth` argument of `spp_swp_spc_flagfullscanwindows`, or remove it** (#155).
- [ ] **Remove other unused arguments that were ported from IDL**, such as `it` of `spp_swp_spc_sincosgain2curr` (#155).
- [ ] **Check whether any time in the crosstalk history equals one of the hard-coded coupling transitions.**
  If so, the order of their correction factors depends on how IDL's unstable `sort` orders ties (#157).
- [ ] **Decide what `_max_dim2` in `spp_swp_spc_moments` should return for a row that is all NaN.**
  It returns column 0, as IDL does; NaN would raise an `IndexError` later, which may be better (#157).
- [ ] **Investigate whether `make_temp_cdfskeleton` needs to round floating-point attributes to the `FORMAT` of each variable.**
  This reduces precision, such as for the `VALIDMIN` and `VALIDMAX` of `flow_angle`, only to match the round trip through `skeletontable` and `skeletoncdf` in IDL (#158).
- [ ] **Evaluate replacing the IDL equivalents in `pyfaradaycup.utils.idl` with Python built-ins or functions from commonly used packages.** ⚠️
  Examples include `median`, `median_filter`, and `interpol`.
  The IDL equivalents reproduce IDL's results exactly, so replacing them could change the results (#155, #157).
- [ ] **Evaluate using `scipy.special.ellipe` instead of Hastings' approximation in `spp_swp_spc_voltwin2kmswin`.** ⚠️
  This would change the speeds slightly, and so the flow angles (#157).

### Calibration and data files

- [ ] **Decide how to handle calibration files, which are updated periodically, and investigate how to improve how they are handled and updated.**
  - Should a new version of pyfaradaycup be released whenever a calibration file is updated, or should the calibration files be kept outside the package, such as in a database (#155)?
  - How should the crosstalk files be updated, if the crosstalk changes with time (#155)?
  - Using the alphabetically last match of a pattern, as IDL does, is brittle (#156).
  - Consider how the calibration files are chosen with the keyword arguments of `spp_swp_spc_apid35x_to_ivt`, such as `hv_calfile`, `gain_calfile`, `offset_calfile`, and `crosstalk_calfile` (#155).
- [ ] **Decide how to handle `.qlf` files, such as `conversion_formulas.qlf`.**
  This file was generated from an Excel file (`SWEAP_FSW_000_CTM.xls`), which will make it hard to update.
  If it does not change, its formulas could be in Python code, rather than parsed with `ast` (#153).
- [ ] **Decide how to handle IDL save files (`.idl`), such as the effective area table and the crosstalk history.**
  They could be converted into a text format, such as JSON or YAML, or into Python code, with tests that the conversion is correct (#157).
- [ ] **Remove the need for skeleton CDF files (#154)**, including in `make_temp_cdfskeleton`, which `cdf_subset` and `cdf_operate_on` use (#158).
- [ ] **Decide whether to replace fill values with NaN**, such as `-99999` in the spectra, `-9999.` in `spp_swp_spc_hvpsthermalcorrection`, and the cycle number 0 for samples that are not in a cycle.
  Be cautious about whether this could cause problems downstream (#155, #157, #158).
- [ ] **Decide whether to port the other capabilities of `spp_swp_spc_get_effective_area`**: angles in degrees, the warm plasma (Mach number) method, and the analytic approximation (#157).
- [ ] **Consider how prefixes of file names, such as `spp_swp_spc_l2_`, should be handled, to support other missions** (#157).

### Names, documentation, and units

- [ ] **Improve the names of variables, functions, and classes once the port from IDL is closer to done** (#153, #155, #156, #157, #159).
  Examples include `Ivt` (perhaps `CurrentVoltageTimeSeries`), `Spectra`, `_read_ascii`, `spp_swp_spc_sincosgain2curr`, the fields of `SensorGains` and `SensorGainOffsets`, `HvpsThermalCorrection`, `_TRANSITIONS` (transitions of what?), `_at`, `_COLD_LINEAR`, the variables in `spp_swp_spc_ivt_to_spectra`, and `_convert` in `main.py`.
  Consider including units in names, such as for `_C` in `spp_swp_spc_voltwin2kmswin`.
- [ ] **Make the public-looking constants and classes in the private `l1_to_l2` modules private**, such as `CROSSTALK_HISTORY`, `EFFECTIVE_AREA_TABLE`, `L2_SKELETON`, `DTOR`, `FILL`, `MAX_WINDOWS`, `SPLITS`, and the dataclasses (#157).
- [ ] **Improve module docstrings and other docstrings**, such as those of `_spp_swp_spc_config_and_hsk_lookup.py`, `_spp_swp_spc_crosstalks.py`, `_spp_swp_spc_get_gainoffsets.py`, and `_spp_swp_spc_voltwin2kmswin.py`.
  Add more context to `spp_swp_spc_ivt_to_spectra`, and a docstring to `_MAX_MODE_FLAG` (#155, #156, #157).
- [ ] **Document the quantities that are used:**
  - DN as a unit (`astropy.units` has `DN`) (#153),
  - the units of the currents, such as `Current.dat` (#155),
  - what a gain stage is (#155),
  - what a coupling or decoupling transition is, and how the sensor plates A, B, C, and D relate to coupling coefficients such as `bc` (#157), and
  - the placeholder uncertainties in `spp_swp_spc_spectra_to_l2cdf`, and whether they are specific to the instrument or mission (#157).
- [ ] **Write the equations in docstrings with LaTeX, and add references to the bibliography**, such as for Hastings' approximation (#157).
- [ ] **Move the description of where the HVPS thermal model came from into a comment in the source code**, rather than the docstring of `spp_swp_spc_hvpsthermalcorrection` (#155).
- [ ] **Decide whether to use `astropy.units`**, such as `Quantity` objects for the effective area and flow angles (#157).
- [ ] **Use `datetime` or `astropy.time` rather than functions ported from IDL for dates and times**, such as in `spp_swp_spc_config_and_hsk_lookup` (#155).
- [ ] **Address the `DTZ001` findings from ruff**, where naive `datetime.datetime` objects are used as UTC times (#157).

### Code structure

- [ ] **Remove duplicated code**, such as sorting stably and keeping the last of each run of equal values, which `_uniq_sorted` in `spp_swp_spc_apid35x_to_ivt`, `spp_swp_spc_merge_ivt`, and `cdf_merge_to_daily` each do (#155).
- [ ] **Move helpers that are shared into `pyfaradaycup.utils`**, such as `_last_match` and `_read_lowercase` in `spp_swp_spc_config_and_hsk_lookup` (#155) and `_indgen_increment` in `spp_swp_spc_ivt_to_spectra` (#157).
- [ ] **Split `spp_swp_spc_spectra_to_l2cdf` into smaller functions** (#157).
- [ ] **Find a cleaner way than `_find_variable` in `cdf_to_survey` to match variable names that differ in case** (#158).
- [ ] **Make `_Split` in `spp_swp_spc_split_l2cdf_by_mode` a dataclass** (#158).
- [ ] **Represent electron and ion modes with names, such as `"electron"` and `"ion"`, rather than 1 and 0** (#157).
- [ ] **Consider using parameter objects rather than functions with many arguments** (#159).

### Tests

- [ ] **Add a testing utility to compare CDF files (#20)**, such as `assert_cdf_file_allclose`, since the comparisons of CDF files are repeated in many tests (#153, #159).
- [ ] **Evaluate comparing with the files made in production with nonzero tolerances.** ⚠️
  The tests now require the files to be exactly the same, so that any difference from IDL is an intentional decision; nonzero tolerances would make them less strict (#158).
- [ ] **Add tests with data from between different coupling and decoupling transitions** (#157).
- [ ] **Check that the tests of `hsk_only` and `sci_only` are good enough** (#159).
- [ ] **Avoid hard-coding the number of skeleton files in `tests/test_cdf_description.py`** (#157).

### Command line tool and pipeline

- [ ] **Choose the input and output directories by default**, with their `YYYY/MM/` subdirectories, while still letting users of the command line tool give them (#159).
- [ ] **Revisit the logging levels in the L1 to L2 step**, such as for the messages of `cdf_subset` and `cdf_operate_on`, and for a date without L1 files, which could be a warning only when the date was specifically requested (#158, #159).
- [ ] **Check that writing a new version of the L2 science files on each run works well with Dagster** (#157).
