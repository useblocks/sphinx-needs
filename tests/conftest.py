"""Pytest conftest module containing common test configuration and fixtures."""
import shutil

import pytest
from sphinx.testing.path import path

pytest_plugins = "sphinx.testing.fixtures"


def copy_srcdir_to_tmpdir(srcdir, tmp):
    srcdir = path(__file__).parent.abspath() / srcdir
    tmproot = tmp / path(srcdir).basename()
    shutil.copytree(srcdir, tmproot)
    return tmproot


def clean_up_tmpdir(targetdir):
    shutil.rmtree(targetdir, True)


@pytest.fixture()
def create_app(make_app, sphinx_test_tempdir, srcdir):
    # copy plantuml.jar to current test temdir
    plantuml_jar_file = path(__file__).parent.abspath() / "doc_test/utils"
    shutil.copytree(plantuml_jar_file, sphinx_test_tempdir / "utils")

    # copy test srcdir to test temporary directory sphinx_test_tempdir
    srcdir = copy_srcdir_to_tmpdir(srcdir, sphinx_test_tempdir)

    # return sphinx.testing fixture make_app and new srcdir which in sphinx_test_tempdir
    yield make_app, srcdir

    # cleanup test temporary directory
    clean_up_tmpdir(sphinx_test_tempdir)
