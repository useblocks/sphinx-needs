# @Test suite for sources outside the roots their records are relative to, TEST_OUTSIDE_ROOTS_1, test, [IMPL_DISC_1]
"""A source file outside the root its records are relative to is diagnosed (#2062).

Two configurations put one there: a configured ``git_root`` that does not contain the
project's ``src_dir`` (or does not exist), which is ignored with one
``codelinks.git_root`` warning, the repository root being detected from ``src_dir``
instead; and a discovered file that resolves to outside ``src_dir`` (a symbolic link out
of the tree), which is not traced, with one ``codelinks.outside_src_dir`` warning
naming the link. Every build case copies ``doc_test/need_id_refs`` (see
``test_need_id_refs``).
"""

import json
import ntpath
import os
import posixpath
import re
import subprocess
import sys
from pathlib import Path, PurePosixPath, PureWindowsPath
from types import SimpleNamespace
from typing import Any

import pytest
import sphinx
from sphinx.testing.util import SphinxTestApp
from typer.testing import CliRunner

from sphinx_codelinks.analyse.references import NeedIdRef
from sphinx_codelinks.cmd import app as cli
from sphinx_codelinks.config import CodeLinksConfig, git_root_problem
from sphinx_codelinks.source_discover import source_discover
from sphinx_codelinks.source_discover.config import SourceDiscoverConfig
from sphinx_codelinks.sphinx_extension.need_id_refs import (
    need_id_refs_store,
    project_roots,
)
from sphinx_codelinks.sphinx_extension.rediscovery import discover_scope
from sphinx_needs_testkit import build_warnings

from .test_need_id_refs import (
    DANGLING,
    FIXTURE,
    _build,
    _json,
    _MakeApp,
    _project,
    _refs,
    _url,
)

#: Sphinx 8 renders a warning's ``[type.subtype]`` itself; 7.4 does not
_SHOWS_WARNING_TYPES = sphinx.version_info >= (8,)

INDEX = (FIXTURE / "docs" / "index.rst").read_text(encoding="utf-8")
DIRECTIVE = ".. src-trace::\n   :project: src\n"
assert DIRECTIVE in INDEX

#: the file the links point at: a one-line need and a reference, so that a traced
#: copy of it shows in the needs and in ``REQ_002``'s references alike
OUTSIDE_SOURCE = "// @outside need, IMPL_OUTSIDE\n// @need-ids: REQ_002\n"

LOCAL_ONLY = ("set_remote_url = true", "set_remote_url = false")
REMOTE_ONLY = ("set_local_url = true", "set_local_url = false")


def _git_root(value: str) -> str:
    return f'\n[codelinks.projects.src.analyse]\ngit_root = "{value}"\n'


def _git_root_warning(root: Path, problem: str) -> str:
    suffix = " [codelinks.git_root]" if _SHOWS_WARNING_TYPES else ""
    return (
        f"WARNING: project 'src': git_root {root.as_posix()} {problem}; it is "
        "ignored, and the repository root is detected from src_dir instead"
        f"{suffix}"
    )


def _outside_warning(link: Path, target: Path, src_dir: Path) -> str:
    """The warning about ``link``, which leads it (the package logger appends the
    type on Sphinx 7)."""
    return (
        f"WARNING: {link.as_posix()} resolves to "
        f"{target.as_posix()}, outside src_dir {src_dir.as_posix()}: not traced "
        "(widen src_dir to cover it, or exclude the link) [codelinks.outside_src_dir]"
    )


def _records(app: SphinxTestApp) -> list[NeedIdRef]:
    """Every directive's records, in file and line order."""
    records = [ref for refs in need_id_refs_store(app.env).values() for ref in refs]
    return sorted(records, key=lambda ref: (ref.path, ref.lineno, ref.need_id))


def _link_out(root: Path, link: str, target: str, *, directory: bool = False) -> None:
    """Make ``root/link`` a symbolic link to ``root/target``."""
    (root / link).symlink_to(root / target, target_is_directory=directory)


# -- a git_root that does not contain src_dir ----------------------------------------


def test_git_root_outside_src_dir_is_ignored_with_a_warning(
    tmp_path: Path, make_app: _MakeApp
) -> None:
    """``git_root = "../other"`` exists but holds no source: one warning naming both
    paths, and the records are relative to the repository detected from ``src_dir``
    -- no ``../``, ``root == "git"``, and each round-trips through its dictionary."""
    (tmp_path / "other").mkdir()
    _project(tmp_path, toml_replace=LOCAL_ONLY, toml_extra=_git_root("../other"))
    app = _build(tmp_path, make_app)

    root = tmp_path.resolve()
    assert build_warnings(app) == [
        _git_root_warning(
            root / "other", f"does not contain src_dir {(root / 'src').as_posix()}"
        ),
        DANGLING,
    ]
    records = _records(app)
    assert records
    assert {ref.path for ref in records} == {"src/refs.cpp"}
    assert {ref.root for ref in records} == {"git"}
    assert [NeedIdRef.from_dict(ref.to_dict()) for ref in records] == records
    assert _refs(app)["REQ_001"] == ["src/refs.cpp#L1", "src/refs.cpp#L3"]


def test_git_root_outside_src_dir_with_remote_urls_uses_the_detected_root(
    tmp_path: Path, make_app: _MakeApp
) -> None:
    """With remote URLs on the remote path is no longer a traceback: the URLs are
    formed below the repository detected from ``src_dir``."""
    (tmp_path / "other").mkdir()
    commit = _project(tmp_path, toml_extra=_git_root("../other"))
    app = _build(tmp_path, make_app)

    root = tmp_path.resolve()
    assert build_warnings(app) == [
        _git_root_warning(
            root / "other", f"does not contain src_dir {(root / 'src').as_posix()}"
        ),
        DANGLING,
    ]
    refs = _refs(app)
    assert refs["REQ_001"] == [_url(commit, 1), _url(commit, 3)]
    assert refs["REQ_003"] == [_url(commit, 7)]


def test_missing_git_root_is_ignored_with_a_warning(
    tmp_path: Path, make_app: _MakeApp
) -> None:
    """A ``git_root`` naming no directory is the same warning class, and the build
    goes on with the detected root."""
    commit = _project(tmp_path, toml_extra=_git_root("../missing"))
    app = _build(tmp_path, make_app)

    assert build_warnings(app) == [
        _git_root_warning(tmp_path.resolve() / "missing", "does not exist"),
        DANGLING,
    ]
    assert _refs(app)["REQ_001"] == [_url(commit, 1), _url(commit, 3)]
    assert {ref.path for ref in _records(app)} == {"src/refs.cpp"}


def test_the_attach_root_is_the_records_root(
    tmp_path: Path, make_app: _MakeApp
) -> None:
    """The root the attach dedupes on is the one the records were made relative to:
    both ignore the same ``git_root``."""
    (tmp_path / "other").mkdir()
    _project(tmp_path, toml_replace=LOCAL_ONLY, toml_extra=_git_root("../other"))
    app = _build(tmp_path, make_app)

    roots = project_roots(app.confdir, CodeLinksConfig.from_sphinx(app.config))
    assert roots == {"src": tmp_path.resolve().as_posix()}


@pytest.mark.parametrize("accepted", ["src_dir", "above_the_repository"])
def test_an_accepted_git_root_is_the_records_and_the_attachs_root(
    tmp_path: Path, make_app: _MakeApp, accepted: str
) -> None:
    """A ``git_root`` other than the detected repository -- ``src_dir`` itself, or a
    directory above the repository that is no repository -- is used by the analysis
    AND by the attach: the records are relative to it, and ``project_roots()`` names
    it."""
    project = tmp_path / "proj"
    project.mkdir()
    value, root, path = {
        "src_dir": ("../src", project / "src", "refs.cpp"),
        "above_the_repository": (tmp_path.as_posix(), tmp_path, "proj/src/refs.cpp"),
    }[accepted]
    _project(project, toml_replace=LOCAL_ONLY, toml_extra=_git_root(value))
    app = _build(project, make_app)

    assert not any("codelinks.git_root" in w for w in build_warnings(app))
    records = _records(app)
    assert records
    assert {ref.path for ref in records} == {path}
    assert {ref.root for ref in records} == {"git"}
    roots = project_roots(app.confdir, CodeLinksConfig.from_sphinx(app.config))
    assert roots == {"src": root.resolve().as_posix()}
    assert (Path(roots["src"]) / path).resolve() == (
        project / "src" / "refs.cpp"
    ).resolve()


@pytest.mark.skipif(
    sys.platform == "win32" or (hasattr(os, "geteuid") and os.geteuid() == 0),
    reason="needs POSIX permissions that bind the running user",
)
def test_an_unreadable_git_root_is_ignored_with_a_warning(
    tmp_path: Path, make_app: _MakeApp
) -> None:
    """A ``git_root`` below a directory that cannot be read is treated as unset, as a
    missing one is, instead of failing the build at ``config-inited``."""
    project = tmp_path / "proj"
    project.mkdir()
    locked = tmp_path / "locked"
    (locked / "inner").mkdir(parents=True)
    _project(
        project,
        toml_replace=LOCAL_ONLY,
        toml_extra=_git_root((locked / "inner").as_posix()),
    )
    locked.chmod(0)
    try:
        app = _build(project, make_app)
    finally:
        locked.chmod(0o755)

    assert [w for w in build_warnings(app) if "codelinks.git_root" in w] == [
        _git_root_warning(locked.resolve() / "inner", "cannot be read")
    ]
    assert {ref.path for ref in _records(app)} == {"src/refs.cpp"}


def test_a_git_root_above_src_dir_changes_nothing(
    tmp_path: Path, make_app: _MakeApp
) -> None:
    """``git_root = ".."`` -- the repository, an ancestor of ``src_dir`` -- warns
    nothing new, and the records and URLs are those of a build without it."""
    commit = _project(tmp_path)
    detected = _build(tmp_path, make_app)
    toml = tmp_path / "docs" / "ubproject.toml"
    toml.write_text(
        toml.read_text(encoding="utf-8") + _git_root(".."), encoding="utf-8"
    )
    configured = _build(tmp_path, make_app)

    # (a second application in one test re-registers Sphinx's nodes, and says so)
    assert [w for w in build_warnings(configured) if "already registered" not in w] == [
        DANGLING
    ]
    assert _refs(configured) == _refs(detected)
    assert _refs(configured)["REQ_001"] == [_url(commit, 1), _url(commit, 3)]
    assert _records(configured) == _records(detected)
    assert project_roots(
        configured.confdir, CodeLinksConfig.from_sphinx(configured.config)
    ) == {"src": tmp_path.resolve().as_posix()}


# -- a file that resolves to outside src_dir -----------------------------------------


@pytest.mark.parametrize(
    "urls",
    [
        pytest.param(LOCAL_ONLY, id="local"),
        pytest.param(REMOTE_ONLY, id="remote"),
        pytest.param(None, id="both"),
    ],
)
def test_a_file_link_out_of_src_dir_is_not_traced(
    tmp_path: Path, make_app: _MakeApp, urls: tuple[str, str] | None
) -> None:
    """``src/ext_link.cpp`` -> ``outside/ext.cpp``: the build succeeds, the file is
    neither traced nor referenced, and one warning names the link."""
    _project(tmp_path, toml_replace=urls, files={"outside/ext.cpp": OUTSIDE_SOURCE})
    _link_out(tmp_path, "src/ext_link.cpp", "outside/ext.cpp")
    app = _build(tmp_path, make_app)

    root = tmp_path.resolve()
    assert build_warnings(app) == [
        _outside_warning(
            root / "src" / "ext_link.cpp", root / "outside" / "ext.cpp", root / "src"
        ),
        DANGLING,
    ]
    assert "IMPL_OUTSIDE" not in _json(app)["needs"]
    assert {ref.path for ref in _records(app)} == {"src/refs.cpp"}


def test_a_link_out_is_warned_once_when_its_scope_is_walked_again(
    tmp_path: Path, make_app: _MakeApp
) -> None:
    """A file added to the scope re-reads ``index``: the scope is walked twice in that
    build (the fingerprint, then the directive), and the link is warned once."""
    _project(tmp_path, files={"outside/ext.cpp": OUTSIDE_SOURCE})
    _link_out(tmp_path, "src/ext_link.cpp", "outside/ext.cpp")
    _build(tmp_path, make_app)
    (tmp_path / "src" / "added.cpp").write_text(
        "// @need-ids: REQ_001\n", encoding="utf-8"
    )
    app = _build(tmp_path, make_app, freshenv=False)

    outside = [w for w in build_warnings(app) if "codelinks.outside_src_dir" in w]
    assert len(outside) == 1, build_warnings(app)
    assert "IMPL_OUTSIDE" not in _json(app)["needs"]


def test_a_followed_directory_link_out_of_src_dir_traces_none_of_its_files(
    tmp_path: Path, make_app: _MakeApp
) -> None:
    """``follow_links = true`` and ``src/dirlink`` -> ``outside/odir``: each file
    below the link is warned once, by its path through the link, and none is traced."""
    _project(
        tmp_path,
        toml_replace=(
            'comment_type = "cpp"',
            'comment_type = "cpp"\nfollow_links = true',
        ),
        files={
            "outside/odir/one.cpp": OUTSIDE_SOURCE,
            "outside/odir/two.cpp": "// @other outside need, IMPL_OUTSIDE_2\n",
        },
    )
    _link_out(tmp_path, "src/dirlink", "outside/odir", directory=True)
    app = _build(tmp_path, make_app)

    root = tmp_path.resolve()
    outside = sorted(w for w in build_warnings(app) if "outside_src_dir" in w)
    assert outside == [
        _outside_warning(
            root / "src" / "dirlink" / name,
            root / "outside" / "odir" / name,
            root / "src",
        )
        for name in ("one.cpp", "two.cpp")
    ]
    needs = _json(app)["needs"]
    assert "IMPL_OUTSIDE" not in needs
    assert "IMPL_OUTSIDE_2" not in needs
    assert {ref.path for ref in _records(app)} == {"src/refs.cpp"}


def test_a_file_scope_naming_a_link_out_of_src_dir_traces_nothing(
    tmp_path: Path, make_app: _MakeApp
) -> None:
    """``:file: ext_link.cpp`` names an existing file outside ``src_dir``: the scope
    is empty, the link is warned, and the build goes on."""
    file_scope = ".. src-trace::\n   :project: src\n   :file: ext_link.cpp\n"
    _project(
        tmp_path,
        files={
            "outside/ext.cpp": OUTSIDE_SOURCE,
            "docs/index.rst": INDEX.replace(DIRECTIVE, file_scope),
        },
    )
    _link_out(tmp_path, "src/ext_link.cpp", "outside/ext.cpp")
    app = _build(tmp_path, make_app)

    root = tmp_path.resolve()
    assert build_warnings(app) == [
        _outside_warning(
            root / "src" / "ext_link.cpp", root / "outside" / "ext.cpp", root / "src"
        )
    ]
    assert "IMPL_OUTSIDE" not in _json(app)["needs"]
    assert _records(app) == []


def test_a_config_only_project_skips_a_link_out_and_attaches_the_rest(
    tmp_path: Path, make_app: _MakeApp
) -> None:
    """No directive traces ``src``: the configuration pass walks it through the same
    discovery, warns about the link, and attaches every other reference."""
    commit = _project(
        tmp_path,
        files={
            "outside/ext.cpp": OUTSIDE_SOURCE,
            "docs/index.rst": INDEX.replace(DIRECTIVE, ""),
        },
    )
    _link_out(tmp_path, "src/ext_link.cpp", "outside/ext.cpp")
    app = _build(tmp_path, make_app)

    root = tmp_path.resolve()
    assert build_warnings(app) == [
        _outside_warning(
            root / "src" / "ext_link.cpp", root / "outside" / "ext.cpp", root / "src"
        ),
        DANGLING,
    ]
    refs = _refs(app)
    assert refs["REQ_001"] == [_url(commit, 1), _url(commit, 3)]
    assert refs["REQ_002"] == [_url(commit, 3)]


def test_the_cli_discover_lists_no_file_outside_src_dir(tmp_path: Path) -> None:
    """``codelinks discover`` lists the files inside and warns on stderr."""
    (tmp_path / "src").mkdir()
    (tmp_path / "outside").mkdir()
    (tmp_path / "src" / "a.cpp").write_text("// a\n", encoding="utf-8")
    (tmp_path / "outside" / "ext.cpp").write_text("// ext\n", encoding="utf-8")
    _link_out(tmp_path, "src/ext_link.cpp", "outside/ext.cpp")

    result = CliRunner().invoke(
        cli, ["discover", str(tmp_path / "src"), "--no-gitignore"]
    )

    assert result.exit_code == 0, result.output
    root = tmp_path.resolve()
    assert result.stdout.splitlines() == [
        "1 files discovered",
        str(root / "src" / "a.cpp"),
    ]
    stderr = re.sub(r"\x1b\[[0-9;?]*[A-Za-z]|\s+", "", result.stderr)
    assert (
        f"{(root / 'src' / 'ext_link.cpp').as_posix()}resolvesto"
        f"{(root / 'outside' / 'ext.cpp').as_posix()},outsidesrc_dir"
        f"{(root / 'src').as_posix()}:nottraced"
    ) in stderr


def test_a_link_leaving_a_directory_scope_but_not_src_dir_is_traced(
    tmp_path: Path,
) -> None:
    """The rule names the PROJECT's ``src_dir``, not the scope's directory: a link in
    ``:directory: a`` to ``b/x.cpp`` below the same ``src_dir`` is found, as it was."""
    src = tmp_path / "src"
    (src / "a").mkdir(parents=True)
    (src / "b").mkdir()
    (src / "b" / "x.cpp").write_text("// x\n", encoding="utf-8")
    _link_out(tmp_path, "src/a/x_link.cpp", "src/b/x.cpp")
    base = SourceDiscoverConfig(src_dir=src, gitignore=False)

    found = discover_scope(src.resolve(), base, "directory", "a", exclude=())

    assert found == [(src / "b" / "x.cpp").resolve()]


@pytest.mark.parametrize(
    ("flavour", "path", "directory", "expected"),
    [
        (posixpath, "/src2/x.cpp", "/src", False),
        (posixpath, "/src/x.cpp", "/src", True),
        (posixpath, "/src/sub/x.cpp", "/src", True),
        (posixpath, "/src", "/src", False),
        (posixpath, "/x.cpp", "/", True),
        (posixpath, "/SRC/x.cpp", "/src", False),
        (ntpath, "C:\\src2\\x.cpp", "C:\\src", False),
        (ntpath, "c:\\SRC\\x.cpp", "C:\\src", True),
        (ntpath, "C:\\x.cpp", "C:\\", True),
        (ntpath, "\\\\server\\share\\src\\x.cpp", "\\\\server\\share\\src", True),
        (ntpath, "C:/src/x.cpp", "C:\\src", True),
        (ntpath, "D:\\src\\x.cpp", "C:\\src", False),
    ],
)
def test_lies_within(
    monkeypatch: pytest.MonkeyPatch,
    flavour: Any,
    path: str,
    directory: str,
    expected: bool,
) -> None:
    """Below the directory, never beside it (``src2`` is not below ``src``), with the
    platform's case folding; a path equal to the directory is no file below it."""
    monkeypatch.setattr(source_discover, "os", SimpleNamespace(path=flavour))
    pure = PureWindowsPath if flavour is ntpath else PurePosixPath

    assert source_discover.lies_within(pure(path), pure(directory)) is expected


def _repository(root: Path, remote: str) -> str:
    """Make ``root`` a repository with ``remote`` as ``origin``; return its commit."""
    git = ["git", "-c", "user.name=t", "-c", "user.email=t@t"]
    git += ["-c", "commit.gpgsign=false"]
    root.mkdir(parents=True, exist_ok=True)
    for args in (
        ["init", "--quiet"],
        ["remote", "add", "origin", remote],
        ["commit", "--quiet", "--allow-empty", "-m", "init"],
    ):
        subprocess.run([*git, *args], cwd=root, check=True, capture_output=True)
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


@pytest.mark.parametrize(
    ("git_root", "problem"),
    [
        pytest.param("../other", "does not contain src_dir {src}", id="sibling"),
        pytest.param("../missing", "does not exist", id="missing"),
    ],
)
def test_the_cli_analyse_ignores_a_git_root_that_does_not_contain_src_dir(
    tmp_path: Path, git_root: str, problem: str
) -> None:
    """``codelinks analyse`` applies the build's rule: one warning on stderr, and the
    remote URLs formed below the repository detected from ``src_dir``."""
    project = tmp_path / "proj"
    (project / "src").mkdir(parents=True)
    (project / "src" / "a.cpp").write_text(
        "// @need-ids: REQ_1\nvoid f() {}\n", encoding="utf-8"
    )
    (project / "cl.toml").write_text(
        "[codelinks.projects.p.source_discover]\n"
        'src_dir = "src"\ncomment_type = "cpp"\ngitignore = false\n'
        "[codelinks.projects.p.analyse]\n"
        f'git_root = "{git_root}"\n',
        encoding="utf-8",
    )
    commit = _repository(project, "https://github.com/example/demo.git")
    _repository(tmp_path / "other", "https://github.com/example/other.git")
    out = tmp_path / "out"
    out.mkdir()

    result = CliRunner().invoke(
        cli, ["analyse", str(project / "cl.toml"), "--outdir", str(out)]
    )

    assert result.exit_code == 0, result.output
    root = tmp_path.resolve()
    src = (root / "proj" / "src").as_posix()
    named = (root / git_root.removeprefix("../")).as_posix()
    expected = (
        f"project 'p': git_root {named} {problem.format(src=src)}; it is ignored, "
        "and the repository root is detected from src_dir instead"
    )
    stderr = re.sub(r"\x1b\[[0-9;?]*[A-Za-z]|\s+", "", result.stderr)
    assert re.sub(r"\s+", "", expected) in stderr
    markers = json.loads((out / "marked_content.json").read_text(encoding="utf-8"))
    assert [marker["remote_url"] for marker in markers["p"]] == [
        f"https://github.com/example/demo/blob/{commit}/src/a.cpp#L1"
    ]


def test_git_root_problem(tmp_path: Path) -> None:
    """The one check both the build and ``codelinks analyse`` apply, row by row."""
    src = tmp_path / "repo" / "src"
    src.mkdir(parents=True)
    (tmp_path / "file").write_text("", encoding="utf-8")
    (tmp_path / "other").mkdir()
    root = tmp_path.resolve()
    src = src.resolve()

    assert git_root_problem(root / "repo", src) is None
    assert git_root_problem(src, src) is None
    assert git_root_problem(root, src) is None
    assert git_root_problem(root / "missing", src) == (
        f"git_root {(root / 'missing').as_posix()} does not exist"
    )
    assert git_root_problem(root / "file", src) == (
        f"git_root {(root / 'file').as_posix()} is not a directory"
    )
    assert git_root_problem(root / "other", src) == (
        f"git_root {(root / 'other').as_posix()} does not contain src_dir "
        f"{src.as_posix()}"
    )
