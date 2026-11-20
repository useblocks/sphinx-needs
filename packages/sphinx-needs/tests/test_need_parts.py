import io
import json
from pathlib import Path
from typing import Any

import pytest
from sphinx.application import Sphinx
from syrupy.extensions.json import JSONSnapshotExtension

from sphinx_needs.data import SphinxNeedsData
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
