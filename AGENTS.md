# AGENTS.md

Guidance for AI coding agents working in this repository.

## Project overview

`pyfaradaycup` provides tools for data pipelines and data analysis for
Faraday cups. Source code is in `src/pyfaradaycup/`, tests are in
`tests/`, and documentation is in `docs/`.

The `pyfaradaycup.decommutator` subpackage converts binary Level 0 (L0)
files into Level 0.5 (L0.5 or L05) CDF files:

- `ccsds_reader` reads CCSDS packets.
- `_l0_to_l05` defines `l0_to_l05`, which performs the conversion from
  L0 to L0.5, and is exported from `pyfaradaycup.decommutator`. Older
  code and filenames sometimes use "L1" to mean L0.5.
- `main` defines the `pfc_decommutator` command line tool with Click,
  which takes a required `L0PATH` argument that is an L0 file or a
  directory of L0 files.

The `pyfaradaycup.l2_to_l3` subpackage is a port, in progress, of the
IDL code that converts SPC L2i CDF files into L3i CDF files of proton
and alpha moments and fits. Like `pyfaradaycup.l1_to_l2`, it has one
private module for each IDL routine, named after it (for example,
`_spp_swp_spc_load_l2` for `spp_swp_spc_load_l2.pro`), and its
`README.md` lists the differences from IDL and the remaining tasks.
Routines that L1 to L2 also uses are ported in `pyfaradaycup.l1_to_l2`
and imported from there.

## Development

- Use [uv](https://docs.astral.sh/uv/) to manage environments.
- Use [nox](https://nox.thea.codes/) sessions defined in `noxfile.py`:
  - `nox -s tests-3.9`: run tests against Python 3.9
  - `nox -s tests-3.14`: run tests against Python 3.14
  - `nox -s typecheck`: run static type checking
  - `nox -s docs`: build the documentation
  - `nox -s dagster_with_coverage`: run all tests, including Dagster
    tests, with code coverage (the `tests` sessions skip Dagster tests)
  - `nox -s zizmor`: find security issues in GitHub workflows
- Run both `nox -s tests-3.9` and `nox -s tests-3.14` when changing Python functionality.
- Lint files with `uvx prek --quiet`.

## Python compatibility

- Python 3.9 is supported, so do not use syntax or standard library
  features introduced after Python 3.9. Use
  `from __future__ import annotations` for newer annotation syntax.
- Python 3.9 and 3.10 use NumPy < 1.22, so do not rely on NumPy
  features introduced in 1.22 or later.

## Testing

- Test data files are in `_psp/data/sci/`. Keep new test data files
  small.
- Each skeleton CDF file in `src/pyfaradaycup/data/cdf_skeletons/` has a
  text description with the same name and a `.txt` extension, so that
  changes to the binary CDF files can be reviewed with `git diff`.
  `tests/test_cdf_description.py` checks that each description matches
  its CDF file. After adding or changing a skeleton CDF file, regenerate
  the descriptions with `uv run python -m pyfaradaycup._cdf_description`
  and commit them with the CDF file. Don't edit the descriptions by hand.
- The SPC flow angle lookup table
  (`spp_swp_spc_calfiles_spc_uvphithetalookup_20190819.idl`, 138 MB) is
  too large for the repository. Tests that need it are skipped unless the
  `PYFARADAYCUP_CALIBRATION_DIR` environment variable is set to the
  directory that contains it.
- Mark long-running tests with `@pytest.mark.slow`. Deselect them with
  `-m "not slow"`.
- Warnings are treated as errors during tests.
- Doctests in `src/pyfaradaycup/` run only in the session for the newest
  supported Python version (`nox -s tests-3.14`), so examples in
  docstrings must pass there.

## Conventions

- Add tests for new functionality.
- Use numpydoc docstrings and type annotations.
- When making suggestions, make sure that the suggestions are specific, unambiguous, and actionable.
