import json
import os
from pathlib import Path

import pytest
from syrupy.filters import props

from sphinx_needs.data import NeedsCoreFields
from sphinx_needs_testkit import assert_no_warnings
from ub_needs_exchange import parse


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


CONF_NARROWED_CORE_FIELD = """\
extensions = ["sphinx_needs"]
needs_reproducible_json = True
needs_fields = {
    "status": {
        "schema": {"type": "string", "enum": ["open", "closed"]},
        "nullable": False,
        "default": "open",
    },
}
"""

INDEX_NARROWED_CORE_FIELD = """\
Test
====

.. req:: Closed
   :id: REQ_001
   :status: closed

.. req:: Unset
   :id: REQ_002

.. req:: Open
   :id: REQ_003
   :status: open
"""


def _current(needs_list: dict) -> dict:
    return needs_list["versions"][needs_list["current_version"]]


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "needs",
            "files": [
                (Path("conf.py"), CONF_NARROWED_CORE_FIELD),
                (Path("index.rst"), INDEX_NARROWED_CORE_FIELD),
            ],
        }
    ],
    indirect=True,
)
def test_narrowed_core_field_in_needs_schema(test_app):
    """A core field a ``needs_fields`` entry narrows is written into ``needs_schema``
    as the project declares it, as an extra field is (:issue:`2263`).

    The block was copied from the core field's built-in schema, so the file declared
    ``status`` nullable with a ``null`` default while the project refused ``null``
    and gave every unset need ``"open"``. The projection is the one extras are
    written with: the type (with ``null`` where nullable), the item type, the
    default; the ``enum`` is not written, for a core field as for an extra.
    """
    app = test_app
    app.build()
    assert_no_warnings(app)

    version = _current(json.loads(Path(app.outdir, "needs.json").read_text()))
    properties = version["needs_schema"]["properties"]
    assert properties["status"] == {
        "type": "string",
        "default": "open",
        "description": NeedsCoreFields["status"]["description"],
        "field_type": "core",
    }
    # a core field the project does not narrow is written as before
    assert properties["tags"] == {
        "type": "array",
        "items": {"type": "string"},
        "default": [],
        "description": NeedsCoreFields["tags"]["description"],
        "field_type": "core",
    }
    # as is one that is not in the fields schema at all
    assert properties["docname"] == {
        **NeedsCoreFields["docname"]["schema"],
        "description": NeedsCoreFields["docname"]["description"],
        "field_type": "core",
    }
    assert {i: n["status"] for i, n in version["needs"].items()} == {
        "REQ_001": "closed",
        "REQ_002": "open",
        "REQ_003": "open",
    }


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "needs",
            "files": [
                (Path("conf.py"), CONF_NARROWED_CORE_FIELD),
                (Path("index.rst"), INDEX_NARROWED_CORE_FIELD),
            ],
            "confoverrides": {"needs_json_remove_defaults": True},
        }
    ],
    indirect=True,
)
def test_narrowed_core_field_default_round_trips(test_app):
    """Under ``needs_json_remove_defaults``, a value equal to a narrowed core field's
    default is left out, and a reader restores it from the file's own ``needs_schema``
    (:issue:`2263`).

    Before, the file's default was the built-in ``null``, so ``"open"`` was always
    written: nothing was lost, but nothing was left out either.
    """
    app = test_app
    app.build()
    assert_no_warnings(app)

    text = Path(app.outdir, "needs.json").read_text()
    written = _current(json.loads(text))["needs"]
    assert {i: n.get("status", "<left out>") for i, n in written.items()} == {
        "REQ_001": "closed",
        "REQ_002": "<left out>",
        "REQ_003": "<left out>",
    }

    # the one reader needimport and needs_external_needs read the file through
    records = parse(text).select_version(None).records()
    assert {r.key: r.fields["status"] for r in records} == {
        "REQ_001": "closed",
        "REQ_002": "open",
        "REQ_003": "open",
    }
