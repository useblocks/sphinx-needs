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
import re
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, Mock, patch

import pytest
from sphinx.util.parallel import parallel_available

from sphinx_needs import filter_common
from sphinx_needs._source_facets import namespace_reads
from sphinx_needs.config import _NEEDS_CONFIG, NeedsSphinxConfig
from sphinx_needs.data import NeedsCoreFields, SphinxNeedsData
from sphinx_needs.derive import filter_problem
from sphinx_needs.filter_common import filter_needs_and_parts, filter_single_need
from sphinx_needs.functions.order import filter_names
from sphinx_needs.ubquery import is_a_literals
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
derive = { kind = "count", over = "links", where = "WHERE" }
"""
)


@pytest.mark.parametrize(
    ("test_app", "where"),
    [
        pytest.param(
            _project(
                INDEX + "\n.. impl:: Links three\n   :id: IMPL_001\n"
                "   :links: REQ_001, SYS_001, HW_001\n",
                toml=DERIVE_TOML.replace("WHERE", where),
            ),
            where,
            id=where,
        )
        # the second raises on every candidate, which a ``where`` reads as "does not
        # pass", silently: the name is checked before either tier evaluates it
        for where in ["c.is_a('rq')", "c.is_a('rq') or tags.nope"]
    ],
    indirect=["test_app"],
)
def test_a_derive_where_is_reported_once_whatever_it_is_evaluated_on(
    test_app: Any, where: str
) -> None:
    """A ``where`` is evaluated candidate by candidate, and has no location: the string
    is reported once, with the type its name is closest to, however its evaluation
    ends."""
    app = test_app
    app.build()
    assert build_warnings(app) == [
        INHERITS_NOPE,
        _unknown("rq", where, hint=" (did you mean 'req'?)"),
    ]
    assert SphinxNeedsData(app.env).get_needs_view()["IMPL_001"]["n_rq"] == 0


#: two derived counts whose ``where`` misspell two different types
TWO_WHERES_TOML = (
    TYPES
    + """
[needs.types.impl]
title = "Implementation"
prefix = "I_"

[needs.fields.n_rq]
schema = { type = "integer" }
derive = { kind = "count", over = "links", where = "c.is_a('rq')" }

[needs.fields.n_sp]
schema = { type = "integer" }
derive = { kind = "count", over = "links", where = "c.is_a('sp')" }
"""
)


@pytest.mark.parametrize(
    "test_app",
    [
        _project(
            INDEX + "\n.. impl:: Links two\n   :id: IMPL_001\n"
            "   :links: REQ_001, SPEC_001\n",
            toml=TWO_WHERES_TOML,
        )
    ],
    indirect=True,
)
def test_two_wheres_naming_two_unknown_types_are_each_reported(test_app: Any) -> None:
    """Two filters with no place are two strings: each is reported once, the second
    is not taken for the first."""
    app = test_app
    app.build()
    assert sorted(build_warnings(app)) == sorted(
        [
            INHERITS_NOPE,
            _unknown("rq", hint=" (did you mean 'req'?)"),
            _unknown("sp"),
        ]
    )


#: a filter of a needtable, and what it reports: each name with its hint, in order
TABLE_FILTERS: list[tuple[str, list[tuple[str, str]]]] = [
    ("c.is_a('req')", []),
    ("c.is_a('nope')", [("nope", "")]),
    ("c.is_a('rq')", [("rq", " (did you mean 'req'?)")]),
    # too far from every type's name for a hint ('req' is 0.67 alike)
    ("c.is_a('rqq')", [("rqq", "")]),
    ("c.is_a('Requirement')", [("Requirement", " (did you mean 'req'?)")]),
    # each name, in the order written
    (
        "c.is_a('rq') or c.is_a('sp')",
        [("rq", " (did you mean 'req'?)"), ("sp", "")],
    ),
    # the index selects no need to evaluate it on
    ("type == 'none' and c.is_a('rq')", [("rq", " (did you mean 'req'?)")]),
    # answered by the eval tier
    ("c.is_a('rq') == True", [("rq", " (did you mean 'req'?)")]),
    # no literal: the name is each need's own value
    ("c.is_a(type)", []),
    ("c.is_a(lineage)", []),
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
        )
        for filter_string, reported in TABLE_FILTERS
    ],
    indirect=["test_app"],
)
def test_a_view_filter_reports_a_literal_naming_no_type(
    test_app: Any, filter_string: str, reported: list[tuple[str, str]]
) -> None:
    """Whichever tier answers the string, and even where the index leaves no need to
    evaluate it on, a literal naming no need type is reported at the view, with the type
    its name is close to or the title of; a name that is no literal is not."""
    app = test_app
    app.build()
    line = _line(_table_index(filter_string), ".. needtable::")
    assert build_warnings(app) == [
        INHERITS_NOPE,
        *(
            f"<srcdir>/index.rst:{line}: {_unknown(name, filter_string, hint)}"
            for name, hint in reported
        ),
    ]


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
    + "\n.. toctree::\n\n   other\n"
    + "".join(f"   page{i}\n" for i in range(5))
)


def _two_documents(parallel: int) -> dict[str, Any]:
    project = _project(TWO_DOCUMENTS_INDEX, buildername="html")
    project["files"].append((Path("other.rst"), OTHER))
    # Sphinx reads and writes in parallel from six documents on
    project["files"].extend(
        (Path(f"page{i}.rst"), f"Page {i}\n======\n") for i in range(5)
    )
    project["parallel"] = parallel
    return project


def _two_documents_warnings() -> list[str]:
    unknown = _unknown("rq", hint=" (did you mean 'req'?)")
    return [
        INHERITS_NOPE,
        f"<srcdir>/index.rst:{_line(TWO_DOCUMENTS_INDEX, '.. needtable::')}: {unknown}",
        f"<srcdir>/other.rst:4: {unknown}",
    ]


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
    # the parallel build did read in chunks (``index .. page0``), where forking is
    # available (POSIX): the warnings above are no serial build's
    status = re.sub(r"\x1b\[[0-9;]*m", "", app._status.getvalue())
    chunked = re.search(r"reading sources\.\.\. \[ *\d+%\] \S+ \.\. ", status)
    assert (chunked is not None) is (app.parallel > 1 and parallel_available)


@pytest.mark.parametrize("test_app", [_two_documents(0)], indirect=True)
def test_each_build_reports_again(test_app: Any) -> None:
    """Once per build: a second build of the same application reports again."""
    app = test_app
    app.build()
    app.build(force_all=True)
    reported = [w for w in build_warnings(app) if w.endswith("[needs.filter_type]")]
    assert len(reported) == 4


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


@pytest.mark.parametrize(
    "test_app",
    [
        _project(
            conf=CONF
            + "needs_warnings = {'first': \"c.is_a('rq')\", 'second': \"c.is_a('rq')\"}\n"
        )
    ],
    indirect=True,
)
def test_each_warnings_filter_is_reported_naming_itself(test_app: Any) -> None:
    """Two ``needs_warnings`` entries with the same string are two filters, each with
    its own origin: each is reported, naming itself."""
    app = test_app
    app.build()
    unknown = _unknown("rq", hint=" (did you mean 'req'?)")
    assert build_warnings(app) == [
        INHERITS_NOPE,
        *(
            unknown.replace(
                " [needs.filter_type]",
                f" (from warning filter {name!r}) [needs.filter_type]",
            )
            for name in ("first", "second")
        ),
    ]


@pytest.mark.parametrize(
    ("filter_string", "names"),
    [
        ("c.is_a('b') and c.is_a('a') or c.is_a('b')", ("b", "a")),
        # written first, nested deeper: an AST walk meets 'b' first
        ("(x and c.is_a('a')) or c.is_a('b')", ("a", "b")),
        ("c.is_a('a') == True", ("a",)),
        ("c.is_a(r'a') or c.is_a('a',)", ("a",)),
        # one literal, as Python reads it
        ("c.is_a('re' 'q')", ("req",)),
        ("c.is_a(type)", ()),
        ("c.is_a()", ()),
        ("c.is_a('a', 'b')", ()),
        ("c.is_a(name='a')", ()),
        ("x.is_a('a')", ()),
        ("c.is_a('a'", ()),
    ],
)
def test_the_names_a_filter_gives_as_a_literal(
    filter_string: str, names: tuple[str, ...]
) -> None:
    """A call of ``c.is_a`` with one string literal and nothing else gives a name of the
    string's own, in the order written, each once; any other shape gives none."""
    assert is_a_literals(filter_string) == names


def test_nothing_is_reported_before_a_build_gives_the_types() -> None:
    """With no need types (no build has prepared them) nothing is known about a name, so
    none is reported: ``c.is_a`` then answers each type itself alone."""
    _NEEDS_CONFIG.clear()  # no name reported by an earlier build is remembered
    config = Mock(
        spec=["filter_data", "variant_data_proxy", "is_a_types", "namespaced_ids"]
    )
    config.filter_data = {}
    config.variant_data_proxy = None
    config.is_a_types = None
    config.namespaced_ids = False
    with patch.object(filter_common, "log_warning") as warn:
        assert filter_needs_and_parts([], config, "c.is_a('rq')") == []
        assert filter_single_need(MagicMock(), config, "c.is_a('rq')") is False
    assert warn.call_args_list == []


# --- where a filter is tested need by need, it is reported where it is written (#2528) ---

#: the places whose filter is tested need by need, each written twice with the same
#: string: (the document's text, with ``{f}`` for the filter and ``{n}`` for what tells
#: the two apart, the configuration's extra text, the builder, the text the line of each
#: place starts with)
NEED_BY_NEED: dict[str, tuple[str, str, str, str]] = {
    "needflow-highlight": (
        ".. needflow::\n   :highlight: {f}\n",
        'needs_flow_engine = "graphviz"\n',
        "html",
        ".. needflow::",
    ),
    "needgantt-milestone_filter": (
        ".. needgantt:: G{n}\n   :milestone_filter: {f}\n",
        'extensions = ["sphinx_needs", "sphinxcontrib.plantuml"]\n',
        "dummy",
        ".. needgantt::",
    ),
    "needsequence-filter": (
        ".. needsequence:: S{n}\n   :start: LINKS_001\n   :filter: {f}\n",
        'extensions = ["sphinx_needs", "sphinxcontrib.plantuml"]\n',
        "dummy",
        ".. needsequence::",
    ),
    "link-condition": (
        ".. spec:: Links on a condition\n   :id: COND_00{n}\n   :links: REQ_001[{f}]\n",
        "",
        "dummy",
        ".. spec:: Links on a condition",
    ),
}

#: :data:`INDEX` with a need needsequence starts from, which sends a message to a need
#: that links another: the receiver its filter is tested on
LINKED_INDEX = INDEX + (
    "\n.. spec:: A message\n   :id: MSG_001\n   :links: SYS_001\n"
    "\n.. spec:: Links the others\n   :id: LINKS_001\n   :links: MSG_001\n"
)

NOSUCH = "c.is_a('nosuch')"


def _twice(place: str, filter_string: str = NOSUCH) -> str:
    """:data:`LINKED_INDEX` with the place written twice, the same string at each."""
    rst = NEED_BY_NEED[place][0]
    return LINKED_INDEX + "".join(
        "\n" + rst.format(f=filter_string, n=n) for n in (1, 2)
    )


def _lines(index: str, marker: str) -> list[int]:
    """The line of every place starting with *marker* in the document :func:`_project`
    writes (which adds a title of three lines above *index*)."""
    return [
        3 + number
        for number, line in enumerate(index.splitlines(), 1)
        if line.startswith(marker)
    ]


def _need_by_need_project(place: str) -> dict[str, Any]:
    _, conf, builder, _ = NEED_BY_NEED[place]
    return _project(_twice(place), conf=CONF + conf, buildername=builder)


@pytest.mark.parametrize(
    ("test_app", "place"),
    [
        pytest.param(_need_by_need_project(place), place, id=place)
        for place in NEED_BY_NEED
    ],
    indirect=["test_app"],
)
def test_a_need_by_need_place_is_reported_where_it_is_written(
    test_app: Any, place: str
) -> None:
    """A needflow highlight, a needgantt milestone filter, a needsequence filter and a
    link condition test their filter need by need: a literal naming no need type is
    reported once at each place the string is written, with its location, as the views
    report it and as ``needs.namespaced_ids_off`` is reported."""
    app = test_app
    app.build()
    index = _twice(place)
    lines = _lines(index, NEED_BY_NEED[place][3])
    assert len(lines) == 2
    reported = [w for w in build_warnings(app) if w.endswith("[needs.filter_type]")]
    assert sorted(reported) == sorted(
        f"<srcdir>/index.rst:{line}: {_unknown('nosuch', NOSUCH)}" for line in lines
    )


#: :data:`LINKED_INDEX` with two needflow highlights, and a constraint on two needs
CONSTRAINED_INDEX = (
    _twice("needflow-highlight")
    + "\n.. req:: Constrained\n   :id: REQ_101\n   :constraints: c1\n"
    + "\n.. req:: Constrained too\n   :id: REQ_102\n   :constraints: c1\n"
)

CONSTRAINED_CONF = (
    CONF
    + 'needs_flow_engine = "graphviz"\n'
    + f"needs_constraints = {{'c1': {{'check_0': {NOSUCH!r}, 'severity': 'LOW'}}}}\n"
    + "needs_constraint_failed_options = {'LOW': {'on_fail': [], 'style': []}}\n"
)


def _constrained_reports() -> list[str]:
    """Each highlight at its line, and the constraint, which has no location, once."""
    lines = _lines(CONSTRAINED_INDEX, ".. needflow::")
    return sorted(
        [
            *(
                f"<srcdir>/index.rst:{line}: {_unknown('nosuch', NOSUCH)}"
                for line in lines
            ),
            _unknown("nosuch", NOSUCH),
        ]
    )


def _filter_type(warnings: list[str]) -> list[str]:
    return sorted(w for w in warnings if w.endswith("[needs.filter_type]"))


@pytest.mark.parametrize(
    "test_app",
    [_project(CONSTRAINED_INDEX, conf=CONSTRAINED_CONF, buildername="html")],
    indirect=True,
)
def test_a_place_with_no_location_is_reported_once_per_build(test_app: Any) -> None:
    """A constraint has no location: tested on two needs, it is reported once, without
    one, beside the highlights that share its string, each at its own line."""
    app = test_app
    app.build()
    assert _filter_type(build_warnings(app)) == _constrained_reports()


@pytest.mark.parametrize(
    "test_app",
    [_project(CONSTRAINED_INDEX, conf=CONSTRAINED_CONF, buildername="html")],
    indirect=True,
)
def test_an_application_building_twice_reports_in_each_build(test_app: Any) -> None:
    """Per build, not per application: the second build reports what the first did."""
    app = test_app
    app.build()
    first = _filter_type(build_warnings(app))
    start = len(app._warning.getvalue())
    app.build(force_all=True)
    second = _filter_type(
        build_warnings(app._warning.getvalue()[start:], srcdir=app.srcdir)
    )
    assert first == second == _constrained_reports()


def test_an_incremental_build_reports_what_a_fresh_one_does(
    make_app: Any, tmp_path: Path
) -> None:
    """A document changed since the last build is read and written again: its
    highlights are reported at their lines, and the constraint once, as a fresh build of
    the same sources reports them."""

    def build(srcdir: Path, fresh: bool) -> list[str]:
        app = make_app(
            "html",
            srcdir=srcdir,
            freshenv=fresh,
            status=io.StringIO(),
            warning=io.StringIO(),
        )
        app.build()
        return _filter_type(build_warnings(app))

    def write(srcdir: Path, index: str) -> None:
        srcdir.mkdir(exist_ok=True)
        (srcdir / "conf.py").write_text(CONSTRAINED_CONF, encoding="utf-8")
        (srcdir / "ubproject.toml").write_text(TYPES, encoding="utf-8")
        (srcdir / "index.rst").write_text("Case\n====\n\n" + index, encoding="utf-8")

    incremental = tmp_path / "incremental"
    write(incremental, CONSTRAINED_INDEX)
    assert build(incremental, True) == _constrained_reports()
    # the same lines: a comment after the last directive
    changed = CONSTRAINED_INDEX + "\n.. a change\n"
    write(incremental, changed)
    fresh = tmp_path / "fresh"
    write(fresh, changed)
    assert build(incremental, False) == build(fresh, True) == _constrained_reports()


#: two needs whose ``effort`` is computed, a ``calc_sum`` over it whose filter is read
#: quietly first (to order the computation), a ``copy`` whose filter is matched quietly
#: first, and a constraint and a highlight sharing the string
QUIET_INDEX = (
    INDEX
    + '\n.. req:: Base one\n   :id: EFF_001\n   :base: 3\n   :effort: [[copy("base")]]\n'
    + '\n.. req:: Base two\n   :id: EFF_002\n   :base: 4\n   :effort: [[copy("base")]]\n'
    + f'\n.. req:: Sum\n   :id: SUM_001\n   :total: [[calc_sum("effort", filter={NOSUCH!r})]]\n'
    + f"\n.. req:: Copy\n   :id: COPY_001\n   :constraints: c1\n"
    f'   :base: [[copy("title", filter={NOSUCH!r})]]\n'
    + f"\n.. needflow::\n   :highlight: {NOSUCH}\n"
)


@pytest.mark.parametrize(
    "test_app",
    [
        _project(
            QUIET_INDEX,
            conf=CONSTRAINED_CONF
            + 'needs_extra_options = ["effort", "base", "total"]\n',
            buildername="html",
        )
    ],
    indirect=True,
)
def test_the_quiet_pre_passes_lose_no_report(test_app: Any) -> None:
    """The pre-passes that order the computed fields evaluate ``calc_sum``'s and
    ``copy``'s filters quietly: each place is still reported where it is evaluated for
    real -- the ``copy`` at its need, the highlight at its line, and the ``calc_sum``
    and the constraint, which share the key of a place with no location, once."""
    app = test_app
    app.build()
    unknown = _unknown("nosuch", NOSUCH)
    assert _filter_type(build_warnings(app)) == sorted(
        [
            f"<srcdir>/index.rst:{_line(QUIET_INDEX, '.. req:: Copy')}: {unknown}",
            f"<srcdir>/index.rst:{_line(QUIET_INDEX, '.. needflow::')}: {unknown}",
            unknown,
        ]
    )


#: an external need whose link condition names no need type
EXTERNAL_NEEDS = json.dumps(
    {
        "current_version": "1.0",
        "versions": {
            "1.0": {
                "needs": {
                    "A": {"id": "A", "type": "req", "title": "A", "content": ""},
                    "B": {
                        "id": "B",
                        "type": "req",
                        "title": "B",
                        "content": "",
                        "links": [f"A[{NOSUCH}]"],
                    },
                }
            }
        },
    }
)


def _external_project() -> dict[str, Any]:
    project = _project(
        conf=CONF + "needs_external_needs = [{'json_path': 'ext.json', "
        "'base_url': 'http://example.org', 'id_prefix': 'EXT_'}]\n"
    )
    project["files"].append((Path("ext.json"), EXTERNAL_NEEDS))
    return project


@pytest.mark.parametrize("test_app", [_external_project()], indirect=True)
def test_an_external_link_condition_names_the_external_need(test_app: Any) -> None:
    """An external need's link condition is written in another project: it has no
    location here, and the report names the external need, as its other link findings
    do."""
    app = test_app
    app.build()
    url = SphinxNeedsData(app.env).get_needs_view()["EXT_B"]["external_url"]
    assert _filter_type(build_warnings(app)) == [
        _unknown("nosuch", NOSUCH).replace(
            " [needs.filter_type]",
            f" (from the external need 'EXT_B': {url}) [needs.filter_type]",
        )
    ]


# --- a padded filter's c.is_a literal is read as the filter is (#2521) ---


@pytest.mark.parametrize("pad", ["", " ", "\t", " \t "])
def test_the_names_of_a_padded_filter(pad: str) -> None:
    """The names are read past the leading spaces and tabs ``eval`` reads past, as the
    filter is evaluated; no further (a newline then a space does not parse)."""
    assert is_a_literals(f"{pad}c.is_a('a') or c.is_a('b')") == ("a", "b")
    assert is_a_literals(f"\n {pad}c.is_a('a')") == ()


#: each pad, and the pad of a ``needpie`` line (docutils turns a tab into spaces)
PADDED = {"none": ("", ""), "space": (" ", " "), "tab": ("\t", " ")}


def _padded_index(line_pad: str) -> str:
    """:data:`INDEX` with a ``needpie`` line and two constrained needs."""
    return (
        INDEX
        + f"\n.. needpie:: P\n\n   {line_pad}{NOSUCH}\n   type == 'req'\n"
        + "\n.. req:: Constrained\n   :id: REQ_101\n   :constraints: c1\n"
        + "\n.. req:: Constrained too\n   :id: REQ_102\n   :constraints: c1\n"
    )


def _padded_project(pad: str, line_pad: str) -> dict[str, Any]:
    filter_string = f"{pad}{NOSUCH}"
    index = _padded_index(line_pad)
    conf = (
        CONF
        + f"needs_warnings = {{'w': {filter_string!r}}}\n"
        + f"needs_constraints = {{'c1': {{'check_0': {filter_string!r}, "
        "'severity': 'LOW'}}\n"
        + "needs_constraint_failed_options = {'LOW': {'on_fail': [], 'style': []}}\n"
    )
    return _project(index, conf=conf, buildername="html")


@pytest.mark.parametrize(
    ("test_app", "pad", "line_pad"),
    [
        pytest.param(_padded_project(pad, line_pad), pad, line_pad, id=name)
        for name, (pad, line_pad) in PADDED.items()
    ],
    indirect=["test_app"],
)
def test_a_padded_filter_naming_no_type_is_reported_as_written(
    test_app: Any, pad: str, line_pad: str
) -> None:
    """A filter with leading spaces or tabs is answered at every place, so a literal of it
    naming no need type is reported as the unpadded one is: a ``needs_warnings`` entry
    naming itself, a ``needpie`` line at its directive, a constraint once with no
    location; each quoting the filter as written."""
    app = test_app
    app.build()
    filter_string = f"{pad}{NOSUCH}"
    line = _line(_padded_index(line_pad), ".. needpie::")
    assert _filter_type(build_warnings(app)) == sorted(
        [
            _unknown("nosuch", filter_string).replace(
                " [needs.filter_type]", " (from warning filter 'w') [needs.filter_type]"
            ),
            f"<srcdir>/index.rst:{line}: {_unknown('nosuch', f'{line_pad}{NOSUCH}')}",
            _unknown("nosuch", filter_string),
        ]
    )


@pytest.mark.parametrize(
    "test_app",
    [
        _project(
            conf=CONF
            + "needs_warnings = {'w': \"\\n c.is_a('nosuch') or c.id.ns == 'x'\"}\n"
        )
    ],
    indirect=True,
)
def test_a_string_eval_refuses_gets_neither_text_report(test_app: Any) -> None:
    """The two text reports read a string as ``eval`` does, past its leading spaces and
    tabs alone: a newline then a space is refused, so the string gets its ``not valid``
    warning and neither a ``needs.filter_type`` nor a ``needs.namespaced_ids_off``."""
    app = test_app
    app.build()
    warnings = build_warnings(app)
    assert [w for w in warnings if w.endswith("[needs.filter_type]")] == []
    assert [w for w in warnings if w.endswith("[needs.namespaced_ids_off]")] == []
    filter_string = "\n c.is_a('nosuch') or c.id.ns == 'x'"
    (refused,) = [w for w in warnings if w.endswith("[needs.filter]")]
    assert refused.startswith(f"WARNING: Filter {filter_string!r} not valid. Error: ")
    assert refused.endswith(" (from warning filter 'w') [needs.filter]")


@pytest.mark.parametrize("pad", ["", " ", "\t", " \t "])
def test_the_two_text_readings_read_a_padded_string_alike(pad: str) -> None:
    """The names of the types and of the namespace values are both read past the
    leading spaces and tabs ``eval`` reads past, and no further."""
    filter_string = f"{pad}c.is_a('a') or c.id.ns == 'x'"
    assert is_a_literals(filter_string) == ("a",)
    assert namespace_reads(filter_string) == ("c.id.ns",)
    assert is_a_literals(f"\n {filter_string}") == ()
    assert namespace_reads(f"\n {filter_string}") == ()


# --- the two text reports of a filter are given together, at each place (#2528) ---

#: a string both text reports read: a type naming no need type, a namespace value
BOTH = "c.is_a('nosuch') or c.id.ns == 'x'"

#: each place, written twice in each of two documents with the same string: (the
#: document's text, with ``{f}`` for the filter and ``{n}`` for what tells the places
#: apart, the configuration's extra text, the builder, whether the place is located)
TOGETHER: dict[str, tuple[str, str, str, bool]] = {
    # no need is tested at the place
    "needflow-highlight-nothing-drawn": (
        ".. needflow::\n   :filter: id == 'NONE'\n   :highlight: {f}\n",
        'needs_flow_engine = "graphviz"\n',
        "html",
        True,
    ),
    "needgantt-milestone_filter-nothing-drawn": (
        ".. needgantt:: G{n}\n   :filter: id == 'NONE'\n   :milestone_filter: {f}\n",
        'extensions = ["sphinx_needs", "sphinxcontrib.plantuml"]\n',
        "dummy",
        True,
    ),
    "needsequence-filter-no-receiver": (
        ".. needsequence:: S{n}\n   :start: REQ_001\n   :filter: {f}\n",
        'extensions = ["sphinx_needs", "sphinxcontrib.plantuml"]\n',
        "dummy",
        True,
    ),
    # one string from one document is evaluated once, and written at each place
    "needextend": ('.. needextend:: "{f}"\n   :+tags: ext{n}\n', "", "dummy", True),
    # a need is tested at the place
    "needflow-highlight": (
        ".. needflow::\n   :highlight: {f}\n",
        'needs_flow_engine = "graphviz"\n',
        "html",
        True,
    ),
    "needgantt-milestone_filter": (
        ".. needgantt:: G{n}\n   :milestone_filter: {f}\n",
        'extensions = ["sphinx_needs", "sphinxcontrib.plantuml"]\n',
        "dummy",
        True,
    ),
    "link-condition": (
        ".. spec:: Linked on a condition {n}\n   :id: COND_{d}{n}\n"
        "   :links: REQ_001[{f}]\n",
        "",
        "dummy",
        True,
    ),
    "calc_sum": (
        ".. spec:: Sum {n}\n   :id: SUM_{d}{n}\n"
        '   :total: [[calc_sum("id", filter={f!r})]]\n',
        "needs_fields = {'total': {'nullable': True, 'schema': {'type': 'number'}}}\n",
        "dummy",
        False,
    ),
}

#: two needs, and two more under a constraint sharing the string, which has no location
TOGETHER_INDEX = (
    INDEX
    + "\n.. req:: Constrained\n   :id: REQ_101\n   :constraints: c1\n"
    + "\n.. req:: Constrained too\n   :id: REQ_102\n   :constraints: c1\n"
    + "\n.. toctree::\n\n   doc1\n   doc2\n"
    + "".join(f"   page{i}\n" for i in range(5))
)

TOGETHER_CONF = (
    CONF
    + f"needs_constraints = {{'c1': {{'check_0': {BOTH!r}, 'severity': 'LOW'}}}}\n"
    + "needs_constraint_failed_options = {'LOW': {'on_fail': [], 'style': []}}\n"
)


def _together_document(place: str, d: int, change: str = "") -> str:
    rst = TOGETHER[place][0]
    return (
        f"Doc {d}\n=====\n"
        + "".join("\n" + rst.format(f=BOTH, n=n, d=d) for n in (1, 2))
        + change
    )


def _write_together(srcdir: Path, place: str, change: str = "") -> None:
    srcdir.mkdir(exist_ok=True)
    texts = {
        "conf.py": TOGETHER_CONF + TOGETHER[place][1],
        "ubproject.toml": TYPES,
        "index.rst": "Case\n====\n\n" + TOGETHER_INDEX,
        "doc1.rst": _together_document(place, 1, change),
        "doc2.rst": _together_document(place, 2),
        # Sphinx reads and writes in parallel from six documents on
        **{f"page{i}.rst": f"Page {i}\n======\n" for i in range(5)},
    }
    for name, text in texts.items():
        (srcdir / name).write_text(text, encoding="utf-8")


def _places(warnings: list[str], code: str) -> dict[str, int]:
    """How often *code* is reported at each place: its file and line, or ``""``."""
    counted: dict[str, int] = {}
    for warning in warnings:
        if warning.endswith(f"[{code}]"):
            where = warning.split("WARNING: ")[0]
            counted[where] = counted.get(where, 0) + 1
    return counted


def _expected_places(place: str, documents: tuple[int, ...]) -> dict[str, int]:
    """Each place written in *documents* once, and the constraint once."""
    expected = {"": 1}
    if TOGETHER[place][3]:
        for d in documents:
            text = _together_document(place, d)
            marker = TOGETHER[place][0].split("\n")[0].split("{")[0]
            for number, line in enumerate(text.splitlines(), 1):
                if line.startswith(marker):
                    expected[f"<srcdir>/doc{d}.rst:{number}: "] = 1
        assert len(expected) == 1 + 2 * len(documents), expected
    return expected


@pytest.mark.parametrize("parallel", [0, 2], ids=["serial", "parallel"])
@pytest.mark.parametrize("place", list(TOGETHER))
def test_the_two_text_reports_are_given_together_at_each_place(
    place: str, parallel: int, make_app: Any, tmp_path: Path
) -> None:
    """``needs.filter_type`` and ``needs.namespaced_ids_off`` are reported together for
    a string at a place: once at each place it is written, with its location, whether
    or not a need is tested there (a needflow drawing no need, a needgantt and a
    needsequence testing none), two ``needextend``\\ s of one document included; a place
    with no location (a constraint, a ``calc_sum``) once. A parallel build reports what a
    serial one does."""
    if parallel and not parallel_available:
        pytest.skip("this platform cannot run a parallel build")
    srcdir = tmp_path / "src"
    _write_together(srcdir, place)
    builder = TOGETHER[place][2]
    app = make_app(
        builder,
        srcdir=srcdir,
        freshenv=True,
        status=io.StringIO(),
        warning=io.StringIO(),
        parallel=parallel,
    )
    app.build()
    status = re.sub(r"\x1b\[[0-9;]*m", "", app._status.getvalue())
    chunked = re.search(r"reading sources\.\.\. \[ *\d+%\] \S+ \.\. ", status)
    assert (chunked is not None) is bool(parallel)
    warnings = build_warnings(app)
    expected = _expected_places(place, (1, 2))
    assert _places(warnings, "needs.filter_type") == expected, warnings
    assert _places(warnings, "needs.namespaced_ids_off") == expected, warnings


@pytest.mark.parametrize("parallel", [0, 2], ids=["serial", "parallel"])
@pytest.mark.parametrize("place", list(TOGETHER))
def test_an_incremental_build_gives_the_two_text_reports_together(
    place: str, parallel: int, make_app: Any, tmp_path: Path
) -> None:
    """A document changed since the last build is read and written again: each place
    in it is given both reports, once, with its location; whatever else the build
    evaluates again is given both, and nothing is given one of them alone."""
    if parallel and not parallel_available:
        pytest.skip("this platform cannot run a parallel build")
    srcdir = tmp_path / "src"
    builder = TOGETHER[place][2]
    for fresh, change in ((True, ""), (False, "\n.. a change\n")):
        _write_together(srcdir, place, change)
        app = make_app(
            builder,
            srcdir=srcdir,
            freshenv=fresh,
            status=io.StringIO(),
            warning=io.StringIO(),
            parallel=parallel,
        )
        app.build()
    warnings = build_warnings(app)
    filter_type = _places(warnings, "needs.filter_type")
    assert filter_type == _places(warnings, "needs.namespaced_ids_off"), warnings
    changed = _expected_places(place, (1,))
    assert {where: filter_type.get(where) for where in changed} == changed, warnings
    assert set(filter_type.values()) == {1}, warnings


@pytest.mark.parametrize(
    "test_app",
    [_project(INDEX + f"\n.. needlist::\n   :filter: {BOTH}\n", buildername="html")],
    indirect=True,
)
def test_the_two_text_reports_come_in_their_order(test_app: Any) -> None:
    """At a place, the type report comes first and the namespace report second, as the
    filter entries have always given them."""
    app = test_app
    app.build()
    codes = [
        code
        for w in build_warnings(app)
        for code in ("needs.filter_type", "needs.namespaced_ids_off")
        if w.endswith(f"[{code}]")
    ]
    assert codes == ["needs.filter_type", "needs.namespaced_ids_off"]
