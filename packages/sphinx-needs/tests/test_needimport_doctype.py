"""``needimport`` parses each imported need's content in the markup its ``doctype`` names.

Behind ``needs_import_parse_by_doctype`` and the directive's ``:parse_by_doctype:``
option. Every project here is built inline (``files``), and every needs.json is written
by the test from the shared bodies of the content-markup tests (``tests/util.py``),
whose constructs the other parser renders visibly differently: parsing a body with the
wrong parser shows in the HTML. Every import goes through the real ``.. needimport::``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from sphinx.testing.util import SphinxTestApp
from sphinx.util.parallel import parallel_available

from sphinx_needs_testkit import build_warnings
from tests.util import (
    BODIES,
    MYST_BODY,
    RST_BODY,
    at,
    html,
    line_of,
    myst_logged,
    need_content_html,
    needs_by_id,
)

PLAIN_EXT = '''\
"""Test-only: a source suffix whose parser is neither reStructuredText nor MyST."""

from docutils.parsers import Parser


class PlainTextParser(Parser):
    supported = ("plaintext",)

    def parse(self, inputstring, document):
        pass


def setup(app):
    app.add_source_suffix(".plain", "plaintext")
    app.add_source_parser(PlainTextParser)
    return {"parallel_read_safe": True, "parallel_write_safe": True}
'''

NEEDS_TYPES = """\
needs_types = [
    dict(directive="req", title="Requirement", prefix="R_", color="#BFD8D2", style="node"),
    dict(directive="spec", title="Specification", prefix="S_", color="#FEDCD2", style="node"),
]
needs_id_regex = r"^[A-Za-z0-9_]+$"
needs_build_json = True
needs_json_remove_defaults = False
show_warning_types = True
"""

CONF = (
    'extensions = ["myst_parser", "sphinx_needs"]\n'
    + NEEDS_TYPES
    + 'source_suffix = {".rst": "restructuredtext", ".md": "markdown"}\n'
)
"""A project that parses reStructuredText and MyST."""

FLAG = "needs_import_parse_by_doctype"


def needs_json(records: list[dict[str, Any]]) -> str:
    """A needs.json holding ``records`` in its current version, with no schema."""
    needs = {r["id"]: r for r in records}
    return json.dumps({"current_version": "1.0", "versions": {"1.0": {"needs": needs}}})


def record(need_id: str, content: str, **fields: Any) -> dict[str, Any]:
    """A need record of type ``spec``."""
    return {
        "id": need_id,
        "type": "spec",
        "title": need_id,
        "content": content,
        **fields,
    }


def body(markup: str, cell: str) -> str:
    """The shared body for ``markup``, its labels named after ``cell``."""
    return "\n".join(BODIES[markup]).replace("{cell}", cell)


HOST_INDEX = [
    "RST host",
    "========",
    "",
    ".. toctree::",
    "",
    "   a_host_md",
    "",
    ".. _hostlabel:",
    "",
    "Host labelled paragraph.",
    "",
    ".. req:: Host need",
    "   :id: REQ_HOST",
    "",
    "   host body",
    "",
]
"""An RST page with the need and the label the shared bodies reference."""

HOST_MD = ["# MyST host", ""]


def rst_import(path: str, options: dict[str, str | None]) -> list[str]:
    """A ``needimport`` in a reStructuredText page."""
    lines = [f".. needimport:: {path}"]
    lines += [
        f"   :{k}: {v}" if v is not None else f"   :{k}:" for k, v in options.items()
    ]
    return [*lines, ""]


def md_import(path: str, options: dict[str, str | None]) -> list[str]:
    """A ``needimport`` in a MyST page."""
    lines = [f"```{{needimport}} {path}"]
    lines += [f":{k}: {v}" if v is not None else f":{k}:" for k, v in options.items()]
    return [*lines, "```", ""]


# ------------------------------------------------------------------------------------
# (1) the 2x2 matrix: (page markup) x (record doctype)

MATRIX_CELLS = {
    # cell: (host page, record doctype)
    "rr": ("index.rst", ".rst"),
    "mr": ("index.rst", ".md"),
    "rm": ("a_host_md.md", ".rst"),
    "mm": ("a_host_md.md", ".md"),
}
"""Cell names as the content-markup tests name them: content markup, then page."""


def imp_id(cell: str) -> str:
    return f"IMP_{cell.upper()}"


def matrix_files(
    option: str | None,
) -> tuple[list[tuple[Path, str]], dict[str, int]]:
    """The matrix project, each directive carrying ``:parse_by_doctype: <option>``
    (``""`` for the bare flag, ``None`` for no option), and each cell's directive line."""
    options = {} if option is None else {"parse_by_doctype": option or None}
    index = list(HOST_INDEX)
    host_md = list(HOST_MD)
    linenos = {}
    files: list[tuple[Path, str]] = [(Path("conf.py"), CONF)]
    for cell, (host, doctype) in MATRIX_CELLS.items():
        path = f"{cell}.json"
        files.append(
            (
                Path(path),
                needs_json(
                    [record(imp_id(cell), body(doctype, cell), doctype=doctype)]
                ),
            )
        )
        page = index if host == "index.rst" else host_md
        linenos[cell] = len(page) + 1
        page += (rst_import if host == "index.rst" else md_import)(path, options)
    files += [
        (Path("index.rst"), "\n".join(index)),
        (Path("a_host_md.md"), "\n".join(host_md)),
    ]
    return files, linenos


MODES = {
    # mode: (project flag, directive option, parsed by doctype)
    "flag_off": (False, None, False),
    "flag_on": (True, None, True),
    "option_on": (False, "", True),
    "option_off": (True, "false", False),
}


def by_doctype_warnings(host: str, doctype: str, first: int, cell: str) -> list[str]:
    """What a cell's body reports when parsed in its ``doctype``, at the directive.

    The content is anchored at the directive's file and line: body line ``i`` is
    reported at ``first + i``, in a reStructuredText and in a MyST page alike.
    """
    if doctype == ".rst":
        role = first + at(RST_BODY, ":nosuchrole:")
        return [
            f"<srcdir>/{host}:{first + at(RST_BODY, '.. nosuchdirective')}: ERROR: "
            'Unknown directive type "nosuchdirective".\n\n.. nosuchdirective:: [docutils]',
            f"<srcdir>/{host}:{role}: ERROR: Unknown interpreted text role "
            '"nosuchrole". [docutils]',
            f"<srcdir>/{host}:{role}: WARNING: undefined label: "
            f"'nosuchlabel_{cell}' [ref.ref]",
        ]
    role = first + at(MYST_BODY, "{nosuchrole}")
    empty_note = first + MYST_BODY.index("```{note}", at(MYST_BODY, "{nosuchrole}"))
    return [
        f"{myst_logged(host, host, first + at(MYST_BODY, '```{nosuchdirective}'))}: "
        "WARNING: Unknown directive type: 'nosuchdirective' [myst.directive_unknown]",
        f"{myst_logged(host, host, role)}: WARNING: Unknown interpreted text role "
        '"nosuchrole". [myst.role_unknown]',
        f"<srcdir>/{host}:{empty_note}: ERROR: Content block expected for the "
        '"note" directive; none found. [docutils]',
        f"<srcdir>/{host}:{role}: WARNING: undefined label: "
        f"'nosuchlabel_{cell}' [ref.ref]",
    ]


def page_parsed_warnings(cell: str, first: int) -> list[str]:
    """What a cell's body reports when parsed as its page's markup: today's route.

    PINNED AS IT IS, defects included: a cross cell's body is mis-parsed silently (no
    warning at all); the undefined label of an RST page's content is reported at the
    line of its role WITHIN the content; and a MyST page reports its content at about
    twice the directive's line (#2144).
    """
    if cell == "rr":
        role = at(RST_BODY, ":nosuchrole:")
        return [
            f"<srcdir>/index.rst:{first + at(RST_BODY, '.. nosuchdirective')}: ERROR: "
            'Unknown directive type "nosuchdirective".\n\n.. nosuchdirective:: [docutils]',
            f"<srcdir>/index.rst:{first + role}: ERROR: Unknown interpreted text role "
            '"nosuchrole". [docutils]',
            f"<srcdir>/index.rst:{role + 1}: WARNING: undefined label: "
            "'nosuchlabel_rr' [ref.ref]",
        ]
    if cell == "mm":
        role = 2 * first + at(MYST_BODY, "{nosuchrole}")
        empty_note = 2 * first + MYST_BODY.index(
            "```{note}", at(MYST_BODY, "{nosuchrole}")
        )
        return [
            f"<srcdir>/a_host_md.md:{2 * first + at(MYST_BODY, '```{nosuchdirective}')}: "
            "WARNING: Unknown directive type: 'nosuchdirective' [myst.directive_unknown]",
            f"<srcdir>/a_host_md.md:{role}: WARNING: Unknown interpreted text role "
            '"nosuchrole". [myst.role_unknown]',
            f"<srcdir>/a_host_md.md:{empty_note}: ERROR: Content block expected for "
            'the "note" directive; none found. [docutils]',
            f"<srcdir>/a_host_md.md:{role}: WARNING: undefined label: "
            "'nosuchlabel_mm' [ref.ref]",
        ]
    return []


SPLIT_PADDING = [
    (Path(f"b_pad_{n}.rst"), f":orphan:\n\nPad {n}\n=====\n") for n in range(4)
]
"""``-j 2`` reads the sorted documents in two chunks, ``a_host_md, b_pad_0, b_pad_1``
and ``b_pad_2, b_pad_3, index``: the two importing pages are read by different workers."""


def matrix_param(mode: str, parallel: bool = False) -> Any:
    flag, option, _ = MODES[mode]
    files, _ = matrix_files(option)
    params: dict[str, Any] = {
        "buildername": "html",
        "files": files,
        "confoverrides": {FLAG: flag},
    }
    if not parallel:
        return pytest.param(params, id=mode)
    return pytest.param(
        {**params, "files": [*files, *SPLIT_PADDING], "parallel": 2},
        id=f"{mode}-j2",
        marks=pytest.mark.skipif(
            not parallel_available, reason="Parallel execution not supported"
        ),
    )


@pytest.mark.parametrize(
    "test_app",
    [*(matrix_param(mode) for mode in MODES), matrix_param("flag_on", parallel=True)],
    indirect=True,
)
def test_the_matrix(test_app: SphinxTestApp, request: pytest.FixtureRequest):
    """(1), (6): page markup x record doctype, under the flag, the option and neither.

    Parsed by its doctype, a body renders as its own markup in either page, and its
    diagnostics are at the directive's line plus the content line's index, in both page
    markups. Parsed as the page's markup -- the flag off, or the option off -- the two
    cross cells are mis-rendered, as they always were (pinned). The need records the
    record's ``doctype``, the importing page and the directive's line, either way. A
    ``-j 2`` build, the two importing pages read by different workers, gives the same.
    """
    app = test_app
    mode = request.node.callspec.id.removesuffix("-j2")
    _, option, parsed_by_doctype = MODES[mode]
    _, linenos = matrix_files(option)
    app.build()

    expected = []
    for cell, (host, doctype) in MATRIX_CELLS.items():
        if parsed_by_doctype:
            expected += by_doctype_warnings(host, doctype, linenos[cell], cell)
        else:
            expected += page_parsed_warnings(cell, linenos[cell])
    assert sorted(build_warnings(app)) == sorted(expected)

    needs = needs_by_id(app)
    for cell, (host, doctype) in MATRIX_CELLS.items():
        need = needs[imp_id(cell)]
        assert (need["docname"], need["lineno"], need["doctype"]) == (
            Path(host).stem,
            linenos[cell],
            doctype,
        ), cell

    for cell, (host, doctype) in MATRIX_CELLS.items():
        content = need_content_html(
            app, Path(host).with_suffix(".html").name, imp_id(cell)
        )
        page_markup = Path(host).suffix
        index = "" if host == "index.rst" else "index.html"
        if parsed_by_doctype or doctype == page_markup:
            # parsed by its own markup: its directive, its link, its role to a page need
            assert '<div class="admonition note">' in content, cell
            assert f'href="{index}#REQ_HOST"' in content, cell
            assert f'href="{index}#hostlabel"' in content, cell
            if doctype == ".md":
                assert (
                    '<a class="reference external" href="https://example.com">'
                    "ref link</a>" in content
                ), cell
        elif doctype == ".md":
            # MyST parsed as reStructuredText: roles and links literal, fences as code
            assert "admonition" not in content, cell
            assert "{need}`REQ_HOST`, a [ref link][lnk]." in content, cell
            assert '<span class="pre">`{note}</span>' in content, cell
        else:
            # reStructuredText parsed as MyST: directives as paragraphs, roles as code
            assert "admonition" not in content, cell
            assert "<p>.. note:: An RST note.</p>" in content, cell
            assert ":need:<code" in content, cell


# ------------------------------------------------------------------------------------
# (2) a doctype this project does not parse: the page's markup, and one warning

NO_MYST_CONF = (
    "import sys\n"
    "from pathlib import Path\n\n"
    "sys.path.insert(0, str(Path(__file__).parent))\n"
    'extensions = ["sphinx_needs", "plain_ext"]\n'
    + NEEDS_TYPES
    + 'source_suffix = {".rst": "restructuredtext", ".nope": "nope"}\n'
)
"""No myst-parser, so nothing registers ``.md``; ``.nope`` maps to a file type no
parser is registered for; ``.plain`` (registered by ``plain_ext``) to a parser that is
neither reStructuredText nor MyST."""

FALLBACK_CONTENT = "Some *emphasis* and a `link <https://example.com>`_."
"""reStructuredText, whatever its record declares: how it renders shows the parser."""

FALLBACK_RECORDS = [
    record("FB_MD_1", FALLBACK_CONTENT, doctype=".md"),
    record("FB_NOPE", FALLBACK_CONTENT, doctype=".nope"),
    record("FB_MD_2", FALLBACK_CONTENT, doctype=".md"),
    record("FB_PLAIN", FALLBACK_CONTENT, doctype=".plain"),
    # blank content: nothing is parsed, so nothing is reported for its doctype
    record("FB_TXT_BLANK", "", doctype=".txt"),
    record("FB_YAML_BLANK", " \n ", doctype=".yaml"),
    # ...but another need of the same doctype with content is
    record("FB_MD_BLANK", "", doctype=".md"),
    record("FB_RST", FALLBACK_CONTENT, doctype=".rst"),
]

FALLBACK_INDEX = [
    "Fallback",
    "========",
    "",
    ".. needimport:: fallback.json",
    "",
    ".. needimport:: fallback.json",
    "   :id_prefix: P_",
    "",
]

FALLBACK_FILES = [
    (Path("conf.py"), NO_MYST_CONF),
    (Path("plain_ext.py"), PLAIN_EXT),
    (Path("index.rst"), "\n".join(FALLBACK_INDEX)),
    (Path("fallback.json"), needs_json(FALLBACK_RECORDS)),
]


def fallback_warnings(line: int) -> list[str]:
    """The ``needs.import_doctype`` warnings of one directive, at ``line``."""
    registered = "'.nope', '.plain', '.rst'"
    reasons = {
        ".md": f"'.md' is not a registered source suffix (registered: {registered})",
        ".nope": "'.nope' maps to file type 'nope', which has no registered parser "
        f"(registered suffixes: {registered})",
        ".plain": "'.plain' is parsed by plain_ext.PlainTextParser "
        f"(registered suffixes: {registered})",
    }
    return [
        f"<srcdir>/index.rst:{line}: WARNING: Imported needs declare doctype "
        f"{doctype!r}, which no parser of this project claims ({reason}); their "
        "content was parsed as this page's markup instead. Add the suffix to "
        "source_suffix with a reStructuredText or MyST parser, or set "
        ":parse_by_doctype: false. [needs.import_doctype]"
        for doctype, reason in reasons.items()
    ]


@pytest.mark.parametrize(
    "test_app",
    [
        pytest.param(
            {
                "buildername": "html",
                "files": FALLBACK_FILES,
                "confoverrides": {FLAG: True},
            },
            id="warned",
        ),
        pytest.param(
            {
                "buildername": "html",
                "files": FALLBACK_FILES,
                "confoverrides": {
                    FLAG: True,
                    "suppress_warnings": ["needs.import_doctype"],
                },
            },
            id="suppressed",
        ),
    ],
    indirect=True,
)
def test_a_doctype_the_project_does_not_parse(
    test_app: SphinxTestApp, request: pytest.FixtureRequest
):
    """(2): the needs are kept, their content parsed as the page's markup, and one
    ``needs.import_doctype`` per directive per such doctype is reported at the
    directive -- none for a doctype whose needs have no content; ``suppress_warnings``
    silences it. The need records the record's ``doctype`` all the same.
    """
    app = test_app
    app.build()

    if request.node.callspec.id == "suppressed":
        assert build_warnings(app) == []
    else:
        # in the order the doctypes are first met in the import
        assert build_warnings(app) == [
            *fallback_warnings(line_of(FALLBACK_INDEX, "needimport")),
            *fallback_warnings(line_of(FALLBACK_INDEX, ":id_prefix:") - 1),
        ]

    needs = needs_by_id(app)
    imported = [r["id"] for r in FALLBACK_RECORDS]
    assert sorted(needs) == sorted([*imported, *(f"P_{i}" for i in imported)])
    for r in FALLBACK_RECORDS:
        for need_id in (r["id"], f"P_{r['id']}"):
            assert needs[need_id]["doctype"] == r["doctype"], need_id
            if r["content"].strip():
                content = need_content_html(app, "index.html", need_id)
                assert "Some <em>emphasis</em> and a " in content, need_id
                assert (
                    '<a class="reference external" href="https://example.com">'
                    "link</a>" in content
                ), need_id


# ------------------------------------------------------------------------------------
# (3) a doctype that says nothing, and the ``needs_json_remove_defaults`` round trip

SILENT_CONTENT = "A [link](https://example.com/md) and `code`."
"""MyST, whatever its record declares: how it renders shows the parser."""

SILENT_RECORDS = [
    record("SI_EMPTY", SILENT_CONTENT, doctype=""),
    record("SI_MISSING", SILENT_CONTENT),
    record("SI_NULL", SILENT_CONTENT, doctype=None),
    record("SI_INT", SILENT_CONTENT, doctype=3),
]

SILENT_INDEX = ["Silent", "======", "", ".. toctree::", "", "   a_host_md", ""]
SILENT_INDEX += rst_import("silent.json", {})
SILENT_MD = ["# Silent (MyST)", "", *md_import("silent.json", {"id_prefix": "M_"})]


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "files": [
                (Path("conf.py"), CONF),
                (Path("index.rst"), "\n".join(SILENT_INDEX)),
                (Path("a_host_md.md"), "\n".join(SILENT_MD)),
                (Path("silent.json"), needs_json(SILENT_RECORDS)),
            ],
            "confoverrides": {FLAG: True},
        }
    ],
    indirect=True,
)
def test_a_doctype_that_says_nothing(test_app: SphinxTestApp):
    """(3): an empty, missing, ``null`` or non-``str`` doctype is the page's markup,
    silently -- no warning, and no crash on the way (a ``MarkupContent`` refuses such a
    markup with a ``ValueError``, which needimport does not catch)."""
    app = test_app
    app.build()
    assert build_warnings(app) == []

    needs = needs_by_id(app)
    for prefix, page, suffix in (
        ("", "index.html", ".rst"),
        ("M_", "a_host_md.html", ".md"),
    ):
        recorded = {r["id"]: needs[prefix + r["id"]]["doctype"] for r in SILENT_RECORDS}
        # a missing or ``null`` doctype is the page's suffix, as for any need that
        # declares none; the others are kept as the record has them
        assert recorded == {
            "SI_EMPTY": "",
            "SI_MISSING": suffix,
            "SI_NULL": suffix,
            "SI_INT": 3,
        }, page
        for r in SILENT_RECORDS:
            content = need_content_html(app, page, prefix + r["id"])
            if suffix == ".md":
                assert (
                    '<a class="reference external" href="https://example.com/md">link</a>'
                    in content
                ), r["id"]
            else:
                assert "A [link](<a class" in content, r["id"]


ROUND_TRIP_BODIES = {
    ".rst": [
        "An RST `link <https://example.com/rst>`_ and ``code_rst``.",
        "",
        ".. note:: An RST note.",
    ],
    ".md": [
        "A MyST [link](https://example.com/md) and `code_md`.",
        "",
        "```{note}",
        "A MyST note.",
        "```",
    ],
}
"""A link, inline code and a ``note``: each renders differently in the other parser."""

EXPORT_INDEX = [
    "Export",
    "======",
    "",
    ".. toctree::",
    "",
    "   a_host_md",
    "",
    ".. spec:: Exported from RST",
    "   :id: EXP_RST",
    "",
    *(f"   {line}".rstrip() for line in ROUND_TRIP_BODIES[".rst"]),
    "",
]
EXPORT_MD = [
    "# Export (MyST)",
    "",
    "```{spec} Exported from MyST",
    ":id: EXP_MD",
    "",
    *ROUND_TRIP_BODIES[".md"],
    "```",
    "",
]

IMPORT_INDEX = ["Import", "======", "", ".. toctree::", "", "   a_host_md", ""]
IMPORT_INDEX += rst_import("exported.json", {"ids": "EXP_MD"})
IMPORT_MD = ["# Import (MyST)", "", *md_import("exported.json", {"ids": "EXP_RST"})]


def assert_rendered_in(markup: str, content: str) -> None:
    """``content`` is the HTML of a ``ROUND_TRIP_BODIES[markup]`` parsed as ``markup``."""
    name = markup.removeprefix(".")
    assert (
        f'<a class="reference external" href="https://example.com/{name}">link</a>'
        in content
    )
    assert f'<span class="pre">code_{name}</span></code>' in content
    assert '<div class="admonition note">' in content


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "files": [
                (Path("conf.py"), CONF + "needs_json_remove_defaults = True\n"),
                (Path("index.rst"), "\n".join(EXPORT_INDEX)),
                (Path("a_host_md.md"), "\n".join(EXPORT_MD)),
            ],
        }
    ],
    indirect=True,
)
def test_a_remove_defaults_export_round_trips(
    test_app: SphinxTestApp, make_app: Any, tmp_path: Path
):
    """(3): ``needs_json_remove_defaults`` drops a ``.rst`` doctype from the export --
    it is the schema's default -- and keeps ``.md``; needimport restores the first from
    the file's ``needs_schema``. So each need of such an export, imported into a page
    of the other markup, is parsed in the markup it was written in."""
    exporter = test_app
    exporter.build()
    assert build_warnings(exporter) == []
    exported = Path(exporter.outdir, "needs.json").read_text(encoding="utf-8")
    version = json.loads(exported)["versions"]
    needs = next(iter(version.values()))
    assert "doctype" not in needs["needs"]["EXP_RST"]
    assert needs["needs"]["EXP_MD"]["doctype"] == ".md"
    assert needs["needs_schema"]["properties"]["doctype"]["default"] == ".rst"
    # one application at a time: a second one set up while the first is alive
    # registers Sphinx's nodes again, with a warning each
    exporter.cleanup()

    srcdir = tmp_path / "importer"
    srcdir.mkdir()
    for name, text in (
        ("conf.py", CONF),
        ("index.rst", "\n".join(IMPORT_INDEX)),
        ("a_host_md.md", "\n".join(IMPORT_MD)),
        ("exported.json", exported),
    ):
        Path(srcdir, name).write_text(text, encoding="utf-8")
    importer = make_app(buildername="html", srcdir=srcdir, confoverrides={FLAG: True})
    try:
        importer.build()
        assert build_warnings(importer) == []
        imported = needs_by_id(importer)
        assert imported["EXP_RST"]["doctype"] == ".rst"
        assert imported["EXP_MD"]["doctype"] == ".md"
        assert_rendered_in(
            ".rst", need_content_html(importer, "a_host_md.html", "EXP_RST")
        )
        assert_rendered_in(".md", need_content_html(importer, "index.html", "EXP_MD"))
    finally:
        importer.cleanup()


# ------------------------------------------------------------------------------------
# (4) interactions: jinja_content, templates, id_prefix

INTERACTION_RECORDS = [
    record(
        "J1",
        "Hello {{ 'JIN' + 'JA' }} and a [jlink](https://example.com/j).",
        doctype=".md",
        jinja_content=True,
    ),
    record("TR", "Body [blink](https://example.com/b).", doctype=".md", template="tpl"),
    record("MD1", "Body [mlink](https://example.com/m).", doctype=".md"),
    record("REF", "See {need}`MD1`.", doctype=".md"),
]

TEMPLATES = {
    "tpl": "**TPL bold** and a `tlink <https://example.com/t>`_, then: {{content}}",
    "pre": "A `prelink <https://example.com/pre>`_.",
}
"""Templates of the importing project: reStructuredText, as its pages are."""

INTERACTION_INDEX = ["Interactions", "============", ""]
INTERACTION_INDEX += rst_import("interactions.json", {"ids": "J1, TR"})
INTERACTION_INDEX += rst_import(
    "interactions.json", {"ids": "MD1", "id_prefix": "T_", "template": "tpl"}
)
INTERACTION_INDEX += rst_import(
    "interactions.json", {"ids": "MD1", "id_prefix": "PRE_", "pre_template": "pre"}
)
INTERACTION_INDEX += rst_import(
    "interactions.json", {"ids": "MD1, REF", "id_prefix": "P_"}
)


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "files": [
                (Path("conf.py"), CONF),
                (Path("index.rst"), "\n".join(INTERACTION_INDEX)),
                (Path("interactions.json"), needs_json(INTERACTION_RECORDS)),
                *(
                    (Path("needs_templates", f"{name}.need"), text)
                    for name, text in TEMPLATES.items()
                ),
            ],
            "confoverrides": {FLAG: True},
        }
    ],
    indirect=True,
)
def test_jinja_templates_and_id_prefix(test_app: SphinxTestApp):
    """(4): ``jinja_content`` text is rendered, then parsed in the record's doctype;
    a need rendered through a template -- the record's ``template`` or the directive's
    ``:template:`` -- is parsed as the page's markup, the template's, content and all;
    a ``:pre_template:`` is the page's markup and the content its doctype's; and
    ``:id_prefix:`` rewrites a ``{need}`` role in MyST content, which then resolves."""
    app = test_app
    app.build()
    assert build_warnings(app) == []

    def link(text: str) -> str:
        """An external link to ``https://example.com/<text without "link">``."""
        path = text.removesuffix("link")
        return f'<a class="reference external" href="https://example.com/{path}">{text}</a>'

    # rendered by Jinja, then parsed as MyST
    content = need_content_html(app, "index.html", "J1")
    assert f"Hello JINJA and a {link('jlink')}" in content
    # through a template: the template's reStructuredText renders, and so the content
    # in it is parsed as reStructuredText too
    for need_id, body_link in (("TR", "blink"), ("T_MD1", "mlink")):
        content = need_content_html(app, "index.html", need_id)
        assert f"<strong>TPL bold</strong> and a {link('tlink')}" in content, need_id
        assert f"then: Body [{body_link}](<a class" in content, need_id
    # a pre template is parsed as the page's markup, the content as its doctype's
    page = html(app, "index.html")
    assert f"A {link('prelink')}." in page
    assert f"Body {link('mlink')}." in need_content_html(app, "index.html", "PRE_MD1")
    # the prefixed id in a MyST role
    assert '<a class="reference internal" href="#P_MD1"' in need_content_html(
        app, "index.html", "P_REF"
    )
    assert needs_by_id(app)["P_REF"]["content"] == "See {need}`P_MD1`."


# ------------------------------------------------------------------------------------
# (7) the flag is read when the pages are: changing it re-reads them

ONE_IMPORT_INDEX = ["One import", "==========", "", *rst_import("one.json", {})]
ONE_IMPORT_FILES = [
    (Path("index.rst"), "\n".join(ONE_IMPORT_INDEX)),
    (
        Path("one.json"),
        needs_json([record("ONE", "\n".join(ROUND_TRIP_BODIES[".md"]), doctype=".md")]),
    ),
]


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "files": [(Path("conf.py"), CONF), *ONE_IMPORT_FILES],
            "confoverrides": {FLAG: False},
        }
    ],
    indirect=True,
)
def test_changing_the_flag_rereads_the_importing_page(
    test_app: SphinxTestApp, make_app: Any
):
    """(7): an incremental build that changes only the flag re-reads the importing
    page, so its content follows the flag; nothing else in the project changed."""
    app = test_app
    app.build()
    assert "admonition" not in need_content_html(app, "index.html", "ONE")
    app.cleanup()

    again = make_app(
        buildername="html",
        srcdir=app.srcdir,
        builddir=Path(app.outdir).parent,
        confoverrides={FLAG: True},
    )
    try:
        again.build()
        assert build_warnings(again) == []
        assert_rendered_in(".md", need_content_html(again, "index.html", "ONE"))
    finally:
        again.cleanup()


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "files": [
                (Path("conf.py"), CONF + 'needs_from_toml = "ubproject.toml"\n'),
                (Path("ubproject.toml"), "[needs]\nimport_parse_by_doctype = true\n"),
                *ONE_IMPORT_FILES,
            ],
        }
    ],
    indirect=True,
)
def test_the_flag_in_ubproject_toml(test_app: SphinxTestApp):
    """``[needs] import_parse_by_doctype`` in ``ubproject.toml`` is the flag."""
    test_app.build()
    assert build_warnings(test_app) == []
    assert_rendered_in(".md", need_content_html(test_app, "index.html", "ONE"))
