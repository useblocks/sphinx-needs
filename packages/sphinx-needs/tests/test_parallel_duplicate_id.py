"""A need id created in two documents renders its card once, under ``-j N`` too (#2087).

Serially, the second directive with an id that exists is refused (``needs.create_need``)
and returns no node. Under ``-j N`` two documents read by different workers each create
the need in their own environment; the merge keeps the first one merged and warns
``needs.duplicate_id`` about the other, and the losing document's doctree still holds
its ``Need`` node. That node is rendered only on the document its need is recorded on,
so the card appears once, as in a serial build.

Docnames are read in sorted order, in ``len // 2``-sized chunks under ``-j 2``: with four
padding pages, ``index, pad_0, pad_1`` and ``pad_2, pad_3, page_b``, so the two
definitions are always read by different workers, both forked from the same
environment. Which worker is merged first decides the winner, so every assertion takes
the winner from the warning rather than assuming it. Sphinx 7 reads in parallel only
above five documents (Sphinx 9 at any count): every ``-j 2`` project here has six.
"""

from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path
from typing import Any

import pytest
from sphinx.application import Sphinx
from sphinx.util.parallel import parallel_available

from sphinx_needs.api import need as need_api
from sphinx_needs.nodes import Need
from sphinx_needs_testkit import build_warnings

CONF = """\
extensions = ["sphinx_needs"]
needs_build_json = True
"""

INDEX = """\
Index
=====

.. toctree::

   page_b

.. req:: Title from index
   :id: REQ_DUP

   Content from index.
"""

PAGE_B = """\
Page B
======

.. req:: Title from page_b
   :id: REQ_DUP

   Content from page_b.

.. req:: Only on page_b
   :id: REQ_B

   Content only on page_b.
"""

PADDING = [(Path(f"pad_{n}.rst"), f":orphan:\n\nPad {n}\n=====\n") for n in range(4)]

FILES = [
    (Path("conf.py"), CONF),
    (Path("index.rst"), INDEX),
    (Path("page_b.rst"), PAGE_B),
    *PADDING,
]

PARALLEL = pytest.mark.skipif(
    not parallel_available, reason="Parallel execution not supported"
)

DUPLICATE = re.compile(
    r"<srcdir>/(index|page_b)\.rst:\d+: WARNING: A need with ID REQ_DUP already "
    r"exists, title: 'Title from (index|page_b)'\. \[needs\.duplicate_id\]"
)
REFUSED = (
    "<srcdir>/page_b.rst:4: WARNING: Need could not be created: "
    "A need with ID 'REQ_DUP' already exists. [needs.create_need]"
)


def serial_and_parallel(
    files: list[tuple[Path, str]], buildername: str = "html"
) -> list[Any]:
    """``test_app`` parameters building ``files`` serially, and with ``-j 2``."""
    return [
        pytest.param(
            {"buildername": buildername, "files": files}, id=f"{buildername}-serial"
        ),
        pytest.param(
            {"buildername": buildername, "files": files, "parallel": 2},
            id=f"{buildername}-j2",
            marks=PARALLEL,
        ),
    ]


def winner_and_loser(warnings: list[str], parallel: bool) -> tuple[str, str]:
    """The document that kept ``REQ_DUP``, and the one that lost it, from the warning.

    Serially ``page_b`` is read second and refused; under ``-j 2`` the merge names the
    loser, which may be either document.
    """
    assert len(warnings) == 1, warnings
    if not parallel:
        assert warnings[0] == REFUSED
        return "index", "page_b"
    match = DUPLICATE.fullmatch(warnings[0])
    assert match, warnings[0]
    loser, loser_title = match.groups()
    assert loser == loser_title, warnings[0]
    return ("page_b" if loser == "index" else "index"), loser


def needs_by_id(app: Sphinx) -> dict[str, dict[str, Any]]:
    """The needs of the build's ``needs.json``, by id."""
    data = json.loads(Path(app.outdir, "needs.json").read_text(encoding="utf-8"))
    return data["versions"][data["current_version"]]["needs"]


def page(app: Sphinx, docname: str) -> str:
    return Path(app.outdir, f"{docname}.html").read_text(encoding="utf-8")


def assert_one_card(app: Sphinx, winner: str, loser: str) -> None:
    """``REQ_DUP`` renders once, on the winner's page, from the winner's directive."""
    needs = needs_by_id(app)
    assert needs["REQ_DUP"]["docname"] == winner
    assert needs["REQ_DUP"]["title"] == f"Title from {winner}"
    pages = {docname: page(app, docname) for docname in ("index", "page_b")}
    assert {d: html.count('id="REQ_DUP"') for d, html in pages.items()} == {
        winner: 1,
        loser: 0,
    }
    assert pages[winner].count(f"Content from {winner}.") == 1
    assert f"Content from {loser}." not in pages[winner] + pages[loser]
    assert pages["page_b"].count('id="REQ_B"') == 1


@pytest.mark.parametrize("test_app", serial_and_parallel(FILES), indirect=True)
def test_a_duplicate_id_renders_once(test_app: Sphinx):
    """One warning, one need, one card: on the page whose need the build kept."""
    app = test_app
    app.build()
    winner, loser = winner_and_loser(build_warnings(app), app.parallel > 1)
    assert list(needs_by_id(app)) == ["REQ_B", "REQ_DUP"]
    assert_one_card(app, winner, loser)


ASSEMBLED = [
    *serial_and_parallel(FILES, "singlehtml"),
    *serial_and_parallel(FILES, "latex"),
]


@pytest.mark.parametrize("test_app", ASSEMBLED, indirect=True)
def test_a_duplicate_id_renders_once_in_an_assembled_document(test_app: Sphinx):
    """``singlehtml`` and ``latex`` resolve ONE tree, assembled from every document.

    ``doctree-resolved`` fires once for it, with the root document's name, so the
    document a need node was written in has to come from the node itself: a rule on
    the name the event passes would render both copies or neither, and would drop
    ``REQ_B``, which is not duplicated at all.
    """
    app = test_app
    app.build()
    winner, loser = winner_and_loser(build_warnings(app), app.parallel > 1)
    if app.builder.name == "singlehtml":
        output = Path(app.outdir, "index.html").read_text(encoding="utf-8")
        assert output.count('id="REQ_DUP"') == 1
        assert output.count('id="REQ_B"') == 1
    else:
        (tex,) = Path(app.outdir).glob("*.tex")
        # LaTeX escapes the underscore of ``page_b``
        output = tex.read_text(encoding="utf-8").replace(r"\_", "_")
    assert output.count(f"Title from {winner}") == 1
    assert output.count(f"Content from {winner}.") == 1
    assert f"Content from {loser}." not in output
    assert output.count("Content only on page_b.") == 1


EXTRACT_FILES = [
    (Path("conf.py"), CONF),
    (Path("index.rst"), INDEX.replace("   page_b\n", "   page_a\n   page_b\n")),
    (
        Path("page_a.rst"),
        "Page A\n======\n\n.. needextract::\n   :filter: id == 'REQ_DUP'\n",
    ),
    (Path("page_b.rst"), PAGE_B),
    *PADDING[:3],
]


@pytest.mark.parametrize("test_app", serial_and_parallel(EXTRACT_FILES), indirect=True)
def test_needextract_shows_the_need_the_build_kept(test_app: Sphinx):
    """``needextract`` copies the content of the directive whose need was kept.

    The extract copies the need's node from a registry each worker fills; under
    ``-j 2`` (chunks ``index, pad_0, pad_1`` and ``pad_2, page_a, page_b``) the merge
    must not let the losing worker's copy replace the winner's, or the extract shows
    the winner's title over the loser's content.
    """
    app = test_app
    app.build()
    winner, loser = winner_and_loser(build_warnings(app), app.parallel > 1)
    assert_one_card(app, winner, loser)
    extract = page(app, "page_a")
    assert extract.count(f"Title from {winner}") == 1
    assert extract.count(f"Content from {winner}.") == 1
    assert f"Content from {loser}." not in extract


def touch(app: Sphinx, docname: str) -> None:
    """Make ``docname`` newer than the build that read it, whatever the clock resolution."""
    later = time.time_ns() + 60_000_000_000
    os.utime(Path(app.srcdir, f"{docname}.rst"), ns=(later, later))


@pytest.mark.parametrize(
    "test_app",
    [pytest.param({"buildername": "html", "files": FILES, "parallel": 2}, id="j2")],
    indirect=True,
)
@PARALLEL
@pytest.mark.parametrize("touched", ["winner", "loser"])
def test_an_incremental_build_keeps_one_card(test_app: Sphinx, touched: str):
    """Rebuilding either document leaves one card in total.

    Re-reading the winner's document purges its need and creates it again, while the
    loser's doctree, if it is not re-read, still holds its node; re-reading the loser's
    document runs its directive against the environment that kept the winner's need,
    which refuses it as a serial build does.
    """
    app = test_app
    app.build()
    first = build_warnings(app)
    winner, loser = winner_and_loser(first, parallel=True)
    assert_one_card(app, winner, loser)

    touch(app, winner if touched == "winner" else loser)
    app.build()
    second = build_warnings(app)[len(first) :]
    if touched == "winner":
        assert second == []
    else:
        lineno = 4 if loser == "page_b" else 8
        assert second == [
            f"<srcdir>/{loser}.rst:{lineno}: WARNING: Need could not be created: "
            "A need with ID 'REQ_DUP' already exists. [needs.create_need]"
        ]
    assert_one_card(app, winner, loser)


INCLUDE_FILES = [
    (Path("conf.py"), CONF + 'exclude_patterns = ["_fragment.rst"]\n'),
    (Path("index.rst"), "Index\n=====\n\n.. include:: _fragment.rst\n"),
    (
        Path("_fragment.rst"),
        ".. req:: Included need\n   :id: REQ_INC\n\n   Content of the fragment.\n",
    ),
    *[(Path(f"pad_{n}.rst"), f":orphan:\n\nPad {n}\n=====\n") for n in range(5)],
]


@pytest.mark.parametrize("test_app", serial_and_parallel(INCLUDE_FILES), indirect=True)
def test_a_need_in_an_included_file_renders(test_app: Sphinx):
    """A need written in an ``include``-d fragment renders on the including page.

    The fragment is not a document, so the need is recorded on the page that includes
    it; the source of the lines it was written on is the fragment.
    """
    app = test_app
    app.build()
    assert build_warnings(app) == []
    assert needs_by_id(app)["REQ_INC"]["docname"] == "index"
    html = page(app, "index")
    assert html.count('id="REQ_INC"') == 1
    assert html.count("Content of the fragment.") == 1


@pytest.mark.parametrize("test_app", serial_and_parallel(FILES), indirect=True)
def test_a_doctree_pickled_before_the_document_tag_still_renders(
    test_app: Sphinx, monkeypatch: pytest.MonkeyPatch
):
    """Need nodes in a doctree pickled before they carried their document still render.

    The first build writes need nodes without the tag (as every earlier release did);
    the second, with the tag back, re-reads nothing and writes the deleted pages from
    those pickled doctrees. A node without the tag is rendered as before -- including,
    under ``-j 2``, the loser's stale copy, which is what an upgrade without a fresh
    environment keeps until the loser's document is read again.
    """
    app = test_app
    original = need_api._create_need_node

    def untagged(*args: Any, **kwargs: Any) -> list[Any]:
        created = original(*args, **kwargs)
        for node in created:
            if isinstance(node, Need):
                node.attributes.pop("docname", None)
        return created

    with monkeypatch.context() as patch:
        patch.setattr(need_api, "_create_need_node", untagged)
        app.build()
    first = build_warnings(app)
    winner, loser = winner_and_loser(first, app.parallel > 1)
    for docname in ("index", "page_b"):
        Path(app.outdir, f"{docname}.html").unlink()

    app.build()
    assert build_warnings(app)[len(first) :] == []
    pages = {docname: page(app, docname) for docname in ("index", "page_b")}
    assert pages[winner].count(f"Content from {winner}.") == 1
    assert pages["page_b"].count('id="REQ_B"') == 1
    stale = 1 if app.parallel > 1 else 0
    assert pages[loser].count('id="REQ_DUP"') == stale
