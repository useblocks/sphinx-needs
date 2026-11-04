"""A link type named ``full_title`` is kept on the record routes (#2466).

``full_title`` is a legacy key of a needs.json record, computed rather than read, so the
record routes dropped it -- unless the project declares a FIELD of that name (#2392). A
LINK type of that name was dropped too, silently: a ``needimport`` or
``needs_external_needs`` record lost its links of that type, while a need directive kept
them.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from sphinx.testing.util import SphinxTestApp

from sphinx_needs.data import SphinxNeedsData
from sphinx_needs_testkit import build_warnings

CONF = """\
extensions = ["sphinx_needs"]
needs_links = {"full_title": {}}
needs_external_needs = [{"base_url": "http://example.org", "json_path": "ext.json"}]
"""

INDEX = """\
A link type named full_title
============================

.. req:: The target
   :id: REQ_T

.. req:: A directive need
   :id: R_DIR
   :full_title: REQ_T

.. needimport:: imp.json
"""


def _needs_json(need_id: str) -> str:
    need = {
        "id": need_id,
        "type": "req",
        "title": f"a record {need_id}",
        "full_title": ["REQ_T"],
    }
    return json.dumps(
        {"current_version": "1.0", "versions": {"1.0": {"needs": {need_id: need}}}}
    )


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "files": [
                (Path("conf.py"), CONF),
                (Path("index.rst"), INDEX),
                (Path("imp.json"), _needs_json("R_IMP")),
                (Path("ext.json"), _needs_json("R_EXT")),
            ],
        }
    ],
    indirect=True,
)
def test_a_link_type_named_full_title_is_kept_on_every_route(test_app: SphinxTestApp):
    """The directive need (the control), the imported and the external need each keep
    their ``full_title`` link, and the target has all three as back links."""
    app = test_app
    app.build()
    assert build_warnings(app) == []
    needs = SphinxNeedsData(app.env).get_needs_view()
    assert {
        need_id: needs[need_id]["full_title"] for need_id in ("R_DIR", "R_IMP", "R_EXT")
    } == {"R_DIR": ["REQ_T"], "R_IMP": ["REQ_T"], "R_EXT": ["REQ_T"]}
    assert sorted(needs["REQ_T"]["full_title_back"]) == ["R_DIR", "R_EXT", "R_IMP"]
