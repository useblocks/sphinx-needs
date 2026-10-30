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
from sphinx_needs._need_source import NeedSourceHop, NeedSourcePhysical
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
