The data files in this directory were transferred from the server used to process the data pipeline.

The following files and directories came from `/psp/code/`.

- `calibration/` (only the calibration files used so far)
- `cdf_skeletons/`
- `conversion_formulas.qlf`
- `SC_HK.blk`
- `SC_HK.qlf`
- `sc_hk_def/`
- `sweap_tlm.blk`

The following files and directories came from `/psp/data/`.

- `moc_data_products/operations_sclk_kernel/spp_sclk_*.tsc`
- `moc_data_products/leap_second_kernel/naif0012.tls`
- `sc_hsk/`

> [!NOTE]
> Whitespace and permissions changes were made to several of the ASCII files.

## Text descriptions of the skeleton CDF files

Each skeleton CDF file in `cdf_skeletons/` has a text description with the
same name and a `.txt` extension, so that changes to the binary CDF files can
be reviewed with `git diff`. The tests check that each description matches
its CDF file. After changing a skeleton CDF file, regenerate the descriptions
with:

```sh
uv run python -m pyfaradaycup._cdf_description
```
