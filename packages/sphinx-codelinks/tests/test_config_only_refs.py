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
        assert warnings[0].endswith(suffix)
        assert set(_refs(app).values()) == {None}


@pytest.mark.skipif(
    not parallel_available, reason="Sphinx reads sources in parallel on POSIX only"
)
def test_parallel_build_attaches_and_pages_the_sources(
    tmp_path: Path, make_app: _MakeApp
) -> None:
    """The configuration pass runs in the main process, so under ``-j 2`` the local
    copies and their source pages are made (unlike a directive's, #2044)."""
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
