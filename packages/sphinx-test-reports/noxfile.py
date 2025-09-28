import nox
from nox import session

PYTHON_VERSIONS = ["3.10", "3.12"]
SPHINX_VERSIONS = ["5.0", "7.2.5", "8.1.3"]
SPHINX_NEEDS_VERSIONS = ["2.1", "4.2", "5.1"]


def run_tests(session, sphinx, sphinx_needs):
    session.install(".[test]")
    session.run("pip", "install", f"sphinx=={sphinx}", silent=True)
    session.run("pip", "install", f"sphinx_needs=={sphinx_needs}", silent=True)
    session.run("make", "test", external=True)


@session(python=PYTHON_VERSIONS)
@nox.parametrize("sphinx_needs", SPHINX_NEEDS_VERSIONS)
@nox.parametrize("sphinx", SPHINX_VERSIONS)
def tests(session, sphinx_needs, sphinx):
    run_tests(session, sphinx, sphinx_needs)


@session(python="3.12")
def linkcheck(session):
    session.install(".[docs]")
    with session.chdir("docs"):
        session.run("make", "linkcheck", external=True)
