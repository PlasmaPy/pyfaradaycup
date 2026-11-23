# L1 to L2

This directory contains the code that converts Parker Solar Probe SPC L1 CDF files into L2 CDF files.
In the IDL pipeline, this is step (5) of `scripts/spp_swp_spc_soc_L0L2_processing_idlscript`, which calls `spp_swp_spc_l1_to_l2_date` and then `spp_swp_spc_split_l2cdf_by_mode`.
It makes two kinds of L2 file for each day:

- a housekeeping file (APID 35F), such as `spp_swp_spc_APID35Fl2hsk_20260803_v00.cdf`, in which the raw values (DN) are converted into engineering units, and
- a science file of current spectra from APIDs 351, 353, and 354, such as `spp_swp_spc_l2_20260803_v00.cdf`, which is then split into a file for each mode, such as `spp_swp_spc_l2i_20260803_v00.cdf`.

So far, only the housekeeping files are made.

The code is a port of IDL and Python code, and keeps the names of the IDL routines and Python functions where possible.

| Python                                | Original                                                                        |
| ------------------------------------- | ------------------------------------------------------------------------------- |
| `swp_spc_l12l2_35f.py`: `convert_one` | `convert_one` in `swp_spc_l12l2_35f.py`, spawned by `spp_swp_spc_l1_to_l2_date` |
| `swp_spc_l12l2_35f.py`: `hk_dn2eng`   | `hk_dn2eng` in `swp_spc_l12l2_35f.py`                                           |

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

Like the original script, `Epoch` is copied by reading it as `datetime.datetime` values, which spacepy rounds to the nearest microsecond.
So the `CDF_TIME_TT2000` values in the L2 file can differ from the L1 file by up to 500 ns.

## To do

- [ ] **Get the production copy of `cdf_skeletons/psp_swp_spc_l2_35f_skeleton.cdf`.**
  The data, the variable types, and the global attributes of the L2 housekeeping file for 2026-08-03 match the file made in production.
  The attributes of the 25 converted variables do not.
  In the production file they are the DN attributes of the L1 variables (such as `UNITS` of `DN` and a `UINT2` `FILLVAL`), while the packaged skeleton gives them engineering-unit attributes.
  `test_convert_one_variable_attributes_match_original` is marked as an expected failure until this is resolved.
- [ ] **Copy `Epoch` without rounding it to the nearest microsecond.**
  `test_convert_one_rounds_epoch_to_microseconds` will need to be changed.
