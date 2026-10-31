"""The source hops of a need: where its text came from (provisional, behaviour-neutral).

Every ``NeedItemSource*`` class carries ``hops``, innermost first, and computes the
legacy location keys from them plus a few stored legacy facts; the doctree-read walk
fills the placement hop's semantic location once. What every build of the suite must
hold is fenced in ``conftest.py`` (``_need_source_fence``). This module pins the rest:
the constructors, equality, pickling and the one write, on the classes; and on a project
that exercises each producer (includes, a nested include, ``list2need`` and a service in
an included file, ``rst_prolog``, MyST with an include, the py, c, cpp, js, rst and std
domains, an autodoc docstring), every need's hops, a parallel build and an incremental
one.
"""

from __future__ import annotations

import ast
import dataclasses
import inspect
import pickle
import shutil
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from sphinx.testing.util import SphinxTestApp
from sphinx.util.parallel import parallel_available
from syrupy.assertion import SnapshotAssertion

import sphinx_needs.directives.need
import sphinx_needs.needs
from sphinx_needs import need_item
from sphinx_needs._need_source import (
    NeedSourceHop,
    NeedSourcePhysical,
    NeedSourceSemantic,
    block_check,
    fence_check,
    project_legacy,
)
from sphinx_needs.api import get_needs_view
from sphinx_needs.data import SphinxNeedsData
from sphinx_needs.need_item import (
    NeedItem,
    NeedItemSourceDirective,
    NeedItemSourceExternal,
    NeedItemSourceImport,
    NeedItemSourceProtocol,
    NeedItemSourceService,
    NeedItemSourceUnknown,
    NeedsContent,
)
from sphinx_needs_testkit import assert_no_warnings
from tests.test_need_item_api import core

PROJECT = Path(__file__).parent / "doc_test" / "doc_need_source_hops"
"""The project; its source directory is ``docs``, and ``outside`` holds files outside it."""

PAGE_A = NeedSourceHop(
    kind="page",
    document="a",
    physical=NeedSourcePhysical(root="srcdir", path="a.rst"),
    language=".rst",
)


def _fragment(path: str, line: int) -> NeedSourceHop:
    return NeedSourceHop(
        kind="file",
        physical=NeedSourcePhysical(
            root="srcdir", path=path, start_line=line, end_line=line + 1
        ),
        language=".rst",
    )


def _sources() -> dict[str, NeedItemSourceProtocol]:
    """One source of each class, built with hops as the producers build them."""
    return {
        "directive": NeedItemSourceDirective(
            lineno_content=6,
            parser_lineno=20,
            hops=(_fragment("frag/a.rst", 4), PAGE_A),
        ),
        "service": NeedItemSourceService(
            lineno=25,
            hops=(
                NeedSourceHop(
                    kind="generated",
                    semantic=(NeedSourceSemantic(kind="service", name="probe"),),
                ),
                PAGE_A,
            ),
        ),
        "import": NeedItemSourceImport(
            lineno=12,
            path="imp.json",
            hops=(
                NeedSourceHop(
                    kind="file",
                    physical=NeedSourcePhysical(root="srcdir", path="imp.json"),
                    language=".json",
                ),
                PAGE_A,
            ),
        ),
        "external": NeedItemSourceExternal(url="http://example.org/a.html#X"),
        "unknown": NeedItemSourceUnknown(docname="a", lineno=3, hops=(PAGE_A,)),
    }


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        (
            NeedItemSourceDirective(docname="a", lineno=3, lineno_content=4),
            "NeedItemSource(docname='a', lineno=3, lineno_content=4, external_url=None, "
            "is_import=False, is_external=False, parser_lineno=None)",
        ),
        (
            NeedItemSourceService(docname="a", lineno=3),
            "NeedItemSource(docname='a', lineno=3, lineno_content=None, "
            "external_url=None, is_import=False, is_external=False, parser_lineno=None)",
        ),
        (
            NeedItemSourceImport(docname="a", lineno=3, path="x.json"),
            "NeedItemSource(docname='a', lineno=3, lineno_content=None, "
            "external_url=None, is_import=True, is_external=False, parser_lineno=None)",
        ),
        (
            NeedItemSourceExternal(url="http://x"),
            "NeedItemSource(docname=None, lineno=None, lineno_content=None, "
            "external_url='http://x', is_import=False, is_external=True, "
            "parser_lineno=None)",
        ),
        (
            NeedItemSourceUnknown(docname="a", lineno=3),
            "NeedItemSource(docname='a', lineno=3, lineno_content=None, "
            "external_url=None, is_import=False, is_external=False, parser_lineno=None)",
        ),
    ],
)
def test_the_legacy_constructors_and_reprs_are_unchanged(
    source: NeedItemSourceProtocol, expected: str
):
    """Every name keeps its keywords, and builds the one class, whose repr is its legacy
    keys and its parser line: the hops are not in it, nor in the repr of a need."""
    assert repr(source) == expected
    assert str(source) == expected


def test_the_legacy_keys_come_from_the_hops():
    """``dict_repr`` is what it was, for sources built from hops alone."""
    sources = _sources()
    assert sources["directive"].dict_repr == {
        "docname": "a",
        "lineno": 4,
        "lineno_content": 6,
        "external_url": None,
        "is_import": False,
        "is_external": False,
    }
    assert sources["service"].dict_repr["docname"] == "a"
    assert sources["service"].dict_repr["lineno"] == 25
    assert sources["import"].dict_repr["is_import"] is True
    assert sources["import"].dict_repr["lineno"] == 12
    assert sources["external"].dict_repr == {
        "docname": None,
        "lineno": None,
        "lineno_content": None,
        "external_url": "http://example.org/a.html#X",
        "is_import": False,
        "is_external": True,
    }
    assert sources["unknown"].dict_repr["docname"] == "a"


def test_a_directive_without_a_true_line_stores_lineno():
    """Where the first hop has no line (autodoc, unmapped), ``lineno`` is stored."""
    hops = (
        NeedSourceHop(
            kind="code",
            physical=NeedSourcePhysical(root="srcdir", path="mod.py"),
            semantic=(NeedSourceSemantic(kind="py:docstring", name="mod.f"),),
        ),
        PAGE_A,
    )
    source = NeedItemSourceDirective(lineno=5, lineno_content=7, hops=hops)
    assert source.lineno == 5
    assert source.dict_repr["lineno"] == 5
    # without one, the need has no lineno: nothing is refused (row 2 of the path)
    assert (
        NeedItemSourceDirective(lineno_content=7, hops=hops).dict_repr["lineno"] is None
    )


def test_a_missing_keyword_is_refused_without_hops():
    """A keyword a name's signature requires is still required, and a hop is a
    ``NeedSourceHop``; the keywords only the hops could have given are no longer
    required (row 2 of the path: no keyword is given twice)."""
    with pytest.raises(TypeError, match="'lineno'"):
        NeedItemSourceService(docname="a")
    with pytest.raises(TypeError, match="'path'"):
        NeedItemSourceImport(docname="a", lineno=1)
    with pytest.raises(TypeError, match="NeedSourceHop"):
        NeedItemSourceService(lineno=1, hops=("a",))


def _need(source: NeedItemSourceProtocol) -> NeedItem:
    """A need of ``source``, its core the need item API tests' (one core to update when
    a core field is added)."""
    return NeedItem(
        source=source,
        content=NeedsContent(doctype=".rst", content=""),
        core=core(),
        extras={},
        links={},
    )


def test_two_needs_differing_only_in_the_fragment_path_are_unequal():
    """``NeedItem.__eq__`` compares the source, and so its hops."""
    one = NeedItemSourceDirective(
        lineno_content=6, hops=(_fragment("frag/a.rst", 4), PAGE_A)
    )
    other = NeedItemSourceDirective(
        lineno_content=6, hops=(_fragment("frag/b.rst", 4), PAGE_A)
    )
    assert one.dict_repr == other.dict_repr
    assert one != other
    assert _need(one) != _need(other)
    assert _need(one) == _need(
        NeedItemSourceDirective(
            lineno_content=6, hops=(_fragment("frag/a.rst", 4), PAGE_A)
        )
    )


@pytest.mark.parametrize("name", list(_sources()))
def test_a_source_pickles_to_an_equal_value(name: str):
    """A source, its placement's semantic location set, survives the environment."""
    source = _sources()[name]
    need = _need(source)
    need._set_placement_semantic((NeedSourceSemantic(kind="section", name="S"),))
    restored = pickle.loads(pickle.dumps(need))
    assert restored == need
    assert restored.source == need.source
    assert restored.source.hops == need.source.hops
    assert repr(restored.source) == repr(need.source)


@pytest.mark.parametrize("name", list(_sources()))
def test_dataclasses_replace_never_silently_breaks(name: str):
    """``dataclasses.replace`` on a source either refuses or rebuilds the same value."""
    source = _sources()[name]
    try:
        replaced = dataclasses.replace(source)
    except TypeError:
        return
    assert replaced == source
    assert replaced.dict_repr == source.dict_repr


def test_the_placement_semantic_is_written_once():
    """The walk's one write: a second raises, a source without hops or placement is
    skipped, and a copy taken before shares the unwalked source."""
    need = _need(_sources()["directive"])
    before = need.copy()
    assert before.source is need.source
    semantic = (NeedSourceSemantic(kind="section", name="S"),)
    need._set_placement_semantic(semantic)
    hops = need.source.hops
    assert hops[0].semantic is None
    assert hops[1].semantic == semantic
    assert before.source.hops[1].semantic is None
    with pytest.raises(ValueError, match="already set"):
        need._set_placement_semantic(semantic)

    external = _need(_sources()["external"])
    external._set_placement_semantic(semantic)
    assert external.source == _sources()["external"]

    class ThirdParty:
        """A source that obeys only ``NeedItemSourceProtocol``."""

        @property
        def dict_repr(self):
            return NeedItemSourceUnknown(docname="a").dict_repr

    third = _need(ThirdParty())
    third._set_placement_semantic(semantic)
    assert isinstance(third.source, ThirdParty)


def test_the_protocol_is_unchanged():
    """``NeedItemSourceProtocol`` is runtime checkable: a member added to it would make
    every third-party source fail ``isinstance``."""
    members = {
        name
        for name in vars(NeedItemSourceProtocol)
        if not name.startswith("_") and name not in {"dict_repr"}
    }
    assert members == set()
    assert "hops" not in vars(NeedItemSourceProtocol)


def test_the_source_of_a_need_is_assigned_in_two_places():
    """``self._source`` is assigned in ``NeedItem.__init__`` and in the one method that
    replaces it: everything else reads it, and every hop is immutable."""
    tree = ast.parse(inspect.getsource(need_item))
    assigning: list[str] = []
    for function in ast.walk(tree):
        if not isinstance(function, ast.FunctionDef | ast.AsyncFunctionDef):
            continue
        for node in ast.walk(function):
            targets: list[ast.expr] = []
            if isinstance(node, ast.Assign):
                targets = node.targets
            elif isinstance(node, ast.AugAssign | ast.AnnAssign):
                targets = [node.target]
            assigning.extend(
                function.name
                for target in targets
                if isinstance(target, ast.Attribute)
                and target.attr == "_source"
                and isinstance(target.value, ast.Name)
                and target.value.id == "self"
            )
            if (
                isinstance(node, ast.Call)
                and node.args[1:2]
                and isinstance(node.args[1], ast.Constant)
                and node.args[1].value == "_source"
            ):
                assigning.append(f"{function.name} (setattr)")
    assert sorted(assigning) == ["__init__", "_set_placement_semantic"]


def test_an_api_need_is_placed_on_its_page():
    """The API's default source (``add_need`` without one: sphinx-codelinks',
    sphinx-test-reports') has one page hop, which the walk gives its semantic location."""
    assert NeedItemSourceUnknown(docname="a").hops == (
        NeedSourceHop(kind="page", document="a"),
    )
    assert NeedItemSourceUnknown().hops == ()


def test_the_placement_is_the_last_hop_with_a_document():
    """Placement is a role: of two hops with a document, the outer one (the last)."""
    page_b = dataclasses.replace(PAGE_A, document="b")
    source = NeedItemSourceUnknown(hops=(PAGE_A, page_b))
    assert source.placement == page_b
    assert source.dict_repr["docname"] == "b"


def test_a_block_check_strips_a_bullet_from_its_first_line_only():
    """A bullet before the directive opens a list item; before any later line of the
    block it is text the block does not have."""
    check = block_check(".. req:: a\n   :id: X\n")
    assert check(["- .. req:: a", "     :id: X"], 1, 2)
    assert check([".. req:: a", "   :id: X"], 1, 2)
    assert not check([".. req:: a", "- :id: X"], 1, 2)
    assert not check([".. req:: a", ":id: XY"], 1, 2)


def test_a_myst_fence_must_be_the_directives_with_its_title():
    """``fence_check`` takes the opening fence of this directive with this title only."""
    check = fence_check("req", "a title")
    assert check(["```{req} a title"], 1, None)
    assert check(["> ::::{req}   a   title  "], 1, None)
    assert not check([":::{note}"], 1, None)
    assert not check([":::{note} a title"], 1, None)
    assert not check(["```{req} a title too"], 1, None)
    assert not check(["```{req}"], 1, None)
    assert not check([":id: X"], 1, None)
    assert fence_check("req", "")(["```{req}"], 1, None)


# --- the project ---------------------------------------------------------------------


def _build(
    make_app: Callable[..., SphinxTestApp],
    srcdir: Path,
    titles: dict[str, str] | None = None,
    **kwargs: Any,
) -> dict[str, tuple[NeedSourceHop, ...]]:
    """Build the project, and return every need's hops (and fill ``titles``, if given)."""
    app = make_app("html", srcdir=srcdir, **kwargs)
    try:
        app.build()
        assert_no_warnings(app)
        if titles is not None:
            titles.update(
                (need_id, need["title"])
                for need_id, need in SphinxNeedsData(app.env).get_needs_view().items()
            )
        return {
            need_id: need.source.hops
            for need_id, need in SphinxNeedsData(app.env).get_needs_view().items()
        }
    finally:
        app.cleanup()


def _compact(hop: NeedSourceHop) -> str:
    """One hop on one line, for a snapshot that reads with the files.

    ``kind [document] root:path:start-end | url (language) :: semantic, ...``
    """
    parts = [hop.kind]
    if hop.document is not None:
        parts.append(f"[{hop.document}]")
    if (physical := hop.physical) is not None:
        if physical.url is not None:
            parts.append(physical.url)
        else:
            where = f"{physical.root}:{physical.path}"
            if physical.start_line is not None:
                where += f":{physical.start_line}-{physical.end_line}"
            parts.append(where)
    if hop.language is not None:
        parts.append(f"({hop.language})")
    if hop.origin is not None:
        parts.append(f"origin={hop.origin}")
    if hop.semantic is not None:
        parts.append(
            ":: "
            + " > ".join(
                f"{entry.kind} {entry.name!r}"
                + "".join(f" {key}={value!r}" for key, value in entry.extras)
                for entry in hop.semantic
            )
        )
    return " ".join(parts)


def _copy(tmp_path: Path) -> Path:
    """A copy of the project; return its source directory."""
    shutil.copytree(PROJECT, tmp_path / "project")
    return tmp_path / "project" / "docs"


def test_the_hops_of_every_need(
    make_app: Callable[..., SphinxTestApp], tmp_path: Path, snapshot: SnapshotAssertion
):
    """Every producer's hops, on a project with each case the walk and the lines meet.

    Read with the files: ``REQ_AX`` is written on line 4 of ``frag/a.rst``, which
    ``inc_host.rst`` includes, so its first hop is that file's, and the page hop has no
    line; ``REQ_BX`` is in ``frag/b.rst``, which ``frag/a.rst`` includes -- docutils keeps
    no chain of includes, so only the innermost file is a hop. The service and the import
    have their directive's true line, not the parser's (``rst_prolog`` shifts it by 4).
    ``REQ_CFX`` is in a C function, whose ``desc_name`` wraps a ``desc_sig_name``: the
    semantic location names it, and its ``signature`` extra is what the legacy walk reads. ``REQ_DOCSTRINGX`` is in a docstring: a ``code`` hop of
    the module, with no line. ``REQ_MDINCX`` is in a MyST include, whose lines
    myst-parser reports one late: no line.
    """
    titles: dict[str, str] = {}
    hops = _build(make_app, _copy(tmp_path), titles, freshenv=True)
    by_title = {title: need_id for need_id, title in titles.items()}
    assert {
        key: [_compact(h) for h in value] for key, value in hops.items()
    } == snapshot

    def lines(need_id: str) -> list[tuple[str | None, int | None, int | None]]:
        return [
            (h.physical.path, h.physical.start_line, h.physical.end_line)
            if h.physical
            else (None, None, None)
            for h in hops[need_id]
        ]

    assert lines("REQ_HOST1X") == [("inc_host.rst", 4, 7)]
    assert lines("REQ_AX") == [("frag/a.rst", 4, 7), ("inc_host.rst", None, None)]
    assert lines("REQ_BX") == [("frag/b.rst", 1, 2), ("inc_host.rst", None, None)]
    assert lines("REQ_L1X") == [("frag/b.rst", 7, 8), ("inc_host.rst", None, None)]
    assert lines("SVC_A") == [
        (None, None, None),
        ("frag/a.rst", 10, 10),
        ("inc_host.rst", None, None),
    ]
    assert lines("I1") == [("imp.json", None, None), ("imp.rst", 7, 7)]
    assert lines("REQ_MDX") == [("mdpage.md", 11, None)]
    assert lines("REQ_MDL1X") == [("mdpage.md", 29, 29)]
    assert lines("REQ_MDINCX") == [("frag/c.md", None, None), ("mdpage.md", None, None)]
    assert lines("REQ_DOCSTRINGX") == [
        ("../outside/source_hops_module.py", None, None),
        ("autodoc_page.rst", None, None),
    ]
    # an include's slice: the line is the file's, the slice's start in it recovered
    # from the include's options (#2428; it was no line)
    assert lines("REQ_STARTAFTERX") == [
        ("frag/after.rst", 5, 6),
        ("lines.rst", None, None),
    ]
    assert lines("REQ_STARTLINEX") == [
        ("frag/from_line.rst", 4, 5),
        ("lines.rst", None, None),
    ]
    # the text the parser numbered is not the file's: no line, never a guessed one
    assert lines("REQ_SRCREADX") == [("srcread.rst", None, None)]
    assert lines("REQ_COLON2X") == [("mdnest.md", None, None)]
    assert lines("REQ_COLON3X") == [("mdnest.md", None, None)]
    # ... and where the file holds the text, its line
    assert lines("REQ_GRIDX") == [("lines.rst", 13, 14)]
    assert lines("REQ_QUOTEX") == [("mdnest.md", 17, None)]
    # in a slice, the file's lines (#2428): ``.. req:: Alpha`` and ``:id: REQ_HIT_A``
    # on 4-5, where the slice's own count claimed lines 1-2 (``.. req:: Alpha beta``,
    # ``:id: REQ_HIT_AB``), which hold them only as part of a line
    assert lines("REQ_HIT_A") == [
        ("frag/hit.rst", 4, 5),
        ("lines.rst", None, None),
    ]
    # a source-read expansion inside a need's body and a list2need item: the first line
    # holds, a later one does not
    assert lines("REQ_EXPANDX") == [("srcread2.rst", None, None)]
    assert lines("REQ_EXPANDITEMX") == [("srcread3.rst", None, None)]
    # MyST: a need whose body opens another need's fence at once is not given the inner
    # fence's line (the title differs) ...
    assert lines(by_title["outer"]) == [("mdnest.md", None, None)]
    assert lines(by_title["outer three"]) == [("mdnest.md", None, None)]
    # ... except inside an identical twin (same name and title): a KNOWN GAP, the outer
    # takes the inner's fence line, 39, where it is written on 38
    (twin,) = (i for i, t in titles.items() if t == "twin" and i != "REQ_TWIN_INNERX")
    assert lines(twin) == [("mdnest.md", 39, None)]
    # ... while in rst, a slice after an example of the directive (a literal block, then
    # the slice after ``MARK``) gives the need its own lines, 8-9, where the slice's count
    # took the example's, 3-4 (#2428)
    assert lines("REQ_X_TWIN") == [("frag/twin.rst", 8, 9), ("lines.rst", None, None)]
    # lines as docutils numbers them: a form feed, tabs at the documents' tab_width 4
    # (an internal tab in the title, an indenting one), a BOM
    assert lines("REQ_FORMFEEDX") == [("formfeed.rst", 8, 11)]
    assert lines("REQ_TABX") == [("tabs.rst", 4, 7)]
    assert lines("REQ_BOMX") == [("bom.rst", 1, 2)]
    assert lines("REQ_BOMMDX") == [("bommd.md", 1, None)]
    # a line block in the body: its ``|`` is the text's, not a table cell's border
    assert lines("REQ_LINEBLOCKX") == [("p1.rst", 10, 14)]
    # a bullet, and a list table's bullets, before the directive
    assert lines("REQ_LISTITEMX") == [("lines.rst", 20, 21)]
    assert lines("REQ_LISTTABLEX") == [("lines.rst", 25, 26)]
    # outside the source directory, a ``..`` path
    assert lines("REQ_OUTSIDEX") == [
        ("../outside/readme.rst", 4, 5),
        ("lines.rst", None, None),
    ]
    assert lines("REQ_DOCSTRINGX")[0] == (
        "../outside/source_hops_module.py",
        None,
        None,
    )
    # through the API: a page hop with no path, walked
    assert hops["REQ_APIX"] == (
        NeedSourceHop(
            kind="page",
            document="p2",
            semantic=(
                NeedSourceSemantic(kind="section", name="Page 2"),
                NeedSourceSemantic(kind="section", name="Sec"),
            ),
        ),
    )
    assert hops["EXT_X1"] == (
        NeedSourceHop(
            kind="external",
            physical=NeedSourcePhysical(url="http://example.org/remote/page.html#X1"),
        ),
    )

    def semantic(need_id: str) -> list[tuple[str, str]]:
        placement = hops[need_id][-1].semantic
        assert placement is not None
        return [(entry.kind, entry.name) for entry in placement]

    assert semantic("REQ_CFX") == [("section", "Domains"), ("c:function", "cfunc")]
    assert semantic("REQ_CPPMX") == [
        ("section", "Domains"),
        ("cpp:class", "Widget"),
        ("cpp:function", "run"),
    ]
    assert semantic("REQ_PYMX") == [
        ("section", "Domains"),
        ("py:class", "Klass"),
        ("py:method", "meth"),
    ]
    assert semantic("REQ_AX") == [("section", "Host"), ("section", "Frag A section")]
    # a hidden need first in its container: the semantic location holds where it is,
    # and the fence holds the legacy values to it (#2398)
    assert semantic("REQ_HIDONLYX") == [("section", "Hidden")]
    assert semantic("REQ_HIDFUNCX") == [
        ("section", "Hidden"),
        ("py:function", "hidden_f"),
    ]


def test_a_sliced_include_gives_the_file_lines(
    make_app: Callable[..., SphinxTestApp], tmp_path: Path
):
    """The needs of ``lines.rst``'s sliced includes record the lines they are written
    on in their files, and their file hops those lines (#2428)."""
    app = make_app("html", srcdir=_copy(tmp_path), freshenv=True)
    try:
        app.build()
        assert_no_warnings(app)
        needs = SphinxNeedsData(app.env).get_needs_view()

        def lines(need_id: str) -> tuple[int | None, list[tuple[Any, ...]]]:
            return needs[need_id]["lineno"], [
                (h.physical.path, h.physical.start_line, h.physical.end_line)
                for h in needs[need_id].source.hops
                if h.physical is not None
            ]

        assert lines("REQ_STARTAFTERX") == (
            5,
            [("frag/after.rst", 5, 6), ("lines.rst", None, None)],
        )
        assert lines("REQ_STARTLINEX") == (
            4,
            [("frag/from_line.rst", 4, 5), ("lines.rst", None, None)],
        )
        assert lines("REQ_HIT_A") == (
            4,
            [("frag/hit.rst", 4, 5), ("lines.rst", None, None)],
        )
        assert lines("REQ_X_TWIN") == (
            8,
            [("frag/twin.rst", 8, 9), ("lines.rst", None, None)],
        )
    finally:
        app.cleanup()


@pytest.mark.skipif(not parallel_available, reason="Parallel execution not supported")
def test_a_parallel_build_gives_the_same_hops(
    make_app: Callable[..., SphinxTestApp], tmp_path: Path
):
    """The walk runs in the worker that reads the document, and the merge moves whole
    needs: a ``-j 2`` build gives every need the hops a serial build gives it."""
    serial = _build(make_app, _copy(tmp_path / "serial"), freshenv=True)
    parallel = _build(make_app, _copy(tmp_path / "parallel"), freshenv=True, parallel=2)
    assert parallel == serial


def test_an_incremental_build_changes_only_the_edited_pages_hops(
    make_app: Callable[..., SphinxTestApp], tmp_path: Path
):
    """The needs of the pages not read again keep their hops from the environment."""
    srcdir = _copy(tmp_path)
    before = _build(make_app, srcdir, freshenv=True)
    page = srcdir / "p3.rst"
    page.write_text(
        page.read_text(encoding="utf8").replace(
            "Sec\n---\n", "Sec\n---\n\nA paragraph.\n\nNew sub\n~~~~~~~\n"
        ),
        encoding="utf8",
    )
    after = _build(make_app, srcdir, freshenv=False)
    changed = {key for key in before if before[key] != after[key]}
    assert changed == {"REQ_P3X"}
    physical = after["REQ_P3X"][0].physical
    assert physical is not None
    assert (physical.start_line, physical.end_line) == (12, 13)
    placement = after["REQ_P3X"][0].semantic
    assert placement is not None
    assert [entry.name for entry in placement] == ["Page 3", "Sec", "New sub"]


def test_the_semantic_walk_is_independent_of_the_legacy_walk(
    make_app: Callable[..., SphinxTestApp],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    """The placement's semantic location is not read from the legacy walk.

    With the legacy walk's result replaced, the hops still name the true sections and
    objects, and their projection no longer equals the legacy values: the fence that
    compares the two (``conftest.py``) is not a tautology. The session fence is lifted
    for this build, since here the two must differ.
    """
    real = sphinx_needs.directives.need.get_sections_and_signature_and_needs

    def poisoned(node):
        _, _, parent_needs = real(node)
        return ["poison"], None, parent_needs

    monkeypatch.setattr(
        sphinx_needs.directives.need, "get_sections_and_signature_and_needs", poisoned
    )
    monkeypatch.setattr(
        sphinx_needs.needs,
        "analyse_need_locations",
        sphinx_needs.directives.need.analyse_need_locations,
    )
    app = make_app("html", srcdir=_copy(tmp_path), freshenv=True)
    try:
        app.build()
        needs = get_needs_view(app)
        need = needs["REQ_PYMX"]
        assert need["sections"] == ("poison",)
        placement = need.source.placement
        assert project_legacy(placement.semantic) == (("Domains",), "meth")
    finally:
        app.cleanup()
