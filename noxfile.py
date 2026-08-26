# /// script
# requires-python = ">=3.12"
# dependencies = [ "nox[uv]", "nox-uv", "uv" ]
# ///

"""
Nox is an automation tool used to run tests, build documentation, and
perform other checks. Nox sessions are defined in noxfile.py.

Running `nox` without arguments will run tests with the version of
Python that `nox` is installed under, skipping slow tests. To invoke a
nox session, enter the top-level directory of this repository and run
`nox -s "<session>"`, where <session> is replaced with the name of the
session. To list available sessions, run `nox -l`.

Doctests are run only for the most recent versions of Python and package
dependencies, and not when code coverage checks are performed. Some of
the checks require the most recent supported version of Python to be
installed.

Nox documentation: https://nox.thea.codes
"""

import os

import nox
import nox_uv

nox.options.default_venv_backend = "uv"

SUPPORTED_PYTHON_VERSIONS: tuple[str, ...] = ("3.12", "3.13", "3.14")
SUPPORTED_OPERATING_SYSTEMS: tuple[str, ...] = ("linux", "macos", "windows")

MAXPYTHON = max(SUPPORTED_PYTHON_VERSIONS)
MINPYTHON = min(SUPPORTED_PYTHON_VERSIONS)

RUNNING_ON_CI: bool = os.getenv("CI") is not None
RUNNING_ON_RTD: bool = os.getenv("READTHEDOCS") is not None


@nox_uv.session(uv_groups=["test"], python=SUPPORTED_PYTHON_VERSIONS)
def tests(session: nox.Session) -> None:
    """Run tests with pytest."""
    session.install(".")
    session.run("pytest", *session.posargs)


@nox_uv.session(uv_groups=["dev"])
def typecheck(session) -> None:
    """Perform static type checking with ty."""
    session.install(".")
    session.run("ty", "check", *session.posargs or ["--fix"])


@nox.session
def validate_lockfile(session: nox.Session) -> None:
    """
    Ensure that uv.lock is consistent with pyproject.toml.

    This check is normally performed locally when running pre-commit or
    prek. Because pre-commit.ci blocks network access, this check is
    instead done in CI via a GitHub workflow that calls this session.
    """
    if RUNNING_ON_CI:
        errmsg = (
            "The Python environments in file 'uv.lock' are inconsistent "
            "with the requirements defined in 'pyproject.toml'. "
            "After installing Nox, this problem can be fixed by running "
            "`nox -s validate_lockfile` in the top-level directory of "
            "your clone of the repository, and then pushing the updated "
            "'uv.lock' to GitHub. "
        )
    else:
        errmsg = (
            "File 'uv.lock' has been updated for consistency with the "
            "requirements defined in 'pyproject.toml'."
        )

    try:
        session.run("uv", "lock", "--no-progress")
    except nox.command.CommandFailed:
        session.error(errmsg)


@nox.session
def build(session: nox.Session) -> None:
    """
    Build the source distribution (sdist) and wheel.

    The sdist and wheel are deposited into the dist/ directory.
    """
    session.install("uv_build")
    session.run("uv", "build", *session.posargs)
    session.notify("check_build")


@nox.session
def check_build(session: nox.Session) -> None:
    """
    Validate the source distribution and wheel.

    This session requires that `nox -s build` has already been run.
    """
    session.install("twine")
    session.run("twine", "check", "dist/*", *session.posargs)


@nox_uv.session(
    python=MAXPYTHON,
    uv_only_groups=["manifest"],
    uv_no_install_project=True,
)
def manifest(session: nox.Session) -> None:
    """
    Check for missing files in MANIFEST.in.

    When run outside of CI, this check may report files that were
    locally created but not included in version control. These false
    positives can be ignored by adding file patterns and paths to
    `ignore` under `[tool.check-manifest]` in `pyproject.toml`.
    """
    # check-manifest would be suitable as a pre-commit hook, except that
    # it requires ∼6 seconds to build the package, which would triple
    # the time needed to run pre-commit.
    session.install("check-manifest")
    session.run("check-manifest", *session.posargs)


@nox_uv.session(python=MAXPYTHON, uv_only_groups=["lint"], uv_no_install_project=True)
def lint(session: nox.Session) -> None:
    """Run all pre-commit hooks defined in .pre-commit-config.yaml."""
    session.run(
        "pre-commit",
        "run",
        "--all-files",
        *session.posargs,
    )


ZIZMOR_TROUBLESHOOTING_MESSAGE = """

🪧 Run this check locally with `nox -s zizmor` to find potential
security vulnerabilities in GitHub workflows and perform safe fixes.

🧰 Perform safe and unsafe fixes with `nox -s zizmor -- --fix=all`.

📜 Audit rules: https://woodruffw.github.io/zizmor/audits

🔗 If a reported potential vulnerability does not necessitate a fix,
then either append a comment like `# zizmor: ignore[unpinned-uses]` to
the reported line (replacing `unpinned-uses` with the audit rule code),
or add the appropriate configuration settings to: .github/zizmor.yml
"""


@nox_uv.session(python=MAXPYTHON, uv_groups=["zizmor"], uv_no_install_project=True)
def zizmor(session: nox.Session) -> None:
    """
    Find common security issues in GitHub workflows.

    Because some of the zizmor audit rules require a GitHub token,
    running this check locally may produce different results than
    running it in CI.

    If no positional arguments are provided, safe fixes will be applied.
    To perform unsafe fixes, run `nox -s zizmor -- --fix=unsafe-only`.

    Configuration file: .github/zizmor.yml
    """
    if RUNNING_ON_CI:
        session.log(ZIZMOR_TROUBLESHOOTING_MESSAGE)

    options = [
        "--show-audit-urls=always",
    ]

    if not RUNNING_ON_CI and not session.posargs:
        options.append("--quiet")

    options.extend(session.posargs or ["--fix=safe"])

    session.run("zizmor", ".github", *options)


if __name__ == "__main__":
    nox.main()
