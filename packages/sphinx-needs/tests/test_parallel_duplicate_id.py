"""A need id created in two documents renders its card once, under ``-j N`` too (#2087).

Serially, the second directive with an id that exists is refused (``needs.create_need``)
and returns no node. Under ``-j N`` two documents read by different workers each create
the need in their own environment; the merge keeps the first one merged and warns
``needs.duplicate_id`` about the other, and the losing document's doctree still holds
its ``Need`` node. That node is rendered only on the document its need is recorded on,
so the card appears once, as in a serial build.

Docnames are read in sorted order, in ``len // 2``-sized chunks under ``-j 2``: with four
padding pages, ``index, pad_0, pad_1`` and ``pad_2, pad_3, page_b``. Sphinx 7 reads in
parallel only above five documents (Sphinx 9 at any count): every ``-j 2`` project here
has six.

That the two definitions are read by different workers is not enough on its own. Sphinx
forks the second worker only after it has handed out the first chunk, and it merges a
worker that has already finished before it forks the next one; a first chunk of three
tiny documents can finish in that gap on a loaded machine, and the second worker then
starts from the merged environment and refuses ``page_b``'s directive as a serial build
does. Which finished worker is merged first is likewise up to the machine. So the ``-j 2``
projects carry a barrier in their ``conf.py`` (see :func:`barrier_conf`): the first chunk
cannot finish before the second is being read, and the chunk that is to merge second
cannot finish before the other one has merged. The assertions still take the winner from
the warning.
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

BARRIER = """
import time
from pathlib import Path

# (first, last) document of each chunk, and the chunk whose merge is to come first
_CHUNKS = @CHUNKS@
_MERGED_FIRST = @MERGED_FIRST@
_TIMEOUT = 60.0


def _flag(app, name):
    # under the doctree directory, so the processes of one build share it and a
    # rebuild finds the flags of the first build (its documents need not wait again)
    path = Path(app.doctreedir, "barrier")
    path.mkdir(parents=True, exist_ok=True)
    return path / name


def _wait(app, name):
    flag = _flag(app, name)
    deadline = time.monotonic() + _TIMEOUT
    while not flag.exists():
        if time.monotonic() > deadline:
            raise RuntimeError(
                f"test barrier: {flag.name!r} not reached in {_TIMEOUT:.0f} s"
            )
        time.sleep(0.005)


def _barrier_read(app, docname, source):
    if app.parallel < 2:
        return
    _flag(app, f"read-{docname}").touch()
    if docname == _CHUNKS[0][0]:
        # the first chunk cannot finish before the second worker has been forked
        _wait(app, f"read-{_CHUNKS[1][0]}")
    second = _CHUNKS[1 - _MERGED_FIRST]
    if docname == second[1]:
        # the chunk that is to merge second finishes only once the other has merged
        _wait(app, f"merged-{_CHUNKS[_MERGED_FIRST][0]}")


def _barrier_merged(app, env, docnames, other):
    for docname in docnames:
        _flag(app, f"merged-{docname}").touch()


def _barrier_setup(app):
    app.connect("source-read", _barrier_read)
    app.connect("env-merge-info", _barrier_merged)
"""


def barrier_conf(
    chunks: tuple[tuple[str, str], tuple[str, str]], merged_first: int = 0
) -> str:
    """``conf.py`` code that fixes how a ``-j 2`` read of the project overlaps and merges.

    ``chunks`` names the first and last document of each chunk; the chunk at index
    ``merged_first`` is merged first. A build that does not read in parallel is left
    alone. The code defines ``_barrier_setup(app)``, which the project's ``setup``
    calls; a wait that is not met within a minute fails the build rather than hanging
    the suite.
    """
    return BARRIER.replace("@CHUNKS@", repr(chunks)).replace(
        "@MERGED_FIRST@", repr(merged_first)
    )


# the chunks of every project with ``index``, ``page_b`` and four other documents
CHUNKS = (("index", "pad_1"), ("pad_2", "page_b"))


def conf(
    chunks: tuple[tuple[str, str], tuple[str, str]] = CHUNKS,
    merged_first: int = 0,
    extra: str = "",
    setup: str = "",
) -> str:
    """The project ``conf.py``: ``CONF``, ``extra``, and the ``-j 2`` barrier."""
    return (
        CONF
        + extra
        + barrier_conf(chunks, merged_first)
        + "\n\ndef setup(app):\n    _barrier_setup(app)\n"
        + setup
    )


FILES = [
    (Path("conf.py"), conf()),
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


@pytest.mark.parametrize(
    ("test_app", "kept"),
    [
        *[
            pytest.param(*param.values, "index", id=param.id, marks=param.marks)
            for param in serial_and_parallel(FILES)
        ],
        pytest.param(
            {
                "buildername": "html",
                "files": [(Path("conf.py"), conf(merged_first=1)), *FILES[1:]],
                "parallel": 2,
            },
            "page_b",
            id="html-j2-page_b-merged-first",
            marks=PARALLEL,
        ),
    ],
    indirect=["test_app"],
)
def test_a_duplicate_id_renders_once(test_app: Sphinx, kept: str):
    """One warning, one need, one card: on the page whose need the build kept.

    Under ``-j 2`` the barrier merges ``index``'s chunk first, or ``page_b``'s: either
    document can be the one that keeps the need.
    """
    app = test_app
    app.build()
    winner, loser = winner_and_loser(build_warnings(app), app.parallel > 1)
    assert winner == kept
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


ROOT_LOSER_CONF = conf(
    (("aa", "pad_1"), ("pad_2", "zz_root")),
    extra='root_doc = "zz_root"\n'
    'latex_documents = [("zz_root", "project.tex", "Project", "Author", "manual")]\n',
)

ROOT_LOSER_FILES = [
    (Path("conf.py"), ROOT_LOSER_CONF),
    (
        Path("zz_root.rst"),
        INDEX.replace("Index\n=====", "Root\n====")
        .replace("page_b", "aa")
        .replace("from index", "from zz_root"),
    ),
    (Path("aa.rst"), PAGE_B.split("\n.. req:: Only on")[0].replace("page_b", "aa")),
    *PADDING,
]


@pytest.mark.parametrize(
    "test_app",
    [
        *serial_and_parallel(ROOT_LOSER_FILES, "singlehtml"),
        *serial_and_parallel(ROOT_LOSER_FILES, "latex"),
    ],
    indirect=True,
)
def test_the_root_document_loses_in_an_assembled_document(test_app: Sphinx):
    """The root document's own copy is the one dropped, when its need was not kept.

    The root sorts last here, so it is read after ``aa`` serially, and refused; under
    ``-j 2`` it is in the second chunk (``aa, pad_0, pad_1`` and ``pad_2, pad_3,
    zz_root``), which the barrier merges second.
    """
    app = test_app
    app.build()
    winner, loser = "aa", "zz_root"
    if app.parallel > 1:
        expected = (
            "<srcdir>/zz_root.rst:8: WARNING: A need with ID REQ_DUP already exists, "
            "title: 'Title from zz_root'. [needs.duplicate_id]"
        )
    else:
        expected = (
            "<srcdir>/zz_root.rst:8: WARNING: Need could not be created: "
            "A need with ID 'REQ_DUP' already exists. [needs.create_need]"
        )
    assert build_warnings(app) == [expected]
    if app.builder.name == "singlehtml":
        output = Path(app.outdir, "zz_root.html").read_text(encoding="utf-8")
        assert output.count('id="REQ_DUP"') == 1
    else:
        output = Path(app.outdir, "project.tex").read_text(encoding="utf-8")
        output = output.replace(r"\_", "_")
    assert output.count(f"Title from {winner}") == 1
    assert output.count(f"Content from {winner}.") == 1
    assert f"Content from {loser}." not in output


# A directive creating its need through the API with no docname, as ``add_need`` allows
NO_DOCNAME_DIRECTIVE = """
from docutils.parsers.rst import Directive

from sphinx_needs.api import add_need


class NoDocname(Directive):
    has_content = True

    def run(self):
        app = self.state.document.settings.env.app
        return add_need(
            app,
            self.state,
            None,
            self.lineno,
            "req",
            "Title from index",
            id="REQ_DUP",
            content="\\n".join(self.content),
        )
"""


def no_docname_files(merged_first: int) -> list[tuple[Path, str]]:
    """``index`` creates ``REQ_DUP`` with no docname, ``page_b`` with a ``req``."""
    index = INDEX.replace(
        ".. req:: Title from index\n   :id: REQ_DUP\n", ".. no-docname::\n"
    )
    return [
        (
            Path("conf.py"),
            conf(
                merged_first=merged_first,
                extra=NO_DOCNAME_DIRECTIVE,
                setup='    app.add_directive("no-docname", NoDocname)\n',
            ),
        ),
        (Path("index.rst"), index),
        (Path("page_b.rst"), PAGE_B),
        *PADDING,
    ]


@pytest.mark.parametrize(
    ("test_app", "kept"),
    [
        pytest.param(
            {"buildername": "html", "files": no_docname_files(0)},
            "index",
            id="html-serial",
        ),
        *[
            pytest.param(
                {
                    "buildername": "html",
                    "files": no_docname_files(merged_first),
                    "parallel": 2,
                },
                kept,
                id=f"html-j2-{kept}-merged-first",
                marks=PARALLEL,
            )
            for merged_first, kept in ((0, "index"), (1, "page_b"))
        ],
    ],
    indirect=["test_app"],
)
def test_a_kept_need_without_a_docname_renders_once(test_app: Sphinx, kept: str):
    """A kept need created with no docname still drops the other document's copy.

    The node of the need that was kept carries no document, so it is rendered; the
    other copy's node names ``page_b``, which is not the kept need's (``None``).

    When ``page_b``'s chunk is merged first, the docname-less need is the one dropped:
    the merge does not warn about it (it warns only about the needs of the documents
    the worker read) and its node, which names no document, is rendered -- two cards.
    That gap is not closed here; the case pins it as it is.
    """
    app = test_app
    app.build()
    warnings = build_warnings(app)
    needs = needs_by_id(app)
    pages = {docname: page(app, docname) for docname in ("index", "page_b")}
    cards = {d: html.count('id="REQ_DUP"') for d, html in pages.items()}
    assert pages["page_b"].count('id="REQ_B"') == 1
    if kept == "page_b":
        assert warnings == []
        assert needs["REQ_DUP"]["docname"] == "page_b"
        assert cards == {"index": 1, "page_b": 1}
        return
    assert winner_and_loser(warnings, app.parallel > 1) == ("index", "page_b")
    assert needs["REQ_DUP"]["docname"] is None
    assert cards == {"index": 1, "page_b": 0}
    assert "Content from page_b." not in pages["index"] + pages["page_b"]


EXTRACT_FILES = [
    (Path("conf.py"), conf()),
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
    loser's doctree, which is not re-read, still holds its node. Sphinx would not
    rewrite the loser's page either, so its output is deleted to make the build
    write it from that pickled doctree. Re-reading the loser's document runs its
    directive against the environment that kept the winner's need, which refuses it as
    a serial build does.
    """
    app = test_app
    app.build()
    first = build_warnings(app)
    winner, loser = winner_and_loser(first, parallel=True)
    assert_one_card(app, winner, loser)

    if touched == "winner":
        touch(app, winner)
        Path(app.outdir, f"{loser}.html").unlink()
    else:
        touch(app, loser)
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
    (
        Path("conf.py"),
        conf(
            (("index", "pad_1"), ("pad_2", "pad_4")),
            extra='exclude_patterns = ["_fragment.rst"]\n',
        ),
    ),
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
