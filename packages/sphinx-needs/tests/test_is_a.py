"""``c.is_a('req')``: a check for a need of a type, or of a type inheriting from it.

It reads the need's own type against the project's need type declarations, through
their ``inherits`` (once checked: ``needs.type_inherits`` drops an ``inherits`` naming no
need type, and every one on a cycle), and no field the need stores: a need carries no
list of its types. What filters select, tier by tier, is pinned in the filter
conformance corpus (``tests/fixtures/filter_conformance.toml``, case
``is-a-follows-inherits``), and a derived field's ``where`` in the derive corpus (case
``where-follows-inherits``); the unit tests of both tiers are in ``test_ubquery.py``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from sphinx_needs.config import NeedsSphinxConfig
from sphinx_needs.data import NeedsCoreFields, SphinxNeedsData
from sphinx_needs.derive import filter_problem
from sphinx_needs.filter_common import is_a_types
from sphinx_needs.functions.order import filter_names
from sphinx_needs_testkit import build_warnings

CONF = """\
extensions = ["sphinx_needs"]
needs_from_toml = "ubproject.toml"
needs_build_json = True
"""

#: req <- sys_req <- hw_req, an unrelated root, and an inherits naming no type
TYPES = """\
[needs.types.req]
title = "Requirement"
prefix = "R_"

[needs.types.sys_req]
title = "System requirement"
prefix = "SR_"
inherits = "req"

[needs.types.hw_req]
title = "Hardware requirement"
prefix = "HR_"
inherits = "sys_req"

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

.. sys_req:: A system requirement
   :id: SYS_001

.. hw_req:: A hardware requirement
   :id: HW_001

.. spec:: An unrelated root
   :id: SPEC_001

.. stray:: Inherits no need type
   :id: STRAY_001
"""

INHERITS_NOPE = (
    "WARNING: Need type 'stray' inherits 'nope', which is not a need type; its "
    "inherits is ignored. [needs.type_inherits]"
)

#: what ``c.is_a(x)`` selects in :data:`INDEX`, for each declared type ``x``
SELECTS = {
    "req": ["HW_001", "REQ_001", "SYS_001"],
    "sys_req": ["HW_001", "SYS_001"],
    "hw_req": ["HW_001"],
    "spec": ["SPEC_001"],
    "stray": ["STRAY_001"],
}


def _project(
    index: str = INDEX,
    toml: str = TYPES,
    conf: str = CONF,
    buildername: str = "needs",
) -> dict[str, Any]:
    return {
        "buildername": buildername,
        "files": [
            (Path("conf.py"), conf),
            (Path("ubproject.toml"), toml),
            (Path("index.rst"), "Case\n====\n\n" + index),
        ],
    }


def _json_needs(app: Any) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    data = json.loads(Path(app.outdir, "needs.json").read_text(encoding="utf-8"))
    version = data["versions"][data["current_version"]]
    return version["needs"], version["needs_schema"]


@pytest.mark.parametrize(
    "test_app",
    [_project(conf=CONF + "needs_json_exclude_fields = []\n")],
    indirect=True,
)
def test_a_need_carries_no_list_of_its_types(test_app: Any) -> None:
    """``c.is_a`` reads the declarations, so no core field holds a need's types: the
    core fields a need type gives are its name and its display, and needs.json writes no
    other key, even where the project writes every field."""
    app = test_app
    app.build()
    assert {name for name in NeedsCoreFields if name.startswith("type")} == {
        "type",
        "type_color",
        "type_name",
        "type_prefix",
        "type_style",
    }
    needs, needs_schema = _json_needs(app)
    assert sorted(needs) == sorted(SphinxNeedsData(app.env).get_needs_view())
    for need in needs.values():
        assert {key for key in need if key.startswith("type")} == {
            "type",
            "type_color",
            "type_name",
            "type_prefix",
            "type_style",
        }
        assert set(need) <= set(needs_schema["properties"])


@pytest.mark.parametrize("test_app", [_project()], indirect=True)
def test_the_build_gives_its_filters_the_declared_types(test_app: Any) -> None:
    """Each need type with itself and every type inheriting from it, transitively: what
    ``c.is_a`` reads, from the declarations once ``inherits`` is checked."""
    app = test_app
    app.build()
    assert build_warnings(app) == [INHERITS_NOPE]
    types = is_a_types(NeedsSphinxConfig(app.config))
    assert types is not None
    assert {name: sorted(types[name]) for name in SELECTS} == {
        "req": ["hw_req", "req", "sys_req"],
        "sys_req": ["hw_req", "sys_req"],
        "hw_req": ["hw_req"],
        "spec": ["spec"],
        "stray": ["stray"],
    }
    assert "nope" not in types


@pytest.mark.parametrize(
    "test_app",
    [
        _project(
            INDEX
            + "".join(
                f"\n.. needextend:: \"c.is_a('{name}')\"\n   :+tags: is_{name}\n"
                for name in [*SELECTS, "nope"]
            )
        )
    ],
    indirect=True,
)
def test_a_needextend_filter_reads_it(test_app: Any) -> None:
    """One word is an id unless it is quoted; the filter is evaluated once per type."""
    app = test_app
    app.build()
    assert build_warnings(app) == [INHERITS_NOPE]
    view = SphinxNeedsData(app.env).get_needs_view()
    for name, ids in SELECTS.items():
        assert sorted(i for i, n in view.items() if f"is_{name}" in n["tags"]) == ids
    assert not any("is_nope" in n["tags"] for n in view.values())


#: a project field that lists types, which ``c.is_a`` does not read
FIELD_TOML = (
    TYPES
    + """
[needs.fields.lineage]
schema = { type = "string" }
"""
)


@pytest.mark.parametrize(
    "test_app",
    [
        _project(
            ".. req:: A requirement\n   :id: REQ_001\n   :lineage: spec\n"
            "\n.. spec:: A specification\n   :id: SPEC_001\n"
            "\n.. needextend:: \"c.is_a('spec')\"\n   :status: spec_like\n",
            toml=FIELD_TOML,
        )
    ],
    indirect=True,
)
def test_is_a_reads_the_type_never_a_field(test_app: Any) -> None:
    """``c.is_a`` reads the need's type, never a field of the need, whatever it holds."""
    app = test_app
    app.build()
    assert build_warnings(app) == [INHERITS_NOPE]
    view = SphinxNeedsData(app.env).get_needs_view()
    assert view["REQ_001"]["lineage"] == "spec"
    assert {i: n["status"] for i, n in view.items()} == {
        "REQ_001": None,
        "SPEC_001": "spec_like",
    }


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
    """``c.is_a('<type>')`` reads the candidate's type alone, so a declared rule may
    read it, as ubCode does; any other shape of it, like every other ``c.`` check, it
    may not."""
    assert filter_problem(where) == problem


@pytest.mark.parametrize(
    ("filter_string", "reads"),
    [
        ("c.is_a('req')", {"type"}),
        ("c.this_doc()", {"docname"}),
        ("c.is_a('req') and c.this_doc() and status", {"type", "docname", "status"}),
    ],
)
def test_what_a_check_reads(filter_string: str, reads: set[str]) -> None:
    assert filter_names(filter_string).names == frozenset(reads)
