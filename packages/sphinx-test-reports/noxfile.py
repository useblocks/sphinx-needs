import nox
from nox import session

PYTHON_VERSIONS = ["3.6", "3.8", "3.9"]
SPHINX_VERSIONS = ["3.2", "3.5", "4.1", "4.2"]
TEST_DEPENDENCIES = [
    "nose",
    "sphinx_testing",
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
    session.run("pip", "install", "-r", "doc-requirements.txt", silent=True)
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
    # LinkCheck cn handle rate limits since Sphinx 3.4, which is needed as
    # our doc has to many links to github.
    session.run("pip", "install", "sphinx==3.5.4", silent=True)

    session.run("pip", "install", "-r", "doc-requirements.txt", silent=True)
    session.run("make", "docs-linkcheck", external=True)
