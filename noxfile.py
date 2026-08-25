# /// script
# requires-python = ">=3.12"
# dependencies = ["nox", "nox-uv", "uv"]
# ///

"""
Nox is an automation tool used to run tests, build documentation, and perform other
checks. Nox sessions are defined in noxfile.py.

Running `nox` without arguments will run tests with the version of
Python that `nox` is installed under, skipping slow tests. To invoke a
nox session, enter the top-level directory of this repository and run
`nox -s "<session>"`, where <session> is replaced with the name of the
session. To list available sessions, run `nox -l`.

The tests can be run with the following options:

* "all": run all tests
* "skipslow": run tests, except tests decorated with `@pytest.mark.slow`
* "cov": run all tests with code coverage checks
* "lowest-direct" : run all tests with lowest versions of direct dependencies
* "lowest-direct-skipslow" : run non-slow tests with lowest versions of direct dependencies

Doctests are run only for the most recent versions of Python and
PlasmaPy dependencies, and not when code coverage checks are performed.
Some of the checks require the most recent supported version of Python
to be installed.

Nox documentation: https://nox.thea.codes
"""

import nox
import nox_uv


@nox_uv.session(uv_groups=["typecheck"])
def typecheck(session) -> None:
    """Perform static type checking with ty."""
    posargs = session.posargs if session.posargs else ["--fix"]
    session.run("ty", "check", *posargs)



if __name__ == "__main__":
    nox.main()
