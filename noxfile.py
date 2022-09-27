import nox
from nox_poetry import session

PYTHON_VERSIONS = ["3.8", "3.10"]
SPHINX_VERSIONS = ["5.2.1", "4.5.0"]
TEST_DEPENDENCIES = [
    "pytest",
    "pytest-xdist",
    "pytest_lsp",
    "pytest-benchmark",
    "myst-parser",
    "responses",
    "lxml",
    "pyparsing!=3.0.4",
    "requests-mock",
]

BENCHMARK_DEPENDENCIES = ["memray"]


def is_supported(python: str, sphinx: str) -> bool:
    return not (python == "3.6" and sphinx not in ["3.2"])


def run_tests(session, sphinx):
    session.install(".")
    session.install(*TEST_DEPENDENCIES)
    session.run("pip", "install", f"sphinx=={sphinx}", silent=True)
    session.run("pip", "install", "-r", "docs/requirements.txt", silent=True)
    session.run("echo", "TEST FINAL PACKAGE LIST")
    session.run("pip", "freeze")
    session.run("make", "test", external=True)


@session(python=PYTHON_VERSIONS)
@nox.parametrize("sphinx", SPHINX_VERSIONS)
def tests(session, sphinx):
    if is_supported(session.python, sphinx):
        run_tests(session, sphinx)
    else:
        session.skip("unsupported combination")


@session(python="3.10")
def linkcheck(session):
    session.install(".")
    # LinkCheck can handle rate limits since Sphinx 3.4, which is needed as
    # our doc has to many links to GitHub.
    session.run("pip", "install", "sphinx==3.5.4", silent=True)

    session.run("pip", "install", "-r", "docs/requirements.txt", silent=True)
    session.run("make", "docs-linkcheck", external=True)


@session(python="3.10")
def benchmark_time(session):
    session.install(".")
    session.install(*TEST_DEPENDENCIES)
    session.install(*BENCHMARK_DEPENDENCIES)
    session.run("pip", "install", "-r", "docs/requirements.txt", silent=True)
    session.run(
        "pytest",
        "tests/benchmarks",
        "-k",
        "_time",
        "--benchmark-json",
        "output.json",
        external=True,
        env={"ON_CI": "true", "FAST_BUILD": "true"},
    )


@session(python="3.10")
def benchmark_memory(session):
    session.install(".")
    session.install(*TEST_DEPENDENCIES)
    session.install(*BENCHMARK_DEPENDENCIES)
    session.run("pip", "install", "-r", "docs/requirements.txt", silent=True)
    session.run(
        "pytest",
        "tests/benchmarks",
        "-k",
        "_memory",
        "--benchmark-json",
        "output.json",
        external=True,
        env={"ON_CI": "true", "FAST_BUILD": "true"},
    )
    session.run("memray", "flamegraph", "-o", "mem_out.html", "mem_out.bin")
