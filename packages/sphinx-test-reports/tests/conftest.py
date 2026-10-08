"""Pytest conftest module containing common test configuration and fixtures."""

import io
import shutil
from pathlib import Path
from tempfile import mkdtemp

import pytest
from docutils.parsers.rst import directives, roles
from sphinx.util.docutils import additional_nodes, unregister_node

# Sphinx is a dependency of this package, so its fixtures are always there. `pytester`,
# which the alias tests drive the old plugin name with, ships with pytest itself. (The
# converter's and the plugin's own suite is ub-test-reports', and runs without Sphinx.)
pytest_plugins = ["sphinx.testing.fixtures", "pytester"]


def copy_srcdir_to_tmpdir(srcdir, tmp):
    srcdir = Path(__file__).parent.absolute() / srcdir
    tmproot = tmp / Path(srcdir).name
    shutil.copytree(srcdir, tmproot)
    return tmproot


@pytest.fixture(scope="function")
def test_app(make_app, request):
    # We create a temp-folder on our own, as the util-functions from sphinx and pytest make troubles.
    # It seems like they reuse certain-temp names
    sphinx_test_tempdir = Path(mkdtemp())

    builder_params = request.param

    # copy plantuml.jar, xml files and json files to current test temdir
    util_files = Path(__file__).parent.absolute() / "doc_test/utils"
    shutil.copytree(util_files, sphinx_test_tempdir / "utils")

    # copy test srcdir to test temporary directory sphinx_test_tempdir
    srcdir = builder_params.get("srcdir")
    src_dir = copy_srcdir_to_tmpdir(srcdir, sphinx_test_tempdir)

    # return sphinx.testing fixture make_app and new srcdir which in sphinx_test_tempdir
    app = make_app(
        buildername=builder_params.get("buildername", "html"),
        srcdir=src_dir,
        freshenv=builder_params.get("freshenv"),
        confoverrides=builder_params.get("confoverrides"),
        status=builder_params.get("status"),
        warning=builder_params.get("warning"),
        tags=builder_params.get("tags"),
        docutilsconf=builder_params.get("docutilsconf"),
        parallel=builder_params.get("parallel", 0),
    )

    yield app

    # cleanup test temporary directory
    shutil.rmtree(sphinx_test_tempdir, False)


@pytest.fixture
def clean_docutils_registry():
    """Start a build from docutils' own registries, with nothing of Sphinx's in them.

    For tests that assert an EMPTY warning stream. Some modules of this suite build with a
    bare ``Sphinx(...)`` (``test_cli_convert.py``, ``test_project_config.py``), which
    registers Sphinx's directives, roles and node classes with docutils and never takes
    them back; the next app built in the same worker then warns ``directive
    'version-deprecated' is already registered`` / ``node class 'toctree' is already
    registered``, once per name. Emptying the two lookup tables and unregistering the
    nodes is what ``sphinx.util.docutils.docutils_namespace`` undoes when an app is cleaned
    up (docutils loads its own directives and roles back from its static registries on
    first use). Request it BEFORE ``test_app`` when using both.
    """
    directives._directives.clear()
    roles._roles.clear()
    for node in list(additional_nodes):
        unregister_node(node)
        additional_nodes.discard(node)


#: The title ``build_page`` puts above its ``rst``: the first line of ``rst`` is line 4.
PAGE_TITLE = "Probe\n=====\n\n"


@pytest.fixture
def build_page(make_app, tmp_path, clean_docutils_registry):
    """Build a one-page project in ``tmp_path``; return ``(app, warning stream text)``.

    ``index.rst`` is :data:`PAGE_TITLE` then ``rst``. ``files`` (name -> bytes) are written
    next to it AS BYTES -- a parser's line, column or byte offset is a claim about the
    bytes, on every platform. ``conf`` is appended to a ``conf.py`` that loads
    sphinx-needs and this extension; ``confoverrides`` go to the app.
    """

    def build(rst, files=None, confoverrides=None, conf=""):
        src = tmp_path / "src"
        src.mkdir()
        (src / "conf.py").write_text(
            'extensions = ["sphinx_needs", "sphinx_test_reports"]\n' + conf,
            encoding="utf-8",
        )
        (src / "index.rst").write_text(PAGE_TITLE + rst, encoding="utf-8")
        for name, data in (files or {}).items():
            (src / name).write_bytes(data)
        warning = io.StringIO()
        app = make_app(
            "html",
            srcdir=src,
            warning=warning,
            confoverrides=confoverrides or {},
            freshenv=True,
        )
        app.build()
        return app, warning.getvalue()

    return build
