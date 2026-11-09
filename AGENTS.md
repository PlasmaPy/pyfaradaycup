# AGENTS.md

Guidance for AI coding agents working in this repository.

## Project overview

`pyfaradaycup` provides tools for data pipelines and data analysis for
Faraday cups. Source code is in `src/pyfaradaycup/`, tests are in
`tests/`, and documentation is in `docs/`.

## Development

- Use [uv](https://docs.astral.sh/uv/) to manage environments.
- Use [nox](https://nox.thea.codes/) sessions defined in `noxfile.py`:
  - `nox -s tests-3.9`: run tests against Python 3.9
  - `nox -s tests-3.14`: run tests against Python 3.14
  - `nox -s typecheck`: run static type checking
  - `nox -s docs`: build the documentation
- Run both `nox -s tests-3.9` and `nox -s tests-3.14` when changing Python functionality.
- Lint files with `uvx prek --quiet`, where prek is an alternative to pre-commit.
- The minimum supported Python version is given by `requires-python` in
  `pyproject.toml`.

## Conventions

- Add tests for new functionality.
- Use numpydoc docstrings and type annotations.
