"""needs.json's ``needs_schema`` gives a link type's literal default (#2208).

The schema block wrote ``"default": []`` for every link type but one derived by type
alone, also for one declared with a literal default: an importer reading the schema
took the wrong value for an absent link list. It now writes the literal default of
every link type that is not derived, as link strings, sorted and deduplicated as a
written link list. A default computed by a dynamic function or a variant has no value
the schema can give, and stays ``[]``; a need type's own default is not the global one,
and is not written.

Under ``needs_json_remove_defaults`` a need holding that default now leaves it out, and
a reader restores it from the schema.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from sphinx_needs_testkit import build_warnings
from ub_needs_exchange import load

CONF = """\
extensions = ["sphinx_needs"]
needs_from_toml = "ubproject.toml"
"""

TOML = """\
[needs]
build_json = true
{extra}

[needs.links.rel]
default = ["REQ_1", "REQ_0", "REQ_1"]

[needs.links.links]
default = ["REQ_0"]

[needs.links.dyn]
default = "[[copy('id')]]"

[needs.links.derived]
derive = {{ kind = "links", where = "id == 'REQ_0'" }}

[needs.types.req]
title = "Requirement"
prefix = "R_"

[needs.types.spec]
title = "Specification"
prefix = "S_"

[needs.types.spec.links.rel]
default = ["REQ_0"]
"""

INDEX = """\
Case
====

.. req:: Target
   :id: REQ_0

.. req:: Takes the defaults
   :id: REQ_1

.. spec:: Takes its type's default
   :id: SPEC_1

.. req:: Sets its own
   :id: REQ_2
   :rel: REQ_0
   :links: REQ_1
"""


def _project(extra: str = "") -> dict[str, Any]:
    return {
        "buildername": "html",
        "files": [
            (Path("conf.py"), CONF),
            (Path("ubproject.toml"), TOML.format(extra=extra)),
            (Path("index.rst"), INDEX),
        ],
    }


def _version(app: Any) -> dict[str, Any]:
    data = json.loads(Path(app.outdir, "needs.json").read_text(encoding="utf-8"))
    return data["versions"][data["current_version"]]


@pytest.mark.parametrize("test_app", [_project()], indirect=True)
def test_the_schema_gives_a_link_types_literal_default(test_app: Any) -> None:
    """The literal default, deduplicated and sorted as the needs hold it; the default
    ``links`` too; ``[]`` for a dynamic default and for a derived link type; the global
    default where a need type declares its own."""
    app = test_app
    app.build()
    assert build_warnings(app) == []
    version = _version(app)
    properties = version["needs_schema"]["properties"]
    assert {
        name: properties[name]["default"]
        for name in ("rel", "links", "dyn", "derived", "rel_back")
    } == {
        "rel": ["REQ_0", "REQ_1"],
        "links": ["REQ_0"],
        "dyn": [],
        "derived": [],
        "rel_back": [],
    }
    needs = version["needs"]
    # the default as the needs hold it
    assert needs["REQ_1"]["rel"] == properties["rel"]["default"]
    assert needs["SPEC_1"]["rel"] == ["REQ_0"]
    assert needs["REQ_1"]["dyn"] == ["REQ_1"]


@pytest.mark.parametrize(
    "test_app", [_project("json_remove_defaults = true")], indirect=True
)
def test_a_link_default_left_out_is_restored_from_the_schema(test_app: Any) -> None:
    """Under ``needs_json_remove_defaults`` a need holding a link type's default leaves
    it out, where it was written because the schema said ``[]``; a reader restores it
    from the file's own schema, so the records read are the needs as built. A need
    holding its type's default, or links of its own, writes them."""
    app = test_app
    app.build()
    assert build_warnings(app) == []
    written = _version(app)["needs"]
    assert "rel" not in written["REQ_0"]
    assert "rel" not in written["REQ_1"]
    assert "links" not in written["REQ_1"]
    assert written["SPEC_1"]["rel"] == ["REQ_0"]
    assert (written["REQ_2"]["rel"], written["REQ_2"]["links"]) == (
        ["REQ_0"],
        ["REQ_1"],
    )
    document = load(Path(app.outdir, "needs.json"))
    records = {
        record.key: record.fields for record in document.select_version(None).records()
    }
    assert {key: fields["rel"] for key, fields in records.items()} == {
        "REQ_0": ["REQ_0", "REQ_1"],
        "REQ_1": ["REQ_0", "REQ_1"],
        "SPEC_1": ["REQ_0"],
        "REQ_2": ["REQ_0"],
    }
    assert records["REQ_1"]["links"] == ["REQ_0"]
