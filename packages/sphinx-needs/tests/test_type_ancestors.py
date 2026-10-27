"""``type_ancestors``: a need's type and the types it inherits from, nearest first.

A core field every need carries, computed from the parents ``inherits`` leaves once it is
checked (``needs.type_inherits`` drops an ``inherits`` naming no need type, and every one
on a cycle), so that a filter, a derived field's ``where``, a ``needextend`` filter and a
schema rule can follow ``inherits`` with no syntax of their own:
``"req" in type_ancestors``. It is read-only -- no directive option, no ``needextend``,
no assignment -- and left out of ``needs.json`` unless the project opts in through
``needs_json_exclude_fields``; a need read from a needs.json gets it from the reading
project's own types. What filters select is pinned in the filter conformance corpus
(``tests/fixtures/filter_conformance.toml``, case ``type-ancestors-follow-inherits``),
and a schema rule's view of it in ``tests/schema/fixtures/fields.yml``.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest

from sphinx_needs.api.need import _import_key_sets
from sphinx_needs.config import _NEEDS_CONFIG, NeedsSphinxConfig
from sphinx_needs.data import NeedsCoreFields, SphinxNeedsData
from sphinx_needs.derive import filter_problem
from sphinx_needs.exceptions import NeedsApiConfigWarning
from sphinx_needs.functions.order import filter_names
from sphinx_needs.needs_schema import FieldsSchema
from sphinx_needs_testkit import build_warnings

CONF = """\
extensions = ["sphinx_needs"]
needs_from_toml = "ubproject.toml"
needs_build_json = True
"""

#: req <- safety_req <- asil_d_req, an unrelated root, and an inherits naming no type
TYPES = """\
[needs.types.req]
title = "Requirement"
prefix = "R_"

[needs.types.safety_req]
title = "Safety requirement"
prefix = "SR_"
inherits = "req"

[needs.types.asil_d_req]
title = "ASIL D requirement"
prefix = "AD_"
inherits = "safety_req"

[needs.types.spec]
title = "Specification"
prefix = "S_"

[needs.types.stray]
title = "Stray"
prefix = "ST_"
inherits = "nope"
"""

INDEX = """\
.. req:: A requirement
   :id: REQ_001

.. safety_req:: A safety requirement
   :id: SREQ_001

.. asil_d_req:: An ASIL D requirement
   :id: ASIL_001

.. spec:: An unrelated root
   :id: SPEC_001

.. stray:: Inherits no need type
   :id: STRAY_001
"""

#: what each need of :data:`INDEX` carries
ANCESTORS = {
    "REQ_001": ["req"],
    "SREQ_001": ["safety_req", "req"],
    "ASIL_001": ["asil_d_req", "safety_req", "req"],
    "SPEC_001": ["spec"],
    "STRAY_001": ["stray"],
}

INHERITS_NOPE = (
    "WARNING: Need type 'stray' inherits 'nope', which is not a need type; its "
    "inherits is ignored. [needs.type_inherits]"
)


def _project(
    index: str = INDEX,
    toml: str = TYPES,
    conf: str = CONF,
    buildername: str = "needs",
    **files: str,
) -> dict[str, Any]:
    return {
        "buildername": buildername,
        "files": [
            (Path("conf.py"), conf),
            (Path("ubproject.toml"), toml),
            (Path("index.rst"), "Case\n====\n\n" + index),
            *((Path(name), text) for name, text in files.items()),
        ],
    }


def _json_needs(app: Any) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    data = json.loads(Path(app.outdir, "needs.json").read_text(encoding="utf-8"))
    version = data["versions"][data["current_version"]]
    return version["needs"], version["needs_schema"]


# -- FieldsSchema -----------------------------------------------------------------------


def test_the_schema_answers_each_type_with_its_ancestors_nearest_first() -> None:
    schema = FieldsSchema()
    schema.set_type_parents({"safety_req": "req", "asil_d_req": "safety_req"})
    assert schema.type_ancestors("asil_d_req") == ("asil_d_req", "safety_req", "req")
    assert schema.type_ancestors("safety_req") == ("safety_req", "req")
    assert schema.type_ancestors("req") == ("req",)
    # a type the schema knows no parent of is a root: an undeclared one included
    assert schema.type_ancestors("external_type") == ("external_type",)
    # the schema of one need type answers the same
    schema.freeze()
    assert schema.for_type("safety_req").type_ancestors("asil_d_req") == (
        "asil_d_req",
        "safety_req",
        "req",
    )


def test_a_schema_never_told_the_parents_answers_the_type_alone() -> None:
    assert FieldsSchema().type_ancestors("req") == ("req",)


def test_the_parents_are_told_once_and_before_the_schema_is_frozen() -> None:
    schema = FieldsSchema()
    schema.set_type_parents({"b": "a"})
    with pytest.raises(ValueError, match="already set"):
        schema.set_type_parents({"b": "a"})
    frozen = FieldsSchema()
    frozen.freeze()
    with pytest.raises(TypeError, match="cannot be changed"):
        frozen.set_type_parents({"b": "a"})


@pytest.mark.parametrize(
    "parents", [{"a": "a"}, {"a": "b", "b": "a"}, {"a": "b", "b": "c", "c": "b"}]
)
def test_parents_on_a_cycle_are_refused(parents: dict[str, str]) -> None:
    """``create_schema`` passes the forest ``inherits`` leaves once checked; a map with a
    cycle, which no walk up would end on, is refused rather than followed."""
    with pytest.raises(ValueError, match="cycle"):
        FieldsSchema().set_type_parents(parents)


# -- the core field ---------------------------------------------------------------------


def test_the_core_field_is_read_only_and_left_out_of_needs_json() -> None:
    """Modelled on ``type_name``: computed by every project that reads a need, so left
    out when one is imported or external, and written to needs.json only on request."""
    params = NeedsCoreFields["type_ancestors"]
    assert params["schema"] == {
        "type": "array",
        "items": {"type": "string"},
        "default": [],
    }
    assert params.get("exclude_json") is True
    assert params.get("exclude_import") is True
    assert params.get("exclude_external") is True
    for flag in (
        "add_to_field_schema",
        "allow_default",
        "allow_extend",
        "allow_df",
        "allow_variants",
        "show_in_layout",
    ):
        assert not params.get(flag), flag
    default_excluded = NeedsSphinxConfig.__dataclass_fields__["json_exclude_fields"]
    assert "type_ancestors" in default_excluded.default_factory()  # type: ignore[misc]
    for reader in ("import", "external"):
        known, omitted = _import_key_sets(FieldsSchema(), reader=reader)
        assert "type_ancestors" in known and "type_ancestors" in omitted, reader


@pytest.mark.parametrize("test_app", [_project()], indirect=True)
def test_every_need_carries_its_type_and_ancestors(test_app: Any) -> None:
    app = test_app
    app.build()
    assert build_warnings(app) == [INHERITS_NOPE]
    view = SphinxNeedsData(app.env).get_needs_view()
    assert {i: list(n["type_ancestors"]) for i, n in view.items()} == ANCESTORS
    # by default it is not in needs.json, neither on a need nor in the schema
    needs, needs_schema = _json_needs(app)
    assert all("type_ancestors" not in need for need in needs.values())
    assert "type_ancestors" not in needs_schema["properties"]


@pytest.mark.parametrize(
    "test_app",
    [_project(conf=CONF + 'needs_json_exclude_fields = ["type_prefix"]\n')],
    indirect=True,
)
def test_needs_json_writes_it_when_the_project_opts_in(test_app: Any) -> None:
    app = test_app
    app.build()
    needs, needs_schema = _json_needs(app)
    assert {i: n["type_ancestors"] for i, n in needs.items()} == ANCESTORS
    assert needs_schema["properties"]["type_ancestors"]["type"] == "array"


def test_a_need_cannot_be_given_one() -> None:
    """Not a directive option, nor a value ``need[...] = ...`` writes: it follows the
    type, which is immutable too."""
    from sphinx_needs.need_item import NeedItem

    assert "type_ancestors" in NeedItem._immutable_core


#: a project that declares a field of each name the three ways a project can
RESERVED_TOML = (
    TYPES
    + """
[needs.fields.type_name]
schema = { type = "string" }

[needs.fields.type_ancestors]
schema = { type = "string" }

[needs.types.req.fields.type_name]
schema = { type = "string" }

[needs.types.req.fields.type_ancestors]
schema = { type = "string" }
"""
)


@pytest.mark.parametrize(
    "test_app",
    [
        _project(
            ".. req:: Sets both\n   :id: REQ_001\n   :type_name: mine\n"
            "   :type_ancestors: mine\n",
            toml=RESERVED_TOML,
        )
    ],
    indirect=True,
)
def test_the_name_is_reserved_as_type_names_is(test_app: Any) -> None:
    """A project field of the name is refused as one of ``type_name`` is, route by
    route: a need type's entry is a ``needs.type_conflict``, a ``needs_fields`` entry
    declares no field (the core field's value stands, and an author cannot set it), and
    neither name is a directive option."""
    app = test_app
    app.build()
    warnings = build_warnings(app)
    for name in ("type_name", "type_ancestors"):
        assert (
            f"WARNING: needs_types['req'].fields['{name}'] declares '{name}', which is "
            "not a field; the entry is ignored [needs.type_conflict]"
        ) in warnings
        assert (
            f"<srcdir>/index.rst:4: WARNING: Unknown option '{name}' [needs.directive]"
            in warnings
            or f"<srcdir>/index.rst:5: WARNING: Unknown option '{name}' [needs.directive]"
            in warnings
        ), warnings
    assert sum("Unknown option" in w for w in warnings) == 2, warnings
    view = SphinxNeedsData(app.env).get_needs_view()
    assert (view["REQ_001"]["type_name"], list(view["REQ_001"]["type_ancestors"])) == (
        "Requirement",
        ["req"],
    )


@pytest.mark.parametrize("name", ["type_name", "type_ancestors"])
def test_an_extension_cannot_register_a_field_of_the_name(name: str) -> None:
    with pytest.raises(NeedsApiConfigWarning, match="core field name"):
        _NEEDS_CONFIG.add_field(name, "mine", "test")


@pytest.mark.parametrize(
    "test_app",
    [
        _project(
            INDEX
            + "\n.. needextend:: SPEC_001\n   :type_ancestors: req\n"
            + "\n.. needextend:: 'req' in type_ancestors and type != 'req'\n"
            + "   :status: inherited\n"
            # one word is an id unless it is quoted
            + "\n.. needextend:: \"c.is_a('safety_req')\"\n   :tags: safety\n"
        )
    ],
    indirect=True,
)
def test_needextend_cannot_set_it_and_its_filter_reads_it(test_app: Any) -> None:
    app = test_app
    app.build()
    warnings = build_warnings(app)
    assert INHERITS_NOPE in warnings
    assert any("type_ancestors" in w and "needextend" in w for w in warnings), warnings
    view = SphinxNeedsData(app.env).get_needs_view()
    assert list(view["SPEC_001"]["type_ancestors"]) == ["spec"]
    assert {i: n["status"] for i, n in view.items()} == {
        "REQ_001": None,
        "SREQ_001": "inherited",
        "ASIL_001": "inherited",
        "SPEC_001": None,
        "STRAY_001": None,
    }
    assert sorted(i for i, n in view.items() if "safety" in n["tags"]) == [
        "ASIL_001",
        "SREQ_001",
    ]


@pytest.mark.parametrize(
    "test_app",
    [
        _project(
            INDEX
            + "\n.. needtable::\n   :filter: 'req' in type_ancestors\n"
            + "   :columns: id, type_ancestors\n   :style: table\n",
            buildername="html",
        )
    ],
    indirect=True,
)
def test_a_needtable_lists_it_as_a_column(test_app: Any) -> None:
    app = test_app
    app.build()
    html = Path(app.outdir, "index.html").read_text(encoding="utf-8")
    cells = re.findall(r'<td class="needs_type_ancestors"><p>(.*?)</p></td>', html)
    # by id: ASIL_001, REQ_001, SREQ_001
    assert cells == [
        "asil_d_req<em>; </em>safety_req<em>; </em>req",
        "req",
        "safety_req<em>; </em>req",
    ]


IMPORTED = json.dumps(
    {
        "current_version": "1.0",
        "versions": {
            "1.0": {
                "needs": {
                    "IMP_001": {
                        "id": "IMP_001",
                        "type": "safety_req",
                        "title": "Imported",
                        "type_ancestors": ["something", "else"],
                    }
                }
            }
        },
    }
)


@pytest.mark.parametrize(
    "test_app",
    [_project(".. needimport:: imported.json\n", **{"imported.json": IMPORTED})],
    indirect=True,
)
def test_an_imported_need_takes_the_reading_projects_types(test_app: Any) -> None:
    app = test_app
    app.build()
    view = SphinxNeedsData(app.env).get_needs_view()
    assert list(view["IMP_001"]["type_ancestors"]) == ["safety_req", "req"]


# -- c.is_a -----------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("where", "problem"),
    [
        ("c.is_a('req')", None),
        ("c.is_a('req') and status == 'open'", None),
        ("c.is_a(type)", "calls 'c.is_a', which a declared rule cannot read"),
        ("c.is_a()", "calls 'c.is_a', which a declared rule cannot read"),
        ("c.is_a('a', 'b')", "calls 'c.is_a', which a declared rule cannot read"),
        ("c.is_a(name='req')", "calls 'c.is_a', which a declared rule cannot read"),
        (
            "c.is_a('req') and c.this_doc()",
            "calls 'c.this_doc', which a declared rule cannot read",
        ),
    ],
)
def test_a_derive_where_takes_is_a_with_a_literal_alone(
    where: str, problem: str | None
) -> None:
    """``c.is_a('<type>')`` reads the candidate alone, so a declared rule may read it,
    as ubCode does; any other shape of it, like every other ``c.`` check, it may not."""
    assert filter_problem(where) == problem


@pytest.mark.parametrize(
    ("filter_string", "reads"),
    [
        ("c.is_a('req')", {"type_ancestors"}),
        ("c.this_doc()", {"docname"}),
        (
            "c.is_a('req') and c.this_doc() and status",
            {"type_ancestors", "docname", "status"},
        ),
    ],
)
def test_what_a_check_reads(filter_string: str, reads: set[str]) -> None:
    assert filter_names(filter_string).names == frozenset(reads)
