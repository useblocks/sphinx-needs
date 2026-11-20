import json
from pathlib import Path

import pytest
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
        "<srcdir>/index.rst:8: WARNING: part_need id p1 in need REQ_001 is already taken. need_part may get overridden. [needs.duplicate_part_id]",
        "<srcdir>/index.rst:13: WARNING: part_need id p1 in need REQ_002 is already taken. need_part may get overridden. [needs.duplicate_part_id]",
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
def test_add_need_warns_of_the_parts_it_drops(test_app: Sphinx):
    """``add_need`` warns once per need of the given ``parts`` a need on a page drops.

    A need on a page takes its parts from its content, which replaces the parts given
    to ``add_need``: that loss was silent. The result stays as it was; what changes is
    one ``needs.part`` warning per need, naming the ids it drops. A given id the
    content marks too is not dropped (the content's text wins), and a hidden or an
    external need keeps the given parts, so none of those warns.
    """
    app = test_app
    with pytest.warns(DeprecationWarning, match="add_need is deprecated"):
        app.build()

    assert build_warnings(app) == [
        "<srcdir>/index.rst:4: WARNING: Need 'ADD_PLAIN': the parts ['ap', 'bp'] given to add_need are dropped: a need on a page takes its parts from its content [needs.part]",
        "<srcdir>/index.rst:6: WARNING: Need 'ADD_MARKS_OTHER': the parts ['ap'] given to add_need are dropped: a need on a page takes its parts from its content [needs.part]",
    ]

    needs = SphinxNeedsData(app.env).get_needs_view()
    assert {
        need_id: {
            part_id: part["content"]
            for part_id, part in needs[need_id]["parts"].items()
        }
        for need_id in (
            "ADD_PLAIN",
            "ADD_MARKS_OTHER",
            "ADD_MARKS_SAME",
            "ADD_HIDDEN",
            "ADD_EXTERNAL",
            "ADD_EMPTY",
        )
    } == {
        "ADD_PLAIN": {},
        "ADD_MARKS_OTHER": {"cp": "content cp"},
        "ADD_MARKS_SAME": {"ap": "content ap"},
        "ADD_HIDDEN": {"ap": "given ap"},
        "ADD_EXTERNAL": {"ap": "given ap"},
        "ADD_EMPTY": {},
    }


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
    """An external need given a part whose text has white space at its ends."""

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
"""

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
    """A part given to ``add_need`` for an external need keeps its text byte for byte."""
    parts = _build_edge_space(test_app)
    assert parts["EXT_STATED"] == {"sp": "  given with spaces\t"}


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
