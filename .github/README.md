# GitHub workflows

<!--This file originally came from PlasmaPy -->

The [`.github/workflows`](.) directory contains [YAML] files that describe the [GitHub Actions] workflows used for during package development, including for continuous integration (CI) checks on pull requests (PRs).

## Workflows

### CI

- [`ci.yml`](./ci.yml) — perform standard continuous integration (CI) checks on PRs

### Maintenance and triage

- [`upgrade-uv-lock.yml`](./upgrade-uv-lock.yml) — update the locked Python environments used in CI

### Quality assurance

- [`installability.yml`](./installability.yml) – test package installation from official channels
- [`pyhc-actions.yml`](./pyhc-actions.yml) – check for interoperability with the Python in Heliophysics Community (PyHC) environment

### Triage

- [`stale.yml`](./stale.yml) — close issues and PRs that have been inactive for a very long time

[github actions]: https://docs.github.com/en/actions
[yaml]: https://en.wikipedia.org/wiki/YAML
