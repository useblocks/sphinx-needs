"""An external need is decorated by the project's default templates, outside any read.

``needs_external_needs`` creates its needs at ``env-before-read-docs``, before any
document is read. A template the project gives every need through ``needs_fields``
(a ``default``) decorates them too, as it always has. Its file is a dependency only of a
document being read: an external need has none, and noting one there failed the build
on Sphinx 7.4 (``KeyError: 'docname'``).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from sphinx_needs.data import SphinxNeedsData
from sphinx_needs_testkit import build_warnings

RECORDS = json.dumps(
    {
        "current_version": "1.0",
        "versions": {
            "1.0": {
                "needs": {
                    "X_1": {"id": "X_1", "type": "req", "title": "X", "content": "body"}
                }
            }
        },
    }
)

CONF = """\
extensions = ["sphinx_needs"]
needs_external_needs = [
    {"base_url": "http://x", "json_path": "ext.json", "id_prefix": "EXT_"}
]
needs_fields = {"pre_template": {"default": "pre"}}
"""


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "files": [
                (Path("conf.py"), CONF),
                (
                    Path("index.rst"),
                    "Index\n=====\n\n.. req:: Local\n   :id: REQ_LOCAL\n",
                ),
                (Path("ext.json"), RECORDS),
                (Path("needs_templates", "pre.need"), "PRE {{ id }}\n"),
            ],
        }
    ],
    indirect=True,
)
def test_an_external_need_takes_the_projects_default_pre_template(
    test_app: Any,
) -> None:
    app = test_app
    app.build()
    assert build_warnings(app) == []
    needs = SphinxNeedsData(app.env).get_needs_view()
    assert needs["EXT_X_1"]["pre_template"] == "pre"
    assert needs["EXT_X_1"]["pre_content"] == "PRE EXT_X_1"
    assert needs["REQ_LOCAL"]["pre_content"] == "PRE REQ_LOCAL"
