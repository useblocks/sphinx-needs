import nox
from nox_poetry import session

PYTHON_VERSIONS = ["3.6", "3.7", "3.8", "3.9"]
SPHINX_VERSIONS = ["2.2", "2.3", "2.4", "3.0", "3.2"]
TEST_DEPENDENCIES = [
    "nose",
    "sphinx_testing",
    "responses",
]
LINT_DEPENDENCIES = [
    "flake8",
    "pep8-naming",
    "flake8-isort",
    "flake8-black",
]


def is_supported(python: str, sphinx: str) -> bool:
    return not (python == "3.6" and float(sphinx) > 3.0)


def run_tests(session, sphinx):
    session.install(".")
    session.install(*TEST_DEPENDENCIES)
    session.run("pip", "install", f"sphinx=={sphinx}", silent=True)
    session.run("pip", "install", "-r", "docs/requirements.txt", silent=True)
    session.run("make", "test", external=True)


@session(python=PYTHON_VERSIONS)
@nox.parametrize("sphinx", SPHINX_VERSIONS)
def tests(session, sphinx):
    if is_supported(session.python, sphinx):
        run_tests(session, sphinx)
    else:
        session.skip("unsupported combination")


@session(python="3.9")
def lint(session):
    session.install(*LINT_DEPENDENCIES)
    session.run("make", "lint", external=True)


@session(python="3.9")
def linkcheck(session):
    session.install(".")
    session.run("pip", "install", "-r", "docs/requirements.txt", silent=True)
    session.run("make", "docs-linkcheck", external=True)
