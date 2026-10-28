"""An incremental build re-writes every page showing a need that changed (#2376).

Sphinx re-reads and writes the documents whose sources changed. A page also shows the
needs of other documents -- a view lists them, a ``:need:`` role names one, a need's links
show their targets and its back links their sources, a dynamic function or a ``derive``
rule reads them, a ``needextend`` changes them -- and before the fix those pages kept the
old values until a full build.

The oracle is a fresh build: after each edit, every page the incremental build leaves
on disk must show what a fresh build of the same sources writes. Diagrams are compared by
their source, which a local extension puts in the page in place of the rendered image, so
no renderer runs.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path

import pytest
from sphinx.testing.util import SphinxTestApp
from sphinx.util.console import strip_colors

from sphinx_needs_testkit import build_warnings

CONF = '''\
from docutils import nodes

extensions = ["sphinx_needs", "sphinxcontrib.plantuml", "sphinx.ext.graphviz"]
needs_fields = {
    "hours": {"schema": {"type": "number"}},
    "backs": {"schema": {"type": "array", "items": {"type": "string"}}},
    "lino": {"schema": {"type": "integer"}},
    "total": {
        "schema": {"type": "number"},
        "derive_by_type": {
            "spec": {"kind": "sum", "field": "hours", "over": "links"},
            "impl": {"kind": "sum", "field": "total", "over": "links"},
        },
    },
}
needs_show_link_title = True
needs_duration_option = "hours"
needs_links = {"mentions": {"derive": {"kind": "content_links"}}}


def _diagram_source(app, doctree, docname):
    """Every diagram as its source, so the page shows what it would draw."""
    from sphinx.ext.graphviz import graphviz
    from sphinxcontrib.plantuml import plantuml

    for node in list(doctree.findall(plantuml)):
        node.replace_self(nodes.literal_block(node["uml"], node["uml"]))
    for node in list(doctree.findall(graphviz)):
        node.replace_self(nodes.literal_block(node["code"], node["code"]))


def setup(app):
    app.connect("doctree-resolved", _diagram_source, priority=999)
'''

PAGES = {
    "index.rst": """\
Index
=====

.. toctree::

   aaa
   reqs
   specs
   copies
   extends
   views
   charts
   roles
   trace
   rollup
   unrelated
""",
    "aaa.rst": """\
First
=====

.. req:: Read first
   :id: AAA_001
   :hours: 1
""",
    "reqs.rst": """\
Requirements
============

Some prose about the requirements.

.. req:: Alpha
   :id: REQ_001
   :status: open
   :hours: 3

.. req:: Beta
   :id: REQ_002
   :status: open
   :hours: 5

   Has a part: :np:`(p1) part one`.

.. req:: Gamma
   :id: REQ_003
   :status: open
   :hours: 1
""",
    "specs.rst": """\
Specifications
==============

The specifications refine the requirements.

.. spec:: Refines alpha
   :id: SPEC_001
   :links: REQ_001

.. spec:: Refines gamma
   :id: SPEC_002
   :links: REQ_003
""",
    "copies.rst": """\
Copies
======

.. spec:: Copies a status
   :id: SPEC_003
   :status: [[copy("status", "REQ_001")]]

   Mentions :need:`REQ_002`.
""",
    "extends.rst": """\
Extends
=======

.. needextend:: IMPL_001
   :status: extended

.. needextend:: type == 'test'
   :+tags: ext
""",
    "views.rst": """\
Views
=====

.. needtable::
   :columns: id, title, status, hours, total, tags

.. needlist::

.. needflow::
   :filter: type in ['req', 'spec']

.. needflow::
   :engine: graphviz

.. needgantt::
   :filter: type == 'req'

.. needsequence::
   :start: SPEC_001

.. needextract::
   :filter: id == 'REQ_001'

.. needuml::

   class "{{ needs['REQ_001'].title }}"

There are :need_count:`type == 'req'` requirements;
the first is titled :ndf:`copy("title", "REQ_001")`.
""",
    "charts.rst": """\
Charts
======

.. needpie::
   :labels: open, other

   status == 'open'
   status != 'open'

.. needbar::
   :xlabels: open, other

   type == 'req' and status == 'open', type == 'req' and status != 'open'
""",
    "roles.rst": """\
Roles
=====

See :need:`REQ_001`, the part :need:`REQ_002.p1`,
what links to :need_incoming:`REQ_002` and what :need_outgoing:`SPEC_002` links to.
""",
    "trace.rst": """\
Trace
=====

.. test:: Tests alpha
   :id: TEST_001
   :links: REQ_001
   :status: [[copy("title")]]
""",
    "rollup.rst": """\
Rollup
======

.. impl:: Sums the specification
   :id: IMPL_002
   :links: SPEC_001
""",
    "unrelated.rst": """\
Unrelated
=========

.. impl:: Stands alone
   :id: IMPL_001

Nothing here shows another need.
""",
}

#: Each edit: the page it changes, the text replaced, its replacement.
EDITS: dict[str, tuple[str, str, str]] = {
    "title": ("reqs.rst", ".. req:: Alpha\n", ".. req:: Alpha prime\n"),
    "status-read-by-function-and-derive": (
        "reqs.rst",
        "   :status: open\n   :hours: 3\n",
        "   :status: closed\n   :hours: 7\n",
    ),
    "link-added": (
        "specs.rst",
        "   :links: REQ_003\n",
        "   :links: REQ_003, REQ_002\n",
    ),
    "need-added": (
        "reqs.rst",
        "   :hours: 1\n",
        "   :hours: 1\n\n.. req:: Delta\n   :id: REQ_004\n   :hours: 2\n",
    ),
    "need-removed": (
        "reqs.rst",
        ".. req:: Gamma\n   :id: REQ_003\n   :status: open\n   :hours: 1\n",
        "",
    ),
    "content-reference-added": (
        "copies.rst",
        "   Mentions :need:`REQ_002`.\n",
        "   Mentions :need:`REQ_002` and :need:`TEST_001`.\n",
    ),
    "extend-by-id-changed": ("extends.rst", ":status: extended", ":status: reviewed"),
    "extend-by-id-removed": (
        "extends.rst",
        ".. needextend:: IMPL_001\n   :status: extended\n",
        "",
    ),
    "extend-by-filter-changed": ("extends.rst", ":+tags: ext", ":+tags: ext2"),
    "link-removed": ("specs.rst", "   :links: REQ_003\n", ""),
    "unrelated-title": ("unrelated.rst", "Stands alone", "Stands tall"),
    "prose": ("specs.rst", "refine the requirements", "detail the requirements"),
    "prose-above-needs": (
        "reqs.rst",
        "Some prose about the requirements.\n",
        "Some prose about the requirements.\n\nAnd more, above the needs.\n",
    ),
}


def _replace(pages: dict[str, str], page: str, old: str, new: str) -> dict[str, str]:
    assert pages[page].count(old) == 1, (page, old)
    return {**pages, page: pages[page].replace(old, new)}


#: ``TEST_001`` (of a type with no rule) linked by an extend, to ``AAA_001``: a need
#: on a page no other link of ``TEST_001`` leads to
_EXTEND_LINKS = _replace(
    PAGES,
    "extends.rst",
    ":+tags: ext\n",
    ":+tags: ext\n\n.. needextend:: TEST_001\n   :+links: AAA_001\n",
)
#: ``IMPL_001`` linked by an extend to ``SPEC_002``, whose ``total`` its rule sums,
#: and an ``impl`` on a page of its own summing ``IMPL_001``'s
_EXTEND_LINK_READ = {
    **_replace(
        _replace(
            PAGES,
            "extends.rst",
            ":status: extended\n",
            ":status: extended\n   :+links: SPEC_002\n",
        ),
        "index.rst",
        "   unrelated\n",
        "   unrelated\n   chain\n",
    ),
    "chain.rst": "Chain\n=====\n\n.. impl:: Sums the extended\n   :id: IMPL_003\n"
    "   :links: IMPL_001\n",
}
#: ``IMPL_001``'s status set by an extend by id, to a copy of ``REQ_002``'s
_EXTEND_CALL = _replace(
    PAGES,
    "extends.rst",
    ":status: extended\n",
    ':status: [[copy("status", "REQ_002")]]\n',
)
#: every test's status set by an extend by filter, to a copy of ``REQ_002``'s
_FILTER_EXTEND_CALL = _replace(
    PAGES, "extends.rst", ":+tags: ext\n", ':status: [[copy("status", "REQ_002")]]\n'
)
#: ``IMPL_001`` linked by an extend with a dynamic function, to ``SPEC_001``'s links
_EXTEND_DYNAMIC_LINKS = _replace(
    PAGES,
    "extends.rst",
    ":status: extended\n",
    ':status: extended\n   :+links: [[copy("links", "SPEC_001")]]\n',
)
#: every test linked by an extend by filter, to ``REQ_002``
_FILTER_EXTEND_LINKS = _replace(
    PAGES, "extends.rst", ":+tags: ext\n", ":+tags: ext\n   :+links: REQ_002\n"
)


def _with_pages(pages: dict[str, str], extra: dict[str, str]) -> dict[str, str]:
    """The project with pages added to it, each named in the toctree."""
    entries = "".join(f"   {name.removesuffix('.rst')}\n" for name in extra)
    return {
        **_replace(pages, "index.rst", "   unrelated\n", "   unrelated\n" + entries),
        **extra,
    }


#: back links read by ``copy``: ``TEST_010`` its own, ``TEST_011`` those
#: ``TEST_010`` copied, ``TEST_012`` ``AAA_001``'s; each on a page of its own
_BACK_COPIES = _with_pages(
    PAGES,
    {
        "own_backs.rst": "Own backs\n=========\n\n.. test:: Copies its back links\n"
        '   :id: TEST_010\n   :backs: [[copy("links_back")]]\n',
        "copied_backs.rst": "Copied backs\n============\n\n.. test:: Copies those\n"
        '   :id: TEST_011\n   :backs: [[copy("backs", "TEST_010")]]\n',
        "other_backs.rst": "Other backs\n===========\n\n.. test:: Copies another's\n"
        '   :id: TEST_012\n   :backs: [[copy("links_back", "AAA_001")]]\n',
    },
)
#: a line number read by a dynamic function, on a page of its own
_LINE_COPY = _with_pages(
    PAGES,
    {
        "lines.rst": "Lines\n=====\n\n.. test:: Copies a line\n   :id: TEST_020\n"
        '   :lino: [[copy("lineno", "REQ_001")]]\n',
    },
)
#: a line number read by a ``derive`` rule of ``test``, ``TEST_001``'s type
_LINE_RULE = {
    **PAGES,
    "conf.py": CONF
    + '\nneeds_fields["lino"] = {"schema": {"type": "integer"}, "derive_by_type": '
    '{"test": {"kind": "copy", "field": "lineno", "from": "REQ_001"}}}\n',
}
_PROSE_ABOVE = EDITS["prose-above-needs"]
_REQ_002_CLOSED = (
    "reqs.rst",
    "   :status: open\n   :hours: 5\n",
    "   :status: closed\n   :hours: 5\n",
)

#: Each scenario: the project before, and after the edit.
SCENARIOS: dict[str, tuple[dict[str, str], dict[str, str]]] = {
    **{name: (PAGES, _replace(PAGES, *edit)) for name, edit in EDITS.items()},
    "extend-links-removed": (
        _EXTEND_LINKS,
        _replace(
            _EXTEND_LINKS,
            "extends.rst",
            "\n.. needextend:: TEST_001\n   :+links: AAA_001\n",
            "",
        ),
    ),
    "extend-links-source-title": (
        _EXTEND_LINKS,
        _replace(_EXTEND_LINKS, "trace.rst", "Tests alpha", "Tests beta"),
    ),
    "extend-links-target-title": (
        _EXTEND_LINKS,
        _replace(_EXTEND_LINKS, "aaa.rst", "Read first\n", "Read first, edited\n"),
    ),
    "extend-link-read-by-rule": (
        _EXTEND_LINK_READ,
        _replace(_EXTEND_LINK_READ, "reqs.rst", "   :hours: 1\n", "   :hours: 4\n"),
    ),
    "extend-call-by-id": (_EXTEND_CALL, _replace(_EXTEND_CALL, *_REQ_002_CLOSED)),
    "extend-call-by-filter": (
        _FILTER_EXTEND_CALL,
        _replace(_FILTER_EXTEND_CALL, *_REQ_002_CLOSED),
    ),
    "extend-dynamic-links": (
        _EXTEND_DYNAMIC_LINKS,
        _replace(
            _EXTEND_DYNAMIC_LINKS,
            "reqs.rst",
            ".. req:: Alpha\n",
            ".. req:: Alpha prime\n",
        ),
    ),
    "filter-extend-links": (
        _FILTER_EXTEND_LINKS,
        _replace(
            _FILTER_EXTEND_LINKS, "reqs.rst", ".. req:: Beta\n", ".. req:: Beta prime\n"
        ),
    ),
    "back-links-read-by-copy": (
        _BACK_COPIES,
        _replace(
            _BACK_COPIES,
            "trace.rst",
            "   :links: REQ_001\n",
            "   :links: REQ_001, TEST_010, AAA_001\n",
        ),
    ),
    "line-read-by-call": (_LINE_COPY, _replace(_LINE_COPY, *_PROSE_ABOVE)),
    "line-read-by-rule": (_LINE_RULE, _replace(_LINE_RULE, *_PROSE_ABOVE)),
    "document-removed": (
        PAGES,
        {
            name: text
            for name, text in _replace(PAGES, "index.rst", "   trace\n", "").items()
            if name != "trace.rst"
        },
    ),
}


def _write(srcdir: Path, pages: dict[str, str]) -> Path:
    """Write the project; a file whose text is the same is left untouched, so that
    Sphinx, which compares modification times, sees only the edited page changed."""
    srcdir.mkdir(parents=True, exist_ok=True)
    for name, text in {"conf.py": CONF, **pages}.items():  # a page may replace conf.py
        path = srcdir / name
        if not path.exists() or path.read_text(encoding="utf-8") != text:
            path.write_text(text, encoding="utf-8")
    for path in srcdir.glob("*.rst"):
        if path.name not in pages:
            path.unlink()
    return srcdir


def _written(app: SphinxTestApp) -> list[str]:
    """The documents the build wrote, from its ``writing output`` lines."""
    status = strip_colors(app._status.getvalue())
    return re.findall(r"writing output\.\.\. \[\s*\d+%\] (\S+)", status)


def _build(
    make_app: Callable[..., SphinxTestApp],
    srcdir: Path,
    *,
    fresh: bool,
    parallel: int = 1,
) -> tuple[list[str], list[str]]:
    """Build, and return the documents written and the warnings."""
    app = make_app("html", srcdir=srcdir, freshenv=fresh, parallel=parallel)
    try:
        app.build()
        return _written(app), build_warnings(app)
    finally:
        app.cleanup()


_BODY = re.compile(
    r'<div class="body" role="main">(.*?)<div class="sphinxsidebar"', re.DOTALL
)
#: The id of a need's container, which hashes where the project is
_CONTAINER_ID = re.compile(r"SNCB-[0-9a-f]+")


def _pages(outdir: Path) -> dict[str, str]:
    """The body of every page, the part a need can show up in."""
    pages = {}
    for path in sorted(outdir.glob("*.html")):
        if path.stem in {"genindex", "search", "permalink"}:
            continue
        match = _BODY.search(path.read_text(encoding="utf-8"))
        assert match is not None, path
        pages[path.stem] = _CONTAINER_ID.sub("SNCB-", match.group(1))
    return pages


def _assert_equivalent(
    make_app: Callable[..., SphinxTestApp],
    tmp_path: Path,
    scenario: str,
    *,
    parallel: int = 1,
) -> list[str]:
    """Build the project, edit it, build incrementally, compare with a fresh build.

    :return: The documents the incremental build wrote.
    """
    before, after = SCENARIOS[scenario]
    incremental = _write(tmp_path / "incremental", before)
    _build(make_app, incremental, fresh=True, parallel=parallel)
    _write(incremental, after)
    written, warnings = _build(make_app, incremental, fresh=False, parallel=parallel)

    fresh = _write(tmp_path / "fresh", after)
    _, fresh_warnings = _build(make_app, fresh, fresh=True, parallel=parallel)

    got = _pages(incremental / "_build" / "html")
    expected = _pages(fresh / "_build" / "html")
    # Sphinx leaves the page of a removed document on disk: only the pages a fresh
    # build writes are compared
    assert expected.keys() <= got.keys()
    stale = sorted(name for name in expected if got[name] != expected[name])
    assert stale == [], f"pages not re-written: {stale} (wrote {written})"
    # the fresh build's warnings name the documents too; the incremental build
    # re-reads only the edited page, so only its own warnings are compared
    assert set(warnings) <= set(fresh_warnings)
    return written


def test_fixture_builds_cleanly(
    make_app: Callable[..., SphinxTestApp], tmp_path: Path
) -> None:
    """The fixture is what the cases below assume: it builds without a warning."""
    srcdir = _write(tmp_path / "src", PAGES)
    _, warnings = _build(make_app, srcdir, fresh=True)
    assert warnings == []


@pytest.mark.parametrize("scenario", SCENARIOS)
def test_incremental_build_equals_fresh_build(
    make_app: Callable[..., SphinxTestApp], tmp_path: Path, scenario: str
) -> None:
    """After the edit, every page on disk is the page a fresh build writes."""
    _assert_equivalent(make_app, tmp_path, scenario)


@pytest.mark.parametrize(
    "scenario", ["title", "link-added", "extend-by-id-changed", "document-removed"]
)
def test_parallel_incremental_build_equals_fresh_build(
    make_app: Callable[..., SphinxTestApp], tmp_path: Path, scenario: str
) -> None:
    """The same with ``-j 2``: the role references of a parallel read are merged."""
    _assert_equivalent(make_app, tmp_path, scenario, parallel=2)


def test_prose_edit_rewrites_only_its_own_page(
    make_app: Callable[..., SphinxTestApp], tmp_path: Path
) -> None:
    """No need changed, so no other page is re-written.

    ``index`` is Sphinx's own: it holds the toctree naming the edited page.
    """
    written = _assert_equivalent(make_app, tmp_path, "prose")
    assert sorted(written) == ["index", "specs"]


def test_edit_above_needs_rewrites_only_the_views(
    make_app: Callable[..., SphinxTestApp], tmp_path: Path
) -> None:
    """Prose added above needs moves them, which a view may show (a ``lineno`` column)
    and nothing else does: only the views are re-written besides the page itself."""
    written = _assert_equivalent(make_app, tmp_path, "prose-above-needs")
    assert sorted(written) == ["charts", "index", "reqs", "views"]


def test_edit_of_a_need_nothing_reads_rewrites_the_views(
    make_app: Callable[..., SphinxTestApp], tmp_path: Path
) -> None:
    """``IMPL_001`` is shown by the views alone: the dynamic functions of the project
    read their own need (``TEST_001``) or a need named in the call (``SPEC_003``), so
    neither of their pages is re-written."""
    written = _assert_equivalent(make_app, tmp_path, "unrelated-title")
    assert sorted(written) == ["charts", "index", "unrelated", "views"]


def test_title_edit_rewrites_the_pages_showing_the_need(
    make_app: Callable[..., SphinxTestApp], tmp_path: Path
) -> None:
    """Not every need-relevant page: a page that shows nothing of the need is not.

    ``views`` and ``charts`` hold views, ``specs`` a need linking to it (whose
    ``derive`` rule reads it), ``copies`` a dynamic function reading it, ``trace`` a need
    linking to it, ``rollup`` a need whose rule reads the ``specs`` one's, ``roles`` a
    role naming it; ``unrelated`` holds a need, but shows nothing of ``REQ_001``, and
    ``extends`` only extends other needs, by id or by a filter, neither of which changed.
    """
    written = _assert_equivalent(make_app, tmp_path, "title")
    assert sorted(written) == [
        "charts",
        "copies",
        "index",
        "reqs",
        "roles",
        "rollup",
        "specs",
        "trace",
        "views",
    ]
