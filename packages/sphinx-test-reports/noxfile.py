import nox
from nox import session

PYTHON_VERSIONS = ["3.11", "3.12"]
SPHINX_VERSIONS = ["7.4.7", "8.1.3"]
SPHINX_NEEDS_VERSIONS = ["6.0.1", "6.3.0", "7.0.0", "8.0.0"]


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
