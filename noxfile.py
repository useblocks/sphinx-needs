import nox
from nox_poetry import session

# The versions here must be in sync with the github-workflows.
# Or at least support all version from there.
# This list can contain more versions as used by the github workflows to support
# custom local tests

PYTHON_VERSIONS = ["3.8", "3.9", "3.10", "3.11"]
SPHINX_VERSIONS = ["5.0", "6.0", "7.0"]


@session(python=PYTHON_VERSIONS)
@nox.parametrize("sphinx", SPHINX_VERSIONS)
def tests(session, sphinx):
    session.install(".[test]")
    session.run("pip", "install", f"sphinx~={sphinx}", silent=True)
    session.run("echo", "TEST FINAL PACKAGE LIST")
    session.run("pip", "freeze")
    posargs = session.posargs or ["tests"]
    session.run("pytest", "--ignore", "tests/benchmarks", *posargs, external=True)


@session(python=PYTHON_VERSIONS)
def tests_no_mpl(session):
    session.install(".[test]")
    session.run("pip", "uninstall", "-y", "matplotlib", "numpy", silent=True)
    session.run("echo", "TEST FINAL PACKAGE LIST")
    session.run("pip", "freeze")
    session.run("pytest", "tests/no_mpl_tests.py", *session.posargs, external=True)


@session(python="3.10")
def benchmark_time(session):
    session.install(".[test,benchmark,docs]")
    session.run(
        "pytest",
        "tests/benchmarks",
        "-k",
        "_time",
        "--benchmark-json",
        "output.json",
        *session.posargs,
        external=True,
    )


@session(python="3.10")
def benchmark_memory(session):
    session.install(".[test,benchmark,docs]")
    session.run(
        "pytest",
        "tests/benchmarks",
        "-k",
        "_memory",
        "--benchmark-json",
        "output.json",
        *session.posargs,
        external=True,
    )
    session.run("memray", "flamegraph", "-o", "mem_out.html", "mem_out.bin")


@session(python="3.8")
def pre_commit(session):
    session.run_always("poetry", "install", external=True)
    session.install("pre-commit")
    session.run("pre-commit", "run", "--all-files", *session.posargs, external=True)


@session(python="3.11")
def linkcheck(session):
    session.install(".[docs]")
    with session.chdir("docs"):
        session.run("sphinx-build", "-b", "linkcheck", ".", "_build/linkcheck", *session.posargs, external=True)


@session(python="3.11")
def docs(session):
    session.install(".[docs]")
    with session.chdir("docs"):
        session.run("sphinx-build", ".", "_build", *session.posargs, external=True)
