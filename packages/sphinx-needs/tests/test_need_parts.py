import io
import json
import re
from pathlib import Path
from typing import Any

import pytest
from docutils import nodes
from sphinx.application import Sphinx
from syrupy.extensions.json import JSONSnapshotExtension

from sphinx_needs.data import SphinxNeedsData
from sphinx_needs.roles.need_part import NeedPartRole
from sphinx_needs_testkit import build_warnings


@pytest.fixture
def snapshot_json(snapshot):
    return snapshot.use_extension(JSONSnapshotExtension)


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "html", "srcdir": "doc_test/doc_need_parts"}],
    indirect=True,
)
def test_doc_need_parts(test_app: Sphinx, snapshot_json):
    app = test_app
    app.build()

    warning_records = build_warnings(app)
    # print(warnings)
    assert warning_records == [
        "<srcdir>/index.rst:38: WARNING: Need 'OTHER_1' has unknown outgoing link 'SP_TOO_001.unknown_part' in field 'links' [needs.link_outgoing]",
        "<srcdir>/index.rst:26: WARNING: Need part not associated with a need. [needs.part]",
        "<srcdir>/index.rst:36: WARNING: linked need part SP_TOO_001.unknown_part not found [needs.link_ref]",
    ]

    html = Path(app.outdir, "index.html").read_text()
    assert (
        '<span class="need-part" id="SP_TOO_001.1">exit()<a class="needs-id reference internal" '
        'href="#SP_TOO_001.1"> 1</a></span>' in html
    )

    assert '<em class="xref need">exit() (SP_TOO_001.1)</em>' in html
    assert '<em class="xref need">start() (SP_TOO_001.2)</em>' in html
    assert '<em class="xref need">blub() (SP_TOO_001.awesome_id)</em>' in html
    assert (
        '<em class="xref need">My custom link name (SP_TOO_001.awesome_id)</em>' in html
    )
    assert "SP_TOO_001" in html

    all_needs = SphinxNeedsData(app.env).get_needs_view()
    assert {
        n["id_complete"]: dict(**n) for n in all_needs.to_list_with_parts()
    } == snapshot_json(name="internal_needs_with_parts")

    data = json.loads(Path(app.outdir, "needs.json").read_text())
    assert data["versions"][""]["needs"] == snapshot_json(name="output_needs")


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "html", "srcdir": "doc_test/doc_need_parts_duplicate"}],
    indirect=True,
)
def test_duplicate_part_id_is_reported_once(test_app: Sphinx):
    """A part id repeated in one need is one ``needs.duplicate_part_id`` warning.

    The skipped duplicate was also reported as a part "not associated with a need",
    which it is: it sits in a need, on the directive path and on the list2need path
    alike. The first part of an id is the one kept. A part outside every need is still
    reported as one.
    """
    app = test_app
    app.build()

    assert build_warnings(app) == [
        "<srcdir>/index.rst:8: WARNING: Need 'REQ_001' already has a part 'p1': the first role of an id marks the part, this one is shown as plain text. [needs.duplicate_part_id]",
        "<srcdir>/index.rst:13: WARNING: Need 'REQ_002' already has a part 'p1': the first role of an id marks the part, this one is shown as plain text. [needs.duplicate_part_id]",
        "<srcdir>/index.rst:15: WARNING: Need part not associated with a need. [needs.part]",
    ]

    needs = SphinxNeedsData(app.env).get_needs_view()
    for need_id in ("REQ_001", "REQ_002"):
        assert {
            part_id: part["content"]
            for part_id, part in needs[need_id]["parts"].items()
        } == {"p1": "first"}, need_id


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "html", "srcdir": "doc_test/doc_add_need_parts"}],
    indirect=True,
)
def test_add_need_keeps_the_parts_it_is_given(test_app: Sphinx):
    """``add_need`` keeps the ``parts`` it is given, by the rule of ``create_need``.

    A need on a page has the parts its content marks, in the order written, then the
    given parts its content does not mark, in the order given; a given id the content
    marks too has the content's text. A hidden or an external need keeps the given
    parts. Nothing is reported: the given parts a need on a page dropped were one
    ``needs.part`` warning per need.
    """
    app = test_app
    with pytest.warns(DeprecationWarning, match="add_need is deprecated"):
        app.build()

    assert build_warnings(app) == []

    needs = SphinxNeedsData(app.env).get_needs_view()
    assert {
        need_id: [
            (part_id, part["content"])
            for part_id, part in needs[need_id]["parts"].items()
        ]
        for need_id in (
            "ADD_PLAIN",
            "ADD_MARKS_OTHER",
            "ADD_MARKS_SAME",
            "ADD_HIDDEN",
            "ADD_EXTERNAL",
            "ADD_EMPTY",
        )
    } == {
        "ADD_PLAIN": [("bp", "given bp"), ("ap", "given ap")],
        "ADD_MARKS_OTHER": [("cp", "content cp"), ("ap", "given ap")],
        "ADD_MARKS_SAME": [("ap", "content ap")],
        "ADD_HIDDEN": [("ap", "given ap")],
        "ADD_EXTERNAL": [("ap", "given ap")],
        "ADD_EMPTY": [],
    }
    html = Path(app.outdir, "index.html").read_text(encoding="utf-8")
    # the parts a need on a page is given and its content does not mark are shown in
    # the block after its content, each with its anchor
    assert html.count('class="needs-stated-parts docutils container"') == 2
    for address in ("ADD_PLAIN.bp", "ADD_PLAIN.ap", "ADD_MARKS_OTHER.ap"):
        assert f'<span class="need-part need-part-stated" id="{address}">' in html


EMPTY_PART_INDEX = """\
Index
=====

.. req:: Parts
   :id: REQ_1

   :np:`(p1) the part`

.. spec:: Links
   :id: SPEC_1
   :links: REQ_1., REQ_1.p1
"""


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
                (Path("index.rst"), EMPTY_PART_INDEX),
            ],
        }
    ],
    ids=["empty-part"],
    indirect=True,
)
def test_a_link_to_the_empty_part_keeps_its_dot(test_app: Sphinx):
    """``REQ_1.`` is a dead link: it is reported, written to needs.json and filtered as
    written, never as ``REQ_1``, which it read back as."""
    app = test_app
    app.build()

    assert build_warnings(app) == [
        "<srcdir>/index.rst:9: WARNING: Need 'SPEC_1' has unknown outgoing link "
        "'REQ_1.' in field 'links' [needs.link_outgoing]"
    ]
    data = json.loads(Path(app.outdir, "needs.json").read_text(encoding="utf8"))
    needs = data["versions"][data["current_version"]]["needs"]
    assert needs["SPEC_1"]["links"] == ["REQ_1.", "REQ_1.p1"]
    assert needs["REQ_1"]["links_back"] == ["SPEC_1"]


#: Unicode's ``White_Space`` property, the white space a part's text loses at its ends
#: (``design/parts-contract.md`` section 1), written out here rather than imported, so
#: that the sweep below pins the set the role strips and not merely the role's constant.
#: It is not Python's ``str.isspace``: that also holds U+001C to U+001F.
UNICODE_WHITE_SPACE = frozenset(
    {
        *range(0x09, 0x0E),
        0x20,
        0x85,
        0xA0,
        0x1680,
        *range(0x2000, 0x200B),
        0x2028,
        0x2029,
        0x202F,
        0x205F,
        0x3000,
    }
)


def test_a_part_text_loses_exactly_unicode_white_space_at_its_ends() -> None:
    """A character at either end of an ``(id)`` part's text is removed if and only if it
    is Unicode ``White_Space``, swept over every code point; inside, it is kept, and a
    text of white space alone is the empty text."""
    assert len(UNICODE_WHITE_SPACE) == 25
    role = NeedPartRole()
    # the sweep calls the role alone: no document, so no source position to record
    role.set_source_info = lambda node, lineno=None: None  # type: ignore[method-assign]
    wrong = []
    for code_point in range(0x110000):
        char = chr(code_point)
        white = code_point in UNICODE_WHITE_SPACE
        for text, expected in (
            (
                f"{char}a{char}b{char}",
                f"a{char}b" if white else f"{char}a{char}b{char}",
            ),
            (f"a{char}", "a" if white else f"a{char}"),
            (char, "" if white else char),
        ):
            role.text = f"(p){text}"
            (part,), messages = role.run()
            assert not messages
            if (part["part_id"], part["title"]) != ("p", expected):
                wrong.append(f"U+{code_point:04X} in {text!r}")
    assert wrong == []


EDGE_SPACE_CONF = '''\
from sphinx.util.docutils import SphinxDirective

from sphinx_needs.api import add_need

extensions = ["sphinx_needs", "myst_parser"]
needs_build_json = True


class StatedParts(SphinxDirective):
    """An external and a hidden need, each given a part whose text has white space at
    its ends."""

    def run(self):
        return add_need(
            self.env.app,
            self.state,
            self.env.docname,
            self.lineno,
            "req",
            "Stated",
            id="EXT_STATED",
            is_external=True,
            external_url="https://example.org/x.html#EXT_STATED",
            parts={"sp": {"id": "sp", "content": "  given with spaces\\t"}},
        ) + add_need(
            self.env.app,
            self.state,
            self.env.docname,
            self.lineno,
            "req",
            "Stated hidden",
            id="HIDDEN_STATED",
            hide=True,
            parts={"hp": {"id": "hp", "content": "\\tgiven hidden  "}},
        )


def setup(app):
    app.add_directive("stated-parts", StatedParts)
'''

# U+00A0 and U+3000 are written as escapes in this literal so that the source shows them
EDGE_SPACE_INDEX = """\
Index
=====

.. toctree::

   myst

.. req:: Edge space
   :id: REQ_1

   :np:`(p1)   three spaces` and :np:`(p2)\u00a0no-break space`
   and (\\ :np:`(p3) after a paren`) and :np:`(p4)\u3000ideographic space`
   and :np:`(m1)
   on the next line` and :np:`(m2) first line
   second line` and :np:`no id given`.

:need:`REQ_1.p1`

.. stated-parts::

.. needimport:: hidden.json
   :hide:
"""

#: A record whose part's text has white space at its ends, imported as a hidden need
EDGE_SPACE_HIDDEN_RECORD = {
    "current_version": "1.0",
    "versions": {
        "1.0": {
            "needs": {
                "IMP_HIDDEN": {
                    "id": "IMP_HIDDEN",
                    "type": "req",
                    "title": "Imported hidden",
                    "content": "Hidden.",
                    "parts": {"ip": {"id": "ip", "content": " record spaced "}},
                }
            }
        }
    },
}

EDGE_SPACE_MYST = """\
# MyST

```{req} MyST edge space
:id: REQ_MD

{np}`(b) trailing ` and {np}`(d)\ttab` and {np}`no id ` and {np}` both no id `
and {np}` (c) both `
```
"""

#: The parts of the project with no ``(id)``: the id is the SHA-1 of the whole text
#: as written, and the text is that whole text
WITHOUT_AN_ID = {
    "92C": "no id given",
    "88E": "no id ",
    "768": " both no id ",
    "6D0": " (c) both ",
}

EDGE_SPACE_PROJECT = {
    "buildername": "html",
    "files": [
        (Path("conf.py"), EDGE_SPACE_CONF),
        (Path("index.rst"), EDGE_SPACE_INDEX),
        (Path("myst.md"), EDGE_SPACE_MYST),
        (Path("hidden.json"), json.dumps(EDGE_SPACE_HIDDEN_RECORD)),
    ],
}


def _build_edge_space(app: Sphinx) -> dict[str, dict[str, str]]:
    """Build the project, which reports nothing, and give each need's parts' texts."""
    with pytest.warns(DeprecationWarning, match="add_need is deprecated"):
        app.build()
    assert build_warnings(app) == []
    needs = SphinxNeedsData(app.env).get_needs_view()
    return {
        need_id: {part_id: part["content"] for part_id, part in need["parts"].items()}
        for need_id, need in needs.items()
    }


@pytest.mark.parametrize(
    "test_app", [EDGE_SPACE_PROJECT], ids=["edge-space"], indirect=True
)
def test_a_part_text_has_no_white_space_at_its_ends(test_app: Sphinx) -> None:
    """An ``(id)`` part's text has no white space at either end, in reStructuredText and
    in MyST: spaces, a no-break space, an ideographic space, a tab and a line break after
    the ``)``, and a trailing space MyST keeps; a line break inside the text stays."""
    parts = _build_edge_space(test_app)
    with_an_id = {
        part_id: text
        for part_id, text in (parts["REQ_1"] | parts["REQ_MD"]).items()
        if part_id not in WITHOUT_AN_ID
    }
    assert with_an_id == {
        "p1": "three spaces",
        "p2": "no-break space",
        "p3": "after a paren",
        "p4": "ideographic space",
        "m1": "on the next line",
        "m2": "first line\nsecond line",
        "b": "trailing",
        "d": "tab",
    }
    data = json.loads(Path(test_app.outdir, "needs.json").read_text(encoding="utf8"))
    written = data["versions"][data["current_version"]]["needs"]
    assert written["REQ_1"]["parts"]["p1"]["content"] == "three spaces"
    assert written["REQ_MD"]["parts"]["b"]["content"] == "trailing"


@pytest.mark.parametrize(
    "test_app", [EDGE_SPACE_PROJECT], ids=["edge-space"], indirect=True
)
def test_a_part_without_an_id_keeps_its_id_and_its_text(test_app: Sphinx) -> None:
    """A part with no ``(id)`` is untouched: its id is the hash of its whole text as
    written, and its text is that whole text, edge white space included (MyST)."""
    parts = _build_edge_space(test_app)
    all_parts = parts["REQ_1"] | parts["REQ_MD"]
    assert {part_id: all_parts.get(part_id) for part_id in WITHOUT_AN_ID} == (
        WITHOUT_AN_ID
    )


@pytest.mark.parametrize(
    "test_app", [EDGE_SPACE_PROJECT], ids=["edge-space"], indirect=True
)
def test_a_stated_part_text_is_kept_as_given(test_app: Sphinx) -> None:
    """A part given to ``add_need`` for an external or a hidden need, and a part a
    record imported as a hidden need states, keeps its text byte for byte."""
    parts = _build_edge_space(test_app)
    assert {
        need_id: parts[need_id]
        for need_id in ("EXT_STATED", "HIDDEN_STATED", "IMP_HIDDEN")
    } == {
        "EXT_STATED": {"sp": "  given with spaces\t"},
        "HIDDEN_STATED": {"hp": "\tgiven hidden  "},
        "IMP_HIDDEN": {"ip": " record spaced "},
    }


@pytest.mark.parametrize(
    "test_app", [EDGE_SPACE_PROJECT], ids=["edge-space"], indirect=True
)
def test_a_part_text_is_rendered_without_its_edge_space(test_app: Sphinx) -> None:
    """On the page the part follows a parenthesis with no space between, and ``:need:``
    names a part by its text with no space before it."""
    _build_edge_space(test_app)
    html = Path(test_app.outdir, "index.html").read_text(encoding="utf8")
    assert (
        '(<span class="need-part" id="REQ_1.p3">after a paren'
        '<a class="needs-id reference internal" href="#REQ_1.p3"> p3</a></span>)'
    ) in html
    assert '<em class="xref need">three spaces (REQ_1.p1)</em>' in html


EVERY_BUILDER_CONF = """\
extensions = ["sphinx_needs"]
# applehelp asks for a bundle id, and runs `hiutil` and `codesign` unless told not to
applehelp_bundle_id = "org.example.parts"
applehelp_disable_external_tools = True
"""

EVERY_BUILDER_INDEX = """\
Parts
=====

.. toctree::

   other

.. req:: A requirement
   :id: REQ_1

   :np:`(p1) a part` of the requirement.

See :need:`REQ_1` and :need:`REQ_1.p1`.
"""

EVERY_BUILDER_OTHER = """\
Other
=====

.. spec:: A specification
   :id: SPEC_1

   :need_part:`(s1) another part`, after :need:`REQ_1.p1`.
"""

_PART_TEXTS = ("a part", "another part")
_PART_INLINES = (
    '<inline classes="need-part" ids="REQ_1.p1">',
    '<inline classes="need-part" ids="SPEC_1.s1">',
)

#: where a writer puts a page, and what of the parts it must write there: ``text``,
#: ``man`` and ``epub`` ended the build on a part, ``texinfo`` warned and wrote its
#: text, and ``xml`` and ``pseudoxml`` wrote a ``NeedPart`` element around its inline
_WRITTEN: dict[str, tuple[str, tuple[str, ...]]] = {
    "text": ("*.txt", _PART_TEXTS),
    "man": ("*.1", _PART_TEXTS),
    "texinfo": ("*.texi", _PART_TEXTS),
    "epub": ("*.xhtml", (*_PART_TEXTS, 'id="REQ_1.p1"', 'id="SPEC_1.s1"')),
    "xml": ("*.xml", _PART_INLINES),
    "pseudoxml": ("*.pseudoxml", _PART_INLINES),
}


def test_a_page_with_parts_builds_with_every_builder(
    make_app: Any, tmp_path: Path
) -> None:
    """A page with need parts, and ``:need:`` references to a need and to a part,
    builds with every builder the running Sphinx registers (#2556).

    Only html and latex knew the ``NeedPart`` node: ``text`` and ``man`` ended the
    build on it, ``texinfo`` warned, and ``epub`` ended it too, because an ``epub=``
    visitor another extension registers stops epub falling back to the html ones. The
    builders are read from the registry, so a builder added later is covered here
    without a new test. None is skipped: applehelp is configured not to run its
    external tools, and the project links nowhere outside itself, so ``linkcheck``
    opens no connection.
    """
    srcdir = tmp_path / "src"
    srcdir.mkdir()
    (srcdir / "conf.py").write_text(EVERY_BUILDER_CONF, encoding="utf-8")
    (srcdir / "index.rst").write_text(EVERY_BUILDER_INDEX, encoding="utf-8")
    (srcdir / "other.rst").write_text(EVERY_BUILDER_OTHER, encoding="utf-8")

    probe = make_app(
        buildername="dummy", srcdir=srcdir, freshenv=True, warning=io.StringIO()
    )
    builders = sorted(probe.registry.builders)
    # the ones the issue was about, so a registry that lost them cannot pass vacuously
    assert {"epub", "html", "latex", "man", "texinfo", "text"} <= set(builders)

    failures: dict[str, str] = {}
    for name in builders:
        app = make_app(
            buildername=name,
            srcdir=srcdir,
            builddir=tmp_path / "build" / name,
            freshenv=True,
            warning=io.StringIO(),
        )
        try:
            app.build()
        except Exception as exc:
            failures[name] = f"{type(exc).__name__}: {exc}"
            continue
        unknown = [w for w in build_warnings(app) if "unknown node type" in w]
        if unknown:
            failures[name] = "\n".join(unknown)
            continue
        if name in _WRITTEN:
            pattern, expected = _WRITTEN[name]
            written = "".join(
                path.read_text(encoding="utf-8")
                for path in Path(app.outdir).glob(pattern)
            )
            missing = [t for t in expected if t not in written]
            if missing:
                failures[name] = f"{missing} is not written"

    assert not failures, "a page with parts fails with these builders:\n" + "\n".join(
        f"- {name}: {reason}" for name, reason in failures.items()
    )


def test_a_part_outside_every_need_builds_with_text(
    make_app: Any, tmp_path: Path
) -> None:
    """A part on a page that holds no need still reaches no writer as a ``NeedPart``.

    Such a page is not one sphinx-needs processes (it records no need), so nothing that
    runs only for its own pages can be what removes the node.
    """
    srcdir = tmp_path / "src"
    srcdir.mkdir()
    (srcdir / "conf.py").write_text(EVERY_BUILDER_CONF, encoding="utf-8")
    (srcdir / "index.rst").write_text(
        "Index\n=====\n\n.. toctree::\n\n   loose\n", encoding="utf-8"
    )
    (srcdir / "loose.rst").write_text(
        "Loose\n=====\n\nA :np:`(x1) loose part` outside every need.\n",
        encoding="utf-8",
    )
    app = make_app(
        buildername="text", srcdir=srcdir, freshenv=True, warning=io.StringIO()
    )
    app.build()

    assert [w for w in build_warnings(app) if "unknown node type" in w] == []


PART_PAGE_CONF = """\
project = "parts"
extensions = ["sphinx_needs"]
needs_build_json = True
# epub warns of an empty version or copyright
version = "1.0"
copyright = "the authors"
"""

#: A part, a repetition of a part id, a link and a reference to the part, and a part
#: outside every need, followed by a paragraph: the end of the section, where texinfo
#: wrote the part's anchor
PART_PAGE_INDEX = """\
Parts
=====

.. req:: A requirement
   :id: REQ_1

   Marks :np:`(p1) a local part` here.
   Marks :np:`(d1) the first` and :np:`(d1) the second` here.

.. test:: A test
   :id: TEST_1
   :links: REQ_1.p1

Outside: :np:`(o1) outside text` here.

A reference to :need:`REQ_1.p1`.

The last paragraph.
"""

#: each one finding, where it is written, on every builder
PART_PAGE_FINDINGS = [
    "<srcdir>/index.rst:7: WARNING: Need 'REQ_1' already has a part 'd1': the first "
    "role of an id marks the part, this one is shown as plain text. "
    "[needs.duplicate_part_id]",
    "<srcdir>/index.rst:14: WARNING: Need part not associated with a need. [needs.part]",
]

#: what a builder reports beside them on this page, as it does without the parts:
#: ``man`` cannot span a cell of a need's table, ``epub`` packs no file of a type it
#: does not know and resolves the page more than once, reporting the outer role again
#: each time
PART_PAGE_OTHER_WARNINGS = {
    "man": [
        '<srcdir>/index.rst:2: WARNING: "table cell spanning" not supported [docutils]'
    ]
    * 2,
    "epub": [
        PART_PAGE_FINDINGS[1],
        PART_PAGE_FINDINGS[1],
        PART_PAGE_FINDINGS[1],
        "WARNING: unknown mimetype for permalink.html, ignoring [epub.unknown_project_files]",
        "WARNING: unknown mimetype for schema_violations.json, ignoring "
        "[epub.unknown_project_files]",
    ],
}

#: the html family's span of a part, byte for byte: stylesheets and scripts select it
P1_SPAN = (
    '<span class="need-part" id="REQ_1.p1">a local part<a class="needs-id reference '
    'internal" href="#REQ_1.p1"> p1</a></span>'
)
D1_SPAN = (
    '<span class="need-part" id="REQ_1.d1">the first<a class="needs-id reference '
    'internal" href="#REQ_1.d1"> d1</a></span>'
)


def _part_page(buildername: str) -> dict[str, Any]:
    return {
        "buildername": buildername,
        "files": [
            (Path("conf.py"), PART_PAGE_CONF),
            (Path("index.rst"), PART_PAGE_INDEX),
        ],
    }


def _built_part_page(app: Sphinx, page: str) -> str:
    """Build the page and read what the builder wrote for it."""
    app.build()
    return Path(app.outdir, page).read_text(encoding="utf-8")


def _assert_part_page_findings(app: Sphinx) -> None:
    """The page reports its two findings, and nothing its builder does not report on
    any page with a need."""
    assert sorted(build_warnings(app)) == sorted(
        PART_PAGE_FINDINGS + PART_PAGE_OTHER_WARNINGS.get(app.builder.name, [])
    )


def _words(written: str) -> str:
    """The text a writer wrote, with its table borders and its line breaks gone."""
    return " ".join(written.replace("|", " ").split())


@pytest.mark.parametrize(
    "test_app,page",
    [
        (_part_page("html"), "index.html"),
        (_part_page("dirhtml"), "index.html"),
        (_part_page("singlehtml"), "index.html"),
        (_part_page("epub"), "index.xhtml"),
    ],
    ids=["html", "dirhtml", "singlehtml", "epub"],
    indirect=["test_app"],
)
def test_a_part_in_the_html_family(test_app: Sphinx, page: str) -> None:
    """The html family writes a part's span exactly as before, the part's id on it, and
    a role repeating the part id shows its text, as plain text with no id: the
    repetition is no part. A role outside every need shows its text too.

    The repetition's and the outer role's text was dropped from the page.
    """
    html = _built_part_page(test_app, page)
    assert f"Marks {P1_SPAN} here." in html
    assert f"Marks {D1_SPAN} and the second here." in html
    assert html.count('id="REQ_1.d1"') == 1
    assert "Outside: outside text here." in html
    _assert_part_page_findings(test_app)

    # the stored parts are the first of each id, as they were: needs.json, the filters
    # and the links read them
    needs = SphinxNeedsData(test_app.env).get_needs_view()
    assert {
        part_id: dict(part) for part_id, part in needs["REQ_1"]["parts"].items()
    } == {
        "p1": {"id": "p1", "content": "a local part", "links_back": ["TEST_1"]},
        "d1": {"id": "d1", "content": "the first"},
    }


@pytest.mark.parametrize(
    "test_app,page",
    [(_part_page("text"), "index.txt"), (_part_page("man"), "parts.1")],
    ids=["text", "man"],
    indirect=["test_app"],
)
def test_a_repeated_part_shows_its_text_in_text_and_man(
    test_app: Sphinx, page: str
) -> None:
    """``text`` and ``man`` write no anchors: a part is its text and its id, and a
    repetition of the id, or a role outside every need, is its text."""
    written = _words(_built_part_page(test_app, page))
    assert "Marks a local part p1 here." in written
    assert "Marks the first d1 and the second here." in written
    assert "Outside: outside text here." in written
    _assert_part_page_findings(test_app)


@pytest.mark.parametrize(
    "test_app", [_part_page("latex")], ids=["latex"], indirect=True
)
def test_a_part_has_a_label_in_latex(test_app: Sphinx) -> None:
    """LaTeX writes a ``\\label`` for a part's address, once, where the part is, so the
    ``\\hyperref`` of every link and reference to it resolves; the LaTeX writer labels
    no ``inline``'s ids, and wrote none. A repetition of the id writes no label."""
    tex = _built_part_page(test_app, "parts.tex")
    label = r"\phantomsection\label{\detokenize{index:REQ_1.p1}}"
    assert rf"Marks \DUrole{{need-part}}{{{label}a local part{{\hyperref" in tex
    assert tex.count(label) == 1
    assert tex.count(r"\label{\detokenize{index:REQ_1.d1}}") == 1
    labels = re.findall(r"\\label\{\\detokenize\{(index:REQ_1\.[^}]*)\}\}", tex)
    references = re.findall(r"\\hyperref\[\\detokenize\{(index:REQ_1\.[^}]*)\}\]", tex)
    assert sorted(labels) == ["index:REQ_1.d1", "index:REQ_1.p1"]
    assert set(references) == set(labels)
    assert "{ d1}}}} and the second here." in tex
    assert "Outside: outside text here." in tex
    _assert_part_page_findings(test_app)

    # the address is the target's alone: the part's inline gave its id up
    doctree = test_app.env.get_and_resolve_doctree("index", test_app.builder)
    holders = [
        node for node in doctree.findall(nodes.Element) if "REQ_1.p1" in node["ids"]
    ]
    assert [type(node) for node in holders] == [nodes.target]


@pytest.mark.parametrize(
    "test_app", [_part_page("texinfo")], ids=["texinfo"], indirect=True
)
def test_a_part_has_its_anchor_in_place_in_texinfo(test_app: Sphinx) -> None:
    """texinfo writes a part's ``@anchor`` before the part's text, once; it wrote it
    after the last paragraph of the section, so a link to the part landed there."""
    texi = _built_part_page(test_app, "parts.texi")
    assert re.search(
        r"Marks @anchor\{index REQ_1 p1\}(@anchor\{\d+\})?a local part@ref\{", texi
    )
    assert texi.count("@anchor{index REQ_1 p1}") == 1
    assert re.search(
        r"Marks @anchor\{index REQ_1 d1\}(@anchor\{\d+\})?the first@ref\{[^}]*\} and "
        r"the second here\.",
        texi,
    )
    assert texi.count("@anchor{index REQ_1 d1}") == 1
    assert "Outside: outside text here." in texi
    _assert_part_page_findings(test_app)


PART_IN_A_TITLE_INDEX = """\
Index
=====

Section :np:`(t1) in a title`
-----------------------------

Body.
"""


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "files": [
                (Path("conf.py"), PART_PAGE_CONF),
                (Path("index.rst"), PART_IN_A_TITLE_INDEX),
            ],
        }
    ],
    ids=["html"],
    indirect=True,
)
def test_a_part_in_a_section_title_is_left_as_it_was(test_app: Sphinx) -> None:
    """A role in a section title shows no text in the heading, as in the entries of the
    tables of contents, which Sphinx copied from the title when the page was read: a
    role outside every need shows its text everywhere else, but here the heading would
    then read otherwise than its entries."""
    html = _built_part_page(test_app, "index.html")
    assert '<h2>Section <a class="headerlink" href="#section"' in html
    assert "in a title" not in html
    assert "in a title" not in test_app.env.tocs["index"].astext()
    assert build_warnings(test_app) == [
        "<srcdir>/index.rst:4: WARNING: Need part not associated with a need. "
        "[needs.part]"
    ]
