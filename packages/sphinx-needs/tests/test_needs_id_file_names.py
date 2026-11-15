"""The names of the files ``needs_build_json_per_id`` writes, one per need.

A need id may hold characters a file name cannot (``SUPPLIER::REQ_1``, accepted by the
default ``needs_id_regex``, holds ``:``, which Windows refuses): each such character is
written as ``%`` and two upper-case hex digits, in both needs.json formats.

No test here creates a file whose name holds ``:`` once the names are encoded, so the
module runs on Windows too.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from sphinx.testing.util import SphinxTestApp

INDEX = """\
Per-id files
============

.. req:: Supplier
   :id: SUPPLIER::REQ_1

.. req:: Plain
   :id: REQ_PLAIN
"""

CONF_1 = """\
extensions = ["sphinx_needs"]
needs_build_json_per_id = True
"""

CONF_2A1 = """\
extensions = ["sphinx_needs"]
needs_build_json_per_id = True
needs_json_format_version = "2a1"
"""


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "files": [(Path("conf.py"), CONF_1), (Path("index.rst"), INDEX)],
        }
    ],
    indirect=True,
)
def test_format_1_file_names(test_app: SphinxTestApp):
    app = test_app
    app.build()

    folder = Path(app.outdir, "needs_id")
    assert sorted(path.name for path in folder.iterdir()) == [
        "REQ_PLAIN.json",
        "SUPPLIER%3A%3AREQ_1.json",
    ]
    data = _read(folder / "SUPPLIER%3A%3AREQ_1.json")
    needs = data["versions"][data["current_version"]]["needs"]
    assert list(needs) == ["SUPPLIER::REQ_1"]
    assert needs["SUPPLIER::REQ_1"]["id"] == "SUPPLIER::REQ_1"


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "files": [(Path("conf.py"), CONF_2A1), (Path("index.rst"), INDEX)],
        }
    ],
    indirect=True,
)
def test_format_2a1_file_names(test_app: SphinxTestApp):
    app = test_app
    app.build()

    folder = Path(app.outdir, "needs_id")
    assert sorted(path.name for path in folder.iterdir()) == [
        "REQ_PLAIN.json",
        "SUPPLIER%3A%3AREQ_1.json",
    ]
    data = _read(folder / "SUPPLIER%3A%3AREQ_1.json")
    assert [record["id"] for record in data["needs"]] == ["SUPPLIER::REQ_1"]
