# @Test suite for need id references attached during the build, TEST_NEED_ID_REFS_1, test, [IMPL_LNK_1]
"""The references of ``@need-ids:`` markers, attached to the needs they name.

Every case builds a copy of ``doc_test/need_id_refs`` made into a git repository, so the
remote URLs carry a real commit. ``src/refs.cpp`` references ``REQ_001`` (lines 1 and 3),
``REQ_002`` (line 3), the unknown ``NOSUCH_ID`` (line 5) and ``REQ_003`` (line 7);
``REQ_001`` is defined in ``index`` before the ``src-trace`` directive, ``REQ_002`` in
``later`` -- read after it -- and ``REQ_003`` in ``sub/deep``. ``SPEC_001`` is referenced
by nothing.
"""

import codecs
import json
import os
import re
import shutil
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
import sphinx
from sphinx.testing.util import SphinxTestApp
from sphinx.util.console import strip_colors
from sphinx.util.parallel import parallel_available

from sphinx_codelinks.sphinx_extension.need_id_refs import need_id_refs_store
from sphinx_needs_testkit import (
    assert_no_warnings,
    build_warnings,
    sphinx_build_command,
)

FIXTURE = Path(__file__).parent / "doc_test" / "need_id_refs"
GITHUB = "https://github.com/example/demo/blob/{commit}/{path}#L{line}"

#: Sphinx 8 renders a warning's ``[type.subtype]`` itself; 7.4 does not
_SHOWS_WARNING_TYPES = sphinx.version_info >= (8,)

_MakeApp = Callable[..., SphinxTestApp]


def _git(root: Path, *args: str) -> str:
    command = ["git", "-c", "user.name=t", "-c", "user.email=t@t"]
    command += ["-c", "commit.gpgsign=false", *args]
    return subprocess.run(
        command, cwd=root, check=True, capture_output=True, text=True
    ).stdout.strip()


def _project(
    root: Path,
    *,
    toml_extra: str = "",
    toml_replace: tuple[str, str] | None = None,
    files: dict[str, str] | None = None,
    append: dict[str, str] | None = None,
    git: bool = True,
) -> str:
    """Copy the fixture into ``root``, change it, commit it; return the commit (or
    ``""`` with ``git=False``: no repository at all)."""
    shutil.copytree(FIXTURE, root, dirs_exist_ok=True)
    toml = root / "docs" / "ubproject.toml"
    text = toml.read_text(encoding="utf-8")
    if toml_replace is not None:
        assert toml_replace[0] in text
        text = text.replace(*toml_replace)
    toml.write_text(text + toml_extra, encoding="utf-8")
    for relative, content in (files or {}).items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    for relative, content in (append or {}).items():
        path = root / relative
        path.write_text(path.read_text(encoding="utf-8") + content, encoding="utf-8")
    if not git:
        return ""
    _git(root, "init", "--quiet")
    _git(root, "remote", "add", "origin", "https://github.com/example/demo.git")
    _git(root, "add", "-A")
    _git(root, "commit", "--quiet", "-m", "init")
    return _git(root, "rev-parse", "HEAD")


def _build(root: Path, make_app: _MakeApp, **kwargs: Any) -> SphinxTestApp:
    kwargs.setdefault("freshenv", True)
    app = make_app(srcdir=root / "docs", **kwargs)
    app.build()
    return app


def _json(app: SphinxTestApp) -> dict[str, Any]:
    data = json.loads(Path(app.outdir, "needs.json").read_text(encoding="utf-8"))
    return data["versions"][data["current_version"]]


def _refs(app: SphinxTestApp) -> dict[str, Any]:
    """Each need's ``code_url``, or ``"<absent>"`` when needs.json has no such key."""
    needs = _json(app)["needs"]
    return {
        need_id: need.get("code_url", "<absent>") for need_id, need in needs.items()
    }


def _url(commit: str, line: int, path: str = "src/refs.cpp") -> str:
    return GITHUB.format(commit=commit, path=path, line=line)


def _card_links(app: SphinxTestApp, page: str) -> list[list[tuple[str, str]]]:
    """Per card on ``page``, the ``(href, name)`` of each link in its ``code_url`` row."""
    html = Path(app.outdir, page).read_text(encoding="utf-8")
    rows = re.findall(r'<span class="needs_code_url">(.*?)</div>', html, re.S)
    return [re.findall(r'href="([^"]*)">([^<]*)</a>', row) for row in rows]


def _warning(location: str, message: str) -> str:
    suffix = " [codelinks.need_id_ref]" if _SHOWS_WARNING_TYPES else ""
    return f"{location}: WARNING: {message}{suffix}"


DANGLING = _warning("src/refs.cpp:5", "@need-ids reference to unknown need 'NOSUCH_ID'")


def test_references_attach_to_needs_in_any_document(
    tmp_path: Path, make_app: _MakeApp
) -> None:
    """Same document, a later one and a nested one alike; N references give N
    entries, in line order; an unreferenced need carries nothing; nothing is
    marked as modified; ``needs_schema`` declares the field as a list."""
    commit = _project(tmp_path)
    app = _build(tmp_path, make_app)

    assert build_warnings(app) == [DANGLING]
    refs = _refs(app)
    assert refs["REQ_001"] == [_url(commit, 1), _url(commit, 3)]
    assert refs["REQ_002"] == [_url(commit, 3)]
    assert refs["REQ_003"] == [_url(commit, 7)]
    assert refs["SPEC_001"] is None
    needs = _json(app)["needs"]
    assert not any(need["is_modified"] for need in needs.values())
    schema = _json(app)["needs_schema"]["properties"]["code_url"]
    assert schema["type"] == ["array", "null"]
    assert schema["items"] == {"type": "string"}
    assert schema["default"] is None

    assert _card_links(app, "index.html") == [
        [
            (_url(commit, 1), "src/refs.cpp#L1"),
            (_url(commit, 3), "src/refs.cpp#L3"),
        ]
    ]
    assert _card_links(app, "later.html") == [[(_url(commit, 3), "src/refs.cpp#L3")]]
    # the value is remote, so the reference-only file is neither copied nor paged
    assert not Path(app.outdir, "src").exists()


def test_unknown_id_warns_at_the_source_line(
    tmp_path: Path, make_app: _MakeApp
) -> None:
    _project(tmp_path)
    app = _build(tmp_path, make_app)

    assert build_warnings(app) == [DANGLING]
    status = app._status.getvalue()
    assert "codelinks [src]: 4 references attached, 1 unknown" in status


def test_unknown_id_warning_is_suppressible(tmp_path: Path, make_app: _MakeApp) -> None:
    _project(tmp_path)
    app = _build(
        tmp_path,
        make_app,
        confoverrides={"suppress_warnings": ["codelinks.need_id_ref"]},
    )

    assert_no_warnings(app)
    assert _refs(app)["REQ_002"] is not None


@pytest.mark.skipif(
    not parallel_available, reason="Sphinx reads sources in parallel on POSIX only"
)
def test_parallel_build_attaches_as_a_serial_one(
    tmp_path: Path, make_app: _MakeApp
) -> None:
    """``-j 2`` reads the directive in a worker; its records reach the main process."""
    serial_root = tmp_path / "serial"
    parallel_root = tmp_path / "parallel"
    commit = _project(serial_root)
    _project(parallel_root)
    serial = _build(serial_root, make_app)
    parallel = _build(parallel_root, make_app, parallel=2)
    # the read really was parallel: Sphinx reports chunks, "page1 .. page3"
    status = strip_colors(parallel._status.getvalue())
    assert re.search(r"reading sources\.\.\. \[\s*\d+%\] \S+ \.\. \S+", status)

    def _normalised(app: SphinxTestApp) -> dict[str, Any]:
        own_commit = _git(Path(app.srcdir).parent, "rev-parse", "HEAD")
        text = json.dumps(_refs(app)).replace(own_commit, "<commit>")
        return json.loads(text)

    assert _refs(serial)["REQ_002"] == [_url(commit, 3)]
    assert _normalised(parallel) == _normalised(serial)
    # a second application in one process also re-registers Sphinx' own nodes
    assert [w for w in build_warnings(parallel) if "@need-ids" in w] == [DANGLING]


def test_unchanged_rebuild_keeps_the_references(
    tmp_path: Path, make_app: _MakeApp
) -> None:
    """Nothing is re-read, and the references still attach, from the pickled env."""
    commit = _project(tmp_path)
    _build(tmp_path, make_app)
    app = _build(tmp_path, make_app, freshenv=False)

    assert "0 added, 0 changed, 0 removed" in app._status.getvalue()
    refs = _refs(app)
    assert refs["REQ_001"] == [_url(commit, 1), _url(commit, 3)]
    assert refs["REQ_002"] == [_url(commit, 3)]


def test_source_edit_clears_a_stale_reference(
    tmp_path: Path, make_app: _MakeApp
) -> None:
    """Editing only the source re-reads the hosting document, whose old records are
    dropped: ``REQ_002`` loses the reference the edit removed."""
    commit = _project(tmp_path)
    _build(tmp_path, make_app)
    source = tmp_path / "src" / "refs.cpp"
    source.write_text(
        source.read_text(encoding="utf-8").replace(
            "@need-ids: REQ_002, REQ_001", "@need-ids: REQ_001"
        ),
        encoding="utf-8",
    )
    later = source.stat().st_mtime + 10
    os.utime(source, (later, later))
    app = _build(tmp_path, make_app, freshenv=False)

    assert "0 added, 1 changed, 0 removed" in app._status.getvalue()
    refs = _refs(app)
    assert refs["REQ_001"] == [_url(commit, 1), _url(commit, 3)]
    assert refs["REQ_002"] is None


def test_user_needextend_of_the_field_wins(tmp_path: Path, make_app: _MakeApp) -> None:
    """The attach runs before ``needextend`` is applied: a user's extend overrides it."""
    commit = _project(
        tmp_path,
        files={
            "docs/override.rst": (
                "Override\n========\n\n"
                ".. needextend:: REQ_002\n   :code_url: user-override\n"
            )
        },
    )
    app = _build(tmp_path, make_app)

    refs = _refs(app)
    assert refs["REQ_002"] == ["user-override"]
    assert refs["REQ_001"] == [_url(commit, 1), _url(commit, 3)]


def test_strict_schema_never_sees_the_field_on_an_unreferenced_need(
    tmp_path: Path, make_app: _MakeApp
) -> None:
    """``SPEC_001`` is validated by a schema with ``unevaluatedProperties: false``:
    the field is unset there, so it is stripped before validation."""
    _project(tmp_path)
    app = _build(
        tmp_path,
        make_app,
        confoverrides={"needs_schema_definitions_from_json": "schemas.json"},
    )

    report = json.loads(
        Path(app.outdir, "schema_violations.json").read_text(encoding="utf-8")
    )
    assert report["validated_needs_count"] >= 1
    assert report["validation_warnings"] == {}
    assert build_warnings(app) == [DANGLING]


def test_overlapping_directives_do_not_double_the_references(
    tmp_path: Path, make_app: _MakeApp
) -> None:
    """A second directive over the same file analyses it again (one walk per
    directive): its records are the same, and each reference is attached once."""
    commit = _project(
        tmp_path,
        append={
            "docs/later.rst": "\n.. src-trace::\n   :project: src\n   :file: refs.cpp\n"
        },
    )
    app = _build(tmp_path, make_app)

    refs = _refs(app)
    assert refs["REQ_001"] == [_url(commit, 1), _url(commit, 3)]
    assert refs["REQ_002"] == [_url(commit, 3)]
    assert build_warnings(app) == [DANGLING]


def test_two_projects_naming_one_field_share_its_list(
    tmp_path: Path, make_app: _MakeApp
) -> None:
    gitlab = "https://gitlab.example.com/demo/-/blob/{commit}/{path}#L{line}"
    commit = _project(
        tmp_path,
        toml_extra=(
            "\n[codelinks.projects.two]\n"
            f'remote_url_pattern = "{gitlab}"\n'
            "[codelinks.projects.two.source_discover]\n"
            'src_dir = "../src2"\n'
            'comment_type = "cpp"\n'
        ),
        files={"src2/more.cpp": "// @need-ids: REQ_001\nvoid more() {}\n"},
        append={"docs/later.rst": "\n.. src-trace::\n   :project: two\n"},
    )
    app = _build(tmp_path, make_app)

    assert _refs(app)["REQ_001"] == [
        _url(commit, 1),
        _url(commit, 3),
        gitlab.format(commit=commit, path="src2/more.cpp", line=1),
    ]
    assert "codelinks [two]: 1 reference attached, 0 unknown" in app._status.getvalue()


@pytest.mark.parametrize("remote", [True, False], ids=["remote-on", "local-only"])
def test_empty_ref_url_field_attaches_nothing(
    tmp_path: Path, make_app: _MakeApp, remote: bool
) -> None:
    """``ref_url_field = ""`` (ubCode's off switch): no field, no attach, no warning --
    and the directive collects nothing and copies nothing for the project."""
    _project(
        tmp_path,
        toml_replace=(
            "[codelinks.projects.src]\n",
            '[codelinks.projects.src]\nref_url_field = ""\n',
        ),
    )
    if not remote:
        toml = tmp_path / "docs" / "ubproject.toml"
        toml.write_text(
            toml.read_text(encoding="utf-8").replace(
                "set_remote_url = true", "set_remote_url = false"
            ),
            encoding="utf-8",
        )
    app = _build(tmp_path, make_app)

    assert need_id_refs_store(app.env) == {}
    assert not Path(app.outdir, "src").exists()
    assert_no_warnings(app)
    assert "code_url" not in _json(app)["needs_schema"]["properties"]
    assert set(_refs(app).values()) == {"<absent>"}
    assert "code_url" not in app.config.needs_string_links


def test_local_urls_when_remote_urls_are_off(
    tmp_path: Path, make_app: _MakeApp
) -> None:
    """Without remote URLs an entry is the local one, relative to the need's own
    document, and links to the source page generated beside the copied file."""
    _project(tmp_path, toml_replace=("set_remote_url = true", "set_remote_url = false"))
    app = _build(tmp_path, make_app)

    refs = _refs(app)
    assert refs["REQ_001"] == ["src/refs.cpp#L1", "src/refs.cpp#L3"]
    assert refs["REQ_003"] == ["../src/refs.cpp#L7"]
    assert _card_links(app, "index.html") == [
        [
            ("src/refs.html#L-1", "src/refs.cpp#L1"),
            ("src/refs.html#L-3", "src/refs.cpp#L3"),
        ]
    ]
    assert _card_links(app, "sub/deep.html") == [
        [("../src/refs.html#L-7", "../src/refs.cpp#L7")]
    ]
    page = Path(app.outdir, "src", "refs.html").read_text(encoding="utf-8")
    assert 'id="L-7"' in page


@pytest.mark.parametrize("local", [True, False], ids=["local-on", "local-off"])
def test_no_remote_url_without_a_git_root(
    tmp_path: Path, make_app: _MakeApp, local: bool
) -> None:
    """Outside a git repository nothing is written as a remote URL (#2045): the
    created need has no ``remote-url``, and a reference falls back to the local link,
    or attaches nothing when local URLs are off. The analysis warns once."""
    _project(
        tmp_path,
        git=False,
        toml_replace=None
        if local
        else ("set_local_url = true", "set_local_url = false"),
        files={"src/impl.cpp": "// @implemented without git, IMPL_NOGIT\n"},
    )
    app = _build(tmp_path, make_app)

    needs = _json(app)["needs"]
    assert needs["IMPL_NOGIT"]["remote-url"] is None
    refs = _refs(app)
    if local:
        assert refs["REQ_001"] == ["src/refs.cpp#L1", "src/refs.cpp#L3"]
    else:
        assert refs["REQ_001"] is None
    records = [ref for refs in need_id_refs_store(app.env).values() for ref in refs]
    assert records and {ref.root for ref in records} == {"src_dir"}
    git_root_warnings = [w for w in build_warnings(app) if "git root is not found" in w]
    assert len(git_root_warnings) == 1, build_warnings(app)
    assert not any("/blob/None" in json.dumps(need) for need in needs.values())


@pytest.mark.parametrize("second", ["aaa", "two"])
def test_two_projects_over_one_file_attach_each_reference_once(
    tmp_path: Path, make_app: _MakeApp, second: str
) -> None:
    """Two projects whose source directories overlap analyse the same file: one entry
    per reference, the FIRST PROJECT BY NAME keeping its URL -- whichever document is
    read first (``aaa`` sorts before ``src`` but is traced in the later document) --
    and the unknown id warned once."""
    gitlab = "https://gitlab.example.com/demo/-/blob/{commit}/{path}#L{line}"
    commit = _project(
        tmp_path,
        toml_extra=(
            f"\n[codelinks.projects.{second}]\n"
            f'remote_url_pattern = "{gitlab}"\n'
            f"[codelinks.projects.{second}.source_discover]\n"
            'src_dir = "../src"\n'
            'comment_type = "cpp"\n'
        ),
        append={"docs/later.rst": f"\n.. src-trace::\n   :project: {second}\n"},
    )
    app = _build(tmp_path, make_app)

    refs = _refs(app)
    if second == "aaa":
        first = [
            gitlab.format(commit=commit, path="src/refs.cpp", line=n) for n in (1, 3)
        ]
    else:
        first = [_url(commit, 1), _url(commit, 3)]
    assert refs["REQ_001"] == first
    assert refs["REQ_002"] == first[1:]
    assert build_warnings(app) == [DANGLING]


def test_two_fields_over_one_file_each_keep_their_list(
    tmp_path: Path, make_app: _MakeApp
) -> None:
    """Two projects over one file naming DIFFERENT fields: each field its own list (two
    declared relations), and one unknown-id warning for the one marker."""
    commit = _project(
        tmp_path,
        toml_extra=(
            "\n[codelinks.projects.mirror]\n"
            'ref_url_field = "test_url"\n'
            f'remote_url_pattern = "{GITHUB}"\n'
            "[codelinks.projects.mirror.source_discover]\n"
            'src_dir = "../src"\n'
            'comment_type = "cpp"\n'
        ),
        append={"docs/later.rst": "\n.. src-trace::\n   :project: mirror\n"},
    )
    app = _build(tmp_path, make_app)

    needs = _json(app)["needs"]
    assert needs["REQ_001"]["code_url"] == [_url(commit, 1), _url(commit, 3)]
    assert needs["REQ_001"]["test_url"] == [_url(commit, 1), _url(commit, 3)]
    assert build_warnings(app) == [DANGLING]


def _two_roots(root: Path, *, git: bool) -> None:
    """Two projects whose files share the relative path but are different files: two
    git repositories (``repoa``, ``repob``), or two plain source directories."""
    docs = root / "docs"
    docs.mkdir(parents=True)
    toml = [
        "[codelinks]",
        "set_local_url = true",
        f"set_remote_url = {str(git).lower()}",
    ]
    for name in ("a", "b"):
        src = root / f"repo{name}" / "src" if git else root / f"src{name}"
        src.mkdir(parents=True)
        (src / "main.cpp").write_text("// @need-ids: REQ_001\n", encoding="utf-8")
        relative = f"../repo{name}/src" if git else f"../src{name}"
        toml += [
            f"[codelinks.projects.{name}]",
            f'remote_url_pattern = "https://github.com/example/repo{name}/blob/'
            '{commit}/{path}#L{line}"',
            f"[codelinks.projects.{name}.source_discover]",
            f'src_dir = "{relative}"',
            'comment_type = "cpp"',
        ]
        if git:
            repo = root / f"repo{name}"
            _git(repo, "init", "--quiet")
            _git(repo, "add", "-A")
            _git(repo, "commit", "--quiet", "-m", "init")
    (docs / "ubproject.toml").write_text("\n".join(toml) + "\n", encoding="utf-8")
    (docs / "conf.py").write_text(
        (FIXTURE / "docs" / "conf.py").read_text(encoding="utf-8"), encoding="utf-8"
    )
    (docs / "index.rst").write_text(
        "Two roots\n=========\n\n.. req:: Cross-cutting\n   :id: REQ_001\n\n"
        ".. src-trace::\n   :project: a\n\n.. src-trace::\n   :project: b\n",
        encoding="utf-8",
    )


@pytest.mark.parametrize("git", [True, False], ids=["two-repositories", "two-src-dirs"])
def test_same_relative_path_under_two_roots_is_two_files(
    tmp_path: Path, make_app: _MakeApp, git: bool
) -> None:
    """``path`` is relative to each project's own root: ``src/main.cpp`` in two
    repositories (or ``main.cpp`` in two source directories) is two files, so both
    references are kept, and both projects report."""
    _two_roots(tmp_path, git=git)
    app = _build(tmp_path, make_app)

    refs = _refs(app)["REQ_001"]
    if git:
        assert [url.split("/blob/")[0] for url in refs] == [
            "https://github.com/example/repoa",
            "https://github.com/example/repob",
        ]
        assert all(url.endswith("/src/main.cpp#L1") for url in refs)
    else:
        assert refs == ["srca/main.cpp#L1", "srcb/main.cpp#L1"]
    status = app._status.getvalue()
    assert "codelinks [a]: 1 reference attached, 0 unknown" in status
    assert "codelinks [b]: 1 reference attached, 0 unknown" in status


def test_no_remote_url_without_a_commit(tmp_path: Path, make_app: _MakeApp) -> None:
    """A repository with no commit yet has no commit for the pattern: no remote URL,
    no ``blob/None`` -- the local link instead (#2045)."""
    _project(
        tmp_path,
        git=False,
        files={"src/impl.cpp": "// @implemented before any commit, IMPL_NOCOMMIT\n"},
    )
    _git(tmp_path, "init", "--quiet")
    _git(tmp_path, "remote", "add", "origin", "https://github.com/example/demo.git")
    app = _build(tmp_path, make_app)

    needs = _json(app)["needs"]
    assert needs["IMPL_NOCOMMIT"]["remote-url"] is None
    assert _refs(app)["REQ_001"] == ["src/refs.cpp#L1", "src/refs.cpp#L3"]
    assert not any("/blob/None" in json.dumps(need) for need in needs.values())


def test_copies_are_byte_identical(tmp_path: Path, make_app: _MakeApp) -> None:
    """With local URLs only, a referenced file and a file with a one-line need are
    copied as bytes -- no codec, no newline translation -- and paged."""
    refs = (FIXTURE / "src" / "refs.cpp").read_text(encoding="utf-8")
    _project(
        tmp_path,
        toml_replace=("set_remote_url = true", "set_remote_url = false"),
        files={
            "src/refs.cpp": (refs + "// café: naïve ✓\n").replace("\n", "\r\n"),
            "src/impl.cpp": "// @Implemented, IMPL_UTF8\r\n// déjà vu\r\n",
        },
    )
    app = _build(tmp_path, make_app)

    for name in ("refs.cpp", "impl.cpp"):
        source = (tmp_path / "src" / name).read_bytes()
        assert Path(app.outdir, "src", name).read_bytes() == source, name
        page = Path(app.outdir, "src", name).with_suffix(".html")
        assert page.exists(), name
    assert "café: naïve ✓" in Path(app.outdir, "src", "refs.html").read_text(
        encoding="utf-8"
    )


_INJECT = """
def setup(app):
    from sphinx_codelinks.analyse.references import NeedIdRef
    from sphinx_codelinks.sphinx_extension.need_id_refs import need_id_refs_store

    def inject(app, env, docnames):
        need_id_refs_store(env)["<pre-analysed>"] = [
            NeedIdRef(need_id=need_id, project="elsewhere", marker="@need-ids:",
                      path="x.cpp", lineno=1, start_column=0, end_column=7,
                      remote_url="https://example.com/x.cpp#L1")
            for need_id in ("REQ_001", "REQ_002")
        ]

    app.connect("env-before-read-docs", inject)
"""


def test_records_of_an_unconfigured_project_warn_once(
    tmp_path: Path, make_app: _MakeApp
) -> None:
    """Records reaching the store for a project this build does not configure (what a
    pre-analysed file could carry) are ignored, with one warning per project."""
    commit = _project(tmp_path, append={"docs/conf.py": _INJECT})
    app = _build(tmp_path, make_app)

    suffix = " [codelinks.need_id_ref]" if _SHOWS_WARNING_TYPES else ""
    ignored = (
        "WARNING: @need-ids records for project 'elsewhere', which this build does not "
        f"configure, were ignored{suffix}"
    )
    assert sorted(build_warnings(app)) == sorted([DANGLING, ignored])
    assert _refs(app)["REQ_001"] == [_url(commit, 1), _url(commit, 3)]


@pytest.mark.parametrize(
    "declaration",
    ['needs_fields = {"code_url": {}}', 'needs_extra_options = ["code_url"]'],
    ids=["needs_fields", "needs_extra_options"],
)
def test_a_user_declaration_of_the_field_names_the_cure(
    tmp_path: Path, make_app: _MakeApp, declaration: str
) -> None:
    """A ``needs_fields`` (or ``needs_extra_options``) entry for the references field
    (the ``write rst`` route's habit) warns with the cause and the cure, beside
    Sphinx-Needs' own duplicate."""
    _project(tmp_path, append={"docs/conf.py": declaration + "\n"})
    app = _build(tmp_path, make_app)

    suffix = " [codelinks.config]" if _SHOWS_WARNING_TYPES else ""
    assert (
        "WARNING: codelinks registers 'code_url' for @need-ids references; remove the "
        f"needs_fields declaration of it, or set ref_url_field{suffix}"
    ) in build_warnings(app)


def test_copies_and_pages_under_an_ascii_locale(tmp_path: Path) -> None:
    """The byte copy and the source page do not depend on the locale's codec.

    The in-process tests run under the suite's (UTF-8) locale, where a decode through the
    locale codec cannot fail; this one builds in a subprocess under the C locale with
    UTF-8 mode and locale coercion off, where it would (``UnicodeDecodeError: 'ascii'``).
    Skipped only where the platform gives that environment a non-ASCII codec."""
    env = {
        **os.environ,
        "LC_ALL": "C",
        "LANG": "C",
        "PYTHONUTF8": "0",
        "PYTHONCOERCECLOCALE": "0",
    }
    env.pop("PYTHONIOENCODING", None)
    probe = subprocess.run(
        [sys.executable, "-c", "import locale; print(locale.getencoding())"],
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    if codecs.lookup(probe.stdout.strip()).name != "ascii":
        pytest.skip(f"the C locale's codec here is {probe.stdout.strip()!r}")
    refs = (FIXTURE / "src" / "refs.cpp").read_text(encoding="utf-8")
    _project(
        tmp_path,
        toml_replace=("set_remote_url = true", "set_remote_url = false"),
        files={"src/refs.cpp": refs + "// café: naïve\n"},
    )
    out = tmp_path / "out"
    result = subprocess.run(
        sphinx_build_command("-b", "html", "-E", "-q", tmp_path / "docs", out),
        env=env,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr.decode("utf-8", "replace")
    source = (tmp_path / "src" / "refs.cpp").read_bytes()
    assert (out / "src" / "refs.cpp").read_bytes() == source
    assert "café: naïve" in (out / "src" / "refs.html").read_text(encoding="utf-8")


def test_a_non_html_build_leaves_no_source_page_pending(
    tmp_path: Path, make_app: _MakeApp
) -> None:
    """The source pages a build registers are generated by the HTML builders only; a
    LaTeX build of a local-only project registers them too, and the next HTML build in
    the same process (an in-process server, a test run) must not inherit them -- its
    pages live in another output directory."""
    _project(
        tmp_path / "a", toml_replace=("set_remote_url = true", "set_remote_url = false")
    )
    _project(tmp_path / "b")
    _build(tmp_path / "a", make_app, buildername="latex")
    app = _build(tmp_path / "b", make_app)

    assert build_warnings(app) == [DANGLING]
