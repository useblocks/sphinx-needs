# @Test suite for the source copies and pages as build state, TEST_SOURCE_PAGES_1, test, [IMPL_LNK_1]
"""The source copies and their pages are build state (#2070, the pages half of #2044).

What to copy and page is recorded in the environment when a document is read (or when a
project without a directive is scanned), and every HTML build copies and pages from that
record at ``html-collect-pages`` -- whether or not the directive's document is read
again, under ``-j N`` too, and for HTML builders only.

Every case builds a copy of ``doc_test/need_id_refs`` (see ``test_need_id_refs``) with
local URLs only, plus ``src/impl.cpp`` holding the one-line need ``IMPL_1``. On the
``directive`` path ``index`` traces the whole project, so ``src/refs.cpp`` (referenced
only) and ``src/impl.cpp`` (a need) are copied and paged; on the ``config-only`` path no
directive traces it, so only the referenced ``src/refs.cpp`` is.
"""

import pickle
import re
import shutil
from pathlib import Path

import pytest
from sphinx.testing.util import SphinxTestApp
from sphinx.util.parallel import parallel_available

from sphinx_needs_testkit import build_warnings

from .test_config_only_refs import NO_DIRECTIVE, _edit, _status
from .test_need_id_refs import (
    _SHOWS_WARNING_TYPES,
    DANGLING,
    GITHUB,
    _build,
    _card_links,
    _MakeApp,
    _project,
)
from .test_rediscovery import _scoped
from .test_url_links import _card_links as _field_links
from .test_url_links import _project as _url_project

IMPL = "// @first impl, IMPL_1, impl\nvoid impl() {}\n"
LOCAL_ONLY = ("set_remote_url = true", "set_remote_url = false")
#: the copies (and so the pages) each path makes
COPIES = {
    "directive": ["src/impl.cpp", "src/refs.cpp"],
    "config-only": ["src/refs.cpp"],
}
#: the ``[docs]`` back-link of a source page
DOCS_LINK = re.compile(r'<a class="viewcode-back" href="([^"]*)">\[docs\]</a>')


def _local_project(
    root: Path, path: str, append: dict[str, str] | None = None, **files: str
) -> None:
    """The fixture with local URLs only and ``src/impl.cpp``; ``index`` without its
    directive on the ``config-only`` path."""
    if path == "config-only":
        files = {**NO_DIRECTIVE, **files}
    _project(
        root,
        toml_replace=LOCAL_ONLY,
        files={"src/impl.cpp": IMPL, **files},
        append=append,
    )


def _copies(outdir: Path) -> list[str]:
    """The source copies in ``outdir``, POSIX and relative to it."""
    return sorted(p.relative_to(outdir).as_posix() for p in outdir.rglob("*.cpp"))


def _page(outdir: Path, copy: str, builder: str = "html") -> Path:
    """The page of ``copy``: ``src/x.html`` (``src/x/index.html`` for ``dirhtml``)."""
    stem = Path(outdir, copy).with_suffix("")
    return stem / "index.html" if builder == "dirhtml" else stem.with_suffix(".html")


def _paged(app: SphinxTestApp, builder: str = "html") -> list[str]:
    """The copies in the output that have a source page beside them."""
    outdir = Path(app.outdir)
    return [c for c in _copies(outdir) if _page(outdir, c, builder).is_file()]


def _recording(
    make_app: _MakeApp, root: Path, **kwargs: object
) -> tuple[SphinxTestApp, list[str]]:
    """A built application, and the source pages (``src/…``) it wrote."""
    app = make_app(srcdir=root / "docs", **kwargs)
    written: list[str] = []

    def record(_app: object, pagename: str, *_args: object) -> None:
        if pagename.startswith("src/"):
            written.append(pagename)

    app.connect("html-page-context", record)
    app.build()
    return app, written


@pytest.mark.parametrize("path", ["directive", "config-only"])
def test_a_cleaned_output_directory_gets_its_copies_and_pages_back(
    tmp_path: Path, make_app: _MakeApp, path: str
) -> None:
    """The HTML output directory removed, the doctrees kept: the next build reads
    nothing, and every copy and page is back -- the card's local link resolves to a
    file (it was a dead link)."""
    _local_project(tmp_path, path)
    first = _build(tmp_path, make_app)
    assert _paged(first) == COPIES[path]
    shutil.rmtree(first.outdir)

    app = _build(tmp_path, make_app, freshenv=False)

    assert "0 added, 0 changed, 0 removed" in _status(app)
    assert _copies(Path(app.outdir)) == COPIES[path]
    assert _paged(app) == COPIES[path]
    [row] = _card_links(app, "index.html")
    assert [href for href, _name in row] == ["src/refs.html#L-1", "src/refs.html#L-3"]
    assert all(Path(app.outdir, href.split("#")[0]).is_file() for href, _ in row)
    if path == "directive":
        index = Path(app.outdir, "index.html").read_text(encoding="utf-8")
        assert _field_links(index, "local-url") == ["src/impl.html#L-1"]


@pytest.mark.parametrize("path", ["directive", "config-only"])
def test_two_builders_sharing_the_doctrees_each_get_the_copies_and_pages(
    tmp_path: Path, make_app: _MakeApp, path: str
) -> None:
    """``html``, then ``dirhtml`` on the same ``_build/doctrees`` (the Makefile
    layout): the second builder's output has its copies and pages too."""
    _local_project(tmp_path, path)
    html = _build(tmp_path, make_app)
    dirhtml = _build(tmp_path, make_app, buildername="dirhtml", freshenv=False)

    assert _paged(html) == COPIES[path]
    assert _copies(Path(dirhtml.outdir)) == COPIES[path]
    assert _paged(dirhtml, "dirhtml") == COPIES[path]


@pytest.mark.parametrize("path", ["directive", "config-only"])
def test_an_unchanged_build_rewrites_no_copy_or_page(
    tmp_path: Path, make_app: _MakeApp, path: str
) -> None:
    """A build that reads nothing keeps every copy and page, and rewrites none of them:
    the copies and pages are up to date (Sphinx 7.4 stops at "no targets are out of
    date" before collecting any page; 9.x collects, and codelinks yields none)."""
    _local_project(tmp_path, path)
    first = _build(tmp_path, make_app)
    outdir = Path(first.outdir)
    files = [outdir / c for c in COPIES[path]] + [
        _page(outdir, c) for c in COPIES[path]
    ]
    stamps = [f.stat().st_mtime_ns for f in files]

    app, written = _recording(make_app, tmp_path, freshenv=False)

    assert "0 added, 0 changed, 0 removed" in _status(app)
    assert _paged(app) == COPIES[path]
    assert written == []
    assert [f.stat().st_mtime_ns for f in files] == stamps


def test_a_page_whose_need_moved_to_another_document_is_written_again(
    tmp_path: Path, make_app: _MakeApp
) -> None:
    """``page1`` defines ``IMPL_1`` and ``page2`` defers to it; ``page1`` removed, ``page2``
    is read again and defines it. The source is untouched, yet the page is written again:
    its ``[docs]`` link names the new document."""
    trace = "\n.. src-trace::\n   :project: src\n   :file: impl.cpp\n"
    _local_project(
        tmp_path,
        "directive",
        append={"docs/page1.rst": trace, "docs/page2.rst": trace},
        **_scoped(":file: refs.cpp"),
    )
    first = _build(tmp_path, make_app)
    page = Path(first.outdir, "src", "impl.html")
    assert DOCS_LINK.findall(page.read_text(encoding="utf-8")) == [
        "../page1.html#IMPL_1"
    ]

    (tmp_path / "docs" / "page1.rst").unlink()
    app = _build(tmp_path, make_app, freshenv=False)

    assert re.search(r"reading sources\.\.\. \[[^\]]*\] page2\b", _status(app))
    assert DOCS_LINK.findall(page.read_text(encoding="utf-8")) == [
        "../page2.html#IMPL_1"
    ]


def test_the_source_page_css_is_on_source_pages_only(
    tmp_path: Path, make_app: _MakeApp
) -> None:
    _local_project(tmp_path, "directive")
    app = _build(tmp_path, make_app)

    css = "_static/source_tracing/ub_sct.css"
    assert css in Path(app.outdir, "src", "impl.html").read_text(encoding="utf-8")
    assert css not in Path(app.outdir, "index.html").read_text(encoding="utf-8")


@pytest.mark.parametrize("path", ["directive", "config-only"])
def test_a_source_edit_shows_in_the_copy_and_the_page(
    tmp_path: Path, make_app: _MakeApp, path: str
) -> None:
    _local_project(tmp_path, path)
    _build(tmp_path, make_app)
    source = tmp_path / "src" / "refs.cpp"
    _edit(source, "return a + 1;", "return a + 12345;")

    app = _build(tmp_path, make_app, freshenv=False)

    assert Path(app.outdir, "src", "refs.cpp").read_bytes() == source.read_bytes()
    page = Path(app.outdir, "src", "refs.html").read_text(encoding="utf-8")
    assert "12345" in page


@pytest.mark.parametrize("builder", ["html", "dirhtml"])
def test_the_back_link_follows_the_builders_uri_rule(
    tmp_path: Path, make_app: _MakeApp, builder: str
) -> None:
    """The ``[docs]`` link of a source page is the builder's own relative URI to the
    need's document: ``dirhtml`` writes ``src/impl/index.html`` and ``sub/deep/``."""
    _local_project(
        tmp_path,
        "directive",
        **_scoped(":file: impl.cpp"),
        **{"src/deep.cpp": "// @deep impl, IMPL_DEEP, impl\n"},
    )
    deep = tmp_path / "docs" / "sub" / "deep.rst"
    deep.write_text(
        deep.read_text(encoding="utf-8")
        + "\n.. src-trace::\n   :project: src\n   :file: deep.cpp\n",
        encoding="utf-8",
    )
    app = _build(tmp_path, make_app, buildername=builder)

    def links(copy: str) -> list[str]:
        page = _page(Path(app.outdir), copy, builder).read_text(encoding="utf-8")
        return DOCS_LINK.findall(page)

    if builder == "html":
        assert links("src/impl.cpp") == ["../index.html#IMPL_1"]
        assert links("src/deep.cpp") == ["../sub/deep.html#IMPL_DEEP"]
    else:
        assert links("src/impl.cpp") == ["../../#IMPL_1"]
        assert links("src/deep.cpp") == ["../../sub/deep/#IMPL_DEEP"]


def test_two_documents_paging_one_file_merge_their_anchors(
    tmp_path: Path, make_app: _MakeApp
) -> None:
    """Two projects over one source directory, each with its own one-line style, trace
    one file from two documents: one copy, one page, each need's ``[docs]`` link."""
    _local_project(
        tmp_path,
        "directive",
        **_scoped(":file: both.cpp"),
        **{
            "src/both.cpp": (
                "// @in index, IMPL_1, impl\n// [[in later, IMPL_2, impl]]\nint x;\n"
            )
        },
    )
    toml = tmp_path / "docs" / "ubproject.toml"
    toml.write_text(
        toml.read_text(encoding="utf-8")
        + (
            "\n[codelinks.projects.two]\n"
            f'remote_url_pattern = "{GITHUB}"\n'
            "[codelinks.projects.two.source_discover]\n"
            'src_dir = "../src"\n'
            'comment_type = "cpp"\n'
            "[codelinks.projects.two.analyse.oneline_comment_style]\n"
            'start_sequence = "[["\n'
            'end_sequence = "]]"\n'
        ),
        encoding="utf-8",
    )
    later = tmp_path / "docs" / "later.rst"
    later.write_text(
        later.read_text(encoding="utf-8")
        + "\n.. src-trace::\n   :project: two\n   :file: both.cpp\n",
        encoding="utf-8",
    )
    app = _build(tmp_path, make_app)

    assert _paged(app) == ["src/both.cpp"]
    page = Path(app.outdir, "src", "both.html").read_text(encoding="utf-8")
    assert DOCS_LINK.findall(page) == ["../index.html#IMPL_1", "../later.html#IMPL_2"]


#: project ``two``: ``src`` again, with its own one-line style (``[[...]]``), so that two
#: documents create needs from one file
TWO = (
    "\n[codelinks.projects.two]\n"
    "[codelinks.projects.two.source_discover]\n"
    'src_dir = "../src"\n'
    'comment_type = "cpp"\n'
    "[codelinks.projects.two.analyse.oneline_comment_style]\n"
    'start_sequence = "[["\n'
    'end_sequence = "]]"\n'
)
BOTH = "// @in later, IMPL_1, impl\n// [[in another, IMPL_2, impl]]\nint x;\n"


def _trace(project: str) -> str:
    return f"\n.. src-trace::\n   :project: {project}\n   :file: both.cpp\n"


def _shared_page(root: Path, *, page1: bool) -> None:
    """``src/both.cpp`` paged from ``later`` (``IMPL_1``, project ``src``) and, with
    ``page1``, from ``page1`` too (``IMPL_2``, project ``two``); ``index`` traces
    nothing, so its re-reads (a glob toctree) touch no page."""
    _local_project(
        root,
        "directive",
        append={"docs/later.rst": _trace("src")}
        | ({"docs/page1.rst": _trace("two")} if page1 else {}),
        **NO_DIRECTIVE,
        **{"src/both.cpp": BOTH},
    )
    toml = root / "docs" / "ubproject.toml"
    toml.write_text(toml.read_text(encoding="utf-8") + TWO, encoding="utf-8")


def _both_links(app: SphinxTestApp) -> list[str]:
    page = Path(app.outdir, "src", "both.html").read_text(encoding="utf-8")
    return DOCS_LINK.findall(page)


def test_a_document_that_stops_tracing_a_shared_file_leaves_its_page(
    tmp_path: Path, make_app: _MakeApp
) -> None:
    """``later`` and ``page1`` both page ``src/both.cpp``; ``page1``'s directive removed
    (the document edited, the file untouched): the page is written again without
    ``page1``'s ``[docs]`` link, although the remaining link names a document not read."""
    _shared_page(tmp_path, page1=True)
    first = _build(tmp_path, make_app)
    assert _both_links(first) == ["../later.html#IMPL_1", "../page1.html#IMPL_2"]

    page1 = tmp_path / "docs" / "page1.rst"
    _edit(page1, _trace("two"), "")
    app = _build(tmp_path, make_app, freshenv=False)

    assert "0 added, 1 changed, 0 removed" in _status(app)
    assert _both_links(app) == ["../later.html#IMPL_1"]


def test_a_new_document_tracing_a_paged_file_adds_its_back_link(
    tmp_path: Path, make_app: _MakeApp
) -> None:
    """``src/both.cpp`` is paged from ``later``; a NEW document traces it too (the file
    untouched): the page is written again with the new document's ``[docs]`` link."""
    _shared_page(tmp_path, page1=False)
    first = _build(tmp_path, make_app)
    assert _both_links(first) == ["../later.html#IMPL_1"]

    (tmp_path / "docs" / "added.rst").write_text(
        "Added\n=====\n" + _trace("two"), encoding="utf-8"
    )
    app = _build(tmp_path, make_app, freshenv=False)

    assert "1 added" in _status(app)
    assert _both_links(app) == ["../later.html#IMPL_1", "../added.html#IMPL_2"]


_REMOVE_AT_COLLECT = """
def setup(app):
    from pathlib import Path

    def remove(app):
        (Path(app.srcdir).parent / "src" / "impl.cpp").unlink()
        return []

    app.connect("html-collect-pages", remove)
"""


def test_a_source_removed_before_the_pages_are_written_warns_once(
    tmp_path: Path, make_app: _MakeApp
) -> None:
    """A recorded source that cannot be read when the pages are written (removed since
    its document was read) warns once, naming it; the build goes on and pages the
    rest."""
    _local_project(tmp_path, "directive", append={"docs/conf.py": _REMOVE_AT_COLLECT})
    app = _build(tmp_path, make_app)

    pages = [w for w in build_warnings(app) if "source page" in w]
    assert len(pages) == 1, build_warnings(app)
    assert "src/impl.cpp" in pages[0]
    if _SHOWS_WARNING_TYPES:
        assert pages[0].endswith("[codelinks.source_page]")
    assert [w for w in build_warnings(app) if w not in pages] == [DANGLING]
    assert _paged(app) == ["src/refs.cpp"]
    assert not Path(app.outdir, "src", "impl.html").exists()


@pytest.mark.skipif(
    not parallel_available, reason="Sphinx reads sources in parallel on POSIX only"
)
def test_parallel_build_pages_a_directives_sources(
    tmp_path: Path, make_app: _MakeApp
) -> None:
    """Under ``-j 2`` the directive is read in a worker; its record reaches the main
    process, so the page exists beside the copy (#2044: the copy only, before)."""
    _url_project(tmp_path, patterns={"a": GITHUB}, pages=7)
    app = make_app(srcdir=tmp_path / "docs", freshenv=True, parallel=2)
    app.build()

    assert re.search(r"reading sources\.\.\. \[\s*\d+%\] \S+ \.\. \S+", _status(app))
    assert Path(app.outdir, "srca", "a.cpp").is_file()
    page = Path(app.outdir, "srca", "a.html").read_text(encoding="utf-8")
    assert DOCS_LINK.findall(page) == ["../index.html#IMPL_A"]


def test_a_config_only_scan_pickled_before_pages_existed_still_loads() -> None:
    """An environment pickled by an earlier release holds ``ConfigOnlyScan`` objects
    without the ``pages`` field; they load, and page nothing."""
    from sphinx_codelinks.sphinx_extension.rediscovery import ConfigOnlyScan

    scan = ConfigOnlyScan(fingerprint=(), records=[])
    object.__delattr__(scan, "pages")  # the state an older class pickled
    assert "pages" not in vars(scan)

    loaded = pickle.loads(pickle.dumps(scan))
    assert loaded.pages == ()
    assert loaded == ConfigOnlyScan(fingerprint=(), records=[])
