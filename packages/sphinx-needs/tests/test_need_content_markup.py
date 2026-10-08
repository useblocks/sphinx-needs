"""``add_need(content=MarkupContent(...))`` and ``ingest_need_record``.

A need's content can be written in a markup that is not its page's -- a source comment,
an imported file -- and is then parsed by the parser the project registers for that
markup's suffix, bound to the page, with its diagnostics at the file and line the content
came from. The matrix is (page markup) x (content markup), all four cells.

The projects are built inline (``files``), each with a test-only driver extension
(:data:`DRIVER`) written into the project and loaded by its ``conf.py``: it calls the
public API the way an extension would. Bodies use constructs the other parser renders
differently, so parsing a body with the wrong parser is visible in the HTML.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

import myst_parser
import pytest
from docutils import nodes
from sphinx.testing.util import SphinxTestApp
from sphinx.util.parallel import parallel_available

from sphinx_needs.api import MarkupContent, get_needs_view
from sphinx_needs_testkit import build_warnings
from tests.util import needs_by_id

MYST_MAJOR = int(myst_parser.__version__.split(".")[0])
"""myst-parser 5 logs its own warnings at ``(env.docname, line)``; 4 at
``(document["source"], line)``, which Sphinx then reads as a docname."""

DRIVER = '''\
"""Test-only driver: creates needs through the public content-markup API."""

from __future__ import annotations

import json
from pathlib import Path

from docutils.parsers import Parser
from docutils.parsers.rst import directives
from docutils.statemachine import StringList
from sphinx.util import logging
from sphinx.util.docutils import SphinxDirective

from sphinx_needs.api import (
    InvalidNeedException,
    MarkupContent,
    add_need,
    ingest_need_record,
)
from sphinx_needs.need_item import NeedItemSourceImport

logger = logging.getLogger(__name__)


class TestNeedContent(SphinxDirective):
    """One need whose content is written in ``:markup:``, as if from ``:source:``."""

    has_content = True
    option_spec = {
        "markup": directives.unchanged_required,
        "source": directives.unchanged_required,
        "first-line": directives.positive_int,
        "type": directives.unchanged_required,
        "title": directives.unchanged_required,
        "id": directives.unchanged_required,
        "links": directives.unchanged,
        "jinja": directives.flag,
        "resolved-lineno": directives.flag,
        "crlf": directives.flag,
    }

    def run(self):
        kwargs = {}
        if "jinja" in self.options:
            kwargs["jinja_content"] = True
        content = (
            StringList([f"{line}\\r" for line in self.content])
            if "crlf" in self.options
            else self.content
        )
        if "markup" in self.options:
            source = None
            if "source" in self.options:
                path = Path(self.env.srcdir, self.options["source"])
                source = (str(path), self.options.get("first-line", 1))
            content = MarkupContent(
                content, markup=self.options["markup"], source=source
            )
        if "links" in self.options:
            kwargs["links"] = self.options["links"]
        # the parser's line, as a need directive's ``parser_lineno``, needimport and
        # sphinx-codelinks pass it; ``:resolved-lineno:`` passes the file line instead
        lineno = self.lineno
        if "resolved-lineno" in self.options:
            lineno = self.get_source_info()[1] or lineno
        try:
            return add_need(
                self.env.app,
                self.state,
                self.env.docname,
                lineno,
                need_type=self.options["type"],
                title=self.options["title"],
                id=self.options["id"],
                content=content,
                lineno_content=self.content_offset + 1,
                **kwargs,
            )
        except InvalidNeedException as err:
            logger.warning(
                f"Need could not be created: {err.message}",
                type="needs",
                subtype="test_need_content",
                location=self.get_location(),
            )
            return []


class TestIngestRecords(SphinxDirective):
    """Needs from a JSON list of ``{"need": <record>, "source": {"path", "line"}}``.

    Each record's ``doctype`` is its content markup; failures and unknown keys are
    reported as needimport reports them: the keys of every record, collected through
    ``unknown_keys``, and those returned for the needs created.
    """

    required_arguments = 1
    option_spec = {"resolved-lineno": directives.flag}

    def run(self):
        path = Path(self.env.srcdir, self.arguments[0])
        self.env.note_dependency(str(path))
        entries = json.loads(path.read_text(encoding="utf-8"))
        lineno = self.lineno
        if "resolved-lineno" in self.options:
            lineno = self.get_source_info()[1] or lineno
        need_source = NeedItemSourceImport(
            docname=self.env.docname, lineno=lineno, path=str(path)
        )
        result = []
        unknown = set()
        returned = set()
        for entry in entries:
            record = entry["need"]
            source = entry.get("source")
            try:
                need_nodes, dropped = ingest_need_record(
                    self.env.app,
                    self.state,
                    record,
                    need_source=need_source,
                    content_markup=record.get("doctype"),
                    content_source=(
                        (str(Path(self.env.srcdir, source["path"])), source["line"])
                        if source
                        else None
                    ),
                    unknown_keys=unknown,
                )
            except InvalidNeedException as err:
                logger.warning(
                    f"Need {record.get('id')!r} could not be imported: {err.message}",
                    type="needs",
                    subtype="test_ingest_records",
                    location=self.get_location(),
                )
            else:
                returned |= dropped
                result.extend(need_nodes)
        if unknown:
            logger.warning(
                f"Unknown keys in records: {sorted(unknown)!r}; "
                f"returned for the needs created: {sorted(returned)!r}",
                type="needs",
                subtype="test_ingest_records",
                location=self.get_location(),
            )
        return result


class PlainTextParser(Parser):
    """A parser that is neither reStructuredText nor MyST."""

    supported = ("plaintext",)

    def parse(self, inputstring, document):
        pass


def setup(app):
    app.add_directive("test-need-content", TestNeedContent)
    app.add_directive("test-ingest-records", TestIngestRecords)
    app.add_source_suffix(".plain", "plaintext")
    app.add_source_parser(PlainTextParser)
    return {"parallel_read_safe": True, "parallel_write_safe": True}
'''

CONF = """\
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
extensions = ["myst_parser", "sphinx_needs", "needcontent_ext"]
needs_types = [
    dict(directive="req", title="Requirement", prefix="R_", color="#BFD8D2", style="node"),
    dict(directive="spec", title="Specification", prefix="S_", color="#FEDCD2", style="node"),
]
needs_id_regex = r"^[A-Za-z0-9_]+$"
needs_build_json = True
needs_json_remove_defaults = False
source_suffix = {".rst": "restructuredtext", ".md": "markdown", ".nope": "nope"}
show_warning_types = True
"""
"""``.nope`` maps to a file type no parser is registered for; ``.plain`` (registered
by the driver) to a parser that is neither reStructuredText nor MyST."""

RST_BODY = [
    "Some *emphasis*, :ref:`host <hostlabel>`, :need:`REQ_HOST`.",
    "",
    ".. note:: An RST note.",
    "",
    ".. _inside_{cell}:",
    "",
    "A labelled paragraph.",
    "",
    ".. nosuchdirective::",
    "",
    ":nosuchrole:`x` and :ref:`nosuchlabel_{cell}`.",
]
"""A reStructuredText body; ``{cell}`` names the cell."""

MYST_BODY = [
    "Some *emphasis*, {ref}`host <hostlabel>`, {need}`REQ_HOST`, a [ref link][lnk].",
    "",
    "```{note}",
    "A MyST note.",
    "```",
    "",
    "(inside_{cell})=",
    "A labelled paragraph.",
    "",
    "```{nosuchdirective}",
    "```",
    "",
    "{nosuchrole}`x` and {ref}`nosuchlabel_{cell}`.",
    "",
    "```{note}",
    "```",
    "",
    "[lnk]: https://example.com",
]
"""A MyST body; the empty ``note`` is an error docutils itself reports."""

BODIES = {".rst": RST_BODY, ".md": MYST_BODY}


def at(body: list[str], start: str) -> int:
    """The 0-based offset of the first body line starting with ``start``."""
    return next(i for i, line in enumerate(body) if line.startswith(start))


def src(name: str) -> str:
    """A content file's path as warnings print it under ``<srcdir>/``."""
    return str(Path("src", name))


def rst_need(
    need_id: str, body: list[str], options: dict[str, Any], cell: str = ""
) -> list[str]:
    """A ``test-need-content`` directive in a reStructuredText page."""
    lines = [".. test-need-content::"]
    lines += [f"   :{k}: {v}" for k, v in options.items()]
    lines += ["   :type: spec", f"   :title: {need_id}", f"   :id: {need_id}", ""]
    lines += [f"   {line}".rstrip() for line in body]
    return [line.replace("{cell}", cell) for line in lines] + [""]


def md_need(
    need_id: str, body: list[str], options: dict[str, Any], cell: str = ""
) -> list[str]:
    """A ``test-need-content`` directive in a MyST page."""
    lines = ["````{test-need-content}"]
    lines += [f":{k}: {v}" for k, v in options.items()]
    lines += [":type: spec", f":title: {need_id}", f":id: {need_id}", ""]
    lines += body
    lines += ["````"]
    return [line.replace("{cell}", cell) for line in lines] + [""]


CELLS = {
    # cell: (host page, content markup, content file, first line)
    "rr": ("index.rst", ".rst", "a.c", 100),
    "mr": ("index.rst", ".md", "b.c", 200),
    "rm": ("a_host_md.md", ".rst", "c.c", 300),
    "mm": ("a_host_md.md", ".md", "d.c", 400),
}
"""The four cells: RST/MyST content in an RST page, RST/MyST content in a MyST page."""


def cell_id(cell: str) -> str:
    return f"SPEC_{cell.upper()}"


def four_cell_files() -> tuple[list[tuple[Path, str]], dict[str, int]]:
    """The four-cell project, and the line each cell's directive is on."""
    index = [
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
    host_md = ["# MyST host", ""]
    linenos = {}
    for cell, (host, markup, name, first) in CELLS.items():
        options = {
            "markup": markup,
            "source": f"src/{name}",
            "first-line": first,
            "links": "REQ_HOST",
        }
        page = index if host == "index.rst" else host_md
        linenos[cell] = len(page) + 1
        build = rst_need if host == "index.rst" else md_need
        page += build(cell_id(cell), BODIES[markup], options, cell)
    # a label in content resolves from its own page, and from another page
    index += [
        "Refs: :ref:`rr <inside_rr>`, :ref:`mr <inside_mr>`, "
        ":ref:`rm <inside_rm>`, :ref:`mm <inside_mm>`.",
        "",
    ]
    host_md += [
        "Refs: {ref}`rr <inside_rr>`, {ref}`mr <inside_mr>`, "
        "{ref}`rm <inside_rm>`, {ref}`mm <inside_mm>`.",
        "",
    ]
    files = [
        (Path("conf.py"), CONF),
        (Path("needcontent_ext.py"), DRIVER),
        (Path("index.rst"), "\n".join(index)),
        (Path("a_host_md.md"), "\n".join(host_md)),
    ]
    return files, linenos


FOUR_CELL_FILES, FOUR_CELL_LINENOS = four_cell_files()


def myst_logged(host: str, source: str, line: int) -> str:
    """Where a warning myst-parser logs itself points, for content from ``source``.

    Not the content's file: this version does not rewrite myst-parser's own locations.
    myst-parser 5 logs the page being read, with the content's line; myst-parser 4 logs
    ``document["source"]`` -- the content's file for the duration -- which Sphinx reads
    as a docname and gives the ``.rst`` suffix (the documented first-slice defect).
    """
    if MYST_MAJOR >= 5:
        return f"<srcdir>/{host}:{line}"
    return f"<srcdir>/{source}.rst:{line}"


def four_cell_warnings(cells: tuple[str, ...] = tuple(CELLS)) -> list[str]:
    """Every warning the four-cell project emits for ``cells``."""
    expected = []
    for cell in cells:
        host, markup, name, first = CELLS[cell]
        if markup == ".rst":
            directive = first + at(RST_BODY, ".. nosuchdirective")
            role = first + at(RST_BODY, ":nosuchrole:")
            expected += [
                f"<srcdir>/{src(name)}:{directive}: ERROR: Unknown directive type "
                '"nosuchdirective".\n\n.. nosuchdirective:: [docutils]',
                f"<srcdir>/{src(name)}:{role}: ERROR: Unknown interpreted text role "
                '"nosuchrole". [docutils]',
                f"<srcdir>/{src(name)}:{role}: WARNING: undefined label: "
                f"'nosuchlabel_{cell}' [ref.ref]",
            ]
        else:
            directive = first + at(MYST_BODY, "```{nosuchdirective}")
            role = first + at(MYST_BODY, "{nosuchrole}")
            empty_note = first + MYST_BODY.index(
                "```{note}", at(MYST_BODY, "{nosuchrole}")
            )
            expected += [
                f"{myst_logged(host, src(name), directive)}: WARNING: Unknown directive "
                "type: 'nosuchdirective' [myst.directive_unknown]",
                f"{myst_logged(host, src(name), role)}: WARNING: Unknown interpreted text "
                'role "nosuchrole". [myst.role_unknown]',
                f"<srcdir>/{src(name)}:{empty_note}: ERROR: Content block expected "
                'for the "note" directive; none found. [docutils]',
                f"<srcdir>/{src(name)}:{role}: WARNING: undefined label: "
                f"'nosuchlabel_{cell}' [ref.ref]",
            ]
    return expected


def html(app: SphinxTestApp, page: str) -> str:
    return Path(app.outdir, page).read_text(encoding="utf-8")


def need_content_html(app: SphinxTestApp, page: str, need_id: str) -> str:
    """The HTML of the content cell of the need ``need_id``."""
    text = html(app, page)
    start = text.index('<td class="need content"', text.index(f'id="{need_id}"'))
    return text[start : text.index("</td>", start)]


SPLIT_PADDING = [
    (Path(f"b_pad_{n}.rst"), f":orphan:\n\nPad {n}\n=====\n") for n in range(4)
]
"""``-j 2`` reads the sorted documents in two chunks (``sphinx.util.parallel.make_chunks``):
``a_host_md, b_pad_0, b_pad_1`` and ``b_pad_2, b_pad_3, index``, so the two pages with
content are read by different workers, and each resolves the other's labels."""


@pytest.mark.parametrize(
    "test_app",
    [
        pytest.param({"buildername": "html", "files": FOUR_CELL_FILES}, id="serial"),
        pytest.param(
            {
                "buildername": "html",
                "files": [*FOUR_CELL_FILES, *SPLIT_PADDING],
                "parallel": 2,
            },
            id="j2",
            marks=pytest.mark.skipif(
                not parallel_available, reason="Parallel execution not supported"
            ),
        ),
    ],
    indirect=True,
)
def test_content_is_parsed_in_its_markup_with_diagnostics_at_its_source(
    test_app: SphinxTestApp,
):
    """(a)-(e), (i): every cell of page markup x content markup, serial and ``-j 2``.

    The body renders in its declared markup; every docutils-level diagnostic names the
    content's file and line (``first_line`` + the body line's offset); the need is
    recorded on the page and line of the directive that created it, with the declared
    markup as its ``doctype``; links, roles and references reach into the page; and a
    label in a body registers with its page, so the page and another page resolve it.
    """
    app = test_app
    app.build()

    assert sorted(build_warnings(app)) == sorted(four_cell_warnings())

    needs = needs_by_id(app)
    assert sorted(needs) == sorted(["REQ_HOST", *(cell_id(c) for c in CELLS)])
    for cell, (host, markup, _, _) in CELLS.items():
        need = needs[cell_id(cell)]
        # (c) the need belongs to the page and the directive; the doctype is the markup
        assert (need["docname"], need["lineno"], need["doctype"]) == (
            Path(host).stem,
            FOUR_CELL_LINENOS[cell],
            markup,
        ), cell
        # (d) a link option naming a page need
        assert need["links"] == ["REQ_HOST"], cell
        # the recorded content is the body as written
        assert need["content"] == "\n".join(BODIES[markup]).replace("{cell}", cell)

    for cell, (host, markup, _, _) in CELLS.items():
        page = Path(host).with_suffix(".html").name
        index = "" if host == "index.rst" else "index.html"
        content = need_content_html(app, page, cell_id(cell))
        # (a) parsed by the declared parser: the other one renders these literally
        assert "Some <em>emphasis</em>" in content, cell
        assert '<div class="admonition note">' in content, cell
        # (d) a role to a page need and a reference to a page label; ``{ref}`` and
        # ``{need}`` work in MyST content in both pages. A ``[text](#anchor)`` link does
        # NOT in a reStructuredText page (myst-parser's ``ResolveAnchorIds`` transform runs
        # only on documents myst-parser reads): a documented gap of this version
        assert f'href="{index}#REQ_HOST"' in content, cell
        assert f'href="{index}#hostlabel"' in content, cell
        if markup == ".md":
            # a reference-style link and its definition, MyST only
            assert (
                '<a class="reference external" href="https://example.com">' in content
            )
        else:
            assert "[ref link]" not in content

    # (e) a label defined in a body resolves from its page and from the other page
    for page in ("index.html", "a_host_md.html"):
        text = html(app, page)
        for cell, (host, _, _, _) in CELLS.items():
            defined_on = Path(host).with_suffix(".html").name
            # a same-page reference, or one into the other page
            target = "" if defined_on == page else defined_on
            assert f'href="{target}#inside-{cell}"' in text, (page, cell)


def line_of(page: list[str], text: str) -> int:
    """The 1-based line of the first page line containing ``text``."""
    return next(i for i, line in enumerate(page, 1) if text in line)


LABEL_INDEX = [
    "Labels",
    "======",
    "",
    ".. toctree::",
    "",
    "   labels_md",
    "",
    ".. _duplabel:",
    "",
    "A page target.",
    "",
    *rst_need(
        "SPEC_DUP_R",
        [".. _duplabel:", "", "A body target with the page target's name."],
        {"markup": ".rst", "source": "src/e.c", "first-line": 500},
    ),
]
LABEL_MD = [
    "# Labels (MyST)",
    "",
    "(dupmd)=",
    "A page target.",
    "",
    *md_need(
        "SPEC_DUP_M",
        [".. _dupmd:", "", "A body target with the page target's name."],
        {"markup": ".rst", "source": "src/f.c", "first-line": 600},
    ),
]


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "files": [
                (Path("conf.py"), CONF),
                (Path("needcontent_ext.py"), DRIVER),
                (Path("index.rst"), "\n".join(LABEL_INDEX)),
                (Path("labels_md.md"), "\n".join(LABEL_MD)),
            ],
        }
    ],
    indirect=True,
)
def test_a_body_label_duplicating_a_page_label_is_reported_at_the_source(
    test_app: SphinxTestApp,
):
    """(e): the body is bound to the page, so docutils sees the duplicate, at the body's line."""
    app = test_app
    app.build()
    assert sorted(build_warnings(app)) == sorted(
        [
            f'<srcdir>/{src("e.c")}:500: WARNING: Duplicate explicit target name: "duplabel". [docutils]',
            f'<srcdir>/{src("f.c")}:600: WARNING: Duplicate explicit target name: "dupmd". [docutils]',
        ]
    )


CONTROL_RST_BODY = [
    "Some *emphasis* and :need:`REQ_HOST`.",
    "",
    ".. note:: An RST note.",
]
CONTROL_MD_BODY = [
    "Some *emphasis* and {need}`REQ_HOST`.",
    "",
    "```{note}",
    "A MyST note.",
    "```",
]
CONTROL_INDEX = [
    "Control",
    "=======",
    "",
    ".. toctree::",
    "",
    "   control_md",
    "",
    ".. req:: Host need",
    "   :id: REQ_HOST",
    "",
    ".. req:: A need directive",
    "   :id: REQ_PLAIN_R",
    "",
    *(f"   {line}".rstrip() for line in CONTROL_RST_BODY),
    "",
    *rst_need("SPEC_PLAIN_R", CONTROL_RST_BODY, {}),
]
CONTROL_MD = [
    "# Control (MyST)",
    "",
    "````{req} A need directive",
    ":id: REQ_PLAIN_M",
    "",
    *CONTROL_MD_BODY,
    "````",
    "",
    *md_need("SPEC_PLAIN_M", CONTROL_MD_BODY, {}),
]


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "files": [
                (Path("conf.py"), CONF),
                (Path("needcontent_ext.py"), DRIVER),
                (Path("index.rst"), "\n".join(CONTROL_INDEX)),
                (Path("control_md.md"), "\n".join(CONTROL_MD)),
            ],
        }
    ],
    indirect=True,
)
def test_without_markup_content_the_page_parser_parses_the_content(
    test_app: SphinxTestApp,
):
    """(h): content that is no ``MarkupContent`` takes the existing path, a need directive's."""
    app = test_app
    app.build()
    assert build_warnings(app) == []
    for page, plain, driven in (
        ("index.html", "REQ_PLAIN_R", "SPEC_PLAIN_R"),
        ("control_md.html", "REQ_PLAIN_M", "SPEC_PLAIN_M"),
    ):
        content = need_content_html(app, page, driven)
        assert content == need_content_html(app, page, plain)
        assert "Some <em>emphasis</em>" in content
        assert '<div class="admonition note">' in content
    needs = needs_by_id(app)
    assert needs["SPEC_PLAIN_R"]["doctype"] == ".rst"
    assert needs["SPEC_PLAIN_M"]["doctype"] == ".md"


ANCHOR_INDEX = [
    "Anchored in the page",
    "====================",
    "",
    ".. toctree::",
    "",
    "   anchor_md",
    "",
    ".. req:: Host need",
    "   :id: REQ_HOST",
    "",
    ".. _hostlabel:",
    "",
    "Host labelled paragraph.",
    "",
    *rst_need("SPEC_ANCHOR_MR", MYST_BODY, {"markup": ".md"}, "anchor_mr"),
    *rst_need("SPEC_TXT", ["Text."], {"markup": ".txt"}),
    *rst_need("SPEC_NOPE", ["Text."], {"markup": ".nope"}),
    *rst_need("SPEC_PLAIN", ["Text."], {"markup": ".plain"}),
]
ANCHOR_MD = [
    "# Anchored in the page (MyST)",
    "",
    *md_need("SPEC_ANCHOR_RM", RST_BODY, {"markup": ".rst"}, "anchor_rm"),
]


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "files": [
                (Path("conf.py"), CONF),
                (Path("needcontent_ext.py"), DRIVER),
                (Path("index.rst"), "\n".join(ANCHOR_INDEX)),
                (Path("anchor_md.md"), "\n".join(ANCHOR_MD)),
            ],
        }
    ],
    indirect=True,
)
def test_without_a_source_and_the_refusals(test_app: SphinxTestApp):
    """(f): no ``source``: the content's lines are the page's, as a directive's own.

    And what ``add_need`` refuses, before it records anything: a ``markup`` the project
    does not register, one whose file type has no parser, and one parsed by a parser
    that is neither reStructuredText nor MyST. (A ``source`` without a ``markup`` cannot
    be written: ``MarkupContent`` requires the markup.)
    """
    app = test_app
    app.build()

    mr = line_of(ANCHOR_INDEX, MYST_BODY[0])  # the body's first line in the page
    rm = line_of(ANCHOR_MD, RST_BODY[0])
    registered = "'.md', '.nope', '.plain', '.rst'"
    supported = "only reStructuredText and MyST parsers are supported."
    refused = "WARNING: Need could not be created:"
    assert sorted(build_warnings(app)) == sorted(
        [
            # MyST content in the RST page
            f"{myst_logged('index.rst', 'index.rst', mr + at(MYST_BODY, '```{nosuchdirective}'))}: WARNING: "
            "Unknown directive type: 'nosuchdirective' [myst.directive_unknown]",
            f"{myst_logged('index.rst', 'index.rst', mr + at(MYST_BODY, '{nosuchrole}'))}: WARNING: "
            'Unknown interpreted text role "nosuchrole". [myst.role_unknown]',
            f"<srcdir>/index.rst:{mr + MYST_BODY.index('```{note}', 5)}: ERROR: "
            'Content block expected for the "note" directive; none found. [docutils]',
            f"<srcdir>/index.rst:{mr + at(MYST_BODY, '{nosuchrole}')}: WARNING: "
            "undefined label: 'nosuchlabel_anchor_mr' [ref.ref]",
            # RST content in the MyST page
            f"<srcdir>/anchor_md.md:{rm + at(RST_BODY, '.. nosuchdirective')}: ERROR: "
            'Unknown directive type "nosuchdirective".\n\n.. nosuchdirective:: [docutils]',
            f"<srcdir>/anchor_md.md:{rm + at(RST_BODY, ':nosuchrole:')}: ERROR: "
            'Unknown interpreted text role "nosuchrole". [docutils]',
            f"<srcdir>/anchor_md.md:{rm + at(RST_BODY, ':nosuchrole:')}: WARNING: "
            "undefined label: 'nosuchlabel_anchor_rm' [ref.ref]",
            # the refusals, reported by the driver at its own directive
            f"<srcdir>/index.rst:{line_of(ANCHOR_INDEX, ':id: SPEC_TXT') - 4}: "
            f"{refused} Content markup '.txt' is not a registered source suffix "
            f"(registered: {registered}); {supported} [needs.test_need_content]",
            f"<srcdir>/index.rst:{line_of(ANCHOR_INDEX, ':id: SPEC_NOPE') - 4}: "
            f"{refused} Content markup '.nope' maps to file type 'nope', which has no "
            f"registered parser (registered suffixes: {registered}); {supported} "
            "[needs.test_need_content]",
            f"<srcdir>/index.rst:{line_of(ANCHOR_INDEX, ':id: SPEC_PLAIN') - 4}: "
            f"{refused} Content markup '.plain' is parsed by "
            "needcontent_ext.PlainTextParser (registered suffixes: "
            f"{registered}); {supported} [needs.test_need_content]",
        ]
    )
    # refused before the need is recorded
    assert sorted(needs_by_id(app)) == ["REQ_HOST", "SPEC_ANCHOR_MR", "SPEC_ANCHOR_RM"]
    # the page anchor changes nothing about how the content renders
    content = need_content_html(app, "index.html", "SPEC_ANCHOR_MR")
    assert '<a class="reference external" href="https://example.com">' in content


RECORDS = [
    {
        "need": {
            "type": "spec",
            "title": "An RST record",
            "id": "SPEC_REC_RST",
            "doctype": ".rst",
            "content": "Some *emphasis*, :need:`REQ_HOST`.\n\n.. nosuchdirective::",
            "links": ["REQ_HOST"],
            "unknown_key": "dropped, and reported",
            # never imported: dropped silently
            "docname": "elsewhere",
            "lineno": 99,
            "full_title": "An RST record, in full",
            "links_back": ["SPEC_ELSEWHERE"],
        },
        "source": {"path": "src/r.c", "line": 7},
    },
    {
        "need": {
            "type": "spec",
            "title": "A MyST record",
            "id": "SPEC_REC_MD",
            "doctype": ".md",
            "content": "Some *emphasis*, {need}`REQ_HOST`, a [ref link][lnk].\n\n"
            "[lnk]: https://example.com",
            "another_unknown_key": 1,
        },
        "source": {"path": "src/m.py", "line": 3},
    },
    {
        "need": {
            "type": "spec",
            "title": "A legacy record",
            "id": "SPEC_REC_LEGACY",
            "description": "Legacy *description*.",
        },
    },
    {
        "need": {
            "type": "nosuchtype",
            "title": "A record of an unknown type",
            "id": "SPEC_REC_BAD",
            "key_of_a_failed_record": 1,
        },
    },
]

RECORDS_INDEX = """\
Records
=======

.. req:: Host need
   :id: REQ_HOST

.. test-ingest-records:: records.json
"""


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "files": [
                (Path("conf.py"), CONF),
                (Path("needcontent_ext.py"), DRIVER),
                (Path("index.rst"), RECORDS_INDEX),
                (Path("records.json"), json.dumps(RECORDS, indent=2)),
            ],
        }
    ],
    indirect=True,
)
def test_ingest_need_record(test_app: SphinxTestApp):
    """(g): one need per needs.json-style record, its content in its ``doctype``.

    The record's unknown keys are returned, and added to ``unknown_keys`` before the
    need is created -- so a record that cannot be created reports them too (the driver
    warns once, naming both sets); a legacy ``description`` is the content; a record
    that cannot be created raises, and the others are still created.
    """
    app = test_app
    app.build()

    assert sorted(build_warnings(app)) == sorted(
        [
            f"<srcdir>/{src('r.c')}:9: ERROR: Unknown directive type "
            '"nosuchdirective".\n\n.. nosuchdirective:: [docutils]',
            "<srcdir>/index.rst:7: WARNING: Need 'SPEC_REC_BAD' could not be imported: "
            "Unknown need type 'nosuchtype'. [needs.test_ingest_records]",
            # the failed record's key reaches the ``unknown_keys`` set; the returned
            # sets are those of the needs created
            "<srcdir>/index.rst:7: WARNING: Unknown keys in records: "
            "['another_unknown_key', 'key_of_a_failed_record', 'unknown_key']; "
            "returned for the needs created: ['another_unknown_key', 'unknown_key'] "
            "[needs.test_ingest_records]",
        ]
    )
    needs = needs_by_id(app)
    assert sorted(needs) == [
        "REQ_HOST",
        "SPEC_REC_LEGACY",
        "SPEC_REC_MD",
        "SPEC_REC_RST",
    ]
    for need_id, doctype in (
        ("SPEC_REC_RST", ".rst"),
        ("SPEC_REC_MD", ".md"),
        # no doctype, so no content markup: the page's
        ("SPEC_REC_LEGACY", ".rst"),
    ):
        need = needs[need_id]
        assert (need["docname"], need["lineno"], need["doctype"]) == (
            "index",
            7,
            doctype,
        ), need_id
        assert need["is_import"] is True
    assert needs["SPEC_REC_RST"]["links"] == ["REQ_HOST"]
    assert needs["SPEC_REC_LEGACY"]["content"] == "Legacy *description*."
    assert "Some <em>emphasis</em>" in need_content_html(
        app, "index.html", "SPEC_REC_RST"
    )
    assert '<a class="reference external" href="https://example.com">' in (
        need_content_html(app, "index.html", "SPEC_REC_MD")
    )
    assert "Legacy <em>description</em>." in (
        need_content_html(app, "index.html", "SPEC_REC_LEGACY")
    )


IMPORTED = {
    "current_version": "1.0",
    "versions": {
        "1.0": {
            "needs": {
                "IMP_1": {
                    "id": "IMP_1",
                    "type": "req",
                    "title": "Imported",
                    "content": "Imported *content*.",
                    "collapse": False,
                    "tags": [],
                },
            }
        }
    },
}


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "files": [
                (Path("conf.py"), CONF),
                (Path("needcontent_ext.py"), DRIVER),
                (
                    Path("index.rst"),
                    "Import\n======\n\n.. needimport:: imported.json\n   :collapse: true\n",
                ),
                (Path("imported.json"), json.dumps(IMPORTED)),
            ],
        }
    ],
    indirect=True,
)
def test_needimport_override_options_survive_the_key_drop(test_app: SphinxTestApp):
    """needimport writes its override options before ``ingest_need_record`` drops keys.

    They used to be written after the drop; every override option is a field the project
    knows and imports, so the order makes no difference, and this pins it.
    """
    app = test_app
    app.build()
    assert build_warnings(app) == []
    assert get_needs_view(app)["IMP_1"]["collapse"] is True


@pytest.mark.parametrize(
    "test_app", [{"buildername": "html", "files": FOUR_CELL_FILES}], indirect=True
)
def test_an_incremental_build_reports_the_same_locations(test_app: SphinxTestApp):
    """(j): re-reading the MyST page re-emits its content's warnings, at the same places."""
    app = test_app
    app.build()
    first = build_warnings(app)
    needs = needs_by_id(app)

    later = time.time() + 10
    os.utime(Path(app.srcdir, "a_host_md.md"), (later, later))
    app.build()
    second = build_warnings(app)[len(first) :]

    # what reading the MyST page reports for its two cells, and what writing reports
    # for all four (every page with needs is written again)
    expected = four_cell_warnings(("rm", "mm")) + [
        w for w in four_cell_warnings(("rr", "mr")) if w.endswith("[ref.ref]")
    ]
    assert sorted(second) == sorted(expected)
    assert needs_by_id(app) == needs


JINJA_BODY = [
    "Rendered {{ 6 * 7 }} with a [ref link][lnk].",
    "",
    "```{note}",
    "```",
    "",
    "[lnk]: https://example.com",
]
JINJA_OPTIONS = {"markup": ".md", "source": "src/j.c", "first-line": 10, "jinja": ""}
JINJA_INDEX = [
    "Rendered content",
    "================",
    "",
    ".. toctree::",
    "",
    "   jinja_md",
    "",
    *rst_need("SPEC_JINJA_R", JINJA_BODY, JINJA_OPTIONS),
]
JINJA_MD = [
    "# Rendered content (MyST)",
    "",
    "Some lines, so that the need is not near the top of the page.",
    "",
    "More of them.",
    "",
    *md_need("SPEC_JINJA_M", JINJA_BODY, JINJA_OPTIONS),
]


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "files": [
                (Path("conf.py"), CONF),
                (Path("needcontent_ext.py"), DRIVER),
                (Path("index.rst"), "\n".join(JINJA_INDEX)),
                (Path("jinja_md.md"), "\n".join(JINJA_MD)),
            ],
        }
    ],
    indirect=True,
)
def test_rendered_content_is_parsed_in_its_markup_at_the_need(test_app: SphinxTestApp):
    """Content rendered by Jinja is in no file: it is anchored at the need's own line.

    The ``MarkupContent``'s ``source`` is ignored for it, as for a template's content. In both pages,
    the rendered text's lines count from the line of the directive that made the need.
    """
    app = test_app
    app.build()
    note = JINJA_BODY.index("```{note}")
    rst = line_of(JINJA_INDEX, ".. test-need-content::")
    md = line_of(JINJA_MD, "````{test-need-content}")
    expected = (
        'ERROR: Content block expected for the "note" directive; none found. [docutils]'
    )
    assert sorted(build_warnings(app)) == [
        f"<srcdir>/index.rst:{rst + note}: {expected}",
        f"<srcdir>/jinja_md.md:{md + note}: {expected}",
    ]
    for page, need_id in (
        ("index.html", "SPEC_JINJA_R"),
        ("jinja_md.html", "SPEC_JINJA_M"),
    ):
        content = need_content_html(app, page, need_id)
        assert "Rendered 42 with a" in content
        assert '<a class="reference external" href="https://example.com">' in content


IMAGE_INDEX = [
    "Images",
    "======",
    "",
    ".. toctree::",
    "",
    "   images_md",
    "",
    *rst_need(
        "SPEC_IMG_MR",
        ["![an image](pic.png)", "", "![an image](missing_mr.png)"],
        {"markup": ".md", "source": "src/i.c", "first-line": 20},
    ),
]
IMAGE_MD = [
    "# Images (MyST)",
    "",
    *md_need(
        "SPEC_IMG_RM",
        [".. image:: pic.png", "", ".. image:: missing_rm.png"],
        {"markup": ".rst", "source": "src/k.c", "first-line": 30},
    ),
]


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "files": [
                (Path("conf.py"), CONF),
                (Path("needcontent_ext.py"), DRIVER),
                (Path("index.rst"), "\n".join(IMAGE_INDEX)),
                (Path("images_md.md"), "\n".join(IMAGE_MD)),
                # next to the pages, not under ``src/``
                (Path("pic.png"), "not read"),
            ],
        }
    ],
    indirect=True,
)
def test_an_image_in_content_resolves_against_the_page(test_app: SphinxTestApp):
    """A relative image path resolves against the page, not the content's file.

    Not refused in this version (documented); the warning for a missing image still
    names the content's file and line, through the nodes the content created.
    """
    app = test_app
    app.build()
    assert sorted(build_warnings(app)) == [
        f"<srcdir>/{src('i.c')}:22: WARNING: image file not readable: missing_mr.png "
        "[image.not_readable]",
        f"<srcdir>/{src('k.c')}:32: WARNING: image file not readable: missing_rm.png "
        "[image.not_readable]",
    ]
    assert '<img alt="an image" src="_images/pic.png" />' in html(app, "index.html")
    assert 'src="_images/pic.png"' in html(app, "images_md.html")


FIELD_NAMED_CONTENT_MARKUP_CONF = (
    CONF
    + 'needs_fields = {"content_markup": {"description": "A field of this project", '
    + '"schema": {"type": "string"}}}\n'
)
"""A project field named ``content_markup``: nothing in ``add_need`` is named so."""

IMPORTED_WITH_A_FIELD_NAMED_CONTENT_MARKUP = {
    "current_version": "1.0",
    "versions": {
        "1.0": {
            "needs": {
                "IMP_OK": {
                    "id": "IMP_OK",
                    "type": "req",
                    "title": "Imported, with a field named content_markup",
                    "content": "Imported *content*.",
                    "content_markup": "a value of the field",
                    "exporter_only": "a key this project does not know",
                    "tags": [],
                },
            }
        }
    },
}


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "files": [
                (Path("conf.py"), FIELD_NAMED_CONTENT_MARKUP_CONF),
                (Path("needcontent_ext.py"), DRIVER),
                (
                    Path("index.rst"),
                    "Import\n======\n\n.. needimport:: imported.json\n\n"
                    ".. req:: A need setting the field\n"
                    "   :id: REQ_FIELD\n"
                    "   :content_markup: markdown, please\n",
                ),
                (
                    Path("imported.json"),
                    json.dumps(IMPORTED_WITH_A_FIELD_NAMED_CONTENT_MARKUP),
                ),
            ],
        }
    ],
    indirect=True,
)
def test_a_field_named_content_markup_is_an_ordinary_field(test_app: SphinxTestApp):
    """``add_need`` takes no argument named ``content_markup``: a field may be.

    A need directive sets it, and a needimport record carrying it imports it as the
    field. The record's key the project does not know is reported in the one
    ``unknown_import_keys`` warning, as for any record that imports fine.
    """
    app = test_app
    app.build()
    assert build_warnings(app) == [
        "<srcdir>/index.rst:4: WARNING: Unknown keys in import need source: "
        "['exporter_only'] [needs.unknown_import_keys]"
    ]
    needs = needs_by_id(app)
    assert needs["IMP_OK"]["content_markup"] == "a value of the field"
    assert needs["IMP_OK"]["doctype"] == ".rst"
    assert needs["REQ_FIELD"]["content_markup"] == "markdown, please"


PROLOG_CONF = (
    CONF
    + 'rst_prolog = ".. |a| replace:: A\\n.. |b| replace:: B\\n"\n'
    + 'exclude_patterns = ["fragment.rst"]\n'
)
"""Two lines of ``rst_prolog``, and a fragment that is only ever included."""

PROLOG_RST_BODY = ["Text.", "", ".. nosuchdirective::"]
PROLOG_MD_BODY = ["Text {{ 6 * 7 }}.", "", "```{note}", "```"]
PROLOG_RECORDS = [
    {
        "need": {
            "type": "spec",
            "title": "A MyST record",
            "id": "SPEC_PROLOG_{suffix}",
            "doctype": ".md",
            "content": "Text.\n\n```{note}\n```",
        }
    }
]
PROLOG_INDEX = [
    "Behind rst_prolog and an include",
    "================================",
    "",
    ".. include:: fragment.rst",
    "",
    ".. req:: Host need",
    "   :id: REQ_HOST",
    "",
    ".. req:: A need directive",
    "   :id: REQ_PROLOG",
    "",
    *(f"   {line}".rstrip() for line in PROLOG_RST_BODY),
    "",
    *rst_need("SPEC_PROLOG_R", PROLOG_RST_BODY, {"markup": ".rst"}),
    *rst_need("SPEC_PROLOG_M", PROLOG_MD_BODY, {"markup": ".md"}),
    # a paragraph ends the run of directives: docutils parses each run after its
    # first directive in a nested state machine starting at that directive
    "A paragraph.",
    "",
    *rst_need("SPEC_PROLOG_J", PROLOG_MD_BODY, {"markup": ".md", "jinja": ""}),
    *rst_need(
        "SPEC_PROLOG_JR",
        PROLOG_MD_BODY,
        {"markup": ".md", "jinja": "", "resolved-lineno": ""},
    ),
    "A paragraph.",
    "",
    ".. test-ingest-records:: records_i.json",
    "",
    ".. test-ingest-records:: records_ir.json",
    "   :resolved-lineno:",
    "",
    "Closing paragraphs, so that the end of the page is no need's line.",
    "",
    "Another one.",
    "",
    "And a third.",
    "",
]


def prolog_records(suffix: str) -> str:
    return json.dumps(PROLOG_RECORDS).replace("{suffix}", suffix)


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "files": [
                (Path("conf.py"), PROLOG_CONF),
                (Path("needcontent_ext.py"), DRIVER),
                (Path("index.rst"), "\n".join(PROLOG_INDEX)),
                (
                    Path("fragment.rst"),
                    "Fragment line one.\n\nFragment line two.\n\nFragment line three.\n",
                ),
                (Path("records_i.json"), prolog_records("I")),
                (Path("records_ir.json"), prolog_records("IR")),
            ],
        }
    ],
    indirect=True,
)
def test_content_anchored_in_the_page_behind_rst_prolog_and_an_include(
    test_app: SphinxTestApp,
):
    """Content without a ``source`` reports the page's lines, as a need directive's.

    ``rst_prolog`` and ``.. include::`` shift the parser's line count away from the
    file's; the anchor maps the parser's line back, so every message here names the
    line it is on in ``index.rst``. ``lineno``/``lineno_content`` are the parser's lines,
    as a directive's ``self.lineno``/``self.content_offset`` give them; a resolved file
    line (``:resolved-lineno:``) falls outside the parser's input here and anchors at
    the need's own line.
    """
    app = test_app
    app.build()

    def body(need_id: str) -> int:
        """The page line of the first body line of the directive creating ``need_id``."""
        return line_of(PROLOG_INDEX, f":id: {need_id}") + 2

    def directive(text: str) -> int:
        """The page line of the directive whose first line or option contains ``text``."""
        at_text = line_of(PROLOG_INDEX, text)
        return max(
            i
            for i, line in enumerate(PROLOG_INDEX[:at_text], 1)
            if line.startswith(".. ")
        )

    unknown = 'ERROR: Unknown directive type "nosuchdirective".\n\n.. nosuchdirective:: [docutils]'
    empty = (
        'ERROR: Content block expected for the "note" directive; none found. [docutils]'
    )
    note = PROLOG_MD_BODY.index("```{note}")
    assert sorted(build_warnings(app)) == sorted(
        [
            # a need directive, and the same body as RST content: the same line
            f"<srcdir>/index.rst:{body('REQ_PROLOG') + 2}: {unknown}",
            f"<srcdir>/index.rst:{body('SPEC_PROLOG_R') + 2}: {unknown}",
            # MyST content
            f"<srcdir>/index.rst:{body('SPEC_PROLOG_M') + note}: {empty}",
            # rendered content, at the need's line, with the parser's or the file's line
            f"<srcdir>/index.rst:{directive(':id: SPEC_PROLOG_J') + note}: {empty}",
            f"<srcdir>/index.rst:{directive(':id: SPEC_PROLOG_JR') + note}: {empty}",
            # a record without a source, at the need's line, either way
            f"<srcdir>/index.rst:{directive('records_i.json') + 2}: {empty}",
            f"<srcdir>/index.rst:{directive('records_ir.json') + 2}: {empty}",
        ]
    )


LINES_RECORDS = [
    {
        "need": {
            "type": "spec",
            "title": "A form feed in a line",
            "id": "SPEC_FF",
            "doctype": ".rst",
            "content": "Text.\x0c A page break, in the same line.\n\n.. nosuchdirective::",
        },
        "source": {"path": "src/ff.c", "line": 10},
    },
    {
        "need": {
            "type": "spec",
            "title": "A form feed in a line, MyST",
            "id": "SPEC_FF_MD",
            "doctype": ".md",
            "content": "Text.\x0c A page break, in the same line.\n\n```{note}\n```",
        },
        "source": {"path": "src/ffm.c", "line": 20},
    },
    {
        "need": {
            "type": "spec",
            "title": "CRLF",
            "id": "SPEC_CRLF",
            "doctype": ".rst",
            "content": "Text::\r\n\r\n   literal\r\n\r\n.. nosuchdirective::\r\n",
        },
        "source": {"path": "src/crlf.c", "line": 30},
    },
]
LINES_INDEX = [
    "Lines",
    "=====",
    "",
    ".. test-ingest-records:: records.json",
    "",
    *rst_need(
        "SPEC_CR_ITEMS",
        ["Text::", "", "   literal", "", ".. nosuchdirective::"],
        {"markup": ".rst", "source": "src/cr.c", "first-line": 40, "crlf": ""},
    ),
]


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "files": [
                (Path("conf.py"), CONF),
                (Path("needcontent_ext.py"), DRIVER),
                (Path("index.rst"), "\n".join(LINES_INDEX)),
                (Path("records.json"), json.dumps(LINES_RECORDS)),
            ],
        }
    ],
    indirect=True,
)
def test_content_lines_are_its_newline_separated_lines(test_app: SphinxTestApp):
    """A line of content is what ``\\n`` separates, as a line of the file it came from.

    A form feed (or another character ``str.splitlines`` breaks on) inside a line does
    not shift the lines after it, and a ``\\r`` ending a line -- CRLF text, or lines
    split from it on ``\\n`` -- parses as it does without one.
    """
    app = test_app
    app.build()
    unknown = 'ERROR: Unknown directive type "nosuchdirective".\n\n.. nosuchdirective:: [docutils]'
    empty = (
        'ERROR: Content block expected for the "note" directive; none found. [docutils]'
    )
    assert sorted(build_warnings(app)) == sorted(
        [
            f"<srcdir>/{src('ff.c')}:12: {unknown}",
            f"<srcdir>/{src('ffm.c')}:22: {empty}",
            f"<srcdir>/{src('crlf.c')}:34: {unknown}",
            f"<srcdir>/{src('cr.c')}:44: {unknown}",
        ]
    )
    for need_id in ("SPEC_CRLF", "SPEC_CR_ITEMS"):
        content = need_content_html(app, "index.html", need_id)
        # ``Text::`` then the indented line: a literal block, highlighted
        assert '<pre><span></span><span class="n">literal</span>' in content, need_id


FILES_CONF = (
    CONF
    # the test layer writes no subdirectories: the content's directory is made here
    + "(Path(__file__).parent / 'src').mkdir(exist_ok=True)\n"
    + "(Path(__file__).parent / 'src' / 'data.csv').write_text("
    + "'BESIDE,THE CONTENT\\n', encoding='utf-8')\n"
)
FILES_INDEX = [
    "Files",
    "=====",
    "",
    ".. toctree::",
    "",
    "   files_md",
    "",
    *rst_need(
        "SPEC_CSV",
        [".. csv-table::", "   :file: data.csv", "", "Text after the table."],
        {"markup": ".rst", "source": "src/a.c", "first-line": 100},
    ),
    "Page text after the need.",
    "",
]
FILES_MD = [
    "# Files (MyST)",
    "",
    "[pagelnk]: https://page.example",
    "",
    "The page uses [its own link][pagelnk].",
    "",
    *md_need(
        "SPEC_LINKDEFS",
        [
            "A page definition: [t][pagelnk].",
            "",
            "Its own definition: [u][ownlnk].",
            "",
            "[ownlnk]: https://own.example",
        ],
        {"markup": ".md", "source": "src/l.c", "first-line": 10},
    ),
]


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "files": [
                (Path("conf.py"), FILES_CONF),
                (Path("needcontent_ext.py"), DRIVER),
                (Path("index.rst"), "\n".join(FILES_INDEX)),
                (Path("files_md.md"), "\n".join(FILES_MD)),
                (Path("data.csv"), "BESIDE,THE PAGE\n"),
            ],
        }
    ],
    indirect=True,
)
def test_what_reads_the_content_file_and_what_reads_the_page(test_app: SphinxTestApp):
    """Where the content's file shows through the page binding, and where it does not.

    docutils resolves ``csv-table :file:`` (and ``raw :file:``) against the source of
    the line being parsed, which in reStructuredText content is the content's file,
    while Sphinx's ``include``, ``literalinclude`` and images resolve against the page.
    After the content, the document is back on the page: nodes the page creates next
    do not name the content's file. And MyST content has its own markdown-it
    environment: the page's reference-link definitions are not its.
    """
    app = test_app
    app.build()
    assert build_warnings(app) == []

    page = html(app, "index.html")  # the table's own cells end the need's content cell
    assert "<p>THE CONTENT</p>" in page
    assert "THE PAGE" not in page

    doctree = app.env.get_doctree("index")
    page_text = next(
        node
        for node in doctree.findall(nodes.paragraph)
        if node.astext() == "Page text after the need."
    )
    assert Path(page_text.source) == Path(app.srcdir, "index.rst")
    targets = [
        node for node in doctree.findall(nodes.target) if "SPEC_CSV" in node["ids"]
    ]
    assert targets
    assert all(Path(node.source) == Path(app.srcdir, "index.rst") for node in targets)

    content = need_content_html(app, "files_md.html", "SPEC_LINKDEFS")
    assert "[t][pagelnk]" in content
    assert "page.example" not in content
    assert '<a class="reference external" href="https://own.example">u</a>' in content


@pytest.mark.parametrize(
    ("kwargs", "exception", "message"),
    [
        (
            {"markup": ".md", "source": ("", 1)},
            ValueError,
            "MarkupContent.source: the path must not be empty",
        ),
        (
            {"markup": ".md", "source": ("a.c", 0)},
            ValueError,
            "MarkupContent.source: the first line is 1-based, got 0",
        ),
        (
            {"markup": ".md", "source": ("a.c", "1")},
            TypeError,
            "MarkupContent.source must be a (path, first_line) tuple of a str and an "
            "int, got ('a.c', '1')",
        ),
        (
            {"markup": ""},
            ValueError,
            "MarkupContent.markup must be a non-empty source suffix, got ''",
        ),
    ],
    ids=["empty_path", "line_0", "line_str", "empty_markup"],
)
def test_a_malformed_markup_content_is_refused_where_it_is_made(
    kwargs: dict[str, Any], exception: type[Exception], message: str
):
    """A ``MarkupContent`` checks its own shape: before any need exists to refuse.

    Whether the markup is a suffix the project registers is ``add_need``'s question
    (``InvalidNeedException``, before the need is recorded); a malformed object is the
    caller's mistake, and fails where it is built.
    """
    with pytest.raises(exception) as excinfo:
        MarkupContent("Text.", **kwargs)
    assert str(excinfo.value) == message
