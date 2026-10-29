"""A need type's declaration of a link type's back links: ``BackLinksSchema``.

A ``[needs.types.<t>.links.<l>_back]`` entry declares how many links of ``l`` point to
a need of the type (``minItems``, ``maxItems``) and the severity of a need failing the
count. The configuration's behaviour is pinned by the fields-per-type conformance
corpus (section "the count of a link type's back links"); these tests pin the schema
object itself: what a declaration may hold, where it is registered, and which schema
of one need type reads it.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from sphinx_needs.needs_schema import (
    BackLinksSchema,
    FieldsSchema,
    LinkDisplayConfig,
    LinkSchema,
)
from sphinx_needs_testkit import build_warnings


def _schema(*need_types: str) -> FieldsSchema:
    schema = FieldsSchema()
    schema.add_link_field(
        LinkSchema(
            name="satisfies",
            schema={"type": "array", "items": {"type": "string"}},
            display=LinkDisplayConfig(incoming="satisfied by", outgoing="satisfies"),
        )
    )
    if need_types:
        schema.set_need_types(need_types)
    return schema


def _back(**kwargs: Any) -> BackLinksSchema:
    return BackLinksSchema(
        name="satisfies_back", link_type="satisfies", **{"schema": {}, **kwargs}
    )


@pytest.mark.parametrize(
    "schema",
    [
        pytest.param({"uniqueItems": True}, id="another-keyword"),
        pytest.param({"minItems": -1}, id="negative"),
        pytest.param({"minItems": True}, id="a-boolean"),
        pytest.param({"maxItems": 1.0}, id="a-float"),
    ],
)
def test_a_count_is_min_items_and_max_items(schema: dict[str, Any]) -> None:
    """Only ``minItems`` and ``maxItems``, each a non-negative integer."""
    with pytest.raises(ValueError, match="schema must give only 'minItems'"):
        _back(schema=schema)


def test_a_declaration_names_its_link_types_back_links() -> None:
    with pytest.raises(ValueError, match="name must be the link type's name"):
        BackLinksSchema(name="satisfies", link_type="satisfies", schema={})


def test_a_declaration_takes_a_severity_of_three() -> None:
    with pytest.raises(ValueError, match="severity must be one of"):
        _back(severity="error")
    assert _back().failure_severity == "violation"
    assert _back(severity="info").failure_severity == "info"


def test_its_json_schema_is_a_list_of_ids_counted() -> None:
    assert _back(schema={"minItems": 1, "maxItems": 2}).json_schema() == {
        "type": "array",
        "items": {"type": "string"},
        "minItems": 1,
        "maxItems": 2,
    }


def test_the_schema_of_its_need_type_reads_it() -> None:
    """A need type that declares only a count of back links (no overlay) has a schema
    of its own, which reads the count; the global view and every other type read none."""
    schema = _schema("req", "spec")
    back = _back(schema={"minItems": 1})
    schema.add_back_links("req", back)
    schema.freeze()
    assert dict(schema.for_type("req").back_links()) == {"satisfies_back": back}
    assert schema.for_type("req") is not schema.for_type(None)
    assert dict(schema.for_type("spec").back_links()) == {}
    assert dict(schema.for_type(None).back_links()) == {}
    assert dict(schema.back_links()) == {}


@pytest.mark.parametrize(
    ("need_type", "back", "message"),
    [
        pytest.param(
            "test",
            _back(),
            "'test' is not a configured need type",
            id="an-unknown-need-type",
        ),
        pytest.param(
            "req",
            BackLinksSchema(name="verifies_back", link_type="verifies", schema={}),
            "there is no link type 'verifies'",
            id="an-unknown-link-type",
        ),
    ],
)
def test_a_declaration_is_refused(
    need_type: str, back: BackLinksSchema, message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        _schema("req").add_back_links(need_type, back)


def test_a_frozen_schema_takes_no_declaration() -> None:
    schema = _schema("req")
    schema.freeze()
    with pytest.raises(TypeError, match="cannot be changed once it is complete"):
        schema.add_back_links("req", _back())


def test_a_schema_told_its_types_after_a_declaration_checks_it() -> None:
    schema = _schema()
    schema.add_back_links("req", _back())
    with pytest.raises(ValueError, match="'req' is not a configured need type"):
        schema.set_need_types(["spec"])


UNKNOWN_KEY = """\
[needs.links.satisfies]

[needs.types.req]
title = "Requirement"
prefix = "R_"

[needs.types.req.links.satisfies_back]
schema = { minItems = 1 }
severty = "warning"

[needs.types.req.links.other_back]
bar = 1
"""


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "needs",
            "files": [
                (
                    Path("conf.py"),
                    'extensions = ["sphinx_needs"]\nneeds_from_toml = "ubproject.toml"\n',
                ),
                (Path("ubproject.toml"), UNKNOWN_KEY),
                (Path("index.rst"), "Case\n====\n\n.. req:: A\n   :id: REQ_1\n"),
            ],
        }
    ],
    indirect=True,
)
def test_an_unknown_key_refuses_a_count(test_app: Any) -> None:
    """A key no ``links`` entry has (a misspelt ``severity``) on the entry of a link
    type's back links is one ``needs.type_conflict``, as any key the count does not
    take is, and the entry is ignored whole: its ``minItems`` does not apply, and the
    key is not also reported as an unknown key of a link type's entry (whose keys the
    count does not take either). An entry named ``<x>_back`` where no link type ``x``
    exists declares a link type of its need types alone, and an unknown key of it is
    reported and ignored as on any other ``links`` entry."""
    app = test_app
    app.build()
    assert build_warnings(app) == [
        "WARNING: needs_types['req'].links['other_back'] has an unknown key 'bar'; "
        "known keys are allow_dead_links, color, copy, default, derive, description, "
        "incoming, outgoing, predicates, schema, severity, style, style_end, "
        "style_part, style_start, target_types; the key is ignored [needs.config]",
        "WARNING: needs_types['req'].links['satisfies_back'] sets 'severty', but "
        "'satisfies_back' is a link type's back links: a need type declares only "
        "their description, schema (minItems, maxItems) and severity; the entry is "
        "ignored [needs.type_conflict]",
    ]


NOT_A_COUNT = """\
[needs.types.req]
title = "Requirement"
prefix = "R_"

[needs.types.spec]
title = "Specification"
prefix = "S_"

[needs.types.req.links.zzz_back]
color = 3
copy = "yes"
outgoing = 5
allow_dead_links = "x"
foo = 1
"""

NOT_A_COUNT_STYLE = """\
[needs.types.req]
title = "Requirement"
prefix = "R_"

[needs.types.spec]
title = "Specification"
prefix = "S_"

[needs.types.req.links.zzz_back]
style = 3

[needs.types.spec.links.zzz_back]
style = "dashed"
"""


def _toml_project(toml: str, index: str, buildername: str) -> dict[str, Any]:
    return {
        "buildername": buildername,
        "files": [
            (
                Path("conf.py"),
                'extensions = ["sphinx_needs"]\nneeds_from_toml = "ubproject.toml"\n',
            ),
            (Path("ubproject.toml"), toml),
            (Path("index.rst"), index),
        ],
    }


@pytest.mark.parametrize(
    "test_app",
    [
        _toml_project(
            NOT_A_COUNT,
            "Case\n====\n\n.. req:: A\n   :id: REQ_1\n\n"
            ".. needtable::\n   :columns: id;zzz_back\n",
            "html",
        )
    ],
    indirect=True,
)
def test_a_back_links_name_of_no_link_type_is_checked_as_a_link_type(
    test_app: Any,
) -> None:
    """``zzz_back``, where no link type ``zzz`` exists, is no count: it declares a link
    type of ``req`` alone, so its keys are checked as a link type's entry's are -- the
    keys not of their shape and the unknown ones reported and ignored -- before the
    link type is declared from them: a ``color`` of ``3`` is not its color (the html
    build drawing it does not fail)."""
    app = test_app
    app.build()
    assert build_warnings(app) == [
        "WARNING: needs_types['req'].links['zzz_back'] has an 'outgoing' that is not a "
        "string (got int) and a 'copy' that is not a boolean (got str) and an "
        "'allow_dead_links' that is not a boolean (got str) and a 'color' that is not "
        "a string (got int); the keys are ignored [needs.config]",
        "WARNING: needs_types['req'].links['zzz_back'] has an unknown key 'foo'; "
        "known keys are allow_dead_links, color, copy, default, derive, description, "
        "incoming, outgoing, predicates, schema, severity, style, style_end, "
        "style_part, style_start, target_types; the key is ignored [needs.config]",
    ]


@pytest.mark.parametrize(
    "test_app",
    [
        _toml_project(
            NOT_A_COUNT_STYLE, "Case\n====\n\n.. req:: A\n   :id: REQ_1\n", "needs"
        )
    ],
    indirect=True,
)
def test_a_key_ignored_is_not_a_link_types_shape(test_app: Any) -> None:
    """A ``style`` of ``3`` on the first declaration of ``zzz_back``, a link type of
    need types alone, is reported and ignored, so the link type's style is the default
    one, which a second declaration giving another is refused against."""
    app = test_app
    app.build()
    assert build_warnings(app) == [
        "WARNING: needs_types['req'].links['zzz_back'] has a 'style' that is not a "
        "string (got int); the key is ignored [needs.config]",
        "WARNING: needs_types['spec'].links['zzz_back'] cannot be declared with style "
        "'dashed': its style is '' on every need type, as need type 'req' declares "
        "it; the entry is ignored [needs.type_conflict]",
    ]
