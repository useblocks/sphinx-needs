"""``:need_outgoing:`` and ``:need_incoming:``, where a part address is their target, and
the need card's outgoing row, where a link names a part of an external need.

Where a need is expected, a part address reads as its need (``design/parts-contract.md``):
a role naming ``REQ_1.p1`` lists the links of ``REQ_1``, exactly as one naming ``REQ_1``.
An address naming a part its need does not have, or a need that does not exist, does not
resolve: it is reported as ``:need:`` reports it, and rendered as ``:need:`` renders an
unresolved reference. Each of those ended the build with a ``KeyError`` of the target,
the unknown need included **(changed output)**.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from sphinx.application import Sphinx

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
    [
        pytest.param(_project(role, "REQ_1.p1"), role, id=role)
        for role in ("need_outgoing", "need_incoming")
    ],
    indirect=["test_app"],
)
def test_a_part_address_reads_as_its_need(test_app: Sphinx, role: str):
    """``REQ_1.p1`` lists what ``REQ_1`` lists, rendered byte for byte as the role naming
    the need renders it."""
    app = test_app
    app.build()
    assert build_warnings(app) == []
    html = Path(app.outdir, "index.html").read_text(encoding="utf8")
    assert _paragraph(html, "Need") == _listed(role)
    assert _paragraph(html, "Target") == _paragraph(html, "Need")


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
    """A role naming a part of the need whose content holds it reads that need."""
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
                # the text of a part marked `(p1) local part` keeps its leading space
                " local part (REQ_1.p1)",
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
