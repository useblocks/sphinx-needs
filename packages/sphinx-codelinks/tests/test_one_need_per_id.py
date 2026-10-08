# @Test suite for one one-line need per id when src-trace scopes overlap, TEST_ONE_NEED_PER_ID_1, test, [IMPL_LNK_1]
"""A one-line need two ``src-trace`` directives both find is created once (#2042).

Every case builds a copy of ``doc_test/need_id_refs`` (see ``test_need_id_refs``) with
``src/impl.cpp`` holding the one-line need ``IMPL_1``, and ``index``'s directive narrowed
to ``:file: refs.cpp`` unless a case says otherwise, so that only the directives a case
adds find ``IMPL_1``. The first owner keeps an id -- the directive read first, a
hand-written need, whatever defined it -- and every other directive finding it skips it
with one ``codelinks.duplicate_need`` warning at the marker's line. A document that
skipped a need is read again when the owner's document changes or goes, so the need
moves instead of vanishing.
"""

import hashlib
import re
from pathlib import Path

import pytest
from sphinx.testing.util import SphinxTestApp
from sphinx.util.console import strip_colors
from sphinx.util.parallel import parallel_available

from sphinx_needs_testkit import build_warnings

from .test_need_id_refs import (
    _SHOWS_WARNING_TYPES,
    DANGLING,
    _build,
    _json,
    _MakeApp,
    _project,
)
from .test_rediscovery import _scoped, _status, _touch_later
from .test_url_links import _card_links as _field_links

IMPL = "// @first impl, IMPL_1, impl, [REQ_001]\nvoid impl() {}\n"
#: the files every case starts from: index traces refs.cpp only
FILES = {
    **_scoped(":file: refs.cpp"),
    "src/impl.cpp": IMPL,
    "src/other.cpp": "// nothing to trace\n",
}


def _trace(option: str = ":file: impl.cpp", project: str = "src") -> str:
    return f"\n.. src-trace::\n   :project: {project}\n   {option}\n"


def _duplicate(
    owner: str,
    docname: str,
    location: str = "src/impl.cpp:1",
    need_id: str = "IMPL_1",
) -> str:
    suffix = " [codelinks.duplicate_need]" if _SHOWS_WARNING_TYPES else ""
    cure = (
        "give the markers distinct ids"
        if owner == docname
        else "narrow one directive's scope"
    )
    return (
        f"{location}: WARNING: one-line need {need_id!r} is already defined in document "
        f"{owner!r}: not created again by the src-trace directive in {docname!r} "
        f"({cure}){suffix}"
    )


def _duplicates(app: SphinxTestApp) -> list[str]:
    return [w for w in build_warnings(app) if "is already defined" in w]


def _owner(app: SphinxTestApp, need_id: str = "IMPL_1") -> str | None:
    """The document ``need_id`` is defined in, per ``needs.json`` (``None``: no need)."""
    need = _json(app)["needs"].get(need_id)
    return None if need is None else need["docname"]


def _cards(app: SphinxTestApp, page: str) -> int:
    html = Path(app.outdir, page).read_text(encoding="utf-8")
    return len(re.findall(r'id="IMPL_1"', html))


def _rewrite(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    assert old in text
    path.write_text(text.replace(old, new), encoding="utf-8")
    _touch_later(path)


#: a one-line style without ``id``: Sphinx-Needs generates it from the type's prefix and
#: the title (local URLs off here; on, in the #2082 case)
IDLESS = {
    "toml_extra": (
        "\n[codelinks.projects.src.analyse.oneline_comment_style]\n"
        'needs_fields = [{ name = "title" }, { name = "type", default = "impl" }]\n'
    ),
    "toml_replace": ("set_local_url = true", "set_local_url = false"),
}
IDLESS_FILES = {**FILES, "src/impl.cpp": "// @first impl\nvoid impl() {}\n"}
#: what Sphinx-Needs generates for ``first impl``: the ``impl`` type's prefix (``I_``) and
#: the first five characters of the title's SHA-1 (``needs_id_length``), upper case
GENERATED = "I_" + hashlib.sha1(b"first impl").hexdigest().upper()[:5]


def test_two_directives_in_one_document_define_the_need_once(
    tmp_path: Path, make_app: _MakeApp
) -> None:
    """``index`` traces the whole project and then ``impl.cpp`` again: one need, one
    warning at the marker's line, and the build goes on (it used to abort with
    ``duplicate_id``)."""
    _project(
        tmp_path,
        files={**FILES, **_scoped(None)},
        append={"docs/index.rst": _trace()},
    )
    app = _build(tmp_path, make_app)

    assert _owner(app) == "index"
    assert _duplicates(app) == [_duplicate("index", "index")]
    assert _cards(app, "index.html") == 1


def test_two_documents_the_earlier_sorting_one_defines_it(
    tmp_path: Path, make_app: _MakeApp
) -> None:
    """Sphinx reads in sorted order: ``page1`` defines ``IMPL_1``, ``page2`` skips it."""
    _project(
        tmp_path,
        files=FILES,
        append={"docs/page1.rst": _trace(), "docs/page2.rst": _trace()},
    )
    app = _build(tmp_path, make_app)

    assert _owner(app) == "page1"
    assert _duplicates(app) == [_duplicate("page1", "page2")]
    # read time, before the attach's warning
    assert build_warnings(app) == [_duplicate("page1", "page2"), DANGLING]
    assert (_cards(app, "page1.html"), _cards(app, "page2.html")) == (1, 0)


def test_the_need_moves_when_its_owner_is_removed(
    tmp_path: Path, make_app: _MakeApp
) -> None:
    """``page2`` skipped ``IMPL_1``; once ``page1`` is gone, ``page2`` is read again
    and defines it."""
    _project(
        tmp_path,
        files=FILES,
        append={"docs/page1.rst": _trace(), "docs/page2.rst": _trace()},
    )
    assert _owner(_build(tmp_path, make_app)) == "page1"

    (tmp_path / "docs" / "page1.rst").unlink()
    app = _build(tmp_path, make_app, freshenv=False)

    assert "0 added, 2 changed, 1 removed" in _status(app)  # index: its glob toctree
    assert re.search(r"reading sources\.\.\. \[[^\]]*\] page2\b", _status(app))
    assert _owner(app) == "page2"
    assert _duplicates(app) == []


def test_the_need_moves_when_its_owner_no_longer_traces_it(
    tmp_path: Path, make_app: _MakeApp
) -> None:
    """``page1``'s directive is narrowed to ``other.cpp``: ``page2`` is read again in
    the same build and defines ``IMPL_1``."""
    _project(
        tmp_path,
        files=FILES,
        append={"docs/page1.rst": _trace(), "docs/page2.rst": _trace()},
    )
    _build(tmp_path, make_app)

    _rewrite(tmp_path / "docs" / "page1.rst", ":file: impl.cpp", ":file: other.cpp")
    app = _build(tmp_path, make_app, freshenv=False)

    assert "0 added, 2 changed, 0 removed" in _status(app)
    assert _owner(app) == "page2"
    assert _duplicates(app) == []


def test_the_need_moves_when_its_owner_loses_the_file_to_an_ignore_rule(
    tmp_path: Path, make_app: _MakeApp
) -> None:
    """A ``.gitignore`` takes ``impl.cpp`` out of ``page1``'s directory scope: ``page1``
    is read again because its scope changed (no dependency of it changed), and so is
    ``page2``, which skipped the need."""
    _project(
        tmp_path,
        files=FILES,
        append={
            "docs/page1.rst": _trace(":directory: ."),
            "docs/page2.rst": _trace(),
        },
    )
    assert _owner(_build(tmp_path, make_app)) == "page1"

    (tmp_path / "src" / ".gitignore").write_text("impl.cpp\n", encoding="utf-8")
    app = _build(tmp_path, make_app, freshenv=False)

    assert "0 added, 2 changed, 0 removed" in _status(app)
    assert _owner(app) == "page2"
    assert _duplicates(app) == []


def test_the_earlier_sorting_directive_takes_the_need_when_both_are_read(
    tmp_path: Path, make_app: _MakeApp
) -> None:
    """An incremental build keeps the incumbent: ``page2`` defined ``IMPL_1`` before
    ``page1`` traced it, and ``page1``, read alone, defers. Once both are read in one
    build, the earlier-sorting ``page1`` defines it -- what a fresh build gives -- since
    ``page2``'s old need is about to be purged."""
    _project(tmp_path, files=FILES, append={"docs/page2.rst": _trace()})
    assert _owner(_build(tmp_path, make_app)) == "page2"

    page1 = tmp_path / "docs" / "page1.rst"
    page1.write_text(page1.read_text(encoding="utf-8") + _trace(), encoding="utf-8")
    _touch_later(page1)
    incumbent = _build(tmp_path, make_app, freshenv=False)
    assert "0 added, 1 changed, 0 removed" in _status(incumbent)
    assert _owner(incumbent) == "page2"
    assert _duplicates(incumbent) == [_duplicate("page2", "page1")]

    for page in ("page1", "page2"):
        path = tmp_path / "docs" / f"{page}.rst"
        path.write_text(path.read_text(encoding="utf-8") + "\n", encoding="utf-8")
        _touch_later(path)
    app = _build(tmp_path, make_app, freshenv=False)

    assert "0 added, 2 changed, 0 removed" in _status(app)
    assert _owner(app) == "page1"
    assert _duplicates(app) == [_duplicate("page1", "page2")]


def test_a_hand_written_need_keeps_its_id(tmp_path: Path, make_app: _MakeApp) -> None:
    """Whatever defined the id first owns it -- here an rst need in ``page1``; the
    directive in ``page2`` skips the marker (it used to abort with ``duplicate_id``)."""
    _project(
        tmp_path,
        files=FILES,
        append={
            "docs/page1.rst": "\n.. impl:: Hand-written\n   :id: IMPL_1\n",
            "docs/page2.rst": _trace(),
        },
    )
    app = _build(tmp_path, make_app)

    assert _owner(app) == "page1"
    assert _json(app)["needs"]["IMPL_1"]["title"] == "Hand-written"
    assert _duplicates(app) == [_duplicate("page1", "page2")]


def test_an_unchanged_owner_rereads_nothing(tmp_path: Path, make_app: _MakeApp) -> None:
    """The skipping document is read again only when its owner changes or goes."""
    _project(
        tmp_path,
        files=FILES,
        append={"docs/page1.rst": _trace(), "docs/page2.rst": _trace()},
    )
    _build(tmp_path, make_app)
    app = _build(tmp_path, make_app, freshenv=False)

    assert "0 added, 0 changed, 0 removed" in _status(app)
    assert _owner(app) == "page1"


def test_nested_projects_define_the_need_once(
    tmp_path: Path, make_app: _MakeApp
) -> None:
    """Ids are global: ``src`` and ``sub`` (``src/sub``) both find ``sub/x.cpp``; the
    project read first defines the need, the other skips it -- no configuration
    error."""
    _project(
        tmp_path,
        files={**_scoped(None), "src/sub/x.cpp": IMPL},
        append={"docs/later.rst": _trace("", project="sub")},
        toml_extra=(
            "\n[codelinks.projects.sub]\n"
            'remote_url_pattern = "https://github.com/example/demo/blob/{commit}/{path}#L{line}"\n'
            "\n[codelinks.projects.sub.source_discover]\n"
            'src_dir = "../src/sub"\n'
            'comment_type = "cpp"\n'
        ),
    )
    app = _build(tmp_path, make_app)

    assert _owner(app) == "index"
    assert _duplicates(app) == [_duplicate("index", "later", "src/sub/x.cpp:1")]


def test_the_summary_line_counts_the_skipped_needs(
    tmp_path: Path, make_app: _MakeApp
) -> None:
    _project(
        tmp_path,
        files=FILES,
        append={"docs/page1.rst": _trace(), "docs/page2.rst": _trace()},
    )
    app = _build(tmp_path, make_app)

    lines = re.findall(r"codelinks \[src\]: [^\n]*", _status(app))
    # one line per directive (index, page1, page2) and the attach's; only page2 skipped
    assert len(lines) == 4
    assert [line for line in lines if "skipped" in line] == [
        "codelinks [src]: 1 file, 1 marker, 1 skipped (already defined)"
    ]


@pytest.mark.skipif(
    not parallel_available, reason="Sphinx reads sources in parallel on POSIX only"
)
def test_parallel_directives_in_two_chunks_leave_one_need(
    tmp_path: Path, make_app: _MakeApp
) -> None:
    """``-j 2`` reads ``index .. page2`` and ``page3 .. sub/deep`` in two workers, which
    cannot see each other's needs: both directives define ``IMPL_1``, and Sphinx-Needs'
    merge keeps one and warns ``needs.duplicate_id`` -- accepted, and documented."""
    _project(
        tmp_path,
        files=FILES,
        append={"docs/page1.rst": _trace(), "docs/page3.rst": _trace()},
    )
    app = _build(tmp_path, make_app, parallel=2)

    status = strip_colors(app._status.getvalue())
    assert re.search(r"reading sources\.\.\. \[\s*\d+%\] \S+ \.\. \S+", status)
    assert _owner(app) in {"page1", "page3"}
    merged = [w for w in build_warnings(app) if "IMPL_1 already exists" in w]
    assert len(merged) == 1, build_warnings(app)
    if _SHOWS_WARNING_TYPES:
        assert merged[0].endswith("[needs.duplicate_id]")
    assert _duplicates(app) == []


def test_a_scope_record_pickled_before_deferred_existed_still_loads() -> None:
    """An environment pickled by an earlier release holds ``ScopeRecord`` objects
    without the ``deferred`` field; they load, and defer nothing."""
    import pickle

    from sphinx_codelinks.sphinx_extension.rediscovery import ScopeRecord

    record = ScopeRecord(project="src", kind="file", target="a.cpp", fingerprint=())
    object.__delattr__(record, "deferred")  # the state an older class pickled
    assert "deferred" not in vars(record)

    loaded = pickle.loads(pickle.dumps(record))
    assert loaded.deferred == ()
    assert loaded == ScopeRecord(
        project="src", kind="file", target="a.cpp", fingerprint=()
    )


@pytest.mark.parametrize("layout", ["one-document", "two-documents"])
def test_a_generated_id_is_defined_once(
    tmp_path: Path, make_app: _MakeApp, layout: str
) -> None:
    """A one-line style without ``id``: the id Sphinx-Needs would generate is checked
    like a written one (it used to abort with ``Unique ID could not be generated``)."""
    if layout == "one-document":
        files = {**IDLESS_FILES, **_scoped(None)}
        append = {"docs/index.rst": _trace()}
        owner, other = "index", "index"
    else:
        files = IDLESS_FILES
        append = {"docs/page1.rst": _trace(), "docs/page2.rst": _trace()}
        owner, other = "page1", "page2"
    _project(tmp_path, files=files, append=append, **IDLESS)  # type: ignore[arg-type]
    app = _build(tmp_path, make_app)

    needs = _json(app)["needs"]
    assert [n for n, need in needs.items() if need["title"] == "first impl"] == [
        GENERATED
    ]
    assert _owner(app, GENERATED) == owner
    assert _duplicates(app) == [_duplicate(owner, other, need_id=GENERATED)]


def test_a_generated_id_with_local_urls_links_its_source_page(
    tmp_path: Path, make_app: _MakeApp
) -> None:
    """A one-line style without ``id`` and local URLs on (no remote URL): the build
    goes on (it used to abort with ``KeyError: 'id'``), the card's local link names the
    source page, and that page's ``[docs]`` anchor links back to the generated id
    (#2082)."""
    _project(
        tmp_path,
        files={**IDLESS_FILES, **_scoped(None)},
        toml_extra=IDLESS["toml_extra"],
        toml_replace=("set_remote_url = true", "set_remote_url = false"),
    )
    app = _build(tmp_path, make_app)

    assert build_warnings(app) == [DANGLING]
    needs = _json(app)["needs"]
    assert needs[GENERATED]["local-url"] == "src/impl.cpp#L1"
    index = Path(app.outdir, "index.html").read_text(encoding="utf-8")
    assert _field_links(index, "local-url") == ["src/impl.html#L-1"]
    page = Path(app.outdir, "src", "impl.html").read_text(encoding="utf-8")
    assert re.findall(
        r'<a class="viewcode-back" href="([^"]*)">\[docs\]</a>', page
    ) == [f"../index.html#{GENERATED}"]


@pytest.mark.parametrize("generated", [False, True], ids=["written-id", "generated-id"])
def test_a_directive_moved_to_another_document(
    tmp_path: Path, make_app: _MakeApp, generated: bool
) -> None:
    """No overlap at any time: ``page2``'s trace moves to ``page1`` in one incremental
    build. ``page1`` is read first, while ``page2``'s old need is still in the store; it
    is about to be purged, so ``page1`` defines the need (this used to abort with
    ``duplicate_id``)."""
    need_id = GENERATED if generated else "IMPL_1"
    _project(
        tmp_path,
        files=IDLESS_FILES if generated else FILES,
        append={"docs/page2.rst": _trace()},
        **(IDLESS if generated else {}),  # type: ignore[arg-type]
    )
    assert _owner(_build(tmp_path, make_app), need_id) == "page2"

    _rewrite(tmp_path / "docs" / "page2.rst", ":file: impl.cpp", ":file: other.cpp")
    page1 = tmp_path / "docs" / "page1.rst"
    page1.write_text(page1.read_text(encoding="utf-8") + _trace(), encoding="utf-8")
    _touch_later(page1)
    app = _build(tmp_path, make_app, freshenv=False)

    assert "0 added, 2 changed, 0 removed" in _status(app)
    assert _owner(app, need_id) == "page1"
    assert _duplicates(app) == []


def test_two_markers_on_one_row_with_one_id_the_leftmost_defines_it(
    tmp_path: Path, make_app: _MakeApp
) -> None:
    """Two one-line needs on one row with one id: the leftmost is created and the other
    is skipped, on every row (#2150). It used to be whichever tree-sitter handed over
    first, which differs between runs; fifteen rows make that visible in one build."""
    rows = 15
    impl = "".join(
        f"/* @left {i}, IMPL_D{i}, impl */ /* @right {i}, IMPL_D{i}, impl */\n"
        for i in range(rows)
    )
    _project(
        tmp_path,
        files={**FILES, "src/impl.cpp": impl},
        append={"docs/index.rst": _trace()},
    )
    app = _build(tmp_path, make_app)

    needs = _json(app)["needs"]
    assert {f"IMPL_D{i}": needs[f"IMPL_D{i}"]["title"] for i in range(rows)} == {
        f"IMPL_D{i}": f"left {i}" for i in range(rows)
    }
    assert _duplicates(app) == [
        _duplicate("index", "index", f"src/impl.cpp:{i + 1}", f"IMPL_D{i}")
        for i in range(rows)
    ]
