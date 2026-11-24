"""Stated parts: the parts a need is given that its content does not mark.

A need is given parts by a ``needimport`` record, by ``create_need(parts=...)`` and by
the deprecated ``add_need(parts=...)``. Where its content is read, it has the parts its
content marks, in the order written, then the given parts whose id the content does
not mark, in the order given; the content's part wins a clash, with no finding. A
stated part of a need on a page is shown in a block after the need's content, one line
per part with its text, its id and its anchor ``NEED.part``. A hidden and an external
need keep the given parts alone, as they did.

A part id is one word: a given part whose id holds white space or a control character
is not a part of a need whose content is read, and ``create_need`` refuses it. Such a
need takes a stated text on one line: each run of white space holding a line break is
one space, in the stored part and so wherever the text is written.

``design/parts-contract.md`` is the rule; ``tests/fixtures/parts_conformance.toml``
pins what both tools answer, and this module what only a page, the API and the stored
data show.
"""

from __future__ import annotations

import io
import json
import re
import time
from pathlib import Path
from typing import Any

import pytest
from docutils import nodes
from sphinx.application import Sphinx
from sphinxcontrib.plantuml import plantuml

from sphinx_needs.config import NeedsSphinxConfig
from sphinx_needs.data import SphinxNeedsData
from sphinx_needs.filter_common import filter_needs_parts
from sphinx_needs.need_item import NeedPartData
from sphinx_needs_testkit import build_warnings

# --- create_need(parts=...) ---------------------------------------------------------------

API_CONF = '''\
from sphinx.util.docutils import SphinxDirective

from sphinx_needs.api import NeedItemSource, create_need
from sphinx_needs.exceptions import InvalidNeedException

extensions = ["sphinx_needs"]
needs_build_json = True
needs_links = {"tests": {}}


class StatedNeed(SphinxDirective):
    """A need created through ``create_need``, given three parts, one of which its
    content marks too."""

    has_content = True
    required_arguments = 1

    def run(self):
        _, need_nodes = create_need(
            self.env.app,
            self.state,
            NeedItemSource.from_directive(self),
            "req",
            "Stated",
            id=self.arguments[0],
            content=self.content,
            parts={"s2": "  second, its ends kept\\t", "s1": "first", "cp": "given cp"},
        )
        return need_nodes


#: parts ``create_need`` cannot store, each refused before anything is recorded: a
#: part id is one word, so one holding white space or a control character is refused
BAD_PARTS = {
    "API_BAD_KEY": {1: "text"},
    "API_EMPTY_KEY": {"": "text"},
    "API_BAD_TEXT": {"k1": 1},
    "API_NO_MAPPING": ["k1"],
    "API_SPACE_KEY": {"sp ace": "text"},
    "API_TAB_KEY": {"a\\tb": "text"},
    "API_NEWLINE_KEY": {"a\\nb": "text"},
    "API_NBSP_KEY": {"a\\u00a0b": "text"},
    "API_CONTROL_KEY": {"a\\x01b": "text"},
}


class Refusals(SphinxDirective):
    """``create_need`` given parts it cannot store, and ``parts`` in ``fields``."""

    def run(self):
        app = self.env.app
        outcomes = self.env.__dict__.setdefault("stated_refusals", {})
        calls = {
            need_id: dict(parts=parts) for need_id, parts in BAD_PARTS.items()
        }
        calls["API_IN_FIELDS"] = dict(fields={"parts": {"k1": "text"}})
        calls["API_IN_LINKS"] = dict(links={"parts": ["REQ_1"]})
        for need_id, kwargs in calls.items():
            try:
                create_need(
                    app, self.state, NeedItemSource.from_directive(self), "req",
                    "Refused", id=need_id, **kwargs,
                )
            except InvalidNeedException as err:
                outcomes[need_id] = (err.type, err.message)
            except Exception as err:
                outcomes[need_id] = (type(err).__name__, str(err))
            else:
                outcomes[need_id] = ("created", "")
        return []


def setup(app):
    app.add_directive("stated-need", StatedNeed)
    app.add_directive("refusals", Refusals)
'''

API_INDEX = """\
Stated
======

.. stated-need:: API_1

   Marks :np:`(cp) content cp` here.

.. req:: Only content
   :id: REQ_1

   Marks :np:`(p1) a content part` here.

.. test:: Links
   :id: TEST_1
   :tests: API_1.s1, API_1.cp

See :need:`API_1.s1`.

.. refusals::
"""

API_PROJECT = {
    "buildername": "html",
    "files": [(Path("conf.py"), API_CONF), (Path("index.rst"), API_INDEX)],
}

#: the line of a stated part in the block, byte for byte: the inline a content part
#: renders, with the class ``need-part-stated`` beside ``need-part``
S1_LINE = (
    '<span class="need-part need-part-stated" id="API_1.s1">first<a class="needs-id '
    'reference internal" href="#API_1.s1"> s1</a></span>'
)
S2_LINE = (
    '<span class="need-part need-part-stated" id="API_1.s2">  second, its ends kept\t'
    '<a class="needs-id reference internal" href="#API_1.s2"> s2</a></span>'
)
#: a content part's inline, as it was
CP_SPAN = (
    '<span class="need-part" id="API_1.cp">content cp<a class="needs-id reference '
    'internal" href="#API_1.cp"> cp</a></span>'
)


def _parts(app: Sphinx, need_id: str) -> list[tuple[str, str, str]]:
    """A need's parts in stored order, each its id, its text and its origin."""
    need = SphinxNeedsData(app.env).get_needs_view()[need_id]
    return [(part.id, part.content, part.origin) for part in need.parts]


def _written(app: Sphinx) -> dict[str, Any]:
    data = json.loads(Path(app.outdir, "needs.json").read_text(encoding="utf-8"))
    return data["versions"][data["current_version"]]["needs"]


@pytest.mark.parametrize("test_app", [API_PROJECT], ids=["api"], indirect=True)
def test_create_need_states_parts(test_app: Sphinx) -> None:
    """``create_need(parts=...)`` merges its parts with its content's: the content's
    first, as written, then the given ones the content does not mark, in the order
    given, each text as given; the content's text wins the id both give. A link to a
    stated part is live, and ``:need:`` to one names it by its text."""
    app = test_app
    app.build()
    assert build_warnings(app) == []
    assert _parts(app, "API_1") == [
        ("cp", "content cp", "content"),
        ("s2", "  second, its ends kept\t", "stated"),
        ("s1", "first", "stated"),
    ]
    assert _parts(app, "REQ_1") == [("p1", "a content part", "content")]

    written = _written(app)
    assert written["API_1"]["parts"] == {
        "cp": {"id": "cp", "content": "content cp", "tests_back": ["TEST_1"]},
        "s1": {"id": "s1", "content": "first", "tests_back": ["TEST_1"]},
        "s2": {"id": "s2", "content": "  second, its ends kept\t"},
    }
    # the stored content is the need's content: the block is no part of it
    assert written["API_1"]["content"] == "Marks :np:`(cp) content cp` here."

    html = Path(app.outdir, "index.html").read_text(encoding="utf-8")
    # one block, the stated parts' lines in order, after the content's part
    assert html.count("needs-stated-parts") == 1
    block = html[html.index('<div class="needs-stated-parts') :]
    assert block.index(S2_LINE) < block.index(S1_LINE) < block.index("</div>")
    assert html.index(CP_SPAN) < html.index('<div class="needs-stated-parts')
    assert html.count("need-part-stated") == 2
    assert re.search(
        r'<a class="reference internal" href="#API_1\.s1"[^>]*>'
        r'<em class="xref need">first \(API_1\.s1\)</em></a>',
        html,
    )


@pytest.mark.parametrize("test_app", [API_PROJECT], ids=["api"], indirect=True)
def test_create_need_refuses_parts_it_cannot_store(test_app: Sphinx) -> None:
    """A part id that is not a non-empty string or not one word, a text that is not a
    string, and parts that are not a mapping are refused with the exception type a bad
    record raises, before anything is recorded; ``parts`` in ``fields`` or in ``links``
    names the argument."""
    app = test_app
    app.build()
    outcomes = app.env.stated_refusals  # type: ignore[attr-defined]
    assert {need_id: outcome[0] for need_id, outcome in outcomes.items()} == {
        "API_BAD_KEY": "parts",
        "API_EMPTY_KEY": "parts",
        "API_BAD_TEXT": "parts",
        "API_NO_MAPPING": "parts",
        "API_SPACE_KEY": "parts",
        "API_TAB_KEY": "parts",
        "API_NEWLINE_KEY": "parts",
        "API_NBSP_KEY": "parts",
        "API_CONTROL_KEY": "parts",
        "API_IN_FIELDS": "invalid_kwargs",
        "API_IN_LINKS": "invalid_kwargs",
    }
    assert outcomes["API_SPACE_KEY"][1] == (
        "a part id is one word, with no white space and no control character, not "
        "'sp ace'"
    )
    assert outcomes["API_IN_FIELDS"][1] == (
        "'parts' is an argument of create_need: give it as parts=, not in 'fields'."
    )
    assert outcomes["API_IN_LINKS"][1] == (
        "'parts' is an argument of create_need: give it as parts=, not in 'links'."
    )
    assert not set(outcomes) & set(SphinxNeedsData(app.env).get_needs_view())


@pytest.mark.parametrize("test_app", [API_PROJECT], ids=["api"], indirect=True)
def test_a_part_s_origin_is_stored_and_nowhere_else(test_app: Sphinx) -> None:
    """A part records whether its need's content marks it or it is stated; the origin
    is not written to needs.json, not answered by a part and not a name a filter
    reads."""
    app = test_app
    app.build()
    need = SphinxNeedsData(app.env).get_needs_view()["API_1"]
    for part_id in ("cp", "s1"):
        item = need.get_part_item(part_id)
        assert item is not None
        assert "origin" not in item
        assert "origin" not in dict(need["parts"][part_id])
    config = NeedsSphinxConfig(app.config)
    view = SphinxNeedsData(app.env).get_needs_view()
    assert (
        filter_needs_parts(
            view.to_list_with_parts(), config, 'is_part and origin == "stated"'
        )
        == []
    )
    # a need takes a part whose origin is one of the two, and no other
    elsewhere = NeedPartData(id="x1", content="text", origin="elsewhere")  # ty: ignore[invalid-argument-type]
    with pytest.raises(ValueError, match="must have the origin 'content' or 'stated'"):
        need.set_parts([elsewhere])
    assert [part.id for part in need.parts] == ["cp", "s2", "s1"]


INGEST_CONF = """\
from sphinx.util.docutils import SphinxDirective

from sphinx_needs.api import NeedItemSource, ingest_need_record

extensions = ["sphinx_needs"]
needs_build_json = True
needs_links = {"tests": {}}


class Ingest(SphinxDirective):
    \"\"\"A need an extension makes of a record of its own, through
    ``ingest_need_record``.\"\"\"

    def run(self):
        need_nodes, _ = ingest_need_record(
            self.env.app,
            self.state,
            {
                "id": "EXT_REC",
                "type": "req",
                "title": "From an extension",
                "content": "Marks :np:`(c1) content one`.",
                "parts": {"r1": {"id": "r1", "content": "record one"}},
            },
            need_source=NeedItemSource.from_directive(self),
        )
        return need_nodes


def setup(app):
    app.add_directive("ingest", Ingest)
"""

INGEST_INDEX = """\
Ingest
======

.. ingest::

.. test:: Links
   :id: TEST_1
   :tests: EXT_REC.r1
"""


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "files": [
                (Path("conf.py"), INGEST_CONF),
                (Path("index.rst"), INGEST_INDEX),
            ],
        }
    ],
    ids=["ingest"],
    indirect=True,
)
def test_an_extension_s_record_states_parts(test_app: Sphinx) -> None:
    """``ingest_need_record`` called by an extension, not by needimport, merges the
    record's parts with its content's as an import does: the stated part is shown in
    the block and a link to it is live."""
    app = test_app
    app.build()
    assert build_warnings(app) == []
    assert _parts(app, "EXT_REC") == [
        ("c1", "content one", "content"),
        ("r1", "record one", "stated"),
    ]
    html = Path(app.outdir, "index.html").read_text(encoding="utf-8")
    assert html.count('<div class="needs-stated-parts docutils container">') == 1
    assert (
        '<span class="need-part need-part-stated" id="EXT_REC.r1">record one<a '
        'class="needs-id reference internal" href="#EXT_REC.r1"> r1</a></span>'
    ) in html
    assert not SphinxNeedsData(app.env).get_needs_view()["TEST_1"]["has_dead_links"]
    assert _written(app)["EXT_REC"]["parts"]["r1"]["tests_back"] == ["TEST_1"]


def test_a_part_built_by_code_is_stated() -> None:
    """``NeedPartData`` built as another extension built it, with an id and a text,
    is a stated part: one built by code is stated by that code."""
    part = NeedPartData(id="x1", content="text")
    assert part.origin == "stated"
    assert NeedPartData(id="x1", content="text", origin="content").origin == "content"


# --- the block, in every builder -------------------------------------------------------

BLOCK_CONF = """\
project = "parts"
extensions = ["sphinx_needs"]
needs_build_json = True
# epub warns of an empty version or copyright
version = "1.0"
copyright = "the authors"
"""

#: an imported need with a part its record states alone, a part both give and a part
#: its content marks; a need whose parts all come from its content; a reference to the
#: stated part; and a paragraph after them
BLOCK_INDEX = """\
Parts
=====

.. needimport:: imported.json

.. req:: Only content
   :id: REQ_1

   Marks :np:`(p1) a content part` here.

A reference to :need:`IMP_1.rp`.

The last paragraph.
"""

BLOCK_RECORD = {
    "current_version": "1.0",
    "versions": {
        "1.0": {
            "needs": {
                "IMP_1": {
                    "id": "IMP_1",
                    "type": "req",
                    "title": "Imported",
                    "content": "Marks :np:`(c1) content one` here.",
                    "parts": {
                        "rp": {"id": "rp", "content": "a record part"},
                        "c1": {"id": "c1", "content": " record c1"},
                    },
                }
            }
        }
    },
}


def _block_page(buildername: str, **conf: str) -> dict[str, Any]:
    return {
        "buildername": buildername,
        "files": [
            (
                Path("conf.py"),
                BLOCK_CONF + "".join(f"{k} = {v}\n" for k, v in conf.items()),
            ),
            (Path("index.rst"), BLOCK_INDEX),
            (Path("imported.json"), json.dumps(BLOCK_RECORD)),
        ],
    }


#: what a builder reports on this page, as it does on any page with a need: ``man``
#: cannot span a cell of a need's table, ``epub`` packs no file of a type it does not
#: know
BLOCK_PAGE_WARNINGS = {
    "man": [
        '<srcdir>/index.rst:2: WARNING: "table cell spanning" not supported [docutils]'
    ]
    * 2,
    "epub": [
        "WARNING: unknown mimetype for permalink.html, ignoring [epub.unknown_project_files]",
        "WARNING: unknown mimetype for schema_violations.json, ignoring "
        "[epub.unknown_project_files]",
    ],
}

RP_LINE = (
    '<span class="need-part need-part-stated" id="IMP_1.rp">a record part<a '
    'class="needs-id reference internal" href="#IMP_1.rp"> rp</a></span>'
)


def _built(app: Sphinx, page: str) -> str:
    app.build()
    assert sorted(build_warnings(app)) == sorted(
        BLOCK_PAGE_WARNINGS.get(app.builder.name, [])
    )
    assert [(p, t) for p, t, _ in _parts(app, "IMP_1")] == [
        ("c1", "content one"),
        ("rp", "a record part"),
    ]
    return Path(app.outdir, page).read_text(encoding="utf-8")


@pytest.mark.parametrize(
    "test_app,filename",
    [
        (_block_page("html"), "index.html"),
        (_block_page("singlehtml"), "index.html"),
        (_block_page("epub"), "index.xhtml"),
    ],
    ids=["html", "singlehtml", "epub"],
    indirect=["test_app"],
)
def test_the_block_in_the_html_family(test_app: Sphinx, filename: str) -> None:
    """The html family writes one block, for the need with a stated part, its line the
    inline of a content part with the class ``need-part-stated``, and ``:need:`` links
    the part's anchor there; the need whose parts all come from its content has none."""
    html = _built(test_app, filename)
    assert html.count('<div class="needs-stated-parts docutils container">') == 1
    block = html[html.index('<div class="needs-stated-parts') :]
    assert block.index(RP_LINE) < block.index("</div>")
    assert html.count('id="IMP_1.rp"') == 1
    assert re.search(
        r'<a class="reference internal" href="#IMP_1\.rp"[^>]*>'
        r'<em class="xref need">a record part \(IMP_1\.rp\)</em></a>',
        html,
    )
    assert html.count("need-part-stated") == 1


def _words(written: str) -> str:
    """The text a writer wrote, with its table borders and its line breaks gone."""
    return " ".join(written.replace("|", " ").split())


@pytest.mark.parametrize(
    "test_app,filename",
    [(_block_page("text"), "index.txt"), (_block_page("man"), "parts.1")],
    ids=["text", "man"],
    indirect=["test_app"],
)
def test_the_block_in_text_and_man(test_app: Sphinx, filename: str) -> None:
    """``text`` and ``man`` write no anchors: the block's line is the part's text and
    its id, after the need's content."""
    written = _words(_built(test_app, filename))
    assert "Marks content one c1 here. a record part rp" in written
    assert written.count("a record part rp") == 1


@pytest.mark.parametrize(
    "test_app", [_block_page("latex")], ids=["latex"], indirect=True
)
def test_the_block_in_latex(test_app: Sphinx) -> None:
    """LaTeX labels the stated part's address on its line in the block, once, and the
    reference to it resolves there."""
    tex = _built(test_app, "parts.tex")
    label = r"\phantomsection\label{\detokenize{index:IMP_1.rp}}"
    assert tex.count(label) == 1
    assert f"{label}a record part" in tex
    labels = re.findall(r"\\label\{\\detokenize\{(index:IMP_1\.[^}]*)\}\}", tex)
    references = re.findall(r"\\hyperref\[\\detokenize\{(index:IMP_1\.[^}]*)\}\]", tex)
    assert sorted(labels) == ["index:IMP_1.c1", "index:IMP_1.rp"]
    assert set(references) == set(labels)


@pytest.mark.parametrize(
    "test_app", [_block_page("texinfo")], ids=["texinfo"], indirect=True
)
def test_the_block_in_texinfo(test_app: Sphinx) -> None:
    """texinfo writes the stated part's ``@anchor`` before its text in the block."""
    texi = _built(test_app, "parts.texi")
    assert re.search(
        r"@anchor\{index IMP_1 rp\}(@anchor\{\d+\})?a record part@ref\{", texi
    )
    assert texi.count("@anchor{index IMP_1 rp}") == 1


@pytest.mark.parametrize(
    "test_app",
    [_block_page("html", needs_import_restrict_content="True")],
    ids=["restricted"],
    indirect=True,
)
def test_restricted_import_content_keeps_the_stated_parts(test_app: Sphinx) -> None:
    """``needs_import_restrict_content`` restricts how a record's content is parsed and
    has no effect on the parts the record states."""
    html = _built(test_app, "index.html")
    assert RP_LINE in html


@pytest.mark.parametrize("test_app", [_block_page("html")], ids=["html"], indirect=True)
def test_the_block_is_the_last_child_of_the_need(test_app: Sphinx) -> None:
    """The block is a child of the need's node itself, after its content: not inside
    the content's last paragraph, where html would hold a ``div`` in a ``p``."""
    html = _built(test_app, "index.html")
    node = SphinxNeedsData(test_app.env).get_need_node("IMP_1")
    assert node is not None
    blocks = [
        n for n in node.findall(nodes.container) if "needs-stated-parts" in n["classes"]
    ]
    assert blocks == [node.children[-1]]
    assert blocks[0].parent is node
    assert isinstance(node.children[-2], nodes.paragraph)
    assert node.children[-2].astext() == "Marks content one c1 here."
    assert html.count('here.</span></p>\n<div class="needs-stated-parts') == 0
    assert html.count('</p>\n<div class="needs-stated-parts docutils container">') == 1


#: a need with a stated part and a needextract of it on the same page
EXTRACT_INDEX = """\
Parts
=====

.. needimport:: imported.json

.. needextract::
   :filter: id == "IMP_1"
"""


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "latex",
            "files": [
                (Path("conf.py"), BLOCK_CONF),
                (Path("index.rst"), EXTRACT_INDEX),
                (Path("imported.json"), json.dumps(BLOCK_RECORD)),
            ],
        }
    ],
    ids=["latex"],
    indirect=True,
)
def test_a_stated_part_shown_twice_on_a_page_is_labelled_once(test_app: Sphinx) -> None:
    """A needextract of a need on the need's own page shows its block twice; LaTeX
    labels the stated part's address once, at the first, as it does a content part."""
    app = test_app
    app.build()
    assert build_warnings(app) == []
    tex = Path(app.outdir, "parts.tex").read_text(encoding="utf-8")
    assert tex.count("a record part{\\hyperref") == 2
    assert tex.count(r"\label{\detokenize{index:IMP_1.rp}}") == 1
    assert tex.count(r"\label{\detokenize{index:IMP_1.c1}}") == 1


#: a record stating parts whose texts hold line breaks, one a blank line, and one
#: holding a run of white space with no line break
BREAKS_RECORD = {
    "current_version": "1.0",
    "versions": {
        "1.0": {
            "needs": {
                "IMP_1": {
                    "id": "IMP_1",
                    "type": "req",
                    "title": "Imported",
                    "content": "No role here.",
                    "parts": {
                        "r1": {"id": "r1", "content": "para1\n\npara2"},
                        "r2": {"id": "r2", "content": "a \t\n \u2028\tb"},
                        "r3": {"id": "r3", "content": "x  y\t"},
                    },
                }
            }
        }
    },
}


def _breaks_page(buildername: str) -> dict[str, Any]:
    return {
        "buildername": buildername,
        "files": [
            (Path("conf.py"), BLOCK_CONF),
            (Path("index.rst"), "Parts\n=====\n\n.. needimport:: imported.json\n"),
            (Path("imported.json"), json.dumps(BREAKS_RECORD)),
        ],
    }


#: each stated part's text as given, and as the block shows it
BREAKS = {
    "r1": ("para1\n\npara2", "para1 para2"),
    "r2": ("a \t\n \u2028\tb", "a b"),
    "r3": ("x  y\t", "x  y\t"),
}


@pytest.mark.parametrize(
    "test_app",
    [_breaks_page("html"), _breaks_page("latex")],
    ids=["html", "latex"],
    indirect=True,
)
def test_the_block_shows_a_line_break_as_a_space(test_app: Sphinx) -> None:
    """The block shows a stated part's text with each run of white space holding a
    line break as one space, so no text ends a paragraph inside a line (a blank line
    in LaTeX is a ``\\par``); a run with no line break is shown as given. The block
    shows the text the need took: the stored text and what a part answers are the
    same one line."""
    app = test_app
    app.build()
    assert build_warnings(app) == []
    assert _parts(app, "IMP_1") == [
        (part_id, shown, "stated") for part_id, (_, shown) in BREAKS.items()
    ]
    need = SphinxNeedsData(app.env).get_needs_view()["IMP_1"]
    for part_id, (_, shown) in BREAKS.items():
        item = need.get_part_item(part_id)
        assert item is not None
        assert item["content"] == shown
    if app.builder.name == "html":
        html = Path(app.outdir, "index.html").read_text(encoding="utf-8")
        for part_id, (_, shown) in BREAKS.items():
            assert f'id="IMP_1.{part_id}">{shown}<a ' in html, part_id
        return
    tex = Path(app.outdir, "parts.tex").read_text(encoding="utf-8")
    texts = re.findall(
        r"\\DUrole\{need-part-stated\}\{\\phantomsection\\label\{\\detokenize\{"
        r"index:IMP_1\.(r\d)\}\}(.*?)\{\\hyperref",
        tex,
        re.DOTALL,
    )
    assert [part_id for part_id, _ in texts] == list(BREAKS)
    for part_id, text in texts:
        assert "\n" not in text, part_id
    assert dict(texts)["r1"] == "para1 para2"


def test_a_stated_text_is_shown_in_time_proportional_to_its_length() -> None:
    """A record's text is any string, a long run of white space included: a need takes
    it on one line in time proportional to its length. A run with no line break is read
    once and kept as given; a pattern that starts over at each character of the run
    takes time proportional to the square of its length, which for this text is many
    times the bound here."""
    # imported here, so that the module still collects on code without the helper
    from sphinx_needs.roles.need_part import _on_one_line

    run = " " * 100_000
    text = f"a{run}b\n{run}c"
    started = time.perf_counter()
    shown = _on_one_line(text)
    elapsed = time.perf_counter() - started
    assert shown == f"a{run}b c"
    assert elapsed < 2.0, elapsed


# --- a stated text is taken on one line ----------------------------------------------------

#: each stated text as given, and as a need whose content is read takes it: one text per
#: kind of line break with no LF in it, each alone, a run holding a break beside a run of
#: two spaces holding none, and a text holding no line break at all; the rule's edges: a
#: control character Python also splits lines at (U+001C) is no line break, white space
#: beyond ASCII (U+00A0, U+3000) beside a break is in its run, and an end that is a run
#: holding a break is one space, as is a text of breaks alone
ONE_LINE = {
    "r1": ("para1\n\npara2", "para1 para2"),
    "r2": ("a \n b", "a b"),
    "r3": ("one  line\t", "one  line\t"),
    "cr": ("a\r\rb", "a b"),
    "vt": ("a\x0bb", "a b"),
    "ff": ("a\x0cb", "a b"),
    "nel": ("a\x85b", "a b"),
    "ls": ("a\u2028b", "a b"),
    "ps": ("a\u2029b", "a b"),
    "crlf": ("a\r\nb", "a b"),
    "mixed": ("a  b\nc", "a  b c"),
    "fs": ("a\x1cb", "a\x1cb"),
    "wide": ("a\xa0\n\u3000b", "a b"),
    "start": ("\nab", " ab"),
    "end": ("ab\n", "ab "),
    "breaks": ("\n\r\n", " "),
}

ONE_LINE_CONF = '''\
import json
from pathlib import Path

from sphinx.util.docutils import SphinxDirective

from sphinx_needs.api import NeedItemSource, add_need, create_need, ingest_need_record

extensions = ["sphinx_needs"]
needs_build_json = True
needs_external_needs = [{"base_url": "http://example.org/", "json_path": "external.json"}]

#: part id to text, as every route below is given it
TEXTS = json.loads(Path(__file__).with_name("texts.json").read_text(encoding="utf-8"))
RECORD_PARTS = {part_id: {"id": part_id, "content": text} for part_id, text in TEXTS.items()}


class Given(SphinxDirective):
    """A need given ``TEXTS`` as its parts by one route: ``ingest`` (an extension's
    record), ``add`` (the deprecated ``add_need``), ``create`` or ``create-hidden``."""

    required_arguments = 2

    def run(self):
        route, need_id = self.arguments
        app, source = self.env.app, NeedItemSource.from_directive(self)
        if route == "ingest":
            record = {
                "id": need_id, "type": "req", "title": "Given",
                "content": "No role here.", "parts": RECORD_PARTS,
            }
            return ingest_need_record(app, self.state, record, need_source=source)[0]
        if route == "add":
            return add_need(
                app, self.state, self.env.docname, self.lineno, "req", "Given",
                id=need_id, content="No role here.", parts=RECORD_PARTS,
            )
        fields = {"hide": True} if route == "create-hidden" else {}
        return create_need(
            app, self.state, source, "req", "Given", id=need_id,
            content="No role here.", parts=TEXTS, fields=fields,
        )[1]


def setup(app):
    app.add_directive("given", Given)
'''

ONE_LINE_INDEX = """\
One line
========

.. needimport:: imported.json

.. needimport:: hidden.json
   :hide:

.. given:: ingest ING_1

.. given:: add ADD_1

.. given:: create API_1

.. given:: create-hidden API_HID
"""


def _one_line_record(
    need_id: str, content: str, more: dict[str, str] | None = None
) -> str:
    """A needs.json holding one need stating ``more`` (part id to text), then every text
    of ``ONE_LINE``."""
    parts = {
        part_id: {"id": part_id, "content": given}
        for part_id, given in (more or {}).items()
    }
    parts.update(
        (part_id, {"id": part_id, "content": given})
        for part_id, (given, _) in ONE_LINE.items()
    )
    record = {
        "id": need_id,
        "type": "req",
        "title": "Given",
        "content": content,
        "parts": parts,
    }
    return json.dumps(
        {"current_version": "1.0", "versions": {"1.0": {"needs": {need_id: record}}}}
    )


#: the imported need's content marks a part whose role is written across two lines
TWO_LINE_ROLE = "Marks :np:`(m1) line one\nline two`."
#: the imported need's record states that part too, with another text holding a break
CLASHING_PART = {"m1": "the record's\n\ntext"}

ONE_LINE_PROJECT = {
    "buildername": "html",
    "files": [
        (Path("conf.py"), ONE_LINE_CONF),
        (Path("index.rst"), ONE_LINE_INDEX),
        (
            Path("texts.json"),
            json.dumps({part_id: given for part_id, (given, _) in ONE_LINE.items()}),
        ),
        (
            Path("imported.json"),
            _one_line_record("IMP_1", TWO_LINE_ROLE, CLASHING_PART),
        ),
        (Path("hidden.json"), _one_line_record("IMP_HID", "No role here.")),
        (Path("external.json"), _one_line_record("EXT_1", "No role here.")),
    ],
}

#: the needs whose content is read, one per route a need is given parts by
READ_NEEDS = ("IMP_1", "ING_1", "ADD_1", "API_1")
#: the needs whose content is not read: a hidden import, an external need, a hidden
#: ``create_need``
UNREAD_NEEDS = ("IMP_HID", "EXT_1", "API_HID")


def _built_one_line(app: Sphinx) -> None:
    with pytest.warns(DeprecationWarning, match="add_need is deprecated"):
        app.build()
    assert build_warnings(app) == []


@pytest.mark.parametrize("test_app", [ONE_LINE_PROJECT], ids=["routes"], indirect=True)
def test_a_stated_text_is_taken_on_one_line(test_app: Sphinx) -> None:
    """A need whose content is read takes a stated part's text with each run of white
    space holding a line break (LF, VT, FF, CR, NEL, LS, PS) as one space, by every
    route a need is given parts: a visible import, an extension's record, ``add_need``
    and ``create_need`` on a page. The stored part, needs.json, what the part answers
    and the block's line all hold that one line; a run holding no line break is kept,
    as is every other character, and an end that is a run holding a break is one space."""
    app = test_app
    _built_one_line(app)
    written = _written(app)
    view = SphinxNeedsData(app.env).get_needs_view()
    html = Path(app.outdir, "index.html").read_text(encoding="utf-8")
    for need_id in READ_NEEDS:
        stated = [(p, t) for p, t, origin in _parts(app, need_id) if origin == "stated"]
        assert stated == [(p, taken) for p, (_, taken) in ONE_LINE.items()], need_id
        assert {
            p: part["content"]
            for p, part in written[need_id]["parts"].items()
            if p in ONE_LINE
        } == {p: taken for p, (_, taken) in ONE_LINE.items()}, need_id
        for part_id, (_, taken) in ONE_LINE.items():
            item = view[need_id].get_part_item(part_id)
            assert item is not None
            assert item["content"] == taken, (need_id, part_id)
            assert f'id="{need_id}.{part_id}">{taken}<a ' in html, (need_id, part_id)


@pytest.mark.parametrize("test_app", [ONE_LINE_PROJECT], ids=["routes"], indirect=True)
def test_a_need_whose_content_is_not_read_keeps_a_text_as_given(
    test_app: Sphinx,
) -> None:
    """A hidden import, an external need and a hidden ``create_need`` do not read their
    content, and keep the texts they are given, line breaks and all."""
    app = test_app
    _built_one_line(app)
    view = SphinxNeedsData(app.env).get_needs_view()
    for need_id in UNREAD_NEEDS:
        assert _parts(app, need_id) == [
            (p, given, "stated") for p, (given, _) in ONE_LINE.items()
        ], need_id
        for part_id, (given, _) in ONE_LINE.items():
            item = view[need_id].get_part_item(part_id)
            assert item is not None
            assert item["content"] == given, (need_id, part_id)
    written = _written(app)
    for need_id in ("IMP_HID", "API_HID"):
        assert {
            p: part["content"] for p, part in written[need_id]["parts"].items()
        } == {p: given for p, (given, _) in ONE_LINE.items()}, need_id


@pytest.mark.parametrize("test_app", [ONE_LINE_PROJECT], ids=["routes"], indirect=True)
def test_a_content_part_keeps_its_line_break(test_app: Sphinx) -> None:
    """The rule is a stated part's alone: a content part whose role is written across
    two lines keeps its line break, in the stored part and on its line, beside the
    stated parts of the same need, which are taken on one line. So does it where the
    record states that id too, with another text: the content's part is the part,
    with its own text as written."""
    app = test_app
    _built_one_line(app)
    parts = _parts(app, "IMP_1")
    assert parts[:2] == [
        ("m1", "line one\nline two", "content"),
        ("r1", "para1 para2", "stated"),
    ]
    assert [p for p, _, _ in parts].count("m1") == 1
    assert _written(app)["IMP_1"]["parts"]["m1"]["content"] == "line one\nline two"
    html = Path(app.outdir, "index.html").read_text(encoding="utf-8")
    assert 'id="IMP_1.m1">line one\nline two<a ' in html
    assert 'id="IMP_1.r1">para1 para2<a ' in html


#: a stated text holding a blank line, listed by a needlist and named by ``:need:``
WRITTEN_INDEX = """\
Parts
=====

.. needimport:: imported.json

.. needlist::
   :filter: type == "req"

A reference to :need:`IMP_1.r1`.
"""

WRITTEN_RECORD = {
    "current_version": "1.0",
    "versions": {
        "1.0": {
            "needs": {
                "IMP_1": {
                    "id": "IMP_1",
                    "type": "req",
                    "title": "Imported",
                    "content": "No role here.",
                    "parts": {"r1": {"id": "r1", "content": "para1\n\npara2"}},
                }
            }
        }
    },
}


def _written_page(
    buildername: str, extensions: str = "", **conf: str
) -> dict[str, Any]:
    conf_py = (
        BLOCK_CONF
        + extensions
        + "needs_views_include_parts = True\n"
        + "".join(f"{k} = {v}\n" for k, v in conf.items())
    )
    return {
        "buildername": buildername,
        "files": [
            (Path("conf.py"), conf_py),
            (Path("index.rst"), WRITTEN_INDEX),
            (Path("imported.json"), json.dumps(WRITTEN_RECORD)),
        ],
    }


def _hyperref_bodies(tex: str) -> list[str]:
    """The text of every ``\\hyperref[...]{...}`` of a LaTeX file, its braces matched."""
    bodies = []
    for found in re.finditer(r"\\hyperref\[[^\]]*\]\{", tex):
        depth, start = 1, found.end()
        end = start
        while depth:
            depth += {"{": 1, "}": -1}.get(tex[end], 0)
            end += 1
        bodies.append(tex[start : end - 1])
    return bodies


@pytest.mark.parametrize(
    "test_app",
    [
        _written_page("latex"),
        _written_page("latex", needs_role_need_template='"{{ title }} <{{ id }}>"'),
    ],
    ids=["default", "template"],
    indirect=True,
)
def test_a_view_and_a_reference_write_a_stated_text_on_one_line(
    test_app: Sphinx,
) -> None:
    """A needlist's line for a stated part and a ``:need:`` reference to it write its
    text on one line inside their ``\\hyperref``: a blank line there stops ``pdflatex``
    (``Paragraph ended before \\label@@hyperref was complete``)."""
    app = test_app
    app.build()
    assert build_warnings(app) == []
    tex = Path(app.outdir, "parts.tex").read_text(encoding="utf-8")
    shown = [body for body in _hyperref_bodies(tex) if "para1" in body]
    # the needlist's line, the reference, and the part's own id link in the block
    assert len(shown) >= 2, shown
    for body in shown:
        assert "\n" not in body, body
        assert "para1 para2" in body, body


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "plantuml": True,
            "files": [
                (
                    Path("conf.py"),
                    'extensions = ["sphinx_needs", "sphinxcontrib.plantuml"]\n',
                ),
                (
                    Path("index.rst"),
                    "Parts\n=====\n\n.. needimport:: imported.json\n\n"
                    ".. needuml::\n\n"
                    '   Alice -> Bob: {{ref("IMP_1.r1", option="title")}}\n',
                ),
                (Path("imported.json"), json.dumps(WRITTEN_RECORD)),
            ],
        }
    ],
    ids=["needuml"],
    indirect=True,
)
def test_a_needuml_reference_to_a_stated_part_draws(test_app: Sphinx) -> None:
    """A needuml ``ref()`` to a stated part writes its text into the diagram's line: on
    one line, the diagram draws."""
    app = test_app
    sources: list[str] = []

    def collect(app_: Sphinx, doctree: Any, docname: str) -> None:
        sources.extend(node["uml"] for node in doctree.findall(plantuml))

    app.connect("doctree-resolved", collect, priority=900)
    app.build()
    assert build_warnings(app) == []
    (uml,) = sources
    assert "para1 para2" in uml


# --- the views ---------------------------------------------------------------------------

VIEWS_CONF = """\
extensions = ["sphinx_needs", "sphinxcontrib.plantuml"]
needs_views_include_parts = True
"""

VIEWS_INDEX = """\
Views
=====

.. toctree::

   extract

.. needimport:: imported.json

.. needtable::
   :filter: id == "IMP_1"
   :show_parts:
   :columns: id, title

.. needflow::
   :filter: id_parent == "IMP_1"
"""

VIEWS_EXTRACT = """\
Extract
=======

.. needextract::
   :filter: id == "IMP_1"

See :need:`IMP_1.r1`.
"""

VIEWS_RECORD = {
    "current_version": "1.0",
    "versions": {
        "1.0": {
            "needs": {
                "IMP_1": {
                    "id": "IMP_1",
                    "type": "req",
                    "title": "Imported",
                    "content": "Marks :np:`(c2) content two` and :np:`(c1) content one`.",
                    "parts": {
                        "r2": {"id": "r2", "content": "record two"},
                        "r1": {"id": "r1", "content": "record one"},
                    },
                }
            }
        }
    },
}

VIEWS_PROJECT = {
    "buildername": "html",
    "files": [
        (Path("conf.py"), VIEWS_CONF),
        (Path("index.rst"), VIEWS_INDEX),
        (Path("extract.rst"), VIEWS_EXTRACT),
        (Path("imported.json"), json.dumps(VIEWS_RECORD)),
    ],
}


@pytest.mark.parametrize("test_app", [VIEWS_PROJECT], ids=["views"], indirect=True)
def test_the_views_show_stated_parts_in_stored_order(test_app: Sphinx) -> None:
    """A needtable with ``:show_parts:``, a needflow and a needextract show a need's
    stated parts through its stored parts, in stored order: the content's, then the
    stated ones."""
    app = test_app
    sources: list[str] = []

    def collect(app_: Sphinx, doctree: Any, docname: str) -> None:
        sources.extend(node["uml"] for node in doctree.findall(plantuml))

    app.connect("doctree-resolved", collect, priority=900)
    app.build()
    assert build_warnings(app) == []
    order = ["c2", "c1", "r2", "r1"]
    assert [p for p, _, _ in _parts(app, "IMP_1")] == order

    html = Path(app.outdir, "index.html").read_text(encoding="utf-8")
    table = html[html.index("<table") : html.index("</table>")]
    rows = re.findall(r'href="#IMP_1\.([a-z0-9]+)"', table)
    assert rows == order

    (uml,) = sources
    assert re.findall(r" as IMP_1\.([a-z0-9]+) \[\[", uml) == order

    extract = Path(app.outdir, "extract.html").read_text(encoding="utf-8")
    assert 'class="needs-stated-parts docutils container"' in extract
    assert re.search(r'id="IMP_1\.r2">record two<a [^>]*href="#IMP_1\.r2"', extract)
    assert re.search(
        r'href="index\.html#IMP_1\.r1"[^>]*><em class="xref need">record one '
        r"\(IMP_1\.r1\)</em>",
        extract,
    )


#: an import whose record states a part its content does not mark, and a needtable whose
#: filter does not name parts
FILTERED_INDEX = """\
Views
=====

.. needimport:: imported.json

.. needtable::
   :filter: type == "req"
   :columns: id, title
"""

#: what ``needs.views_include_parts`` reports for that needtable while the value is unset
VIEWS_REPORT = (
    "<srcdir>/index.rst:6: WARNING: This needtable's filter selects 1 need part: from "
    "Sphinx-Needs 10.0 a view's filter selects needs only, and a needtable lists a "
    "need's parts under it only with :show_parts:. Set needs_views_include_parts = True "
    "to keep listing them, or False to list needs only now; or suppress "
    "needs.views_include_parts. [needs.views_include_parts]"
)


#: a record whose content marks no part, stating one
FILTERED_RECORD = {
    "current_version": "1.0",
    "versions": {
        "1.0": {
            "needs": {
                "IMP_1": {
                    "id": "IMP_1",
                    "type": "req",
                    "title": "Imported",
                    "content": "No role here.",
                    "parts": {"rp": {"id": "rp", "content": "a record part"}},
                }
            }
        }
    },
}


def _filtered_page(value: str | None) -> dict[str, Any]:
    conf = BLOCK_CONF + (
        "" if value is None else f"needs_views_include_parts = {value}\n"
    )
    return {
        "buildername": "html",
        "files": [
            (Path("conf.py"), conf),
            (Path("index.rst"), FILTERED_INDEX),
            (Path("imported.json"), json.dumps(FILTERED_RECORD)),
        ],
    }


@pytest.mark.parametrize(
    "test_app,rows,warnings",
    [
        (_filtered_page(None), ["IMP_1", "IMP_1.rp"], [VIEWS_REPORT]),
        (_filtered_page("False"), ["IMP_1"], []),
        (_filtered_page("True"), ["IMP_1", "IMP_1.rp"], []),
    ],
    ids=["unset", "false", "true"],
    indirect=["test_app"],
)
def test_a_view_s_filter_tests_stated_parts(
    test_app: Sphinx, rows: list[str], warnings: list[str]
) -> None:
    """A stated part is a part like any other: a view's filter tests it while
    ``needs_views_include_parts`` is unset or ``True``, so a needtable whose filter does
    not name parts lists it, and while the value is unset reports
    ``needs.views_include_parts`` for it once; ``False`` tests the needs alone."""
    app = test_app
    app.build()
    assert build_warnings(app) == warnings
    html = Path(app.outdir, "index.html").read_text(encoding="utf-8")
    start = html.index('<table class="NEEDS_DATATABLES')
    table = html[start : html.index("</table>", start)]
    assert re.findall(r'href="#(IMP_1[^"]*)"', table) == rows


# --- a part id is one word -----------------------------------------------------------------

#: a needflow drawing an imported need and its parts, and a link to one of them
ONE_WORD_INDEX = """\
Parts
=====

.. needimport:: imported.json

.. needflow::
   :filter: id == "IMP_1" or id_parent == "IMP_1"

.. test:: Links
   :id: TEST_1
   :links: IMP_1.ok
"""


def _one_word_page(part_id: str, **params: Any) -> dict[str, Any]:
    record = {
        "current_version": "1.0",
        "versions": {
            "1.0": {
                "needs": {
                    "IMP_1": {
                        "id": "IMP_1",
                        "type": "req",
                        "title": "Imported",
                        "content": "Marks :np:`(c1) content one`.",
                        "parts": {
                            part_id: {"id": part_id, "content": "not one word"},
                            "ok": {"id": "ok", "content": "one word"},
                        },
                    }
                }
            }
        },
    }
    conf = (
        'extensions = ["sphinx_needs", "sphinxcontrib.plantuml"]\n'
        "needs_build_json = True\n"
        "needs_views_include_parts = True\n"
    )
    return {
        "buildername": "html",
        "files": [
            (Path("conf.py"), conf),
            (Path("index.rst"), ONE_WORD_INDEX),
            (Path("imported.json"), json.dumps(record)),
        ],
        **params,
    }


def _assert_not_taken(app: Sphinx) -> None:
    """The need has its content's part and the one-word part alone, shows that one in
    its block, writes those two, and the link to the one-word part is live."""
    assert _parts(app, "IMP_1") == [
        ("c1", "content one", "content"),
        ("ok", "one word", "stated"),
    ]
    assert set(_written(app)["IMP_1"]["parts"]) == {"c1", "ok"}
    html = Path(app.outdir, "index.html").read_text(encoding="utf-8")
    assert html.count("need-part-stated") == 1
    assert 'id="IMP_1.ok"' in html
    assert "not one word" not in html
    assert not SphinxNeedsData(app.env).get_needs_view()["TEST_1"]["has_dead_links"]


@pytest.mark.parametrize(
    "test_app",
    [_one_word_page("sp ace", plantuml=True)],
    ids=["plantuml"],
    indirect=True,
)
def test_a_part_id_holding_a_space_is_not_taken(test_app: Sphinx) -> None:
    """A given part whose id holds white space is not a part of a need whose content is
    read: a PlantUML needflow drawing the need's parts draws (it took such an id
    unquoted, and failed), and nothing is reported."""
    app = test_app
    app.build()
    assert build_warnings(app) == []
    _assert_not_taken(app)


@pytest.mark.parametrize(
    "test_app",
    [
        _one_word_page("a\tb"),
        _one_word_page("a\nb"),
        _one_word_page("a\u00a0b"),
        _one_word_page("a\u2028b"),
        _one_word_page("a\x01b"),
        _one_word_page("a\x85b"),
    ],
    ids=[
        "tab",
        "line-feed",
        "no-break-space",
        "line-separator",
        "control",
        "next-line",
    ],
    indirect=True,
)
def test_a_part_id_holding_white_space_or_a_control_character_is_not_taken(
    test_app: Sphinx,
) -> None:
    """A part id is one word: one holding a character of Unicode's ``White_Space``
    property or of the general category ``Cc`` is not taken, and nothing is
    reported."""
    app = test_app
    app.build()
    assert build_warnings(app) == []
    _assert_not_taken(app)


#: one-word ids outside ``White_Space`` and ``Cc``: a zero width space, a byte order
#: mark, a right-to-left override and a soft hyphen (general category ``Cf``) and a
#: private use character (``Co``)
OTHER_WORDS = ["a\u200bb", "a\ufeffb", "a\u202eb", "a\ue000b", "a\xadb"]

OTHER_WORDS_RECORD = {
    "current_version": "1.0",
    "versions": {
        "1.0": {
            "needs": {
                "IMP_1": {
                    "id": "IMP_1",
                    "type": "req",
                    "title": "Imported",
                    "content": "Marks :np:`(c1) content one`.",
                    "parts": {
                        **{
                            part_id: {"id": part_id, "content": "one word"}
                            for part_id in OTHER_WORDS
                        },
                        "ok": {"id": "ok", "content": "one word"},
                    },
                }
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
                (
                    Path("conf.py"),
                    'extensions = ["sphinx_needs"]\nneeds_build_json = True\n',
                ),
                (
                    Path("index.rst"),
                    "Parts\n=====\n\n.. needimport:: imported.json\n\n"
                    ".. test:: Links\n   :id: TEST_1\n   :links: IMP_1.ok\n",
                ),
                (Path("imported.json"), json.dumps(OTHER_WORDS_RECORD)),
            ],
        }
    ],
    ids=["format-and-private-use"],
    indirect=True,
)
def test_a_part_id_holding_another_character_of_category_c_is_taken(
    test_app: Sphinx,
) -> None:
    """The control characters an id may not hold are the general category ``Cc``
    alone: an id holding a format (``Cf``) or a private use (``Co``) character is one
    word, and taken."""
    app = test_app
    app.build()
    assert build_warnings(app) == []
    assert [p for p, _, _ in _parts(app, "IMP_1")] == ["c1", *OTHER_WORDS, "ok"]
    assert set(_written(app)["IMP_1"]["parts"]) == {"c1", *OTHER_WORDS, "ok"}
    html = Path(app.outdir, "index.html").read_text(encoding="utf-8")
    assert html.count("need-part-stated") == len(OTHER_WORDS) + 1


# --- what does not change ----------------------------------------------------------------

UNCHANGED_CONF = """\
extensions = ["sphinx_needs"]
needs_external_needs = [{"base_url": "http://example.org/", "json_path": "external.json"}]
"""

UNCHANGED_INDEX = """\
Unchanged
=========

.. needimport:: hidden.json
   :hide:
"""

#: a record whose content marks one part and which states two others
_RECORD: dict[str, Any] = {
    "type": "req",
    "title": "Given",
    "content": "Marks :np:`(c1) content one`.",
    "parts": {
        "r2": {"id": "r2", "content": "record two"},
        "r1": {"id": "r1", "content": "record one"},
    },
}


def _envelope(need_id: str, *more: str) -> str:
    """A needs.json holding one need of ``_RECORD``, stating the parts ``more`` too."""
    record = {
        "id": need_id,
        **_RECORD,
        "parts": {
            **_RECORD["parts"],
            **{part_id: {"id": part_id, "content": "more"} for part_id in more},
        },
    }
    return json.dumps(
        {"current_version": "1.0", "versions": {"1.0": {"needs": {need_id: record}}}}
    )


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "files": [
                (Path("conf.py"), UNCHANGED_CONF),
                (Path("index.rst"), UNCHANGED_INDEX),
                (Path("hidden.json"), _envelope("IMP_HIDDEN")),
                (Path("external.json"), _envelope("EXT_1")),
            ],
        }
    ],
    ids=["hidden-and-external"],
    indirect=True,
)
def test_a_hidden_and_an_external_need_keep_the_given_parts(test_app: Sphinx) -> None:
    """A hidden need, whose content is not read, and an external need, which has no
    content here, keep the parts their record states, in its order, and no other; a
    hidden need renders nothing."""
    app = test_app
    app.build()
    assert build_warnings(app) == []
    needs = SphinxNeedsData(app.env).get_needs_view()
    for need_id in ("IMP_HIDDEN", "EXT_1"):
        assert [
            (pid, part["content"]) for pid, part in needs[need_id]["parts"].items()
        ] == [("r2", "record two"), ("r1", "record one")], need_id
    html = Path(app.outdir, "index.html").read_text(encoding="utf-8")
    assert "IMP_HIDDEN" not in html
    assert "need-part" not in html


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "files": [
                (Path("conf.py"), UNCHANGED_CONF),
                (Path("index.rst"), UNCHANGED_INDEX),
                (Path("hidden.json"), _envelope("IMP_HIDDEN", "sp ace")),
                (Path("external.json"), _envelope("EXT_1", "sp ace")),
            ],
        }
    ],
    ids=["hidden-and-external"],
    indirect=True,
)
def test_a_hidden_and_an_external_need_keep_a_part_id_of_two_words(
    test_app: Sphinx,
) -> None:
    """A hidden and an external need keep what they are given, a part whose id is not
    one word included."""
    app = test_app
    app.build()
    assert build_warnings(app) == []
    needs = SphinxNeedsData(app.env).get_needs_view()
    for need_id in ("IMP_HIDDEN", "EXT_1"):
        assert list(needs[need_id]["parts"]) == ["r2", "r1", "sp ace"], need_id


# --- a round trip --------------------------------------------------------------------------

ROUND_TRIP_WRITER = """\
Writer
======

.. req:: Written
   :id: REQ_A

   Marks :np:`(z9) zed`, :np:`(a1) ay` and :np:`(952) a number`.
"""

ROUND_TRIP_READER = """\
Reader
======

.. needimport:: written.json
"""


def test_a_round_trip_states_no_part(make_app: Any, tmp_path: Path) -> None:
    """A needs.json sphinx-needs wrote, imported: every part its records state is one
    its content marks, so the needs have their parts in the order written there (not
    the file's, which is by id), none stated, and no block."""
    writer = tmp_path / "writer"
    writer.mkdir()
    (writer / "conf.py").write_text(
        'extensions = ["sphinx_needs"]\nneeds_build_json = True\n', encoding="utf-8"
    )
    (writer / "index.rst").write_text(ROUND_TRIP_WRITER, encoding="utf-8")
    app = make_app(
        buildername="html", srcdir=writer, freshenv=True, warning=io.StringIO()
    )
    app.build()
    assert build_warnings(app) == []
    written = Path(app.outdir, "needs.json").read_text(encoding="utf-8")
    assert list(json.loads(written)["versions"][""]["needs"]["REQ_A"]["parts"]) == [
        "952",
        "a1",
        "z9",
    ]
    # the next application registers Sphinx's nodes again: this one gives them back
    app.cleanup()

    reader = tmp_path / "reader"
    reader.mkdir()
    (reader / "conf.py").write_text('extensions = ["sphinx_needs"]\n', encoding="utf-8")
    (reader / "index.rst").write_text(ROUND_TRIP_READER, encoding="utf-8")
    (reader / "written.json").write_text(written, encoding="utf-8")
    app = make_app(
        buildername="html", srcdir=reader, freshenv=True, warning=io.StringIO()
    )
    app.build()
    assert build_warnings(app) == []
    assert _parts(app, "REQ_A") == [
        ("z9", "zed", "content"),
        ("a1", "ay", "content"),
        ("952", "a number", "content"),
    ]
    html = Path(app.outdir, "index.html").read_text(encoding="utf-8")
    assert "needs-stated-parts" not in html
    assert "need-part-stated" not in html
    assert html.count('class="need-part"') == 3
