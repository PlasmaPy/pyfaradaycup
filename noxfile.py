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
import pathlib

import nox
import nox.command
import nox_uv

nox.options.default_venv_backend = "uv"

SUPPORTED_PYTHON_VERSIONS: tuple[str, ...] = (
    "3.9",
    "3.10",
    "3.11",
    "3.12",
    "3.13",
    "3.14",
)
SUPPORTED_OPERATING_SYSTEMS: tuple[str, ...] = ("linux", "macos", "windows")

MAXPYTHON = max(SUPPORTED_PYTHON_VERSIONS)
MINPYTHON = min(SUPPORTED_PYTHON_VERSIONS)

RUNNING_ON_CI: bool = os.getenv("CI") is not None
RUNNING_ON_RTD: bool = os.getenv("READTHEDOCS") is not None

DOCPYTHON = "3.14"


@nox_uv.session(uv_groups=["test"], python=SUPPORTED_PYTHON_VERSIONS)
def tests(session: nox.Session) -> None:
    """Run tests with pytest."""
    session.install(".")
    session.run("pytest", *session.posargs)


if RUNNING_ON_RTD:
    rtd_output_path = pathlib.Path(os.environ.get("READTHEDOCS_OUTPUT")) / "html"  # ty:ignore[invalid-argument-type]
    rtd_output_path.mkdir(parents=True, exist_ok=True)
    doc_build_dir = str(rtd_output_path)
else:
    doc_build_dir = "docs/_build/html"


SPHINX_BASE_COMMAND: list[str] = [
    "sphinx-build",
    "docs/source/",
    doc_build_dir,
    "--nitpicky",
    "--keep-going",
]

if not RUNNING_ON_RTD:
    SPHINX_BASE_COMMAND.extend(["--fail-on-warning"])

BUILD_HTML: tuple[str, ...] = ("--builder", "html")
CHECK_HYPERLINKS: tuple[str, ...] = ("--builder", "linkcheck")

DOC_TROUBLESHOOTING_MESSAGE = """

📘 Tips for troubleshooting common documentation build failures are in
PlasmaPy's documentation guide at:

🔗 https://docs.plasmapy.org/en/latest/contributing/doc_guide.html#troubleshooting
"""


@nox_uv.session(python=DOCPYTHON, uv_groups=["docs"])
def docs(session: nox.Session) -> None:
    """
    Build documentation with Sphinx.

    This session may require installation of pandoc and graphviz.

    Configuration file: docs/source/conf.py
    """
    if RUNNING_ON_CI:
        session.log(DOC_TROUBLESHOOTING_MESSAGE)

    # Can we use pixi or conda to install graphviz and pandoc if they
    # are not installed?

    # session.run_install("dot", "-V", external=True)
    # session.run_install("pandoc", "--version", external=True)

    session.run(*SPHINX_BASE_COMMAND, *BUILD_HTML, *session.posargs)

    landing_page = pathlib.Path(doc_build_dir) / "index.html"
    if landing_page.exists():
        session.log(f"The documentation may be previewed at {landing_page}")
    else:
        session.error(f"Documentation preview landing page not found: {landing_page}")


# The following session was copied from PlasmaPy's noxfile.py, and will
# be necessary for when we connect to Read the Docs.

# @nox_uv.session(python=DOCPYTHON, uv_groups=["docs"])
# def htmlzip(session: nox.Session) -> None:
#     """Bundle documentation build into a zip file on Read the Docs."""
#     if not RUNNING_ON_RTD:
#         session.error("This session must be run on Read the Docs.")
#
#     html_build_dir = pathlib.Path(doc_build_dir)
#     html_landing_page = (html_build_dir / "index.html").resolve()
#     READTHEDOCS_OUTPUT = html_build_dir.parent
#     if not html_landing_page.exists():
#         session.error(
#             f"No documentation build found at: {html_landing_page}\n"
#             f"It appears the documentation has not been built.",
#         )
#
#     command = [
#         "sphinx-build",
#         "--show-traceback",
#         "--doctree-dir",
#         f"{html_build_dir / '.doctrees'}",
#         "--builder",
#         "singlehtml",
#         "--define",
#         "language=en",
#         "./docs/source",  # source directory
#         f"{READTHEDOCS_OUTPUT / 'htmlzip'}",  # output directory
#     ]
#     session.run(*command)
#
#     # now build the zip file
#     READTHEDOCS_PROJECT = os.environ.get("READTHEDOCS_PROJECT")
#     READTHEDOCS_LANGUAGE = os.environ.get("READTHEDOCS_LANGUAGE")
#     READTHEDOCS_VERSION = os.environ.get("READTHEDOCS_VERSION")
#
#     # mimic RTD default naming convention
#     zip_name = f"{READTHEDOCS_PROJECT}-{READTHEDOCS_LANGUAGE}-{READTHEDOCS_VERSION}.zip"
#
#     cwd = pathlib.Path.cwd()
#     session.chdir(f"{READTHEDOCS_OUTPUT / 'htmlzip'}")
#     session.run("zip", "-r", "-m", f"{zip_name}", ".", external=True)
#     session.chdir(f"{cwd}")
#
#     session.log(f"The htmlzip was placed in: {READTHEDOCS_OUTPUT / 'htmlzip'}")


@nox_uv.session(uv_groups=["dev"])
def typecheck(session: nox.Session) -> None:
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
