"""The ``source.*`` facets of a filter: what the shared corpus cannot say.

``tests/fixtures/filter_conformance.toml`` (its "source facets" section) pins what each
facet selects, for every producer it can build, in both tiers. This module pins the rest:
each facet's rule over the hops of every producer, those the corpus cannot build among
them (a service, autodoc, an external need given a page, a needs.json read from a URL, a
source with no hops); a declaration named ``source`` switching the facets off (W-1), with
its one warning; the ``eval`` tier binding them only for a filter naming them; the
did-you-mean of an unknown facet; the places that have no facets saying so; a derived
field's ``where`` reading them.
"""

from __future__ import annotations

import ast
import inspect
from pathlib import Path
from typing import Any

import pytest

from sphinx_needs import _source_facets, filter_common
from sphinx_needs._need_source import (
    NeedSourceHop,
    NeedSourcePhysical,
    NeedSourceSemantic,
)
from sphinx_needs._source_facets import (
    READERS,
    SOURCE_FACETS,
    SourceFacets,
    kind_of,
    line_of,
    path_of,
    paths_of,
    symbol_of,
)
from sphinx_needs.config import NeedsSphinxConfig
from sphinx_needs.data import SphinxNeedsData
from sphinx_needs.exceptions import NeedsInvalidFilter
from sphinx_needs.filter_common import filter_needs_view, filter_single_need
from sphinx_needs.need_item import NeedItemSource
from sphinx_needs.ubquery import CompiledFilter
from sphinx_needs_testkit import build_warnings

#: pinned before the source facets land: red until the commit that serves each
_UNTIL_MESSAGES = pytest.mark.xfail(
    strict=True, reason="the unavailability messages land in their own commit"
)


def _page(path: str, line: int | None = None, document: str = "index") -> NeedSourceHop:
    return NeedSourceHop(
        kind="page",
        document=document,
        physical=NeedSourcePhysical(root="srcdir", path=path, start_line=line),
        language=".rst",
    )


def _file(path: str, line: int | None = None) -> NeedSourceHop:
    return NeedSourceHop(
        kind="file",
        physical=NeedSourcePhysical(root="srcdir", path=path, start_line=line),
        language=path[path.rindex(".") :],
    )


def _code(
    path: str,
    line: int | None = None,
    *,
    root: str | None = "srcdir",
    entity: tuple[tuple[str, str], ...] = (),
    qualified: str | None = None,
) -> NeedSourceHop:
    semantic = tuple(NeedSourceSemantic(kind=kind, name=name) for kind, name in entity)
    if semantic and qualified is not None:
        last = semantic[-1]
        semantic = (
            *semantic[:-1],
            NeedSourceSemantic(
                kind=last.kind, name=last.name, extras=(("qualified_name", qualified),)
            ),
        )
    return NeedSourceHop(
        kind="code",
        physical=NeedSourcePhysical(root=root, path=path, start_line=line),
        semantic=semantic or None,
        language="python",
    )


def _report(path: str) -> NeedSourceHop:
    return NeedSourceHop(
        kind="report",
        physical=NeedSourcePhysical(root="srcdir", path=path),
        language=".xml",
    )


_EXTERNAL = NeedSourceHop(
    kind="external", physical=NeedSourcePhysical(url="https://example.org/p.html#X")
)
_SERVICE = NeedSourceHop(
    kind="generated", semantic=(NeedSourceSemantic(kind="service", name="svc"),)
)
_DOWNLOADED = NeedSourceHop(
    kind="file",
    physical=NeedSourcePhysical(url="https://example.org/needs.json"),
    language=".json",
)


class _ThirdParty:
    """A third party's source: the legacy keys alone, no hops."""

    def __init__(self, *, is_external: bool = False) -> None:
        self.dict_repr = {
            "docname": "index",
            "lineno": 3,
            "lineno_content": None,
            "external_url": None,
            "is_import": False,
            "is_external": is_external,
        }


#: each producer's source, as it records it (``tests/test_need_source.py`` pins the
#: hops themselves), and the five facets the hops give: kind, path, line, paths, symbol
SHAPES: dict[str, tuple[Any, tuple[Any, ...]]] = {
    "page": (
        NeedItemSource((_page("index.rst", 4),)),
        ("page", "index.rst", 4, ("index.rst",), None),
    ),
    "include": (
        NeedItemSource((_file("frag/a.rst", 1), _page("index.rst"))),
        ("page", "frag/a.rst", 1, ("frag/a.rst", "index.rst"), None),
    ),
    "nested-include": (
        NeedItemSource(
            (_file("frag/b.rst", 2), _file("frag/a.rst"), _page("index.rst"))
        ),
        ("page", "frag/b.rst", 2, ("frag/b.rst", "frag/a.rst", "index.rst"), None),
    ),
    "a-path-twice": (
        NeedItemSource((_file("frag/a.rst", 2), _file("frag/a.rst"), _page("x.rst"))),
        ("page", "frag/a.rst", 2, ("frag/a.rst", "x.rst"), None),
    ),
    "on-page": (
        NeedItemSource((_page("p2.rst"),), lineno=15),
        ("page", "p2.rst", None, ("p2.rst",), None),
    ),
    "service": (
        NeedItemSource((_SERVICE, _file("frag/a.rst", 10), _page("index.rst"))),
        ("generated", None, None, ("frag/a.rst", "index.rst"), None),
    ),
    "autodoc": (
        NeedItemSource(
            (
                _code("../m.py", entity=(("function", "f"),), qualified="f"),
                _page("api.rst"),
            )
        ),
        ("code", "../m.py", None, ("../m.py", "api.rst"), "f"),
    ),
    "codelinks": (
        NeedItemSource(
            (
                _code(
                    "../src/e.py",
                    4,
                    entity=(("class", "Engine"), ("method", "start")),
                    qualified="Engine.start",
                ),
                _page("code.rst", 7),
            )
        ),
        ("code", "../src/e.py", 4, ("../src/e.py", "code.rst"), "Engine.start"),
    ),
    "codelinks-file-marker": (
        NeedItemSource((_code("../src/e.py", 1), _page("code.rst", 7))),
        ("code", "../src/e.py", 1, ("../src/e.py", "code.rst"), None),
    ),
    "codelinks-no-qualified-name": (
        NeedItemSource((_code("../src/e.py", 4, entity=(("function", "f"),)),)),
        ("code", "../src/e.py", 4, ("../src/e.py",), None),
    ),
    "test-file": (
        NeedItemSource((_report("r.xml"), _page("tests.rst", 3))),
        ("report", "r.xml", None, ("r.xml", "tests.rst"), None),
    ),
    "test-case": (
        NeedItemSource(
            (
                _code("tests/t.py", 28, root=None),
                _report("r.xml"),
                _page("tests.rst", 3),
            )
        ),
        ("report", None, None, ("r.xml", "tests.rst"), None),
    ),
    "needimport": (
        NeedItemSource((_file("imp.json"), _page("imp.rst", 7)), is_import=True),
        ("import", None, None, ("imp.json", "imp.rst"), None),
    ),
    "needimport-of-a-url": (
        NeedItemSource((_DOWNLOADED, _page("imp.rst", 7)), is_import=True),
        ("import", None, None, ("imp.rst",), None),
    ),
    "an-imported-test-case": (
        NeedItemSource(
            (_report("up.xml"), _file("imp.json"), _page("imp.rst", 7)),
            is_import=True,
        ),
        ("import", None, None, ("up.xml", "imp.json", "imp.rst"), None),
    ),
    "external": (
        NeedItemSource((_EXTERNAL,)),
        ("external", None, None, (), None),
    ),
    "external-given-a-page": (
        NeedItemSource((_EXTERNAL, _page("index.rst"))),
        ("external", None, None, (), None),
    ),
    "a-kind-to-come": (
        NeedItemSource(
            (
                NeedSourceHop(
                    kind="record",
                    physical=NeedSourcePhysical(root="srcdir", path="alm.csv"),
                ),
                _page("index.rst"),
            )
        ),
        ("page", "alm.csv", None, ("alm.csv", "index.rst"), None),
    ),
    "no-hops": (NeedItemSource(), (None, None, None, (), None)),
    "third-party": (_ThirdParty(), (None, None, None, (), None)),
    "third-party-external": (
        _ThirdParty(is_external=True),
        ("external", None, None, (), None),
    ),
}


class _Need(dict[str, Any]):
    """A need as the facets' readers read it: its fields, and its source."""

    def __init__(self, source: Any, **fields: Any) -> None:
        super().__init__(fields)
        self.source = source


@pytest.mark.parametrize(("source", "facets"), SHAPES.values(), ids=SHAPES.keys())
def test_each_facet_of_each_producer(source: Any, facets: tuple[Any, ...]) -> None:
    """The rules by named position: ``kind`` the producer (external, import, report,
    code, generated, page, in that order; open to more), ``path`` and ``line``
    ``hops[0]``'s under the source directory (none for an import, an external need or a
    service, and none where ``hops[0]`` has no such path: a test case's test file, a
    downloaded needs.json), ``paths`` every hop's, innermost first, each once (none for
    an external need, keyed on ``hops[0]``: a page after it is not where it comes
    from), ``symbol`` a code entity's qualified name."""
    found = tuple(f(source) for f in (kind_of, path_of, line_of, paths_of, symbol_of))
    assert found == facets


def test_a_part_and_the_eval_object_read_the_need_s_facets() -> None:
    """Every facet has one reader, which both tiers call: the parsed tier on the need
    (a part's need), ``eval`` through the object it binds, which computes a facet when
    it is read and refuses a name that is no facet."""
    assert tuple(sorted(READERS)) == SOURCE_FACETS
    need = _Need(
        SHAPES["codelinks"][0],
        id="IMPL_001",
        docname="code",
        sections=("Traced", "Code"),
    )
    facets = SourceFacets(need)
    assert [getattr(facets, name) for name in SOURCE_FACETS] == [
        "code",
        "code",
        4,
        "../src/e.py",
        ("../src/e.py", "code.rst"),
        ("Traced", "Code"),
        "Engine.start",
    ]
    assert facets == SourceFacets(need)
    assert facets != SourceFacets(_Need(need.source, **need))
    assert hash(facets) == hash(SourceFacets(need))
    assert repr(facets) == "<source of 'IMPL_001'>"
    with pytest.raises(AttributeError, match=r"no facet 'end_line' \(its facets: "):
        _ = facets.end_line
    with pytest.raises(AttributeError, match=r"no facet 'pathz' \(did you mean 'path'"):
        _ = facets.pathz


def test_the_facet_module_imports_no_sphinx_of_its_own() -> None:
    """The facets are computed from what a need holds: the module imports neither
    Sphinx nor docutils itself, nor the need class, which will compute its legacy keys
    through it."""
    tree = ast.parse(inspect.getsource(_source_facets))
    imported = {
        alias.name if isinstance(node, ast.Import) else node.module or ""
        for node in ast.walk(tree)
        if isinstance(node, ast.Import | ast.ImportFrom)
        for alias in node.names
    }
    assert not {
        name
        for name in imported
        if name.split(".")[0] in {"sphinx", "docutils"}
        or name == "sphinx_needs.need_item"
    }


INDEX = """\
Index
=====

.. req:: Written by hand
   :id: REQ_001
   {source}

.. req:: Written by a tool
   :id: REQ_002

.. spec:: A spec
   :id: SPEC_001
"""


def _project(conf: str, index: str = INDEX.format(source="")) -> dict[str, Any]:
    return {
        "buildername": "needs",
        "files": [
            (Path("conf.py"), 'extensions = ["sphinx_needs"]\n' + conf),
            (Path("index.rst"), index),
        ],
    }


def _both_tiers(app: Any, filter_string: str) -> dict[str, bool | str]:
    """Each need's answer, the same in the parsed tier and in ``eval`` (asserted)."""
    view = SphinxNeedsData(app.env).get_needs_view()
    config = NeedsSphinxConfig(app.config)

    def answers() -> dict[str, bool | str]:
        found: dict[str, bool | str] = {}
        for need in view.values():
            try:
                found[need["id"]] = filter_single_need(need, config, filter_string)
            except NeedsInvalidFilter as error:
                found[need["id"]] = f"error: {error}"
        return found

    parsed = answers()
    refused = CompiledFilter(None, "refused", False)
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(filter_common, "compile_portable", lambda _: refused)
        evaluated = answers()
    assert parsed == evaluated
    return parsed


SHADOWED = "which switches the source.* filter facets off for the project"


@pytest.mark.parametrize(
    ("test_app", "warning", "reads"),
    [
        pytest.param(
            _project(
                'needs_fields = {"source": {"nullable": True}}\n',
                INDEX.format(source=":source: manual"),
            ),
            f"A field named 'source' is declared, {SHADOWED}: 'source' in a filter "
            "reads the field",
            {"REQ_001": True, "REQ_002": False, "SPEC_001": False},
            id="field",
        ),
        pytest.param(
            _project('needs_links = {"source": {}}\n'),
            f"A link type named 'source' is declared, {SHADOWED}: 'source' in a filter "
            "reads the link type",
            {"REQ_001": False, "REQ_002": False, "SPEC_001": False},
            id="link-type",
        ),
        pytest.param(
            _project(
                "needs_types = [\n"
                '    {"directive": "req", "title": "Req", "prefix": "R_",'
                ' "fields": {"source": {"schema": {"type": "string"}}}},\n'
                '    {"directive": "spec", "title": "Spec", "prefix": "S_"},\n'
                "]\n",
                INDEX.format(source=":source: manual"),
            ),
            f"A field named 'source' is declared, {SHADOWED}: 'source' in a filter "
            "reads the field",
            # a spec reads the field too, which its type does not declare: unset there
            {"REQ_001": True, "REQ_002": False, "SPEC_001": False},
            id="field-of-one-need-type",
        ),
        pytest.param(
            _project('needs_filter_data = {"source": "manual"}\n'),
            f"A needs_filter_data key named 'source' is declared, {SHADOWED}: 'source' "
            "in a filter reads the needs_filter_data key",
            {"REQ_001": True, "REQ_002": True, "SPEC_001": True},
            id="filter-data",
        ),
    ],
    indirect=["test_app"],
)
def test_a_declaration_named_source_switches_the_facets_off(
    test_app: Any, warning: str, reads: dict[str, bool]
) -> None:
    """W-1: a field, a link type or a ``needs_filter_data`` key named ``source`` switches
    the facets off for the whole project, with one warning per build, and ``source``
    reads the declaration in both tiers -- on every need, a need of a type that does
    not declare the field included, so that no filter reads the facets on some needs
    and the field on others. (A field and a ``needs_filter_data`` key of one name are
    refused by the configuration already.)"""
    app = test_app
    app.build()
    assert [w for w in build_warnings(app) if not w.endswith("[needs.deprecated]")] == [
        f"WARNING: {warning} [needs.source_shadowed]"
    ]
    assert NeedsSphinxConfig(app.config).source_shadowed is True
    assert _both_tiers(app, 'source == "manual"') == reads
    # an attribute of what the name reads: no facet
    assert all(
        isinstance(answer, str) and "has no attribute 'path'" in answer
        for answer in _both_tiers(app, 'source.path == "index.rst"').values()
    )


@pytest.mark.parametrize("test_app", [_project("")], indirect=True)
def test_no_declaration_named_source_leaves_the_facets_on(test_app: Any) -> None:
    app = test_app
    app.build()
    assert build_warnings(app) == []
    assert _both_tiers(app, 'source.path == "index.rst"') == {
        "REQ_001": True,
        "REQ_002": True,
        "SPEC_001": True,
    }
    assert NeedsSphinxConfig(app.config).source_shadowed is False


@pytest.mark.parametrize("test_app", [_project("")], indirect=True)
def test_eval_binds_the_facets_only_for_a_filter_naming_source(
    test_app: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Binding the facets costs every evaluation, so ``eval`` binds them only where the
    compiled filter names ``source``: in its own names, or in a code object it nests --
    a generator expression's body, a lambda's -- where they are looked up too. The
    parsed tier reads a facet without binding them at all. Counted, not timed."""
    app = test_app
    app.build()
    made: list[str] = []
    real = getattr(filter_common, "SourceFacets", None)

    def counting(need: Any) -> Any:
        made.append(need["id"])
        assert real is not None
        return real(need)

    monkeypatch.setattr(filter_common, "SourceFacets", counting, raising=False)
    view = SphinxNeedsData(app.env).get_needs_view()
    config = NeedsSphinxConfig(app.config)
    every = ["REQ_001", "REQ_002", "SPEC_001"]

    def selected(filter_string: str) -> list[str]:
        made.clear()
        return sorted(
            need["id"] for need in filter_needs_view(view, config, filter_string)
        )

    # eval, not naming source: nothing bound
    assert selected('any(t == "x" for t in tags) or id in [i for i in [id]]') == every
    assert made == []
    # the parsed tier reads the facet it names, binding nothing
    assert selected('source.path == "index.rst"') == every
    assert made == []
    # eval naming source: bound once per need
    assert selected('source.path in [p for p in ["index.rst"]]') == every
    assert sorted(made) == every
    # ... in a generator expression's body alone
    assert selected('any(source.kind == kind for kind in ["page"])') == every
    assert sorted(made) == every
    # ... and in a lambda's
    assert selected('(lambda: source.kind)() == "page"') == every
    assert sorted(made) == every


@pytest.mark.parametrize("test_app", [_project("")], indirect=True)
def test_an_unknown_facet_is_reported_with_the_closest_facet(test_app: Any) -> None:
    """``source.<name>`` naming no facet falls to ``eval``, which reports it on every
    need, naming the closest facet, or every facet where none is close."""
    app = test_app
    app.build()
    assert set(_both_tiers(app, 'source.pth == "x"').values()) == {
        "error: Filter 'source.pth == \"x\"' not valid. Error: source has no facet "
        "'pth' (did you mean 'path'?)."
    }
    assert set(_both_tiers(app, 'source.colour == "x"').values()) == {
        "error: Filter 'source.colour == \"x\"' not valid. Error: source has no facet "
        "'colour' (its facets: document, kind, line, path, paths, sections, symbol)."
    }


UNAVAILABLE = "name 'source' is not defined; the source.* facets are not available in"


@_UNTIL_MESSAGES
@pytest.mark.parametrize(
    ("test_app", "expected"),
    [
        pytest.param(
            _project(
                'needs_fields = {"owner": {"nullable": True, "predicates": '
                '[(\'source.path == "index.rst"\', "me")]}}\n'
            ),
            "<srcdir>/index.rst:4: WARNING: needs_fields['owner']['predicates']: "
            "Predicate 'source.path == \"index.rst\"' not valid. Error: "
            f"{UNAVAILABLE} a field predicate. The predicate is skipped. [needs.config]",
            id="field-predicate",
        ),
        pytest.param(
            {
                "buildername": "needs",
                "files": [
                    (Path("conf.py"), 'extensions = ["sphinx_needs"]\n'),
                    (
                        Path("index.rst"),
                        "Index\n=====\n\n.. needimport:: imp.json\n"
                        '   :filter: source.kind == "page"\n',
                    ),
                    (
                        Path("imp.json"),
                        '{"current_version": "1.0", "versions": {"1.0": {"needs": '
                        '{"IMP_001": {"id": "IMP_001", "type": "req", "title": "x", '
                        '"content": ""}}}}}',
                    ),
                ],
            },
            "<srcdir>/index.rst:4: WARNING: needimport: Filter 'source.kind == \"page\"' "
            f"not valid. Error: {UNAVAILABLE} a needimport filter, which reads the "
            "imported record. [needs.needimport]",
            id="needimport-filter",
        ),
        pytest.param(
            _project(
                'needs_fields = {"owner": {"nullable": True, "parse_variants": True}}\n',
                INDEX.format(source=':owner: <<source.kind == "page": a, b>>'),
            ),
            "<srcdir>/index.rst:4: WARNING: Error while resolving dynamic values for "
            "field 'owner', of need 'REQ_001': "
            f"{UNAVAILABLE} a variant condition [needs.dynamic_function]",
            id="variant-condition",
        ),
    ],
    indirect=["test_app"],
)
def test_where_there_are_no_facets_the_error_says_so(
    test_app: Any, expected: str
) -> None:
    """A field predicate runs as the need is created, a needimport filter reads the
    imported record, and a variant condition reads the need's fields: none has the
    facets, and ``source`` there fails with an error that says so."""
    app = test_app
    app.build()
    assert build_warnings(app) == [expected]


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "needs",
            "files": [
                (
                    Path("conf.py"),
                    'extensions = ["sphinx_needs"]\n'
                    'needs_links = {"same_file": {"derive": {"kind": "links", '
                    '"where": "source.path == \'index.rst\'"}}}\n',
                ),
                (
                    Path("index.rst"),
                    "Index\n=====\n\n.. req:: Here\n   :id: REQ_001\n\n"
                    ".. include:: frag.txt\n",
                ),
                (Path("frag.txt"), ".. req:: There\n   :id: REQ_002\n"),
            ],
        }
    ],
    indirect=True,
)
def test_a_derived_where_reads_the_facets(test_app: Any) -> None:
    """A derived field's ``where`` may read the facets, which read hops fixed before
    the pass: the rule computes (a need links every other one it selects), and no read
    of them is reported."""
    app = test_app
    app.build()
    assert build_warnings(app) == []
    needs = SphinxNeedsData(app.env).get_needs_view()
    assert needs["REQ_001"]["same_file"] == []
    assert needs["REQ_002"]["same_file"] == ["REQ_001"]
