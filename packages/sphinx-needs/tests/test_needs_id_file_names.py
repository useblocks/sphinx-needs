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

CONF_DRAFT = """\
extensions = ["sphinx_needs"]
needs_build_json_per_id = True
needs_json_format_version = "2a2"
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
            "files": [(Path("conf.py"), CONF_DRAFT), (Path("index.rst"), INDEX)],
        }
    ],
    indirect=True,
)
def test_draft_file_names(test_app: SphinxTestApp):
    app = test_app
    app.build()

    folder = Path(app.outdir, "needs_id")
    assert sorted(path.name for path in folder.iterdir()) == [
        "REQ_PLAIN.json",
        "SUPPLIER%3A%3AREQ_1.json",
    ]
    data = _read(folder / "SUPPLIER%3A%3AREQ_1.json")
    assert [record["id"] for record in data["needs"]] == ["SUPPLIER::REQ_1"]


@pytest.mark.parametrize(
    ("need_id", "file_name"),
    [
        ("REQ_1", "REQ_1.json"),
        ("nc::REQ_1", "nc%3A%3AREQ_1.json"),
        ("a<b", "a%3Cb.json"),
        ("a>b", "a%3Eb.json"),
        ("a:b", "a%3Ab.json"),
        ('a"b', "a%22b.json"),
        ("a/b", "a%2Fb.json"),
        ("a\\b", "a%5Cb.json"),
        ("a|b", "a%7Cb.json"),
        ("a?b", "a%3Fb.json"),
        ("a*b", "a%2Ab.json"),
        ("50%", "50%25.json"),
        ("50%3A", "50%253A.json"),
        ("a\x00b", "a%00b.json"),
        ("a\tb", "a%09b.json"),
        ("a\x1fb", "a%1Fb.json"),
        # kept: everything else, DEL and non-ASCII text included
        ("a\x7fb", "a\x7fb.json"),
        ("REQ-1.a b'c;d=é", "REQ-1.a b'c;d=é.json"),
    ],
)
def test_id_file_name(need_id: str, file_name: str):
    from sphinx_needs.builder import _id_file_name

    assert _id_file_name(need_id) == file_name


def test_id_file_names_are_distinct():
    """``%`` is encoded too, so an id that reads like an encoded one keeps its own name."""
    from sphinx_needs.builder import _id_file_name

    ids = ["a:b", "a%3Ab", "a%b", "a%253Ab"]
    assert len({_id_file_name(need_id) for need_id in ids}) == len(ids)
