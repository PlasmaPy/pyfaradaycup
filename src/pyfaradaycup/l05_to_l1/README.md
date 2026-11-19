# L0.5 to L1

This directory contains the code that converts Parker Solar Probe SPC L0.5 CDF files into daily L1 CDF files.
An L1 file is a merge of the L0.5 files for one APID and one day, and the data values are not changed.
For historical reasons, the L0.5 files are named `*_L1.cdf`.

The code is a port of IDL code, and keeps the names of the IDL functions where possible.
IDL names are case-insensitive, so `CDF_merge_to_daily` becomes `cdf_merge_to_daily`.

| Python                                                                      | IDL                                                                                     |
| --------------------------------------------------------------------------- | --------------------------------------------------------------------------------------- |
| `main.py`: the `l05_to_l1` command line tool                                | step 4.2 of `scripts/spp_swp_spc_soc_L0L2_processing_idlscript`                         |
| `_spp_swp_spc_l05_to_l1.py`: `spp_swp_spc_l05_to_l1_dates`                  | `spp_swp_spc_l05_to_l1_dates.pro`                                                       |
| `_spp_swp_spc_l05_to_l1.py`: `spp_swp_spc_l05_to_l1_date`                   | `spp_swp_spc_l05_to_l1_date.pro`                                                        |
| `_spp_swp_spc_l05_to_l1.py`: `spp_swp_spc_which_apid`                       | `spp_swp_spc_which_apid.pro`                                                            |
| `_spp_swp_spc_l05_to_l1.py`: `_l05_children`                                | the `unique_dates` and `l05_children` of each `spc_rawfile` in the `sdc_state` registry |
| `cdf_to_survey.py`: `cdf_merge_to_daily`                                    | `CDF_merge_to_daily` in `idllib/CDF_to_survey.pro`                                      |
| `cdf_to_survey.py`: `_read_mycdf`, `_read_master_cdf`, `_write_data_to_cdf` | `read_myCDF`, `read_master_cdf`, and `write_data_to_cdf` in CDAWlib                     |
| `pyfaradaycup.utils.idl`: `cdf_epoch_tojuldays`, `julday`, `uniq`           | the IDL built-in functions `CDF_EPOCH_TOJULDAYS`, `JULDAY`, and `UNIQ`                  |

> [!NOTE]
> This file was generated with Claude.

## Differences from IDL

- The L0.5 files for a date are found by searching `L05/YYYY/MM/APID*/` for the month of the date and the months before and after it, because there is no `sdc_state` registry.
- Variables are matched between the skeleton and the input files by name rather than by position, and an error is raised if they differ.
- Variables are selected along their record dimension, rather than along the first dimension with as many elements as `Epoch` has records.
  These are the same for the current L1 skeletons, whose variables are all one-dimensional.
- Of a set of duplicate records, the one in the last input file is kept.
  IDL's `sort` is not stable, so which duplicate IDL keeps is not defined.
- A warning is logged for each input file that is missing, rather than depending only on whether the last file is missing.
- An L0.5 file that cannot be read, such as one that is truncated or still being written, is skipped with a warning.
- An existing L1 file is replaced only with `--overwrite`.

## To do

- [ ] **Remove duplicate records based on the exact `CDF_TIME_TT2000` values of `Epoch`.**
  To mimic IDL, records are de-duplicated by comparing their times as float64 Julian days, which differ by about 40 µs near the present.
  Records that are less than about 40 µs apart are therefore treated as duplicates, and one of them is dropped.
  Comparing the int64 values of `Epoch` instead would only drop records with exactly the same time.
  `test_cdf_merge_to_daily_merges_near_duplicates` will need to be changed.
- [ ] **Check the conversion of times to dates and Julian days against IDL.**
  The documentation of `CDF_EPOCH_TOJULDAYS` does not say how it handles leap seconds, and `CDF_merge_to_daily` calls `CDF_EPOCH, /BREAKDOWN` on `CDF_TIME_TT2000` values without `/TT2000`.
  Compare `pyfaradaycup.utils.idl.cdf_epoch_tojuldays` and `pyfaradaycup.utils.idl.julday` with IDL for times near midnight and during the leap second at the end of 2016.
