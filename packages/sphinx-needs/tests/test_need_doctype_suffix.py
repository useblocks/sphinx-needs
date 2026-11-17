"""A need's ``doctype`` is the markup its content is written in.

A need inside ``{eval-rst}`` on a MyST page is ``.rst`` (the conformance corpus pins
it). Only a docutils reStructuredText state on a page MyST parses gives ``.rst``: a page
with another suffix that docutils parses as reStructuredText (``.txt``) keeps its own
suffix, as every need on a page did before.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

CONF = """\
extensions = ["sphinx_needs", "myst_parser"]
needs_build_json = True
source_suffix = {".rst": "restructuredtext", ".txt": "restructuredtext", ".md": "markdown"}
"""


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "needs",
            "files": [
                (Path("conf.py"), CONF),
                (Path("index.rst"), "Index\n=====\n\n.. toctree::\n\n   other\n"),
                (Path("other.txt"), "Other\n=====\n\n.. req:: T\n   :id: REQ_TXT\n"),
            ],
        }
    ],
    indirect=True,
)
def test_a_need_on_an_rst_page_of_another_suffix_keeps_it(test_app: Any) -> None:
    app = test_app
    app.build()
    data = json.loads(Path(app.outdir, "needs.json").read_text(encoding="utf-8"))
    needs = data["versions"][data["current_version"]]["needs"]
    assert needs["REQ_TXT"]["doctype"] == ".txt"
