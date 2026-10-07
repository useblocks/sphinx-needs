"""The order of the dynamic-function pass: what each call reads, and the schedule.

Unit tests of :mod:`sphinx_needs.functions.order`, on needs made without Sphinx: the
edge each built-in and argument form adds, read from the call text alone (a table
over call texts), the cycles, the columns, the order of the steps and the empty value
of a field. The build-level behaviour is pinned by ``test_dynamic_functions_strata``.
"""

from typing import Any
from unittest.mock import Mock

import pytest

from sphinx_needs.config import NeedsSphinxConfig
from sphinx_needs.filter_common import filter_single_need
from sphinx_needs.functions.functions import DynamicFunctionParsed
from sphinx_needs.functions.order import (
    BUILTINS,
    Column,
    FilterNames,
    Project,
    Step,
    build_stratum,
    filter_names,
    schedule,
    strongly_connected,
    typed_empty,
)
from sphinx_needs.need_item import NeedItem, NeedLink, NeedsContent
from sphinx_needs.needs_schema import (
    FieldFunctionArray,
    FieldSchema,
    LinkDisplayConfig,
    LinkSchema,
    LinksFunctionArray,
)
from sphinx_needs.variants import VariantFunctionParsed

CORE: dict[str, Any] = {
    "type": "req",
    "type_name": "Req",
    "type_prefix": "R_",
    "type_color": "",
    "type_style": "node",
    "status": None,
    "tags": [],
    "constraints": (),
    "title": "T",
    "collapse": False,
    "arch": {},
    "style": None,
    "layout": None,
    "hide": False,
    "external_css": "external_link",
    "has_dead_links": False,
    "has_forbidden_dead_links": False,
    "sections": (),
    "signature": None,
}

CONFIG = Mock(spec=NeedsSphinxConfig)
CONFIG.filter_data = {}
CONFIG.variant_data_proxy = None


def _value(text: str) -> Any:
    if text.startswith("[["):
        return DynamicFunctionParsed.from_string(text[2:-2], allow_need=True)
    return VariantFunctionParsed.from_string(text[2:-2])


def _need(need_id: str, *, links: Any = (), **fields: Any) -> NeedItem:
    """A need; a string value starting ``[[`` or ``<<`` is a call or a variant.

    Every need has ``grp``, which the filters below read, as every need of a project
    has every field.
    """
    fields.setdefault("grp", None)
    core = {**CORE, "id": need_id}
    extras: dict[str, Any] = {}
    dynamic: dict[str, Any] = {}
    for name, value in fields.items():
        computed = isinstance(value, str) and value[:2] in ("[[", "<<")
        target = core if name in CORE else extras
        target[name] = None if computed else value
        if computed:
            dynamic[name] = FieldFunctionArray((_value(value),))
    if isinstance(links, str):
        dynamic["links"] = LinksFunctionArray((_value(links),))
        links = ()
    return NeedItem(
        core=core,
        extras=extras,
        links={"links": [NeedLink(id=t) for t in links]},
        source=None,
        content=NeedsContent(content="", doctype=".rst"),
        dynamic_fields=dynamic,
        _validate=False,
    )


def _project(*needs: NeedItem, refs: dict[str, list[str]] | None = None) -> Project:
    by_id = {need.id: need for need in needs}

    def copy_match(filter_string: str, caller: NeedItem) -> str | None:
        matches = [
            n.id
            for n in by_id.values()
            if filter_single_need(n, CONFIG, filter_string, current_need=caller)
        ]
        return min(matches) if matches else None

    def sum_candidates(filter_string: str) -> list[str]:
        return [
            i
            for i in sorted(by_id)
            if filter_single_need(by_id[i], CONFIG, filter_string)
        ]

    return Project(
        by_id,
        link_fields={"links"},
        variants={"is_x": 'summary == "x"'},
        not_fields={"build_tags", "var", "shadowed"},
        builtins=BUILTINS,
        copy_match=copy_match,
        sum_candidates=sum_candidates,
        content_refs=lambda need_id: (refs or {}).get(need_id, []),
    )


def _table_project(field: str, text: str) -> Project:
    """The reader ``RD`` with ``field`` set to ``text``, among needs it can read."""
    return _project(
        _need(
            "DYN",
            summary="[[copy('title')]]",
            hours="[[copy('title')]]",
            status="[[copy('title')]]",
            grp="g",
        ),
        _need("DYN2", links="[[copy('links', 'SRC')]]", grp="h"),
        _need("SRC", summary="x", hours=1, status="open", grp="g", links=["TGT"]),
        _need("TGT"),
        _need(
            "RD",
            **({} if field == "links" else {"links": ["DYN", "SRC", "DYN"]}),
            summary="[[copy('title')]]",
            comment="authored",
            parent="DYN",
            which="summary",
            flag=True,
            grp="g",
            cparent="[[copy('parent')]]",
            **{field: text},
        ),
        refs={"RD": ["DYN", "SRC"]},
    )


EVERY_STATUS = 'status == "open"'


@pytest.mark.parametrize(
    ("field", "text", "expected"),
    [
        # S: a field of the need itself
        ("out", "[[copy('summary')]]", {"deps": [("RD", "summary")]}),
        ("out", "[[copy('comment')]]", {}),
        (
            "out",
            "[[test(need.summary, x=need.comment)]]",
            {"deps": [("RD", "summary")]},
        ),
        ("out", "[[echo('text')]]", {}),
        # R1: a field of a named need
        ("out", "[[copy('summary', 'DYN')]]", {"deps": [("DYN", "summary")]}),
        ("out", "[[copy('summary', need_id='DYN')]]", {"deps": [("DYN", "summary")]}),
        ("out", "[[copy('summary', 'NOPE')]]", {}),
        ("out", "[[copy('summary', 'DYN', 'one', 'two', 'three', 'four')]]", {}),
        # a back link is final once stratum 1 is computed
        ("out", "[[copy('links_back')]]", {}),
        # a link field read from stratum 2 is final
        ("out", "[[copy('links', 'DYN2')]]", {}),
        # need.<field> selecting the need or the field: read when final, else blocked
        ("out", "[[copy('summary', need.parent)]]", {"deps": [("DYN", "summary")]}),
        ("out", "[[copy(need.which)]]", {"deps": [("RD", "summary")]}),
        (
            "out",
            "[[copy('summary', need.cparent)]]",
            {
                "deps": [("RD", "cparent")],
                "blocked": ("dynamic function 'copy'", ["need.cparent"]),
            },
        ),
        ("out", "[[copy('summary', need.unknown)]]", {}),
        # a selected value that is no string (here a list, a boolean) fails the call
        ("out", "[[copy('summary', need.links)]]", {}),
        ("out", "[[copy('summary', filter=need.flag)]]", {}),
        # copy(filter=): the lowest-id match, when every name the filter reads is final
        (
            "out",
            "[[copy('summary', filter='grp == \"g\"')]]",
            {"deps": [("DYN", "summary")]},
        ),
        ("out", "[[copy('summary', filter='grp == \"h\"')]]", {}),
        (
            "out",
            "[[copy('summary', filter='current_need[\"grp\"] == grp')]]",
            {"deps": [("DYN", "summary")]},
        ),
        # ... else a column of every need's value of each computed name, and its own
        (
            "out",
            f"[[copy('summary', filter='{EVERY_STATUS}')]]",
            {
                "deps": [("RD", "summary")],
                "columns": [
                    (Column("summary"), EVERY_STATUS),
                    (Column("status"), EVERY_STATUS),
                ],
            },
        ),
        # a filter whose reads cannot be told: computed last
        ("out", "[[copy('summary', filter='len(needs) > 0')]]", {"opaque": True}),
        (
            "out",
            "[[copy('summary', filter='current_need[grp] == 1')]]",
            {"opaque": True},
        ),
        # U: calc_sum over every need, or over the candidates of a filter on final values
        ("out", "[[calc_sum('hours')]]", {"columns": [(Column("hours"), None)]}),
        (
            "out",
            "[[calc_sum('hours', 'grp == \"g\"')]]",
            {"columns": [(Column("hours", 'grp == "g"'), None)]},
        ),
        (
            "out",
            f"[[calc_sum('hours', '{EVERY_STATUS}')]]",
            {
                "columns": [
                    (Column("hours"), EVERY_STATUS),
                    (Column("status"), EVERY_STATUS),
                ]
            },
        ),
        # L1: the targets of the need's own links, in the order written, duplicates too
        (
            "out",
            "[[calc_sum('hours', links_only=True)]]",
            {"deps": [("DYN", "hours"), ("DYN", "hours")]},
        ),
        (
            "out",
            "[[calc_sum('hours', links_only=need.flag)]]",
            {"deps": [("DYN", "hours"), ("DYN", "hours")]},
        ),
        (
            "out",
            f"[[check_linked_values('ok', 'status', 'open', '{EVERY_STATUS}')]]",
            {"deps": [("DYN", "status")] * 4},
        ),
        # variants: every condition's names, evaluated or not, minus filter data
        (
            "out",
            '<<[comment == "y"]:a, [summary == "x"]:b, c>>',
            {"deps": [("RD", "summary")]},
        ),
        ("out", "<<is_x:a, b>>", {"deps": [("RD", "summary")]}),
        ("out", '<<[shadowed == "x"]:a, [build_tags]:b, c>>', {}),
        (
            "out",
            '<<[out == "x"]:a, b>>',
            {"deps": [("RD", "out")], "reads_itself_by_variant": True},
        ),
        # a user function is computed last
        ("out", "[[mine('summary')]]", {"user_functions": ["mine"]}),
        # stratum 1: link fields, ordered among themselves; a later value is out of scope
        ("links", "[[copy('links', 'DYN2')]]", {"deps": [("DYN2", "links")]}),
        (
            "links",
            "[[copy('summary', 'DYN')]]",
            {"scope": [("dynamic function 'copy'", [("summary", "DYN")])]},
        ),
        (
            "links",
            "[[copy('links_back')]]",
            {"scope": [("dynamic function 'copy'", [("links_back", "RD")])]},
        ),
        (
            "links",
            f"[[links_from_content(filter='{EVERY_STATUS}')]]",
            {"scope": [("dynamic function 'links_from_content'", [("status", "DYN")])]},
        ),
        ("links", "[[links_from_content(filter='grp == \"g\"')]]", {}),
    ],
)
def test_what_a_call_reads(field, text, expected):
    """The edges of one node, from its call text and the needs it names."""
    project = _table_project(field, text)
    stratum = 1 if field == "links" else 2
    reads = project.node_reads(("RD", field), stratum)
    got = {
        "deps": list(reads.deps),
        "columns": list(reads.columns),
        "scope": list(reads.scope),
        "blocked": reads.blocked,
        "user_functions": list(reads.user_functions),
        "opaque": reads.opaque,
        "reads_itself_by_variant": reads.reads_itself_by_variant,
    }
    defaults = {
        "deps": [],
        "columns": [],
        "scope": [],
        "blocked": None,
        "user_functions": [],
        "opaque": False,
        "reads_itself_by_variant": False,
    }
    assert got == {**defaults, **expected}


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ('status == "open"', FilterNames(frozenset({"status"}), frozenset(), False)),
        (
            'current_need["grp"] == grp and "a" in tags',
            FilterNames(frozenset({"grp", "tags"}), frozenset({"grp"}), False),
        ),
        (
            "any(t == 'a' for t in tags)",
            FilterNames(frozenset({"any", "tags"}), frozenset(), False),
        ),
        (
            "search('a', title) and var.x",
            FilterNames(frozenset({"title"}), frozenset(), False),
        ),
        ("c.this_doc()", FilterNames(frozenset({"docname"}), frozenset(), False)),
        ("shadowed == 1", FilterNames(frozenset(), frozenset(), False)),
        ("len(needs) > 1", FilterNames(frozenset({"len"}), frozenset(), True)),
        ("current_need[key]", FilterNames(frozenset({"key"}), frozenset(), True)),
        ("current_need.get('x')", FilterNames(frozenset(), frozenset(), True)),
        ("status ==", FilterNames(frozenset(), frozenset(), False)),
    ],
)
def test_filter_names(text, expected):
    """A filter's free names, its constant ``current_need`` keys, and whether it is opaque."""
    assert filter_names(text, frozenset({"shadowed"})) == expected


@pytest.mark.parametrize(
    ("schema", "nullable", "expected"),
    [
        ({"type": "string"}, True, None),
        ({"type": "string"}, False, ""),
        ({"type": "boolean"}, False, False),
        ({"type": "integer"}, False, 0),
        ({"type": "number"}, False, 0.0),
        ({"type": "array", "items": {"type": "string"}}, False, []),
    ],
)
def test_typed_empty(schema, nullable, expected):
    """A field's empty value: ``None`` when nullable, else its type's empty value."""
    field = FieldSchema(name="f", schema=schema, nullable=nullable)
    assert typed_empty(field) == expected
    assert type(typed_empty(field)) is type(expected)


def test_typed_empty_of_a_link_field():
    link = LinkSchema(
        name="links",
        schema={"type": "array", "items": {"type": "string"}},
        display=LinkDisplayConfig(outgoing="links", incoming="linked by"),
    )
    assert typed_empty(link) == []


def test_a_chain_is_computed_from_its_end():
    """``A`` reads ``B`` reads ``C``: ``C`` first, whatever the ids."""
    project = _project(
        _need("A", summary="[[copy('summary', 'B')]]"),
        _need("B", summary="[[copy('summary', 'C')]]"),
        _need("C", summary="[[copy('title')]]"),
    )
    assert build_stratum(project, 2).steps == [
        Step((("C", "summary"),)),
        Step((("B", "summary"),)),
        Step((("A", "summary"),)),
    ]


def test_independent_nodes_by_need_id_then_field():
    project = _project(
        _need("B", summary="[[copy('title')]]", comment="[[copy('title')]]"),
        _need("A", summary="[[copy('title')]]"),
    )
    assert [s.nodes for s in build_stratum(project, 2).steps] == [
        (("A", "summary"),),
        (("B", "comment"),),
        (("B", "summary"),),
    ]


def test_cycles_and_their_columns():
    """Every node of a strongly connected group is a member; a column says why."""
    project = _project(
        _need("CY_B", summary="[[copy('summary', 'CY_A')]]"),
        _need("CY_A", summary="[[copy('summary', 'CY_B')]]"),
        _need("SELF", summary="[[copy('summary')]]"),
        _need("SP", hours="[[calc_sum('hours')]]"),
        _need("P2", total=f"[[calc_sum('total', '{EVERY_STATUS}')]]"),
        _need("ST", status="[[copy('title')]]"),
        _need("AFTER", comment="[[copy('summary', 'CY_A')]]"),
    )
    steps = build_stratum(project, 2).steps
    assert [s for s in steps if s.cycle] == [
        Step((("CY_A", "summary"), ("CY_B", "summary")), cycle=True),
        Step((("SELF", "summary"),), cycle=True),
        Step((("SP", "hours"),), cycle=True, through=None),
        # after ``ST``, whose ``status`` its filter's column reads
        Step((("P2", "total"),), cycle=True, through=EVERY_STATUS),
    ]
    # a reader of a cycle comes after it, and is no member
    order = [s.nodes[0] for s in steps]
    assert order.index(("AFTER", "comment")) > order.index(("CY_A", "summary"))


def test_a_filter_on_final_values_is_no_cycle():
    """The candidates are computed before the stratum: the reader is not among them."""
    project = _project(
        _need("P", hours="[[calc_sum('hours', 'grp == \"g\"')]]"),
        _need("S_2", hours=2, grp="g"),
        _need("S_3", hours="[[copy('title')]]", grp="g"),
    )
    assert build_stratum(project, 2).steps == [
        Step((("S_3", "hours"),)),
        Step((("P", "hours"),)),
    ]


def test_user_functions_and_opaque_filters_come_last():
    """In ``(need id, field)`` order, after every built-in node; nothing waits for them."""
    project = _project(
        _need("A", summary="[[mine()]]"),
        _need("B", summary="[[copy('summary', 'A')]]"),
        _need("C", summary="[[copy('title', filter='len(needs) > 0')]]"),
        _need("D", total="[[calc_sum('summary')]]"),
    )
    assert [s.nodes for s in build_stratum(project, 2).steps] == [
        (("B", "summary"),),
        (("D", "total"),),
        (("A", "summary"),),
        (("C", "summary"),),
    ]


def test_link_fields_are_stratum_one():
    project = _project(
        _need("A", links="[[copy('links', 'B')]]", summary="[[copy('title')]]"),
        _need("B", links="[[copy('links', 'C')]]"),
        _need("C", links=["A"]),
    )
    assert [s.nodes for s in build_stratum(project, 1).steps] == [
        (("B", "links"),),
        (("A", "links"),),
    ]
    assert [s.nodes for s in build_stratum(project, 2).steps] == [(("A", "summary"),)]


def test_strongly_connected_and_schedule():
    """Components come out after everything they read; ready ones by key."""
    edges = [[1], [0], [], [2, 3]]
    components = strongly_connected(edges)
    assert sorted(sorted(c) for c in components) == [[0, 1], [2], [3]]
    keys = [(f"N{min(c)}", "") for c in components]
    assert [sorted(c) for c in schedule(edges, components, keys)] == [[0, 1], [2], [3]]


def test_a_20000_node_chain_is_ordered_without_recursion():
    """A chain longer than Python's recursion limit: each need copies the next one."""
    count = 20_000
    project = _project(
        *(
            _need(f"N{i:05d}", summary=f"[[copy('summary', 'N{i + 1:05d}')]]")
            for i in range(count - 1)
        ),
        _need(f"N{count - 1:05d}", summary="[[copy('title')]]"),
    )
    steps = build_stratum(project, 2).steps
    assert not any(step.cycle for step in steps)
    assert [step.nodes[0][0] for step in steps] == [
        f"N{i:05d}" for i in reversed(range(count))
    ]
