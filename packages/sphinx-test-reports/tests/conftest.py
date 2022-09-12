"""Pytest conftest module containing common test configuration and fixtures."""
import shutil
from tempfile import mkdtemp

import pytest
from sphinx.testing.path import path

pytest_plugins = "sphinx.testing.fixtures"


def copy_srcdir_to_tmpdir(srcdir, tmp):
    srcdir = path(__file__).parent.abspath() / srcdir
    tmproot = tmp / path(srcdir).basename()
    shutil.copytree(srcdir, tmproot)
    return tmproot


@pytest.fixture(scope="function")
def test_app(make_app, request):
    # We create a temp-folder on our own, as the util-functions from sphinx and pytest make troubles.
    # It seems like they reuse certain-temp names
    sphinx_test_tempdir = path(mkdtemp())

    builder_params = request.param

    # copy plantuml.jar, xml files and json files to current test temdir
    util_files = path(__file__).parent.abspath() / "doc_test/utils"
    shutil.copytree(util_files, sphinx_test_tempdir / "utils")

    # copy test srcdir to test temporary directory sphinx_test_tempdir
    srcdir = builder_params.get("srcdir", None)
    src_dir = copy_srcdir_to_tmpdir(srcdir, sphinx_test_tempdir)

    # return sphinx.testing fixture make_app and new srcdir which in sphinx_test_tempdir
    app = make_app(
        buildername=builder_params.get("buildername", "html"),
        srcdir=src_dir,
        freshenv=builder_params.get("freshenv", None),
        confoverrides=builder_params.get("confoverrides", None),
        status=builder_params.get("status", None),
        warning=builder_params.get("warning", None),
        tags=builder_params.get("tags", None),
        docutilsconf=builder_params.get("docutilsconf", None),
        parallel=builder_params.get("parallel", 0),
    )

    yield app

    # cleanup test temporary directory
    shutil.rmtree(sphinx_test_tempdir, False)
