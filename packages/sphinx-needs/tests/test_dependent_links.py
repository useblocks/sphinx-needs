"""Which end of a link depends on the other: ``dependent`` on a link type's entry.

``dependent`` is one of ``"source"`` (the need the link is written on depends on the
need it points to; the default), ``"target"`` (the need it points to depends on the
need the link is written on) and ``"both"``. sphinx-needs checks it and keeps it on the
link type's schema, and acts on it nowhere: no link, check, view or exported file moves
with it. On a link type declared on need types alone it is part of the shape, as
``summary`` is. The shared corpus pins the shape rule by its consequences
(``tests/fixtures/field_declaration_conformance.toml``); this module pins what the
corpus does not compare: the configuration findings and their texts, the stored value,
and that ``needs.json`` is the same with it as without it.
"""

import json
from pathlib import Path
from typing import Any, get_args

import pytest

from sphinx_needs.config import (
    LINK_DEPENDENT_VALUES,
    LinkDependent,
    NeedLinksConfig,
    NeedTypeLinkDeclaration,
)
from sphinx_needs.data import SphinxNeedsData
from sphinx_needs.derive import DeriveInvalid, parse_derive
from sphinx_needs.needs import NEED_TYPE_LINK_SHAPE_KEYS
from sphinx_needs.needs_schema import LinkDisplayConfig, LinkSchema
from sphinx_needs_testkit import build_warnings


def _project(conf: str, index: str) -> dict:
    return {
        "buildername": "needs",
        "files": [(Path("conf.py"), conf), (Path("index.rst"), index)],
    }


def _needs(app: Any) -> dict[str, Any]:
    data = json.loads(Path(app.outdir, "needs.json").read_text("utf8"))
    return data["versions"][data["current_version"]]["needs"]


def test_the_names_are_one_constant() -> None:
    """The three names are one constant, which the TypedDict's ``Literal`` is; the key
    is part of a link type's shape, right after ``summary``."""
    assert LINK_DEPENDENT_VALUES == ("source", "target", "both")
    assert get_args(LinkDependent) == LINK_DEPENDENT_VALUES
    # each declaration of the key is typed by the alias, not by names of its own
    for klass in (NeedLinksConfig, NeedTypeLinkDeclaration, LinkSchema):
        assert "LinkDependent" in str(klass.__annotations__["dependent"]), klass
    keys = list(NEED_TYPE_LINK_SHAPE_KEYS)
    assert keys[keys.index("summary") + 1] == "dependent"


CONF_NAMES = """\
extensions = ["sphinx_needs"]
needs_build_json = True
suppress_warnings = ["needs.deprecated"]
needs_links = {
    "satisfies": {"dependent": "source"},
    "satisfied_by": {"dependent": "target"},
    "related": {"dependent": "both"},
    "plain": {},
    "parent_needs": {"dependent": "target"},
}
needs_extra_links = [{"option": "realised_by", "dependent": "target"}]
needs_types = [
    {"directive": "req", "title": "Requirement", "prefix": "R_"},
    {"directive": "spec", "title": "Specification", "prefix": "S_"},
]
"""

INDEX_NAMES = """\
Dependent
=========

.. req:: Requirement
   :id: REQ_1
   :satisfied_by: SPEC_1
   :realised_by: SPEC_1

.. spec:: Specification
   :id: SPEC_1
   :satisfies: REQ_1
   :related: REQ_1
   :plain: REQ_1
   :parent_needs: REQ_1
"""


@pytest.mark.parametrize("test_app", [_project(CONF_NAMES, INDEX_NAMES)], indirect=True)
def test_dependent_is_one_of_three_names(test_app: Any) -> None:
    """Each of the three names is accepted, with no warning (a ``-W`` build passes), on
    ``needs_links``, ``needs_extra_links`` and a core link type's entry, and kept on the
    link type's schema; a link type that gives none, ``links`` among them, is
    ``"source"``. The links are held as any link type's."""
    app = test_app
    app.build()
    assert build_warnings(app) == []
    schema = SphinxNeedsData(app.env).get_schema()
    assert {
        link.name: link.dependent
        for link in schema.iter_link_fields()
        if not link.name.endswith("_back")
    } == {
        "satisfies": "source",
        "satisfied_by": "target",
        "related": "both",
        "plain": "source",
        "parent_needs": "target",
        "realised_by": "target",
        "links": "source",
    }
    # a need type's own declaration reads the link type's
    declared = schema.for_type("spec").get_link_field("satisfied_by")
    assert declared is not None and declared.dependent == "target"
    needs = _needs(app)
    assert needs["SPEC_1"]["satisfies"] == ["REQ_1"]
    assert needs["REQ_1"]["satisfied_by"] == ["SPEC_1"]
    assert needs["SPEC_1"]["satisfied_by_back"] == ["REQ_1"]
    assert needs["REQ_1"]["realised_by"] == ["SPEC_1"]


def _wrong_conf(option: str, value: object) -> str:
    entry = (
        f'needs_links = {{"satisfied_by": {{"dependent": {value!r}}}}}'
        if option == "needs_links"
        else f'needs_extra_links = [{{"option": "satisfied_by", "dependent": {value!r}}}]'
    )
    return (
        'extensions = ["sphinx_needs"]\n'
        "needs_build_json = True\n"
        'suppress_warnings = ["needs.deprecated"]\n'
        f"{entry}\n"
    )


INDEX_WRONG = """\
Dependent
=========

.. req:: Requirement
   :id: REQ_1

.. req:: Another
   :id: REQ_2
   :satisfied_by: REQ_1
"""


@pytest.mark.parametrize(
    ("value", "got"),
    [("upstream", "'upstream'"), (1, "int"), (True, "bool"), ("", "''")],
    ids=["another-string", "a-number", "a-boolean", "the-empty-string"],
)
@pytest.mark.parametrize("option", ["needs_links", "needs_extra_links"])
def test_a_dependent_that_is_no_name_is_ignored(
    option: str, value: object, got: str, make_app: Any, tmp_path: Path
) -> None:
    """A value that is none of the three names -- another string, a number, a
    boolean -- is one ``needs.config`` warning naming it, the key is ignored (the
    default, ``"source"``, stands) and the build goes on."""
    srcdir = tmp_path / "src"
    srcdir.mkdir()
    (srcdir / "conf.py").write_text(_wrong_conf(option, value), encoding="utf8")
    (srcdir / "index.rst").write_text(INDEX_WRONG, encoding="utf8")
    app = make_app("needs", srcdir=srcdir, freshenv=True)
    try:
        app.build()
        assert build_warnings(app) == [
            f"WARNING: {option}['satisfied_by'] has a 'dependent' that is not one of "
            f"'source', 'target' and 'both' (got {got}); the key is ignored "
            "[needs.config]"
        ]
        link = SphinxNeedsData(app.env).get_schema().get_link_field("satisfied_by")
        assert link is not None and link.dependent == "source"
        assert _needs(app)["REQ_2"]["satisfied_by"] == ["REQ_1"]
    finally:
        app.cleanup()


CONF_TYPE_LOCAL = """\
extensions = ["sphinx_needs"]
needs_build_json = True
needs_links = {"satisfies": {"dependent": "source"}}
needs_types = [
    {
        "directive": "req",
        "title": "Requirement",
        "prefix": "R_",
        "links": {"satisfied_by": {"dependent": "target"}, "rel": {}},
    },
    {
        "directive": "spec",
        "title": "Specification",
        "prefix": "S_",
        "links": {
            "satisfied_by": {"dependent": "target"},
            "rel": {"dependent": "both"},
            "satisfies": {"dependent": "target", "schema": {"maxItems": 1}},
        },
    },
    {
        "directive": "comp",
        "title": "Component",
        "prefix": "C_",
        "links": {"satisfied_by": {"dependent": "upstream"}},
    },
]
"""

INDEX_TYPE_LOCAL = """\
Dependent on need types
=======================

.. req:: Sets the shapes
   :id: REQ_1
   :satisfied_by: SPEC_1
   :rel: SPEC_1

.. req:: Another
   :id: REQ_2

.. spec:: Repeats one, refused on another
   :id: SPEC_1
   :satisfied_by: COMP_1
   :rel: REQ_1
   :satisfies: REQ_1, REQ_2

.. comp:: Its value ignored, its entry used
   :id: COMP_1
   :satisfied_by: REQ_1
"""


@pytest.mark.parametrize(
    "test_app", [_project(CONF_TYPE_LOCAL, INDEX_TYPE_LOCAL)], indirect=True
)
def test_dependent_on_a_need_types_entry(test_app: Any) -> None:
    """On a link type need types alone declare, ``dependent`` is part of the shape:
    the first root declaration sets it, a silent one too (``"source"``), and another
    declaration may repeat it; another value is a ``needs.type_conflict``, which
    refuses a root's entry. A value that is none of the names is a ``needs.config``
    finding, dropped, and the entry used. On a link type ``needs_links`` declares, a
    need type's ``dependent`` is a ``needs.config`` finding, the key ignored and the
    rest of the entry used (its ``schema`` holds)."""
    app = test_app
    app.build()
    assert build_warnings(app) == [
        # a list of need types names an entry by its position
        "WARNING: needs_types entry 3 ('comp').links['satisfied_by'] has a "
        "'dependent' that is not one of 'source', 'target' and 'both' (got "
        "'upstream'); the key is ignored [needs.config]",
        "WARNING: needs_types['spec'].links['rel'] cannot be declared with dependent "
        "'both': its dependent is 'source' on every need type, as need type 'req' "
        "declares it; the entry is ignored [needs.type_conflict]",
        "WARNING: needs_types['spec'].links['satisfies'] sets 'dependent', which a "
        "need type gives only a link type declared on need types alone; 'satisfies' "
        "keeps its own on every need type and the key is ignored [needs.config]",
        "<srcdir>/index.rst:12: WARNING: Link type 'rel' is not declared on need type "
        "'spec' and cannot be set in need 'SPEC_1'; the value 'REQ_1' is ignored "
        "[needs.undeclared_for_type]",
        # the rest of the entry is used: its schema holds
        "ERROR: Need 'SPEC_1' has schema violations:\n"
        "  Severity:       violation\n"
        "  Field:          satisfies\n"
        "  Need path:      SPEC_1\n"
        "  Schema path:    links > schema > properties > satisfies > maxItems\n"
        '  Schema message: ["REQ_1","REQ_2"] has more than 1 item '
        "[sn_schema_violation.link_fail]",
    ]
    schema = SphinxNeedsData(app.env).get_schema()
    for name, dependent in (
        ("satisfied_by", "target"),
        ("rel", "source"),
        ("satisfies", "source"),
    ):
        link = schema.get_link_field(name)
        assert link is not None and link.dependent == dependent, name
    declared = schema.for_type("comp").get_link_field("satisfied_by")
    assert declared is not None and declared.dependent == "target"
    needs = _needs(app)
    assert needs["SPEC_1"]["satisfied_by"] == ["COMP_1"]
    assert needs["COMP_1"]["satisfied_by"] == ["REQ_1"]
    assert needs["SPEC_1"]["rel"] == []
    assert needs["SPEC_1"]["satisfies"] == ["REQ_1", "REQ_2"]


#: a project setting ``dependent`` on every route a link type is declared by, and on
#: every kind of computed link type; ``DEPENDENT`` maps a link type to its entry's key
CONF_EVERY_ROUTE = """\
extensions = ["sphinx_needs"]
needs_build_json = True
needs_reproducible_json = True
suppress_warnings = ["needs.deprecated"]
_UNION = {"kind": "union", "fields": ["satisfies", "satisfied_by"]}
_BY_TYPE = {"spec": {"kind": "links", "where": "type == 'req'"}}
_COPY = {"kind": "copy", "field": "id", "over": "satisfies"}
_SELECTED = {"kind": "links", "where": "type == 'comp'"}
_MENTIONED = {"kind": "content_links"}
needs_links = {
    "satisfies": {**DEPENDENT.get("satisfies", {})},
    "satisfied_by": {"outgoing": "is satisfied by", **DEPENDENT.get("satisfied_by", {})},
    "trace": {"derive": _UNION, **DEPENDENT.get("trace", {})},
    "refines": {"derive_by_type": _BY_TYPE, **DEPENDENT.get("refines", {})},
    "selected": {"derive": _SELECTED, **DEPENDENT.get("selected", {})},
    "mentions": {"derive": _MENTIONED, **DEPENDENT.get("mentions", {})},
    "covers": {"summary": True, **DEPENDENT.get("covers", {})},
}
needs_extra_links = [{"option": "old", **DEPENDENT.get("old", {})}]
needs_types = [
    {
        "directive": "req",
        "title": "Requirement",
        "prefix": "R_",
        "links": {"realised_by": {**DEPENDENT.get("realised_by", {})}},
    },
    {
        "directive": "spec",
        "title": "Specification",
        "prefix": "S_",
        "links": {
            "chain": {"derive": _COPY, **DEPENDENT.get("chain", {})},
            "both_ways": {"derive": _UNION, **DEPENDENT.get("both_ways", {})},
        },
    },
    {"directive": "comp", "title": "Component", "prefix": "C_"},
]
"""

#: the value each link type of :data:`CONF_EVERY_ROUTE` is given
EVERY_ROUTE = {
    "satisfies": "source",
    "satisfied_by": "target",
    "trace": "both",
    "refines": "target",
    "selected": "target",
    "mentions": "target",
    "covers": "target",
    "old": "target",
    "realised_by": "target",
    "chain": "target",
    "both_ways": "both",
}

INDEX_EVERY_ROUTE = """\
Every route
===========

.. req:: Requirement
   :id: REQ_1
   :realised_by: COMP_1

.. comp:: Component
   :id: COMP_1

.. spec:: Specification
   :id: SPEC_1
   :satisfies: REQ_1
   :satisfied_by: REQ_1
   :covers: REQ_1
   :old: REQ_1

   Mentions :need:`REQ_1`.
"""


def _build_every_route(
    make_app: Any, srcdir: Path, dependent: dict[str, str]
) -> tuple[list[str], bytes, Any]:
    srcdir.mkdir()
    given = {name: {"dependent": value} for name, value in dependent.items()}
    (srcdir / "conf.py").write_text(
        f"DEPENDENT = {given!r}\n{CONF_EVERY_ROUTE}", encoding="utf8"
    )
    (srcdir / "index.rst").write_text(INDEX_EVERY_ROUTE, encoding="utf8")
    app = make_app("needs", srcdir=srcdir, freshenv=True)
    try:
        app.build()
        schema = SphinxNeedsData(app.env).get_schema()
        stored = {
            name: link.dependent
            for name in EVERY_ROUTE
            if (link := schema.get_link_field(name)) is not None
        }
        return (
            build_warnings(app),
            Path(app.outdir, "needs.json").read_bytes(),
            stored,
        )
    finally:
        app.cleanup()


def test_dependent_on_a_summary_or_union_link_type(
    make_app: Any, tmp_path: Path
) -> None:
    """On a summary link type (``summary = true``, a ``copy`` or ``collect``), a union,
    and a ``links`` or ``content_links`` rule's link type (an ordinary one for
    ``dependent``), beside a
    ``derive`` or a ``derive_by_type``, on a ``needs_links`` entry and on a need type's
    declaration alike, ``dependent`` is accepted with no finding -- no
    ``derive_invalid``, as ``summary = false`` beside a copy is -- and kept as given;
    every rule computes its links as without it."""
    warnings, _, stored = _build_every_route(make_app, tmp_path / "with", EVERY_ROUTE)
    assert warnings == []
    assert stored == EVERY_ROUTE
    plain_warnings, _, plain = _build_every_route(make_app, tmp_path / "without", {})
    assert plain_warnings == []
    assert plain == dict.fromkeys(EVERY_ROUTE, "source")


def test_needs_json_is_the_same_with_dependent_as_without(
    make_app: Any, tmp_path: Path
) -> None:
    """``dependent`` is not exported: two projects differing only in it, on every
    route a link type is declared by and on every kind of computed link type, write
    the same ``needs.json``, byte for byte -- every link computed as without it."""
    _, given, _ = _build_every_route(make_app, tmp_path / "with", EVERY_ROUTE)
    _, plain, _ = _build_every_route(make_app, tmp_path / "without", {})
    assert given == plain
    needs = json.loads(given)["versions"][""]["needs"]
    assert needs["SPEC_1"]["trace"] == ["REQ_1"]
    assert needs["SPEC_1"]["refines"] == ["REQ_1"]
    assert needs["SPEC_1"]["selected"] == ["COMP_1"]
    assert needs["SPEC_1"]["mentions"] == ["REQ_1"]
    assert needs["SPEC_1"]["chain"] == ["REQ_1"]
    assert needs["SPEC_1"]["both_ways"] == ["REQ_1"]
    assert needs["REQ_1"]["realised_by"] == ["COMP_1"]
    assert needs["SPEC_1"]["old"] == ["REQ_1"]


def test_dependent_is_no_role_of_a_rule() -> None:
    """A rule is no place for it: it is the link type's, beside its rules."""
    assert parse_derive(
        {"kind": "links", "where": "type == 'req'", "dependent": "target"},
        on_link=True,
    ) == DeriveInvalid(
        "links",
        "kind 'links': 'dependent' is not a role; which end of a link depends on the "
        "other is given on the link type's entry, beside derive",
    )


def _link(**kwargs: Any) -> LinkSchema:
    return LinkSchema(
        name="blocks",
        schema={"type": "array", "items": {"type": "string"}},
        display=LinkDisplayConfig(incoming="blocked by", outgoing="blocks"),
        **kwargs,
    )


def test_the_link_schema_holds_one_of_the_names() -> None:
    """``LinkSchema.dependent`` is ``"source"`` unless given, and one of the names."""
    assert _link().dependent == "source"
    for value in LINK_DEPENDENT_VALUES:
        assert _link(dependent=value).dependent == value
    for value in ("upstream", "", 1, True, None):
        with pytest.raises(
            ValueError, match="dependent must be one of 'source', 'target' and 'both'"
        ):
            _link(dependent=value)
