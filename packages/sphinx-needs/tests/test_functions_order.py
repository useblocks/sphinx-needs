"""The order of the dynamic-function pass: what each call reads, and the schedule.

Unit tests of :mod:`sphinx_needs.functions.order`, on needs made without Sphinx: the
edge each built-in and argument form adds, read from the call text alone (a table
over call texts), the cycles, the columns, the order of the steps and the empty value
of a field. The build-level behaviour is pinned by ``test_dynamic_functions_strata``.
"""

import inspect
from typing import Any, Final
from unittest.mock import Mock

import pytest

from sphinx_needs.config import NeedsSphinxConfig
from sphinx_needs.derive import DeriveCall, DeriveJoin, DeriveRule
from sphinx_needs.filter_common import filter_single_need
from sphinx_needs.functions.functions import DynamicFunctionParsed
from sphinx_needs.functions.order import (
    BUILTINS,
    JOIN_READ,
    Column,
    Declaration,
    Declared,
    DeclaredRead,
    FilterNames,
    OutOfScope,
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
    "type_ancestors": ["req"],
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
        links = (links,)
    if any(text[:2] in ("[[", "<<") for text in links):
        dynamic["links"] = LinksFunctionArray(
            tuple(
                _value(text) if text[:2] in ("[[", "<<") else NeedLink(id=text)
                for text in links
            )
        )
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


def _project(
    *needs: NeedItem,
    refs: dict[str, list[str]] | None = None,
    link_fields: tuple[str, ...] = ("links",),
    declared: dict[str, Any] | None = None,
) -> Project:
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
        link_fields=link_fields,
        variants={"is_x": 'summary == "x"'},
        not_fields={"build_tags", "var", "shadowed"},
        builtins=BUILTINS,
        copy_match=copy_match,
        sum_candidates=sum_candidates,
        content_refs=lambda need_id: (refs or {}).get(need_id, []),
        declared=declared,
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
            unset=None,
            empty="",
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
        # need.<field> selecting the need or the field: read when final; computed in
        # the same stratum, the call is not run and the node reads nothing
        ("out", "[[copy('summary', need.parent)]]", {"deps": [("DYN", "summary")]}),
        ("out", "[[copy(need.which)]]", {"deps": [("RD", "summary")]}),
        (
            "out",
            "[[copy('summary', need.cparent)]]",
            {
                "scope": [
                    OutOfScope("dynamic function 'copy'", selectors=("need.cparent",))
                ]
            },
        ),
        ("out", "[[copy('summary', need.unknown)]]", {}),
        # a need.<field> passed as a value is read like the field, and chains
        (
            "out",
            "[[check_linked_values('ok', 'status', need.cparent)]]",
            {"deps": [("RD", "cparent"), ("DYN", "status"), ("DYN", "status")]},
        ),
        (
            "out",
            "[[check_linked_values(need.cparent, 'status', 'open')]]",
            {"deps": [("RD", "cparent"), ("DYN", "status"), ("DYN", "status")]},
        ),
        (
            "out",
            "[[copy('summary', 'DYN', upper=need.cparent)]]",
            {"deps": [("RD", "cparent"), ("DYN", "summary")]},
        ),
        # an unset (or empty) selector fails the call; an unset value is None
        ("out", "[[copy('summary', need.unset)]]", {}),
        ("out", "[[copy('summary', need.empty)]]", {}),
        ("out", "[[calc_sum('hours', links_only=need.empty)]]", {}),
        (
            "out",
            "[[copy('summary', 'DYN', upper=need.unset)]]",
            {"deps": [("DYN", "summary")]},
        ),
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
        # with a need named, current_need is that need
        (
            "out",
            "[[copy('summary', 'DYN', filter='current_need[\"status\"] == status')]]",
            {
                "deps": [("DYN", "status"), ("DYN", "summary")],
                "columns": [
                    (Column("summary"), 'current_need["status"] == status'),
                    (Column("status"), 'current_need["status"] == status'),
                ],
            },
        ),
        # (DYN2's grp "h" matches DYN2 alone, which computes no summary; the caller's
        # "g" would match DYN, which does)
        (
            "out",
            "[[copy('summary', 'DYN2', filter='current_need[\"grp\"] == grp')]]",
            {},
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
        # stratum 1: link fields, ordered among themselves; a later value is out of
        # scope, and the node reads nothing
        ("links", "[[copy('links', 'DYN2')]]", {"deps": [("DYN2", "links")]}),
        (
            "links",
            "[[copy('summary', 'DYN')]]",
            {"scope": [OutOfScope("dynamic function 'copy'", (("summary", "DYN"),))]},
        ),
        (
            "links",
            "[[copy('links_back')]]",
            {"scope": [OutOfScope("dynamic function 'copy'", (("links_back", "RD"),))]},
        ),
        (
            "links",
            "[[copy('summary', need.parent)]]",
            {"scope": [OutOfScope("dynamic function 'copy'", (("summary", "DYN"),))]},
        ),
        # the dead-link flags are set with the back links
        (
            "links",
            "<<[has_dead_links]:TGT, SRC>>",
            {"scope": [OutOfScope("variant condition", (("has_dead_links", "RD"),))]},
        ),
        (
            "links",
            "[[copy('links', filter='has_forbidden_dead_links')]]",
            {
                "scope": [
                    OutOfScope(
                        "dynamic function 'copy'", (("has_forbidden_dead_links", "RD"),)
                    )
                ]
            },
        ),
        ("out", "<<[has_dead_links]:a, b>>", {}),
        # a selector computed after the stratum is a read out of scope
        (
            "links",
            "[[copy('links', need.cparent)]]",
            {"scope": [OutOfScope("dynamic function 'copy'", (("cparent", "RD"),))]},
        ),
        # one call out of scope: the node reads nothing, its other calls included
        (
            "links",
            ("TGT", "[[copy('links', 'DYN2')]]", "[[copy('summary', 'DYN')]]"),
            {"scope": [OutOfScope("dynamic function 'copy'", (("summary", "DYN"),))]},
        ),
        (
            "links",
            f"[[links_from_content(filter='{EVERY_STATUS}')]]",
            {
                "scope": [
                    OutOfScope(
                        "dynamic function 'links_from_content'", (("status", "DYN"),)
                    )
                ]
            },
        ),
        ("links", "[[links_from_content(filter='grp == \"g\"')]]", {}),
        # links_from_filter: every need is a candidate, so a name computed in the same
        # stratum is a column, one computed after it out of scope, a final one nothing;
        # current_need is the need the call is in
        ("links", "[[links_from_filter('grp == \"g\"')]]", {}),
        (
            "links",
            "[[links_from_filter('current_need[\"grp\"] == grp')]]",
            {},
        ),
        (
            "links",
            f"[[links_from_filter('{EVERY_STATUS}')]]",
            {
                "scope": [
                    OutOfScope(
                        "dynamic function 'links_from_filter'", (("status", "DYN"),)
                    )
                ]
            },
        ),
        # links_from_match: the reader's own value, and the field on every need through
        # its column, with the filter's names; computed after the stratum: out of scope
        ("links", "[[links_from_match('grp', 'which')]]", {}),
        (
            "links",
            "[[links_from_match('status', 'which')]]",
            {
                "scope": [
                    OutOfScope(
                        "dynamic function 'links_from_match'", (("status", "DYN"),)
                    )
                ]
            },
        ),
        (
            "links",
            "[[links_from_match('grp', 'summary')]]",
            {
                "scope": [
                    OutOfScope(
                        "dynamic function 'links_from_match'", (("summary", "RD"),)
                    )
                ]
            },
        ),
        (
            "links",
            f"[[links_from_match('grp', 'which', filter='{EVERY_STATUS}')]]",
            {
                "scope": [
                    OutOfScope(
                        "dynamic function 'links_from_match'", (("status", "DYN"),)
                    )
                ]
            },
        ),
        (
            "out",
            "[[links_from_match('summary', 'which')]]",
            {"columns": [(Column("summary"), JOIN_READ)]},
        ),
        (
            "out",
            "[[links_from_match('grp', 'which', filter='len(needs) > 1')]]",
            {"opaque": True},
        ),
        # an empty name, or a link type, fails the call: it reads nothing
        ("links", "[[links_from_match('', 'summary')]]", {}),
        ("links", "[[links_from_match('links', 'which')]]", {}),
        ("links", "[[links_from_match('grp', 'links_back')]]", {}),
        # calc_sum's filter may name ``needs``: what it reads cannot be told, so last
        (
            "out",
            "[[calc_sum('hours', filter='any(id in s[\"links\"] for s in needs)')]]",
            {"opaque": True},
        ),
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
        "user_functions": list(reads.user_functions),
        "opaque": reads.opaque,
        "reads_itself_by_variant": reads.reads_itself_by_variant,
    }
    defaults = {
        "deps": [],
        "columns": [],
        "scope": [],
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


def test_a_fingerprint_reads_the_names_it_includes_on_its_own_need():
    """A ``fingerprint`` rule is late, and reads each name it includes on its own need,
    less its ``exclude``: a name computed in the late step too orders the fingerprint
    after it (``fp``), unless the rule excludes it (``fp_less``). (A fingerprint never
    includes a derived field; the late ``summary`` here stands for any value computed
    in the step.)"""
    rules = {
        ("A", "fp"): DeriveCall(DeriveRule(kind="fingerprint")),
        ("A", "fp_less"): DeriveCall(
            DeriveRule(kind="fingerprint", exclude=("summary",))
        ),
        ("A", "summary"): DeriveCall(
            DeriveRule(kind="copy", field="title", after_derived=True)
        ),
    }
    project = Project(
        {"A": _need("A", summary=None, fp=None, fp_less=None)},
        rules=rules,
        link_fields=("links",),
        variants={},
        not_fields=set(),
        builtins=BUILTINS,
        copy_match=lambda _filter, _caller: None,
        sum_candidates=lambda _filter: [],
        content_refs=lambda _need_id: [],
        fingerprint_names=("id", "title", "summary", "links"),
    )
    assert project.nodes[("A", "fp")] == project.nodes[("A", "fp_less")] == 3
    assert list(project.node_reads(("A", "fp"), 3).deps) == [("A", "summary")]
    assert list(project.node_reads(("A", "fp_less"), 3).deps) == []
    assert build_stratum(project, 3).steps.index(Step((("A", "summary"),))) < (
        build_stratum(project, 3).steps.index(Step((("A", "fp"),)))
    )


def test_a_join_reads_its_own_value_and_its_columns():
    """A rule with a ``join`` reads ``equals`` on its own need, and ``field`` (and a
    ``copy``'s ``field``) on every need through their columns, whatever ``copy``
    would read without the join: a computed column is waited for, and a column
    computed after a ``links`` join's step is a read out of scope on each need
    computing it."""
    copy_join = DeriveRule(
        kind="copy", field="hours", join=DeriveJoin("summary", "which")
    )
    links_join = DeriveRule(kind="links", join=DeriveJoin("summary", "which"))
    rules = {
        ("RD", "o"): DeriveCall(copy_join),
        ("RD", "own"): DeriveCall(
            DeriveRule(kind="copy", field="title", join=DeriveJoin("grp", "summary"))
        ),
        ("RD", "lnk"): DeriveCall(links_join),
    }
    project = Project(
        {
            "DYN": _need("DYN", summary="[[copy('title')]]", hours="[[copy('title')]]"),
            "RD": _need("RD", summary="[[copy('title')]]", which="x", o=None, own=None),
        },
        rules=rules,
        link_fields=("links", "lnk"),
        variants={},
        not_fields=set(),
        builtins=BUILTINS,
        copy_match=lambda _filter, _caller: None,
        sum_candidates=lambda _filter: [],
        content_refs=lambda _need_id: [],
    )
    reads = project.node_reads(("RD", "o"), 2)
    assert list(reads.deps) == []
    assert list(reads.columns) == [
        (Column("summary"), JOIN_READ),
        (Column("hours"), JOIN_READ),
    ]
    own = project.node_reads(("RD", "own"), 2)
    assert (list(own.deps), list(own.columns)) == ([("RD", "summary")], [])
    lnk = project.node_reads(("RD", "lnk"), 1)
    assert list(lnk.scope) == [
        OutOfScope("derive rule 'links'", (("summary", "DYN"), ("summary", "RD")))
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
        Step(
            (("CY_A", "summary"), ("CY_B", "summary")), cycle=True, through=(None, None)
        ),
        Step((("SELF", "summary"),), cycle=True, through=(None,)),
        Step((("SP", "hours"),), cycle=True, through=((Column("hours"), None),)),
        # after ``ST``, whose ``status`` its filter's column reads
        Step(
            (("P2", "total"),),
            cycle=True,
            through=((Column("total"), EVERY_STATUS),),
        ),
    ]
    # a reader of a cycle comes after it, and is no member
    order = [s.nodes[0] for s in steps]
    assert order.index(("AFTER", "comment")) > order.index(("CY_A", "summary"))


def test_each_cycle_member_names_the_column_it_reads():
    """The column a member reads its cycle through is its own, not its group's.

    ``FILT``'s filter names a computed field, ``SELF_SUM`` sums every need, both over
    ``total``; ``S_SUM``'s filter is on final values, but keeps ``S_SUM`` itself.
    """
    project = _project(
        _need(
            "FILT",
            total="[[calc_sum('total', 'comment == \"x\"')]]",
            comment="[[copy('title')]]",
        ),
        _need("SELF_SUM", total="[[calc_sum('total')]]"),
        _need("S_SUM", hours="[[calc_sum('hours', 'type == \"req\"')]]"),
    )
    assert [s for s in build_stratum(project, 2).steps if s.cycle] == [
        Step(
            (("FILT", "total"), ("SELF_SUM", "total")),
            cycle=True,
            through=((Column("total"), 'comment == "x"'), (Column("total"), None)),
        ),
        Step(
            (("S_SUM", "hours"),),
            cycle=True,
            through=((Column("hours", 'type == "req"'), None),),
        ),
    ]


def test_why_a_read_came_before_its_value():
    """The run-time check groups the reads it reports by what computes the value.

    Your own function, or a call whose filter cannot be read, runs after the other
    built-in functions; any other read before its value is a gap in the order, which
    the message asks to be reported.
    """
    from sphinx_needs.functions.functions import _Pass

    project = _project(
        _need("U", summary="[[mine()]]"),
        _need("O", summary="[[copy('title', filter='len(needs) > 0')]]"),
        _need("X", summary="[[copy('title')]]"),
    )
    pass_ = _Pass(project)
    pass_.stratum = build_stratum(project, 2)
    assert pass_.causes([("summary", ["O", "U", "X"])]) == [
        (
            "it is computed by a call whose filter cannot be read, which runs after "
            "the other built-in functions",
            [("summary", ["O"])],
        ),
        (
            "it is computed by your own function 'mine', which runs after the "
            "built-in functions",
            [("summary", ["U"])],
        ),
        (
            "the order of the pass did not account for this read; please report this "
            "at https://github.com/useblocks/sphinx-needs/issues",
            [("summary", ["X"])],
        ),
    ]


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


def _through_links_project(field: str, text: Any) -> Project:
    """``RD`` computes its ``links`` (``TGT``, written, and a copy) and ``field`` from ``text``.

    ``blocks`` and ``refs`` are link fields too, so ``RD.blocks`` is computed in
    stratum 1 with the links it reads. ``refs`` is computed in stratum 1 by ``DYN`` and
    by the written target ``TGT``; ``summary`` in stratum 2 by ``DYN``; ``hours`` by
    no need.
    """
    return _project(
        _need("DYN", summary="[[copy('title')]]", refs="[[copy('links', 'SRC')]]"),
        _need("SRC", links=["TGT"]),
        _need("TGT", hours=1, refs="[[copy('links', 'SRC')]]"),
        _need(
            "RD",
            **(
                {"links": text}
                if field == "links"
                else {"links": ("TGT", "[[copy('links', 'SRC')]]"), field: text}
            ),
        ),
        link_fields=("links", "blocks", "refs"),
    )


CLV: Final = "dynamic function 'check_linked_values'"


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        # (a) computed by some need in the same stratum: the column, its written
        # target TGT included, and no edge of its own to TGT
        (
            "[[check_linked_values('ok', 'refs', 'x')]]",
            {"columns": [(Column("refs"), ("RD", "links"))]},
        ),
        (
            "[[calc_sum('refs', links_only=True)]]",
            {"columns": [(Column("refs"), ("RD", "links"))]},
        ),
        # ... and so are the fields its filter names
        (
            "[[check_linked_values('ok', 'hours', 1, 'len(refs) == 0')]]",
            {"columns": [(Column("refs"), ("RD", "links"))]},
        ),
        # (c) computed by no need: final, the links alone
        ("[[check_linked_values('ok', 'hours', 1)]]", {}),
        ("[[calc_sum('hours', links_only=True)]]", {}),
    ],
)
def test_a_read_through_computed_links_is_a_column_read(text, expected):
    """A read through a need's own links computed in the same stratum reads a column.

    Which needs the links name is known only once they are computed, so the field is
    read on every need that computes it, as a whole-project ``calc_sum`` reads it;
    the call is computed after its own ``links`` all the same.
    """
    reads = _through_links_project("blocks", text).node_reads(("RD", "blocks"), 1)
    assert {"deps": list(reads.deps), "columns": list(reads.columns)} == {
        "deps": [("RD", "links")],
        "columns": [],
        **expected,
    }
    assert list(reads.scope) == []


@pytest.mark.parametrize(
    ("text", "reads", "linked"),
    [
        # (b) computed in a later stratum, by a need the links do not name
        ("[[check_linked_values('ok', 'summary', 'x')]]", (("summary", "DYN"),), ()),
        ("[[calc_sum('summary', links_only=True)]]", (("summary", "DYN"),), ()),
        # (b) a back link or a dead-link flag, of whichever need the links name
        ("[[check_linked_values('ok', 'links_back', 'x')]]", (), ("links_back",)),
        ("[[calc_sum('has_dead_links', links_only=True)]]", (), ("has_dead_links",)),
        (
            "[[check_linked_values('ok', 'refs', 'x', 'summary == \"x\"')]]",
            (("summary", "DYN"),),
            (),
        ),
    ],
)
def test_a_later_read_through_computed_links_is_out_of_scope(text, reads, linked):
    """A read through computed links of a value final only after the stratum is a sink.

    The value is computed (or set with the back links) after stratum 1, on any need
    the links may name, so the call is not run: it reads nothing.
    """
    got = _through_links_project("blocks", text).node_reads(("RD", "blocks"), 1)
    what = CLV if "check" in text else "dynamic function 'calc_sum'"
    expected = (
        OutOfScope(what, reads, linked=linked) if linked else OutOfScope(what, reads)
    )
    assert (list(got.deps), list(got.columns), list(got.scope)) == ([], [], [expected])


def test_a_link_field_reading_through_itself_stays_a_cycle():
    """The links that read through themselves are a self-cycle, not a column read.

    ``summary`` is computed after stratum 1, but the call is on a cycle with itself
    before it reads anything else.
    """
    text = ("TGT", "[[check_linked_values('TGT', 'summary', 'x')]]")
    project = _through_links_project("links", text)
    reads = project.node_reads(("RD", "links"), 1)
    assert (list(reads.deps), list(reads.columns), list(reads.scope)) == (
        [("RD", "links")],
        [],
        [],
    )
    assert [s for s in build_stratum(project, 1).steps if s.cycle] == [
        Step((("RD", "links"),), cycle=True, through=(None,))
    ]


def test_a_cycle_through_computed_links_names_them():
    """A need reading its own field through its computed links is on a cycle with it.

    ``RD.refs`` reads the ``refs`` column, which ``RD.refs`` is in: the member names
    the column, and why every need is in it, its own computed links.
    """
    project = _through_links_project(
        "refs", "[[check_linked_values('ok', 'refs', 'x')]]"
    )
    cycles = [s for s in build_stratum(project, 1).steps if s.cycle]
    assert cycles == [
        Step(
            (("RD", "refs"),),
            cycle=True,
            through=((Column("refs"), ("RD", "links")),),
        )
    ]


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


# -- a function of your own that declares what it reads ------------------------------


def _declaration(
    *parameters: str, own: tuple[str, ...] = (), every: tuple[str, ...] = ()
) -> Declaration:
    """A declaration over the parameters (after app, need, needs); ``*name`` is the
    ``*args`` one."""
    signature = inspect.Signature(
        [
            inspect.Parameter(
                name.lstrip("*"),
                inspect.Parameter.VAR_POSITIONAL
                if name.startswith("*")
                else inspect.Parameter.POSITIONAL_OR_KEYWORD,
            )
            for name in parameters
        ]
    )
    return Declaration(signature, own, every)


def test_a_declared_call_is_ordered_like_a_built_in_one():
    """Its declared reads are waited for, and its readers wait for it: ``A``'s summary
    reads its ``comment``, which a built-in copy computes, and ``C`` copies ``A``'s
    summary -- where an undeclared ``mine`` would come last, after C."""
    needs = (
        _need("A", summary="[[mine('comment')]]", comment="[[copy('title')]]"),
        _need("C", summary="[[copy('summary', 'A')]]"),
    )
    declared = {"mine": _declaration("option", own=("option",))}
    stratum = build_stratum(_project(*needs, declared=declared), 2)
    assert [s.nodes for s in stratum.steps] == [
        (("A", "comment"),),
        (("A", "summary"),),
        (("C", "summary"),),
    ]
    reads = stratum.reads[("A", "summary")]
    assert (reads.last, reads.user_functions, reads.deps) == (
        False,
        (),
        [("A", "comment")],
    )
    assert reads.declared == [
        Declared(0, "mine", frozenset({("A", "comment")}), frozenset())
    ]
    # undeclared, it is computed last
    undeclared = build_stratum(_project(*needs), 2)
    assert [s.nodes for s in undeclared.steps][-1] == (("A", "summary"),)


def test_a_declared_read_on_every_need_is_a_column():
    """``every`` reads the field on every need computing it: the call waits for them
    all, and on a cycle the message names the declaration. The arguments of a
    ``*args`` parameter are each a field."""
    project = _project(
        _need("A", summary="[[mine('summary')]]"),
        _need("B", summary="[[copy('title')]]"),
        _need("C", comment="[[mine('comment')]]"),
        _need("D", grp="[[many('summary', 'comment')]]"),
        declared={
            "mine": _declaration("option", every=("option",)),
            "many": _declaration("*options", every=("options",)),
        },
    )
    stratum = build_stratum(project, 2)
    assert stratum.reads[("A", "summary")].columns == [
        (Column("summary"), DeclaredRead("mine"))
    ]
    assert [c for c, _ in stratum.reads[("D", "grp")].columns] == [
        Column("summary"),
        Column("comment"),
    ]
    order = [s.nodes for s in stratum.steps]
    assert order.index((("B", "summary"),)) < order.index((("A", "summary"),))
    # reading its own field on every need, ``A`` is on a cycle through it
    assert [s for s in stratum.steps if s.cycle] == [
        Step(
            (("A", "summary"),),
            cycle=True,
            through=((Column("summary"), DeclaredRead("mine")),),
        ),
        Step(
            (("C", "comment"),),
            cycle=True,
            through=((Column("comment"), DeclaredRead("mine")),),
        ),
    ]


def test_a_declared_self_read_is_a_cycle():
    project = _project(
        _need("A", summary="[[mine('summary')]]"),
        declared={"mine": _declaration("option", own=("option",))},
    )
    assert build_stratum(project, 2).steps == [
        Step((("A", "summary"),), cycle=True, through=(None,))
    ]


def test_a_declared_read_of_a_later_step_is_out_of_scope():
    """A link field's call declaring a read of a field computed after the link fields
    cannot be ordered: it is not run (a sink), as a built-in call reading it."""
    project = _project(
        _need("A", links="[[mine('summary', 'comment')]]", summary="[[copy('title')]]"),
        declared={"mine": _declaration("a", "b", own=("a",), every=("b",))},
    )
    reads = build_stratum(project, 1).reads[("A", "links")]
    assert reads.sink
    assert reads.scope == [OutOfScope("dynamic function 'mine'", (("summary", "A"),))]


def test_a_need_argument_of_a_declared_call_is_a_dependency():
    """A ``need.<field>`` argument of a parameter the declaration does not name is
    data, a read of its own need: computed in the same stratum, a dependency (its own
    field, a cycle); final, nothing to wait for."""
    project = _project(
        _need("A", summary="[[mine('grp', need.grp)]]", grp="G"),
        _need(
            "B", summary="[[mine('grp', need.comment)]]", comment="[[copy('title')]]"
        ),
        _need("D", summary="[[mine('grp', need.summary)]]"),
        declared={"mine": _declaration("option", "value", own=("option",))},
    )
    stratum = build_stratum(project, 2)
    declared = stratum.reads[("A", "summary")].declared
    assert [(d.nodes, d.arguments) for d in declared] == [
        (frozenset({("A", "grp")}), frozenset({"grp"}))
    ]
    b = stratum.reads[("B", "summary")]
    assert (b.sink, b.last, b.deps) == (False, False, [("B", "comment")])
    order = [s.nodes[0] for s in stratum.steps]
    assert order.index(("B", "comment")) < order.index(("B", "summary"))
    assert [s.nodes for s in stratum.steps if s.cycle] == [(("D", "summary"),)]
    assert project.refused == {}


@pytest.mark.parametrize(
    ("call", "why"),
    [
        pytest.param(
            "[[mine(need.comment)]]",
            "the argument of its parameter 'option' is need.comment, not a field name "
            "written in the call",
            id="need-argument",
        ),
        pytest.param(
            "[[mine(3)]]",
            "the argument of its parameter 'option' is 3, not a field name written in "
            "the call",
            id="number",
        ),
        pytest.param(
            "[[mine()]]",
            "its call does not fit its parameters: missing a required argument: "
            "'option'",
            id="missing",
        ),
        pytest.param(
            "[[mine('a', 'b')]]",
            "its call does not fit its parameters: too many positional arguments",
            id="too-many",
        ),
    ],
)
def test_a_call_whose_declared_argument_is_no_field_name_is_computed_last(call, why):
    """The call cannot be declared: it is computed last, as a call of a function
    declaring nothing, and the project keeps why, for the first call only (the pass
    warns once per function)."""
    project = _project(
        _need("A", summary=call, comment="[[copy('title')]]"),
        _need("B", summary=call),
        _need("C", summary="[[copy('title')]]"),
        declared={"mine": _declaration("option", own=("option",))},
    )
    stratum = build_stratum(project, 2)
    assert stratum.reads[("A", "summary")].last
    assert stratum.reads[("A", "summary")].user_functions == ["mine"]
    assert [s.nodes[0] for s in stratum.steps][-2:] == [
        ("A", "summary"),
        ("B", "summary"),
    ]
    assert project.refused == {"mine": (("A", "summary"), why)}


def test_a_built_in_name_is_never_declared():
    """A declaration under the name of a built-in function the project has not
    replaced is ignored: the built-in's reads are known."""
    project = _project(
        _need("A", summary="[[copy('title')]]"),
        declared={"copy": _declaration("option", own=("option",))},
    )
    assert project.declared == {}
    assert not build_stratum(project, 2).steps[0].cycle
