# AGENTS.md

Guidance for AI coding agents working in this repository.

## Project overview

`pyfaradaycup` provides tools for data pipelines and data analysis for
Faraday cups. Source code is in `src/pyfaradaycup/`, tests are in
`tests/`, and documentation is in `docs/`.

The `pyfaradaycup.decommutator` subpackage converts binary Level 0 (L0)
files into Level 0.5 (L0.5 or L05) CDF files:

- `ccsds_reader_pipeline` reads CCSDS packets.
- `_l0_to_l05` defines `l0_to_l05`, which performs the conversion from
  L0 to L0.5, and is exported from `pyfaradaycup.decommutator`. Older
  code and filenames sometimes use "L1" to mean L0.5.
- `main` defines the `pfc_decommutator` command line tool with Click,
  which takes a required `L0FILE` argument.

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

- Test data files are in `tests/data/sci/`. Keep new test data files
  small.
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
