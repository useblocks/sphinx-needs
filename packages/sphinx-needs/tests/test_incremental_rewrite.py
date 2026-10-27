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
    "total": {
        "schema": {"type": "number"},
        "derive": {"kind": "sum", "field": "hours", "over": "links"},
    },
}
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

   reqs
   specs
   extends
   views
   charts
   roles
   unrelated
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

.. spec:: Copies a status
   :id: SPEC_003
   :status: [[copy("status", "REQ_001")]]

   Mentions :need:`REQ_002`.
""",
    "extends.rst": """\
Extends
=======

.. needextend:: REQ_002
   :status: extended

.. needextend:: type == 'spec'
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
        "specs.rst",
        "   Mentions :need:`REQ_002`.\n",
        "   Mentions :need:`REQ_002` and :need:`REQ_001`.\n",
    ),
    "extend-by-id-changed": ("extends.rst", ":status: extended", ":status: reviewed"),
    "extend-by-id-removed": (
        "extends.rst",
        ".. needextend:: REQ_002\n   :status: extended\n",
        "",
    ),
    "extend-by-filter-changed": ("extends.rst", ":+tags: ext", ":+tags: ext2"),
    "prose": ("specs.rst", "refine the requirements", "detail the requirements"),
}


def _write(srcdir: Path, pages: dict[str, str]) -> Path:
    """Write the project; a file whose text is the same is left untouched, so that
    Sphinx, which compares modification times, sees only the edited page changed."""
    srcdir.mkdir(parents=True, exist_ok=True)
    for name, text in {"conf.py": CONF, **pages}.items():
        path = srcdir / name
        if not path.exists() or path.read_text(encoding="utf-8") != text:
            path.write_text(text, encoding="utf-8")
    for path in srcdir.glob("*.rst"):
        if path.name not in pages:
            path.unlink()
    return srcdir


def _edited(name: str) -> dict[str, str]:
    page, old, new = EDITS[name]
    assert PAGES[page].count(old) == 1, (name, old)
    return {**PAGES, page: PAGES[page].replace(old, new)}


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
    after: dict[str, str],
    *,
    parallel: int = 1,
) -> list[str]:
    """Edit the built project, build incrementally, compare with a fresh build.

    :return: The documents the incremental build wrote.
    """
    incremental = _write(tmp_path / "incremental", PAGES)
    _build(make_app, incremental, fresh=True, parallel=parallel)
    _write(incremental, after)
    written, warnings = _build(make_app, incremental, fresh=False, parallel=parallel)

    fresh = _write(tmp_path / "fresh", after)
    _, fresh_warnings = _build(make_app, fresh, fresh=True, parallel=parallel)

    got = _pages(incremental / "_build" / "html")
    expected = _pages(fresh / "_build" / "html")
    assert got.keys() == expected.keys()
    stale = sorted(name for name in got if got[name] != expected[name])
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


@pytest.mark.parametrize("edit", EDITS)
def test_incremental_build_equals_fresh_build(
    make_app: Callable[..., SphinxTestApp], tmp_path: Path, edit: str
) -> None:
    """After the edit, every page on disk is the page a fresh build writes."""
    _assert_equivalent(make_app, tmp_path, _edited(edit))


@pytest.mark.parametrize("edit", ["title", "link-added", "extend-by-id-changed"])
def test_parallel_incremental_build_equals_fresh_build(
    make_app: Callable[..., SphinxTestApp], tmp_path: Path, edit: str
) -> None:
    """The same with ``-j 2``: the role references of a parallel read are merged."""
    _assert_equivalent(make_app, tmp_path, _edited(edit), parallel=2)


def test_prose_edit_rewrites_only_its_own_page(
    make_app: Callable[..., SphinxTestApp], tmp_path: Path
) -> None:
    """No need changed, so no other page is re-written.

    ``index`` is Sphinx's own: it holds the toctree naming the edited page.
    """
    written = _assert_equivalent(make_app, tmp_path, _edited("prose"))
    assert sorted(written) == ["index", "specs"]


def test_title_edit_rewrites_the_pages_showing_the_need(
    make_app: Callable[..., SphinxTestApp], tmp_path: Path
) -> None:
    """Not every need-relevant page: a page that shows nothing of the need is not.

    ``views`` and ``charts`` hold views, ``specs`` the need linking to it (and the
    dynamic function and the ``derive`` rule reading it), ``roles`` a role naming it;
    ``unrelated`` holds a need, but shows nothing of ``REQ_001``, and ``extends`` only
    extends other needs by id or by a filter that does not change.
    """
    written = _assert_equivalent(make_app, tmp_path, _edited("title"))
    assert sorted(written) == [
        "charts",
        "index",
        "reqs",
        "roles",
        "specs",
        "views",
    ]
