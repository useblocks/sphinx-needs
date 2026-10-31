"""``NeedItemSource``: the one source class, and what became of the five it replaces.

A need's source is one frozen class, :class:`~sphinx_needs.need_item.NeedItemSource`:
its hops, innermost first, and the location facts the hops cannot give yet. The legacy
location keys (``dict_repr``) are one rule per key. ``from_directive`` is the source of a
need a directive creates, for a docutils ``Directive`` as for a ``SphinxDirective``. The
five names of 9.1.0 are deprecated factories building it from their own keywords, until
10.0, and ``add_need`` is deprecated in favour of ``create_need``.

The values each name and each call shape gives are fenced against the base in
``test_need_source_legacy_keys.py``; this module pins the rest.
"""

from __future__ import annotations

import dataclasses
import inspect
import warnings
from pathlib import Path
from typing import Any

import pytest
from sphinx.testing.util import SphinxTestApp

from sphinx_needs import need_item
from sphinx_needs._need_source import (
    NeedSourceHop,
    NeedSourcePhysical,
    NeedSourceSemantic,
)
from sphinx_needs.data import SphinxNeedsData
from sphinx_needs_testkit import assert_no_warnings
from tests.test_need_item_api import core

FIVE = (
    "NeedItemSourceUnknown",
    "NeedItemSourceDirective",
    "NeedItemSourceService",
    "NeedItemSourceExternal",
    "NeedItemSourceImport",
)
"""The source classes of 9.1.0, now names of deprecated factories."""

PAGE_A = NeedSourceHop(kind="page", document="a")
LINED_A = NeedSourceHop(
    kind="page",
    document="a",
    physical=NeedSourcePhysical(root="srcdir", path="a.rst", start_line=5, end_line=6),
    language=".rst",
)
GENERATED = NeedSourceHop(kind="generated")
IMPORTED = NeedSourceHop(kind="file", language=".json")
URL = "http://example.org/a.html#X"
EXTERNAL = NeedSourceHop(kind="external", physical=NeedSourcePhysical(url=URL))


def _keys(
    docname: str | None = None,
    lineno: int | None = None,
    lineno_content: int | None = None,
    external_url: str | None = None,
    is_import: bool = False,
    is_external: bool = False,
) -> dict[str, Any]:
    return {
        "docname": docname,
        "lineno": lineno,
        "lineno_content": lineno_content,
        "external_url": external_url,
        "is_import": is_import,
        "is_external": is_external,
    }


FACTORY_CASES = [
    # (name, its 9.1.0 keywords, the legacy keys 9.1.0 gave, the hops)
    ("NeedItemSourceUnknown", {}, _keys(), ()),
    (
        "NeedItemSourceUnknown",
        {"docname": "a", "lineno": 3},
        _keys("a", 3),
        (PAGE_A,),
    ),
    (
        "NeedItemSourceUnknown",
        {"docname": "a", "lineno": 3, "lineno_content": 4, "is_import": True},
        _keys("a", 3, 4, is_import=True),
        (PAGE_A,),
    ),
    (
        "NeedItemSourceUnknown",
        {"is_external": True, "external_url": URL},
        _keys(external_url=URL, is_external=True),
        (EXTERNAL,),
    ),
    (
        "NeedItemSourceUnknown",
        {"docname": "a", "lineno": 3, "is_external": True, "external_url": URL},
        _keys("a", 3, external_url=URL, is_external=True),
        (EXTERNAL, PAGE_A),
    ),
    (
        # given hops whose first is no external hop: the external hop goes first
        "NeedItemSourceUnknown",
        {"hops": (PAGE_A,), "docname": "a", "is_external": True, "external_url": URL},
        _keys("a", external_url=URL, is_external=True),
        (EXTERNAL, PAGE_A),
    ),
    (
        "NeedItemSourceUnknown",
        {"hops": (LINED_A,), "lineno": 3},
        _keys("a", 3),
        (LINED_A,),
    ),
    (
        "NeedItemSourceDirective",
        {"docname": "a", "lineno": 3, "lineno_content": 4, "parser_lineno": 9},
        _keys("a", 3, 4),
        (PAGE_A,),
    ),
    (
        "NeedItemSourceDirective",
        {"hops": (LINED_A,), "lineno_content": 6},
        _keys("a", 5, 6),
        (LINED_A,),
    ),
    (
        "NeedItemSourceDirective",
        {"hops": (PAGE_A,), "lineno": 3, "lineno_content": 6},
        _keys("a", 3, 6),
        (PAGE_A,),
    ),
    (
        "NeedItemSourceService",
        {"docname": "a", "lineno": 3},
        _keys("a", 3),
        (PAGE_A,),
    ),
    (
        "NeedItemSourceService",
        {"lineno": 3, "hops": (GENERATED, PAGE_A)},
        _keys("a", 3),
        (GENERATED, PAGE_A),
    ),
    (
        "NeedItemSourceExternal",
        {"url": URL},
        _keys(external_url=URL, is_external=True),
        (EXTERNAL,),
    ),
    (
        "NeedItemSourceExternal",
        {"hops": (EXTERNAL,)},
        _keys(external_url=URL, is_external=True),
        (EXTERNAL,),
    ),
    (
        "NeedItemSourceImport",
        {"docname": "a", "lineno": 3, "path": "x.json"},
        _keys("a", 3, is_import=True),
        (NeedSourceHop(kind="file"), PAGE_A),
    ),
    (
        "NeedItemSourceImport",
        {"lineno": 3, "path": "x.json", "hops": (IMPORTED, PAGE_A)},
        _keys("a", 3, is_import=True),
        (IMPORTED, PAGE_A),
    ),
]


def _deprecations(
    caught: list[warnings.WarningMessage],
) -> list[warnings.WarningMessage]:
    return [w for w in caught if issubclass(w.category, DeprecationWarning)]


@pytest.mark.parametrize(
    ("name", "keywords", "keys", "hops"),
    FACTORY_CASES,
    ids=[f"{case[0][14:]}-{'-'.join(case[1]) or 'none'}" for case in FACTORY_CASES],
)
def test_each_old_name_is_a_deprecated_factory_of_the_one_class(
    name: str, keywords: dict[str, Any], keys: dict[str, Any], hops: tuple
):
    """Each name warns where it is read, at its reader's line, and builds the one class
    with the legacy keys 9.1.0's class gave and the hops it had."""
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        factory = getattr(need_item, name)
    (warning,) = _deprecations(caught)
    assert warning.filename == __file__
    message = str(warning.message)
    assert message.startswith(f"sphinx_needs.need_item.{name} is deprecated")
    assert "NeedItemSource" in message.removeprefix(f"sphinx_needs.need_item.{name}")
    assert "10.0" in message

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        source = factory(**keywords)
    assert _deprecations(caught) == [], "the call itself does not warn again"
    assert type(source) is need_item.NeedItemSource
    assert source.dict_repr == keys
    assert source.hops == hops


def test_an_old_name_imported_warns_at_the_import():
    """``from sphinx_needs.need_item import <name>`` -- how sphinx-codelinks 2.0 reads
    one -- warns at the importing line."""
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        from sphinx_needs.need_item import NeedItemSourceUnknown  # noqa: F401
    (warning,) = _deprecations(caught)
    assert warning.filename == __file__
    assert "NeedItemSourceUnknown" in str(warning.message)


def test_the_old_names_are_not_listed_and_a_wrong_name_is_an_attribute_error():
    """``dir()`` lists the one class and not the five deprecated names, so nothing that
    walks the module meets a warning; a name that is neither raises ``AttributeError``,
    without one."""
    names = dir(need_item)
    assert "NeedItemSource" in names
    assert not set(FIVE) & set(names)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        with pytest.raises(AttributeError, match="NeedItemSourceRemoved"):
            need_item.NeedItemSourceRemoved  # noqa: B018
    assert _deprecations(caught) == []


def test_the_one_class():
    """Frozen and slotted; its constructor takes the hops and the facts they cannot
    give, and nothing twice."""
    from sphinx_needs.need_item import NeedItemSource

    assert dataclasses.is_dataclass(NeedItemSource)
    assert "__slots__" in vars(NeedItemSource)
    parameters = inspect.signature(NeedItemSource).parameters
    assert [(p.name, p.kind, p.default) for p in parameters.values()] == [
        ("hops", inspect.Parameter.POSITIONAL_OR_KEYWORD, ()),
        ("lineno", inspect.Parameter.KEYWORD_ONLY, None),
        ("lineno_content", inspect.Parameter.KEYWORD_ONLY, None),
        ("parser_lineno", inspect.Parameter.KEYWORD_ONLY, None),
        ("is_import", inspect.Parameter.KEYWORD_ONLY, False),
    ]
    source = NeedItemSource([LINED_A], lineno=3, lineno_content=4, parser_lineno=9)
    assert source.hops == (LINED_A,)
    with pytest.raises(dataclasses.FrozenInstanceError):
        source.hops = ()  # ty: ignore[invalid-assignment]
    assert NeedItemSource().dict_repr == _keys()
    with pytest.raises(TypeError, match="NeedSourceHop"):
        NeedItemSource(["page"])  # ty: ignore[invalid-argument-type]
    # a need made without a source has the empty one
    need = need_item.NeedItem(
        source=None,
        content=need_item.NeedsContent(doctype=".rst", content=""),
        core=core(),
        extras={},
        links={},
    )
    assert need.source == NeedItemSource()


def test_the_directive_name_keeps_the_parser_line():
    """``NeedItemSourceDirective(parser_lineno=...)`` keeps it, though it is in no
    legacy key: a rendered ``pre_template`` / ``post_template`` is parsed at it."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        source = need_item.NeedItemSourceDirective(
            docname="a", lineno=3, lineno_content=4, parser_lineno=9
        )
    assert source.parser_lineno == 9


class _UnmappedStateMachine:
    """A state machine that cannot map a line: docutils' ``get_source_and_line`` gives
    ``(None, None)`` where its input has no entry for the offset (an ``IndexError``)."""

    def get_source_and_line(self, lineno: int | None = None) -> tuple[None, None]:
        return None, None


def test_from_directive_keeps_the_parser_line_where_the_state_machine_has_none(
    tmp_path: Path,
):
    """Where the line cannot be resolved, ``lineno`` is the directive's own (parser)
    line, as a need directive has recorded it since #1349, and the page hop has none."""
    from types import SimpleNamespace

    from sphinx_needs.need_item import NeedItemSource

    env = SimpleNamespace(
        srcdir=str(tmp_path),
        docname="a",
        doc2path=lambda docname: str(tmp_path / f"{docname}.rst"),
    )
    directive = SimpleNamespace(
        name="req",
        arguments=["title"],
        lineno=7,
        content_offset=8,
        block_text=".. req:: title\n",
        state=SimpleNamespace(
            document=SimpleNamespace(settings=SimpleNamespace(env=env))
        ),
        state_machine=_UnmappedStateMachine(),
    )
    source = NeedItemSource.from_directive(directive)  # ty: ignore[invalid-argument-type]
    assert source.dict_repr["lineno"] == 7
    assert source.parser_lineno == 7
    assert source.lineno_content == 9
    assert [(hop.kind, hop.document) for hop in source.hops] == [("page", "a")]
    assert source.hops[0].physical is not None
    assert source.hops[0].physical.start_line is None


def test_a_name_given_both_keywords_and_hops_keeps_the_hops():
    """The five names refuse no combination (row 2 of the path: no keyword is given
    twice): where 9.1.0 refused a keyword that disagreed with the hops, the hops are the
    source, and a ``lineno`` given is the need's."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        unknown = need_item.NeedItemSourceUnknown(docname="b", hops=(PAGE_A,))
        external = need_item.NeedItemSourceExternal(url="http://b", hops=(EXTERNAL,))
        directive = need_item.NeedItemSourceDirective(
            lineno=9, lineno_content=1, hops=(LINED_A,)
        )
    assert unknown.dict_repr["docname"] == "a"
    assert external.dict_repr["external_url"] == URL
    assert directive.dict_repr["lineno"] == 9


@pytest.mark.parametrize(
    ("docname", "lineno"), [("a", 3), ("a", None), (None, 3), (None, None)]
)
def test_on_page_is_the_source_add_need_builds(docname: str | None, lineno: int | None):
    """``NeedItemSource.on_page(docname, lineno=...)``, the stable spelling outside a
    directive, is the source ``add_need(app, state, docname, lineno, ...)`` and
    ``NeedItemSourceUnknown(docname=, lineno=)`` build: one ``page`` hop, no file, no
    line check; no hop without a document."""
    from sphinx_needs.api.need import _legacy_source
    from sphinx_needs.need_item import NeedItemSource

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        factory = need_item.NeedItemSourceUnknown
    source = NeedItemSource.on_page(docname, lineno=lineno)
    assert source == factory(docname=docname, lineno=lineno)
    assert source == _legacy_source(None, docname=docname, lineno=lineno)
    assert source.dict_repr == _keys(docname, lineno)
    assert source.hops == (() if docname is None else (PAGE_A,))
    parameters = inspect.signature(NeedItemSource.on_page).parameters
    assert [(p.name, p.kind, p.default) for p in parameters.values()] == [
        ("docname", inspect.Parameter.POSITIONAL_OR_KEYWORD, inspect.Parameter.empty),
        ("lineno", inspect.Parameter.KEYWORD_ONLY, None),
    ]


def test_the_module_getattr_is_hidden_from_type_checkers():
    """The five names are served at run time only: a module ``__getattr__`` that a type
    checker sees would type every name of the module as ``Any``, so a misspelt import
    from it would not be reported."""
    import ast

    tree = ast.parse(Path(need_item.__file__).read_text(encoding="utf-8"))
    (guard,) = [
        node
        for node in tree.body
        if isinstance(node, ast.If)
        and any(
            isinstance(inner, ast.FunctionDef) and inner.name == "__getattr__"
            for inner in node.body
        )
    ]
    assert ast.unparse(guard.test) == "not TYPE_CHECKING"
    assert not any(
        isinstance(node, ast.FunctionDef) and node.name == "__getattr__"
        for node in tree.body
    )


def test_the_five_names_are_declared_for_type_checkers_as_they_are_at_run_time():
    """Type checkers do not see the run-time ``__getattr__``, so each of the five names
    is declared for them under ``TYPE_CHECKING``: a function with the keywords of its
    factory, returning ``NeedItemSource``, marked ``@deprecated`` with the run-time
    warning's text. A name imported from 9.1.0's code type-checks, deprecated, rather
    than failing to resolve before 10.0."""
    import ast

    tree = ast.parse(Path(need_item.__file__).read_text(encoding="utf-8"))
    declared = {
        inner.name: inner
        for node in tree.body
        if isinstance(node, ast.If) and ast.unparse(node.test) == "TYPE_CHECKING"
        for inner in node.body
        if isinstance(inner, ast.FunctionDef)
    }
    assert set(FIVE) <= set(declared)
    assert set(need_item._DEPRECATED_SOURCES) == set(FIVE)
    for name in FIVE:
        node = declared[name]
        (decorator,) = node.decorator_list
        assert isinstance(decorator, ast.Call)
        assert ast.unparse(decorator.func) == "deprecated"
        (message,) = decorator.args
        assert isinstance(message, ast.Constant)
        assert message.value == need_item._deprecation_message(name)
        assert ast.unparse(node.returns) == "NeedItemSource"
        arguments = node.args
        assert not (arguments.posonlyargs or arguments.args or arguments.vararg)
        assert arguments.kwarg is None
        declared_parameters = [
            (
                argument.arg,
                ast.unparse(argument.annotation),
                inspect.Parameter.empty
                if default is None
                else ast.literal_eval(default),
            )
            for argument, default in zip(
                arguments.kwonlyargs, arguments.kw_defaults, strict=True
            )
        ]
        runtime = inspect.signature(need_item._DEPRECATED_SOURCES[name])
        assert declared_parameters == [
            (parameter.name, parameter.annotation, parameter.default)
            for parameter in runtime.parameters.values()
        ], name
        assert all(
            parameter.kind is inspect.Parameter.KEYWORD_ONLY
            for parameter in runtime.parameters.values()
        )
        assert runtime.return_annotation == "NeedItemSource"


@pytest.mark.parametrize(
    ("hops", "given", "lineno"),
    [
        pytest.param((LINED_A,), 3, 3, id="given-wins-over-the-first-hops-line"),
        pytest.param((LINED_A,), None, 5, id="else-the-first-hops-line"),
        pytest.param((PAGE_A,), None, None, id="else-none"),
        pytest.param((PAGE_A, LINED_A), None, None, id="the-first-hop-only"),
    ],
)
def test_lineno_is_as_given_else_the_first_hops_line(
    hops: tuple, given: int | None, lineno: int | None
):
    """The rule of ``lineno``: a test-report need's first hop is the test function, whose
    line is not the need's."""
    from sphinx_needs.need_item import NeedItemSource

    source = NeedItemSource(hops, lineno=given)
    assert source.dict_repr["lineno"] == lineno
    assert source.lineno == lineno


@pytest.mark.parametrize(
    ("hops", "is_import", "keys"),
    [
        pytest.param((EXTERNAL,), False, _keys(external_url=URL, is_external=True)),
        pytest.param(
            (NeedSourceHop(kind="external"), PAGE_A),
            False,
            _keys("a", is_external=True),
            id="external-without-a-url",
        ),
        pytest.param((PAGE_A, EXTERNAL), False, _keys("a"), id="external-not-first"),
        pytest.param(
            (IMPORTED, PAGE_A), False, _keys("a"), id="a-file-hop-is-no-import"
        ),
        pytest.param((IMPORTED, PAGE_A), True, _keys("a", is_import=True)),
    ],
)
def test_the_legacy_keys_one_rule_each(
    hops: tuple, is_import: bool, keys: dict[str, Any]
):
    """``docname`` is the placement's document, ``is_external`` / ``external_url`` an
    external first hop's, ``is_import`` as given: no hop says a ``needimport`` read the
    file (an included rst file is a ``file`` hop too)."""
    from sphinx_needs.need_item import NeedItemSource

    assert NeedItemSource(hops, is_import=is_import).dict_repr == keys


def test_the_class_and_the_hop_types_are_public_from_the_api():
    import sphinx_needs.api
    from sphinx_needs import _need_source

    for name, module in (
        ("NeedItemSource", need_item),
        ("NeedSourceHop", _need_source),
        ("NeedSourcePhysical", _need_source),
        ("NeedSourceSemantic", _need_source),
    ):
        assert name in sphinx_needs.api.__all__
        assert getattr(sphinx_needs.api, name) is getattr(module, name)


def test_the_hops_base_class_is_gone():
    from sphinx_needs import _need_source

    assert not hasattr(_need_source, "HopsSource")


FROM_DIRECTIVE_EXT = '''\
"""Directives creating their needs with ``NeedItemSource.from_directive``."""

from docutils.parsers.rst import Directive
from sphinx.util.docutils import SphinxDirective

from sphinx_needs.api import NeedItemSource, NeedSourceHop, create_need


class Plain(Directive):
    """A docutils directive, as sphinx-test-reports' are: no ``env``, no
    ``get_source_info``."""

    has_content = True

    def run(self):
        env = self.state.document.settings.env
        first = [NeedSourceHop(kind="code"), NeedSourceHop(kind="file")]
        need, nodes = create_need(
            env.app,
            self.state,
            NeedItemSource.from_directive(self, first=first),
            "req",
            "plain",
            id="R_PLAIN",
        )
        return nodes


class Sphinxy(SphinxDirective):
    has_content = True

    def run(self):
        need, nodes = create_need(
            self.env.app,
            self.state,
            NeedItemSource.from_directive(self),
            "req",
            "sphinxy",
            id="R_SPHINXY",
        )
        return nodes


def setup(app):
    app.add_directive("plain", Plain)
    app.add_directive("sphinxy", Sphinxy)
    return {"parallel_read_safe": True}
'''


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "files": [
                (
                    Path("conf.py"),
                    "import sys\nfrom pathlib import Path\n\n"
                    "sys.path.insert(0, str(Path(__file__).parent))\n"
                    'sys.modules.pop("from_directive_ext", None)\n'
                    'extensions = ["sphinx_needs", "from_directive_ext"]\n'
                    # shifts the parser's lines: from_directive gives the written one
                    'rst_prolog = ".. |a| replace:: A\\n\\n.. |b| replace:: B\\n"\n',
                ),
                (Path("from_directive_ext.py"), FROM_DIRECTIVE_EXT),
                (
                    Path("index.rst"),
                    "Page\n====\n\n.. plain::\n\n   body\n\n.. sphinxy::\n\n"
                    "   body\n\n.. req:: a need\n   :id: R_NEED\n\n   body\n",
                ),
            ],
        }
    ],
    indirect=True,
)
def test_from_directive_gives_a_need_directive_s_source(test_app: SphinxTestApp):
    """A docutils ``Directive`` and a ``SphinxDirective`` get the source a need directive
    records: the line the directive is written on (not the parser's, which
    ``rst_prolog`` shifts), its parser line, its content offset, and the page's hop with
    the directive's lines, after the hops given as ``first``."""
    from sphinx_needs.need_item import NeedItemSource

    app = test_app
    app.build()
    assert_no_warnings(app)
    needs = SphinxNeedsData(app.env).get_needs_view()
    prolog = 4  # its three lines, and the blank line Sphinx adds after them
    for need_id, line, end in (("R_PLAIN", 4, 6), ("R_SPHINXY", 8, 10)):
        source = needs[need_id].source
        assert type(source) is NeedItemSource
        assert needs[need_id]["lineno"] == line
        assert source.parser_lineno == line + prolog
        assert source.lineno_content == line + prolog + 2
        page = source.hops[-1]
        assert page.document == "index"
        assert page.physical is not None
        assert (page.physical.start_line, page.physical.end_line) == (line, end)
    assert [hop.kind for hop in needs["R_PLAIN"].source.hops] == [
        "code",
        "file",
        "page",
    ]
    # the need directive's own source is the same construction
    directive = needs["R_NEED"].source
    assert type(directive) is NeedItemSource
    assert needs["R_NEED"]["lineno"] == 12
    assert directive.parser_lineno == 12 + prolog


# --- what create_need records of a source given on a page, or external -------------

ON_PAGE_EXT = '''\
"""A directive creating needs on its page through the stable spellings, and external
needs through ``add_external_need``."""

from docutils.parsers.rst import Directive

from sphinx_needs.api import (
    NeedItemSource,
    NeedSourceHop,
    add_external_need,
    create_need,
    ingest_need_record,
)


class OnPage(Directive):
    def run(self):
        env = self.state.document.settings.env
        _, created = create_need(
            env.app,
            self.state,
            NeedItemSource.on_page(env.docname, lineno=self.lineno),
            "req",
            "created on its page",
            id="R_ON_PAGE",
        )
        ingested, _ = ingest_need_record(
            env.app,
            self.state,
            {"id": "R_INGESTED", "type": "req", "title": "ingested on its page"},
            need_source=NeedItemSource.on_page(env.docname, lineno=self.lineno),
        )
        two_pages = NeedItemSource(
            (
                NeedSourceHop(kind="page", document="inc"),
                NeedSourceHop(kind="page", document="index"),
            ),
            lineno=self.lineno,
        )
        _, two = create_need(
            env.app, self.state, two_pages, "req", "two pages", id="R_TWO_PAGES"
        )
        add_external_need(
            env.app,
            "req",
            "external",
            id="R_EXTERNAL",
            external_url="http://example.org/e.html#R_EXTERNAL",
            sections=["Inner", "Outer"],
        )
        add_external_need(
            env.app,
            "req",
            "external, no sections",
            id="R_EXTERNAL_BARE",
            external_url="http://example.org/e.html#R_EXTERNAL_BARE",
        )
        return [*created, *ingested, *two]


def setup(app):
    app.add_directive("on-page", OnPage)
    return {"parallel_read_safe": True}
'''

ON_PAGE_PROJECT = {
    "buildername": "html",
    "files": [
        (
            Path("conf.py"),
            "import sys\nfrom pathlib import Path\n\n"
            "sys.path.insert(0, str(Path(__file__).parent))\n"
            'sys.modules.pop("on_page_ext", None)\n'
            'extensions = ["sphinx_needs", "on_page_ext"]\n'
            'exclude_patterns = ["inc.rst", "_build"]\n',
        ),
        (Path("on_page_ext.py"), ON_PAGE_EXT),
        # the directive in an included file: the page is the document's, not that file
        (Path("index.rst"), "Page\n====\n\n.. include:: inc.rst\n"),
        (Path("inc.rst"), "Sub\n---\n\n.. on-page::\n"),
    ],
}


@pytest.mark.parametrize("test_app", [ON_PAGE_PROJECT], indirect=True)
def test_create_need_records_an_on_page_need_s_page_path(test_app: SphinxTestApp):
    """``NeedItemSource.on_page`` builds a page hop with no path; ``create_need`` (and
    ``ingest_need_record``, through it) records the page's path -- the document's file,
    not the included file the directive is in -- and its suffix, with no line. The
    legacy keys are ``on_page``'s, as they were."""
    from sphinx_needs.need_item import NeedItemSource

    app = test_app
    app.build()
    assert_no_warnings(app)
    needs = SphinxNeedsData(app.env).get_needs_view()
    for need_id in ("R_ON_PAGE", "R_INGESTED"):
        source = needs[need_id].source
        assert source.hops == (
            NeedSourceHop(
                kind="page",
                document="index",
                physical=NeedSourcePhysical(root="srcdir", path="index.rst"),
                language=".rst",
                semantic=(
                    NeedSourceSemantic(kind="section", name="Page"),
                    NeedSourceSemantic(kind="section", name="Sub"),
                ),
            ),
        ), need_id
        lineno = needs[need_id]["lineno"]
        assert lineno is not None
        assert (
            source.dict_repr == NeedItemSource.on_page("index", lineno=lineno).dict_repr
        )


@pytest.mark.parametrize("test_app", [ON_PAGE_PROJECT], indirect=True)
def test_create_need_records_the_file_of_each_page_hop_given_none(
    test_app: SphinxTestApp,
):
    """Every page hop with a document and no path is given its document's file, not
    the placement alone: a source written by hand with two page hops (the included
    file's document, then the page)."""
    app = test_app
    app.build()
    assert_no_warnings(app)
    hops = SphinxNeedsData(app.env).get_needs_view()["R_TWO_PAGES"].source.hops
    assert [(hop.document, hop.physical, hop.language) for hop in hops] == [
        ("inc", NeedSourcePhysical(root="srcdir", path="inc.rst"), ".rst"),
        ("index", NeedSourcePhysical(root="srcdir", path="index.rst"), ".rst"),
    ]


@pytest.mark.parametrize("test_app", [ON_PAGE_PROJECT], indirect=True)
def test_add_external_need_puts_its_sections_on_the_external_hop(
    test_app: SphinxTestApp,
):
    """``sections`` (innermost first, as the legacy field holds them) are the
    ``external`` hop's semantic location, outermost first; the legacy ``sections`` is
    the value given. Without ``sections``, the hop's semantic location is unknown."""
    app = test_app
    app.build()
    assert_no_warnings(app)
    needs = SphinxNeedsData(app.env).get_needs_view()
    assert needs["R_EXTERNAL"].source.hops == (
        NeedSourceHop(
            kind="external",
            physical=NeedSourcePhysical(url="http://example.org/e.html#R_EXTERNAL"),
            semantic=(
                NeedSourceSemantic(kind="section", name="Outer"),
                NeedSourceSemantic(kind="section", name="Inner"),
            ),
        ),
    )
    assert needs["R_EXTERNAL"]["sections"] == ("Inner", "Outer")
    (bare,) = needs["R_EXTERNAL_BARE"].source.hops
    assert (bare.kind, bare.semantic) == ("external", None)
    assert needs["R_EXTERNAL_BARE"]["sections"] == ()


# --- add_need's deprecation --------------------------------------------------------

ADD_NEED_WARNING = (
    "add_need is deprecated and will be removed in sphinx-needs 10.0: use "
    "sphinx_needs.api.create_need, which takes the need's location as a NeedItemSource "
    "(NeedItemSource.from_directive(self) in a directive) and its fields and links as "
    "two mappings; see 'Migrating from add_need' in the API documentation"
)


def test_add_need_warns_at_the_line_of_the_extension_calling_it(
    make_app, tmp_path: Path
):
    """Each call of ``add_need`` is one ``DeprecationWarning`` at its caller's file and
    line -- an extension's, never sphinx-needs' -- and no Sphinx warning, so a ``-W``
    build of a project using such an extension still passes. ``create_need``,
    ``ingest_need_record``, ``add_external_need`` and ``generate_need`` do not warn."""
    import shutil

    from tests.test_need_source_legacy_keys import (
        SHAPE_IDS_ADDED,
        SHAPE_IDS_EXTERNAL,
        SHAPES_PROJECT,
    )

    shutil.copytree(SHAPES_PROJECT, tmp_path / "project")
    app = make_app("html", srcdir=tmp_path / "project", freshenv=True)
    try:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            app.build()
        assert_no_warnings(app)
    finally:
        app.cleanup()
    add_need_warnings = [
        w for w in caught if str(w.message).startswith("add_need is deprecated")
    ]
    calls = [
        need_id
        for need_id in (*SHAPE_IDS_ADDED, *SHAPE_IDS_EXTERNAL)
        if need_id.startswith("SHAPE_ADD_")
    ]
    assert len(add_need_warnings) == len(calls)
    for warning in add_need_warnings:
        assert warning.category is DeprecationWarning
        assert str(warning.message) == ADD_NEED_WARNING
        assert Path(warning.filename).name == "source_shapes_ext.py"


# --- the comparison key of a need that only moved -----------------------------------


def _moved_pairs() -> dict[str, tuple[Any, Any]]:
    """For each kind of source, the source of a need and of the same need written lower
    (every line field and every hop line moved by 10)."""
    from sphinx_needs.need_item import NeedItemSource

    def lined(start: int) -> NeedSourceHop:
        return dataclasses.replace(
            LINED_A,
            physical=NeedSourcePhysical(
                root="srcdir", path="a.rst", start_line=start, end_line=start + 1
            ),
        )

    def fragment(start: int) -> NeedSourceHop:
        return NeedSourceHop(
            kind="file",
            physical=NeedSourcePhysical(
                root="srcdir", path="f.rst", start_line=start, end_line=start + 2
            ),
            language=".rst",
        )

    def directive(at: int) -> Any:
        return NeedItemSource(
            (lined(at),), lineno=at, lineno_content=at + 2, parser_lineno=at + 4
        )

    def included(at: int) -> Any:
        return NeedItemSource(
            (fragment(at), PAGE_A), lineno=at, lineno_content=at + 1, parser_lineno=at
        )

    return {
        "directive": (directive(5), directive(15)),
        "included": (included(3), included(13)),
        "service": (
            NeedItemSource((GENERATED, lined(5)), lineno=9),
            NeedItemSource((GENERATED, lined(15)), lineno=19),
        ),
        "import": (
            NeedItemSource((IMPORTED, lined(5)), lineno=9, is_import=True),
            NeedItemSource((IMPORTED, lined(15)), lineno=19, is_import=True),
        ),
        "api": (
            NeedItemSource.on_page("a", lineno=3),
            NeedItemSource.on_page("a", lineno=13),
        ),
    }


@pytest.mark.parametrize("kind", ["directive", "included", "service", "import", "api"])
def test_a_need_that_only_moved_compares_equal_through_the_seam(kind: str):
    """``NeedItemSource._without_lines()`` is the key an incremental build compares a
    re-read need by (``NeedItem.moved_only``): the source without its line fields and
    without its hops' lines -- the key ``_without_lines`` built from outside the class
    before -- so a need that only moved is the same need, and one from another file is
    not."""
    from sphinx_needs.need_item import _without_lines

    before, after = _moved_pairs()[kind]
    assert before != after
    assert before._without_lines() == after._without_lines()
    assert _without_lines(before) == before._without_lines()
    # the key #2414 built from the outside: the class, and its fields but the lines
    assert before._without_lines() == (
        type(before),
        (
            ("hops", tuple(hop._without_lines() for hop in before.hops)),
            ("is_import", before.is_import),
        ),
    )
    for hop in before.hops:
        if hop.physical is not None:
            assert hop._without_lines().physical == dataclasses.replace(
                hop.physical, start_line=None, end_line=None
            )
    assert _need(before).moved_only(_need(after))
    assert not _need(before).moved_only(_need(before))
    # placed elsewhere is no move
    from sphinx_needs.need_item import NeedItemSource

    assert not _need(before).moved_only(_need(NeedItemSource.on_page("b", lineno=3)))


def _need(source: Any) -> need_item.NeedItem:
    return need_item.NeedItem(
        source=source,
        content=need_item.NeedsContent(doctype=".rst", content=""),
        core=core(),
        extras={},
        links={},
    )


def test_a_field_added_to_the_source_is_compared_by_the_seam():
    """The seam fails safe, as #2414's key did: it compares every field but the named
    line fields and ``dict_repr``, so a field added to the class later is compared,
    and a need differing in it counts as changed (re-written), never as "only moved"."""
    from sphinx_needs.need_item import NeedItemSource

    @dataclasses.dataclass(slots=True, frozen=True, init=False, repr=False)
    class Faceted(NeedItemSource):
        facet: str

        def __init__(self, hops: Any = (), *, facet: str, **keywords: Any) -> None:
            NeedItemSource.__init__(self, hops, **keywords)
            object.__setattr__(self, "facet", facet)

    one = Faceted((PAGE_A,), lineno=3, facet="one")
    other = Faceted((PAGE_A,), lineno=3, facet="other")
    moved = Faceted((PAGE_A,), lineno=13, facet="one")
    assert one != other
    assert one._without_lines() != other._without_lines()
    assert not _need(one).moved_only(_need(other))
    assert _need(one).moved_only(_need(moved))


class _ProtocolSource:
    """A third party's source, which obeys ``NeedItemSourceProtocol`` only."""

    def __init__(self, lineno: int) -> None:
        self.lineno = lineno

    @property
    def dict_repr(self) -> dict[str, Any]:
        return _keys("a", self.lineno)


@dataclasses.dataclass(frozen=True)
class _DataclassSource:
    """A third party's source that is a dataclass with hops and a line."""

    hops: tuple[NeedSourceHop, ...]
    lineno: int

    @property
    def dict_repr(self) -> dict[str, Any]:
        return _keys("a", self.lineno)


def test_a_third_party_source_takes_the_fallback_not_the_seam():
    """``_without_lines`` keeps #2414's fallback for a source that is no
    ``NeedItemSource``: one that is no dataclass is compared as it is (so a change of
    its line is a change, never a move); a dataclass is compared by its fields but the
    line fields, its hops without their lines."""
    from sphinx_needs.need_item import _without_lines

    plain = _ProtocolSource(3)
    assert _without_lines(plain) is plain
    assert not _need(plain).moved_only(_need(_ProtocolSource(13)))

    def lined(start: int, path: str = "a.rst") -> NeedSourceHop:
        return dataclasses.replace(
            LINED_A,
            physical=NeedSourcePhysical(
                root="srcdir", path=path, start_line=start, end_line=start + 1
            ),
        )

    before = _DataclassSource((lined(5),), 5)
    assert _need(before).moved_only(_need(_DataclassSource((lined(15),), 15)))
    assert not _need(before).moved_only(
        _need(_DataclassSource((lined(15, "b.rst"),), 15))
    )


def test_what_is_stable_of_the_one_class():
    """What ``NeedItemSource`` promises as stable, and nothing more: its name, public
    from ``sphinx_needs.api``, and the two constructors' signatures. (The general
    constructor and its keywords are provisional; ``test_the_one_class`` pins them as
    they are today, which is not a promise.) A change here is a change of the stable
    API: it needs a deprecation."""
    import sphinx_needs.api
    from sphinx_needs.need_item import NeedItemSource

    assert sphinx_needs.api.NeedItemSource is NeedItemSource
    assert NeedItemSource.__name__ == "NeedItemSource"

    def described(function: Any) -> list[tuple[str, Any, Any]]:
        return [
            (parameter.name, parameter.kind, parameter.default)
            for parameter in inspect.signature(function).parameters.values()
        ]

    positional = inspect.Parameter.POSITIONAL_OR_KEYWORD
    keyword = inspect.Parameter.KEYWORD_ONLY
    empty = inspect.Parameter.empty
    assert described(NeedItemSource.from_directive) == [
        ("directive", positional, empty),
        ("first", keyword, ()),
    ]
    assert described(NeedItemSource.on_page) == [
        ("docname", positional, empty),
        ("lineno", keyword, None),
    ]


def test_with_hops_keeps_every_other_field():
    """``create_need``'s one write on a source replaces its hops and nothing else: the
    given ``lineno``, ``lineno_content``, ``parser_lineno`` (the template's parse
    offset reads it) and ``is_import`` are kept, and the legacy keys are recomputed."""
    from sphinx_needs.need_item import NeedItemSource

    bare = NeedSourceHop(kind="page", document="index")
    filled = NeedSourceHop(
        kind="page",
        document="index",
        physical=NeedSourcePhysical(root="srcdir", path="index.rst"),
    )
    source = NeedItemSource(
        (bare,), lineno=3, lineno_content=4, parser_lineno=2, is_import=True
    )
    new = source._with_hops((filled,))
    assert new.hops == (filled,)
    assert (new._lineno, new.lineno_content, new.parser_lineno, new.is_import) == (
        3,
        4,
        2,
        True,
    )
    assert new.dict_repr == source.dict_repr
