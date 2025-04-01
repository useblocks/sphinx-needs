"""Pytest conftest module containing common test configuration and fixtures."""

import shutil
from pathlib import Path
from tempfile import mkdtemp

import pytest
from packaging.version import Version
from sphinx import __version__ as sphinx_version

if Version(sphinx_version) < Version("7.2"):
    from sphinx.testing.path import path


pytest_plugins = "sphinx.testing.fixtures"


def copy_srcdir_to_tmpdir(srcdir, tmp):
    srcdir = Path(__file__).parent.absolute() / srcdir
    tmproot = tmp / Path(srcdir).name
    shutil.copytree(srcdir, tmproot)
    return (
        tmproot
        if Version(sphinx_version) >= Version("7.2")
        else path(tmproot.absolute())
    )


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
