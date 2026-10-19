"""The ``fingerprint`` derive kind: the whole need, digested for change detection.

A ``fingerprint`` rule computes the lowercase hex SHA-256 of one compact JSON object with
sorted keys: ``id``, ``type``, ``title``, ``status``, ``tags``, ``content``, every field
the project declares and every link type, neither derived (``parent_needs`` aside), each
entering only where the need's value differs from the field's default -- compared as
JSON text. The corpus (``fixtures/derive_conformance.toml``) pins the byte format with
the hexes ubCode computes too; the tests here pin the rest of the contract: how the rule
is read, which names it includes, the edges of the entry rule, and the needs it does
not run on.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from sphinx_needs.data import SphinxNeedsData
from sphinx_needs.derive import (
    NO_DEFAULT,
    DeriveInvalid,
    DeriveRule,
    check_derive_rules,
    fingerprint_names,
    parse_derive,
)
from sphinx_needs.needs_schema import (
    FieldLiteralValue,
    FieldSchema,
    FieldsSchema,
    LinkDisplayConfig,
    LinkSchema,
    LinksLiteralValue,
)
from sphinx_needs_testkit import build_warnings

#: the names sphinx-needs gives every need without a project declaring them: the
#: needgantt fields and the services' fields
IMPLICIT_EXTRAS = (
    "duration",
    "completion",
    "query",
    "specific",
    "max_amount",
    "max_content_lines",
    "id_prefix",
    "user",
    "created_at",
    "updated_at",
    "closed_at",
    "service",
    "url",
    "avatar",
)


def _needs(app: Any) -> dict[str, dict[str, Any]]:
    data = json.loads(Path(app.outdir, "needs.json").read_text(encoding="utf-8"))
    return data["versions"][data["current_version"]]["needs"]


def _warnings(app: Any) -> list[str]:
    """The build's warnings, but for the deprecation of ``needs_extra_options``."""
    return [w for w in build_warnings(app) if not w.endswith("[needs.deprecated]")]


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _project(conf: str, index: str, **files: str) -> dict[str, Any]:
    return {
        "buildername": "needs",
        "files": [
            (Path("conf.py"), conf),
            (Path("index.rst"), index),
            *((Path(name), text) for name, text in files.items()),
        ],
    }


# -- reading the rule ------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw,expected",
    [
        pytest.param(
            {"kind": "fingerprint"}, DeriveRule(kind="fingerprint"), id="bare"
        ),
        pytest.param(
            {"kind": "fingerprint", "exclude": []},
            DeriveRule(kind="fingerprint"),
            id="exclude-nothing",
        ),
        pytest.param(
            {"kind": "fingerprint", "exclude": ["id", "status"]},
            DeriveRule(kind="fingerprint", exclude=("id", "status")),
            id="exclude",
        ),
    ],
)
def test_a_fingerprint_rule_is_read(raw, expected):
    """``exclude`` is the one role, and optional; an empty list leaves nothing out. The
    rule runs in the late step, as ``hash`` does, without ``after``."""
    rule = parse_derive(raw, on_link=False)
    assert rule == expected
    assert isinstance(rule, DeriveRule)
    assert rule.late
    assert not rule.link_valued


_EXCLUDE_TYPE = "kind 'fingerprint': the role 'exclude' must be a list of field names"


@pytest.mark.parametrize(
    "raw,on_link,kind,reason",
    [
        pytest.param(
            {"kind": "fingerprint", "exclude": "id"},
            False,
            "fingerprint",
            _EXCLUDE_TYPE,
            id="exclude-a-string",
        ),
        pytest.param(
            {"kind": "fingerprint", "exclude": ["id", ""]},
            False,
            "fingerprint",
            _EXCLUDE_TYPE,
            id="exclude-a-blank-name",
        ),
        pytest.param(
            {"kind": "fingerprint", "exclude": ["id", 1]},
            False,
            "fingerprint",
            _EXCLUDE_TYPE,
            id="exclude-not-a-name",
        ),
        pytest.param(
            {"kind": "fingerprint", "exclude": ["status", "id", "status"]},
            False,
            "fingerprint",
            "kind 'fingerprint': the role 'exclude' names 'status' twice",
            id="exclude-twice",
        ),
        pytest.param(
            {"kind": "fingerprint", "fields": ["title"]},
            False,
            "fingerprint",
            "kind 'fingerprint' does not take the role 'fields'",
            id="fields",
        ),
        pytest.param(
            {"kind": "fingerprint", "after": "derived"},
            False,
            "fingerprint",
            "kind 'fingerprint' does not take the role 'after'",
            id="after",
        ),
        pytest.param(
            {"kind": "hash", "fields": ["title"], "exclude": ["id"]},
            False,
            "hash",
            "kind 'hash' does not take the role 'exclude'",
            id="exclude-on-hash",
        ),
        pytest.param(
            {"kind": "fingerprint"},
            True,
            "fingerprint",
            "kind 'fingerprint' computes a value, so it is declared on a field "
            "(needs_fields), not on a link type",
            id="on-a-link-type",
        ),
        # one problem per rule, the first in the order the problems are looked for:
        # unknown role, side, role not taken, role value, a name twice
        pytest.param(
            {"kind": "fingerprint", "join": {"field": "title", "equals": "title"}},
            False,
            "fingerprint",
            "kind 'fingerprint' does not take the role 'join'",
            id="join-not-taken",
        ),
        pytest.param(
            {"kind": "fingerprint", "nope": 1, "fields": ["title"]},
            False,
            "fingerprint",
            "kind 'fingerprint': 'nope' is not a role",
            id="first-unknown-role",
        ),
        pytest.param(
            {"kind": "fingerprint", "fields": ["title"]},
            True,
            "fingerprint",
            "kind 'fingerprint' computes a value, so it is declared on a field "
            "(needs_fields), not on a link type",
            id="first-side",
        ),
        pytest.param(
            {"kind": "fingerprint", "exclude": "id", "after": "derived"},
            False,
            "fingerprint",
            "kind 'fingerprint' does not take the role 'after'",
            id="first-role-not-taken",
        ),
        pytest.param(
            {"kind": "fingerprint", "exclude": ["id", "id", 1]},
            False,
            "fingerprint",
            _EXCLUDE_TYPE,
            id="first-role-value",
        ),
    ],
)
def test_a_fingerprint_rule_is_refused(raw, on_link, kind, reason):
    """Each shape of a rule that cannot be read is one marker, with why."""
    assert parse_derive(raw, on_link=on_link) == DeriveInvalid(kind, reason)


def _link(name: str, **kwargs: Any) -> LinkSchema:
    return LinkSchema(
        name=name,
        schema={"type": "array", "items": {"type": "string"}},
        display=LinkDisplayConfig(incoming=f"{name} in", outgoing=name),
        **kwargs,
    )


def _schema(*rules: tuple[str, dict[str, Any], str]) -> FieldsSchema:
    """A schema like the one a build makes: the core ``status`` and ``tags``, two
    project fields, one field an extension registers, a derived field, the link types
    ``links`` and ``parent_needs``, and one fingerprint field per rule given."""
    schema = FieldsSchema()
    schema.add_core_field(
        FieldSchema(
            name="status", schema={"type": "string"}, nullable=True, allow_defaults=True
        )
    )
    schema.add_core_field(
        FieldSchema(
            name="tags",
            schema={"type": "array", "items": {"type": "string"}},
            default=FieldLiteralValue([]),
            allow_defaults=True,
        )
    )
    schema.add_extra_field(
        FieldSchema(name="owner", schema={"type": "string"}, nullable=True),
        project=True,
    )
    schema.add_extra_field(
        FieldSchema(
            name="prio",
            schema={"type": "string"},
            default=FieldLiteralValue("low"),
            allow_defaults=True,
        ),
        project=True,
    )
    schema.add_extra_field(
        FieldSchema(name="ext_result", schema={"type": "string"}, nullable=True)
    )
    schema.add_extra_field(
        FieldSchema(
            name="total",
            schema={"type": "integer"},
            nullable=True,
            derive=DeriveRule(kind="count", over="links"),
        ),
        project=True,
    )
    for name, raw, type_ in rules:
        rule = parse_derive(raw, on_link=False)
        schema.add_extra_field(
            FieldSchema(name=name, schema={"type": type_}, nullable=True, derive=rule),
            project=True,
        )
    schema.add_link_field(_link("links", default=LinksLiteralValue([])))
    schema.add_link_field(_link("parent_needs", default=LinksLiteralValue([])))
    return schema


def test_the_names_a_fingerprint_includes():
    """The six core names, the project's fields and link types, none derived, with the
    default each is compared against: none for ``id``, ``type`` and ``title``, ``""``
    for ``content``, a literal default, else ``None`` for a nullable field.

    Never the field an extension registers (``ext_result``), a derived field (``total``,
    the fingerprint itself), nor ``parent_needs``.
    """
    schema = _schema(("fp", {"kind": "fingerprint"}, "string"))
    assert fingerprint_names(schema) == {
        "id": NO_DEFAULT,
        "type": NO_DEFAULT,
        "title": NO_DEFAULT,
        "status": None,
        "tags": [],
        "content": "",
        "owner": None,
        "prio": "low",
        "links": [],
    }


@pytest.mark.parametrize(
    "exclude,reason",
    [
        pytest.param(
            ["nope"],
            "the role 'exclude' names 'nope', which is not a field or a link type",
            id="unknown",
        ),
        *(
            pytest.param(
                [name],
                f"the role 'exclude' names {name!r}, which a fingerprint never includes",
                id=f"never-{name}",
            )
            for name in (
                "docname",
                "lineno",
                "layout",
                "is_external",
                "parts",
                "constraints",
                "parent_needs",
                "parent_need",
                "links_back",
                "total",
                "fp_other",
                "ext_result",
            )
        ),
        # the names in the order listed: the first that cannot be excluded
        pytest.param(
            ["status", "docname", "nope"],
            "the role 'exclude' names 'docname', which a fingerprint never includes",
            id="first-in-order",
        ),
    ],
)
def test_exclude_names_what_a_fingerprint_includes(exclude, reason):
    """``exclude`` may name only what the fingerprint includes: a name that is nothing a
    need has, and one a fingerprint never includes (a location, presentation,
    bookkeeping, ``parts``, ``constraints``, ``parent_needs``, back links, a derived
    field, another fingerprint, a field an extension registers), are told apart."""
    schema = _schema(
        ("fp", {"kind": "fingerprint", "exclude": exclude}, "string"),
        ("fp_other", {"kind": "fingerprint"}, "string"),
    )
    problems = check_derive_rules(schema)
    assert [(p.name, p.reason) for p in problems] == [
        ("fp", f"kind 'fingerprint': {reason}")
    ]


def test_exclude_may_name_every_name_a_fingerprint_includes():
    schema = _schema(
        (
            "fp",
            {
                "kind": "fingerprint",
                "exclude": [*fingerprint_names(_schema())],
            },
            "string",
        )
    )
    assert check_derive_rules(schema) == []


@pytest.mark.parametrize("type_", ["integer", "number", "boolean"])
def test_a_fingerprint_gives_a_string(type_):
    schema = _schema(("fp", {"kind": "fingerprint"}, type_))
    assert [p.reason for p in check_derive_rules(schema)] == [
        f"kind 'fingerprint' gives a string, which the field's schema ({type_}) "
        "cannot hold"
    ]


# -- the entry rule ----------------------------------------------------------------------

ENTRY_CONF = """\
extensions = ["sphinx_needs"]
needs_build_json = True
needs_extra_options = ["legacy"]
needs_links = {"covers": {"default": ["REQ_10", "REQ_9", "REQ_9"]}}
needs_fields = {
    "owner": {"schema": {"type": "string"}},
    "done": {"schema": {"type": "boolean"}},
    "points": {"schema": {"type": "integer"}},
    "labels": {"schema": {"type": "array", "items": {"type": "string"}}},
    "prio": {"schema": {"type": "string"}, "default": "low"},
    "zero": {"schema": {"type": "number"}, "default": 0.0},
    "one": {"schema": {"type": "number"}, "default": 1},
    "dyn": {"schema": {"type": "string"}, "default": "[[copy('id')]]"},
    "fp": {"schema": {"type": "string"}, "derive": {"kind": "fingerprint"}},
}
"""

ENTRY_INDEX = """\
Entry
=====

.. req:: Nine
   :id: REQ_9
   :status: open

.. req:: Ten
   :id: REQ_10

.. req:: Defaults written out
   :id: REQ_1
   :prio: low
   :zero: 0
   :one: 1
   :covers: REQ_10, REQ_9[status == 'open']

.. req:: Empty values
   :id: REQ_2
   :owner:
   :done: false
   :points: 0
   :labels:
   :legacy: x
   :zero: -0.0
   :covers: REQ_9
"""

#: the JSON text each need's fingerprint is the SHA-256 of, written out by hand
ENTRY_TEXTS = {
    "REQ_9": '{"dyn":"REQ_9","id":"REQ_9","status":"open","title":"Nine","type":"req"}',
    "REQ_10": '{"dyn":"REQ_10","id":"REQ_10","title":"Ten","type":"req"}',
    "REQ_1": '{"dyn":"REQ_1","id":"REQ_1","title":"Defaults written out","type":"req"}',
    "REQ_2": (
        '{"covers":["REQ_9"],"done":false,"dyn":"REQ_2","id":"REQ_2","labels":[],'
        '"legacy":"x","owner":"","points":0,"title":"Empty values","type":"req",'
        '"zero":-0.0}'
    ),
}


@pytest.mark.parametrize("test_app", [_project(ENTRY_CONF, ENTRY_INDEX)], indirect=True)
def test_a_name_enters_where_it_differs_from_its_default(test_app):
    """The entry rule, edge by edge, the default compared as JSON text:

    - a value written equal to its default enters no more than an unset one (``REQ_1``:
      ``prio``, ``zero`` written ``0``, ``one`` written ``1``);
    - a number field's integer default (``one = 1``) is a float, as the field's values
      are: the needs leaving it unset (stored ``1``) and ``REQ_1`` (stored ``1.0``)
      agree;
    - ``""``, ``false``, ``0`` and ``[]`` differ from a null default, and a legacy
      extra option's ``"x"`` from its ``""`` (``REQ_2``);
    - ``-0.0`` differs from a default ``0.0``, although Python finds them equal;
    - a default that is a dynamic function is no literal default: ``dyn`` is compared
      against null, so its computed value enters on every need;
    - a link type is compared with its default after both are normalised: written in
      another order, with a condition, it is still the default (``REQ_1``).
    """
    app = test_app
    app.build()
    assert _warnings(app) == []
    needs = _needs(app)
    assert needs["REQ_10"]["one"] == 1
    assert needs["REQ_1"]["one"] == 1.0
    assert needs["REQ_2"]["zero"] == 0.0
    for need_id, text in ENTRY_TEXTS.items():
        assert needs[need_id]["fp"] == _sha256(text), (need_id, text)
    assert set(fingerprint_names(SphinxNeedsData(app.env).get_schema())) == {
        "id",
        "type",
        "title",
        "status",
        "tags",
        "content",
        "legacy",
        "owner",
        "done",
        "points",
        "labels",
        "prio",
        "zero",
        "one",
        "dyn",
        "covers",
        "links",
    }


LIST_DEFAULT_CONF = """\
extensions = ["sphinx_needs"]
needs_build_json = True
needs_fields = {
    "labels": {
        "schema": {"type": "array", "items": {"type": "string"}},
        "nullable": False,
        "default": [],
    },
    "tags": {"default": "[[copy('labels')]]"},
    "fp": {"schema": {"type": "string"}, "derive": {"kind": "fingerprint"}},
}
needs_links = {"covers": {"default": "[[copy('links')]]"}}
"""

LIST_DEFAULT_INDEX = """\
Computed defaults
=================

.. req:: Nothing computed
   :id: REQ_1

.. req:: Computed
   :id: REQ_2
   :labels: a, b
   :links: REQ_1
"""


@pytest.mark.parametrize(
    "test_app", [_project(LIST_DEFAULT_CONF, LIST_DEFAULT_INDEX)], indirect=True
)
def test_a_computed_default_of_a_link_type_or_tags_compares_as_empty(test_app):
    """A default that is a dynamic function or a variant is no literal default; on a
    link type, and on ``tags``, the value is then compared against ``[]``, their empty
    value, not entered always: a need whose computed ``covers`` and ``tags`` are empty
    adds neither (``REQ_1``), one whose computed lists are not adds both (``REQ_2``)."""
    app = test_app
    app.build()
    assert build_warnings(app) == []
    needs = _needs(app)
    assert (needs["REQ_1"]["tags"], needs["REQ_1"]["covers"]) == ([], [])
    assert needs["REQ_1"]["fp"] == _sha256(
        '{"id":"REQ_1","title":"Nothing computed","type":"req"}'
    )
    assert needs["REQ_2"]["fp"] == _sha256(
        '{"covers":["REQ_1"],"id":"REQ_2","labels":["a","b"],"links":["REQ_1"],'
        '"tags":["a","b"],"title":"Computed","type":"req"}'
    )
    names = fingerprint_names(SphinxNeedsData(app.env).get_schema())
    assert (names["tags"], names["covers"]) == ([], [])


# -- what never moves a fingerprint --------------------------------------------------------

BASE_CONF = """\
extensions = ["sphinx_needs"]
needs_build_json = True
needs_fields = {
    "owner": {"schema": {"type": "string"}},
    "fp": {"schema": {"type": "string"}, "derive": {"kind": "fingerprint"}},
}
"""

ADDED_CONF = """\
extensions = ["sphinx_needs"]
needs_build_json = True
needs_extra_options = ["legacy"]
needs_links = {"verifies": {}, "refines": {"default": []}}
needs_fields = {
    "owner": {"schema": {"type": "string"}},
    "fp": {"schema": {"type": "string"}, "derive": {"kind": "fingerprint"}},
    "added_nullable": {"schema": {"type": "integer"}},
    "added_default": {"schema": {"type": "string"}, "default": "zzz"},
    "added_flag": {"schema": {"type": "boolean"}, "nullable": False, "default": False},
    "added_number": {"schema": {"type": "number"}, "default": 2},
    "added_derived": {"schema": {"type": "integer"}, "derive": {"kind": "count", "over": "links"}},
    "added_hash": {"schema": {"type": "string"}, "derive": {"kind": "hash", "fields": ["title"]}},
}
"""

STABLE_INDEX = """\
Stable
======

.. req:: Owned
   :id: REQ_1
   :owner: alice

   Body.

.. spec:: Linked
   :id: SPEC_1
   :links: REQ_1
"""

STABLE_TEXTS = {
    "REQ_1": '{"content":"Body.","id":"REQ_1","owner":"alice","title":"Owned","type":"req"}',
    "SPEC_1": '{"id":"SPEC_1","links":["REQ_1"],"title":"Linked","type":"spec"}',
}


@pytest.mark.parametrize(
    "test_app",
    [
        pytest.param(_project(BASE_CONF, STABLE_INDEX), id="base"),
        pytest.param(_project(ADDED_CONF, STABLE_INDEX), id="added"),
    ],
    indirect=True,
)
def test_declaring_more_moves_no_fingerprint(test_app):
    """Each build gives each need the same fingerprint: declaring a nullable field, a
    field with a default (an integer one in a number field among them), a boolean
    defaulting to false, a legacy extra option, link types, a derived field and a hash
    moves none, as every need leaves the new names at their default."""
    app = test_app
    app.build()
    assert _warnings(app) == []
    needs = _needs(app)
    for need_id, text in STABLE_TEXTS.items():
        assert needs[need_id]["fp"] == _sha256(text), (need_id, text)


EXTENSION_CONF = """\
from sphinx_needs.api import add_extra_option, add_field

extensions = ["sphinx_needs"]
needs_build_json = True
needs_fields = {
    "fp": {"schema": {"type": "string"}, "derive": {"kind": "fingerprint"}},
    "fp_ext": {
        "schema": {"type": "string"},
        "derive": {"kind": "fingerprint", "exclude": ["ext_result"]},
    },
    "fp_gantt": {
        "schema": {"type": "string"},
        "derive": {"kind": "fingerprint", "exclude": ["duration"]},
    },
}


# a configured service registers its fields, url among them
needs_services = {"github-issues": {}}


def setup(app):
    add_field("ext_result", "set by an extension", schema={"type": "string"})
    add_extra_option(app, "ext_legacy")
"""

EXTENSION_INDEX = """\
Extension
=========

.. req:: Registered values
   :id: REQ_1
   :ext_result: passed
   :ext_legacy: x
   :duration: 3
   :completion: 50
   :url: https://example.org
"""


@pytest.mark.parametrize(
    "test_app", [_project(EXTENSION_CONF, EXTENSION_INDEX)], indirect=True
)
def test_registered_fields_never_enter(test_app):
    """A field an extension registers (``add_field``, ``add_extra_option``) and the
    names sphinx-needs gives every need (``duration``, ``completion``, a configured
    service's fields) never enter, set or not; ``exclude`` cannot name one."""
    app = test_app
    app.build()
    assert build_warnings(app) == [
        "WARNING: Invalid derive of field 'fp_ext': kind 'fingerprint': the role "
        "'exclude' names 'ext_result', which a fingerprint never includes; the field "
        "cannot be set in a need or by a needextend, and holds its empty value "
        "[needs.derive_invalid]",
        "WARNING: Invalid derive of field 'fp_gantt': kind 'fingerprint': the role "
        "'exclude' names 'duration', which a fingerprint never includes; the field "
        "cannot be set in a need or by a needextend, and holds its empty value "
        "[needs.derive_invalid]",
    ]
    need = _needs(app)["REQ_1"]
    assert (need["ext_result"], need["duration"], need["url"]) == (
        "passed",
        3,
        "https://example.org",
    )
    names = fingerprint_names(SphinxNeedsData(app.env).get_schema())
    assert not {"ext_result", "ext_legacy", *IMPLICIT_EXTRAS} & set(names)
    assert need["fp"] == _sha256(
        '{"id":"REQ_1","title":"Registered values","type":"req"}'
    )
    assert need["fp_ext"] is None
    assert need["fp_gantt"] is None


# -- final values, and the needs a rule does not run on ------------------------------------

FINAL_CONF = """\
extensions = ["sphinx_needs"]
needs_build_json = True
needs_id_regex = "^[A-Z0-9_]{5,}"
needs_external_needs = [{"base_url": "http://example.org/", "json_path": "external.json"}]
needs_fields = {
    "owner": {"schema": {"type": "string"}, "parse_variants": True},
    "fp": {"schema": {"type": "string"}, "derive": {"kind": "fingerprint"}},
}
"""

FINAL_INDEX = """\
Final
=====

.. req:: Variant and extend
   :id: REQ_1
   :owner: <<[type == 'req']:alice, bob>>
   :tags: a

.. needextend:: REQ_1
   :status: closed
   :+tags: b

.. req:: Hidden
   :id: REQ_H
   :hide:

   Hidden body.

.. req:: Parent
   :id: PARENT_1

   .. req:: Child
      :id: CHILD_1

.. needimport:: imported.json
"""


def _carried(prefix: str, value: str) -> str:
    """A needs.json of two needs: one carrying a fingerprint, one carrying none."""
    return json.dumps(
        {
            "current_version": "1.0",
            "versions": {
                "1.0": {
                    "needs": {
                        f"{prefix}_1": {
                            "id": f"{prefix}_1",
                            "type": "req",
                            "title": "Carried",
                            "fp": value,
                        },
                        f"{prefix}_2": {
                            "id": f"{prefix}_2",
                            "type": "req",
                            "title": "Without",
                        },
                    }
                }
            },
        }
    )


@pytest.mark.parametrize(
    "test_app",
    [
        _project(
            FINAL_CONF,
            FINAL_INDEX,
            **{
                "imported.json": _carried("IMP", "x"),
                "external.json": _carried("EXT", "y"),
            },
        )
    ],
    indirect=True,
)
def test_a_fingerprint_reads_final_values(test_app):
    """A variant's value and a needextend's are read as final (``REQ_1``); a hidden
    need's fingerprint is computed like any other, its content included (``REQ_H``);
    a nested need's ``parent_needs`` never enters (``CHILD_1``); no rule runs on an
    imported or an external need, which keeps the value it carries, or holds null
    (``IMP_*``, ``EXT_*``; ``needs.json`` does not write an external need)."""
    app = test_app
    app.build()
    needs = _needs(app)
    assert needs["REQ_1"]["owner"] == "alice"
    assert needs["REQ_1"]["fp"] == _sha256(
        '{"id":"REQ_1","owner":"alice","status":"closed","tags":["a","b"],'
        '"title":"Variant and extend","type":"req"}'
    )
    assert needs["REQ_H"]["fp"] == _sha256(
        '{"content":"Hidden body.","id":"REQ_H","title":"Hidden","type":"req"}'
    )
    assert needs["CHILD_1"]["parent_needs"] == ["PARENT_1"]
    assert needs["CHILD_1"]["fp"] == _sha256(
        '{"id":"CHILD_1","title":"Child","type":"req"}'
    )
    parent_text = json.dumps(
        {
            "content": needs["PARENT_1"]["content"],
            "id": "PARENT_1",
            "title": "Parent",
            "type": "req",
        },
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    assert ".. req:: Child" in parent_text
    assert needs["PARENT_1"]["fp"] == _sha256(parent_text)
    assert needs["IMP_1"]["fp"] == "x"
    assert needs["IMP_2"]["fp"] is None
    every = SphinxNeedsData(app.env).get_needs_view()
    assert every["EXT_1"]["is_external"]
    assert every["EXT_1"]["fp"] == "y"
    assert every["EXT_2"]["fp"] is None


# -- change detection --------------------------------------------------------------------

#: REQ_1's fingerprint, before and after its body is edited
REVIEWED = _sha256(
    '{"content":"Reviewed text.","id":"REQ_1","title":"Target","type":"req"}'
)
EDITED = _sha256(
    '{"content":"Edited text.","id":"REQ_1","title":"Target","type":"req"}'
)

CHANGE_CONF = """\
extensions = ["sphinx_needs"]
needs_build_json = True
needs_fields = {
    "fp": {"schema": {"type": "string"}, "derive": {"kind": "fingerprint"}},
}
"""

CHANGE_INDEX = f"""\
Change
======

.. req:: Target
   :id: REQ_1

   Edited text.

.. spec:: Pinned to the reviewed text
   :id: SPEC_OLD
   :links: REQ_1[fp == "{REVIEWED}"]

.. spec:: Pinned to the current text
   :id: SPEC_NEW
   :links: REQ_1[fp == "{EDITED}"]

.. spec:: Pinned by a prefix
   :id: SPEC_PREFIX
   :links: REQ_1[fp.startswith('{EDITED[:12]}')]
"""


@pytest.mark.parametrize(
    "test_app", [_project(CHANGE_CONF, CHANGE_INDEX)], indirect=True
)
def test_a_link_condition_detects_a_changed_need(test_app):
    """The use case: a link condition pinning a need's fingerprint fails once the need
    changes (``SPEC_OLD``), and holds while it does not, in full or by a prefix."""
    app = test_app
    app.build()
    assert _needs(app)["REQ_1"]["fp"] == EDITED
    assert build_warnings(app) == [
        f"<srcdir>/index.rst:9: WARNING: Need 'SPEC_OLD' link 'REQ_1' in field 'links': "
        f"condition 'fp == \"{REVIEWED}\"' not satisfied by target need 'REQ_1' "
        "[needs.link_condition_failed]"
    ]
