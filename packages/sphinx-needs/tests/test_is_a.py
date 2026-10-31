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

import io
import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, Mock, patch

import pytest

from sphinx_needs import filter_common
from sphinx_needs.config import _NEEDS_CONFIG, NeedsSphinxConfig
from sphinx_needs.data import NeedsCoreFields, SphinxNeedsData
from sphinx_needs.derive import filter_problem
from sphinx_needs.filter_common import filter_needs_and_parts, filter_single_need
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
    types = NeedsSphinxConfig(app.config).is_a_types
    assert types is not None
    assert {name: sorted(types[name]) for name in SELECTS} == {
        "req": ["hw_req", "req", "sys_req"],
        "sys_req": ["hw_req", "sys_req"],
        "hw_req": ["hw_req"],
        "spec": ["spec"],
        "stray": ["stray"],
    }
    assert "nope" not in types


#: :data:`INDEX` with a needextend per declared type, and one naming no type
EXTENDS_INDEX = INDEX + "".join(
    f"\n.. needextend:: \"c.is_a('{name}')\"\n   :+tags: is_{name}\n"
    for name in [*SELECTS, "nope"]
)


def _line(index: str, text: str) -> int:
    """The line of the document :func:`_project` writes on which *text* starts: the
    project adds a title of three lines above *index*."""
    return 3 + 1 + index[: index.index(text)].count("\n")


def _unknown(name: str, filter_string: str | None = None, hint: str = "") -> str:
    """The warning for a ``c.is_a`` literal naming no need type, without a location."""
    filter_string = filter_string or f"c.is_a({name!r})"
    return (
        f"WARNING: Filter {filter_string!r} names {name!r}, which is not a need type"
        f"{hint}; c.is_a({name!r}) selects no need [needs.filter_type]"
    )


@pytest.mark.xfail(strict=True, reason="pin: a type name no type has is not reported")
@pytest.mark.parametrize("test_app", [_project(EXTENDS_INDEX)], indirect=True)
def test_a_needextend_filter_reads_it(test_app: Any) -> None:
    """One word is an id unless it is quoted; the filter is evaluated once per type, and
    the one naming no need type is reported where it is written."""
    app = test_app
    app.build()
    line = _line(EXTENDS_INDEX, ".. needextend:: \"c.is_a('nope')\"")
    assert build_warnings(app) == [
        INHERITS_NOPE,
        f"<srcdir>/index.rst:{line}: {_unknown('nope')}",
    ]
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
        # a `c` read otherwise reads the document, as before `c.is_a`
        ("getattr(c, 'this_doc')()", {"getattr", "docname"}),
        ("[c for c in tags if c]", {"tags"}),
    ],
)
def test_what_a_check_reads(filter_string: str, reads: set[str]) -> None:
    assert filter_names(filter_string).names == frozenset(reads)


#: two projects with the same document and filters, and different ``inherits``
TWO_PROJECTS = {
    "sys": 'sys_req = { title = "System requirement", prefix = "SR_", inherits = "req" }',
    "spec": 'spec = { title = "Specification", prefix = "S_", inherits = "req" }',
}

TWO_PROJECTS_INDEX = """\
Case
====

.. req:: A requirement
   :id: REQ_001

.. sys_req:: A system requirement
   :id: SYS_001

.. sys_req:: Another system requirement
   :id: SYS_002

.. spec:: A specification
   :id: SPEC_001

.. impl:: Links them all
   :id: IMPL_001
   :links: REQ_001, SYS_001, SYS_002, SPEC_001

.. needextend:: "c.is_a('req')"
   :+tags: req_like
"""

#: what ``c.is_a('req')`` selects in each project
TWO_PROJECTS_SELECT = {
    "sys": ["REQ_001", "SYS_001", "SYS_002"],
    "spec": ["REQ_001", "SPEC_001"],
}


def _two_projects_toml(inherits: str) -> str:
    """The default types, ``req``, ``sys_req`` and ``spec``, one of the last two
    inheriting from ``req``, and a derived count through the same filter."""
    other = "sys" if inherits == "spec" else "spec"
    other_entry = TWO_PROJECTS[other].split(", inherits")[0] + " }"
    return f"""\
[needs.types]
req = {{ title = "Requirement", prefix = "R_" }}
{TWO_PROJECTS[inherits]}
{other_entry}
impl = {{ title = "Implementation", prefix = "I_" }}

[needs.fields.n_req_like]
schema = {{ type = "integer" }}
derive = {{ kind = "count", over = "links", where = "c.is_a('req')" }}
"""


@pytest.mark.parametrize(
    "order", [("sys", "spec", "sys"), ("spec", "sys", "spec")], ids="-".join
)
def test_each_project_reads_its_own_types_in_one_process(
    order: tuple[str, ...], make_app: Any, tmp_path: Path
) -> None:
    """The compiled filter is cached per string and shared by every project a process
    builds, so the need types are passed per call, never compiled in: two projects with
    different ``inherits`` and the same ``c.is_a('req')`` (a needextend filter, on the
    fast tier, and a derived field's ``where``, need by need) each select by their own,
    whichever builds first, and the first again after the second."""
    for step, inherits in enumerate(order):
        srcdir = tmp_path / f"{step}-{inherits}"
        srcdir.mkdir()
        (srcdir / "conf.py").write_text(CONF.replace("needs_build_json = True\n", ""))
        (srcdir / "ubproject.toml").write_text(_two_projects_toml(inherits))
        (srcdir / "index.rst").write_text(TWO_PROJECTS_INDEX)
        app = make_app(
            srcdir=srcdir, buildername="needs", freshenv=True, warning=io.StringIO()
        )
        app.build()
        # a second application in one process re-registers Sphinx's own nodes, which
        # Sphinx warns about: the project's own findings are the needs ones
        assert [w for w in build_warnings(app) if "[needs." in w] == [], inherits
        view = SphinxNeedsData(app.env).get_needs_view()
        tagged = sorted(i for i, need in view.items() if "req_like" in need["tags"])
        assert tagged == TWO_PROJECTS_SELECT[inherits], (step, inherits)
        assert view["IMPL_001"]["n_req_like"] == len(TWO_PROJECTS_SELECT[inherits]), (
            step,
            inherits,
        )


# --- a c.is_a literal naming no need type is reported (#2402) ---

#: a derived count whose ``where`` names no need type, over three candidates
DERIVE_TOML = (
    TYPES
    + """
[needs.types.impl]
title = "Implementation"
prefix = "I_"

[needs.fields.n_rq]
schema = { type = "integer" }
derive = { kind = "count", over = "links", where = "c.is_a('rq')" }
"""
)


@pytest.mark.xfail(strict=True, reason="pin: a type name no type has is not reported")
@pytest.mark.parametrize(
    "test_app",
    [
        _project(
            INDEX + "\n.. impl:: Links three\n   :id: IMPL_001\n"
            "   :links: REQ_001, SYS_001, HW_001\n",
            toml=DERIVE_TOML,
        )
    ],
    indirect=True,
)
def test_a_derive_where_is_reported_once_whatever_it_is_evaluated_on(
    test_app: Any,
) -> None:
    """A ``where`` is evaluated candidate by candidate, and has no location: the string
    is reported once, with the type its name is closest to."""
    app = test_app
    app.build()
    assert build_warnings(app) == [
        INHERITS_NOPE,
        _unknown("rq", hint=" (did you mean 'req'?)"),
    ]
    assert SphinxNeedsData(app.env).get_needs_view()["IMPL_001"]["n_rq"] == 0


#: a filter of a needtable, and what it reports: the name and its hint, or nothing
TABLE_FILTERS = [
    ("c.is_a('req')", None),
    ("c.is_a('nope')", ("nope", "")),
    ("c.is_a('rq')", ("rq", " (did you mean 'req'?)")),
    ("c.is_a('Requirement')", ("Requirement", " (did you mean 'req'?)")),
    # the index selects no need to evaluate it on
    ("type == 'none' and c.is_a('rq')", ("rq", " (did you mean 'req'?)")),
    # answered by the eval tier
    ("c.is_a('rq') == True", ("rq", " (did you mean 'req'?)")),
    # no literal: the name is each need's own value
    ("c.is_a(type)", None),
    ("c.is_a(lineage)", None),
]


def _table_index(filter_string: str) -> str:
    return INDEX + f"\n.. needtable::\n   :filter: {filter_string}\n"


@pytest.mark.parametrize(
    ("test_app", "filter_string", "reported"),
    [
        pytest.param(
            _project(_table_index(filter_string), toml=FIELD_TOML, buildername="html"),
            filter_string,
            reported,
            id=filter_string,
            marks=[]
            if reported is None
            else [pytest.mark.xfail(strict=True, reason="pin: not reported")],
        )
        for filter_string, reported in TABLE_FILTERS
    ],
    indirect=["test_app"],
)
def test_a_view_filter_reports_a_literal_naming_no_type(
    test_app: Any, filter_string: str, reported: tuple[str, str] | None
) -> None:
    """Whichever tier answers the string, and even where the index leaves no need to
    evaluate it on, a literal naming no need type is reported at the view, with the type
    its name is close to or the title of; a name that is no literal is not."""
    app = test_app
    app.build()
    expected = [INHERITS_NOPE]
    if reported is not None:
        name, hint = reported
        line = _line(_table_index(filter_string), ".. needtable::")
        expected.append(
            f"<srcdir>/index.rst:{line}: {_unknown(name, filter_string, hint)}"
        )
    assert build_warnings(app) == expected


#: two documents, each with a needtable of the same filter naming no need type
OTHER = """\
Other
=====

.. needtable::
   :filter: c.is_a('rq')
"""

TWO_DOCUMENTS_INDEX = (
    INDEX
    + "\n.. needtable::\n   :filter: c.is_a('rq')\n"
    + ("\n.. toctree::\n\n   other\n")
)


def _two_documents(parallel: int) -> dict[str, Any]:
    project = _project(TWO_DOCUMENTS_INDEX, buildername="html")
    project["files"].append((Path("other.rst"), OTHER))
    project["parallel"] = parallel
    return project


def _two_documents_warnings() -> list[str]:
    unknown = _unknown("rq", hint=" (did you mean 'req'?)")
    return [
        INHERITS_NOPE,
        f"<srcdir>/index.rst:{_line(TWO_DOCUMENTS_INDEX, '.. needtable::')}: {unknown}",
        f"<srcdir>/other.rst:4: {unknown}",
    ]


@pytest.mark.xfail(strict=True, reason="pin: a type name no type has is not reported")
@pytest.mark.parametrize(
    "test_app",
    [_two_documents(0), _two_documents(2)],
    indirect=True,
    ids=["serial", "parallel"],
)
def test_one_filter_in_two_places_is_reported_at_each(test_app: Any) -> None:
    """Once per filter and location: the same string in two documents is reported at
    each, once, and a parallel build reports what a serial one does (every filter that
    can hold ``c`` is evaluated in the main process)."""
    app = test_app
    app.build()
    assert sorted(build_warnings(app)) == sorted(_two_documents_warnings())


@pytest.mark.xfail(strict=True, reason="pin: a type name no type has is not reported")
@pytest.mark.parametrize("test_app", [_two_documents(0)], indirect=True)
def test_each_build_reports_again(test_app: Any) -> None:
    """Once per build: a second build of the same application reports again."""
    app = test_app
    app.build()
    app.build(force_all=True)
    reported = [w for w in build_warnings(app) if w.endswith("[needs.filter_type]")]
    assert len(reported) == 4


@pytest.mark.xfail(strict=True, reason="pin: a type name no type has is not reported")
@pytest.mark.parametrize(
    "test_app",
    [_project(conf=CONF + "needs_warnings = {'odd': \"c.is_a('rq')\"}\n")],
    indirect=True,
)
def test_a_warnings_filter_says_which_it_is(test_app: Any) -> None:
    """A filter configured outside every document has no location: the report says
    which it is, as a failed one does."""
    app = test_app
    app.build()
    assert build_warnings(app) == [
        INHERITS_NOPE,
        _unknown("rq", hint=" (did you mean 'req'?)").replace(
            " [needs.filter_type]", " (from warning filter 'odd') [needs.filter_type]"
        ),
    ]


def test_nothing_is_reported_before_a_build_gives_the_types() -> None:
    """With no need types (no build has prepared them) nothing is known about a name, so
    none is reported: ``c.is_a`` then answers each type itself alone."""
    _NEEDS_CONFIG.clear()  # no name reported by an earlier build is remembered
    config = Mock(spec=["filter_data", "variant_data_proxy", "is_a_types"])
    config.filter_data = {}
    config.variant_data_proxy = None
    config.is_a_types = None
    with patch.object(filter_common, "log_warning") as warn:
        assert filter_needs_and_parts([], config, "c.is_a('rq')") == []
        assert filter_single_need(MagicMock(), config, "c.is_a('rq')") is False
    assert warn.call_args_list == []
