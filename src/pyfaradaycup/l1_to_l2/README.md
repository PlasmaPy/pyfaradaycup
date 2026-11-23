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

- `cdf_subset` and `cdf_operate_on` in `pyfaradaycup.l05_to_l1.cdf_to_survey` make their skeleton with `make_temp_cdfskeleton`, which does not run the CDF command line tools `skeletontable` and `skeletoncdf`, or use the hard-coded directory `/home/mstevens/temp/`.
  Instead, it copies the file, deletes its records, and makes the changes that the round trip through a skeleton table makes, as seen in the files split in production:
  newlines in the string attributes of variables become spaces, floating-point attributes are rounded to the `FORMAT` of the variable (so the `VALIDMIN` and `VALIDMAX` of `flow_angle`, with `E7.2`, become ±1.57), and the pad value of each character variable becomes one space.
- Variables are matched by name rather than by position, and selected along their record dimension rather than along their first dimension with as many elements as there are records.
- Only the name of the file is changed to name the split files, while IDL replaces `spc_l2_` anywhere in the path.
- When there are electron flux angle spectra but no electron calibration spectra, IDL tries to make the voltages of the missing `l2ecal` file positive and lists it among the files it wrote. Here, the file is skipped.

Behaviors of IDL that are reproduced, and could be changed later:

- The `l2ecal` file is only written when there are electron flux angle spectra (mode 6), since IDL checks the number of those rather than of electron calibration spectra (mode 7).
- A main L2 file with only one spectrum is not split.

## To do

- [ ] **Give the converted housekeeping variables the attributes in the skeleton.**
  Like the original script, each variable converted into engineering units gets the attributes of the L1 variable, such as a `UNITS` of `DN`, a `UINT2` `FILLVAL`, and a `VALIDMAX` in DN, because spacepy copies the attributes of the `VarCopy` that is assigned to it.
  The skeleton `psp_swp_spc_l2_35f_skeleton.cdf`, which is the same as the copy in `/psp/code/cdf_skeletons/`, has engineering-unit attributes for these variables, which are not used.
  `test_convert_one_attributes` will need to be changed.
- [ ] **Choose the full scan candidates deterministically, or as intended.**
  `spp_swp_spc_apid35x_to_ivt` takes `cyclenum[uniq(has_dble, sort(has_dble))]`, which indexes `cyclenum` rather than `has_dble`.
  For the many samples where `has_dble` is 0, this selects the cycle number of an arbitrary sample, which depends on how IDL's unstable `sort` orders ties; the same applies to `has_fseq`.
  That cycle gets an extra count, so it can be flagged as a full scan when it is not one, or not flagged when it is.
  Here, the sort is stable, so it is the cycle of the last such sample.
  This gives the same results as IDL for 2026-08-03.
- [ ] **Average the flow angles over the windows around the peak of each spectrum, as intended.**
  `spp_swp_spc_moments` averages the peak windows of 7 consecutive spectra instead, because of how IDL's `max(..., dim=2)` returns subscripts.
  This would change the flow angles and the differential charge flux density.
- [ ] **Use `db` in the north–south crosstalk correction factor.**
- [ ] **Write the `l2ecal` file when there are electron calibration spectra.**
  `spp_swp_spc_split_l2cdf_by_mode` checks for electron flux angle spectra instead, as IDL does.
- [ ] **Use the cosine DN in `spp_swp_spc_sincosgain2curr`.**
  This would change the currents of APIDs 351 and 353.
- [ ] **Copy `Epoch` without rounding it to the nearest microsecond.**
  `test_convert_one_rounds_epoch_to_microseconds` will need to be changed.
