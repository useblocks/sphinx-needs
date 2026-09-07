"""Pytest conftest module containing common test configuration and fixtures."""

from __future__ import annotations

import json
import os.path
import re
import secrets
import shutil
import string
import tempfile
import tomllib
from pathlib import Path

import pytest
import yaml
from _pytest.mark import ParameterSet
from docutils import nodes
from docutils.nodes import document
from sphinx import version_info
from sphinx.application import Sphinx
from sphinx.testing.util import SphinxTestApp
from sphinx.util.console import strip_colors
from syrupy.extensions.single_file import SingleFileSnapshotExtension, WriteMode

from sphinx_needs._jinja import render_template_string

pytest_plugins = "sphinx.testing.fixtures"


def generate_random_string() -> str:
    """
    Generate a random string of 10 characters consisting of letters (both uppercase and lowercase) and digits.

    :return: A random string.
    """
    characters = string.ascii_letters + string.digits
    return "".join(secrets.choice(characters) for i in range(10))


def copy_srcdir_to_tmpdir(srcdir: Path, tmp: Path) -> Path:
    """
    Copy Source Directory to Temporary Directory.

    This function copies the contents of a source directory to a temporary
    directory. It generates a random subdirectory within the temporary directory
    to avoid conflicts and enable parallel processes to run without conflicts.

    :param srcdir: Path to the source directory.
    :param tmp: Path to the temporary directory.

    :return: Path to the newly created directory in the temporary directory.
    """
    srcdir = Path(__file__).parent.resolve() / srcdir
    tmproot = tmp.joinpath(generate_random_string()) / Path(srcdir).name
    shutil.copytree(srcdir, tmproot)
    return tmproot


def create_src_files_in_tmpdir(files: list[tuple[Path, str]], tmp: Path) -> Path:
    """Create source files in a temporary directory under the subdir src."""
    subdir = Path("src")
    tmproot = tmp.joinpath(generate_random_string()) / subdir
    tmproot.mkdir(exist_ok=True, parents=True)
    for file in files:
        file_path, content = file
        file_abs = tmproot.joinpath(str(file_path))
        file_abs.parent.mkdir(exist_ok=True)
        file_abs.write_text(content)
    return tmproot


def pytest_addoption(parser):
    parser.addoption(
        "--sn-build-dir",
        action="store",
        default=None,
        help="Base directory for sphinx-needs builds",
    )


def copy_test_utils(source: Path, destination: Path) -> None:
    """Copy ``tests/doc_test/utils`` into the session tempdir, if it is there at all.

    It no longer copies a jar, and today it copies nothing: ``doc_test/utils`` held
    exactly one file -- a plantuml jar for this package alone -- and the workspace now
    carries one shared jar, committed at ``vendor/plantuml/`` at the version
    ``vendor/plantuml/pin.toml`` names, so the directory is gone and this call is a
    no-op. What remains is the
    GUARD, and it is the load-bearing half: ``copytree`` on a directory that is not
    there raises ``FileNotFoundError`` out of a session fixture every rendering test
    depends on, which would take out the suite before
    :func:`resolve_plantuml_command` -- the whole point of which is to let a tree with
    no jar be pointed at a PlantUML of its own -- was ever reached.

    The destination is created only when there is something to put in it, so a caller
    that finds no ``<tempdir>/utils`` knows there was nothing to copy.

    :param source: The suite's own ``doc_test/utils`` directory.
    :param destination: Where it is copied to for this session.
    """
    if not source.is_dir():
        return
    destination.mkdir(exist_ok=True)
    shutil.copytree(source, destination, dirs_exist_ok=True)


@pytest.fixture(scope="session")
def sphinx_test_tempdir(request) -> Path:
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

    # `doc_test/utils` is empty of anything the suite ships today -- the plantuml jar
    # that used to live there is committed at `vendor/plantuml/` instead -- so this is a
    # guarded no-op kept for fixture data a test project might need copied once per
    # session rather than per test
    copy_test_utils(
        Path(__file__).parent.resolve() / "doc_test/utils",
        sphinx_test_tempdir / "utils",
    )

    return sphinx_test_tempdir


# The jar path is DOUBLE-QUOTED. sphinxcontrib-plantuml passes a list or tuple through
# untouched and `shlex`-splits anything else -- `posix=True` off Windows, `posix=False`
# plus its own `_ntunquote` on it -- so an unquoted path containing a space arrives as
# two argv elements and the render dies. Both split paths strip these quotes again, so
# the argv is unchanged for a path without one. sphinx-mounts solves the same problem by
# returning a tuple; a string is what this fixture's callers already pass around.
_PLANTUML_JAVA = 'java -Djava.awt.headless=true -jar "{}"'


def workspace_plantuml_jar() -> Path | None:
    """The workspace's one PlantUML jar, committed under ``vendor/plantuml/``.

    Computed from the pin rather than hard-coded, because the version is IN the filename
    (``plantuml-<version>.jar``) and ``vendor/plantuml/pin.toml`` is the one place this
    repository writes it -- the jar this replaced was called ``plantuml.jar`` and was four
    years old without anyone noticing.

    Returns ``None`` when there is no pin to read, which is what an sdist looks like:
    ``vendor/`` sits at the repository root, and flit's ``[tool.flit.sdist] include``
    patterns cannot escape the package directory, so neither the pin nor the jar is in the
    tarball. That is the case route (3) below exists for.

    This reads the TOML itself instead of importing ``tools/src/sn_tools/fetch_plantuml.py``
    (which computes the same path) on purpose: the tooling is a virtual member run by path
    and installed into nothing, so a test suite that imported it would only work from a
    checkout -- exactly the tree that does not need this fallback reasoning.

    :return: The pinned jar's path, or ``None`` if this tree carries no pin.
    """
    root = Path(__file__).resolve().parents[3]
    pin = root / "vendor" / "plantuml" / "pin.toml"
    if not pin.is_file():
        return None
    version = tomllib.loads(pin.read_text(encoding="utf-8"))["version"]
    return pin.parent / f"plantuml-{version}.jar"


def resolve_plantuml_command(workspace_jar: Path | None) -> str:
    """Work out how this suite renders PlantUML, from three sources in this order.

    The point of the chain is that the jar's *location* is an implementation detail of
    this package rather than a fact its callers have to know.

    1. ``PLANTUML_JAR``, run through ``java``. Naming a jar is an explicit choice, so it
       wins: it is how sphinx-mounts' suite is already pointed at a renderer, and it is
       the only route open to someone running these tests from the sdist -- which ships no
       jar at all now that the workspace keeps one. A variable that is set but names no
       file is a mistake worth a red run rather than a silent fall-through: falling through
       would render with a renderer the caller did not ask for and say nothing.
    2. The workspace's committed jar, ``vendor/plantuml/plantuml-<pinned version>.jar``.
       The default in a checkout, which carries it; every rendering poe task additionally
       declares ``deps = ["fetch-plantuml"]``, which hashes it against the pin.
    3. A ``plantuml`` executable on ``PATH`` -- and only once (2) is gone. This suite
       renders for real and asserts on the output, so a developer machine that happens to
       carry a homebrew ``plantuml`` must not quietly swap the renderer version out from
       under it. The executable is the fallback for a tree with no jar, not a preference.

    An EMPTY ``PLANTUML_JAR`` is treated as unset rather than as a mistake, because that
    is how it arrives: a developer shell with ``PLANTUML_JAR=`` exported, and a workflow
    that computes the value with an expression. sphinx-mounts reads it the same way.

    :param workspace_jar: The pinned jar's path, or ``None`` if this tree carries no pin.
    :return: The value for the ``plantuml`` configuration.
    """
    env_jar = os.environ.get("PLANTUML_JAR")
    if env_jar:
        if not Path(env_jar).is_file():
            raise RuntimeError(
                f"PLANTUML_JAR names {env_jar!r}, which is not a file. "
                "Point it at a plantuml jar, or unset it to render with the "
                "jar committed at vendor/plantuml/."
            )
        return _PLANTUML_JAVA.format(env_jar)
    if workspace_jar is not None and workspace_jar.is_file():
        return _PLANTUML_JAVA.format(workspace_jar)
    # sphinxcontrib.plantuml invokes the command synchronously; on Windows the
    # chocolatey package's `plantuml` shim is non-blocking (javaw), so its `plantumlc`
    # (java) shim is the one to use there -- a lesson sphinx-mounts has already paid for
    # (see `_plantuml_extra_conf` in its tests/test_path_directives.py)
    for name in ("plantumlc", "plantuml") if os.name == "nt" else ("plantuml",):
        if executable := shutil.which(name):
            return executable
    # Two messages, because two trees. In a CHECKOUT the fix is the task, so it leads. In a
    # tree with no pin -- an sdist -- there is no `vendor/`, no root `pyproject.toml` and no
    # poe to run it with, so leading with `poe fetch-plantuml` would be an instruction the
    # reader cannot follow; the two routes that do work lead instead. `docs/conf.py` and
    # `performance/performance_test.py` say the same two things in the same order.
    if workspace_jar is None:
        raise RuntimeError(
            "no PlantUML to render with: no `plantuml` (nor, on Windows, `plantumlc`) is "
            "on PATH and PLANTUML_JAR is unset, and this tree has no "
            "vendor/plantuml/pin.toml naming one -- which is what an sdist looks like. "
            "Set PLANTUML_JAR to a plantuml jar (with java on PATH), or install a "
            "plantuml executable; in a checkout of the repository, "
            "`uv run poe fetch-plantuml` downloads the pinned one."
        )
    raise RuntimeError(
        f"no PlantUML to render with: {workspace_jar} does not exist, no `plantuml` "
        "(nor, on Windows, `plantumlc`) is on PATH, and PLANTUML_JAR is unset. Run "
        "`uv run poe fetch-plantuml` to download the pinned jar, or set PLANTUML_JAR "
        "to a plantuml jar of your own (with java on PATH), or install a plantuml "
        "executable."
    )


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
    ``request.getfixturevalue`` inside the opt-in branch instead.

    :return: The value for the ``plantuml`` configuration.
    """
    return resolve_plantuml_command(workspace_plantuml_jar())


# The ``plantuml`` command for a build that did NOT opt in: one that cannot be run. Not
# merely a placeholder -- sphinxcontrib-plantuml's own default is the bare word
# ``plantuml``, so a build left on the default renders for real, silently, with whatever
# unpinned renderer the developer's machine happens to carry. One token, no spaces, so
# that whatever splits it (``shlex`` off Windows, sphinxcontrib's own unquoting on it)
# still names it in the ``plantuml command %r cannot be run`` error it raises.
_INERT_PLANTUML_COMMAND = (
    "sphinx-needs-tests-this-build-did-not-opt-into-plantuml"
    "--add-plantuml-True-to-its-test_app-parameters"
)


def _skip_plantuml_node(self, node: nodes.Element) -> None:
    """Visit a ``plantuml`` node by dropping it: no subprocess, no warning, no markup."""
    raise nodes.SkipNode


def _refuse_to_render(*args: object, **kwargs: object) -> None:
    """Stand in for sphinxcontrib-plantuml's renderer on a build that did not opt in."""
    raise AssertionError(
        "PlantUML rendering was reached by a test_app build that did not opt into it. "
        "Add '\"plantuml\": True' to that test's test_app parameter dict if it means "
        "to render; otherwise find out what got past the inert node visitors."
    )


def make_plantuml_inert(app: SphinxTestApp) -> None:
    """Neutralise PlantUML rendering for one app, for a test that did not opt in.

    Three layers, and each covers what the one before it cannot:

    * every node visitor sphinxcontrib-plantuml registers is replaced with one that raises
      ``SkipNode``. That is where the time goes: the directive still parses and the node
      still reaches the doctree -- so the tests that inspect ``plantuml`` nodes, or the
      ``.puml`` files sphinx-needs writes itself, keep passing untouched -- but no JVM
      starts, and a JVM start is 2.04 s of every 2.13 s render, measured.
    * THIS APP'S OWN ``PlantumlBuilder`` has its two render entry points replaced with one
      that raises. That is the assertion that nothing renders, and it is made on the app
      rather than on the output directory because 23 test functions in this suite run a
      real ``sphinx-build`` SUBPROCESS (twelve of them in ``test_needuml.py``), four of them
      into ``app.outdir`` itself: a rendered file found in that directory cannot be
      attributed to the fixture's app, while a call reaching this object can only have come
      from it.
    * the ``plantuml`` configuration is pointed at :data:`_INERT_PLANTUML_COMMAND`. This one
      is a SENTINEL rather than a fence, and the difference is worth stating: its whole
      protection is that the token cannot be ``exec``-ed, and when sphinxcontrib does try it
      the resulting ``PlantUmlError`` is caught by its own ``_prepare_html_render``, logged as
      a warning and turned into a ``SkipNode`` -- so a build that got past both layers above
      would warn and drop the diagram rather than fail. It also does not reach the batch
      renderer: ``PlantumlBuilder.__init__`` freezes ``_base_cmdargs`` at ``builder-inited``,
      before this function runs, and only ``render()`` and ``render_plantuml_inline()`` read
      the live config (layer two is what covers that path). What it does buy is that "not
      opted in" never means "run sphinxcontrib's default", which is the bare word
      ``plantuml`` -- i.e. render with an unpinned renderer, and say nothing.

    Layer one could also be spelled with a PUBLIC config value: ``plantuml_output_format =
    "none"`` makes ``_prepare_html_render`` raise ``SkipNode`` and zeroes the batch path's
    ``image_formats``, in every sphinxcontrib-plantuml back to 0.18.1. It is not used here
    because it covers only the html and latex builders, where ``_NODE_VISITORS`` covers all
    seven; and the private name is safe to depend on precisely because layer two is loud --
    if a future release dropped it, the import below raises ``ImportError`` at fixture setup
    rather than quietly restoring rendering.

    **What this does NOT cover**: anything that is not this app object. A test that runs
    ``sphinx-build`` as a subprocess gets a process with its own config (see
    :func:`plantuml_subprocess_args`), and a test that calls ``make_app`` directly without
    taking :func:`plantuml_command` never comes through here at all.

    All of it happens after the app exists rather than through ``confoverrides``, because a
    project that does not load ``sphinxcontrib.plantuml`` -- 88 of this suite's 138 test
    projects -- would otherwise collect an "unknown config value 'plantuml' in override,
    ignoring" warning that it never used to have.

    :param app: The application to neutralise, already constructed and not yet built.
    """
    if "sphinxcontrib.plantuml" not in app.extensions:
        return

    from sphinxcontrib.plantuml import _NODE_VISITORS, plantuml

    app.config.plantuml = _INERT_PLANTUML_COMMAND
    app.add_node(
        plantuml,
        override=True,
        **dict.fromkeys(_NODE_VISITORS, (_skip_plantuml_node, None)),
    )
    plantuml_builder = getattr(app.builder, "plantuml_builder", None)
    if plantuml_builder is not None:
        plantuml_builder.render = _refuse_to_render
        plantuml_builder.render_batches = _refuse_to_render


@pytest.fixture(scope="session")
def plantuml_subprocess_args(plantuml_command: str) -> list[str]:
    """``sphinx-build`` arguments pointing a SUBPROCESS build at this suite's renderer.

    :func:`make_plantuml_inert` patches an app object, and a test that shells out to
    ``sphinx-build`` gets a process the fixture cannot reach: it reads the project's own
    ``conf.py``, where sphinxcontrib-plantuml's default is the bare word ``plantuml``. Such
    a build therefore renders with whatever renderer the machine happens to carry, unpinned
    and silently -- measured, before this fixture existed, as eight diagrams drawn by a
    developer's homebrew PlantUML 1.2026.1 against the 1.2026.8 ``vendor/plantuml/pin.toml``
    names. Passing these in makes a subprocess build render with the same command every
    in-process build uses, and raise on a machine that has no renderer at all.

    :return: ``["-D", "plantuml=<command>"]``, to splat into a ``sphinx-build`` argv.
    """
    return ["-D", f"plantuml={plantuml_command}"]


#: A line STARTS a warning record when it carries a severity token, optionally behind the
#: location sphinx puts in front of it (``<path>: `` or ``<path>:<line>: ``). Everything
#: after such a line and before the next one is a continuation of that record.
#:
#: This is a HEURISTIC over what sphinx and docutils happen to emit, not a boundary either
#: of them defines, and it is worth knowing where it parts company from the truth: a
#: continuation line at column 0 that itself carries a severity token, or that merely reads
#: ``something: WARNING: …``, starts a new record. Every continuation this suite provokes is
#: indented -- docutils indents its literal blocks, sphinx-needs indents its violation
#: reports -- and the anchored ``^`` plus the non-greedy ``.*?:\s`` cannot reach a token
#: behind leading whitespace, so the heuristic holds here. It is a much narrower failure
#: than splitting on the substring ``"WARNING: "``, which is what this suite used to do:
#: that detached every location from its message, turned N located warnings into N+1
#: entries, erased the WARNING/ERROR distinction, and cut in half any message that merely
#: quoted the token anywhere at all.
_RECORD_START = re.compile(r"^(?:.*?:\s)?(?:WARNING|ERROR|SEVERE|CRITICAL):\s")


def _warning_stream_text(app: SphinxTestApp) -> str:
    """The raw warning stream of a built application.

    Raises rather than returning ``""`` when there is no readable stream. The attribute
    this API replaced set ``warning_list = None`` in that case, so an assertion on it
    FAILED; returning empty text instead would make :func:`assert_no_warnings` pass on an
    application whose warnings were never read, which is the one failure mode this whole
    change exists to remove.

    :param app: A built application.
    :return: Everything written to its warning stream.
    :raises TypeError: If neither ``_warning`` nor ``warning`` is a readable stream.
    """
    stream = getattr(app, "_warning", None)
    if not hasattr(stream, "getvalue"):
        stream = getattr(app, "warning", None)
    if not hasattr(stream, "getvalue"):
        builder = getattr(getattr(app, "builder", None), "name", "<unknown>")
        raise TypeError(
            f"the {builder!r} application has no readable warning stream: its `_warning` "
            f"attribute is {getattr(app, '_warning', None)!r}. Reading warnings from it "
            "would silently report none."
        )
    return str(stream.getvalue())


def build_warnings(
    source: SphinxTestApp | str, *, srcdir: str | Path | None = None
) -> list[str]:
    """Every warning a build emitted, normalised, one entry per RECORD.

    The one normalisation this suite has, in one place:

    * ANSI colour codes stripped (``strip_colors``);
    * the source directory rewritten to ``<srcdir>/``, so an assertion can name a file
      without knowing which temporary directory the fixture chose;
    * one entry per warning record, **including its location**, with a multi-line message
      kept whole rather than split into one entry per line -- see :data:`_RECORD_START` for
      what "record" means here and where the heuristic stops holding;
    * the severity token kept as it was emitted, so an ``ERROR`` never reads as a
      ``WARNING``;
    * anything before the first record DROPPED, so a capture that carries a build's status
      lines ("Running Sphinx v…", "build succeeded") reports the warnings in it and not the
      noise around them.

    Read AFTER the build, never snapshotted during fixture setup: the attribute this
    replaced was computed before the test called ``app.build()``, so every assertion on it
    was really an assertion about application construction.

    :param source: A built application, or captured text (a subprocess' ``stderr``).
    :param srcdir: The directory to rewrite to ``<srcdir>/``. Taken from the application
        when ``source`` is one; give it explicitly for captured text if the rewrite matters.
    :return: One string per warning record, in emission order.
    """
    if isinstance(source, str):
        text = source
    else:
        text = _warning_stream_text(source)
        if srcdir is None:
            srcdir = source.srcdir

    text = strip_colors(text)
    if srcdir is not None:
        # through `Path`, so a caller that passes a string with a trailing separator still
        # gets the rewrite (`app.srcdir` is a Path and never has one)
        root = str(Path(srcdir))
        for separator in (os.sep, "/"):
            text = text.replace(root + separator, "<srcdir>/")

    records: list[str] = []
    for line in text.splitlines():
        if _RECORD_START.match(line):
            records.append(line)
        elif records:
            records[-1] += "\n" + line
    return records


def assert_no_warnings(
    source: SphinxTestApp | str, *, srcdir: str | Path | None = None
) -> None:
    """Assert a build emitted nothing at all, and print everything it did emit if it did.

    :param source: A built application, or captured text.
    :param srcdir: Passed through to :func:`build_warnings`.
    """
    emitted = build_warnings(source, srcdir=srcdir)
    assert not emitted, "the build emitted {} warning(s):\n{}".format(
        len(emitted), "\n".join(emitted)
    )


def warning_count(
    source: SphinxTestApp | str,
    warning_type: str | None = None,
    *,
    srcdir: str | Path | None = None,
) -> int:
    """How many warnings a build emitted, optionally only those of one warning type.

    :param source: A built application, or captured text.
    :param warning_type: Count only records carrying exactly this warning type, matched
        against the ``[type]`` token sphinx emits -- brackets included, so
        ``"needs.variant"`` does not also count ``needs.variants``. It is one type, not a
        family: there is no prefix matching here, deliberately, because this codebase has
        live collisions (``needs.link_outgoing`` / ``needs.link_ref`` /
        ``needs.link_condition_failed``) that a prefix would silently merge.
    :param srcdir: Passed through to :func:`build_warnings`.
    :return: The number of matching warning records.
    """
    emitted = build_warnings(source, srcdir=srcdir)
    if warning_type is None:
        return len(emitted)
    token = f"[{warning_type}]"
    return sum(1 for record in emitted if token in record)


# node classes from extensions outside sphinx-needs are exempt from the parent check:
# sphinx-design installs its tab nodes by assigning ``children`` directly, so they never get
# a parent (#1757), and the invariant guarded here (#1564) is about sphinx-needs' own nodes
_PARENT_CHECK_EXEMPT_MODULES = ("sphinx_design.",)


def _check_parent_child(app: Sphinx, doctree: document, docname: str):
    for idx, node in enumerate(doctree.findall()):
        if idx == 0:
            continue
        if type(node).__module__.startswith(_PARENT_CHECK_EXEMPT_MODULES):
            continue
        assert node.parent is not None, (
            f"{docname}: <{type(node).__name__}> has no parent"
        )


@pytest.fixture(scope="function")
def test_app(make_app, sphinx_test_tempdir, request):
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
    Twelve of this suite's 266 parameter dicts opt in -- diagrams are parsed everywhere,
    but only those twelve assert on a rendered one, and rendering the rest cost a third
    of the suite's wall time.

    :param make_app: A fixture for creating Sphinx applications.
    :param sphinx_test_tempdir: A fixture for providing the Sphinx test temporary directory.
    :param request: A pytest request object for accessing fixture parameters.

    :return: A Sphinx application object.
    """
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
        src_dir = copy_srcdir_to_tmpdir(srcdir, sphinx_test_tempdir)
    else:
        # create given files in tmpdir
        src_dir = create_src_files_in_tmpdir(files, sphinx_test_tempdir)

    parent_path = src_dir.parent.resolve()

    if version_info < (7, 2):
        from sphinx.testing.path import path

        src_dir = path(str(src_dir))

    # return sphinx.testing fixture make_app and new srcdir which is in sphinx_test_tempdir
    app: SphinxTestApp = make_app(
        buildername=builder_params.get("buildername", "html"),
        srcdir=src_dir,
        freshenv=builder_params.get("freshenv"),
        confoverrides=sphinx_conf_overrides,
        status=builder_params.get("status"),
        warning=builder_params.get("warning"),
        tags=builder_params.get("tags"),
        docutilsconf=builder_params.get("docutilsconf"),
        parallel=builder_params.get("parallel", 0),
    )

    if not renders:
        make_plantuml_inert(app)
    # Check created all parent-child node relationships after any other
    # code within the doctree-resolved event by setting the priority to 999.
    # Placing this test here provides coverage for quite a few tests in
    # the suite, and hopefully will test any future features.
    app.connect("doctree-resolved", _check_parent_child, priority=999)

    yield app

    app.cleanup()

    # Clean up the srcdir of each Sphinx app after the test function has executed
    if request.config.getoption("--sn-build-dir") is None:
        shutil.rmtree(parent_path, ignore_errors=True)


class DoctreeSnapshotExtension(SingleFileSnapshotExtension):
    _write_mode = WriteMode.TEXT
    file_extension = "doctree.xml"

    def serialize(self, data, **kwargs):
        if not isinstance(data, document):
            raise TypeError(f"Expected document, got {type(data)}")
        doc = data.deepcopy()
        doc["source"] = "<source>"  # this will be a temp path
        doc.attributes.pop("translation_progress", None)  # added in sphinx 7.1
        return doc.pformat()


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


def pytest_generate_tests(metafunc: pytest.Metafunc) -> None:
    """Generate tests for a ``@pytest.mark.fixture_file`` decorator."""
    for marker in metafunc.definition.iter_markers(name="fixture_file"):
        params = create_parameters(*marker.args, **marker.kwargs)
        metafunc.parametrize(argnames="content", argvalues=params)


THIS_DIR = Path(__file__).parent


def create_parameters(
    *rel_paths: str, skip_files: list[str] | None = None
) -> list[ParameterSet]:
    """Create parameters for a pytest param_file decorator."""
    paths: list[Path] = []
    for rel_path in rel_paths:
        assert not Path(rel_path).is_absolute()
        path = THIS_DIR.joinpath(rel_path)
        if path.is_file():
            paths.append(path)
        elif path.is_dir():
            paths.extend(path.glob("*.yaml"))
        else:
            raise FileNotFoundError(f"File / folder not found: {path}")

    if skip_files:
        paths = [
            path for path in paths if str(path.relative_to(THIS_DIR)) not in skip_files
        ]

    if not paths:
        raise FileNotFoundError(f"No files found: {rel_paths}")

    if len(paths) == 1:
        with paths[0].open(encoding="utf8") as f:
            try:
                data = yaml.safe_load(f)
            except Exception as err:
                raise OSError(f"Error loading {paths[0]}") from err
        return [pytest.param(value, id=id) for id, value in data.items()]
    else:
        params: list[ParameterSet] = []
        for subpath in paths:
            with subpath.open(encoding="utf8") as f:
                try:
                    data = yaml.safe_load(f)
                except Exception as err:
                    raise OSError(f"Error loading {subpath}") from err
            for key, value in data.items():
                params.append(
                    pytest.param(
                        value,
                        id=f"{subpath.relative_to(THIS_DIR).with_suffix('').as_posix()}-{key}",
                    )
                )
        return params


@pytest.fixture
def write_fixture_files():
    def _inner(tmp: Path, content: dict[str, str]) -> None:
        section_file_mapping: dict[str, Path] = {
            "conf": tmp / "conf.py",
            "ubproject": tmp / "ubproject.toml",
            "rst": tmp / "index.rst",
            "schemas": tmp / "schemas.json",
        }
        for section, file_path in section_file_mapping.items():
            if section in content:
                if isinstance(content[section], dict):
                    # used for schemas.json
                    file_path.write_text(
                        json.dumps(content[section], indent=2), encoding="utf-8"
                    )
                elif isinstance(content[section], str):
                    file_path.write_text(content[section], encoding="utf-8")
                else:
                    raise ValueError(
                        f"Unsupported content type for section '{section}': {type(content[section])}"
                    )

    return _inner


@pytest.fixture
def schema_benchmark_app(tmpdir: Path, request: pytest.SubRequest, make_app):
    """Fixture to create a schema benchmark Sphinx project."""
    need_cnt: int = request.param

    assert need_cnt % 10 == 0, "need_cnt must be a multiple of 10"
    page_cnt = int(need_cnt / 10)

    this_file_dir = Path(__file__).parent

    src_dir = this_file_dir / "doc_test" / "doc_schema_benchmark"
    page_template_path = src_dir / "page.rst.j2"
    with page_template_path.open() as fp:
        template_content = fp.read()

    pages_dir = Path(tmpdir) / "pages"
    pages_dir.mkdir(exist_ok=True)
    toctree_content = """
.. toctree::
    :maxdepth: 2

"""
    width = len(str(page_cnt))
    for i in range(1, page_cnt + 1):
        i_fmt = f"{i:0{width}d}"
        page_rst_content = render_template_string(
            template_content, {"page_nr": i_fmt}, autoescape=False
        )

        page_name = f"page_{i_fmt}"
        page_file = f"{page_name}.rst"
        page_rst_path = pages_dir / page_file
        page_rst_path.write_text(page_rst_content, encoding="utf-8")
        toctree_content += f"   pages/{page_name}\n"

    index_file = tmpdir / "index.rst"
    index_file.write_text(toctree_content, encoding="utf-8")

    copy_files = [
        src_dir / "conf.py",
        src_dir / "schemas.json",
        src_dir / "ubproject.toml",
    ]
    for copy_file in copy_files:
        dst_file = tmpdir / copy_file.name
        dst_file.write_text(copy_file.read_text(), encoding="utf-8")

    app: SphinxTestApp = make_app(
        # the schema builder does only validate, no output
        buildername="schema",
        srcdir=Path(tmpdir),
        freshenv=True,
    )
    yield app
    app.cleanup()
