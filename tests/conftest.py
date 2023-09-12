"""Pytest conftest module containing common test configuration and fixtures."""
import shutil
from tempfile import mkdtemp

import pytest
from docutils.nodes import document
from sphinx.testing.path import path
from syrupy.extensions.single_file import SingleFileSnapshotExtension, WriteMode

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

    # copy plantuml.jar to current test temdir
    plantuml_jar_file = path(__file__).parent.abspath() / "doc_test/utils"
    shutil.copytree(plantuml_jar_file, sphinx_test_tempdir / "utils")

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


class DoctreeSnapshotExtension(SingleFileSnapshotExtension):
    _write_mode = WriteMode.TEXT
    _file_extension = "doctree.xml"

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
    return snapshot.with_defaults(extension_class=DoctreeSnapshotExtension)
