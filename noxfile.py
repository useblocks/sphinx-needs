import nox
from nox_poetry import session


PYTHON_VERSIONS = ["3.6", "3.7", "3.8"]
SPHINX_VERSIONS = ["2.2", "2.3", "2.4", "3.0", "3.2"]
TEST_DEPENDENCIES = [
    "nose",
    "sphinx_testing",
    "sphinxcontrib.plantuml",
    "matplotlib",
    "responses",
    "sphinx_copybutton",
]


def is_supported(python: str, sphinx: str) -> bool:
    return not (python == "3.6" and float(sphinx) > 3.0)


def run_tests(session, sphinx):
    session.install(".")
    session.install(*TEST_DEPENDENCIES)
    session.run("pip", "install", f"sphinx=={sphinx}", silent=True)
    session.run("nosetests", "-w", "tests")


@session(python=PYTHON_VERSIONS)
@nox.parametrize("sphinx", SPHINX_VERSIONS)
def tests(session, sphinx):
    if is_supported(session.python, sphinx):
        run_tests(session, sphinx)
    else:
        session.skip("unsupported combination")
