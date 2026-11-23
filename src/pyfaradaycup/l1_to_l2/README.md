# L1 to L2

This directory contains the code that converts Parker Solar Probe SPC L1 CDF files into L2 CDF files.
In the IDL pipeline, this is step (5) of `scripts/spp_swp_spc_soc_L0L2_processing_idlscript`, which calls `spp_swp_spc_l1_to_l2_date` and then `spp_swp_spc_split_l2cdf_by_mode`.
It makes two kinds of L2 file for each day:

- a housekeeping file (APID 35F), such as `spp_swp_spc_APID35Fl2hsk_20260803_v00.cdf`, in which the raw values (DN) are converted into engineering units, and
- a science file of current spectra from APIDs 351, 353, and 354, such as `spp_swp_spc_l2_20260803_v00.cdf`, which is then split into a file for each mode, such as `spp_swp_spc_l2i_20260803_v00.cdf`.

So far, the housekeeping files are made, and the first steps of making the science files are ported:

1. converting the packets of each science L1 file into a current–voltage–time (IVT) series, with `spp_swp_spc_apid35x_to_ivt`,
1. merging the IVTs, with `spp_swp_spc_merge_ivt`, and
1. dividing the merged IVT into spectra, with `spp_swp_spc_ivt_to_spectra`.

For 2026-08-03, the spectra are exactly the same as in the L2 file made in production: the times, voltages, and currents of every window, and the flags that make up `MODE_FLAG`.

The code is a port of IDL and Python code, and keeps the names of the IDL routines and Python functions where possible.

| Python                                                                    | Original                                                                                                                                 |
| ------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------- |
| `swp_spc_l12l2_35f.py`: `convert_one`                                     | `convert_one` in `swp_spc_l12l2_35f.py`, spawned by `spp_swp_spc_l1_to_l2_date`                                                          |
| `swp_spc_l12l2_35f.py`: `hk_dn2eng`                                       | `hk_dn2eng` in `swp_spc_l12l2_35f.py`                                                                                                    |
| `_spp_swp_spc_apid35x_to_ivt.py`: `spp_swp_spc_apid35x_to_ivt`, `Ivt`     | `spp_swp_spc_apid35x_to_ivt.pro` and the structure it returns                                                                            |
| `_spp_swp_spc_apid35x_get_currents.py`                                    | `spp_swp_spc_apid351_get_currents.pro`, `spp_swp_spc_apid353_get_currents.pro`, and `spp_swp_spc_apid354_get_currents.pro`               |
| `_spp_swp_spc_sincosgain2curr.py`                                         | `spp_swp_spc_sincosgain2curr.pro`                                                                                                        |
| `_spp_swp_spc_get_gains.py`, `_spp_swp_spc_get_gainoffsets.py`            | `spp_swp_spc_get_gains.pro`, `spp_swp_spc_get_gainoffsets.pro`                                                                           |
| `_spp_swp_spc_config_and_hsk_lookup.py`                                   | `spp_swp_spc_config_and_hsk_lookup.pro`                                                                                                  |
| `_spp_swp_spc_flagfullscanwindows.py`                                     | `spp_swp_spc_flagfullscanwindows.pro`, which also defines `spp_swp_spc_fullscanseqlookup` and `spp_swp_spc_fullscanseqlookup_defaultkey` |
| `_spp_swp_spc_parse_cycles.py`                                            | `spp_swp_spc_parse_cycles.pro`                                                                                                           |
| `_spp_swp_spc_win2volt.py`                                                | `spp_swp_spc_win2volt.pro`                                                                                                               |
| `_spp_swp_spc_hvpsthermalcorrection.py`                                   | `spp_swp_spc_hvpsthermalcorrection.pro`                                                                                                  |
| `_spp_swp_spc_totalharmonicdistortion.py`                                 | `spp_swp_spc_totalharmonicdistortion.pro`                                                                                                |
| `_spp_swp_spc_crosstalk_correct.py`, `_spp_swp_spc_crosstalks.py`         | `spp_swp_spc_crosstalk_correct.pro`, `spp_swp_spc_crosstalks.pro`                                                                        |
| `_spp_swp_spc_merge_ivt.py`: `spp_swp_spc_merge_ivt`                      | `spp_swp_spc_merge_ivt.pro`                                                                                                              |
| `_spp_swp_spc_ivt_to_spectra.py`: `spp_swp_spc_ivt_to_spectra`, `Spectra` | `spp_swp_spc_ivt_to_spectra.pro` and the structure it returns                                                                            |
| `_calibration.py`                                                         | finding the last calibration file with `file_search`, and reading it with `read_ascii`                                                   |
| `pyfaradaycup.utils.idl`: `label_region`, `median`, `value_locate`        | the IDL built-in functions `LABEL_REGION` (for 1-D arrays), `MEDIAN` (without `/EVEN`), and `VALUE_LOCATE`                               |

> [!NOTE]
> This file was generated with Claude.

## Differences from the original code

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

Like the original script, `Epoch` is copied by reading it as `datetime.datetime` values, which spacepy rounds to the nearest microsecond.
So the `CDF_TIME_TT2000` values in the L2 file can differ from the L1 file by up to 500 ns.

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
- [ ] **Use the cosine DN in `spp_swp_spc_sincosgain2curr`.**
  This would change the currents of APIDs 351 and 353.
- [ ] **Copy `Epoch` without rounding it to the nearest microsecond.**
  `test_convert_one_rounds_epoch_to_microseconds` will need to be changed.
