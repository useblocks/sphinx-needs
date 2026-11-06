"""A ``:need:`` reference to a part of an external need (#2487).

The external needs are read from ``upstream_needs.json``, which sphinx-needs wrote for a
page whose need ``UP_001`` has the parts ``p1`` and ``p2``; that page's HTML gives each
part the anchor ``UP_001.<part>`` (``test_need_parts.py`` pins the anchor a part gets).
"""

from pathlib import Path

import pytest
from sphinx.application import Sphinx

from sphinx_needs_testkit import build_warnings


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "html", "srcdir": "doc_test/doc_external_need_parts"}],
    indirect=True,
)
def test_external_need_part_reference(test_app: Sphinx):
    """A part reference names the part and links its anchor; a whole need is unchanged.

    A reference to a part of an external need is written as one to a part of a need of
    the project: the part's text and the full ``ID.part`` (or the text given in the
    role), in the role's ``<em class="xref need">``, keeping the external css class.
    Its link is the external need's URL, whose fragment, when the need's id ends with it
    (the default URL, with or without an ``id_prefix``), is followed by ``.<part>``; a
    ``target_url`` of another shape is kept as it is.
    """
    app = test_app
    app.build()

    # the part check is unchanged: a part the external need does not have is warned
    assert build_warnings(app) == [
        "<srcdir>/index.rst:10: WARNING: linked need part UP_001.nope not found [needs.link_ref]",
    ]

    html = Path(app.outdir, "index.html").read_text()
    url = "https://up.example.org/docs"
    expected = {
        # a whole external need: its id, as before
        "Need": (
            f'<a class="external_link reference external" href="{url}/index.html#UP_001">'
            "UP_001</a>"
        ),
        "Part": (
            f'<a class="external_link reference external" href="{url}/index.html#UP_001.p1">'
            '<em class="xref need">first part text (UP_001.p1)</em></a>'
        ),
        "Named part": (
            f'<a class="external_link reference external" href="{url}/index.html#UP_001.p2">'
            '<em class="xref need">Custom text (UP_001.p2)</em></a>'
        ),
        # unresolved, as a reference to a missing local part is
        "Missing part": (
            '<a class="reference internal" href="#Unknown need" title="UP_001.nope?">'
            '<em class="xref need">UP_001.nope</em></a>'
        ),
        "Prefixed need": (
            f'<a class="external_link reference external" href="{url}/index.html#UP_001">'
            "EXT_UP_001</a>"
        ),
        # the URL's fragment is the upstream id, without the prefix
        "Prefixed part": (
            f'<a class="external_link reference external" href="{url}/index.html#UP_001.p1">'
            '<em class="xref need">first part text (EXT_UP_001.p1)</em></a>'
        ),
        # a target_url without a fragment, and one whose fragment is not the id: as given
        "Target URL part": (
            f'<a class="external_link reference external" href="{url}/issue/UP_001">'
            '<em class="xref need">first part text (TGT_UP_001.p1)</em></a>'
        ),
        "Anchored target URL part": (
            f'<a class="external_link reference external" href="{url}/page.html#req-UP_001">'
            '<em class="xref need">second part text (ANC_UP_001.p2)</em></a>'
        ),
    }
    wrong = [
        label
        for label, anchor in expected.items()
        if f"<p>{label}: {anchor}</p>" not in html
    ]
    assert wrong == []
