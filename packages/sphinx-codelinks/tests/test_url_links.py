# @Test suite for the URL fields' string links, TEST_URL_LINKS_1, test, [IMPL_URL_LINKS_1]
"""The ``local-url`` / ``remote-url`` string links, registered at ``config-inited``.

The directive used to write them into the configuration at read time, which a ``-j N``
worker never hands back, which changed the configuration on every build, and which let
the last project read decide every need's remote link.
"""

import json
import re
import subprocess
from collections.abc import Callable
from pathlib import Path, PureWindowsPath
from types import SimpleNamespace

import pytest
import sphinx
from sphinx.testing.util import SphinxTestApp
from sphinx.util.parallel import parallel_available

from sphinx_codelinks.sphinx_extension.directives.src_trace import (
    generate_remote_url,
    generate_str_link_name,
)
from sphinx_codelinks.sphinx_extension.string_links import url_string_link
from sphinx_needs.config import NeedsSphinxConfig
from sphinx_needs.string_links import compiled_string_links
from sphinx_needs_testkit import assert_no_warnings, build_warnings

GITHUB = "https://github.com/example/demo/blob/{commit}/{path}#L{line}"
GITLAB = "https://gitlab.example.com/demo/-/blob/{commit}/{path}?ref=b#L{line}"
GITWEB = "https://git.example.com/?p=demo.git;a=blob;f={path};hb={commit}#l{line}"

#: Sphinx 8 renders a warning's ``[type.subtype]`` itself; 7.4 does not
_SHOWS_WARNING_TYPES = sphinx.version_info >= (8,)

#: a conf.py ``setup`` recording ``needs_string_links`` just before Sphinx-Needs
#: compiles them (its listener is at priority 551)
_PROBE = """
def setup(app):
    def probe(app, config):
        app._codelinks_probe = dict(config.needs_string_links)
    app.connect("config-inited", probe, priority=550)
"""


def _project(
    root: Path,
    *,
    patterns: dict[str, str],
    pages: int = 0,
    conf_extra: str = "",
    with_id: bool = True,
) -> str:
    """A git repository with one source directory per project and a docs directory.

    ``index`` traces the first project and ``later`` the second (if any); ``pages``
    more documents make a ``-j 2`` read genuinely parallel. ``with_id=False`` drops
    ``id`` from the one-line style, so each need's id is generated. Returns the commit.
    """
    docs = root / "docs"
    docs.mkdir()
    toml = ["[codelinks]", "set_local_url = true", "set_remote_url = true", ""]
    for index, (name, pattern) in enumerate(patterns.items()):
        src = root / f"src{name}"
        src.mkdir()
        marker = f"need in {name}" + (f", IMPL_{name.upper()}" if with_id else "")
        (src / f"{name}.cpp").write_text(
            "int x = 0;\n" * index + f"// [[{marker}]]\n", encoding="utf-8"
        )
        toml += [
            f"[codelinks.projects.{name}]",
            f'remote_url_pattern = "{pattern}"',
            f"[codelinks.projects.{name}.source_discover]",
            f'src_dir = "../src{name}"',
            'comment_type = "cpp"',
            f"[codelinks.projects.{name}.analyse.oneline_comment_style]",
            'start_sequence = "[["',
            'end_sequence = "]]"',
            'needs_fields = [{ name = "title" }, '
            + ('{ name = "id" }, ' if with_id else "")
            + '{ name = "type", default = "impl" }]',
            "",
        ]
    (docs / "ubproject.toml").write_text("\n".join(toml), encoding="utf-8")
    (docs / "conf.py").write_text(
        "extensions = ['sphinx_needs', 'sphinx_codelinks']\n"
        "exclude_patterns = ['_build']\n"
        "needs_build_json = True\n" + conf_extra,
        encoding="utf-8",
    )
    names = list(patterns)
    toctree = ".. toctree::\n   :glob:\n\n   *\n\n" if pages or len(names) > 1 else ""
    (docs / "index.rst").write_text(
        f"Index\n=====\n\n{toctree}.. src-trace::\n   :project: {names[0]}\n",
        encoding="utf-8",
    )
    if len(names) > 1:
        (docs / "later.rst").write_text(
            f"Later\n=====\n\n.. src-trace::\n   :project: {names[1]}\n",
            encoding="utf-8",
        )
    for page in range(pages):
        (docs / f"page{page}.rst").write_text(
            f"Page {page}\n=======\n\ntext\n", encoding="utf-8"
        )
    git = ["git", "-c", "user.name=t", "-c", "user.email=t@t"]
    git += ["-c", "commit.gpgsign=false"]
    subprocess.run([*git, "init", "--quiet"], cwd=root, check=True)
    subprocess.run(
        [*git, "remote", "add", "origin", "https://github.com/example/demo.git"],
        cwd=root,
        check=True,
    )
    subprocess.run([*git, "add", "-A"], cwd=root, check=True)
    subprocess.run([*git, "commit", "--quiet", "-m", "init"], cwd=root, check=True)
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _card_links(html: str, field: str) -> list[str | None]:
    """The href in each card's ``field`` row, or ``None`` for a row of plain text."""
    rows = re.findall(
        rf'needs_{re.escape(field)}"><span class="needs_label">[^<]*</span>'
        r'<span class="needs_data">(.*?)</span></span>',
        html,
        re.S,
    )
    hrefs: list[str | None] = []
    for row in rows:
        found = re.search(r'href="([^"]*)"', row)
        hrefs.append(found.group(1) if found else None)
    return hrefs


def _needs(app: SphinxTestApp) -> dict[str, dict[str, object]]:
    data = json.loads(Path(app.outdir, "needs.json").read_text(encoding="utf-8"))
    return data["versions"][data["current_version"]]["needs"]


#: a one-line need at line 7, as ``_line_span`` reads it
_NEED_AT_7 = SimpleNamespace(
    source_map={"start": {"row": 6, "column": 0}, "end": {"row": 6, "column": 0}}
)


def test_remote_url_path_is_posix_for_windows_paths() -> None:
    """A URL path is POSIX: built from Windows paths (``str()`` would give
    ``srca\\a.cpp``), the filled-in pattern still holds ``srca/a.cpp``."""
    out = PureWindowsPath("C:/docs/_build/html")
    url = generate_remote_url(
        _NEED_AT_7,  # ty: ignore[invalid-argument-type]
        out / "srca" / "a.cpp",  # ty: ignore[invalid-argument-type]
        {
            "remote_src_dir": PureWindowsPath("srca"),
            "target_dir": out / "srca",
        },  # ty: ignore[invalid-argument-type]
        GITHUB,
        "a" * 40,
    )
    assert url == GITHUB.format(commit="a" * 40, path="srca/a.cpp", line=7)
    assert "\\" not in url


def test_local_url_value_is_posix_for_windows_paths() -> None:
    """The local value becomes the link's href (``<value>.html#L-<line>``): POSIX too."""
    value = generate_str_link_name(
        _NEED_AT_7,  # ty: ignore[invalid-argument-type]
        PureWindowsPath("..", "srca", "a.cpp"),  # ty: ignore[invalid-argument-type]
    )
    assert value == "../srca/a.cpp#L7"


@pytest.mark.parametrize(
    ("url", "name"),
    [
        pytest.param(
            "https://github.com/o/r/blob/" + "a" * 40 + "/src/x.cpp#L3",
            "src/x.cpp#L3",
            id="github",
        ),
        pytest.param(
            "https://gitlab.com/o/r/-/blob/" + "0123456789" * 4 + "/a/b.c#L10-L12",
            "a/b.c#L10-L12",
            id="gitlab-span",
        ),
        pytest.param(
            "https://bitbucket.org/o/r/src/" + "f" * 64 + "/x.py#lines-2",
            "x.py#lines-2",
            id="bitbucket-sha256",
        ),
        pytest.param(
            "https://example.com/src/main.py#L1",
            "https://example.com/src/main.py#L1",
            id="no-commit-falls-back-to-the-url",
        ),
        pytest.param(
            "https://github.com/cafe1234/r/blob/None/x.cpp#L1",
            "https://github.com/cafe1234/r/blob/None/x.cpp#L1",
            id="no-git-rev-falls-back-to-the-url",
        ),
        pytest.param("foo", None, id="not-a-url"),
        pytest.param("srca/a.cpp#L7", None, id="old-fragment-shape"),
        pytest.param("javascript:alert(1)", None, id="scheme-without-slashes"),
    ],
)
def test_url_string_link_names_the_location_after_the_commit(
    url: str, name: str | None
) -> None:
    """The identity link targets the URL itself and is named by its ``path#Lline``
    tail -- the part after a full commit hash -- or by the URL when there is none. A
    value with no ``scheme://`` is not a URL: no match, so Sphinx-Needs renders text."""
    entry = url_string_link("remote-url")
    match = re.search(entry["regex"], url)
    if name is None:
        assert match is None
        return
    assert match is not None
    groups = match.groupdict()
    assert groups["codelinks_url"] == url
    assert (groups["codelinks_location"] or groups["codelinks_url"]) == name


def test_string_links_are_registered_before_sphinx_needs_compiles_them(
    tmp_path: Path, make_app: Callable[..., SphinxTestApp]
) -> None:
    """Both entries are in ``needs_string_links`` before Sphinx-Needs' listener at
    priority 551 runs, are compiled by it, and render as links on the card."""
    commit = _project(tmp_path, patterns={"a": GITHUB}, conf_extra=_PROBE)
    app = make_app(srcdir=tmp_path / "docs", freshenv=True)

    probe = app._codelinks_probe  # ty: ignore[unresolved-attribute]
    # the URL fields, and the field @need-ids references are attached to
    assert set(probe) == {"local-url", "remote-url", "code_url"}
    assert probe["remote-url"] == url_string_link("remote-url")
    compiled = compiled_string_links(NeedsSphinxConfig(app.config))
    assert {"local-url", "remote-url", "code_url"} <= set(compiled)

    app.build()
    assert_no_warnings(app)
    html = Path(app.outdir, "index.html").read_text(encoding="utf-8")
    url = GITHUB.format(commit=commit, path="srca/a.cpp", line=1)
    assert _card_links(html, "remote-url") == [url]
    assert _card_links(html, "local-url") == ["srca/a.html#L-1"]
    # the local link's name: the value up to the extension, and the line
    assert '<a class="reference external" href="srca/a.html#L-1">srca/a#L1</a>' in html


def test_a_need_without_an_id_links_its_generated_id(
    tmp_path: Path, make_app: Callable[..., SphinxTestApp]
) -> None:
    """A one-line style with no ``id`` field builds with local URLs on (it used to
    raise ``KeyError: 'id'``), and the source page's line links to the generated id."""
    _project(tmp_path, patterns={"a": GITHUB}, with_id=False)
    app = make_app(srcdir=tmp_path / "docs", freshenv=True)
    app.build()

    assert_no_warnings(app)
    (need_id,) = _needs(app)
    source = Path(app.outdir, "srca", "a.html").read_text(encoding="utf-8")
    assert f"index.html#{need_id}" in source
    index = Path(app.outdir, "index.html").read_text(encoding="utf-8")
    assert _card_links(index, "local-url") == ["srca/a.html#L-1"]


def test_user_string_links_are_kept_and_not_mutated(
    tmp_path: Path, make_app: Callable[..., SphinxTestApp]
) -> None:
    """codelinks adds its entries beside the user's, and rebinds the value rather than
    writing into the conf.py dict."""
    user_entry = (
        "{'regex': r'^(?P<v>.+)$', 'link_url': '{{v}}', 'link_name': '{{v}}', "
        "'options': ['title']}"
    )
    _project(
        tmp_path,
        patterns={"a": GITHUB},
        conf_extra=f"USER_LINKS = {{'mine': {user_entry}}}\n"
        "needs_string_links = USER_LINKS\n",
    )
    app = make_app(srcdir=tmp_path / "docs", freshenv=True)

    assert set(app.config.needs_string_links) == {
        "mine",
        "local-url",
        "remote-url",
        "code_url",
    }
    assert set(app.config._raw_config["USER_LINKS"]) == {"mine"}


@pytest.mark.skipif(
    not parallel_available, reason="Sphinx reads sources in parallel on POSIX only"
)
def test_parallel_build_renders_the_url_links(
    tmp_path: Path, make_app: Callable[..., SphinxTestApp]
) -> None:
    """Under ``-j 2`` the card's URL rows are links, exactly as in a serial build."""
    commit = _project(tmp_path, patterns={"a": GITHUB}, pages=7)
    app = make_app(srcdir=tmp_path / "docs", freshenv=True, parallel=2)
    app.build()

    assert_no_warnings(app)
    html = Path(app.outdir, "index.html").read_text(encoding="utf-8")
    url = GITHUB.format(commit=commit, path="srca/a.cpp", line=1)
    assert _card_links(html, "remote-url") == [url]
    assert _card_links(html, "local-url") == ["srca/a.html#L-1"]


def test_each_project_links_with_its_own_remote_url_pattern(
    tmp_path: Path, make_app: Callable[..., SphinxTestApp]
) -> None:
    """Two projects with different patterns: each need's card links with its own
    project's pattern (it used to be the pattern of the project read last, for every
    need), and ``needs.json`` holds that URL."""
    commit = _project(tmp_path, patterns={"a": GITHUB, "b": GITLAB})
    app = make_app(srcdir=tmp_path / "docs", freshenv=True)
    app.build()

    assert_no_warnings(app)
    url_a = GITHUB.format(commit=commit, path="srca/a.cpp", line=1)
    url_b = GITLAB.format(commit=commit, path="srcb/b.cpp", line=2)
    # the cards first: on master these name the last-read-wins defect
    index = Path(app.outdir, "index.html").read_text(encoding="utf-8")
    later = Path(app.outdir, "later.html").read_text(encoding="utf-8")
    assert _card_links(index, "remote-url") == [url_a]
    assert _card_links(later, "remote-url") == [url_b]
    needs = _needs(app)
    assert needs["IMPL_A"]["remote-url"] == url_a
    assert needs["IMPL_B"]["remote-url"] == url_b
    assert needs["IMPL_A"]["local-url"] == "srca/a.cpp#L1"


def test_a_needs_string_links_that_is_not_a_dict_is_left_alone(
    tmp_path: Path, make_app: Callable[..., SphinxTestApp]
) -> None:
    """codelinks adds nothing to a ``needs_string_links`` that is not a dict; the build
    goes on with Sphinx-Needs' own warning about it."""
    _project(tmp_path, patterns={"a": GITHUB}, conf_extra="needs_string_links = []\n")
    app = make_app(srcdir=tmp_path / "docs", freshenv=True)
    app.build()

    warnings = build_warnings(app)
    assert len(warnings) == 1, warnings
    assert "needs_string_links must be a dict, got []." in warnings[0]


def test_rebuild_does_not_change_the_string_links(
    tmp_path: Path, make_app: Callable[..., SphinxTestApp]
) -> None:
    """An unchanged rebuild reads the same ``needs_string_links`` the last build wrote:
    no "configuration has changed" naming it, and the links still render."""
    commit = _project(tmp_path, patterns={"a": GITHUB})
    make_app(srcdir=tmp_path / "docs", freshenv=True).build()
    for _ in range(2):
        app = make_app(srcdir=tmp_path / "docs", freshenv=False)
        app.build()
        status = app._status.getvalue()
        assert "0 added, 0 changed, 0 removed" in status
        assert "needs_string_links" not in status

    html = Path(app.outdir, "index.html").read_text(encoding="utf-8")
    url = GITHUB.format(commit=commit, path="srca/a.cpp", line=1)
    assert _card_links(html, "remote-url") == [url]


@pytest.mark.parametrize(
    "pattern",
    [
        pytest.param(GITWEB, id="semicolon"),
        pytest.param("https://example.com/{commit}/{path},view#L{line}", id="comma"),
    ],
)
def test_pattern_with_a_separator_warns(
    tmp_path: Path, make_app: Callable[..., SphinxTestApp], pattern: str
) -> None:
    """Sphinx-Needs splits a string-linked value on ``,`` and ``;``: a pattern holding
    either cannot render as one link, and the configuration check says so."""
    _project(tmp_path, patterns={"a": pattern})
    app = make_app(srcdir=tmp_path / "docs", freshenv=True)
    app.build()

    suffix = " [codelinks.remote_url_pattern]" if _SHOWS_WARNING_TYPES else ""
    assert build_warnings(app) == [
        f"WARNING: Project 'a': remote_url_pattern {pattern!r} contains ',' or ';'. "
        "Sphinx-Needs splits string-linked values on ',' and ';', so this pattern's "
        f"links will not render as one link.{suffix}"
    ]


def test_pattern_separator_warning_needs_remote_urls(
    tmp_path: Path, make_app: Callable[..., SphinxTestApp]
) -> None:
    """With remote URLs off the pattern is never filled in: no warning."""
    _project(tmp_path, patterns={"a": GITWEB})
    toml = tmp_path / "docs" / "ubproject.toml"
    toml.write_text(
        toml.read_text(encoding="utf-8").replace(
            "set_remote_url = true", "set_remote_url = false"
        ),
        encoding="utf-8",
    )
    app = make_app(srcdir=tmp_path / "docs", freshenv=True)
    app.build()

    assert_no_warnings(app)


def test_pattern_separator_warning_is_suppressible(
    tmp_path: Path, make_app: Callable[..., SphinxTestApp]
) -> None:
    _project(
        tmp_path,
        patterns={"a": GITWEB},
        conf_extra='suppress_warnings = ["codelinks.remote_url_pattern"]\n',
    )
    app = make_app(srcdir=tmp_path / "docs", freshenv=True)
    app.build()

    assert_no_warnings(app)
