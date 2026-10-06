# @Test suite for incremental builds that see new source files, TEST_REDISCOVERY_1, test, [IMPL_LNK_1]
"""Incremental builds see the files a ``src-trace`` directive's scope gains or loses.

Every case builds a copy of ``doc_test/need_id_refs`` (see ``test_need_id_refs``), with
the ``src-trace`` directive of ``index`` given the scope the case needs, then builds
again without ``-E``: a file added, removed or edited under the scope re-reads the
hosting document; a file outside the scope does not.
"""

import os
import re
from pathlib import Path, PureWindowsPath
from typing import Any

import pytest
from sphinx.testing.util import SphinxTestApp
from sphinx.util.console import strip_colors
from sphinx.util.parallel import parallel_available

from .test_need_id_refs import (
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

#: a one-line need and a reference, in a file the first build did not see
NEW_SOURCE = "// @new need, IMPL_NEW, impl, [REQ_002]\n// @need-ids: REQ_002\n"


def _scoped(option: str | None) -> dict[str, str]:
    """``files=`` for :func:`_project`: ``index``'s directive with ``option`` added."""
    directive = DIRECTIVE if option is None else f"{DIRECTIVE}   {option}\n"
    return {"docs/index.rst": INDEX.replace(DIRECTIVE, directive)}


def _status(app: SphinxTestApp) -> str:
    return strip_colors(app._status.getvalue())


def _touch_later(path: Path) -> None:
    later = path.stat().st_mtime + 10
    os.utime(path, (later, later))


def test_unchanged_rebuild_reads_nothing(tmp_path: Path, make_app: _MakeApp) -> None:
    """The fingerprint is stable: a rebuild with nothing touched re-reads nothing."""
    _project(tmp_path, files=_scoped(":directory: ."))
    _build(tmp_path, make_app)
    app = _build(tmp_path, make_app, freshenv=False)

    assert "0 added, 0 changed, 0 removed" in _status(app)


def test_new_file_in_a_directory_scope_rereads_the_host(
    tmp_path: Path, make_app: _MakeApp
) -> None:
    """A file added under a ``:directory:`` scope is seen without ``-E``: its one-line
    need is created and its reference attached (#2040)."""
    commit = _project(tmp_path, files=_scoped(":directory: ."))
    first = _build(tmp_path, make_app)
    assert "IMPL_NEW" not in _json(first)["needs"]

    (tmp_path / "src" / "new.cpp").write_text(NEW_SOURCE, encoding="utf-8")
    app = _build(tmp_path, make_app, freshenv=False)

    assert "0 added, 1 changed, 0 removed" in _status(app)
    assert "IMPL_NEW" in _json(app)["needs"]
    assert _refs(app)["REQ_002"] == [
        _url(commit, 2, "src/new.cpp"),
        _url(commit, 3),
    ]


def test_new_file_in_a_subdirectory_of_the_scope_rereads_the_host(
    tmp_path: Path, make_app: _MakeApp
) -> None:
    """The walk is recursive: a nested addition counts (a directory's own mtime would
    not show it)."""
    _project(tmp_path, files={**_scoped(":directory: ."), "src/lib/a.cpp": "// a\n"})
    _build(tmp_path, make_app)

    (tmp_path / "src" / "lib" / "deeper").mkdir()
    (tmp_path / "src" / "lib" / "deeper" / "new.cpp").write_text(
        NEW_SOURCE, encoding="utf-8"
    )
    app = _build(tmp_path, make_app, freshenv=False)

    assert "0 added, 1 changed, 0 removed" in _status(app)
    assert "IMPL_NEW" in _json(app)["needs"]


def test_new_sibling_of_a_file_scope_rereads_nothing(
    tmp_path: Path, make_app: _MakeApp
) -> None:
    """A ``:file:`` scope is that one file: a new file beside it costs nothing."""
    _project(tmp_path, files=_scoped(":file: refs.cpp"))
    _build(tmp_path, make_app)

    (tmp_path / "src" / "sibling.cpp").write_text(NEW_SOURCE, encoding="utf-8")
    app = _build(tmp_path, make_app, freshenv=False)

    assert "0 added, 0 changed, 0 removed" in _status(app)
    assert "IMPL_NEW" not in _json(app)["needs"]


def test_removed_file_rereads_and_drops_its_records(
    tmp_path: Path, make_app: _MakeApp
) -> None:
    commit = _project(
        tmp_path,
        files={
            **_scoped(":directory: ."),
            "src/new.cpp": NEW_SOURCE,
        },
    )
    first = _build(tmp_path, make_app)
    assert _refs(first)["REQ_002"] == [_url(commit, 2, "src/new.cpp"), _url(commit, 3)]

    (tmp_path / "src" / "new.cpp").unlink()
    app = _build(tmp_path, make_app, freshenv=False)

    assert "0 added, 1 changed, 0 removed" in _status(app)
    assert "IMPL_NEW" not in _json(app)["needs"]
    assert _refs(app)["REQ_002"] == [_url(commit, 3)]


@pytest.mark.parametrize("rule", ["exclude", "gitignore"])
def test_new_file_the_discovery_rules_skip_rereads_nothing(
    tmp_path: Path, make_app: _MakeApp, rule: str
) -> None:
    """The fingerprint walks exactly what the directive discovers."""
    if rule == "exclude":
        _project(
            tmp_path,
            files=_scoped(":directory: ."),
            toml_replace=(
                'src_dir = "../src"\n',
                'src_dir = "../src"\nexclude = ["skipped/**"]\n',
            ),
        )
    else:
        _project(
            tmp_path,
            files={**_scoped(":directory: ."), "src/.gitignore": "skipped/\n"},
        )
    _build(tmp_path, make_app)

    (tmp_path / "src" / "skipped").mkdir()
    (tmp_path / "src" / "skipped" / "new.cpp").write_text(NEW_SOURCE, encoding="utf-8")
    app = _build(tmp_path, make_app, freshenv=False)

    assert "0 added, 0 changed, 0 removed" in _status(app)
    assert "IMPL_NEW" not in _json(app)["needs"]


def test_two_directives_over_one_scope_walk_it_once(
    tmp_path: Path, make_app: _MakeApp, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The check is memoised per scope within a build."""
    from sphinx_codelinks.sphinx_extension import rediscovery

    _project(
        tmp_path,
        append={"docs/later.rst": f"\n{DIRECTIVE}"},
    )
    _build(tmp_path, make_app)
    walks: list[Any] = []
    original = rediscovery.discover_scope

    def counting(*args: Any, **kwargs: Any) -> Any:
        walks.append(args)
        return original(*args, **kwargs)

    monkeypatch.setattr(rediscovery, "discover_scope", counting)
    app = _build(tmp_path, make_app, freshenv=False)

    assert "0 added, 0 changed, 0 removed" in _status(app)
    assert len(walks) == 1


@pytest.mark.skipif(
    not parallel_available, reason="Sphinx reads sources in parallel on POSIX only"
)
def test_scopes_read_in_parallel_reach_the_main_process(
    tmp_path: Path, make_app: _MakeApp
) -> None:
    """``-j 2`` records the scopes in a worker; ``env-merge-info`` brings them back, so the
    next (serial) build still sees the new file."""
    _project(tmp_path, files=_scoped(":directory: ."))
    first = _build(tmp_path, make_app, parallel=2)
    assert re.search(r"reading sources\.\.\. \[\s*\d+%\] \S+ \.\. \S+", _status(first))

    (tmp_path / "src" / "new.cpp").write_text(NEW_SOURCE, encoding="utf-8")
    app = _build(tmp_path, make_app, freshenv=False)

    assert "0 added, 1 changed, 0 removed" in _status(app)
    assert "IMPL_NEW" in _json(app)["needs"]


def test_a_card_in_a_document_not_read_again_is_rewritten(
    tmp_path: Path, make_app: _MakeApp
) -> None:
    """A source-only edit re-reads only the hosting document; ``REQ_002`` lives in
    ``later``, which is not read again -- its card is still rewritten, and so it no
    longer shows the reference the edit removed. ``later`` is written, not read."""
    commit = _project(tmp_path)
    first = _build(tmp_path, make_app)
    assert _card_links(first, "later.html") == [[(_url(commit, 3), "src/refs.cpp#L3")]]

    source = tmp_path / "src" / "refs.cpp"
    source.write_text(
        source.read_text(encoding="utf-8").replace(
            "@need-ids: REQ_002, REQ_001", "@need-ids: REQ_001"
        ),
        encoding="utf-8",
    )
    _touch_later(source)
    app = _build(tmp_path, make_app, freshenv=False)

    status = _status(app)
    assert "0 added, 1 changed, 0 removed" in status
    assert _refs(app)["REQ_002"] is None
    assert _card_links(app, "later.html") == []
    assert not re.search(r"reading sources\.\.\. \[[^\]]*\] later\b", status)
    assert re.search(r"writing output\.\.\. \[[^\]]*\] later\b", status)


def test_fingerprint_is_the_discovered_files_with_mtime_and_size(
    tmp_path: Path,
) -> None:
    from sphinx_codelinks.source_discover.config import SourceDiscoverConfig
    from sphinx_codelinks.sphinx_extension.rediscovery import fingerprint

    (tmp_path / "lib").mkdir()
    (tmp_path / "b.cpp").write_bytes(b"// b\n")
    (tmp_path / "lib" / "a.cpp").write_bytes(b"// aa\n")
    (tmp_path / "notes.txt").write_text("not a source\n", encoding="utf-8")
    config = SourceDiscoverConfig(tmp_path, comment_type="cpp")

    found = fingerprint(config, exclude=())
    assert [(path, size) for path, _mtime, size in found] == [
        ("b.cpp", 5),
        ("lib/a.cpp", 6),
    ]
    assert fingerprint(config, exclude=()) == found
    _touch_later(tmp_path / "b.cpp")
    assert fingerprint(config, exclude=()) != found
    assert fingerprint(SourceDiscoverConfig(tmp_path / "missing"), exclude=()) == ()


def test_a_file_scope_fingerprints_that_one_file(tmp_path: Path) -> None:
    from sphinx_codelinks.sphinx_extension.rediscovery import file_fingerprint

    (tmp_path / "a.cpp").write_bytes(b"// a\n")
    found = file_fingerprint(tmp_path, "a.cpp")
    assert [(path, size) for path, _mtime, size in found] == [("a.cpp", 5)]
    (tmp_path / "b.cpp").write_bytes(b"// b\n")
    assert file_fingerprint(tmp_path, "a.cpp") == found
    assert file_fingerprint(tmp_path, "missing.cpp") == ()


def test_fingerprint_paths_are_posix_on_windows() -> None:
    """The stored path is POSIX whatever the platform's separator."""
    from sphinx_codelinks.sphinx_extension.rediscovery import scope_relative_path

    path = PureWindowsPath("C:/work/src/lib/a.cpp")
    assert scope_relative_path(path, PureWindowsPath("C:/work/src")) == "lib/a.cpp"


def test_exclusion_stops_at_the_directory_boundary(tmp_path: Path) -> None:
    """``_build2/`` is not under ``_build/``: the excluded prefix ends at a separator."""
    from sphinx_codelinks.sphinx_extension.rediscovery import _outside

    root = tmp_path.resolve()
    files = [root / "_build" / "a.cpp", root / "_build2" / "a.cpp"]
    assert _outside(files, [root / "_build"]) == [root / "_build2" / "a.cpp"]
