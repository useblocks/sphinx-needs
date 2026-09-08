import json
import os
from pathlib import Path

import pytest
from syrupy.filters import props

from sphinx_needs_testkit import assert_no_warnings


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "needs", "srcdir": "doc_test/doc_needs_builder"}],
    indirect=True,
)
def test_doc_needs_builder(test_app, snapshot):
    app = test_app
    app.build()

    needs_list = json.loads(Path(app.outdir, "needs.json").read_text())
    assert needs_list == snapshot(exclude=props("created", "project", "creator"))


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "needs",
            "srcdir": "doc_test/doc_needs_builder",
            "confoverrides": {"needs_reproducible_json": True},
        }
    ],
    indirect=True,
)
def test_doc_needs_builder_reproducible(test_app, snapshot):
    app = test_app
    app.build()

    needs_list = json.loads(Path(app.outdir, "needs.json").read_text())
    assert needs_list == snapshot(exclude=props("project", "creator"))


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "needs",
            "srcdir": "doc_test/doc_needs_builder",
            "confoverrides": {"needs_json_remove_defaults": True},
        }
    ],
    indirect=True,
)
def test_doc_needs_builder_remove_defaults(test_app, snapshot):
    app = test_app
    app.build()

    needs_list = json.loads(Path(app.outdir, "needs.json").read_text())
    assert needs_list == snapshot(exclude=props("created", "project", "creator"))


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "needs", "srcdir": "doc_test/doc_needs_builder_negative_tests"}],
    indirect=True,
)
def test_doc_needs_build_without_needs_file(test_app):
    app = test_app
    app.build()

    assert_no_warnings(app)
    assert (
        "needs.json found, but will not be used because needs_file not configured."
        in app._status.getvalue()
    )


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "html", "srcdir": "doc_test/doc_needs_builder_parallel"}],
    indirect=True,
)
def test_needs_html_and_json(test_app, make_app):
    """
    Build html output and needs.json in one sphinx-build
    """
    app = test_app
    app.build()

    needs_json_path = os.path.join(app.outdir, "needs.json")
    assert os.path.exists(needs_json_path)

    # the same source, a second time, through the needs builder: its own build
    # directory, so it reads the sources afresh rather than the html build's doctrees
    needs_app = make_app(
        buildername="needs",
        srcdir=app.srcdir,
        builddir=Path(app.srcdir).parent / "needs_build",
    )
    needs_app.build()

    needs_json_path_2 = os.path.join(needs_app.outdir, "needs.json")
    assert os.path.exists(needs_json_path_2)

    # Check if the needs.json files from html/parallel build and builder are the same
    with open(needs_json_path) as f1:
        needs_1 = json.load(f1)
        with open(needs_json_path_2) as f2:
            needs_2 = json.load(f2)

            # Just check need-data, as the rest contains not matching timestamps
            need_data_1 = needs_1["versions"]["1.0"]["needs"]
            need_data_2 = needs_2["versions"]["1.0"]["needs"]
            assert need_data_1 == need_data_2


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "needs", "srcdir": "doc_test/doc_needs_builder_empty"}],
    indirect=True,
)
def test_doc_needs_builder_empty(test_app):
    app = test_app
    app.build()

    needs_list = json.loads(Path(app.outdir, "needs.json").read_text())
    assert "current_version" in needs_list
    assert needs_list["current_version"] == ""

    version = needs_list["current_version"]
    assert "versions" in needs_list
    assert version in needs_list["versions"]
    assert needs_list["versions"][version]["needs_amount"] == 0
    assert needs_list["versions"][version]["needs"] == {}
