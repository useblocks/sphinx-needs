"""The pytest plugin: the fixtures and hooks this workspace's suites share.

A suite opts in with one line in its own ``tests/conftest.py``::

    pytest_plugins = ["sphinx.testing.fixtures", "sphinx_needs_testkit.fixtures"]

and keeps whatever is genuinely its own beside it. Nothing here is loaded by an entry
point, deliberately: a ``pytest11`` plugin auto-loads into EVERY pytest session in an
environment that has it installed, so a user's own ``test_app`` fixture would collide with
this one silently. ``sphinx.testing.fixtures`` -- which every conftest here already names
the same way -- declines the entry point for the same reason.

**THE ORDER OF THAT LIST IS LOAD-BEARING.** ``sphinx.testing.fixtures`` defines a
``sphinx_test_tempdir`` of its own, and this module deliberately overrides it -- the
suite's builds go in one named directory that ``--sn-build-dir`` can move, not in pytest's
per-session temporary one. Two plugins define a fixture at the same level, so the one
registered LAST wins, which is why the two are named here in this order rather than this
module pulling sphinx's in for itself: a ``pytest_plugins`` inside a plugin is imported
*after* that plugin registers, so it would win instead, and the suite would quietly build
somewhere else. (Measured: it does, and every test still passes.)

**Two fixtures are the suite's to define, not this plugin's**, and both are deliberately
absent -- no default at all -- so that a suite which lost one gets pytest's "fixture not
found" for every build it makes, rather than a wrong answer:

``tests_dir``
    the suite's own ``tests`` directory, which a relative ``srcdir`` is resolved against.
    Three suites means three trees of test projects, and this module lives beside none of
    them.

``test_app_events``
    ``(event, handler, priority)`` triples to connect to every application
    :func:`test_app` builds -- the invariants the suite asserts of its own builds, which
    this plugin cannot know. A suite with none says so with an empty tuple; sphinx-needs
    gives its parent-child doctree check. It has no default HERE precisely because losing
    such a check silently is the failure this arc must not introduce: a default of "no
    checks" would make deleting the override a green run.
"""

from __future__ import annotations

import os.path
import shutil
import tempfile
from collections.abc import Callable, Iterator, Sequence
from pathlib import Path

import pytest
from sphinx.testing.util import SphinxTestApp

from ._plantuml import (
    make_plantuml_inert,
    require_plantuml_extension,
    resolve_plantuml_command,
    workspace_plantuml_jar,
)
from ._snapshots import DoctreeSnapshotExtension
from ._srcdir import (
    copy_srcdir_to_tmpdir,
    copy_test_utils,
    create_src_files_in_tmpdir,
)


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--sn-build-dir",
        action="store",
        default=None,
        help="Base directory for sphinx-needs builds",
    )


@pytest.fixture(scope="session")
def sphinx_test_tempdir(request: pytest.FixtureRequest, tests_dir: Path) -> Path:
    """
    Fixture to provide a temporary directory for Sphinx testing.

    This function creates a custom temporary folder to avoid potential conflicts
    with utility functions from Sphinx and pytest.

    :return Path: Path object representing the temporary directory.
    """
    # We create a temp-folder on our own, as the util-functions from sphinx and pytest make troubles.
    # It seems like they reuse certain-temp names

    temp_base = os.path.abspath(
        request.config.getoption("--sn-build-dir") or tempfile.gettempdir()
    )

    sphinx_test_tempdir = Path(temp_base).joinpath("sn_test_build_data")

    # if not (sphinx_test_tempdir.exists() and sphinx_test_tempdir.isdir()):
    sphinx_test_tempdir.mkdir(exist_ok=True)

    # a guarded no-op for the suites in this repository -- none of them has a
    # `doc_test/utils` any more -- kept for fixture data a suite might need copied once
    # per session rather than per test; see `copy_test_utils`
    copy_test_utils(tests_dir / "doc_test/utils", sphinx_test_tempdir / "utils")

    return sphinx_test_tempdir


@pytest.fixture(scope="session")
def plantuml_command() -> str:
    """The plantuml command every test project that RENDERS builds its diagrams with.

    CI runners have java and the checkout's jar but no ``plantuml`` on ``PATH``, so a
    project left on sphinxcontrib-plantuml's default command fails to render there while
    passing on any machine that happens to have one installed. Every test that renders
    therefore takes its command from here, whether it goes through :func:`test_app` or
    calls ``make_app`` itself -- no test builds the path to the jar for itself.

    :func:`resolve_plantuml_command` RAISES when it finds no renderer at all, which is
    why :func:`test_app` does NOT name this fixture in its signature: a fixture named
    there is resolved whether or not the body uses it, and on a machine with no jar and
    no ``PLANTUML_JAR`` that difference is the whole suite erroring instead of the dozen
    tests that genuinely need a renderer. It is pulled in with
    ``request.getfixturevalue`` inside the opt-in branch instead, and a ``make_app``
    caller that renders only for some of its parameters should do the same rather than
    name it in its signature.

    :return: The value for the ``plantuml`` configuration.
    """
    return resolve_plantuml_command(workspace_plantuml_jar())


@pytest.fixture(scope="function")
def test_app(
    make_app,
    sphinx_test_tempdir: Path,
    tests_dir: Path,
    test_app_events: Sequence[tuple[str, Callable[..., object], int]],
    request: pytest.FixtureRequest,
) -> Iterator[SphinxTestApp]:
    """
    Fixture for creating a Sphinx application for testing.

    This fixture creates a Sphinx application with specified builder parameters and
    config overrides. It also copies the test source directory to the test temporary
    directory. The fixture yields the Sphinx application, and cleans up the temporary
    source directory after the test function has executed.

    **Rendering PlantUML is opt in**: a parameter dict that says ``"plantuml": True``
    gets the session's :func:`plantuml_command`; every other build gets an inert
    renderer (:func:`make_plantuml_inert`), which REFUSES to render rather than
    quietly rendering with whatever renderer the machine happens to carry.
    Twelve of the sphinx-needs suite's 266 parameter dicts opt in -- diagrams are parsed
    everywhere, but only those twelve assert on a rendered one, and rendering the rest
    cost a third of the suite's wall time.

    Once a build opts in, ``plantuml`` and ``plantuml_batch_size`` in its own
    ``confoverrides`` are overwritten without a word: the renderer is the suite's, not the
    test's.

    :param make_app: A fixture for creating Sphinx applications.
    :param sphinx_test_tempdir: A fixture for providing the Sphinx test temporary directory.
    :param tests_dir: The suite's own ``tests`` directory (the suite defines this).
    :param test_app_events: Sphinx events the suite connects to every build.
    :param request: A pytest request object for accessing fixture parameters.

    :return: A Sphinx application object.
    """
    # THE PLUGIN ORDER, asserted rather than trusted to a comment. `sphinx.testing.fixtures`
    # defines a `sphinx_test_tempdir` of its own -- `tmp_path_factory.getbasetemp()`, named
    # `pytest-<n>` -- and where two plugins define a fixture the one registered LAST wins. If
    # it wins here, every build in the suite goes somewhere else and `--sn-build-dir` is
    # inert, with the whole suite still GREEN. The names cannot collide, so this is total.
    assert sphinx_test_tempdir.name == "sn_test_build_data", (
        "sphinx.testing.fixtures' sphinx_test_tempdir won -- check the plugin order: this "
        "plugin must be named AFTER `sphinx.testing.fixtures` in the suite's "
        "`pytest_plugins`"
    )

    builder_params = request.param

    # a COPY, because ``builder_params`` is the dict object in the test module's own
    # ``@pytest.mark.parametrize`` argument list -- evaluated once at collection and
    # shared by every rerun of that parameter, so updating it in place writes into the
    # test's source-level literal
    sphinx_conf_overrides = dict(builder_params.get("confoverrides", {}))
    renders = builder_params.get("plantuml", False)
    if renders:
        # requested HERE and not in the signature: `plantuml_command` raises on a machine
        # with no renderer, and a fixture named in a signature is resolved whether or not
        # the body uses it
        sphinx_conf_overrides.update(
            plantuml=request.getfixturevalue("plantuml_command"),
            # sphinxcontrib-plantuml renders one diagram per `java` process by default
            # (`plantuml_batch_size` is 1, and `collect_nodes` is only called above 1), and
            # the JVM start is 2.04 s of every 2.13 s render, measured. Batching renders a
            # whole document's diagrams in one process. 100 is "as many as there are": the
            # largest opted-in project draws a dozen
            plantuml_batch_size=100,
        )

    srcdir = builder_params.get("srcdir")
    files = builder_params.get("files")
    if (srcdir is None) == (files is None):
        raise ValueError("Exactly one of srcdir, files must not be None")

    if srcdir is not None:
        # copy test srcdir to test temporary directory sphinx_test_tempdir
        src_dir = copy_srcdir_to_tmpdir(
            srcdir, sphinx_test_tempdir, relative_to=tests_dir
        )
    else:
        # create given files in tmpdir
        src_dir = create_src_files_in_tmpdir(files, sphinx_test_tempdir)

    parent_path = src_dir.parent.resolve()

    # return sphinx.testing fixture make_app and new srcdir which is in sphinx_test_tempdir
    app: SphinxTestApp = make_app(
        buildername=builder_params.get("buildername", "html"),
        srcdir=src_dir,
        freshenv=builder_params.get("freshenv"),
        confoverrides=sphinx_conf_overrides,
        status=builder_params.get("status"),
        warning=builder_params.get("warning"),
        tags=builder_params.get("tags"),
        parallel=builder_params.get("parallel", 0),
    )

    if renders:
        # an opt-in on a project that never loads the extension renders nothing and earns
        # two `unknown config value ... in override, ignoring` warnings instead -- the
        # exact warnings the opt-in design removed from every other project
        require_plantuml_extension(
            app, f"{request.node.nodeid} (srcdir {srcdir or files})"
        )
    elif getattr(app.config, "plantuml", None) == "plantuml":
        # `elif`, and the guard rather than a bare call: a suite whose own `make_app`
        # already applies this policy (sphinx-needs' does) has neutralised the app before
        # it got here, and calling it twice is duplicated work and duplicated intent.
        # The condition is the same one: sphinxcontrib-plantuml's default command.
        make_plantuml_inert(app)
    for event, handler, priority in test_app_events:
        app.connect(event, handler, priority=priority)

    yield app

    app.cleanup()

    # Clean up the srcdir of each Sphinx app after the test function has executed
    if request.config.getoption("--sn-build-dir") is None:
        shutil.rmtree(parent_path, ignore_errors=True)


@pytest.fixture
def snapshot_doctree(snapshot):
    """Snapshot fixture for doctrees.

    Here we try to sanitize the doctree, to make the snapshots reproducible.
    """
    try:
        return snapshot.with_defaults(extension_class=DoctreeSnapshotExtension)
    except AttributeError:
        # fallback for older versions of pytest-snapshot
        return snapshot.use_extension(DoctreeSnapshotExtension)
