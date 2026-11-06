import json
from pathlib import Path

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
