"""The ``c.source`` facets of a filter: what the shared corpus cannot say.

``tests/fixtures/filter_conformance.toml`` (its "source facets" section) pins what each
facet selects, for every producer it can build, in both tiers. This module pins the rest:
each facet's rule over the hops of every producer, those the corpus cannot build among
them (a service, autodoc, an external need given a page, a needs.json read from a URL, a
source with no hops); that ``c`` holds them whatever a project declares, and that a root
``source`` is a field like any other; that every channel evaluating a filter binds
``c``; the did-you-mean of an unknown facet; the places that have no facets saying so.
"""

from __future__ import annotations

import ast
import inspect
import json
from pathlib import Path
from typing import Any

import pytest

from sphinx_needs import _source_facets, filter_common, variants
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
from sphinx_needs.filter_common import filter_single_need
from sphinx_needs.need_item import NeedItemSource
from sphinx_needs.ubquery import CompiledFilter
from sphinx_needs_testkit import build_warnings


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
    "a-service-writing-a-file": (
        NeedItemSource(
            (
                NeedSourceHop(
                    kind="generated",
                    physical=NeedSourcePhysical(root="srcdir", path="gen/out.json"),
                ),
                _page("index.rst"),
            )
        ),
        ("generated", None, None, ("gen/out.json", "index.rst"), None),
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
    "a-code-hop-not-innermost": (
        NeedItemSource(
            (
                _file("frag/a.rst", 2),
                _code("../m.py", 3, entity=(("function", "f"),), qualified="f"),
                _page("x.rst"),
            )
        ),
        ("page", "frag/a.rst", 2, ("frag/a.rst", "../m.py", "x.rst"), None),
    ),
    "an-imported-external": (
        NeedItemSource((_EXTERNAL, _page("imp.rst", 7)), is_import=True),
        ("import", None, None, ("imp.rst",), None),
    ),
    "an-import-of-an-external-need-upstream": (
        NeedItemSource(
            (_EXTERNAL, _file("imp.json"), _page("imp.rst", 7)), is_import=True
        ),
        ("import", None, None, ("imp.json", "imp.rst"), None),
    ),
    "an-upstream-hop-with-an-origin": (
        NeedItemSource(
            (
                NeedSourceHop(
                    kind="page",
                    origin="upstream",
                    physical=NeedSourcePhysical(root="srcdir", path="index.rst"),
                ),
                _file("imp.json"),
                _page("imp.rst", 7),
            ),
            is_import=True,
        ),
        ("import", None, None, ("imp.json", "imp.rst"), None),
    ),
    "an-upstream-code-hop-with-an-origin": (
        NeedItemSource(
            (
                NeedSourceHop(
                    kind="code",
                    origin="upstream",
                    physical=NeedSourcePhysical(
                        root="srcdir", path="../src/e.py", start_line=4
                    ),
                ),
                _file("imp.json"),
                _page("imp.rst", 7),
            ),
            is_import=True,
        ),
        ("import", None, None, ("imp.json", "imp.rst"), None),
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
    """The rules by named position: ``kind`` the producer (import, external, report,
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
    assert repr(facets) == "<c.source of 'IMPL_001'>"
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


EVERY = {"REQ_001": True, "REQ_002": True, "SPEC_001": True}


@pytest.mark.parametrize("test_app", [_project("")], indirect=True)
def test_c_source_reads_the_facets_and_a_root_source_is_no_name(test_app: Any) -> None:
    """``c.source.<facet>`` is the one spelling, in both tiers; ``source`` alone is a
    name like any other, which nothing declares here: undefined, as on any filter."""
    app = test_app
    app.build()
    assert build_warnings(app) == []
    assert _both_tiers(app, 'c.source.path == "index.rst"') == EVERY
    assert _both_tiers(app, 'c.source.kind == "page" and c.source.line > 3') == EVERY
    assert set(_both_tiers(app, 'source.path == "index.rst"').values()) == {
        "error: Filter 'source.path == \"index.rst\"' not valid. "
        "Error: name 'source' is not defined."
    }


@pytest.mark.parametrize(
    ("test_app", "reads"),
    [
        pytest.param(
            _project(
                'needs_fields = {"source": {"nullable": True}}\n',
                INDEX.format(source=":source: manual"),
            ),
            {"REQ_001": True, "REQ_002": False, "SPEC_001": False},
            id="field",
        ),
        pytest.param(
            _project('needs_links = {"source": {}}\n'),
            {"REQ_001": False, "REQ_002": False, "SPEC_001": False},
            id="link-type",
        ),
        pytest.param(
            _project('needs_filter_data = {"source": "manual"}\n'),
            {"REQ_001": True, "REQ_002": True, "SPEC_001": True},
            id="filter-data",
        ),
    ],
    indirect=["test_app"],
)
def test_a_declaration_named_source_is_a_name_like_any_other(
    test_app: Any, reads: dict[str, bool]
) -> None:
    """A field, a link type or a ``needs_filter_data`` key named ``source`` is read as
    it always was, and the build says nothing of it: the facets live under ``c``, which
    no declaration reaches."""
    app = test_app
    app.build()
    assert [
        w for w in build_warnings(app) if not w.endswith("[needs.deprecated]")
    ] == []
    assert _both_tiers(app, 'source == "manual"') == reads
    assert _both_tiers(app, 'c.source.kind == "page"') == EVERY


@pytest.mark.parametrize(
    "test_app",
    [
        pytest.param(
            _project(
                'needs_fields = {"c": {"nullable": True}}\n',
                INDEX.format(source=":c: manual"),
            ),
            id="field",
        ),
        pytest.param(
            _project('needs_filter_data = {"c": "manual"}\n'), id="filter-data"
        ),
    ],
    indirect=True,
)
def test_c_is_the_check_context_whatever_is_named_c(test_app: Any) -> None:
    """``c`` is the check context in every tier, set over the need's fields and the
    ``needs_filter_data`` keys, as ``c.this_doc()`` and ``c.is_a()`` always read it:
    a field or a key named ``c`` reaches no facet."""
    app = test_app
    app.build()
    assert [
        w for w in build_warnings(app) if not w.endswith("[needs.deprecated]")
    ] == []
    assert _both_tiers(app, 'c.source.path == "index.rst"') == EVERY
    assert _both_tiers(app, 'c.is_a("req")') == {
        "REQ_001": True,
        "REQ_002": True,
        "SPEC_001": False,
    }


@pytest.mark.parametrize("test_app", [_project("")], indirect=True)
def test_a_facet_costs_its_own_work_alone(
    test_app: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A filter reading one facet computes that facet, in either tier:
    ``c.source.path`` reads the kind (an import's or an external need's has none) and
    the path, never the paths, the line or the symbol."""
    app = test_app
    app.build()
    called: list[str] = []
    for name in ("kind_of", "path_of", "line_of", "paths_of", "symbol_of"):
        real = getattr(_source_facets, name)

        def counting(source: Any, _real: Any = real, _name: str = name) -> Any:
            called.append(_name)
            return _real(source)

        monkeypatch.setattr(_source_facets, name, counting)
    assert _both_tiers(app, 'c.source.path == "index.rst"') == EVERY
    assert set(called) == {"kind_of", "path_of"}


@pytest.mark.parametrize("test_app", [_project("")], indirect=True)
def test_an_unknown_facet_is_reported_with_the_closest_facet(test_app: Any) -> None:
    """``c.source.<name>`` naming no facet falls to ``eval``, which reports it on every
    need, naming the closest facet, or every facet where none is close."""
    app = test_app
    app.build()
    assert set(_both_tiers(app, 'c.source.pth == "x"').values()) == {
        "error: Filter 'c.source.pth == \"x\"' not valid. Error: c.source has no "
        "facet 'pth' (did you mean 'path'?)."
    }
    assert set(_both_tiers(app, 'c.source.colour == "x"').values()) == {
        "error: Filter 'c.source.colour == \"x\"' not valid. Error: c.source has no "
        "facet 'colour' (its facets: document, kind, line, path, paths, sections, "
        "symbol)."
    }


UNAVAILABLE = "the c.source facets are not available in"


@pytest.mark.parametrize(
    ("test_app", "expected"),
    [
        pytest.param(
            _project(
                'needs_fields = {"owner": {"nullable": True, "predicates": '
                '[(\'c.source.path == "index.rst"\', "me")]}}\n'
            ),
            "<srcdir>/index.rst:4: WARNING: needs_fields['owner']['predicates']: "
            "Predicate 'c.source.path == \"index.rst\"' not valid. Error: name 'c' is "
            f"not defined; {UNAVAILABLE} a field predicate. The predicate is skipped. "
            "[needs.config]",
            id="field-predicate",
        ),
        pytest.param(
            _project(
                'needs_fields = {"owner": {"nullable": True, "predicates": '
                '[(\'c.is_a("req")\', "me")]}}\n'
            ),
            "<srcdir>/index.rst:4: WARNING: needs_fields['owner']['predicates']: "
            "Predicate 'c.is_a(\"req\")' not valid. Error: name 'c' is not defined. "
            "The predicate is skipped. [needs.config]",
            id="a-check-that-is-no-facet",
        ),
        pytest.param(
            {
                "buildername": "needs",
                "files": [
                    (Path("conf.py"), 'extensions = ["sphinx_needs"]\n'),
                    (
                        Path("index.rst"),
                        "Index\n=====\n\n.. needimport:: imp.json\n"
                        '   :filter: c.source.kind == "page"\n',
                    ),
                    (
                        Path("imp.json"),
                        '{"current_version": "1.0", "versions": {"1.0": {"needs": '
                        '{"IMP_001": {"id": "IMP_001", "type": "req", "title": "x", '
                        '"content": ""}}}}}',
                    ),
                ],
            },
            "<srcdir>/index.rst:4: WARNING: needimport: Filter 'c.source.kind == "
            "\"page\"' not valid. Error: name 'c' is not defined; "
            f"{UNAVAILABLE} a needimport filter, which reads the imported record. "
            "[needs.needimport]",
            id="needimport-filter",
        ),
        pytest.param(
            _project(
                'needs_fields = {"owner": {"nullable": True, "parse_variants": True}}\n',
                INDEX.format(source=':owner: <<c.source.kind == "page": a, b>>'),
            ),
            "<srcdir>/index.rst:4: WARNING: Error while resolving dynamic values for "
            "field 'owner', of need 'REQ_001': name 'c' is not defined; "
            f"{UNAVAILABLE} a variant condition [needs.dynamic_function]",
            id="variant-condition",
        ),
        pytest.param(
            _project(
                'needs_fields = {"c": {"nullable": True}, '
                '"owner": {"nullable": True, "parse_variants": True}}\n',
                INDEX.format(
                    source=':c: manual\n   :owner: <<c.source.kind == "page": a, b>>'
                ),
            ),
            "<srcdir>/index.rst:4: WARNING: Error while resolving dynamic values for "
            "field 'owner', of need 'REQ_001': 'str' object has no attribute 'source'; "
            f"{UNAVAILABLE} a variant condition [needs.dynamic_function]",
            id="variant-condition-and-a-field-named-c",
        ),
    ],
    indirect=["test_app"],
)
def test_where_there_are_no_facets_the_error_says_so(
    test_app: Any, expected: str
) -> None:
    """A field predicate runs as the need is created, a needimport filter reads the
    imported record, and a variant condition reads the need's fields: none has a check
    context, and a facet read there fails with an error that says so -- ``c``
    undefined, or, where a field is named ``c``, its value having no ``source``. A
    failure that reads no facet reads as it always did."""
    app = test_app
    app.build()
    assert build_warnings(app) == [expected]


def test_a_needflow_variant_condition_says_it_has_no_facets(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``match_variants`` (needflow's variant options) evaluates over the need data
    alone: ``c`` there is undefined, and its warning says why."""
    logged: list[str] = []
    monkeypatch.setattr(
        variants,
        "log_warning",
        lambda _logger, message, *_a, **_k: logged.append(message),
    )
    assert variants.match_variants('[c.source.kind == "page"]:a, b', {}, {}) == "b"
    assert logged == [
        "Error in variant expression 'c.source.kind == \"page\"': name 'c' is not "
        f"defined; {UNAVAILABLE} a variant condition"
    ]


#: an ``eval``-tier facet read: the lambda keeps it out of the parsed tier, so only a
#: bound ``c`` answers it (no brackets: it is also written inside a dynamic function)
ON_INDEX = "(lambda: c.source.path)() == 'index.rst'"

CONF_CHANNELS = f"""\
needs_build_json = True
needs_builder_filter = "{ON_INDEX}"
needs_warnings = {{"off_index": "not ({ON_INDEX})"}}
needs_constraints = {{"on_index": {{"check_0": "{ON_INDEX}", "severity": "CRITICAL"}}}}
needs_links = {{"same_page": {{"derive": {{"kind": "links", "where": "{ON_INDEX}"}}}}}}
needs_fields = {{"first_on_index": {{"nullable": True}}}}
"""

INDEX_CHANNELS = f"""\
Index
=====

.. req:: One
   :id: REQ_001
   :constraints: on_index

.. req:: Two
   :id: REQ_002
   :links: REQ_001[{ON_INDEX}]
   :first_on_index: [[copy("id", filter="{ON_INDEX} and id == 'REQ_001'")]]

.. needextend:: {ON_INDEX}
   :+tags: on_index
"""


@pytest.mark.parametrize(
    "test_app", [_project(CONF_CHANNELS, INDEX_CHANNELS)], indirect=True
)
def test_every_channel_evaluating_a_filter_binds_c(test_app: Any) -> None:
    """Each channel that evaluates a filter through ``eval`` gives it the check context,
    so ``c.source`` reads the facets there: ``needs_builder_filter``, ``needs_warnings``,
    a constraint, a derived field's ``where``, a link condition, ``copy(filter=...)`` and
    a ``needextend``; the views are the corpus's."""
    app = test_app
    app.build()
    assert build_warnings(app) == []
    needs = SphinxNeedsData(app.env).get_needs_view()
    assert needs["REQ_001"]["constraints_passed"] is True
    assert needs["REQ_001"]["same_page"] == ["REQ_002"]
    assert needs["REQ_002"]["same_page"] == ["REQ_001"]
    assert needs["REQ_002"]["first_on_index"] == "REQ_001"
    assert all("on_index" in need["tags"] for need in needs.values())
    written = json.loads(Path(app.outdir, "needs.json").read_text(encoding="utf-8"))
    version = written["versions"][written["current_version"]]
    assert sorted(version["needs"]) == ["REQ_001", "REQ_002"]


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
                    '"where": "c.source.path == \'index.rst\'"}}}\n',
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
    """A derived field's ``where`` may read ``c.source.<facet>`` (another ``c.`` check
    but ``c.is_a`` is refused there): the rule computes (a need links every other one it
    selects), and no read of them is reported."""
    app = test_app
    app.build()
    assert build_warnings(app) == []
    needs = SphinxNeedsData(app.env).get_needs_view()
    assert needs["REQ_001"]["same_file"] == []
    assert needs["REQ_002"]["same_file"] == ["REQ_001"]
