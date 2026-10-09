# @Test suite for multi-line needs rendered by src-trace, TEST_MULTILINE_RENDER_1, test, [IMPL_LNK_1]
"""``src-trace`` creates a need from every multi-line need of its files (#1885).

Every case builds a copy of ``doc_test/need_id_refs`` (see ``test_need_id_refs``) made
into a git repository, with ``myst-parser`` loaded, ``get_multiline_needs`` on, a host
need ``REQ_HOST`` and a label ``host-label`` in ``index``, and ``src/refs.cpp`` emptied of
its references. A block's body is parsed in the markup it declares, whatever the page's:
the four cells (page markup by body markup) render the same role link, reference, list and literal.
"""

import hashlib
import re
from pathlib import Path
from typing import Any

import myst_parser
import pytest
from sphinx.testing.util import SphinxTestApp
from sphinx.util.parallel import parallel_available

from sphinx_needs_testkit import build_warnings

from .test_need_id_refs import _SHOWS_WARNING_TYPES, _build, _json, _MakeApp, _project
from .test_rediscovery import _touch_later

MYST_MAJOR = int(myst_parser.__version__.split(".")[0])

CONF = """\
extensions = ["sphinx_needs", "sphinx_codelinks", "myst_parser"]
exclude_patterns = ["_build"]
needs_build_json = True
source_suffix = {".rst": "restructuredtext", ".md": "markdown"}
needs_fields = {"priority": {"description": "Priority", "schema": {"type": "integer"}}}
"""

INDEX = """\
Multi-line needs
================

.. toctree::
   :glob:

   *
   sub/*

.. req:: A host need
   :id: REQ_HOST

.. _host-label:

Host label target
-----------------
"""

MULTILINE = """
[codelinks.projects.src.analyse]
get_oneline_needs = true
get_multiline_needs = true
"""

#: the files every case starts from
BASE = {
    "docs/conf.py": CONF,
    "docs/index.rst": INDEX,
    "src/refs.cpp": "// no markers here\n",
}

PAGE_RST = """\
RST page
========

.. src-trace::
   :project: src
   :file: rr.c

.. src-trace::
   :project: src
   :file: rm.c
"""

PAGE_MD = """\
# MyST page

```{src-trace}
:project: src
:file: mr.c
```

```{src-trace}
:project: src
:file: mm.c
```
"""

RST_BODY = """\
 * Body in RST, see :need:`REQ_HOST` and :ref:`host-label`.
 *
 * - bullet one
 * - bullet with ``inline literal``"""

MYST_BODY = """\
 * Body in MyST, see {need}`REQ_HOST` and {ref}`host-label`.
 *
 * - bullet one
 * - bullet with `inline literal`"""


def _cell(name: str, markup: str, body: str) -> str:
    """A source file: a one-line need on line 1, a block opening on line 5."""
    upper = name.upper()
    return f"""\
// @one-line in {name}.c, IMPL_{upper}_ONE, impl, [REQ_HOST]
void f() {{}}

/**
 * @need[{markup}] req: {upper} body
 * :id: REQ_{upper}
 * :links: REQ_HOST, IMPL_{upper}_ONE
 *
{body}
 * @endneed
 */
void g() {{}}
"""


#: the four cells: (source, page, the directive's line on it, the body's markup)
CELLS = {
    "REQ_RR": ("rr.c", "page_rst", 4, ".rst"),
    "REQ_RM": ("rm.c", "page_rst", 8, ".md"),
    "REQ_MR": ("mr.c", "page_md", 3, ".rst"),
    "REQ_MM": ("mm.c", "page_md", 8, ".md"),
}

FOUR_CELLS = {
    "docs/page_rst.rst": PAGE_RST,
    "docs/page_md.md": PAGE_MD,
    "src/rr.c": _cell("rr", "rst", RST_BODY),
    "src/rm.c": _cell("rm", "md", MYST_BODY),
    "src/mr.c": _cell("mr", "rst", RST_BODY),
    "src/mm.c": _cell("mm", "md", MYST_BODY),
}


def _blocks(tmp_path: Path, files: dict[str, str], *, toml_extra: str = "") -> str:
    """The project with ``files`` added; return its commit."""
    return _project(
        tmp_path, files={**BASE, **files}, toml_extra=MULTILINE + toml_extra
    )


def _warning(location: str, message: str, subtype: str) -> str:
    suffix = f" [codelinks.{subtype}]" if _SHOWS_WARNING_TYPES else ""
    return f"{location}: WARNING: {message}{suffix}"


def _multiline(location: str, message: str) -> str:
    return _warning(location, message, "multiline_need")


def _content_html(app: SphinxTestApp, page: str, need_id: str) -> str:
    """The HTML of the content cell of the need ``need_id``."""
    text = Path(app.outdir, page).read_text(encoding="utf-8")
    start = text.index('<td class="need content"', text.index(f'id="{need_id}"'))
    return text[start : text.index("</td>", start)]


def _need(app: SphinxTestApp, need_id: str) -> dict[str, Any] | None:
    return _json(app)["needs"].get(need_id)


def _card(app: SphinxTestApp, page: str, need_id: str) -> str | None:
    """The HTML of the need's table on ``page``, ``None`` without one."""
    html = Path(app.outdir, page).read_text(encoding="utf-8")
    match = re.search(rf'<table class="[^"]*" id="{need_id}"[^>]*>', html)
    return (
        None
        if match is None
        else html[match.start() : html.index("</table>", match.start())]
    )


def _warnings(app: SphinxTestApp) -> list[str]:
    """:func:`build_warnings` without the extension re-registration notes a second
    application in one process logs."""
    return [w for w in build_warnings(app) if "is already registered" not in w]


def test_four_cells_render_in_the_declared_markup(
    tmp_path: Path, make_app: _MakeApp
) -> None:
    """An RST and a MyST body, each in an RST and a MyST page: the same role link,
    reference, list and literal in all four; each need recorded at its directive with
    the body's doctype, its links converted, its URLs at the block's open line."""
    commit = _blocks(tmp_path, FOUR_CELLS)
    app = _build(tmp_path, make_app)

    assert build_warnings(app) == []
    for need_id, (source, page, lineno, doctype) in CELLS.items():
        need = _need(app, need_id)
        assert need is not None, need_id
        upper = need_id.removeprefix("REQ_")
        assert {
            key: need[key]
            for key in ("docname", "lineno", "doctype", "links", "is_import")
        } == {
            "docname": page,
            "lineno": lineno,
            "doctype": doctype,
            # Sphinx-Needs keeps a need's links sorted
            "links": [f"IMPL_{upper}_ONE", "REQ_HOST"],
            "is_import": False,
        }, need_id
        assert need["local-url"] == f"src/{source}#L5"
        assert need["remote-url"] == (
            f"https://github.com/example/demo/blob/{commit}/src/{source}#L5"
        )
        html = _content_html(app, f"{page}.html", need_id)
        assert 'href="index.html#REQ_HOST"' in html, need_id
        assert 'href="index.html#host-label"' in html, need_id
        assert '<ul class="simple">' in html, need_id
        assert '<code class="docutils literal notranslate">' in html, need_id
        # no role written in the other markup is left as text
        assert ":need:" not in html, need_id
        assert "{need}" not in html, need_id
        # the source page links the open line back to the need
        source_page = Path(app.outdir, "src", source.replace(".c", ".html"))
        assert (
            f'<a class="viewcode-back" href="../{page}.html#{need_id}">[docs]</a>'
            '<a id="L-5" name="L-5">'
        ) in source_page.read_text(encoding="utf-8"), need_id


def _myst_logged(page: str, source: str, line: int) -> str:
    """Where a warning myst-parser logs itself points, for a body in ``source``:
    myst-parser 5 names the page being read with the body's line, myst-parser 4 the
    body's file with an ``.rst`` suffix (Sphinx-Needs' documented first-slice gap)."""
    if MYST_MAJOR >= 5:
        return f"<srcdir>/docs/{page}:{line}"
    return f"<srcdir>/src/{source}.rst:{line}"


def _diagnostics_cell(name: str, markup: str) -> str:
    upper = name.upper()
    if markup == "rst":
        body = " * A bad role :nosuchrole:`x` here.\n *\n * .. nosuchdirective:: arg"
    else:
        body = " * A bad role {nosuchrole}`x` here.\n *\n * ```{nosuchdirective} arg\n * ```"
    return f"""\
// a file with one block, opening on line 3

/**
 * @need[{markup}] spec: {upper} diagnostics
 * :id: SPEC_{upper}
 *
{body}
 * @endneed
 */
void h() {{}}
"""


def test_body_diagnostics_name_the_source_line(
    tmp_path: Path, make_app: _MakeApp
) -> None:
    """A message about an RST body names the source file and line (absolute: Sphinx
    makes a node's source absolute); myst-parser's own messages about a MyST body name
    the page (myst-parser 5) or ``<source>.rst`` (4), with the source line."""
    _blocks(
        tmp_path,
        {
            "docs/page_rst.rst": PAGE_RST,
            "docs/page_md.md": PAGE_MD,
            "src/rr.c": _diagnostics_cell("rr", "rst"),
            "src/rm.c": _diagnostics_cell("rm", "md"),
            "src/mr.c": _diagnostics_cell("mr", "rst"),
            "src/mm.c": _diagnostics_cell("mm", "md"),
        },
    )
    app = _build(tmp_path, make_app)

    docutils = " [docutils]" if _SHOWS_WARNING_TYPES else ""

    def myst(kind: str) -> str:
        return f" [myst.{kind}]" if _SHOWS_WARNING_TYPES else ""

    def rst(source: str) -> list[str]:
        return [
            f"<srcdir>/src/{source}:7: ERROR: Unknown interpreted text role "
            f'"nosuchrole".{docutils}',
            f'<srcdir>/src/{source}:9: ERROR: Unknown directive type "nosuchdirective".'
            "\n\n.. nosuchdirective:: arg"
            f"{docutils}",
        ]

    def md(page: str, source: str) -> list[str]:
        return [
            f"{_myst_logged(page, source, 7)}: WARNING: Unknown interpreted text role "
            f'"nosuchrole".{myst("role_unknown")}',
            f"{_myst_logged(page, source, 9)}: WARNING: Unknown directive type: "
            f"'nosuchdirective'{myst('directive_unknown')}",
        ]

    assert sorted(build_warnings(app, srcdir=tmp_path)) == sorted(
        [
            *rst("mr.c"),
            *md("page_md.md", "mm.c"),
            *rst("rr.c"),
            *md("page_rst.rst", "rm.c"),
        ]
    )
    for need_id in ("SPEC_RR", "SPEC_RM", "SPEC_MR", "SPEC_MM"):
        assert _need(app, need_id) is not None, need_id


Q3_HEAD = "// @need req: Q3 block\n"
#: an expectation on the need's card on its page rather than on ``needs.json``: ``None``
#: for no card, else a text the card holds
CARD = "<card>"
Q3_BODY = "//\n// Body {{ 1 + 1 }} here.\n// @endneed\nvoid q() {}\n"


@pytest.mark.parametrize(
    ("options", "expected", "warnings"),
    [
        pytest.param(
            [":links: REQ_HOST; REQ_002 | SPEC_001"],
            {"links": ["REQ_002", "REQ_HOST", "SPEC_001"]},
            [],
            id="links_split",
        ),
        pytest.param([":tags: a, b"], {"tags": ["a", "b"]}, [], id="tags_split"),
        pytest.param([":status: open"], {"status": "open"}, [], id="status"),
        pytest.param([":priority: 3"], {"priority": 3}, [], id="typed_field_coerced"),
        pytest.param(
            [":priority: notanint"],
            None,
            [
                (
                    1,
                    "invalid_field_value: multi-line need could not be created: Field "
                    "'priority' is invalid: Cannot convert 'notanint' to integer",
                )
            ],
            id="typed_field_refused",
        ),
        pytest.param(
            [":nosuch: x"],
            {"title": "Q3 block"},
            [
                (
                    3,
                    "multi-line need option 'nosuch' is not an option of the need "
                    "directive: ignored",
                )
            ],
            id="unknown_option_warned",
        ),
        pytest.param([":hide:"], {CARD: None}, [], id="hide_flag"),
        pytest.param(
            [":collapse: true"], {CARD: "target__hide__meta"}, [], id="collapse"
        ),
        pytest.param(
            [":constraints: nosuchconstraint"],
            None,
            [
                (
                    1,
                    "invalid_constraints: multi-line need could not be created: "
                    "Constraints {'nosuchconstraint'} not in 'needs_constraints'.",
                )
            ],
            id="unknown_constraint_refused",
        ),
        pytest.param(
            [":jinja_content: false"],
            {"jinja_content": False, "content": "Body {{ 1 + 1 }} here."},
            [],
            id="jinja_content_false",
        ),
        pytest.param(
            [":jinja_content: true"],
            {"jinja_content": True, "content": "Body 2 here."},
            [],
            id="jinja_content_true",
        ),
        pytest.param(
            [":jinja_content: maybe"],
            None,
            [
                (
                    3,
                    "multi-line need could not be created: Invalid value for "
                    "'jinja_content' option: not a flag or case-insensitive "
                    "true/false/yes/no",
                )
            ],
            id="jinja_content_refused",
        ),
        pytest.param(
            [":docname: elsewhere", ":lineno: 99"],
            {"docname": "page_q", "lineno": 4},
            [
                (
                    3,
                    "multi-line need option 'docname' is not an option of the need "
                    "directive: ignored",
                ),
                (
                    4,
                    "multi-line need option 'lineno' is not an option of the need "
                    "directive: ignored",
                ),
            ],
            id="computed_keys_warned",
        ),
        pytest.param(
            [":parts: some text"],
            {"parts": {}},
            [
                (
                    3,
                    "multi-line need option 'parts' is not an option of the need "
                    "directive: ignored",
                )
            ],
            id="parts_warned_not_crashing",
        ),
        pytest.param(
            [":arch: some text"],
            {"arch": {}},
            [
                (
                    3,
                    "multi-line need option 'arch' is not an option of the need "
                    "directive: ignored",
                )
            ],
            id="arch_warned",
        ),
        pytest.param(
            [":delete: true"],
            {"title": "Q3 block"},
            [
                (
                    3,
                    "multi-line need option 'delete' is not an option of the need "
                    "directive: ignored",
                )
            ],
            id="directive_only_option_warned",
        ),
    ],
)
def test_options_are_the_need_directives(
    tmp_path: Path,
    make_app: _MakeApp,
    options: list[str],
    expected: dict[str, Any] | None,
    warnings: list[tuple[int, str]],
) -> None:
    """A block takes the options ``.. req::`` takes, converted as the directive converts
    them: links and tags split, typed fields coerced, ``jinja_content`` a flag. A key
    the directive does not know is ignored with a warning at its line, the need kept; a
    value Sphinx-Needs refuses refuses the need, warned at the open line."""
    source = Q3_HEAD + "// :id: REQ_Q3\n"
    source += "".join(f"// {option}\n" for option in options) + Q3_BODY
    _blocks(
        tmp_path,
        {
            "docs/page_q.rst": "Q\n=\n\n.. src-trace::\n   :project: src\n   :file: q.c\n",
            "src/q.c": source,
        },
    )
    app = _build(tmp_path, make_app)

    assert build_warnings(app) == [
        _multiline(f"src/q.c:{line}", message) for line, message in warnings
    ]
    need = _need(app, "REQ_Q3")
    if expected is None:
        assert need is None
        return
    assert need is not None
    fields = {key: value for key, value in expected.items() if key != CARD}
    assert {key: need[key] for key in fields} == fields
    if CARD in expected:
        card = _card(app, "page_q.html", "REQ_Q3")
        if expected[CARD] is None:
            assert card is None
        else:
            assert card is not None
            assert expected[CARD] in card


def test_an_empty_id_is_refused_with_the_directives_message(
    tmp_path: Path, make_app: _MakeApp
) -> None:
    _blocks(
        tmp_path,
        {
            "docs/page_q.rst": "Q\n=\n\n.. src-trace::\n   :project: src\n   :file: q.c\n",
            "src/q.c": Q3_HEAD + "// :id:\n" + Q3_BODY,
        },
    )
    app = _build(tmp_path, make_app)

    assert build_warnings(app) == [
        _multiline(
            "src/q.c:2",
            "multi-line need could not be created: Invalid value for 'id' option: "
            "'id' must not be empty",
        )
    ]
    assert not [
        need for need in _json(app)["needs"].values() if need["docname"] == "page_q"
    ]


def test_an_unknown_type_is_refused_at_the_open_line(
    tmp_path: Path, make_app: _MakeApp
) -> None:
    _blocks(
        tmp_path,
        {
            "docs/page_q.rst": "Q\n=\n\n.. src-trace::\n   :project: src\n   :file: q.c\n",
            "src/q.c": "// a block of an unknown type\n// @need nosuchtype: T\n"
            "// :id: X_1\n// @endneed\n",
        },
    )
    app = _build(tmp_path, make_app)

    assert build_warnings(app) == [
        _multiline(
            "src/q.c:2",
            "invalid_type: multi-line need could not be created: Unknown need type "
            "'nosuchtype'.",
        )
    ]
    assert _need(app, "X_1") is None


DUPLICATES = """\
/**
 * @need req: Block first
 * :id: DUP_1
 * @endneed
 */
void a() {}
// @one-line after the block, DUP_1, impl
void b() {}
// @one-line before the block, DUP_2, impl
void c() {}
// @need req: Block after the one-line need
// :id: DUP_2
// @endneed
void d() {}
// @need req: The first of two blocks
// :id: DUP_3
// @endneed
void e() {}
// @need req: The second of two blocks
// :id: DUP_3
// @endneed
void f() {}
// @need req: Generated id block
// @endneed
void g() {}
"""


def _duplicate(location: str, kind: str, need_id: str) -> str:
    return _warning(
        location,
        f"{kind} {need_id!r} is already defined in document 'page_d': not created again "
        "by the src-trace directive in 'page_d' (give the markers distinct ids)",
        "duplicate_need",
    )


def test_one_need_per_id_across_kinds_the_earlier_line_wins(
    tmp_path: Path, make_app: _MakeApp
) -> None:
    """One-line needs and blocks are one list in source order: of two markers with one
    id, whatever their kinds, the earlier keeps it and the warning names the kind of the
    one skipped. A block without ``:id:`` gets the id Sphinx-Needs generates."""
    _blocks(
        tmp_path,
        {
            "docs/page_d.rst": "D\n=\n\n.. src-trace::\n   :project: src\n   :file: d.c\n",
            "src/d.c": DUPLICATES,
        },
    )
    app = _build(tmp_path, make_app)

    assert build_warnings(app) == [
        _duplicate("src/d.c:7", "one-line need", "DUP_1"),
        _duplicate("src/d.c:11", "multi-line need", "DUP_2"),
        _duplicate("src/d.c:19", "multi-line need", "DUP_3"),
    ]
    needs = _json(app)["needs"]
    assert (needs["DUP_1"]["type"], needs["DUP_1"]["title"]) == ("req", "Block first")
    assert (needs["DUP_2"]["type"], needs["DUP_2"]["title"]) == (
        "impl",
        "one-line before the block",
    )
    assert needs["DUP_3"]["title"] == "The first of two blocks"
    generated = "R_" + hashlib.sha1(b"Generated id block").hexdigest().upper()[:5]
    assert needs[generated]["title"] == "Generated id block"


ORDER = {
    "src/order/a.c": (
        "// @one-line A1, IMPL_A1_ONE, impl\n"
        "void a1() {}\n"
        "// @need req: Block B1\n"
        "// :id: REQ_B1_BLK\n"
        "// @endneed\n"
        "void b1() {}\n\n\n\n\n"
        "// @one-line A2, IMPL_A2_ONE, impl\n"
        "void a2() {}\n"
    ),
    "src/order/b.c": (
        "void nothing() {}\n"
        "// @one-line C1, IMPL_C1_ONE, impl\n"
        "void c1() {}\n"
        "// @need req: Block D1\n"
        "// :id: REQ_D1_BLK\n"
        "// @endneed\n"
        "void d1() {}\n"
    ),
}


def _card_order(app: SphinxTestApp, page: str) -> list[str]:
    html = Path(app.outdir, page).read_text(encoding="utf-8")
    return list(
        dict.fromkeys(re.findall(r'<table class="need[^"]*" id="([A-Z0-9_]+)"', html))
    )


def test_cards_follow_the_open_lines_across_files(
    tmp_path: Path, make_app: _MakeApp
) -> None:
    """A block takes its place by its open line, in the order one-line needs already
    have: by row across the directive's files, then by file."""
    _blocks(
        tmp_path,
        {
            **ORDER,
            "docs/page_o.rst": "O\n=\n\n.. src-trace::\n   :project: src\n"
            "   :directory: order\n",
        },
    )
    app = _build(tmp_path, make_app)

    assert build_warnings(app) == []
    assert _card_order(app, "page_o.html") == [
        "IMPL_A1_ONE",
        "IMPL_C1_ONE",
        "REQ_B1_BLK",
        "REQ_D1_BLK",
        "IMPL_A2_ONE",
    ]


@pytest.mark.skipif(
    not parallel_available, reason="Sphinx reads sources in parallel on POSIX only"
)
def test_parallel_build_matches_the_serial_one(
    tmp_path: Path, make_app: _MakeApp
) -> None:
    """``-j 2`` records the same needs, warnings and content as a serial build: a block
    is created through ``add_need``, which the parallel merge already handles."""
    _blocks(tmp_path, FOUR_CELLS)
    serial = _build(tmp_path, make_app)
    serial_needs = _json(serial)["needs"]
    serial_warnings = sorted(build_warnings(serial))
    serial_html = {
        need_id: _content_html(serial, f"{page}.html", need_id)
        for need_id, (_, page, _, _) in CELLS.items()
    }

    parallel = _build(tmp_path, make_app, parallel=2)

    assert _json(parallel)["needs"] == serial_needs
    assert sorted(_warnings(parallel)) == serial_warnings
    assert {
        need_id: _content_html(parallel, f"{page}.html", need_id)
        for need_id, (_, page, _, _) in CELLS.items()
    } == serial_html


INCREMENTAL = (
    "// @need req: Other title\n//\n// Other body.\n// @endneed\nvoid o() {}\n"
)


def test_an_edited_block_is_read_again(tmp_path: Path, make_app: _MakeApp) -> None:
    """An incremental build after editing a block's body updates its content; after
    editing its title the generated id moves, with no duplicate warning."""
    _blocks(
        tmp_path,
        {
            "docs/page_i.rst": "I\n=\n\n.. src-trace::\n   :project: src\n   :file: i.c\n",
            "src/i.c": INCREMENTAL,
        },
    )
    first_id = "R_" + hashlib.sha1(b"Other title").hexdigest().upper()[:5]
    app = _build(tmp_path, make_app)
    assert _need(app, first_id)["content"] == "Other body."  # type: ignore[index]

    source = tmp_path / "src" / "i.c"
    source.write_text(
        INCREMENTAL.replace("Other body.", "Edited body."), encoding="utf-8"
    )
    _touch_later(source)
    app = _build(tmp_path, make_app, freshenv=False)
    assert _warnings(app) == []
    assert _need(app, first_id)["content"] == "Edited body."  # type: ignore[index]

    source.write_text(
        INCREMENTAL.replace("Other body.", "Edited body.").replace(
            "Other title", "Edited title"
        ),
        encoding="utf-8",
    )
    _touch_later(source)
    app = _build(tmp_path, make_app, freshenv=False)
    second_id = "R_" + hashlib.sha1(b"Edited title").hexdigest().upper()[:5]
    assert _warnings(app) == []
    assert _need(app, first_id) is None
    assert _need(app, second_id)["content"] == "Edited body."  # type: ignore[index]


def test_analyser_warnings_on_blocks_are_multiline_need(
    tmp_path: Path, make_app: _MakeApp
) -> None:
    """A malformed block is reported at its source line under ``codelinks.multiline_need``
    -- every warning about blocks in the build shares one subtype -- while a malformed
    one-line marker stays ``codelinks.oneline``."""
    _blocks(
        tmp_path,
        {
            "docs/page_w.rst": "W\n=\n\n.. src-trace::\n   :project: src\n   :file: w.c\n",
            "src/w.c": "// @need req: Never closed\n// :id: REQ_OPEN\nvoid w() {}\n"
            "// @only a title, X_1, impl, [A], extra\nvoid x() {}\n",
        },
    )
    app = _build(tmp_path, make_app)

    assert build_warnings(app) == [
        _multiline(
            "src/w.c:1",
            "multiline_need_unterminated: no '@endneed' line before the comment ends; "
            "the block is skipped",
        ),
        _warning(
            "src/w.c:4",
            "too_many_fields: 5 given fields, maximum is 4",
            "oneline",
        ),
    ]
