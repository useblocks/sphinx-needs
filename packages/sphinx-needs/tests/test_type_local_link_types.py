"""A link type may be declared on the need types that have it alone.

A ``links`` entry of a need type naming no link type the project declares -- no
``needs_links`` or ``needs_extra_links`` entry, not ``links`` or ``parent_needs``, and
no field -- declares a link type of its own: the link type of the types that declare it
(by their own entry, or an ancestor's; an empty entry declares), absent on every other
type, where its needs hold no links. Every type that declares it agrees on its shape --
whether it is derived, and its display, ``copy`` and ``allow_dead_links``, which a
``needs_links`` entry gives for every need type -- and the first declaration of a type
without an ancestor declaring it, an empty one too, sets it; every other declaration may
repeat it, and no more.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest
from docutils import nodes

from sphinx_needs.api.need import generate_need
from sphinx_needs.config import NeedsSphinxConfig
from sphinx_needs.data import SphinxNeedsData
from sphinx_needs.directives.needflow._model import resolve_link_types
from sphinx_needs.exceptions import NeedsConfigException
from sphinx_needs.needs_schema import FieldsSchema, LinkDisplayConfig, LinkSchema
from sphinx_needs_testkit import build_warnings

CONF = """\
extensions = ["sphinx_needs"]
needs_build_json = True
"""

#: the default need types but ``need``, as a table keyed by directive
BASE_TYPES: dict[str, dict[str, Any]] = {
    "req": {"title": "Requirement", "prefix": "R_"},
    "spec": {"title": "Specification", "prefix": "S_"},
    "impl": {"title": "Implementation", "prefix": "I_"},
    "test": {"title": "Test Case", "prefix": "T_"},
}

#: a link type of ``needs_links``
BLOCKS = {"incoming": "is blocked by", "outgoing": "blocks"}


def _types(**declarations: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """``BASE_TYPES``, each named type with its declarations added (a type not in
    ``BASE_TYPES`` is added, with a title and a prefix of its own)."""
    types = {
        name: {**entry, **declarations.get(name, {})}
        for name, entry in BASE_TYPES.items()
    }
    for name, entry in declarations.items():
        if name not in types:
            prefix = name.upper() + "_"
            types[name] = {"title": name, "prefix": prefix, **entry}
    return types


def _conf(types: object, extra: str = "") -> str:
    return CONF + f"needs_types = {types!r}\n" + extra


def _project(conf: str, index: str = "", builder: str = "needs") -> dict[str, Any]:
    return {
        "buildername": builder,
        "files": [
            (Path("conf.py"), conf),
            (Path("index.rst"), "Case\n====\n\n" + index),
        ],
    }


def _version(app: Any) -> dict[str, Any]:
    data = json.loads(Path(app.outdir, "needs.json").read_text(encoding="utf-8"))
    return data["versions"][data["current_version"]]


def _needs(app: Any) -> dict[str, dict[str, Any]]:
    return _version(app)["needs"]


def _schema(app: Any) -> FieldsSchema:
    return SphinxNeedsData(app.env).get_schema()


def _field(app: Any, need_type: str | None, name: str) -> Any:
    """The declaration of ``name`` the needs of ``need_type`` read."""
    field = _schema(app).for_type(need_type).get_any_field(name)
    assert field is not None
    return field


def _undeclared(
    line: int | None, need: str, need_type: str, value: object, name: str = "verifies"
) -> str:
    at = "" if line is None else f"<srcdir>/index.rst:{line}: "
    return (
        f"{at}WARNING: Link type {name!r} is not declared on need type {need_type!r} "
        f"and cannot be set in need {need!r}; the value {value!r} is ignored "
        "[needs.undeclared_for_type]"
    )


def _not_extended(line: int, option: str, need_type: str, needs: list[str]) -> str:
    count = f"{len(needs)} need{'' if len(needs) == 1 else 's'}"
    return (
        f"<srcdir>/index.rst:{line}: WARNING: Option {option!r} does not support "
        f"extend operations on need type {need_type!r}; it does not extend {count} "
        f"({', '.join(needs)}). [needs.needextend]"
    )


def _conflict(text: str) -> str:
    return f"WARNING: {text}; the entry is ignored [needs.type_conflict]"


def _cannot(need_type: str, name: str, key: str, own: object, agreed: object, by: str):
    """The finding of a declaration giving a key another value than the shape's."""
    return _conflict(
        f"needs_types[{need_type!r}].links[{name!r}] cannot be declared with {key} "
        f"{own!r}: its {key} is {agreed!r} on every need type, as need type {by!r} "
        "declares it"
    )


def _values(app: Any, *names: str) -> dict[str, tuple[Any, ...]]:
    return {
        need_id: tuple(need[name] for name in names)
        for need_id, need in _needs(app).items()
    }


# -- the projection, on a schema built by hand ----------------------------------------


def _link(name: str) -> LinkSchema:
    return LinkSchema(
        name=name,
        schema={"type": "array", "items": {"type": "string"}},
        display=LinkDisplayConfig(incoming=f"{name} in", outgoing=f"{name} out"),
        directive_option=True,
        allow_extend=True,
        allow_defaults=True,
    )


def test_a_link_type_of_some_need_types_is_projected_per_link_type() -> None:
    """The schema's views project a link type of some need types alone as they project
    such a field: on every other type it is one absent declaration -- not authorable,
    not extendable -- shared by those types; a declaring type, and the global view,
    read the global declaration; every other link type is as declared for all."""
    schema = FieldsSchema()
    for name in ("links", "parent_needs", "verifies"):
        schema.add_link_field(_link(name))
    schema.set_need_types(["req", "spec", "impl"])
    schema._localise("verifies", ["req"])
    req, spec, impl, every = (schema.for_type(t) for t in ("req", "spec", "impl", None))
    assert req is every
    absent = spec.get_link_field("verifies")
    assert absent is not None
    assert (absent.directive_option, absent.allow_extend) == (False, False)
    assert absent.display == _link("verifies").display
    assert impl.get_link_field("verifies") is absent
    assert every.get_link_field("verifies") is schema.global_declaration("verifies")
    assert (spec.declares("verifies"), req.declares("verifies")) == (False, True)
    for name in ("links", "parent_needs"):
        assert spec.get_link_field(name) is every.get_link_field(name), name


# -- a link type declared on need types alone -----------------------------------------

LOCAL_TYPES = _types(
    req={
        "links": {
            "verifies": {
                "description": "What a requirement verifies",
                "incoming": "is verified by",
                "outgoing": "verifies",
                "schema": {"maxItems": 2},
            }
        }
    },
    sreq={"inherits": "req"},
    test={"links": {"verifies": {"outgoing": "verifies"}}},
)

LOCAL_INDEX = """\
.. req:: A
   :id: R_001
   :verifies: S_001

.. sreq:: B
   :id: SREQ_001
   :verifies: R_001

.. test:: C
   :id: T_001
   :verifies: R_001, SREQ_001

.. spec:: D
   :id: S_001
   :verifies: R_001

.. spec:: E
   :id: S_002

.. impl:: F
   :id: I_001

.. needextend:: type == 'spec'
   :+verifies: R_001

.. needextend:: type == 'spec'
   :verifies: R_001

.. needextend:: type in ['spec', 'impl']
   :-verifies:

.. needextend:: R_001
   :+verifies: I_001
"""


@pytest.mark.parametrize(
    "test_app",
    [
        _project(
            _conf(LOCAL_TYPES, f"needs_links = {{'blocks': {BLOCKS!r}}}\n"), LOCAL_INDEX
        )
    ],
    indirect=True,
)
def test_a_link_type_declared_on_need_types_alone(test_app: Any) -> None:
    """A ``links`` entry naming no link type declares one: the link type of the types
    that declare it, and their children. A link set for it on a need of another type
    is ignored, and reported; a needextend does not extend it there, one warning for
    each needextend, type and option; such a need holds no links, ``[]`` -- a link
    list is never ``None`` -- and its back links are on every need. The needs.json
    declares it once, as a link type of the roots that declare it."""
    app = test_app
    app.build()
    assert build_warnings(app) == [
        _undeclared(16, "S_001", "spec", "R_001"),
        _not_extended(26, "+verifies", "spec", ["S_001", "S_002"]),
        _not_extended(29, "verifies", "spec", ["S_001", "S_002"]),
        _not_extended(32, "-verifies", "impl", ["I_001"]),
        _not_extended(32, "-verifies", "spec", ["S_001", "S_002"]),
    ]
    assert _values(app, "verifies", "verifies_back") == {
        "R_001": (["I_001", "S_001"], ["SREQ_001", "T_001"]),
        "SREQ_001": (["R_001"], ["T_001"]),
        "T_001": (["R_001", "SREQ_001"], []),
        "S_001": ([], ["R_001"]),
        "S_002": ([], []),
        "I_001": ([], ["R_001"]),
    }
    properties = _version(app)["needs_schema"]["properties"]
    assert properties["verifies"] == {
        "default": [],
        "description": "Declared by need types 'req', 'test'",
        "field_type": "links",
        "items": {"type": "string"},
        "type": "array",
    }
    assert properties["verifies_back"]["field_type"] == "backlinks"
    schema = _schema(app)
    glob = schema.global_declaration("verifies")
    assert glob is not None
    assert glob.kind == "link"
    assert (glob.directive_option, glob.allow_extend) == (True, True)
    assert sorted(dict(schema.type_declarations("verifies"))) == ["req", "sreq", "test"]
    assert _field(app, "req", "verifies").description == "What a requirement verifies"
    assert _field(app, "sreq", "verifies") is _field(app, "req", "verifies")
    absent = _field(app, "spec", "verifies")
    assert (absent.directive_option, absent.allow_extend) == (False, False)
    assert _field(app, "impl", "verifies") is absent
    assert _field(app, None, "verifies") is glob
    assert not schema.for_type("spec").declares("verifies")
    # a link type needs_links declares is on every type, as declared for all
    for need_type in ("req", "spec", "impl", "test", "sreq"):
        assert _field(app, need_type, "blocks") is _field(app, None, "blocks")


@pytest.mark.parametrize(
    "test_app",
    [
        _project(
            _conf(_types(spec={"links": {"nope": {"description": "d"}}})),
            ".. spec:: A\n   :id: S_001\n   :nope: R_001\n\n"
            ".. req:: B\n   :id: R_001\n",
        )
    ],
    indirect=True,
)
def test_an_entry_naming_no_link_type_declares_one(test_app: Any) -> None:
    """An entry of a name declared nowhere, once refused as no link type, is the
    declaration of a link type of its type alone, its keys the type's."""
    app = test_app
    app.build()
    assert build_warnings(app) == []
    assert _values(app, "nope", "nope_back") == {
        "S_001": (["R_001"], []),
        "R_001": ([], ["S_001"]),
    }
    assert _field(app, "spec", "nope").description == "d"
    assert sorted(dict(_schema(app).type_declarations("nope"))) == ["spec"]
    glob = _schema(app).global_declaration("nope")
    assert glob is not None
    assert glob.description == "Declared by need types 'spec'"


@pytest.mark.parametrize(
    "test_app",
    [_project(_conf(LOCAL_TYPES))],
    indirect=True,
)
def test_add_need_takes_the_link_and_refuses_it(test_app: Any) -> None:
    """``add_need`` takes a keyword of a link type another type declares -- it is a
    link type of the project -- and refuses its links, as a need directive does."""
    app = test_app
    app.build()
    need = generate_need(
        NeedsSphinxConfig(app.config),
        _schema(app),
        "spec",
        "A",
        id="S_001",
        verifies=["R_001"],
    )
    assert need["verifies"] == []
    assert build_warnings(app) == [_undeclared(None, "S_001", "spec", ["R_001"])]


# -- the display, copy and dead links: the first root declaration's -------------------

DISPLAY_TYPES = _types(
    req={
        "links": {
            "verifies": {
                "incoming": "is verified by",
                "outgoing": "verifies",
                "color": "#ff0000",
                "style": "dashed",
                "style_part": "bold",
                "style_start": "<-",
                "style_end": "-->",
                "allow_dead_links": True,
            }
        }
    },
    # a later root of no key of its own takes the shape
    test={"links": {"verifies": {}}},
    # an empty first root sets the defaults of a needs_links entry
    impl={"links": {"rel": {}}},
)

DISPLAY_INDEX = """\
.. req:: A
   :id: R_001
   :verifies: S_001, NOPE_1

.. spec:: B
   :id: S_001

.. test:: C
   :id: T_001
   :verifies: R_001

.. impl:: D
   :id: I_001
   :rel: R_001

.. needtable::
   :columns: id, verifies, verifies_back
   :style: table

.. needreport::
   :links:
"""


@pytest.mark.parametrize(
    "test_app",
    [
        _project(
            _conf(
                DISPLAY_TYPES,
                "needs_render_context = {'report_directive': 'admonition'}\n",
            ),
            DISPLAY_INDEX,
            "html",
        )
    ],
    indirect=True,
)
def test_the_first_root_declaration_gives_the_display(test_app: Any) -> None:
    """The display, ``copy`` and ``allow_dead_links`` of the link type, on every need
    type, are what its first root declaration gives, with the defaults of a
    ``needs_links`` entry for the rest -- all of them for an empty one; every renderer
    reads them as it reads a ``needs_links`` entry's: a need's link rows, a needtable's
    columns, a needflow's link types and edge styles, a needreport."""
    app = test_app
    app.build()
    # the dead link is allowed, as the root declares
    assert build_warnings(app) == []
    union = _schema(app).get_link_field("verifies")
    assert union is not None
    assert union.display == LinkDisplayConfig(
        incoming="is verified by",
        outgoing="verifies",
        color="#ff0000",
        style="dashed",
        style_part="bold",
        style_start="<-",
        style_end="-->",
    )
    assert (union.copy, union.allow_dead_links) == (False, True)
    rel = _schema(app).get_link_field("rel")
    assert rel is not None
    assert rel.display == LinkDisplayConfig(incoming="rel incoming", outgoing="rel")
    assert (rel.copy, rel.allow_dead_links) == (False, False)
    html = Path(app.outdir, "index.html").read_text(encoding="utf-8")
    text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html))
    # the link rows of R_001: its outgoing and its incoming links, by the root's labels
    assert (
        "R_001 verifies: NOPE_1 , S_001 is verified by: T_001 rel incoming: I_001"
        in (text)
    )
    # the needtable's columns, and a needreport's link types table (name, incoming,
    # outgoing, copy, allow_dead_links), the link types in the schema's order
    assert "ID Verifies Verifies Back" in text
    assert (
        "Parent_needs Child needs Parent needs False False "
        "Verifies Is verified by Verifies False True Rel Rel incoming Rel False False"
    ) in text
    # a needflow's link types: the name resolves, its edges styled as the root says
    flow: Any = {"target_id": "needflow-index-0", "link_types": ["verifies"]}
    drawn = resolve_link_types(
        flow,
        schema=_schema(app),
        config=NeedsSphinxConfig(app.config),
        location=nodes.paragraph(),
    )
    assert [(link.name, link.display.style) for link in drawn] == [
        ("verifies", "dashed")
    ]


COPY_TYPES = _types(
    req={"links": {"verifies": {"copy": True}}},
    sreq={"inherits": "req"},
    # a second root, of no key of its own, takes copy = true
    test={"links": {"verifies": {}}},
    task={
        "links": {
            "cites": {
                "derive": {"kind": "links", "where": "type == 'spec'"},
                "copy": True,
            }
        }
    },
)

COPY_INDEX = """\
.. req:: A
   :id: R_001
   :verifies: S_001

.. sreq:: B
   :id: SREQ_001
   :verifies: R_001

.. test:: C
   :id: T_001
   :verifies: R_001

.. spec:: D
   :id: S_001
   :verifies: R_001

.. task:: E
   :id: TASK_001
"""


@pytest.mark.parametrize(
    "test_app",
    [_project(_conf(COPY_TYPES), COPY_INDEX)],
    indirect=True,
)
def test_copy_is_the_first_root_declarations(test_app: Any) -> None:
    """With ``copy`` in the first root declaration, the links of every declaring need
    are copied into ``links`` -- a later root's too, which takes the shape -- and a
    need of a type that does not declare the link type copies none; ``copy`` beside a
    ``derive`` is refused as on a ``needs_links`` entry."""
    app = test_app
    app.build()
    assert build_warnings(app) == [
        "WARNING: Invalid derive of link type 'cites': by need type: 'copy' is not "
        "available on a derived link type in this release, and is ignored; the rule "
        "applies [needs.derive_invalid]",
        _undeclared(16, "S_001", "spec", "R_001"),
    ]
    assert _values(app, "verifies", "links") == {
        "R_001": (["S_001"], ["S_001"]),
        "SREQ_001": (["R_001"], ["R_001"]),
        "T_001": (["R_001"], ["R_001"]),
        "S_001": ([], []),
        "TASK_001": ([], []),
    }
    assert _needs(app)["TASK_001"]["cites"] == ["S_001"]


DEAD_LINKS_CONF = _conf(
    _types(
        req={
            "links": {
                "verifies": {"allow_dead_links": True},
                "checks": {"allow_dead_links": True, "copy": True},
            }
        }
    ),
    "needs_links = {'gchecks': {'allow_dead_links': True, 'copy': True}}\n",
)


@pytest.mark.parametrize(
    "test_app",
    [
        _project(
            DEAD_LINKS_CONF,
            ".. req:: A\n   :id: R_001\n   :verifies: NOPE_1\n\n"
            ".. req:: B\n   :id: R_002\n   :checks: NOPE_2\n\n"
            ".. req:: C\n   :id: R_003\n   :gchecks: NOPE_3\n",
        )
    ],
    indirect=True,
)
def test_dead_links_are_the_first_root_declarations(test_app: Any) -> None:
    """With ``allow_dead_links`` in the first root declaration, a dead link of the
    link type is allowed, as for a ``needs_links`` entry."""
    app = test_app
    app.build()
    # with copy beside it, the dead link copied into ``links`` is reported, in both
    # link types: that is what a needs_links entry of the same keys does (gchecks),
    # and not this declaration's to change
    assert build_warnings(app) == [
        "<srcdir>/index.rst:8: WARNING: Need 'R_002' has unknown outgoing link "
        "'NOPE_2' in field 'links' [needs.link_outgoing]",
        "<srcdir>/index.rst:8: WARNING: Need 'R_002' has unknown outgoing link "
        "'NOPE_2' in field 'checks' [needs.link_outgoing]",
        "<srcdir>/index.rst:12: WARNING: Need 'R_003' has unknown outgoing link "
        "'NOPE_3' in field 'gchecks' [needs.link_outgoing]",
        "<srcdir>/index.rst:12: WARNING: Need 'R_003' has unknown outgoing link "
        "'NOPE_3' in field 'links' [needs.link_outgoing]",
    ]
    needs = _needs(app)
    assert (
        needs["R_001"]["has_dead_links"],
        needs["R_001"]["has_forbidden_dead_links"],
    ) == (True, False)


# -- the shape, and who sets it -------------------------------------------------------

SHAPE_TYPES = {
    "x": {"title": "X", "prefix": "X_", "inherits": "nope"},
    "fa": {
        "title": "FA",
        "prefix": "FA_",
        "fields": {"f": {"schema": {"type": "integer"}}},
    },
    "fb": {
        "title": "FB",
        "prefix": "FB_",
        "fields": {"f": {"schema": {"type": "string"}}},
    },
    # an empty first root: it sets the defaults
    "a": {"title": "A", "prefix": "A_", "links": {"rel": {}}},
    # a later root giving a key the first left out: refused, it cannot add one
    "b": {"title": "B", "prefix": "B_", "links": {"rel": {"incoming": "related from"}}},
    # a later root repeating a default: accepted
    "c": {
        "title": "C",
        "prefix": "C_",
        "links": {"rel": {"outgoing": "rel", "schema": {"maxItems": 1}}},
    },
    # a child giving another value: refused, it still declares through its parent
    "ca": {
        "title": "CA",
        "prefix": "CA_",
        "inherits": "a",
        "links": {"rel": {"incoming": "zzz", "default": ["A_001"]}},
    },
    # a child of a refused root is a root of its own
    "bb": {"title": "BB", "prefix": "BB_", "inherits": "b", "links": {"rel": {}}},
    "req": {
        "title": "Req",
        "prefix": "R_",
        "links": {"verifies": {"incoming": "is verified by"}},
    },
    "bad": {
        "title": "Bad",
        "prefix": "BAD_",
        "links": {"verifies": {"incoming": "other"}},
    },
}

SHAPE_INDEX = """\
.. a:: A
   :id: A_001

.. b:: B
   :id: B_001
   :rel: A_001

.. c:: C
   :id: C_001
   :rel: A_001

.. ca:: CA
   :id: CA_001

.. ca:: CA
   :id: CA_002
   :rel: A_001

.. bb:: BB
   :id: BB_001
   :rel: A_001

.. bad:: Bad
   :id: BAD_001
   :verifies: A_001
"""


@pytest.mark.parametrize(
    "test_app",
    [_project(_conf(SHAPE_TYPES), SHAPE_INDEX)],
    indirect=True,
)
def test_the_first_root_declaration_sets_the_shape(test_app: Any) -> None:
    """The first root declaration sets the shape, an empty one too; another declaration
    may repeat a value and no more -- a key the first left out, given another value,
    is refused like any other value. A refused root declares nothing, a refused child
    still declares through its parent, and a child of a refused root is a root of its
    own. The findings of the link types come after the walk's and the fields'."""
    app = test_app
    app.build()
    assert build_warnings(app) == [
        "WARNING: Need type 'x' inherits 'nope', which is not a need type; its "
        "inherits is ignored. [needs.type_inherits]",
        _conflict(
            "needs_types['fb'].fields['f'] cannot be declared with type 'string' "
            "(items None): its type is 'integer' (items None) on every need type, as "
            "need type 'fa' declares it"
        ),
        _cannot("b", "rel", "incoming", "related from", "rel incoming", "a"),
        _cannot("ca", "rel", "incoming", "zzz", "rel incoming", "a"),
        _cannot("bad", "verifies", "incoming", "other", "is verified by", "req"),
        _undeclared(7, "B_001", "b", "A_001", "rel"),
        _undeclared(26, "BAD_001", "bad", "A_001"),
    ]
    assert _values(app, "rel") == {
        "A_001": ([],),
        "B_001": ([],),
        "C_001": (["A_001"],),
        "CA_001": ([],),
        "CA_002": (["A_001"],),
        "BB_001": (["A_001"],),
        "BAD_001": ([],),
    }
    glob = _schema(app).global_declaration("rel")
    assert glob is not None
    assert glob.description == "Declared by need types 'a', 'c', 'bb'"
    assert glob.display == LinkDisplayConfig(incoming="rel incoming", outgoing="rel")
    assert _field(app, "c", "rel").schema["maxItems"] == 1
    assert not _schema(app).for_type("b").declares("rel")
    assert _schema(app).for_type("ca").declares("rel")


DERIVED_TYPES = _types(
    task={
        "links": {
            "mentions": {
                "derive": {"kind": "links", "where": "type == 'req'"},
                "outgoing": "mentions",
            }
        }
    },
    subtask={"inherits": "task"},
    # a root without the derive: derivation is all or none
    plain={"links": {"mentions": {"outgoing": "mentions"}}},
)

DERIVED_INDEX = """\
.. req:: A
   :id: R_001

.. req:: B
   :id: R_002

.. task:: C
   :id: TASK_001
   :mentions: S_001

.. subtask:: D
   :id: SUBTASK_001

.. spec:: E
   :id: S_001
   :mentions: R_001

.. plain:: F
   :id: PLAIN_001
"""


@pytest.mark.parametrize(
    "test_app",
    [_project(_conf(DERIVED_TYPES), DERIVED_INDEX)],
    indirect=True,
)
def test_a_derived_link_type_declared_on_need_types_alone(test_app: Any) -> None:
    """A ``derive`` in the first root declaration makes the link type derived on every
    type that declares it -- a child inheriting the rule -- and a root without one is
    refused; its needs compute their links, an author's are refused there as for any
    derived link type, and on a type that does not declare it the need holds no links,
    and a link set is ignored as undeclared."""
    app = test_app
    app.build()
    assert build_warnings(app) == [
        _conflict(
            "needs_types['plain'].links['mentions'] cannot be declared without a "
            "'derive': it is derived on every need type that declares it, as need "
            "type 'task' declares it"
        ),
        "<srcdir>/index.rst:10: WARNING: Link type 'mentions' is derived (kind "
        "'links') and cannot be set in a need; the value 'S_001' is ignored "
        "[needs.derive_authored]",
        _undeclared(17, "S_001", "spec", "R_001", "mentions"),
    ]
    assert _values(app, "mentions", "mentions_back") == {
        "R_001": ([], ["SUBTASK_001", "TASK_001"]),
        "R_002": ([], ["SUBTASK_001", "TASK_001"]),
        "TASK_001": (["R_001", "R_002"], []),
        "SUBTASK_001": (["R_001", "R_002"], []),
        "S_001": ([], []),
        "PLAIN_001": ([], []),
    }
    properties = _version(app)["needs_schema"]["properties"]
    assert properties["mentions"]["readOnly"] is True
    assert properties["mentions"]["description"] == "Declared by need types 'task'"


# -- from outside ---------------------------------------------------------------------

OUTSIDE_TYPES = _types(
    req={"links": {"verifies": {"incoming": "is verified by"}}},
    task={
        "links": {"mentions": {"derive": {"kind": "links", "where": "type == 'req'"}}}
    },
)


def test_from_outside(make_app: Any, tmp_path: Path) -> None:
    """A needs.json of the project carries every link type on every need, ``[]`` where
    the need's type does not declare it: imported, and read as external needs, by a
    project of the same configuration it gives no warning. An edited one, giving such
    a need links, is dropped with the warning -- a derived link type's too -- while a
    declaring need keeps its links, a derived link type's as data."""
    index = (
        ".. req:: A\n   :id: R_001\n   :verifies: S_001\n\n"
        ".. req:: B\n   :id: R_002\n\n"
        ".. spec:: C\n   :id: S_001\n\n"
        ".. task:: D\n   :id: TASK_001\n"
    )
    first = tmp_path / "first"
    first.mkdir()
    (first / "conf.py").write_text(_conf(OUTSIDE_TYPES), encoding="utf-8")
    (first / "index.rst").write_text("Case\n====\n\n" + index, encoding="utf-8")
    app = make_app("needs", srcdir=first)
    app.build()
    assert build_warnings(app) == []
    exported = json.loads(Path(app.outdir, "needs.json").read_text(encoding="utf-8"))
    app.cleanup()
    needs = exported["versions"][exported["current_version"]]["needs"]
    assert (needs["S_001"]["verifies"], needs["S_001"]["mentions"]) == ([], [])
    assert needs["TASK_001"]["mentions"] == ["R_001", "R_002"]

    second = tmp_path / "second"
    second.mkdir()
    (second / "same.json").write_text(json.dumps(exported), encoding="utf-8")
    needs["S_001"]["verifies"] = ["R_001"]
    needs["S_001"]["mentions"] = ["R_002"]
    needs["TASK_001"]["mentions"] = ["R_002"]
    (second / "edited.json").write_text(json.dumps(exported), encoding="utf-8")
    external = (
        "needs_external_needs = [{'base_url': 'http://example.org', "
        f"'json_path': {str(second / 'edited.json')!r}, 'id_prefix': 'E_'}}]\n"
    )
    (second / "conf.py").write_text(_conf(OUTSIDE_TYPES, external), encoding="utf-8")
    (second / "index.rst").write_text(
        "Case\n====\n\n.. needimport:: same.json\n   :id_prefix: M_\n\n"
        ".. needimport:: edited.json\n   :id_prefix: X_\n",
        encoding="utf-8",
    )
    app = make_app("needs", srcdir=second)
    app.build()
    assert build_warnings(app) == [
        _undeclared(None, "E_S_001", "spec", ["E_R_001"]),
        _undeclared(None, "E_S_001", "spec", ["E_R_002"], "mentions"),
        _undeclared(7, "X_S_001", "spec", ["X_R_001"]),
        _undeclared(7, "X_S_001", "spec", ["X_R_002"], "mentions"),
    ]
    held = SphinxNeedsData(app.env).get_needs_view()
    for prefix, task in (
        ("M_", ["R_001", "R_002"]),
        ("X_", ["R_002"]),
        ("E_", ["R_002"]),
    ):
        assert {
            k.removeprefix(prefix): (
                [x.removeprefix(prefix) for x in v["verifies"]],
                [x.removeprefix(prefix) for x in v["mentions"]],
            )
            for k, v in held.items()
            if k.startswith(prefix)
        } == {
            "R_001": (["S_001"], []),
            "R_002": ([], []),
            "S_001": ([], []),
            "TASK_001": ([], task),
        }, prefix


# -- what a declaration of a link type declared otherwise cannot give -----------------


@pytest.mark.parametrize(
    "test_app",
    [
        _project(
            _conf(
                _types(
                    spec={
                        "links": {
                            "blocks": {
                                "incoming": "x",
                                "copy": True,
                                "default": ["R_001"],
                                "schema": {"maxItems": 1},
                            }
                        }
                    },
                    req={"links": {"links": {"incoming": "in"}}},
                    impl={"links": {"parent_needs": {"style": "bold"}}},
                ),
                f"needs_links = {{'blocks': {BLOCKS!r}}}\n",
            ),
            ".. req:: A\n   :id: R_001\n\n.. spec:: B\n   :id: S_001\n",
        )
    ],
    indirect=True,
)
def test_the_display_of_a_link_type_declared_otherwise_is_not_a_types(
    test_app: Any,
) -> None:
    """A link type ``needs_links`` declares, ``links`` and ``parent_needs`` are drawn,
    copied and checked the same on every need type: a type's declaration giving their
    display, ``copy`` or ``allow_dead_links`` is one ``needs.config`` warning, those
    keys ignored and the rest of the declaration used; the link type stays on every
    type."""
    app = test_app
    app.build()
    assert build_warnings(app) == [
        "WARNING: needs_types['req'].links['links'] sets 'incoming', which a need "
        "type gives only a link type declared on need types alone; 'links' keeps its "
        "own on every need type and the key is ignored [needs.config]",
        "WARNING: needs_types['spec'].links['blocks'] sets 'incoming' and 'copy', "
        "which a need type gives only a link type declared on need types alone; "
        "'blocks' keeps its own on every need type and the keys are ignored "
        "[needs.config]",
        "WARNING: needs_types['impl'].links['parent_needs'] sets 'style', which a "
        "need type gives only a link type declared on need types alone; "
        "'parent_needs' keeps its own on every need type and the key is ignored "
        "[needs.config]",
    ]
    assert _values(app, "blocks", "links") == {
        "R_001": ([], []),
        "S_001": (["R_001"], []),
    }
    assert _field(app, "spec", "blocks").schema["maxItems"] == 1
    for name, incoming in (
        ("blocks", "is blocked by"),
        ("links", "links incoming"),
        ("parent_needs", "child needs"),
    ):
        union = _schema(app).get_link_field(name)
        assert union is not None
        assert (union.display.incoming, union.copy) == (incoming, False), name
        assert union.display.style == "", name
    for need_type in BASE_TYPES:
        assert _schema(app).for_type(need_type).declares("blocks"), need_type


@pytest.mark.parametrize(
    "test_app",
    [
        _project(
            _conf(
                _types(
                    spec={
                        "links": {
                            "rel": {
                                "parse_variants": True,
                                "parse_dynamic_functions": False,
                                "parse_conditions": False,
                                "derive_by_type": {},
                                "copy": "yes",
                            }
                        }
                    }
                )
            ),
            ".. spec:: A\n   :id: S_001\n   :rel: S_001\n",
        )
    ],
    indirect=True,
)
def test_what_a_declaration_of_a_link_type_cannot_give(test_app: Any) -> None:
    """The display, ``copy`` and ``allow_dead_links`` keys are a declaration's, of
    their shape; ``parse_variants``, ``parse_dynamic_functions``,
    ``parse_conditions`` and ``derive_by_type`` are not, on any link type."""
    app = test_app
    app.build()
    assert build_warnings(app) == [
        "WARNING: needs_types['spec'].links['rel'] has a 'copy' that is not a boolean "
        "(got str); the key is ignored [needs.config]",
        "WARNING: needs_types['spec'].links['rel'] has unknown keys 'parse_variants', "
        "'parse_dynamic_functions', 'parse_conditions', 'derive_by_type'; known keys "
        "are description, schema, default, predicates, derive, incoming, outgoing, "
        "copy, allow_dead_links, color, style, style_part, style_start, style_end; "
        "the keys are ignored [needs.config]",
    ]
    union = _schema(app).get_link_field("rel")
    assert union is not None
    assert union.copy is False
    rel = _field(app, None, "rel")
    assert (rel.parse_variants, rel.parse_conditions) == (False, True)
    assert _needs(app)["S_001"]["rel"] == ["S_001"]


@pytest.mark.parametrize(
    "test_app",
    [
        _project(
            _conf(
                {
                    "e": {"title": "E", "prefix": "E_", "links": {"both": {}}},
                    "f": {
                        "title": "F",
                        "prefix": "F_",
                        "fields": {"both": {"schema": {"type": "string"}}},
                    },
                }
            ),
            ".. e:: A\n   :id: E_001\n   :both: F_001\n\n"
            ".. f:: B\n   :id: F_001\n   :both: x\n",
        )
    ],
    indirect=True,
)
def test_a_name_under_fields_and_links_is_a_field(test_app: Any) -> None:
    """A name one type declares under ``fields`` and another under ``links``, neither
    declared otherwise, is a field, whichever type comes first: the ``links`` entry is
    refused as it is for any field."""
    app = test_app
    app.build()
    assert build_warnings(app) == [
        _conflict(
            "needs_types['e'].links['both'] declares 'both', which is a field, not a "
            "link type"
        ),
        "<srcdir>/index.rst:4: WARNING: Field 'both' is not declared on need type "
        "'e' and cannot be set in need 'E_001'; the value 'F_001' is ignored "
        "[needs.undeclared_for_type]",
    ]
    assert _values(app, "both") == {"E_001": (None,), "F_001": ("x",)}
    assert _schema(app).get_link_field("both") is None


@pytest.mark.parametrize(
    "test_app",
    [
        _project(
            _conf(
                {
                    "b": {"title": "B", "prefix": "B_", "links": {"late": {}}},
                    "c": {
                        "title": "C",
                        "prefix": "C_",
                        "inherits": "d",
                        "links": {"child": {}},
                    },
                    "a": {"title": "A", "prefix": "A_", "links": {"early": {}}},
                    "d": {"title": "D", "prefix": "D_", "links": {"parent": {}}},
                },
                "needs_links = {'zeta': {}, 'alpha': {}}\n"
                "needs_extra_links = [{'option': 'mid'}]\n",
            ),
            ".. a:: A\n   :id: A_001\n",
        )
    ],
    indirect=True,
)
def test_the_link_types_declared_on_need_types_alone_come_last(test_app: Any) -> None:
    """The link types declared on need types alone come after the ``needs_links`` and
    ``needs_extra_links`` ones, in the order their first root declarations are
    resolved -- a parent before its children."""
    app = test_app
    app.build()
    names = [link.name for link in _schema(app).iter_link_fields()]
    assert names == [
        "zeta",
        "alpha",
        "links",
        "parent_needs",
        "mid",
        "late",
        "parent",
        "child",
        "early",
    ]


@pytest.mark.parametrize(
    ("extra", "warning"),
    [
        pytest.param(
            "needs_string_links = {'s': {'regex': r'^(?P<value>R_\\d+)$', "
            "'link_url': 'http://x/{{value}}', 'link_name': '{{value}}', "
            "'options': [NAME]}}\n",
            "WARNING: needs_string_links['s']: 'options' names NAME, which is not a "
            "registered need field, so it can never match. [needs.string_link]",
            id="string-links",
        ),
        pytest.param(
            "needs_card_layouts = {'card': {'footer': ['field:' + NAME]}}\n",
            "WARNING: needs_card_layouts['card']: footer element references the need "
            "field NAME, which is not registered; it will render empty. "
            "[needs.card_layout]",
            id="card-layouts",
        ),
    ],
)
def test_the_configuration_readers_read_it_as_a_needs_links_one(
    make_app: Any, tmp_path: Path, extra: str, warning: str
) -> None:
    """The readers of the configuration that run before the schema is built read a
    link type declared on need types alone as they read one of ``needs_links``."""
    found = []
    for name in ("verifies", "blocks"):
        srcdir = tmp_path / name
        srcdir.mkdir()
        conf = _conf(
            _types(req={"links": {"verifies": {}}}),
            f"needs_links = {{'blocks': {{}}}}\nNAME = {name!r}\n" + extra,
        )
        (srcdir / "conf.py").write_text(conf, encoding="utf-8")
        (srcdir / "index.rst").write_text("Case\n====\n", encoding="utf-8")
        app = make_app("needs", srcdir=srcdir)
        app.build()
        found.append(build_warnings(app))
        app.cleanup()
    assert found == [
        [warning.replace("NAME", repr(name))] for name in ("verifies", "blocks")
    ]


def test_a_variant_option_naming_it_is_refused_as_a_needs_links_one(
    make_app: Any, tmp_path: Path
) -> None:
    """``needs_variant_options`` may not name a link type declared on need types
    alone, as it may not name one of ``needs_links``."""
    for name in ("verifies", "blocks"):
        srcdir = tmp_path / name
        srcdir.mkdir()
        conf = _conf(
            _types(req={"links": {"verifies": {}}}),
            f"needs_links = {{'blocks': {{}}}}\nneeds_variant_options = [{name!r}]\n",
        )
        (srcdir / "conf.py").write_text(conf, encoding="utf-8")
        (srcdir / "index.rst").write_text("Case\n====\n", encoding="utf-8")
        with pytest.raises(NeedsConfigException) as exc_info:
            make_app("needs", srcdir=srcdir)
        assert str(exc_info.value) == (
            f"Variant option `{name}` is not added in needs_fields. This is not "
            "allowed."
        )
