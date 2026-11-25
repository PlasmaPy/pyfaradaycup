# L2 to L3

This directory contains the code that converts Parker Solar Probe SPC L2i CDF files into L3i CDF files.
The L3i files, such as `spp_swp_spc_l3i_20260803_v00.cdf`, have the proton and alpha particle moments and fits for each spectrum in the L2i file of the same day, such as `spp_swp_spc_l2i_20260803_v00.cdf`, along with the ephemeris of the spacecraft and data quality flags.

In IDL, `spp_swp_spc_process_l3i_multithread_daterange` starts one IDL process for each date, which calls `spp_swp_spc_l2i_to_l3_date`.
That reads the L2i file with `spp_swp_spc_load_l2`, and `spp_swp_spc_write_l3_spci_cdf` analyzes each spectrum with `spp_swp_spc_get1rdf` and writes the L3i file.
The L3 step is commented out of `scripts/spp_swp_spc_soc_L0L2_processing_idlscript`; the release session scripts (`scripts/psp_swp_spc_vv_rel2*_session_script*`) run it by hand with `ew_timedep_correct=1`.

The port is in progress.
So far, it reads the L2i file, the names of the data quality flags, and the flow angle lookup table.

The code is a port of IDL code, and keeps the names of the IDL routines where possible.
Routines that the L1 to L2 step also uses, such as `spp_swp_spc_get_effective_area` and `spp_swp_spc_crosstalk_correction_factor`, are ported in `pyfaradaycup.l1_to_l2` and imported from there.

| Python                                                                         | Original                                                                 |
| ------------------------------------------------------------------------------ | ------------------------------------------------------------------------ |
| `_spp_swp_spc_load_l2.py`: `spp_swp_spc_load_l2`, `L2i`, `L2Variable`          | `spp_swp_spc_load_l2.pro`, and the structure from `read_myCDF`           |
| `_spp_swp_spc_l3i_flagnames.py`: `spp_swp_spc_l3i_flagnames`                   | `spp_swp_spc_l3i_flagnames.pro`                                          |
| `_spp_swp_spc_get_angle_table.py`: `spp_swp_spc_get_angle_table`, `AngleTable` | `spp_swp_spc_get_angle_table.pro`, and the `table` structure it restores |

These routines remain to be ported:

| Original                                      | Purpose                                                                   |
| --------------------------------------------- | ------------------------------------------------------------------------- |
| `spp_swp_spc_process_l3i_multithread.pro`     | runs `spp_swp_spc_l2i_to_l3_date` for each date, in parallel              |
| `spp_swp_spc_l2i_to_l3_date.pro`              | makes the L3i file for each date                                          |
| `spp_swp_spc_write_l3_spci_cdf.pro`           | analyzes every spectrum of a day and writes the L3i file (also `crosspn`) |
| `spp_swp_spc_get1rdf.pro`                     | moments, fits, flow angles, and flags of one spectrum                     |
| `spp_swp_spc_splineinvert.pro`                | currents → flux function P(V)                                             |
| `spp_swp_spc_zmoments.pro`                    | moments of a distribution                                                 |
| `spp_swp_spc_pmax_response.pro`               | forward model of the response to a Maxwellian, fitted with `CURVEFIT`     |
| `spp_swp_spc_get_angles.pro`                  | flow angles from the lookup table                                         |
| `spp_swp_spc_get_effective_area.pro`          | warm (Mach number) and `/approx` branches, in `pyfaradaycup.l1_to_l2`     |
| `spp_swp_spc_ev2kms.pro`                      | voltage → speed, in `pyfaradaycup.l1_to_l2`                               |
| `spp_swp_spc_get_l3ephempars.pro`             | spacecraft ephemeris, with a cache file                                   |
| `spp_swp_spc_load_ephemeris_standardset.pro`  | SPICE lookups (also `get_lte_kernels`)                                    |
| IDL's `CURVEFIT`, `TRISOL`, and `INTERPOLATE` | in `pyfaradaycup.utils.idl`                                               |

> [!NOTE]
> This file was generated with Claude.

## Inputs

- The L2i files, such as `spp_swp_spc_l2i_20260803_v00.cdf`.
- The L3 skeleton `psp_l3_spci_00000000_v08.cdf`, in the package data, which is the last `psp_l3_spci_000*.cdf` in `/psp/code/cdf_skeletons/`.
  Its variables and attributes are the same as in the L3i file made in production for 2026-08-03, apart from `Logical_file_id`, `Generation_date`, and the values of `DQF_flagnames` and `array32_index`, which are written with each file.
- The flow angle lookup table `spp_swp_spc_calfiles_spc_uvphithetalookup_20190819.idl`, the default in IDL.
  It is 138 MB, so it is not in the package data.
  Give its path with `table_file`, or set the `PYFARADAYCUP_CALIBRATION_DIR` environment variable to the directory that contains it.
  Tests that need it are skipped otherwise.
- The effective area table and the crosstalk coupling history, which are in the package data for the L1 to L2 step.
- SPICE kernels, which are not in the package data (see the to-do list).

## Differences from the original code

### Reading the L2i file (`spp_swp_spc_load_l2`)

- The L2 directory is an argument, rather than the `l2_path` of the `spp_swp_spc_paths` COMMON block or of the `control` structure.
- Only a single date is supported, rather than a date, an array of dates, or file names.
  The L3 step only uses a single date.
- `None` is returned when there is no L2i file, rather than `-1`.
- Only the values (`.dat`) and fill values (`.fillval`) of the variables are kept, with lower-case names, since these are all that the L3 step uses.
  The values are the raw values, so times are `CDF_TIME_TT2000` integers, as in IDL.
- The `nan` keyword, which the L3 step does not use, is not ported.

Like IDL, the last `l2dir/YYYY/MM/*_l2i_*YYYYMMDD*.cdf` file is read, which is the highest version.
The pattern does not match the `l2ifa`, `l2ifs`, or `l2ical` files, but it would match a release file such as `psp_swp_spc_l2i_20260803_v02.cdf`, which sorts before `spp_swp_spc_l2i_20260803_v00.cdf`.

### Names of the data quality flags (`spp_swp_spc_l3i_flagnames`)

- More than 32 names raise `ValueError`, where IDL stops with a subscript error.
- The `version` keyword, which IDL ignores, is not ported.

### Flow angle lookup table (`spp_swp_spc_get_angle_table`)

- The arrays are transposed from the order that `scipy.io.readsav` gives, so that they have IDL's order of dimensions, and `u[i, j, m]` here is `table.u[i, j, m]` in IDL.
  `phi` varies along the first dimension and `theta` along the second; `u` and `v` have a third dimension for the Mach number.
- The default file is in the directory given by `PYFARADAYCUP_CALIBRATION_DIR`, rather than `code_path + 'calibration/'`.

## Possible bugs in the original code

These are found by reading the IDL code, and are described in more detail in `CLAUDE.md` of the snapshot of the IDL code.
They will be checked as the routines are ported.

- `spp_swp_spc_l2i_to_l3_date` calls `create_struc`, which does not exist (`create_struct` is meant), when it is given both `control` and other keywords.
- `spp_swp_spc_crosstalk_correction_factor` uses `cb` twice and not `db` in the north–south factor, which the L3 step applies only with `ns_timedep_correct` (#160).
- In `spp_swp_spc_get1rdf`, `dtheta` uses `kp` instead of `kt`, and `sigma_theta` uses `dphi` instead of `dtheta`.
- In `spp_swp_spc_write_l3_spci_cdf`, `vp_moment_SC_deltahigh` and `vp_moment_SC_deltalow` look swapped compared with those of the density and thermal speed, and `vp_moment_RTN_deltalow` is computed from `deltahigh`.
- The densities from the moments are normalized with an area of 137.260 mm², and those from the fits with 131.78035 mm².
- `spp_swp_spc_get_l3ephempars` reuses a cache file when the sum of the differences of the times is 0, rather than when every time is the same.
- The time is converted for SPICE with `et = 1e-9 * TT2000`, which treats TT as TDB (an error of up to about 1.7 ms).
- In `get_lte_kernels`, the swap for reversed limits sets `jdmax = jdmin`.
- The output directories are made with `mkdir`, without `-p`.

## To do

Items marked with ⚠️ would change the numerical results, so the L3i files would no longer match the ones made in production exactly.

- [ ] Port the remaining routines (see the table above), and the `l2_to_l3` command line tool.
- [ ] Find the SPICE kernels for 2026-08-03 (`de430.bsp`, `psp_dyn_2018_135_100.tf`, an SPK for the spacecraft that covers 2026-08, and the attitude kernels for 2026-08-02 to 2026-08-04), or the ephemeris cache file `spp_swp_spc_l3ephem_20260803.idl`, to test the ephemeris and RTN velocities.
- [ ] Find IDL's `curvefit.pro`, which is not in the snapshot of the IDL code, to port `CURVEFIT` exactly.
- [ ] Check which flow angle lookup table and effective area table were used in production.
  The `Calibrations_used` global attribute of the skeleton lists `uvphithetalookup_20200417` and `effectiveAreaTable_v1`, while IDL uses `uvphithetalookup_20190819` and `effectiveAreaTable_v0` by default.
- [ ] Use `astropy.constants` instead of the hard-coded constants, such as `13842`, `9.58e7`, `1.04396848e-8`, and `15.348852`. ⚠️
- [ ] Decide whether to process dates in parallel, as IDL does.
- [ ] Decide whether to port `spp_swp_spc_saltandpepper_filter`, which is only used with the `saltandpepper_filter` tag of `control`.
- [ ] Decide whether to port the release steps that follow L3: `spp_swp_spc_cleanup_low_versions`, `psp_swp_spc_validate_date`, and `spp_swp_spc_L3_ephem_patch`, which redoes the ephemeris of existing L3 files.
