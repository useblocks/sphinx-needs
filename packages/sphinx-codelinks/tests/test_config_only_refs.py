# @Test suite for references of projects without a src-trace directive, TEST_CONFIG_ONLY_REFS_1, test, [IMPL_LNK_1]
"""ubCode's config-only mode: a project with no ``src-trace`` directive still has its
``@need-ids:`` references attached.

Every case builds a copy of ``doc_test/need_id_refs`` (see ``test_need_id_refs``) whose
``index`` has NO ``src-trace`` directive, so project ``src`` is configured but traced by
nothing. Its ``refs.cpp`` references ``REQ_001`` (lines 1 and 3), ``REQ_002`` (line 3),
``NOSUCH_ID`` (line 5) and ``REQ_003`` (line 7).
"""

import os
import re
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from sphinx.errors import ExtensionError
from sphinx.testing.util import SphinxTestApp
from sphinx.util.console import strip_colors
from sphinx.util.parallel import parallel_available

from sphinx_codelinks.analyse.analyse import SourceAnalyse
from sphinx_needs_testkit import assert_no_warnings, build_warnings

from .test_need_id_refs import (
    _SHOWS_WARNING_TYPES,
    DANGLING,
    FIXTURE,
    _build,
    _card_links,
    _json,
    _MakeApp,
    _project,
    _refs,
    _url,
)

INDEX = (FIXTURE / "docs" / "index.rst").read_text(encoding="utf-8")
DIRECTIVE = ".. src-trace::\n   :project: src\n"
assert DIRECTIVE in INDEX
#: ``index`` without its directive: project ``src`` is configuration only
NO_DIRECTIVE = {"docs/index.rst": INDEX.replace(DIRECTIVE, "")}


def _status(app: SphinxTestApp) -> str:
    return strip_colors(app._status.getvalue())


def _touch_later(path: Path) -> None:
    later = path.stat().st_mtime + 10
    os.utime(path, (later, later))


def _edit(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    assert old in text
    path.write_text(text.replace(old, new), encoding="utf-8")
    _touch_later(path)


@pytest.fixture
def analyses(monkeypatch: pytest.MonkeyPatch) -> Iterator[list[str]]:
    """The names of the projects ``SourceAnalyse.run`` analysed, in order."""
    calls: list[str] = []
    original = SourceAnalyse.run

    def counting(self: SourceAnalyse, *args: Any, **kwargs: Any) -> None:
        calls.append(self.name)
        original(self, *args, **kwargs)

    monkeypatch.setattr(SourceAnalyse, "run", counting)
    yield calls


def _config_only_store(app: SphinxTestApp) -> dict[str, Any]:
    from sphinx_codelinks.sphinx_extension.rediscovery import config_only_refs_store

    return config_only_refs_store(app.env)


def test_references_attach_without_a_directive(
    tmp_path: Path, make_app: _MakeApp
) -> None:
    commit = _project(tmp_path, files=NO_DIRECTIVE)
    app = _build(tmp_path, make_app)

    refs = _refs(app)
    assert refs["REQ_001"] == [_url(commit, 1), _url(commit, 3)]
    assert refs["REQ_002"] == [_url(commit, 3)]
    assert refs["REQ_003"] == [_url(commit, 7)]
    assert refs["SPEC_001"] is None
    assert build_warnings(app) == [DANGLING]
    status = _status(app)
    assert "codelinks [src]: 1 file, 5 references\n" in status
    assert "codelinks [src]: 4 references attached, 1 unknown" in status
    assert _card_links(app, "later.html") == [[(_url(commit, 3), "src/refs.cpp#L3")]]


def test_a_project_with_a_directive_is_not_scanned_again(
    tmp_path: Path, make_app: _MakeApp, analyses: list[str]
) -> None:
    """The directive owns its project: the configuration pass skips it."""
    commit = _project(tmp_path)
    app = _build(tmp_path, make_app)

    assert analyses == ["src"]
    assert _config_only_store(app) == {}
    assert _refs(app)["REQ_001"] == [_url(commit, 1), _url(commit, 3)]
    assert "codelinks [src]: 4 references attached, 1 unknown" in _status(app)


def test_unchanged_rebuild_does_not_analyse(
    tmp_path: Path, make_app: _MakeApp, analyses: list[str]
) -> None:
    commit = _project(tmp_path, files=NO_DIRECTIVE)
    _build(tmp_path, make_app)
    assert analyses == ["src"]

    app = _build(tmp_path, make_app, freshenv=False)

    assert analyses == ["src"]
    assert "0 added, 0 changed, 0 removed" in _status(app)
    assert _refs(app)["REQ_002"] == [_url(commit, 3)]


def test_a_source_only_edit_is_analysed_once(
    tmp_path: Path, make_app: _MakeApp, analyses: list[str]
) -> None:
    """The edit is analysed in the build that sees it; that build reads no document,
    yet the environment is pickled (the affected page is written), so the next build
    finds a matching fingerprint and analyses nothing."""
    commit = _project(tmp_path, files=NO_DIRECTIVE)
    _build(tmp_path, make_app)
    _edit(
        tmp_path / "src" / "refs.cpp",
        "@need-ids: REQ_002, REQ_001",
        "@need-ids: REQ_001",
    )
    analyses.clear()

    edited = _build(tmp_path, make_app, freshenv=False)
    assert analyses == ["src"]
    assert "0 added, 0 changed, 0 removed" in _status(edited)
    assert _refs(edited)["REQ_002"] is None

    analyses.clear()
    app = _build(tmp_path, make_app, freshenv=False)
    assert analyses == []
    assert _refs(app)["REQ_002"] is None
    assert _refs(app)["REQ_001"] == [_url(commit, 1), _url(commit, 3)]


@pytest.mark.parametrize("change", ["edit", "new-file"])
def test_a_source_change_refreshes_the_records(
    tmp_path: Path, make_app: _MakeApp, change: str
) -> None:
    commit = _project(tmp_path, files=NO_DIRECTIVE)
    _build(tmp_path, make_app)
    if change == "edit":
        _edit(
            tmp_path / "src" / "refs.cpp",
            "@need-ids: REQ_002, REQ_001",
            "@need-ids: REQ_001",
        )
    else:
        (tmp_path / "src" / "new.cpp").write_text(
            "// @need-ids: SPEC_001\n", encoding="utf-8"
        )
    app = _build(tmp_path, make_app, freshenv=False)

    refs = _refs(app)
    if change == "edit":
        assert refs["REQ_001"] == [_url(commit, 1), _url(commit, 3)]
        assert refs["REQ_002"] is None
        assert refs["SPEC_001"] is None
    else:
        assert refs["REQ_002"] == [_url(commit, 3)]
        assert refs["SPEC_001"] == [_url(commit, 1, "src/new.cpp")]


def test_a_card_in_a_document_not_read_again_is_rewritten(
    tmp_path: Path, make_app: _MakeApp
) -> None:
    """No document is read at all, and ``later`` -- hosting ``REQ_002`` -- is written:
    its card no longer shows the reference the edit removed."""
    commit = _project(tmp_path, files=NO_DIRECTIVE)
    first = _build(tmp_path, make_app)
    assert _card_links(first, "later.html") == [[(_url(commit, 3), "src/refs.cpp#L3")]]

    _edit(
        tmp_path / "src" / "refs.cpp",
        "@need-ids: REQ_002, REQ_001",
        "@need-ids: REQ_001",
    )
    app = _build(tmp_path, make_app, freshenv=False)

    status = _status(app)
    assert "0 added, 0 changed, 0 removed" in status
    assert re.search(r"writing output\.\.\. \[[^\]]*\] later\b", status)
    assert _card_links(app, "later.html") == []


def test_removing_the_directive_attaches_from_the_configuration(
    tmp_path: Path, make_app: _MakeApp
) -> None:
    """The build that drops the last directive of a project attaches its references
    from the configuration pass already."""
    commit = _project(tmp_path)
    _build(tmp_path, make_app)
    _edit(tmp_path / "docs" / "index.rst", DIRECTIVE, "")
    app = _build(tmp_path, make_app, freshenv=False)

    assert "0 added, 1 changed, 0 removed" in _status(app)
    assert _refs(app)["REQ_001"] == [_url(commit, 1), _url(commit, 3)]
    assert set(_config_only_store(app)) == {"src"}


def test_a_project_new_to_the_configuration_is_attached(
    tmp_path: Path, make_app: _MakeApp
) -> None:
    gitlab = "https://gitlab.example.com/demo/-/blob/{commit}/{path}#L{line}"
    commit = _project(
        tmp_path, files={"src2/more.cpp": "// @need-ids: REQ_001\nvoid more() {}\n"}
    )
    _build(tmp_path, make_app)
    toml = tmp_path / "docs" / "ubproject.toml"
    toml.write_text(
        toml.read_text(encoding="utf-8")
        + (
            "\n[codelinks.projects.two]\n"
            f'remote_url_pattern = "{gitlab}"\n'
            "[codelinks.projects.two.source_discover]\n"
            'src_dir = "../src2"\n'
            'comment_type = "cpp"\n'
        ),
        encoding="utf-8",
    )
    app = _build(tmp_path, make_app, freshenv=False)

    assert _refs(app)["REQ_001"] == [
        _url(commit, 1),
        _url(commit, 3),
        gitlab.format(commit=commit, path="src2/more.cpp", line=1),
    ]


@pytest.mark.parametrize("gate", ["empty-field", "urls-off"])
def test_the_gate_off_scans_nothing(
    tmp_path: Path, make_app: _MakeApp, analyses: list[str], gate: str
) -> None:
    if gate == "empty-field":
        replace = (
            "[codelinks.projects.src]\n",
            '[codelinks.projects.src]\nref_url_field = ""\n',
        )
    else:
        replace = (
            "set_local_url = true\nset_remote_url = true\n",
            "set_local_url = false\nset_remote_url = false\n",
        )
    _project(tmp_path, files=NO_DIRECTIVE, toml_replace=replace)
    app = _build(tmp_path, make_app)

    assert analyses == []
    assert _config_only_store(app) == {}
    assert_no_warnings(app)
    assert set(_refs(app).values()) == {"<absent>"}


def test_a_missing_source_directory_warns_once_and_builds(
    tmp_path: Path, make_app: _MakeApp
) -> None:
    _project(
        tmp_path,
        files=NO_DIRECTIVE,
        toml_replace=('src_dir = "../src"', 'src_dir = "../nosuch"'),
    )
    suffix = " [codelinks.need_id_ref]" if _SHOWS_WARNING_TYPES else ""
    for freshenv in (True, False):
        app = _build(tmp_path, make_app, freshenv=freshenv)
        # a second application in one process also re-registers Sphinx' own nodes
        warnings = [w for w in build_warnings(app) if "is already registered" not in w]
        assert len(warnings) == 1, warnings
        assert warnings[0].startswith("WARNING: codelinks [src]: ")
        assert "nosuch" in warnings[0]
        assert "ConfigOnlyError: source directory" in warnings[0]
        assert warnings[0].endswith(suffix)
        assert set(_refs(app).values()) == {None}


@pytest.mark.skipif(
    not parallel_available, reason="Sphinx reads sources in parallel on POSIX only"
)
def test_parallel_build_attaches_and_pages_the_sources(
    tmp_path: Path, make_app: _MakeApp
) -> None:
    """The configuration pass runs in the main process, so under ``-j 2`` the local
    copies and their source pages are made (a directive's too, since #2044)."""
    _project(
        tmp_path,
        files=NO_DIRECTIVE,
        toml_replace=("set_remote_url = true", "set_remote_url = false"),
    )
    app = _build(tmp_path, make_app, parallel=2)

    assert re.search(r"reading sources\.\.\. \[\s*\d+%\] \S+ \.\. \S+", _status(app))
    refs = _refs(app)
    assert refs["REQ_001"] == ["src/refs.cpp#L1", "src/refs.cpp#L3"]
    assert refs["REQ_003"] == ["../src/refs.cpp#L7"]
    assert 'id="L-7"' in Path(app.outdir, "src", "refs.html").read_text(
        encoding="utf-8"
    )


def test_one_line_needs_are_not_created_and_are_counted(
    tmp_path: Path, make_app: _MakeApp
) -> None:
    """There is no directive to own them; ubCode creates none either."""
    _project(
        tmp_path,
        files={
            **NO_DIRECTIVE,
            "src/impl.cpp": "// @implemented here, IMPL_CONFIG_ONLY\nvoid f() {}\n",
        },
    )
    app = _build(tmp_path, make_app)

    assert "IMPL_CONFIG_ONLY" not in _json(app)["needs"]
    assert (
        "codelinks [src]: 2 files, 5 references, 1 one-line need not created "
        "(no src-trace directive)"
    ) in _status(app)


GITLAB = "https://gitlab.example.com/demo/-/blob/{commit}/{path}#L{line}"


@pytest.mark.parametrize("change", ["set_remote_url", "remote_url_pattern"])
def test_a_configuration_change_analyses_again(
    tmp_path: Path, make_app: _MakeApp, analyses: list[str], change: str
) -> None:
    """The fingerprint covers the files only: a configuration change (every document is
    read again) analyses the project again too, so its records follow the new values."""
    commit = _project(tmp_path, files=NO_DIRECTIVE)
    _build(tmp_path, make_app)
    toml = tmp_path / "docs" / "ubproject.toml"
    if change == "set_remote_url":
        _edit(toml, "set_remote_url = true", "set_remote_url = false")
    else:
        _edit(
            toml, "https://github.com/example/demo/blob/", GITLAB.split("{commit}")[0]
        )
    analyses.clear()
    app = _build(tmp_path, make_app, freshenv=False)

    assert analyses == ["src"]
    if change == "set_remote_url":
        assert _refs(app)["REQ_001"] == ["src/refs.cpp#L1", "src/refs.cpp#L3"]
        assert _card_links(app, "later.html") == [
            [("src/refs.html#L-3", "src/refs.cpp#L3")]
        ]
    else:
        assert _refs(app)["REQ_001"] == [
            GITLAB.format(commit=commit, path="src/refs.cpp", line=line)
            for line in (1, 3)
        ]


def test_a_configuration_change_while_a_directive_owns_the_project(
    tmp_path: Path, make_app: _MakeApp, analyses: list[str]
) -> None:
    """An entry ignored while a directive owned the project is not reused after a
    configuration change once the directive goes: config-only, directive added, remote
    URLs switched off, directive removed -- as ``-E`` would give."""
    _project(tmp_path, files=NO_DIRECTIVE)
    index = tmp_path / "docs" / "index.rst"
    toml = tmp_path / "docs" / "ubproject.toml"
    _build(tmp_path, make_app)
    _edit(index, INDEX.replace(DIRECTIVE, ""), INDEX)
    _build(tmp_path, make_app, freshenv=False)
    _edit(toml, "set_remote_url = true", "set_remote_url = false")
    _build(tmp_path, make_app, freshenv=False)
    _edit(index, INDEX, INDEX.replace(DIRECTIVE, ""))
    analyses.clear()
    app = _build(tmp_path, make_app, freshenv=False)

    assert analyses == ["src"]
    assert _refs(app)["REQ_001"] == ["src/refs.cpp#L1", "src/refs.cpp#L3"]


def _repository_wide(tmp_path: Path, path: str, *, gitignore: bool = True) -> None:
    """The fixture with ``src_dir = ".."`` -- the whole repository, docs and their
    ``_build`` included, no ignore rule for it -- and local URLs only, so that every
    HTML build copies the sources into its output."""
    _project(
        tmp_path,
        files=NO_DIRECTIVE if path == "config-only" else None,
        toml_replace=('src_dir = "../src"', 'src_dir = ".."'),
    )
    toml = tmp_path / "docs" / "ubproject.toml"
    text = toml.read_text(encoding="utf-8").replace(
        "set_remote_url = true", "set_remote_url = false"
    )
    if not gitignore:
        text = text.replace(
            'comment_type = "cpp"', 'comment_type = "cpp"\ngitignore = false'
        )
    toml.write_text(text, encoding="utf-8")


def _discovered(app: SphinxTestApp, path: str) -> list[str]:
    """What the last discovery of project ``src`` listed (relative to ``src_dir``)."""
    if path == "config-only":
        found = _config_only_store(app)["src"].fingerprint
    else:
        from sphinx_codelinks.sphinx_extension.rediscovery import scope_store

        found = tuple(
            e for scope in scope_store(app.env)["index"] for e in scope.fingerprint
        )
    return [relative for relative, _mtime, _size in found]


def _duplicates(app: SphinxTestApp) -> list[str]:
    return [w for w in build_warnings(app) if "duplicate" in w]


@pytest.mark.parametrize("path", ["directive", "config-only"])
def test_the_build_output_is_never_traced(
    tmp_path: Path, make_app: _MakeApp, analyses: list[str], path: str
) -> None:
    """A source directory containing the output directory does not trace the
    extension's own copies: nothing is analysed again, and each reference stays one
    entry. On the directive path the hosting document is edited once, so the directive
    runs again with the copies present (on the fresh build its discovery runs before it
    writes them)."""
    _repository_wide(tmp_path, path)
    first = _build(tmp_path, make_app)
    assert len(_refs(first)["REQ_003"]) == 1
    if path == "directive":
        # now, not later: a future mtime would re-read it on every build
        (tmp_path / "docs" / "index.rst").touch()
        rerun = _build(tmp_path, make_app, freshenv=False)
        assert "0 added, 1 changed, 0 removed" in _status(rerun)
        assert len(_refs(rerun)["REQ_003"]) == 1
    analyses.clear()
    for _ in range(3):
        app = _build(tmp_path, make_app, freshenv=False)
        assert "0 added, 0 changed, 0 removed" in _status(app)
        assert len(_refs(app)["REQ_003"]) == 1

    assert analyses == []
    assert len(list(tmp_path.rglob("*.cpp"))) == 2


@pytest.mark.parametrize("gitignore", [True, False], ids=["gitignore", "no-gitignore"])
@pytest.mark.parametrize(
    "builders",
    [("html", "dirhtml", "html", "dirhtml"), ("html", "latex", "html")],
    ids=["html-dirhtml", "html-latex"],
)
@pytest.mark.parametrize("path", ["directive", "config-only"])
def test_other_builders_output_is_never_traced(
    tmp_path: Path,
    make_app: _MakeApp,
    analyses: list[str],
    path: str,
    builders: tuple[str, ...],
    gitignore: bool,
) -> None:
    """The Makefile layout -- ``_build/<builder>`` beside a shared ``_build/doctrees``:
    one builder never traces another's copies -- with ``gitignore = true`` because an
    ``.ignore`` sits at the root of every builder's output and doctree directories,
    with ``gitignore = false`` because the build
    directory inside the documentation source directory is skipped as a whole: nothing
    is analysed again, each reference stays one entry, and no copy is ever made of a
    copy. (The doctree directory's half of the rule is unobservable here: no source
    file is ever written under it.) On the directive path the hosting document is
    edited after the first build, so the directive runs again with another builder's
    copies present."""
    _repository_wide(tmp_path, path, gitignore=gitignore)
    for number, builder in enumerate(builders):
        if number == 1 and path == "directive":
            # now, not later: a future mtime would re-read it on every build
            (tmp_path / "docs" / "index.rst").touch()
        if number == 2:
            analyses.clear()
        app = _build(tmp_path, make_app, buildername=builder, freshenv=number == 0)
        needs_json = Path(app.outdir, "needs.json")
        if needs_json.exists():
            assert len(_refs(app)["REQ_003"]) == 1, builder
        # each builder copies the source into its own output, once: no copy of a copy
        copies = [p for p in tmp_path.rglob("*.cpp") if "_build" in p.parts]
        assert all(p.parts.count("_build") == 1 for p in copies), copies

    assert analyses == []


@pytest.mark.parametrize(
    "builders",
    [("html", "dirhtml", "html", "dirhtml"), ("html", "latex", "html")],
    ids=["html-dirhtml", "html-latex"],
)
@pytest.mark.parametrize("path", ["directive", "config-only"])
def test_two_output_trees_outside_the_docs_never_trace_each_other(
    tmp_path: Path,
    make_app: _MakeApp,
    path: str,
    builders: tuple[str, ...],
) -> None:
    """``src_dir = "."`` at a repository root and the output in ``build/<builder>``,
    outside the documentation source directory, with no ignore rule for ``build/``
    (#2071): the ``.ignore`` at the root of every builder's output and doctree
    directories keeps every builder's copies out of
    discovery -- nothing under ``build/`` is ever listed, no copy is made of a copy,
    each reference stays one entry, and no one-line need is defined twice."""
    _repository_wide(tmp_path, path)
    name = tmp_path.name
    for number, builder in enumerate(builders):
        if number == 1 and path == "directive":
            # now, not later: a future mtime would re-read it on every build
            (tmp_path / "docs" / "index.rst").touch()
        app = _build(
            tmp_path,
            make_app,
            buildername=builder,
            builddir=tmp_path / "build",
            freshenv=number == 0,
        )
        assert _discovered(app, path) == ["src/refs.cpp"], builder
        if Path(app.outdir, "needs.json").exists():
            assert len(_refs(app)["REQ_003"]) == 1, builder
        assert _duplicates(app) == [], builder
        copies = sorted(
            p.relative_to(tmp_path).as_posix()
            for p in (tmp_path / "build").rglob("*.cpp")
        )
        paged = sorted({b for b in builders[: number + 1] if b != "latex"})
        assert copies == [f"build/{b}/{name}/src/refs.cpp" for b in paged], builder


@pytest.mark.parametrize("path", ["directive", "config-only"])
def test_an_output_directory_beside_traced_sources_hides_nothing(
    tmp_path: Path, make_app: _MakeApp, path: str
) -> None:
    """The output and doctree directories placed directly inside a traced source
    directory (``docs/code/html``, ``docs/code/doctrees``): with ``gitignore = true``
    the sources beside them are traced -- only the two directories themselves are
    skipped (#2065's caveat, gone) -- by the directive, by the scope walk of an
    unchanged rebuild (which re-reads nothing) and by the config-only scan."""
    files = {
        "docs/code/beside.cpp": (
            "// @need-ids: REQ_001\n// @beside the output, IMPL_BESIDE, impl\n"
        )
    }
    _project(
        tmp_path,
        toml_replace=('src_dir = "../src"', 'src_dir = "code"'),
        files={**files, **(NO_DIRECTIVE if path == "config-only" else {})},
    )
    toml = tmp_path / "docs" / "ubproject.toml"
    _edit(toml, "set_remote_url = true", "set_remote_url = false")
    builddir = tmp_path / "docs" / "code"
    first = _build(tmp_path, make_app, builddir=builddir)
    unchanged = _build(tmp_path, make_app, builddir=builddir, freshenv=False)

    assert "0 added, 0 changed, 0 removed" in _status(unchanged)
    assert _discovered(unchanged, path) == ["beside.cpp"]
    assert _refs(unchanged)["REQ_001"] == ["code/beside.cpp#L1"]
    if path == "config-only":
        return
    assert "IMPL_BESIDE" in _json(first)["needs"]
    (tmp_path / "docs" / "index.rst").touch()
    app = _build(tmp_path, make_app, builddir=builddir, freshenv=False)

    assert "0 added, 1 changed, 0 removed" in _status(app)
    assert _json(app)["needs"]["IMPL_BESIDE"]["docname"] == "index"
    assert _duplicates(app) == []
    copies = sorted(p.relative_to(builddir).as_posix() for p in builddir.rglob("*.cpp"))
    assert copies == ["beside.cpp", "html/code/beside.cpp"]


@pytest.mark.parametrize("builder", ["html", "latex"])
def test_the_output_and_doctree_directories_hold_an_ignore_that_is_never_traced(
    tmp_path: Path, make_app: _MakeApp, builder: str
) -> None:
    """Every builder writes ``.ignore`` (``*``) at the root of its output directory and
    of the doctree directory, on every build: restored when deleted, an identical one
    left alone, and itself never a source -- so with ``gitignore = true`` nothing any
    builder writes is traced."""
    from sphinx_codelinks.source_discover.config import SourceDiscoverConfig
    from sphinx_codelinks.sphinx_extension.rediscovery import fingerprint

    _project(tmp_path, toml_replace=("set_remote_url = true", "set_remote_url = false"))
    first = _build(tmp_path, make_app, buildername=builder)
    roots = [Path(first.outdir), Path(first.doctreedir)]
    markers = [root / ".ignore" for root in roots]
    assert [m.read_bytes() for m in markers] == [b"*\n", b"*\n"]
    left = markers[1].stat().st_mtime_ns
    markers[0].unlink()

    _build(tmp_path, make_app, buildername=builder, freshenv=False)

    assert markers[0].read_bytes() == b"*\n"
    assert markers[1].stat().st_mtime_ns == left
    for root in roots:
        for gitignore in (True, False):
            listed = [
                entry[0]
                for entry in fingerprint(
                    SourceDiscoverConfig(root, gitignore=gitignore, comment_type="cpp"),
                    exclude=(),
                )
            ]
            assert ".ignore" not in {Path(e).name for e in listed}, (root, gitignore)
            if gitignore:
                assert listed == [], root


_DOWNLOAD = "\nThe implementation: :download:`impl.cpp <../src/impl.cpp>`.\n"


def test_a_downloaded_source_in_another_builders_output_is_never_traced(
    tmp_path: Path, make_app: _MakeApp
) -> None:
    """The Makefile layout, ``src_dir = ".."``, no ignore rule for ``_build``, the
    default ``gitignore = true``, and ``index`` offering a traced source for download:
    every HTML builder copies it into ``_downloads/``, and no builder traces another's
    copy -- only ``src/`` is discovered, the need is defined once from ``src/impl.cpp``,
    and the third build reads nothing."""
    _repository_wide(tmp_path, "directive")
    (tmp_path / "src" / "impl.cpp").write_text(
        "// @first impl, IMPL_1, impl\n", encoding="utf-8"
    )
    index = tmp_path / "docs" / "index.rst"
    index.write_text(index.read_text(encoding="utf-8") + _DOWNLOAD, encoding="utf-8")
    name = tmp_path.name
    for number, builder in enumerate(("html", "dirhtml", "html")):
        if number == 1:
            # now, not later: a future mtime would re-read it on every build
            index.touch()
        app = _build(tmp_path, make_app, buildername=builder, freshenv=number == 0)
        assert list(Path(app.outdir, "_downloads").rglob("impl.cpp")), builder
        assert _discovered(app, "directive") == ["src/impl.cpp", "src/refs.cpp"], (
            builder
        )
        assert _duplicates(app) == [], builder
        assert _json(app)["needs"]["IMPL_1"]["local-url"] == f"{name}/src/impl.cpp#L1"
    assert "0 added, 0 changed, 0 removed" in _status(app)


@pytest.mark.parametrize("state", ["unchanged", "failing-scan"])
def test_a_build_with_nothing_to_redo_writes_nothing(
    tmp_path: Path, make_app: _MakeApp, state: str
) -> None:
    """No document is written for a project that was not analysed again, nor for one
    whose scan fails (it would fail again next build)."""
    _project(
        tmp_path,
        files=NO_DIRECTIVE,
        toml_replace=None
        if state == "unchanged"
        else ('src_dir = "../src"', 'src_dir = "../nosuch"'),
    )
    _build(tmp_path, make_app)
    for _ in range(2):
        app = _build(tmp_path, make_app, freshenv=False)
        status = _status(app)
        assert "0 added, 0 changed, 0 removed" in status
        assert not re.search(r"writing output\.\.\. \[", status), status


@pytest.mark.parametrize(
    ("old", "new"),
    [
        ("return a + 1;", "return a + 12345;"),
        ("void deep()", "void DEEP()"),
        ("@need-ids: NOSUCH_ID", "@need-ids: NOSUCH_TWO"),
    ],
    ids=["code-only", "same-size-rename", "unknown-id"],
)
def test_an_edit_that_moves_no_reference_is_analysed_once(
    tmp_path: Path, make_app: _MakeApp, analyses: list[str], old: str, new: str
) -> None:
    """No known need's references change, so no need's document is written; the root
    document is, so the environment -- and the new scan -- is kept."""
    commit = _project(tmp_path, files=NO_DIRECTIVE)
    _build(tmp_path, make_app)
    _edit(tmp_path / "src" / "refs.cpp", old, new)
    counts = []
    for build in range(4):
        analyses.clear()
        app = _build(tmp_path, make_app, freshenv=False)
        counts.append(len(analyses))
        if build == 0:
            status = _status(app)
            assert "pickling environment" in status
            assert re.search(r"writing output\.\.\. \[[^\]]*\] index\b", status)
        assert _refs(app)["REQ_001"] == [_url(commit, 1), _url(commit, 3)]

    assert counts == [1, 0, 0, 0]


def test_a_programming_error_in_the_scan_fails_the_build(
    tmp_path: Path, make_app: _MakeApp, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Only the errors discovery and the analysis raise become a warning; a bug in the
    extension is not read as a scan failure."""
    from sphinx_codelinks.sphinx_extension import rediscovery

    def broken(*_args: Any, **_kwargs: Any) -> Any:
        raise KeyError("not a scan failure")

    monkeypatch.setattr(rediscovery, "scan_config_only_project", broken)
    _project(tmp_path, files=NO_DIRECTIVE)
    with pytest.raises(ExtensionError) as raised:
        _build(tmp_path, make_app)
    assert isinstance(raised.value.orig_exc, KeyError)


_EARLY_EXTENSION = """
def setup(app):
    from sphinx_needs.data import SphinxNeedsData

    def resolve(app, env):
        SphinxNeedsData(env).get_needs_view()

    app.connect("env-updated", resolve)
    return {"parallel_read_safe": True}
"""


def test_the_scan_runs_before_other_env_updated_handlers(
    tmp_path: Path, make_app: _MakeApp
) -> None:
    """An extension loaded before this one whose ``env-updated`` handler resolves the
    needs (post-processing, so the attach) still sees the config-only references."""
    commit = _project(
        tmp_path,
        files={**NO_DIRECTIVE, "docs/early.py": _EARLY_EXTENSION},
        append={
            "docs/conf.py": (
                "import os, sys\n"
                "sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))\n"
                'extensions.insert(1, "early")\n'
            )
        },
    )
    app = _build(tmp_path, make_app)

    assert _refs(app)["REQ_001"] == [_url(commit, 1), _url(commit, 3)]
