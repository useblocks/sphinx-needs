"""The warning for a filter that reads a namespace value while namespaced ids are off.

With ``needs_namespaced_ids`` off (the default until 10.0), ``c.id.ns`` is empty for
every need, ``c.id.local`` is the whole id and ``c.in_namespace()`` is false for every
need: a filter reading one of them is answered, and the answer means nothing. So such a
filter is reported, once per place it is written, as ``needs.namespaced_ids_off``. It is
decided from the filter's text, before any tier runs; the answer does not change; a
filter refused today keeps its refusal alone; with the switch on nothing is reported.
The design record is ``design/namespaced-ids.md``, section "The warning for a namespace
filter with the switch off".
"""

from __future__ import annotations

import io
import json
import re
from pathlib import Path
from typing import Any

import pytest
from sphinx.errors import ExtensionError
from sphinx.util.parallel import parallel_available

from sphinx_needs.config import NeedsSphinxConfig
from sphinx_needs.data import SphinxNeedsData
from sphinx_needs_testkit import build_warnings

#: the code every warning of this rule ends with
CODE = "[needs.namespaced_ids_off]"

#: the switch unset (off); no id pattern, so that an id holding ``::`` is created either
#: way and nothing here depends on how the patterns read one
CONF = 'extensions = ["sphinx_needs"]\nneeds_id_regex = ""\n'

#: the same project with the switch on
ON = "needs_namespaced_ids = True\n"

#: three needs, one of them namespaced where the switch is on; each links the one before
NEEDS = """\
Index
=====

.. req:: One
   :id: REQ_1

.. req:: Two
   :id: nc::REQ_2
   :links: REQ_1

.. req:: Three
   :id: nc::m2::REQ_3
   :links: nc::REQ_2

"""

#: what each name read gives with the switch off
CONSEQUENCE = {
    "c.id.ns": "c.id.ns is empty for every need",
    "c.id.local": "c.id.local is the whole id",
    "c.in_namespace()": "c.in_namespace() is false for every need",
}


def _text(*names: str) -> str:
    """The warning for a filter reading *names*, in the order the rule fixes."""
    said = names[0] if len(names) == 1 else f"{', '.join(names[:-1])} and {names[-1]}"
    return (
        f"The filter reads {said}, but namespaced ids are off for this project: "
        f"{'; '.join(CONSEQUENCE[name] for name in names)}. Set needs_namespaced_ids "
        "= True to read '::' in an id as a namespace separator, or suppress "
        f"needs.namespaced_ids_off. {CODE}"
    )


def _line(text: str, marker: str) -> int:
    """The 1-based line of *text* on which *marker* first appears."""
    for number, line in enumerate(text.splitlines(), 1):
        if marker in line:
            return number
    raise AssertionError(f"{marker!r} not in the document")


def _build(
    make_app: Any,
    tmp_path: Path,
    index: str,
    conf: str = CONF,
    *,
    files: dict[str, str] | None = None,
    buildername: str = "dummy",
    **kwargs: Any,
) -> Any:
    srcdir = tmp_path / "src"
    srcdir.mkdir(parents=True, exist_ok=True)
    (srcdir / "conf.py").write_text(conf, "utf-8")
    (srcdir / "index.rst").write_text(index, "utf-8")
    for name, text in (files or {}).items():
        (srcdir / name).write_text(text, "utf-8")
    app = make_app(
        buildername,
        srcdir=srcdir,
        freshenv=True,
        status=io.StringIO(),
        warning=kwargs.pop("warning", None) or io.StringIO(),
        **kwargs,
    )
    app.build()
    return app


def _ours(warnings: list[str]) -> list[str]:
    return [w for w in warnings if w.endswith(CODE)]


# --- the rule's table, row by row, at one place (a needlist's :filter:) -----------------

#: rows 1-14 of the rule's table: the filter, and the names the warning gives (None: no
#: warning of this rule)
ROWS: list[tuple[int, str, tuple[str, ...] | None]] = [
    (1, 'c.in_namespace("nc")', ("c.in_namespace()",)),
    (2, 'c.id.ns == "nc"', ("c.id.ns",)),
    (3, 'c.id.local == "REQ_1"', ("c.id.local",)),
    (4, 'c.id.ns == "nc" and c.in_namespace("nc")', ("c.id.ns", "c.in_namespace()")),
    (
        5,
        'c.id.ns == "nc" and c.id.local == "REQ_1" and c.in_namespace("nc")',
        ("c.id.ns", "c.id.local", "c.in_namespace()"),
    ),
    (6, 'not c.in_namespace("nc")', ("c.in_namespace()",)),
    (7, 'status == "open" and c.id.local == "REQ_1"', ("c.id.local",)),
    (8, 'id == "nc::REQ_1"', None),
    (9, '"c.in_namespace" in title', None),
    (10, 'c.is_a("req")', None),
]

#: rows 11-13: refused today, each with the error it is refused with
REFUSED: list[tuple[int, str, str]] = [
    (11, 'c.in_namespace("a::::b")', "c.in_namespace: 'a::::b' is not a namespace"),
    (12, 'c.in_namespace("")', "c.in_namespace('') names no namespace"),
    (
        13,
        'c.id == "nc::REQ_1"',
        "c.id holds the facets of the id, not the id: compare id, c.id.local or c.id.ns",
    ),
]

#: the rows reading a namespace value, which row 15 builds with the switch on
READING = [row for row in ROWS if row[2] is not None]


def _needlist(filter_string: str) -> str:
    return f"{NEEDS}.. needlist::\n   :filter: {filter_string}\n"


@pytest.mark.parametrize(
    ("row", "filter_string", "names"), ROWS, ids=[f"row{r[0]}" for r in ROWS]
)
def test_the_rule_row_by_row(
    row: int,
    filter_string: str,
    names: tuple[str, ...] | None,
    make_app: Any,
    tmp_path: Path,
) -> None:
    """Rows 1-10: a filter reading a namespace value is reported once, at the place it
    is written, with the names it reads in the fixed order; one that does not (a plain
    ``id``, a name inside a string literal, ``c.is_a``) is not. The exact text is
    asserted for every row, rows 1, 4 and 5 among them."""
    index = _needlist(filter_string)
    app = _build(make_app, tmp_path, index)
    ours = _ours(build_warnings(app))
    if names is None:
        assert len(ours) == 0, ours
        return
    assert len(ours) == 1, ours
    where = f"<srcdir>/index.rst:{_line(index, '.. needlist::')}: WARNING: "
    assert ours[0] == where + _text(*names)


@pytest.mark.parametrize(
    ("row", "filter_string", "error"), REFUSED, ids=[f"row{r[0]}" for r in REFUSED]
)
def test_a_refused_filter_gets_its_refusal_alone(
    row: int, filter_string: str, error: str, make_app: Any, tmp_path: Path
) -> None:
    """Rows 11-13: an argument of ``c.in_namespace`` that names no namespace, and a
    compared ``c.id``, keep the one ``needs.filter`` warning they have today, and get no
    warning of this rule."""
    app = _build(make_app, tmp_path, _needlist(filter_string))
    warnings = build_warnings(app)
    assert len(_ours(warnings)) == 0, warnings
    refusals = [w for w in warnings if w.endswith("[needs.filter]")]
    assert len(refusals) == 1, warnings
    assert error in refusals[0]


def test_row14_a_filter_that_does_not_parse_gets_its_parse_error_alone(
    make_app: Any, tmp_path: Path
) -> None:
    """Row 14: a filter that does not parse gets the parse error it has today, alone:
    at a link condition the ``needs.link_condition_invalid`` warning; at a needlist the
    error that stops the build (which is reached with no warning of this rule)."""
    broken = 'c.in_namespace("nc"'
    index = NEEDS + f".. req:: Four\n   :id: REQ_4\n   :links: REQ_1[{broken}]\n"
    app = _build(make_app, tmp_path, index)
    warnings = build_warnings(app)
    assert len(_ours(warnings)) == 0, warnings
    (invalid,) = [w for w in warnings if w.endswith("[needs.link_condition_invalid]")]
    assert "was never closed" in invalid

    stream = io.StringIO()
    with pytest.raises(ExtensionError, match="was never closed"):
        _build(make_app, tmp_path / "list", _needlist(broken), warning=stream)
    assert _ours(build_warnings(stream.getvalue())) == []


@pytest.mark.parametrize(
    ("row", "filter_string", "names"), READING, ids=[f"row{r[0]}" for r in READING]
)
def test_row15_with_the_switch_on_nothing_is_reported(
    row: int,
    filter_string: str,
    names: tuple[str, ...],
    make_app: Any,
    tmp_path: Path,
) -> None:
    """Row 15: rows 1-7 with the switch on are not reported."""
    app = _build(make_app, tmp_path, _needlist(filter_string), CONF + ON)
    assert len(_ours(build_warnings(app))) == 0


# --- the answer does not change ---------------------------------------------------------


@pytest.mark.parametrize(
    ("filter_string", "expected"),
    [
        ('c.in_namespace("nc")', []),
        ('not c.in_namespace("nc")', ["REQ_1", "nc::REQ_2", "nc::m2::REQ_3"]),
        ('c.id.ns == ""', ["REQ_1", "nc::REQ_2", "nc::m2::REQ_3"]),
        ('c.id.local == "REQ_2"', []),
        ('c.id.local == "nc::REQ_2"', ["nc::REQ_2"]),
    ],
)
def test_the_answer_does_not_change(
    filter_string: str, expected: list[str], make_app: Any, tmp_path: Path
) -> None:
    """The filter is answered as it was: with the switch off every need is plain."""
    from sphinx_needs.filter_common import filter_needs_view

    app = _build(make_app, tmp_path, NEEDS)
    view = SphinxNeedsData(app.env).get_needs_view()
    config = NeedsSphinxConfig(app.config)
    found = sorted(n["id"] for n in filter_needs_view(view, config, filter_string))
    assert found == expected


# --- one pin per place a filter string is read ------------------------------------------

#: the filter each place below is given: its own string, so that no two places share one
PLACE_FILTER = 'c.id.ns == "{tag}"'

#: each place, as (the document's extra text, the configuration's extra text, the marker
#: of the line the warning is located at, or None where it has no location, and the text
#: the warning is to end with before the code, where the place names itself)
PLACES: dict[str, tuple[str, str, str | None, str]] = {
    "needlist-filter": (".. needlist::\n   :filter: {f}\n", "", ".. needlist::", ""),
    "needtable-filter": (
        ".. needtable::\n   :filter: {f}\n",
        "",
        ".. needtable::",
        "",
    ),
    "needflow-filter": (
        ".. needflow::\n   :filter: {f}\n",
        'needs_flow_engine = "graphviz"\n',
        ".. needflow::",
        "",
    ),
    "needflow-highlight": (
        ".. needflow::\n   :highlight: {f}\n",
        'needs_flow_engine = "graphviz"\n',
        ".. needflow::",
        "",
    ),
    "needgantt-filter": (
        ".. needgantt:: G\n   :filter: {f}\n",
        'extensions.append("sphinxcontrib.plantuml")\n',
        ".. needgantt::",
        "",
    ),
    "needgantt-milestone_filter": (
        ".. needgantt:: G\n   :milestone_filter: {f}\n",
        'extensions.append("sphinxcontrib.plantuml")\n',
        ".. needgantt::",
        "",
    ),
    "needsequence-filter": (
        ".. needsequence:: S\n   :start: nc::m2::REQ_3\n   :filter: {f}\n",
        'extensions.append("sphinxcontrib.plantuml")\n',
        ".. needsequence::",
        "",
    ),
    "needextract-filter": (
        ".. needextract::\n   :filter: {f}\n",
        "",
        ".. needextract::",
        "",
    ),
    "needextract-argument": (".. needextract:: {f}\n", "", ".. needextract::", ""),
    "needpie-filter": (
        '.. needpie:: P\n   :filter: {f}\n\n   type == "req"\n',
        "",
        ".. needpie::",
        "",
    ),
    "needpie-line": (".. needpie:: P\n\n   {f}\n", "", ".. needpie::", ""),
    "needbar-cell": (".. needbar:: B\n\n   {f}\n", "", ".. needbar::", ""),
    "need_count-role": ("Count :need_count:`{f}`.\n", "", "Count :need_count:", ""),
    "needextend-argument": (
        ".. needextend:: {f}\n   :status: done\n",
        "",
        ".. needextend::",
        "",
    ),
    "needextend-quoted": (
        '.. needextend:: "{f}"\n   :status: done\n',
        "",
        ".. needextend::",
        "",
    ),
    "link-condition": (
        ".. req:: Four\n   :id: REQ_4\n   :links: REQ_1[{f}]\n",
        "",
        ".. req:: Four",
        "",
    ),
    "copy-filter": (
        ".. req:: Four\n   :id: REQ_4\n   :status: [[copy(\"title\", filter='{f}')]]\n",
        "",
        ".. req:: Four",
        "",
    ),
    "calc_sum-filter": (
        ".. req:: Four\n   :id: REQ_4\n   :status: [[calc_sum(\"title\", filter='{f}')]]\n",
        "",
        None,
        "",
    ),
    "check_linked_values-filter": (
        ".. req:: Four\n   :id: REQ_4\n   :links: REQ_1\n"
        '   :status: [[check_linked_values("ok", "title", "One", \'{f}\')]]\n',
        "",
        None,
        "",
    ),
    "links_from_filter": (
        ".. req:: Four\n   :id: REQ_4\n   :links: [[links_from_filter('{f}')]]\n",
        "",
        None,
        "",
    ),
    "links_from_match-filter": (
        ".. req:: Four\n   :id: REQ_4\n"
        '   :links: [[links_from_match("type", "type", filter=\'{f}\')]]\n',
        "",
        None,
        "",
    ),
    "links_from_content-filter": (
        ".. req:: Four\n   :id: REQ_4\n"
        "   :links: [[links_from_content(filter='{f}')]]\n\n   See :need:`REQ_1`.\n",
        "",
        None,
        "",
    ),
    "derive-where": (
        "",
        "needs_fields = {{'n_back': {{'schema': {{'type': 'integer'}}, 'derive': "
        "{{'kind': 'count', 'over': 'links', 'where': '{f}'}}}}}}\n",
        None,
        "",
    ),
    "needs_constraints": (
        ".. req:: Four\n   :id: REQ_4\n   :constraints: c1\n",
        "needs_constraints = {{'c1': {{'check_0': '{f}', 'severity': 'LOW'}}}}\n"
        "needs_constraint_failed_options = {{'LOW': {{'on_fail': [], 'style': []}}}}\n",
        None,
        "",
    ),
    "needuml-filter": (
        ".. needuml::\n\n   {{% for n in filter('{f}') %}}{{{{n.id}}}}{{% endfor %}}\n",
        'extensions.append("sphinxcontrib.plantuml")\n',
        None,
        "",
    ),
    "needs_warnings": (
        "",
        "needs_warnings = {{'w1': '{f}'}}\n",
        None,
        " (from warning filter 'w1')",
    ),
    "needs_builder_filter": (
        "",
        "needs_build_json = True\nneeds_builder_filter = '{f}'\n",
        None,
        " (from need_builder_filter)",
    ),
}


#: the places drawn for HTML output alone (a graphviz needflow)
HTML_PLACES = frozenset({"needflow-filter", "needflow-highlight"})


@pytest.mark.parametrize("place", list(PLACES))
def test_each_place_is_reported_once(place: str, make_app: Any, tmp_path: Path) -> None:
    """Every place a filter string is read: one warning, at the location the place's
    other findings are given (none for a configuration entry, which names itself where
    its other findings do)."""
    rst, conf, marker, origin = PLACES[place]
    filter_string = PLACE_FILTER.format(tag=place)
    index = NEEDS + rst.format(f=filter_string)
    app = _build(
        make_app,
        tmp_path,
        index,
        CONF + conf.format(f=filter_string),
        buildername="html" if place in HTML_PLACES else "dummy",
    )
    warnings = build_warnings(app)
    ours = _ours(warnings)
    assert len(ours) == 1, warnings
    text = _text("c.id.ns")
    if origin:
        text = text.replace(f" {CODE}", f"{origin} {CODE}")
    where = f"<srcdir>/index.rst:{_line(index, marker)}: " if marker is not None else ""
    assert ours[0] == f"{where}WARNING: {text}"


#: the places with no check context: a ``c.`` read is refused there today
NO_CHECK_CONTEXT: dict[str, tuple[str, str, dict[str, str], str]] = {
    "needimport-filter": (
        ".. needimport:: imp.json\n   :filter: {f}\n",
        "",
        {
            "imp.json": json.dumps(
                {
                    "current_version": "1.0",
                    "versions": {
                        "1.0": {
                            "needs": {
                                "IMP_1": {
                                    "id": "IMP_1",
                                    "type": "req",
                                    "title": "Imported",
                                    "content": "",
                                }
                            }
                        }
                    },
                }
            )
        },
        "the c.id facets are not available in a needimport filter",
    ),
    "field-predicate": (
        "",
        "needs_fields = {{'pf': {{'predicates': [('{f}', 'x')]}}}}\n",
        {},
        "the c.id facets are not available in a field predicate",
    ),
    "variant-condition": (
        ".. req:: Four\n   :id: REQ_4\n   :vf: <<[{f}]:x, y>>\n",
        "needs_fields = {{'vf': {{'parse_variants': True}}}}\n",
        {},
        "the c.id facets are not available in a variant condition",
    ),
}


@pytest.mark.parametrize("place", list(NO_CHECK_CONTEXT))
def test_where_there_is_no_check_context_the_refusal_stands_alone(
    place: str, make_app: Any, tmp_path: Path
) -> None:
    """A needimport filter, a field's predicate and a variant condition have no check
    context: a namespace read there is refused today, and gets that refusal alone."""
    rst, conf, files, said = NO_CHECK_CONTEXT[place]
    filter_string = PLACE_FILTER.format(tag=place)
    index = NEEDS + rst.format(f=filter_string)
    app = _build(
        make_app,
        tmp_path,
        index,
        CONF + conf.format(f=filter_string),
        files=files,
    )
    warnings = build_warnings(app)
    assert len(_ours(warnings)) == 0, warnings
    assert len([w for w in warnings if said in w]) >= 1, warnings


# --- once per place ---------------------------------------------------------------------


def test_once_per_place_however_many_needs_it_is_read_for(
    make_app: Any, tmp_path: Path
) -> None:
    """A filter evaluated need by need (``eval``, a constraint on every need, a derived
    field's ``where`` on every candidate, a needgantt's milestone filter read twice per
    need) is reported once per place per build; the same string in two places is two
    warnings, two needextends of one document among them."""
    many = "".join(
        f".. req:: Many {i}\n   :id: MANY_{i}\n   :links: REQ_1\n   :constraints: c1\n\n"
        for i in range(5)
    )
    evaluated = 'c.id.local == "REQ_1" and len(title) > 0'
    gantt = 'c.id.ns == "g"'
    index = (
        NEEDS
        + many
        + f".. needlist::\n   :filter: {evaluated}\n\n"
        + f".. needlist::\n   :filter: {evaluated}\n\n"
        + f".. needgantt:: G\n   :milestone_filter: {gantt}\n\n"
        + '.. needextend:: c.id.ns == "x"\n   :status: a\n\n'
        + '.. needextend:: c.id.ns == "x"\n   :status: b\n'
    )
    conf = (
        CONF
        + 'extensions.append("sphinxcontrib.plantuml")\n'
        + "needs_constraints = {'c1': {'check_0': 'c.id.local != \"\"', "
        "'severity': 'LOW'}}\n"
        + "needs_constraint_failed_options = {'LOW': {'on_fail': [], 'style': []}}\n"
        + "needs_fields = {'n_back': {'schema': {'type': 'integer'}, 'derive': "
        "{'kind': 'count', 'over': 'links', 'where': 'c.in_namespace(\"nc\")'}}}\n"
    )
    app = _build(make_app, tmp_path, index, conf)
    ours = _ours(build_warnings(app))
    lines = [index.splitlines()[i - 1] for i in range(1, len(index.splitlines()) + 1)]
    located = sorted(
        int(m[1]) for w in ours if (m := re.match(r"<srcdir>/index\.rst:(\d+):", w))
    )
    expected = sorted(
        number
        for number, line in enumerate(lines, 1)
        if line.startswith((".. needlist::", ".. needgantt::", ".. needextend::"))
    )
    assert located == expected, ours
    # the constraint and the derived field's where: one each, with no location
    assert len([w for w in ours if w.startswith("WARNING: ")]) == 2, ours


def test_reported_when_no_need_is_tested(make_app: Any, tmp_path: Path) -> None:
    """It is decided from the text: a filter over no need at all is reported too."""
    index = NEEDS + '.. needlist::\n   :types: spec\n   :filter: c.id.ns == "nc"\n'
    app = _build(make_app, tmp_path, index)
    assert len(_ours(build_warnings(app))) == 1


def test_it_can_be_suppressed(make_app: Any, tmp_path: Path) -> None:
    """The warning type is suppressed as any other: ``suppress_warnings``."""
    conf = CONF + 'suppress_warnings = ["needs.namespaced_ids_off"]\n'
    app = _build(make_app, tmp_path, _needlist('c.in_namespace("nc")'), conf)
    assert build_warnings(app) == []


# --- per build: an incremental build, and a parallel one --------------------------------

TOGGLE_INDEX = _needlist('c.in_namespace("nc")')
TOGGLE_CONF = CONF + "needs_warnings = {'w1': 'c.id.local == \"REQ_1\"'}\n"


def test_switching_it_on_and_off_again_through_incremental_builds(
    make_app: Any, tmp_path: Path
) -> None:
    """Switching ``needs_namespaced_ids`` on and back off in one source directory, with
    nothing else changed: the warnings go and come back, the same as a cold build each
    time (flipping the switch re-reads every document)."""
    srcdir = tmp_path / "src"
    srcdir.mkdir()
    (srcdir / "conf.py").write_text(TOGGLE_CONF, "utf-8")
    (srcdir / "index.rst").write_text(TOGGLE_INDEX, "utf-8")

    def build(switch: bool, where: Path, fresh: bool) -> list[str]:
        app = make_app(
            "html",
            srcdir=where,
            freshenv=fresh,
            status=io.StringIO(),
            warning=io.StringIO(),
            confoverrides={"needs_namespaced_ids": switch},
        )
        app.build()
        return _ours(build_warnings(app))

    cold: dict[bool, list[str]] = {}
    for switch in (False, True):
        cold_dir = tmp_path / f"cold-{switch}"
        cold_dir.mkdir()
        for name in ("conf.py", "index.rst"):
            (cold_dir / name).write_text((srcdir / name).read_text("utf-8"), "utf-8")
        cold[switch] = build(switch, cold_dir, True)
    assert len(cold[False]) == 2, cold
    assert cold[True] == []
    for switch in (False, True, False, True, False):
        assert build(switch, srcdir, False) == cold[switch], switch


def test_an_unchanged_rebuild_reports_what_it_evaluates_again(
    make_app: Any, tmp_path: Path
) -> None:
    """Per build: a second build with nothing changed writes no page again, so the
    needlist on the unchanged page is not evaluated and not reported; a configuration
    entry evaluated again in that build is reported again."""
    srcdir = tmp_path / "src"
    srcdir.mkdir()
    (srcdir / "conf.py").write_text(
        TOGGLE_CONF + "needs_build_json = True\n"
        "needs_builder_filter = 'c.id.ns == \"\"'\n",
        "utf-8",
    )
    (srcdir / "index.rst").write_text(TOGGLE_INDEX, "utf-8")
    runs = []
    for _ in range(2):
        app = make_app(
            "html", srcdir=srcdir, status=io.StringIO(), warning=io.StringIO()
        )
        app.build()
        runs.append(_ours(build_warnings(app)))
    first, second = runs
    assert len([w for w in first if w.startswith("<srcdir>/index.rst")]) == 1, first
    assert [w for w in second if w.startswith("<srcdir>/index.rst")] == [], second
    builder = [w for w in first if "(from need_builder_filter)" in w]
    assert len(builder) == 1, first
    assert [w for w in second if "(from need_builder_filter)" in w] == builder


@pytest.mark.parametrize("parallel", [0, 2], ids=["serial", "parallel"])
def test_a_parallel_build_reports_as_a_serial_one(
    parallel: int, make_app: Any, tmp_path: Path
) -> None:
    """``-j 2``: Sphinx reads the documents in worker processes (from six documents on)
    and resolves them in the main one, where every filter of a page is evaluated: the
    same warnings as a serial build, once per place, a page's own location each."""
    if parallel and not parallel_available:
        pytest.skip("this platform cannot run a parallel build")
    srcdir = tmp_path / "src"
    srcdir.mkdir()
    (srcdir / "conf.py").write_text(TOGGLE_CONF, "utf-8")
    toctree = "\n.. toctree::\n\n" + "".join(f"   page{i}\n" for i in range(8))
    (srcdir / "index.rst").write_text(NEEDS + toctree, "utf-8")
    for i in range(8):
        (srcdir / f"page{i}.rst").write_text(
            f"Page {i}\n======\n\n.. req:: P{i}\n   :id: PG_{i}\n\n"
            '.. needlist::\n   :filter: c.in_namespace("nc")\n',
            "utf-8",
        )
    app = make_app(
        "html",
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
    ours = sorted(_ours(build_warnings(app)))
    assert ours == sorted(
        [
            f"<srcdir>/page{i}.rst:7: WARNING: {_text('c.in_namespace()')}"
            for i in range(8)
        ]
        + [
            "WARNING: "
            + _text("c.id.local").replace(
                f" {CODE}", f" (from warning filter 'w1') {CODE}"
            )
        ]
    )
