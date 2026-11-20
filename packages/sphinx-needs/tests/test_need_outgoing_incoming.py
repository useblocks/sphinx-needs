"""``:need_outgoing:`` and ``:need_incoming:``, where a part address is their target, and
the need card's outgoing row, where a link names a part of an external need.

Where a need is expected, a part address reads as its need (``design/parts-contract.md``):
``:need_outgoing:`` naming ``REQ_1.p1`` lists the links of ``REQ_1``, exactly as one naming
``REQ_1``, since a part has no links of its own. A part has back links of its own, so
``:need_incoming:`` naming ``REQ_1.p1`` lists those: the links naming that part, and only
those. An address naming a part its need does not have, or a need that does not exist, does not
resolve: it is reported as ``:need:`` reports it, and rendered as ``:need:`` renders an
unresolved reference. Each of those ended the build with a ``KeyError`` of the target,
the unknown need included **(changed output)**.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from sphinx.application import Sphinx

from sphinx_needs.data import SphinxNeedsData
from sphinx_needs_testkit import build_warnings

CONF = 'extensions = ["sphinx_needs"]\n'

NAMESPACED_CONF = CONF + "needs_namespaced_ids = True\n"

ROLES = """\
Roles
=====

.. req:: Target
   :id: {ns}REQ_1
   :links: {ns}REQ_2

   The target, with :np:`(p1) the part`.

.. req:: Linked
   :id: {ns}REQ_2

.. spec:: Links the part
   :id: {ns}SPEC_1
   :links: {ns}REQ_1.p1

.. test:: Links the need
   :id: {ns}TEST_1
   :links: {ns}REQ_1

Need: :{role}:`{ns}REQ_1`

Target: :{role}:`{target}`
"""

#: the line of the ``Target:`` paragraph in :data:`ROLES`
TARGET_LINE = 23

#: ``:need:`` given the role's target, after :data:`ROLES`
REF = "\nRef: :need:`{target}`\n"

#: the line of the ``Ref:`` paragraph of :data:`REF`
REF_LINE = 25


def _project(role: str, target: str) -> dict[str, object]:
    return {
        "buildername": "html",
        "files": [
            (Path("conf.py"), CONF),
            (Path("index.rst"), ROLES.format(role=role, target=target, ns="")),
        ],
    }


def _namespaced_project(role: str, target: str) -> dict[str, object]:
    """:data:`ROLES` with every need in the namespace ``nc``, and ``:need:`` given the
    role's target."""
    index = ROLES.format(role=role, target=target, ns="nc::") + REF.format(
        target=target
    )
    return {
        "buildername": "html",
        "files": [(Path("conf.py"), NAMESPACED_CONF), (Path("index.rst"), index)],
    }


def _paragraph(html: str, label: str) -> str:
    """The HTML of the paragraph ``<label>: …``, after its label."""
    match = re.search(rf"<p>{re.escape(label)}: (.*?)</p>", html, re.S)
    assert match is not None, label
    return match[1]


def _unresolved(role: str, target: str) -> str:
    """``:need:``'s rendering of a reference that does not resolve."""
    return (
        f'<a class="reference internal" href="#Unknown need" title="{target}?">'
        f'<em class="xref {role}">{target}</em></a>'
    )


def _not_found(
    target: str, *, part: bool = False, hint: str = "", line: int = TARGET_LINE
) -> str:
    """``:need:``'s report of a reference that does not resolve."""
    noun = "need part" if part else "need"
    return (
        f"<srcdir>/index.rst:{line}: WARNING: linked {noun} {target} not found{hint} "
        "[needs.link_ref]"
    )


#: what each role lists for ``{ns}REQ_1``, rendered: its outgoing link, and the needs
#: linking it, through its part and whole, each linked to its anchor
LISTED = {
    "need_outgoing": (
        '<a class="reference internal" href="#{ns}REQ_2" title="{ns}REQ_1">{ns}REQ_2</a>'
    ),
    "need_incoming": (
        '<a class="reference internal" href="#{ns}SPEC_1" title="{ns}REQ_1">'
        "{ns}SPEC_1</a>, "
        '<a class="reference internal" href="#{ns}TEST_1" title="{ns}REQ_1">'
        "{ns}TEST_1</a>"
    ),
}


def _listed(role: str, ns: str = "") -> str:
    """What *role* lists for the need ``{ns}REQ_1`` of :data:`ROLES`, rendered."""
    return f"<span>{LISTED[role].format(ns=ns)}</span>"


@pytest.mark.parametrize(
    "test_app,role",
    [pytest.param(_project("need_outgoing", "REQ_1.p1"), "need_outgoing", id="found")],
    indirect=["test_app"],
)
def test_need_outgoing_on_a_part_address_reads_as_its_need(test_app: Sphinx, role: str):
    """``REQ_1.p1`` lists what ``REQ_1`` lists, rendered byte for byte as the role naming
    the need renders it: a part has no links of its own."""
    app = test_app
    app.build()
    assert build_warnings(app) == []
    html = Path(app.outdir, "index.html").read_text(encoding="utf8")
    assert _paragraph(html, "Need") == _listed(role)
    assert _paragraph(html, "Target") == _paragraph(html, "Need")


def _incoming(target: str, *sources: str) -> str:
    """What ``:need_incoming:`` naming *target* (or a part of it) renders, listing
    *sources*, each linked to its anchor; ``None`` when it lists nothing."""
    if not sources:
        return "<span>None</span>"
    return (
        "<span>"
        + ", ".join(
            f'<a class="reference internal" href="#{source}" title="{target}">'
            f"{source}</a>"
            for source in sources
        )
        + "</span>"
    )


INCOMING = """\
Incoming
========

.. req:: Parts
   :id: REQ_1

   :np:`(p1) one` and :np:`(p2) two`

.. spec:: Links the need
   :id: SPEC_A
   :links: REQ_1

.. spec:: Links the first part
   :id: SPEC_B
   :links: REQ_1.p1

.. spec:: Links the second part
   :id: SPEC_C
   :links: REQ_1.p2

Part: :need_incoming:`REQ_1.p1`

Need: :need_incoming:`REQ_1`
"""


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "files": [(Path("conf.py"), CONF), (Path("index.rst"), INCOMING)],
        }
    ],
    indirect=True,
    ids=["parts"],
)
def test_need_incoming_on_a_part_lists_the_parts_back_links(test_app: Sphinx):
    """``REQ_1.p1`` lists the links naming that part, and only those; ``REQ_1`` lists
    every link to the need, a link to one of its parts included."""
    app = test_app
    app.build()
    assert build_warnings(app) == []
    html = Path(app.outdir, "index.html").read_text(encoding="utf8")
    assert _paragraph(html, "Part") == _incoming("REQ_1", "SPEC_B")
    assert _paragraph(html, "Need") == _incoming("REQ_1", "SPEC_A", "SPEC_B", "SPEC_C")


def _ids(paragraph: str) -> list[str]:
    """The ids a ``:need_incoming:`` paragraph lists, in the order it lists them."""
    return re.findall(r'<a class="reference internal" [^>]*>([^<]+)</a>', paragraph)


SIBLINGS = """\
Siblings
========

.. req:: Parts
   :id: REQ_1

   :np:`(p1) one` and :np:`(p10) ten`

.. spec:: Links the first part
   :id: SPEC_F
   :links: REQ_1.p1

.. spec:: Links the tenth part only
   :id: SPEC_T
   :links: REQ_1.p10

.. spec:: Links the first part too
   :id: SPEC_B
   :links: REQ_1.p1

.. spec:: Blocks the first part
   :id: SPEC_K
   :blocks: REQ_1.p1

.. spec:: Blocks the need
   :id: SPEC_M
   :blocks: REQ_1

Part: :need_incoming:`REQ_1.p1`

Need: :need_incoming:`REQ_1`
"""

#: :data:`SIBLINGS`, with the second link type ``blocks``
SIBLINGS_PROJECT = {
    "buildername": "html",
    "files": [
        (Path("conf.py"), CONF + 'needs_links = {"blocks": {}}\n'),
        (Path("index.rst"), SIBLINGS),
    ],
}


def _siblings(app: Sphinx) -> tuple[list[str], list[str]]:
    """Build :data:`SIBLINGS`: the ids listed for ``REQ_1.p1`` and for ``REQ_1``."""
    app.build()
    assert build_warnings(app) == []
    html = Path(app.outdir, "index.html").read_text(encoding="utf8")
    return _ids(_paragraph(html, "Part")), _ids(_paragraph(html, "Need"))


@pytest.mark.parametrize(
    "test_app", [SIBLINGS_PROJECT], indirect=True, ids=["siblings"]
)
def test_need_incoming_on_a_part_is_not_a_prefix_of_its_siblings(test_app: Sphinx):
    """``REQ_1.p1`` does not list ``SPEC_T``, which links ``REQ_1.p10`` alone, an
    address ``REQ_1.p1`` is a prefix of; ``REQ_1`` lists it."""
    part, need = _siblings(test_app)
    assert "SPEC_T" not in part
    assert set(part) == {"SPEC_F", "SPEC_B"}
    assert "SPEC_T" in need


@pytest.mark.parametrize(
    "test_app", [SIBLINGS_PROJECT], indirect=True, ids=["siblings"]
)
def test_need_incoming_on_a_part_reads_one_link_type(test_app: Sphinx):
    """The plain form reads ``links`` alone, on the part as on the need: neither lists
    ``SPEC_K``, which blocks ``REQ_1.p1``, and ``REQ_1`` does not list ``SPEC_M``, which
    blocks it whole."""
    part, need = _siblings(test_app)
    assert not {"SPEC_K", "SPEC_M"} & set(need)
    assert "SPEC_K" not in part
    assert set(part) == {"SPEC_F", "SPEC_B"}


@pytest.mark.parametrize(
    "test_app", [SIBLINGS_PROJECT], indirect=True, ids=["siblings"]
)
def test_need_incoming_on_a_part_lists_in_the_parts_stored_order(test_app: Sphinx):
    """``REQ_1.p1`` lists the needs linking it in the order the part's stored back links
    hold them, read from the build's data."""
    part, _ = _siblings(test_app)
    stored = SphinxNeedsData(test_app.env).get_needs_view()["REQ_1"].get_part("p1")
    assert stored is not None
    order = [link.to_filter_string() for link in stored.backlinks["links"]]
    assert len(order) == 2
    assert part == order


#: a role writing the node the need card's incoming row writes, ``NeedIncoming`` with a
#: ``link_type``, for a target the role's text gives: ``<target> <link type>_back``
BY_TYPE_CONF = """\
from docutils import nodes

from sphinx_needs.roles.need_incoming import NeedIncoming

extensions = ["sphinx_needs"]
needs_links = {"blocks": {}}


def incoming_by_type(name, rawtext, text, lineno, inliner, options=None, content=None):
    target, link_type = text.split()
    node = NeedIncoming(reftarget=target, link_type=link_type)
    node.append(nodes.inline(target, target))
    return [node], []


def setup(app):
    app.add_role("incoming_by_type", incoming_by_type)
"""

BY_TYPE = """\
By type
=======

.. req:: Parts
   :id: REQ_1

   :np:`(p1) one` and :np:`(p2) two`

.. spec:: Blocks the first part
   :id: SPEC_B
   :blocks: REQ_1.p1

.. spec:: Links the first part
   :id: SPEC_L
   :links: REQ_1.p1

.. spec:: Blocks the need
   :id: SPEC_N
   :blocks: REQ_1

.. spec:: Blocks the second part
   :id: SPEC_O
   :blocks: REQ_1.p2

Part: :incoming_by_type:`REQ_1.p1 blocks_back`

Need: :incoming_by_type:`REQ_1 blocks_back`

Part links: :incoming_by_type:`REQ_1.p1 links_back`
"""


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "files": [(Path("conf.py"), BY_TYPE_CONF), (Path("index.rst"), BY_TYPE)],
        }
    ],
    indirect=True,
    ids=["blocks"],
)
def test_need_incoming_by_link_type_on_a_part(test_app: Sphinx):
    """The role's link-type form reads the same link type on the part: ``blocks`` of
    ``REQ_1.p1`` is ``SPEC_B`` alone, a ``links`` link to the part, a ``blocks`` link to
    the need and one to its other part kept out; on ``REQ_1`` it is every ``blocks``
    link to the need."""
    app = test_app
    app.build()
    assert build_warnings(app) == []
    html = Path(app.outdir, "index.html").read_text(encoding="utf8")
    assert _paragraph(html, "Part") == _incoming("REQ_1", "SPEC_B")
    assert _paragraph(html, "Need") == _incoming("REQ_1", "SPEC_B", "SPEC_N", "SPEC_O")
    assert _paragraph(html, "Part links") == _incoming("REQ_1", "SPEC_L")


@pytest.mark.parametrize(
    "test_app,role,target,part,ns,hint",
    [
        *(
            pytest.param(
                _project(role, target), role, target, part, "", "", id=f"{role}-{name}"
            )
            for role in ("need_outgoing", "need_incoming")
            for name, target, part in (
                # the need exists and does not have the part
                ("part-missing", "REQ_1.p9", True),
                # the need does not exist: it ended the build too (changed output)
                ("need-missing", "NOPE_1", False),
                ("part-of-a-missing-need", "NOPE_1.p1", False),
                # a condition is not taken off: ``p1[…]`` is a part REQ_1 does not have
                ("condition-after-the-part", "REQ_1.p1[is_need]", True),
            )
        ),
        # with namespaced ids, a need named without its namespace: the report offers
        # the hint ``:need:`` offers for the same target
        pytest.param(
            _namespaced_project("need_outgoing", "REQ_1"),
            "need_outgoing",
            "REQ_1",
            False,
            "nc::",
            " (did you mean 'nc::REQ_1'?)",
            id="need_outgoing-namespace-left-off",
        ),
    ],
    indirect=["test_app"],
)
def test_an_address_that_does_not_resolve(
    test_app: Sphinx, role: str, target: str, part: bool, ns: str, hint: str
):
    """It is reported as ``:need:`` reports it, naming the address as written, and
    rendered as ``:need:`` renders an unresolved reference; the build goes on."""
    app = test_app
    app.build()
    expected = [_not_found(target, part=part, hint=hint)]
    if ns:
        # ``:need:`` given the same target is reported first, with the same hint
        expected.insert(0, _not_found(target, part=part, hint=hint, line=REF_LINE))
    assert build_warnings(app) == expected
    html = Path(app.outdir, "index.html").read_text(encoding="utf8")
    assert _paragraph(html, "Target") == _unresolved(role, target)
    # the role naming the need, on the same page, is untouched
    assert _paragraph(html, "Need") == _listed(role, ns)


IN_OWN_CONTENT = """\
Roles
=====

.. req:: Target
   :id: REQ_1
   :links: REQ_2

   The target, with :np:`(p1) the part`.

   Target: :{role}:`REQ_1.p1`

.. req:: Linked
   :id: REQ_2

.. spec:: Links the part
   :id: SPEC_1
   :links: REQ_1.p1
"""


@pytest.mark.parametrize(
    "test_app,listed",
    [
        pytest.param(
            {
                "buildername": "html",
                "files": [
                    (Path("conf.py"), CONF),
                    (Path("index.rst"), IN_OWN_CONTENT.format(role=role)),
                ],
            },
            listed,
            id=role,
        )
        for role, listed in (
            (
                "need_outgoing",
                '<a class="reference internal" href="#REQ_2" title="REQ_1">REQ_2</a>',
            ),
            (
                "need_incoming",
                '<a class="reference internal" href="#SPEC_1" title="REQ_1">SPEC_1</a>',
            ),
        )
    ],
    indirect=["test_app"],
)
def test_a_role_in_its_needs_own_content(test_app: Sphinx, listed: str):
    """A role naming a part of the need whose content holds it resolves:
    ``:need_outgoing:`` lists the need's links, ``:need_incoming:`` the part's back
    links."""
    app = test_app
    app.build()
    assert build_warnings(app) == []
    html = Path(app.outdir, "index.html").read_text(encoding="utf8")
    assert _paragraph(html, "Target") == f"<span>{listed}</span>"


EXTERNAL_JSON = (
    '{"current_version": "1.0", "versions": {"1.0": {"needs": {'
    '"EXT_1": {"id": "EXT_1", "type": "req", "title": "External", "content": "", '
    '"links": ["EXT_2"], '
    '"parts": {"rp": {"id": "rp", "content": "a record part whose text runs past '
    'thirty characters"}, '
    '"a.b": {"id": "a.b", "content": "a dotted part"}}}, '
    '"EXT_2": {"id": "EXT_2", "type": "req", "title": "Second", "content": ""}}}}}'
)

EXTERNAL_CONF = """\
extensions = ["sphinx_needs"]
needs_external_needs = [
    {"base_url": "http://example.org", "json_path": "external.json"},
]
"""

#: the external source of :data:`EXTERNAL_CONF`, its needs' ids prefixed with ``X_``
PREFIXED_CONF = """\
extensions = ["sphinx_needs"]
needs_external_needs = [
    {"base_url": "http://example.org", "json_path": "external.json", "id_prefix": "X_"},
]
"""

CARD = """\
Card
====

.. req:: Local
   :id: REQ_1

   :np:`(p1) local part`

.. spec:: Linker
   :id: SPEC_1
   :links: {p}EXT_1, {p}EXT_1.a.b, {p}EXT_1.rp, REQ_1.p1

Ref: :need:`{p}EXT_1.rp`
"""

ROLE_ON_AN_EXTERNAL_PART = """\
Role
====

Out: :need_outgoing:`EXT_1.rp`
"""


def _external(conf: str, index: str) -> dict[str, object]:
    return {
        "buildername": "html",
        "files": [
            (Path("conf.py"), conf),
            (Path("external.json"), EXTERNAL_JSON),
            (Path("index.rst"), index),
        ],
    }


def _row(html: str, need_id: str) -> str:
    """The links of the outgoing row of the card of *need_id*."""
    card = html[html.index(f'id="{need_id}"') :]
    match = re.search(
        r'outgoing: <span class="links"><span>(.*?)</span></span>', card, re.S
    )
    assert match is not None
    return match[1]


#: an external need's URL: its record names no document
_URL = "http://example.org/__error__.html"


@pytest.mark.parametrize(
    "test_app,prefix,texts",
    [
        pytest.param(
            _external(EXTERNAL_CONF, CARD.format(p="")),
            "",
            ("EXT_1.rp", "REQ_1.p1", "EXT_1.a.b"),
            id="default",
        ),
        pytest.param(
            _external(
                EXTERNAL_CONF + "needs_show_link_title = True\n", CARD.format(p="")
            ),
            "",
            (
                # a part's text is cut at 30 characters, as for a local part
                "a record part whose text ru... (EXT_1.rp)",
                # the text of a part marked `(p1) local part` has no leading space
                "local part (REQ_1.p1)",
                "a dotted part (EXT_1.a.b)",
            ),
            id="show-link-title",
        ),
        pytest.param(
            _external(PREFIXED_CONF, CARD.format(p="X_")),
            "X_",
            ("X_EXT_1.rp", "REQ_1.p1", "X_EXT_1.a.b"),
            id="id-prefix",
        ),
    ],
    indirect=["test_app"],
)
def test_the_card_row_keeps_an_external_parts_address(
    test_app: Sphinx, prefix: str, texts: tuple[str, str, str]
):
    """The outgoing row shows a link to a part of an external need as it shows one to a
    local part (the part's text and ``ID.part``, as the row's configuration gives them),
    linked to the part's anchor, as ``:need:`` links it (a source's ``id_prefix``
    included); a link to the whole external need is unchanged. The row showed the
    need's id and linked the need's URL: the part was lost."""
    app = test_app
    app.build()
    assert build_warnings(app) == []
    html = Path(app.outdir, "index.html").read_text(encoding="utf8")
    external, local, dotted = texts
    externals = (
        f'<a class="external_link reference external" href="{_URL}#EXT_1">'
        f"{prefix}EXT_1</a>, "
        f'<a class="external_link reference external" href="{_URL}#EXT_1.a.b">'
        f"{dotted}</a>, "
        f'<a class="external_link reference external" href="{_URL}#EXT_1.rp">'
        f"{external}</a>"
    )
    local_part = (
        f'<a class="reference internal" href="#REQ_1.p1" title="SPEC_1">{local}</a>'
    )
    # the row lists its links sorted by id: ``X_EXT_1`` sorts after ``REQ_1``
    assert _row(html, "SPEC_1") == (
        f"{local_part}, {externals}" if prefix else f"{externals}, {local_part}"
    )
    # the part's anchor is the one ``:need:`` links for the same address
    row_href = re.search(
        rf'href="([^"]*)">{re.escape(external)}</a>', _row(html, "SPEC_1")
    )
    ref_href = re.search(r'href="([^"]*)"', _paragraph(html, "Ref"))
    assert row_href is not None
    assert ref_href is not None
    assert row_href[1] == f"{_URL}#EXT_1.rp"
    assert ref_href[1] == f"{_URL}#EXT_1.rp"
    assert row_href[1] == ref_href[1]


@pytest.mark.parametrize(
    "test_app",
    [_external(EXTERNAL_CONF, ROLE_ON_AN_EXTERNAL_PART)],
    indirect=True,
    ids=["found"],
)
def test_a_role_naming_a_part_of_an_external_need(test_app: Sphinx):
    """``:need_outgoing:`` naming a part of an external need lists that need's links."""
    app = test_app
    app.build()
    assert build_warnings(app) == []
    html = Path(app.outdir, "index.html").read_text(encoding="utf8")
    assert _paragraph(html, "Out") == (
        f'<span><a class="external_link reference external" href="{_URL}#EXT_2">'
        "EXT_2</a></span>"
    )


IMPORT_JSON = (
    '{"current_version": "1.0", "versions": {"1.0": {"needs": {'
    '"IMP_1": {"id": "IMP_1", "type": "req", "title": "Imported", '
    '"content": ":np:`(ip) an imported part`"}}}}}'
)

OTHER_PARTS = """\
Other parts
===========

.. needimport:: imported.json

.. req:: Linked whole only
   :id: REQ_1

   :np:`(p1) nothing links here`

.. req:: Nothing links here
   :id: LONE_1

.. spec:: Links the external part
   :id: SPEC_1
   :links: EXT_1.rp

.. spec:: Links the external need and the imported one
   :id: SPEC_2
   :links: EXT_1, IMP_1, REQ_1

.. spec:: Links the imported part
   :id: SPEC_3
   :links: IMP_1.ip

External: :need_incoming:`EXT_1.rp`

Imported: :need_incoming:`IMP_1.ip`

Unlinked: :need_incoming:`REQ_1.p1`

Lone: :need_incoming:`LONE_1`
"""


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "files": [
                (Path("conf.py"), EXTERNAL_CONF),
                (Path("external.json"), EXTERNAL_JSON),
                (Path("imported.json"), IMPORT_JSON),
                (Path("index.rst"), OTHER_PARTS),
            ],
        }
    ],
    indirect=True,
    ids=["external-imported-unlinked"],
)
def test_need_incoming_on_an_external_imported_or_unlinked_part(test_app: Sphinx):
    """The part an external need's record states, and the part an imported need's
    content marks, list their own back links; a part no need links to renders as a need
    no need links to renders, however many links its need has."""
    app = test_app
    app.build()
    assert build_warnings(app) == []
    html = Path(app.outdir, "index.html").read_text(encoding="utf8")
    assert _paragraph(html, "External") == _incoming("EXT_1", "SPEC_1")
    assert _paragraph(html, "Imported") == _incoming("IMP_1", "SPEC_3")
    assert _paragraph(html, "Lone") == _incoming("LONE_1")
    assert _paragraph(html, "Unlinked") == _paragraph(html, "Lone")
