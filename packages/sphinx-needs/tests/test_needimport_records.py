"""``needimport`` and the shapes a needs.json record's keys can take.

A needs.json is not always written by sphinx-needs: a hand-written file, or another
producer, may omit ``tags`` or give a key a value of the wrong type. The schema check
of the file only logs at INFO level, so each record reaches the import as it is: a
record ``needimport`` cannot create is reported as a ``needs.import_need`` warning
naming the need, and skipped, rather than ending the build.

Every project here is built inline (``files``), its needs.json written by the test.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from sphinx.testing.util import SphinxTestApp

from sphinx_needs_testkit import build_warnings
from tests.util import needs_by_id

CONF = """\
extensions = ["myst_parser", "sphinx_needs"]
source_suffix = {".rst": "restructuredtext", ".md": "markdown"}
needs_types = [
    dict(directive="spec", title="Specification", prefix="S_", color="#FEDCD2", style="node"),
]
needs_id_regex = r"^[A-Za-z0-9_]+$"
needs_build_json = True
needs_json_remove_defaults = False
show_warning_types = True
"""
"""A project that parses reStructuredText and MyST: a record's ``doctype`` of ``.md``
is one it can parse content in."""


def needs_json(records: list[dict[str, Any]]) -> str:
    """A needs.json holding ``records`` in its current version, with no schema."""
    needs = {r["id"]: r for r in records}
    return json.dumps({"current_version": "1", "versions": {"1": {"needs": needs}}})


def record(need_id: str, **fields: Any) -> dict[str, Any]:
    """A need record of type ``spec``, whose ``doctype`` is MyST."""
    return {"id": need_id, "type": "spec", "title": need_id, "doctype": ".md", **fields}


def project(records: list[dict[str, Any]], options: list[str]) -> dict[str, Any]:
    """The ``test_app`` parameters of a project importing ``records`` with ``options``
    (``":name: value"`` lines), its directive on line 1 of ``index.rst``."""
    index = "\n".join([".. needimport:: needs.json", *(f"   {o}" for o in options)])
    return {
        "buildername": "html",
        "files": [
            (Path("conf.py"), CONF),
            (Path("needs.json"), needs_json(records)),
            (Path("index.rst"), index + "\n"),
        ],
    }


ROUTES = {
    # route: the directive's options
    "page_markup": [],
    "by_doctype": [":parse_by_doctype: true"],
}
"""The two routes a record's content is parsed on: as the page's markup, and as the
markup its ``doctype`` names."""


def not_imported(need_id: str, message: str) -> str:
    return (
        f"<srcdir>/index.rst:1: WARNING: Need {need_id!r} could not be imported: "
        f"{message} [needs.import_need]"
    )


# ------------------------------------------------------------------------------------
# ``:tags:`` and the record's own ``tags`` (#2132)

TAGS_RECORDS = [
    record("NO_TAGS"),
    record("NULL_TAGS", tags=None),
    record("LIST_TAGS", tags=["x"]),
    record("STR_TAGS", tags="x; y"),
]


@pytest.mark.parametrize(
    ("test_app", "expected"),
    [
        pytest.param(
            project(TAGS_RECORDS, [":tags: a, b"]),
            {
                "NO_TAGS": ["a", "b"],
                "NULL_TAGS": ["a", "b"],
                "LIST_TAGS": ["x", "a", "b"],
                "STR_TAGS": ["x", "y", "a", "b"],
            },
            id="tags_option",
        ),
        pytest.param(
            project(TAGS_RECORDS, []),
            {
                "NO_TAGS": [],
                "NULL_TAGS": [],
                "LIST_TAGS": ["x"],
                "STR_TAGS": ["x", "y"],
            },
            id="no_tags_option",
        ),
    ],
    indirect=["test_app"],
)
def test_tags_option_extends_the_record_tags(
    test_app: SphinxTestApp, expected: dict[str, list[str]]
) -> None:
    """``:tags:`` is added to each record's own ``tags``, whatever shape they have:
    absent or ``null`` are none, a list is extended, and a string is split as the
    option itself is. Without the option, each record keeps its own (the control:
    ``add_need`` splits a string of tags the same way)."""
    test_app.build()
    assert test_app.statuscode == 0
    assert build_warnings(test_app) == []
    assert {k: v["tags"] for k, v in needs_by_id(test_app).items()} == expected


# ------------------------------------------------------------------------------------
# a record whose ``content`` is not a string (#2147)


@pytest.mark.parametrize(
    "test_app",
    [
        pytest.param(
            project(
                [
                    record("INT_CONTENT", content=5),
                    record("NULL_CONTENT", content=None),
                    record("NULL_DESCRIPTION", description=None),
                    record("STR_CONTENT", content="Imported content."),
                ],
                options,
            ),
            id=route,
        )
        for route, options in ROUTES.items()
    ],
    indirect=True,
)
def test_content_not_a_string_is_not_imported(test_app: SphinxTestApp) -> None:
    """A ``content`` (or a legacy ``description`` taken as it) that is not a string is
    reported, naming the need, and the need skipped; the file's other needs import."""
    test_app.build()
    assert test_app.statuscode == 0
    assert build_warnings(test_app) == [
        not_imported("INT_CONTENT", "content must be a string, not int"),
        not_imported("NULL_CONTENT", "content must be a string, not NoneType"),
        not_imported("NULL_DESCRIPTION", "content must be a string, not NoneType"),
    ]
    needs = needs_by_id(test_app)
    assert list(needs) == ["STR_CONTENT"]
    assert needs["STR_CONTENT"]["content"] == "Imported content."


@pytest.mark.parametrize(
    "test_app",
    [
        pytest.param(project([record("NO_CONTENT")], options), id=route)
        for route, options in ROUTES.items()
    ],
    indirect=True,
)
def test_record_without_content_imports_empty(test_app: SphinxTestApp) -> None:
    """A record with no ``content`` key at all is a need with empty content."""
    test_app.build()
    assert test_app.statuscode == 0
    assert build_warnings(test_app) == []
    needs = needs_by_id(test_app)
    assert list(needs) == ["NO_CONTENT"]
    assert needs["NO_CONTENT"]["content"] == ""


# ------------------------------------------------------------------------------------
# a record whose ``type`` is not a string


@pytest.mark.parametrize(
    "test_app",
    [
        pytest.param(
            project(
                [
                    record("INT_TYPE", type=5),
                    record("NULL_TYPE", type=None),
                    record("LIST_TYPE", type=["spec"]),
                    record("DICT_TYPE", type={}),
                    record("STR_TYPE"),
                ],
                [],
            ),
            id="page_markup",
        )
    ],
    indirect=True,
)
def test_type_not_a_string_is_not_imported(test_app: SphinxTestApp) -> None:
    """A ``type`` that is not a string is reported, naming the need, and the need
    skipped; the file's other needs import."""
    test_app.build()
    assert test_app.statuscode == 0
    assert build_warnings(test_app) == [
        not_imported("INT_TYPE", "type must be a string, not int"),
        not_imported("NULL_TYPE", "type must be a string, not NoneType"),
        not_imported("LIST_TYPE", "type must be a string, not list"),
        not_imported("DICT_TYPE", "type must be a string, not dict"),
    ]
    assert list(needs_by_id(test_app)) == ["STR_TYPE"]
