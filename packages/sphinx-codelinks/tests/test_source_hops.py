# @Test suite for the code hop of every need src-trace creates, TEST_SOURCE_HOPS_1, test, [IMPL_LNK_1]
"""Where a need ``src-trace`` creates comes from: its ``code`` hop, then its page.

Every need ``src-trace`` creates, one-line and multi-line, records innermost first the
marker in its source file (a ``code`` hop: the file under the Sphinx source directory,
the marker's 1-based lines, the entity it is attached to, outermost first, and the file's
language) and the page the directive is written on. Its ``lineno`` is the line the
directive is written on, after ``rst_prolog`` and in an included file too. The hops are
provisional and reach no ``needs.json``.
"""

from __future__ import annotations

import io
import json
import os
import pickle
import re
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from sphinx.testing.util import SphinxTestApp
from sphinx.util.console import strip_colors

from sphinx_codelinks.analyse.entity import name_chain
from sphinx_needs.api import NeedItemSource, NeedSourceHop
from sphinx_needs.data import SphinxNeedsData

_MakeApp = Callable[..., SphinxTestApp]

# --- the project ----------------------------------------------------------------------

PY = """\
# @Python file marker, IMPL_PY_FILE, impl

class Shape:
    # @Area of a shape, IMPL_PY_ONE, impl
    def area(self):
        def inner():  # @Inner helper, IMPL_PY_LOCALS, impl
            pass


# @need impl: Python block
# :id: IMPL_PY_MULTI
#
# The body.
# @endneed
def compute():
    pass
"""

#: the same method of the same class, in its class (here) and out of line (below)
CPP_NESTED = """\
namespace ns {
class W {
  public:
    // @In-class f, IMPL_CPP_IN, impl
    void f() {}
};
}  // namespace ns

/**
 * @need impl: C++ block
 * :id: IMPL_CPP_MULTI
 *
 * The body.
 * @endneed
 */
int run() { return 0; }
"""

CPP_OUT = """\
namespace ns {
class W {
  public:
    void f();
};
}  // namespace ns

// @Out-of-line f, IMPL_CPP_OUT, impl
void ns::W::f() {}
"""

C = """\
// @C add, IMPL_C_ONE, impl
int add(int a, int b) { return a + b; }

/*
 * @need impl: C block
 * :id: IMPL_C_MULTI
 *
 * The body.
 * @endneed
 */
int sub(int a, int b) { return a - b; }
"""

#: a file of another suffix, traced by a C++ project (``:file:``): the project's language
FOREIGN = """\
// @Foreign suffix, IMPL_FOREIGN, impl

int helper() { return 1; }
"""

RS = """\
pub trait Shape {
    fn area(&self) -> f64;
}

pub struct Widget;

impl Shape for Widget {
    // @Widget area, IMPL_RS_TRAIT, impl
    fn area(&self) -> f64 {
        1.0
    }
    // @need impl: Rust trait block
    // :id: IMPL_RS_TRAIT_MULTI
    //
    // The body.
    // @endneed
    fn perimeter(&self) -> f64 {
        2.0
    }
}

impl Widget {
    // @need impl: Rust block
    // :id: IMPL_RS_MULTI
    //
    // The body.
    // @endneed
    pub fn new() -> Self {
        Widget
    }
}
"""

TS = """\
export class Greeter {
  // @Greet, IMPL_TS_ONE, impl
  greet(name: string): string {
    return name;
  }
}

/**
 * @need impl: TypeScript block
 * :id: IMPL_TS_MULTI
 *
 * The body.
 * @endneed
 */
export function farewell(): void {}
"""

#: a YAML entry has no name: the hop has a language and no semantic location
YAML = """\
service:
  # @YAML entry, IMPL_YAML_ONE, impl
  port: 8080
  # @need impl: YAML block
  # :id: IMPL_YAML_MULTI
  #
  # The body.
  # @endneed
  host: localhost
"""

#: inside the Sphinx source directory: a path without ``..``
INSIDE = """\
# @Inside the source directory, IMPL_INSIDE, impl
def inside():
    pass
"""

#: CRLF line ends: lines count as they do with LF
CRLF = (
    b"class K:\r\n"
    b"    # @CRLF method, IMPL_CRLF_ONE, impl\r\n"
    b"    def m(self):\r\n"
    b"        pass\r\n"
    b"\r\n"
    b"\r\n"
    b"# @need impl: CRLF block\r\n"
    b"# :id: IMPL_CRLF_MULTI\r\n"
    b"#\r\n"
    b"# The body.\r\n"
    b"# @endneed\r\n"
    b"def g():\r\n"
    b"    pass\r\n"
)

TOML = """\
[codelinks.projects.py.source_discover]
src_dir = "../src/py"
comment_type = "python"

[codelinks.projects.cpp.source_discover]
src_dir = "../src/cpp"
comment_type = "cpp"

[codelinks.projects.rust.source_discover]
src_dir = "../src/rust"
comment_type = "rust"

[codelinks.projects.ts.source_discover]
src_dir = "../src/ts"
comment_type = "ts"

[codelinks.projects.yaml.source_discover]
src_dir = "../src/yaml"
comment_type = "yaml"

[codelinks.projects.inside.source_discover]
src_dir = "code"
comment_type = "python"
""" + "".join(
    f"""
[codelinks.projects.{project}.analyse]
get_oneline_needs = true
get_multiline_needs = true
"""
    for project in ("py", "cpp", "rust", "ts", "yaml", "inside")
)

CONF = """\
extensions = ["sphinx_needs", "sphinx_codelinks"]
exclude_patterns = ["_build"]
needs_build_json = True
"""

INDEX = """\
Hops
====

.. src-trace::
   :project: py

.. src-trace::
   :project: cpp

.. src-trace::
   :project: cpp
   :file: tool.py

Languages
---------

.. src-trace::
   :project: rust

.. src-trace::
   :project: ts

.. src-trace::
   :project: yaml

.. src-trace::
   :project: inside
"""

FILES: dict[str, str | bytes] = {
    "docs/conf.py": CONF,
    "docs/ubproject.toml": TOML,
    "docs/index.rst": INDEX,
    "docs/code/inside.py": INSIDE,
    "src/py/shapes.py": PY,
    "src/py/crlf.py": CRLF,
    "src/cpp/nested.cpp": CPP_NESTED,
    "src/cpp/outofline.cpp": CPP_OUT,
    "src/cpp/calc.c": C,
    "src/cpp/tool.py": FOREIGN,
    "src/rust/lib.rs": RS,
    "src/ts/greeter.ts": TS,
    "src/yaml/service.yaml": YAML,
}


def _write(root: Path, files: dict[str, str | bytes | None]) -> Path:
    """Write the project under ``root``; return its Sphinx source directory. A file whose
    content is the same is left untouched (Sphinx compares modification times), and
    ``None`` removes one."""
    for name, content in files.items():
        path = root / name
        if content is None:
            path.unlink(missing_ok=True)
            continue
        data = content.encode("utf-8") if isinstance(content, str) else content
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists() or path.read_bytes() != data:
            path.write_bytes(data)
    return root / "docs"


def _build(
    make_app: _MakeApp, srcdir: Path, *, fresh: bool = True
) -> tuple[SphinxTestApp, list[str], list[str]]:
    """Build; return the app, the documents read and the documents written."""
    app = make_app("html", srcdir=srcdir, freshenv=fresh, warning=io.StringIO())
    app.build()
    status = strip_colors(app._status.getvalue())
    read = re.findall(r"reading sources\.\.\. \[\s*\d+%\] (\S+)", status)
    written = re.findall(r"writing output\.\.\. \[\s*\d+%\] (\S+)", status)
    return app, read, written


def _compact(hop: NeedSourceHop) -> str:
    """One hop on one line: ``kind [document] root:path:start-end (language) ::
    semantic``, as sphinx-needs' own hop snapshots print them."""
    parts = [hop.kind]
    if hop.document is not None:
        parts.append(f"[{hop.document}]")
    if (physical := hop.physical) is not None:
        where = f"{physical.root}:{physical.path}"
        if physical.start_line is not None:
            where += f":{physical.start_line}"
            if physical.end_line is not None:
                where += f"-{physical.end_line}"
        parts.append(where)
    if hop.language is not None:
        parts.append(f"({hop.language})")
    if hop.origin is not None:
        parts.append(f"origin={hop.origin}")
    if hop.semantic is not None:
        parts.append(
            ":: "
            + " > ".join(
                f"{entry.kind} {entry.name!r}"
                + "".join(f" {key}={value!r}" for key, value in entry.extras)
                for entry in hop.semantic
            )
        )
    return " ".join(parts)


@pytest.fixture
def built(make_app: _MakeApp, tmp_path: Path) -> SphinxTestApp:
    app, _, _ = _build(make_app, _write(tmp_path, FILES))
    return app


def _hops(app: SphinxTestApp) -> dict[str, list[str]]:
    return {
        need_id: [_compact(hop) for hop in need.source.hops]
        for need_id, need in SphinxNeedsData(app.env).get_needs_view().items()
    }


# --- the hops ---------------------------------------------------------------------------

_HOPS = "section 'Hops'"
_LANGUAGES = "section 'Hops' > section 'Languages'"

#: Every need's hops, innermost first: the marker in its file, then the directive.
EXPECTED_HOPS = {
    # attached to nothing (the file): the language from the comment type, no semantic
    "IMPL_PY_FILE": [
        "code srcdir:../src/py/shapes.py:1-1 (python)",
        f"page [index] srcdir:index.rst:4-5 (.rst) :: {_HOPS}",
    ],
    "IMPL_PY_ONE": [
        "code srcdir:../src/py/shapes.py:4-4 (python) :: class 'Shape' > method 'area'",
        f"page [index] srcdir:index.rst:4-5 (.rst) :: {_HOPS}",
    ],
    # Python's `<locals>` is implied by the kinds: a method another part follows
    "IMPL_PY_LOCALS": [
        "code srcdir:../src/py/shapes.py:6-6 (python) :: class 'Shape' > "
        "method 'area' > function 'inner'",
        f"page [index] srcdir:index.rst:4-5 (.rst) :: {_HOPS}",
    ],
    # a multi-line need: its open line to its close line
    "IMPL_PY_MULTI": [
        "code srcdir:../src/py/shapes.py:10-14 (python) :: function 'compute'",
        f"page [index] srcdir:index.rst:4-5 (.rst) :: {_HOPS}",
    ],
    "IMPL_CRLF_ONE": [
        "code srcdir:../src/py/crlf.py:2-2 (python) :: class 'K' > method 'm'",
        f"page [index] srcdir:index.rst:4-5 (.rst) :: {_HOPS}",
    ],
    "IMPL_CRLF_MULTI": [
        "code srcdir:../src/py/crlf.py:7-11 (python) :: function 'g'",
        f"page [index] srcdir:index.rst:4-5 (.rst) :: {_HOPS}",
    ],
    # the pair: equal names, different kinds, carried as the analysis gives them
    "IMPL_CPP_IN": [
        "code srcdir:../src/cpp/nested.cpp:4-4 (cpp) :: namespace 'ns' > class 'W' > "
        "method 'f'",
        f"page [index] srcdir:index.rst:7-8 (.rst) :: {_HOPS}",
    ],
    "IMPL_CPP_OUT": [
        "code srcdir:../src/cpp/outofline.cpp:8-8 (cpp) :: scope 'ns' > class 'W' > "
        "method 'f'",
        f"page [index] srcdir:index.rst:7-8 (.rst) :: {_HOPS}",
    ],
    "IMPL_CPP_MULTI": [
        "code srcdir:../src/cpp/nested.cpp:10-14 (cpp) :: function 'run'",
        f"page [index] srcdir:index.rst:7-8 (.rst) :: {_HOPS}",
    ],
    # a `.c` file is C, in a project of the cpp comment type
    "IMPL_C_ONE": [
        "code srcdir:../src/cpp/calc.c:1-1 (c) :: function 'add'",
        f"page [index] srcdir:index.rst:7-8 (.rst) :: {_HOPS}",
    ],
    "IMPL_C_MULTI": [
        "code srcdir:../src/cpp/calc.c:5-9 (c) :: function 'sub'",
        f"page [index] srcdir:index.rst:7-8 (.rst) :: {_HOPS}",
    ],
    # a `.py` file traced by a C++ project: the project's language, not the suffix's
    "IMPL_FOREIGN": [
        "code srcdir:../src/cpp/tool.py:1-1 (cpp)",
        f"page [index] srcdir:index.rst:10-12 (.rst) :: {_HOPS}",
    ],
    # a trait impl: the trait is an extra of the `impl` part
    "IMPL_RS_TRAIT": [
        "code srcdir:../src/rust/lib.rs:8-8 (rust) :: impl 'Widget' trait='Shape' > "
        "method 'area'",
        f"page [index] srcdir:index.rst:17-18 (.rst) :: {_LANGUAGES}",
    ],
    # a multi-line need in a trait impl: the trait too
    "IMPL_RS_TRAIT_MULTI": [
        "code srcdir:../src/rust/lib.rs:12-16 (rust) :: impl 'Widget' trait='Shape' > "
        "method 'perimeter'",
        f"page [index] srcdir:index.rst:17-18 (.rst) :: {_LANGUAGES}",
    ],
    "IMPL_RS_MULTI": [
        "code srcdir:../src/rust/lib.rs:23-27 (rust) :: impl 'Widget' > method 'new'",
        f"page [index] srcdir:index.rst:17-18 (.rst) :: {_LANGUAGES}",
    ],
    "IMPL_TS_ONE": [
        "code srcdir:../src/ts/greeter.ts:2-2 (typescript) :: class 'Greeter' > "
        "method 'greet'",
        f"page [index] srcdir:index.rst:20-21 (.rst) :: {_LANGUAGES}",
    ],
    "IMPL_TS_MULTI": [
        "code srcdir:../src/ts/greeter.ts:9-13 (typescript) :: function 'farewell'",
        f"page [index] srcdir:index.rst:20-21 (.rst) :: {_LANGUAGES}",
    ],
    # a YAML entry has no name: no semantic location
    "IMPL_YAML_ONE": [
        "code srcdir:../src/yaml/service.yaml:2-2 (yaml)",
        f"page [index] srcdir:index.rst:23-24 (.rst) :: {_LANGUAGES}",
    ],
    "IMPL_YAML_MULTI": [
        "code srcdir:../src/yaml/service.yaml:4-8 (yaml)",
        f"page [index] srcdir:index.rst:23-24 (.rst) :: {_LANGUAGES}",
    ],
    # inside the source directory: no `..`
    "IMPL_INSIDE": [
        "code srcdir:code/inside.py:1-1 (python) :: function 'inside'",
        f"page [index] srcdir:index.rst:26-27 (.rst) :: {_LANGUAGES}",
    ],
}


@pytest.mark.parametrize("need_id", list(EXPECTED_HOPS))
def test_every_need_records_its_code_hop(built: SphinxTestApp, need_id: str) -> None:
    assert _hops(built)[need_id] == EXPECTED_HOPS[need_id]


def test_the_project_traces_exactly_the_pinned_needs(built: SphinxTestApp) -> None:
    assert sorted(_hops(built)) == sorted(EXPECTED_HOPS)


def test_the_cpp_pair_has_one_name_chain_and_two_kind_sequences(
    built: SphinxTestApp,
) -> None:
    """The hop carries the parts as given; identity is codelinks' ``name_chain``."""
    needs = SphinxNeedsData(built.env).get_needs_view()
    nested, out = (needs[i].source.hops[0] for i in ("IMPL_CPP_IN", "IMPL_CPP_OUT"))
    assert [p.kind for p in nested.semantic or ()] == ["namespace", "class", "method"]
    assert [p.kind for p in out.semantic or ()] == ["scope", "class", "method"]

    def chain(hop: NeedSourceHop) -> Any:
        parts: list[Any] = [
            {"kind": p.kind, "name": p.name, **dict(p.extras)}
            for p in hop.semantic or ()
        ]
        return name_chain(parts, hop.language or "")

    assert chain(nested) == chain(out)


def test_a_need_s_lineno_is_its_directive_s_line(built: SphinxTestApp) -> None:
    """The line the directive is written on: the page hop's start line."""
    needs = SphinxNeedsData(built.env).get_needs_view()
    assert {need_id: needs[need_id]["lineno"] for need_id in EXPECTED_HOPS} == {
        need_id: int(re.findall(r"index\.rst:(\d+)-", hops[-1])[0])
        for need_id, hops in EXPECTED_HOPS.items()
    }


def test_a_need_s_body_is_anchored_at_its_directive_s_line(
    built: SphinxTestApp,
) -> None:
    """``lineno_content`` is the directive's line, one-line and multi-line alike, not
    the line after its block where ``from_directive`` puts it: a body parsed at the page
    without a ``content_source`` is the marker's, and is anchored at the directive
    (``test_a_fallback_on_a_page_of_a_third_parser_keeps_the_need``)."""
    needs = SphinxNeedsData(built.env).get_needs_view()
    assert {
        need_id: (
            needs[need_id].source.lineno_content,
            needs[need_id].source.parser_lineno,
        )
        for need_id in (
            "IMPL_PY_ONE",
            "IMPL_PY_MULTI",
            "IMPL_RS_TRAIT",
            "IMPL_RS_MULTI",
        )
    } == {
        "IMPL_PY_ONE": (4, 4),
        "IMPL_PY_MULTI": (4, 4),
        "IMPL_RS_TRAIT": (17, 17),
        "IMPL_RS_MULTI": (17, 17),
    }


def test_no_hop_reaches_needs_json(built: SphinxTestApp) -> None:
    text = Path(built.outdir, "needs.json").read_text(encoding="utf-8")
    assert "semantic" not in text
    assert "hops" not in text
    assert "shapes.py" not in text


def test_a_need_after_rst_prolog_is_at_its_line_in_the_file(
    make_app: _MakeApp, tmp_path: Path
) -> None:
    """``rst_prolog`` shifts the parser's count, not the file's lines."""
    conf = CONF + 'rst_prolog = ".. |a| replace:: A\\n.. |b| replace:: B\\n"\n'
    app, _, _ = _build(make_app, _write(tmp_path, {**FILES, "docs/conf.py": conf}))
    needs = SphinxNeedsData(app.env).get_needs_view()
    assert needs["IMPL_PY_ONE"]["lineno"] == 4
    assert needs["IMPL_RS_TRAIT"]["lineno"] == 17
    # the body's anchor stays in the parser's count, which the prolog shifts
    source = needs["IMPL_PY_ONE"].source
    assert source.lineno_content == source.parser_lineno == 7
    assert _hops(app)["IMPL_RS_TRAIT"] == EXPECTED_HOPS["IMPL_RS_TRAIT"]


def test_a_need_in_an_included_file_is_at_its_line_there(
    make_app: _MakeApp, tmp_path: Path
) -> None:
    page = "Hops\n====\n\nProse.\n\n.. include:: traced.rst.txt\n"
    included = "Some prose.\n\n.. src-trace::\n   :project: rust\n"
    app, _, _ = _build(
        make_app,
        _write(
            tmp_path,
            {**FILES, "docs/index.rst": page, "docs/traced.rst.txt": included},
        ),
    )
    needs = SphinxNeedsData(app.env).get_needs_view()
    # line 3 of ``traced.rst.txt``, the included file, as a need directive records it
    # (the parser's count, 10 before, was a line neither file has the directive on)
    assert needs["IMPL_RS_TRAIT"]["lineno"] == 3
    assert _hops(app)["IMPL_RS_TRAIT"] == [
        "code srcdir:../src/rust/lib.rs:8-8 (rust) :: impl 'Widget' trait='Shape' > "
        "method 'area'",
        "file srcdir:traced.rst.txt:3-4 (.txt)",
        "page [index] srcdir:index.rst (.rst) :: section 'Hops'",
    ]


# --- the code hop's path: Sphinx-Needs' rule, computed here ----------------------------

_SRCDIR = os.path.join(os.sep, "project", "docs")

#: ``(srcdir, path)``: what ``physical_for`` and the package's helper are both asked.
PATH_SHAPES = {
    "inside": (_SRCDIR, os.path.join(_SRCDIR, "code", "a.py")),
    "outside": (_SRCDIR, os.path.join(os.sep, "project", "src", "a.py")),
    "far outside": (_SRCDIR, os.path.join(os.sep, "elsewhere", "a.py")),
    "relative to the working directory": ("docs", os.path.join("src", "a.py")),
    "the source directory itself": (_SRCDIR, _SRCDIR),
    "dotted segments": (_SRCDIR, os.path.join(_SRCDIR, "a", "..", "a.py")),
}
if sys.platform == "win32":
    PATH_SHAPES["backslashes"] = ("C:\\project\\docs", "C:\\project\\src\\a.py")
    PATH_SHAPES["forward slashes"] = ("C:/project/docs", "C:/project/docs/a.py")
    PATH_SHAPES["another drive"] = ("C:\\project\\docs", "D:\\src\\a.py")


@pytest.mark.parametrize("shape", list(PATH_SHAPES))
def test_the_code_path_is_sphinx_needs_rule(shape: str) -> None:
    from sphinx_codelinks.sphinx_extension.directives.src_trace import _code_physical
    from sphinx_needs._need_source import physical_for

    srcdir, path = PATH_SHAPES[shape]
    assert _code_physical(srcdir, path) == physical_for(srcdir, path)
    assert _code_physical(srcdir, path, 3, 7) == physical_for(srcdir, path, 3, 7)


def test_the_code_path_under_a_symlinked_directory_is_sphinx_needs_rule(
    tmp_path: Path,
) -> None:
    from sphinx_codelinks.sphinx_extension.directives.src_trace import _code_physical
    from sphinx_needs._need_source import physical_for

    (tmp_path / "real").mkdir()
    (tmp_path / "real" / "a.py").write_text(INSIDE, encoding="utf-8")
    (tmp_path / "docs").mkdir()
    try:
        (tmp_path / "docs" / "linked").symlink_to(
            tmp_path / "real", target_is_directory=True
        )
    except OSError:
        pytest.skip("no symlinks here")
    for srcdir, path in [
        (tmp_path / "docs", tmp_path / "docs" / "linked" / "a.py"),
        (tmp_path / "docs" / "linked", tmp_path / "real" / "a.py"),
    ]:
        assert _code_physical(srcdir, path) == physical_for(srcdir, path)


# --- incremental builds: each equals a fresh build -------------------------------------

#: a page whose need the traced one links to: it shows the traced need as a back link
OTHER = """\
Other
=====

.. req:: A requirement
   :id: REQ_1
"""

PY_LINKED = PY.replace(
    "# @Area of a shape, IMPL_PY_ONE, impl",
    "# @Area of a shape, IMPL_PY_ONE, impl, [REQ_1]",
)
INCREMENTAL = {
    **FILES,
    "docs/index.rst": INDEX + "\n.. toctree::\n\n   other\n",
    "docs/other.rst": OTHER,
    "src/py/shapes.py": PY_LINKED,
}

#: ``scenario: {file: new content}``, over :data:`INCREMENTAL`
SCENARIOS: dict[str, dict[str, str | bytes | None]] = {
    # three lines above every marker of the file: the needs only move
    "marker-moved": {"src/py/shapes.py": "\n\n\n" + PY_LINKED},
    # the entity a marker is attached to is renamed: its hop's semantic changes
    "entity-renamed": {
        "src/py/shapes.py": PY_LINKED.replace("def area", "def surface")
    },
    # the marker itself is edited
    "source-edited": {
        "src/py/shapes.py": PY_LINKED.replace("Area of a shape", "Area of any shape")
    },
}


def _pages(outdir: Path) -> dict[str, str]:
    """The body of every page, the part a need can show up in."""
    body = re.compile(
        r'<div class="body" role="main">(.*?)<div class="sphinxsidebar"', re.DOTALL
    )
    pages = {}
    for path in sorted(outdir.glob("*.html")):
        if path.stem in {"genindex", "search", "permalink"}:
            continue
        match = body.search(path.read_text(encoding="utf-8"))
        assert match is not None, path
        pages[path.stem] = re.sub(r"SNCB-[0-9a-f]+", "SNCB-", match.group(1))
    return pages


def _sources(app: SphinxTestApp) -> dict[str, Any]:
    """Every need's lineno and hops (paths are relative, so two projects compare)."""
    return {
        need_id: (need["lineno"], need.source.hops)
        for need_id, need in SphinxNeedsData(app.env).get_needs_view().items()
    }


def _needs_json(app: SphinxTestApp) -> dict[str, Any]:
    data = json.loads(Path(app.outdir, "needs.json").read_text(encoding="utf-8"))
    return data["versions"][data["current_version"]]["needs"]


def _assert_equivalent(
    make_app: _MakeApp, tmp_path: Path, scenario: str
) -> tuple[SphinxTestApp, list[str]]:
    """Build, edit, build incrementally, and compare with a fresh build of the edit.

    :return: The incremental app, and the documents it wrote.
    """
    after = {**INCREMENTAL, **SCENARIOS[scenario]}
    incremental = _write(tmp_path / "incremental", INCREMENTAL)
    _build(make_app, incremental)
    _write(tmp_path / "incremental", after)
    app, _, written = _build(make_app, incremental, fresh=False)

    fresh_app, _, _ = _build(make_app, _write(tmp_path / "fresh", after))
    got, expected = _pages(Path(app.outdir)), _pages(Path(fresh_app.outdir))
    stale = sorted(name for name in expected if got.get(name) != expected[name])
    assert stale == [], f"pages not re-written: {stale} (wrote {written})"
    assert _needs_json(app) == _needs_json(fresh_app)
    assert _sources(app) == _sources(fresh_app)
    return app, written


def test_a_marker_that_moves_rewrites_only_its_own_page(
    make_app: _MakeApp, tmp_path: Path
) -> None:
    """Its needs only moved: the page showing one as a back link is not re-written."""
    app, written = _assert_equivalent(make_app, tmp_path, "marker-moved")
    assert written == ["index"]
    assert _hops(app)["IMPL_PY_ONE"][0].startswith(
        "code srcdir:../src/py/shapes.py:7-7 "
    )


def test_a_renamed_entity_rewrites_the_pages_showing_its_need(
    make_app: _MakeApp, tmp_path: Path
) -> None:
    app, written = _assert_equivalent(make_app, tmp_path, "entity-renamed")
    assert sorted(written) == ["index", "other"]
    assert _hops(app)["IMPL_PY_ONE"][0].endswith(":: class 'Shape' > method 'surface'")


def test_an_edited_source_file_equals_a_fresh_build(
    make_app: _MakeApp, tmp_path: Path
) -> None:
    _, written = _assert_equivalent(make_app, tmp_path, "source-edited")
    assert sorted(written) == ["index", "other"]


# --- the upgrade ------------------------------------------------------------------------


def test_an_environment_pickled_at_env_version_1_is_read_again(
    make_app: _MakeApp, tmp_path: Path
) -> None:
    """Version 1 recorded each need on its page alone, at the parser's line, with no
    code hop. Nothing in the sources or the configuration changed: ``env_version`` 2 is
    what has the build read the page again here, rather than keep those records."""
    srcdir = _write(tmp_path, FILES)
    app, _, _ = _build(make_app, srcdir)
    pickled = Path(app.doctreedir, "environment.pickle")
    env = pickle.loads(pickled.read_bytes())
    env.version["sphinx_codelinks"] = 1
    # what version 1 recorded: the page, at the directive's line, and nothing else
    for need in env._needs_all_needs.values():
        need._source = NeedItemSource.on_page(need["docname"], lineno=need["lineno"])
    pickled.write_bytes(pickle.dumps(env, pickle.HIGHEST_PROTOCOL))

    app, read, _ = _build(make_app, srcdir, fresh=False)
    assert read == ["index"]
    assert _hops(app) == EXPECTED_HOPS
