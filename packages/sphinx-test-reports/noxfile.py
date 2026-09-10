import nox
from nox import session

PYTHON_VERSIONS = ["3.11", "3.12"]
SPHINX_VERSIONS = ["7.4.7", "8.1.3"]
SPHINX_NEEDS_VERSIONS = ["6.0.1", "6.3.0", "7.0.0", "8.0.0", "8.5.0"]


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


#: The oldest pytest the plugin's tests run on, per Python: 7.0 is the plugin's
#: own floor (the pytest extra), and 7.3.2 the first pytest that runs on
#: Python 3.12 at all.
PLUGIN_PYTEST_FLOORS = [("3.11", "7.0.1"), ("3.12", "7.3.2")]


@session
@nox.parametrize("python,pytest_version", PLUGIN_PYTEST_FLOORS)
def plugin_floor(session, pytest_version):
    """The pytest plugin's tests on the oldest pytest it supports."""
    session.install(".[test]", f"pytest=={pytest_version}")
    session.run("pytest", "tests/test_pytest_plugin.py")


@session(python="3.12")
def linkcheck(session):
    session.install(".[docs]")
    with session.chdir("docs"):
        session.run("make", "linkcheck", external=True)
