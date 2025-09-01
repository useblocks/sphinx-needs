import json
import os
from pathlib import Path

import pytest
from sphinx.application import Sphinx
from sphinx.util.console import strip_colors
from syrupy.extensions.json import JSONSnapshotExtension

from sphinx_needs.data import SphinxNeedsData


@pytest.fixture
def snapshot_json(snapshot):
    return snapshot.use_extension(JSONSnapshotExtension)


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "html", "srcdir": "doc_test/doc_need_parts", "no_plantuml": True}],
    indirect=True,
)
def test_doc_need_parts(test_app: Sphinx, snapshot_json):
    app = test_app
    app.build()

    warnings = strip_colors(
        app._warning.getvalue().replace(str(app.srcdir) + os.sep, "srcdir/")
    ).splitlines()
    # print(warnings)
    assert warnings == [
        "srcdir/index.rst:38: WARNING: Need 'OTHER_1' has unknown outgoing link 'SP_TOO_001.unknown_part' in field 'links' [needs.link_outgoing]",
        "srcdir/index.rst:26: WARNING: Need part not associated with a need. [needs.part]",
        "srcdir/index.rst:36: WARNING: linked need part SP_TOO_001.unknown_part not found [needs.link_ref]",
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
