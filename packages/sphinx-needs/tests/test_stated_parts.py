"""Stated parts: the parts a need is given that its content does not mark.

A need is given parts by a ``needimport`` record, by ``create_need(parts=...)`` and by
the deprecated ``add_need(parts=...)``. Where its content is read, it has the parts its
content marks, in the order written, then the given parts whose id the content does
not mark, in the order given; the content's part wins a clash, with no finding. A
stated part of a need on a page is shown in a block after the need's content, one line
per part with its text, its id and its anchor ``NEED.part``. A hidden and an external
need keep the given parts alone, as they did.

``design/parts-contract.md`` is the rule; ``tests/fixtures/parts_conformance.toml``
pins what both tools answer, and this module what only a page, the API and the stored
data show.
"""

from __future__ import annotations

import io
import json
import re
from pathlib import Path
from typing import Any

import pytest
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


#: parts ``create_need`` cannot store, each refused before anything is recorded
BAD_PARTS = {
    "API_BAD_KEY": {1: "text"},
    "API_EMPTY_KEY": {"": "text"},
    "API_BAD_TEXT": {"k1": 1},
    "API_NO_MAPPING": ["k1"],
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
    """A part id that is not a non-empty string, a text that is not a string, and
    parts that are not a mapping are refused as a bad record's are, before anything is
    recorded; ``parts`` in ``fields`` names the argument."""
    app = test_app
    app.build()
    outcomes = app.env.stated_refusals  # type: ignore[attr-defined]
    assert {need_id: outcome[0] for need_id, outcome in outcomes.items()} == {
        "API_BAD_KEY": "parts",
        "API_EMPTY_KEY": "parts",
        "API_BAD_TEXT": "parts",
        "API_NO_MAPPING": "parts",
        "API_IN_FIELDS": "invalid_kwargs",
    }
    assert outcomes["API_IN_FIELDS"][1] == (
        "'parts' is an argument of create_need: give it as parts=, not in 'fields'."
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
_RECORD = {
    "type": "req",
    "title": "Given",
    "content": "Marks :np:`(c1) content one`.",
    "parts": {
        "r2": {"id": "r2", "content": "record two"},
        "r1": {"id": "r1", "content": "record one"},
    },
}


def _envelope(need_id: str) -> str:
    return json.dumps(
        {
            "current_version": "1.0",
            "versions": {"1.0": {"needs": {need_id: {"id": need_id, **_RECORD}}}},
        }
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
