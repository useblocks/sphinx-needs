"""Pytest conftest module containing common test configuration and fixtures."""

from __future__ import annotations

import json
import os.path
import secrets
import shutil
import string
import tempfile
import tomllib
from pathlib import Path

import pytest
import yaml
from _pytest.mark import ParameterSet
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
    exactly one file -- the vendored plantuml jar -- and that jar is now fetched once
    per checkout into ``vendor/plantuml/`` at the version ``vendor/plantuml/pin.toml``
    names, so the directory is gone and this call is a no-op. What remains is the
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
    # that used to live there is fetched into `vendor/plantuml/` instead -- so this is a
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
    """The jar ``uv run poe fetch-plantuml`` puts under ``vendor/plantuml/``.

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
       jar at all now that the workspace fetches one. A variable that is set but names no
       file is a mistake worth a red run rather than a silent fall-through: falling through
       would render with a renderer the caller did not ask for and say nothing.
    2. The workspace's fetched jar, ``vendor/plantuml/plantuml-<pinned version>.jar``. The
       default in a checkout, and what every rendering poe task guarantees by declaring
       ``deps = ["fetch-plantuml"]``.
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
                "jar `uv run poe fetch-plantuml` puts in vendor/plantuml/."
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
    """The plantuml command every test project must build its diagrams with.

    CI runners have java and the fetched jar but no ``plantuml`` on ``PATH``, so a
    project left on sphinxcontrib-plantuml's default command fails to render there while
    passing on any machine that happens to have one installed. Every test therefore takes
    its command from here, whether it goes through :func:`test_app` or calls ``make_app``
    itself -- no test builds the path to the jar for itself.

    :return: The value for the ``plantuml`` configuration.
    """
    return resolve_plantuml_command(workspace_plantuml_jar())


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
def test_app(make_app, sphinx_test_tempdir, plantuml_command, request):
    """
    Fixture for creating a Sphinx application for testing.

    This fixture creates a Sphinx application with specified builder parameters and
    config overrides. It also copies the test source directory to the test temporary
    directory. The fixture yields the Sphinx application, and cleans up the temporary
    source directory after the test function has executed.

    :param make_app: A fixture for creating Sphinx applications.
    :param sphinx_test_tempdir: A fixture for providing the Sphinx test temporary directory.
    :param plantuml_command: A fixture for the plantuml command to render with.
    :param request: A pytest request object for accessing fixture parameters.

    :return: A Sphinx application object.
    """
    builder_params = request.param

    sphinx_conf_overrides = builder_params.get("confoverrides", {})
    if not builder_params.get("no_plantuml", False):
        # Since we don't want copy the plantuml.jar file for each test function,
        # we need to override the plantuml conf variable and set it to what we have already
        sphinx_conf_overrides.update(plantuml=plantuml_command)

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
    # Add the Sphinx warning as list to the app
    # Somehow "app._warning" seems to be just a boolean, if the builder is "latex" or "singlehtml".
    # In this case we don't catch the warnings.
    if builder_params.get("buildername", "html") == "html":
        app.warning_list = strip_colors(
            app._warning.getvalue().replace(str(app.srcdir) + os.sep, "srcdir/")
        ).splitlines()
    else:
        app.warning_list = None

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
def get_warnings_list():
    """
    Fixture to get a list of warnings from a SphinxTestApp.

    The split happens in each occurence of "WARNING: ".
    Each warning is returned as a string with \n as multi line speparator.
    """

    def _get_warnings_list(app: SphinxTestApp) -> list[str]:
        warnings_raw = strip_colors(app.warning.getvalue())
        warnings_split = [
            part
            for part in warnings_raw.replace("ERROR: ", "WARNING: ").split("WARNING: ")
            if part
        ]
        return warnings_split

    return _get_warnings_list


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
