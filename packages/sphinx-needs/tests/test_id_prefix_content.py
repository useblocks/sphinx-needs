"""An ``id_prefix`` rewrites an id of the file in a need's content only where it
stands as a whole id.

Beside the word boundary, an id of the file that is one end of a longer ``::``-joined
id is not rewritten: ``other::PLAIN_1`` names ``other::PLAIN_1``, not the file's
``PLAIN_1``. A single ``:`` is still a boundary, and so is a ``::`` that ends the text
or is followed by white space (a literal block marker).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from sphinx.testing.util import SphinxTestApp

from sphinx_needs.utils import import_prefix_link_edit

FILE_IDS = ["PLAIN_1", "nc::REQ_1"]

DEEP_IDS = ["Z" * n for n in range(1, 1200)]
"""Ids that make the trie too deep for the pattern compiler: the pattern then falls
back to one alternation, which must apply the same rule."""

ROWS = [
    # (content, expected with the prefix written as {p})
    ("PLAIN_1", "{p}PLAIN_1"),
    (":need:`PLAIN_1`", ":need:`{p}PLAIN_1`"),
    ("PLAIN_1: x", "{p}PLAIN_1: x"),
    ("(PLAIN_1)", "({p}PLAIN_1)"),
    ("x:PLAIN_1", "x:{p}PLAIN_1"),
    ("PLAIN_1:x", "{p}PLAIN_1:x"),
    ("nc::REQ_1", "{p}nc::REQ_1"),
    ("other::PLAIN_1", "other::PLAIN_1"),
    ("PLAIN_1::x", "PLAIN_1::x"),
    ("other::nc::REQ_1", "other::nc::REQ_1"),
    ("nc::REQ_1::x", "nc::REQ_1::x"),
    ("a-::PLAIN_1", "a-::PLAIN_1"),
    ("PLAIN_1::-x", "PLAIN_1::-x"),
    ("ü::PLAIN_1", "ü::PLAIN_1"),
    ("see PLAIN_1::\n\n   literal", "see {p}PLAIN_1::\n\n   literal"),
    ("see PLAIN_1::", "see {p}PLAIN_1::"),
    ("PLAIN_1:: x", "{p}PLAIN_1:: x"),
    ("x ::PLAIN_1", "x ::{p}PLAIN_1"),
    ("x:::PLAIN_1", "x:::{p}PLAIN_1"),
    # after the id, too, only a word character or ``-`` beyond the ``::`` joins
    ("PLAIN_1::.", "{p}PLAIN_1::."),
    ("PLAIN_1:::x", "{p}PLAIN_1:::x"),
    ("PLAIN_1::ü", "PLAIN_1::ü"),
    (
        "Words: nc::REQ_1, other::PLAIN_1, PLAIN_1::x, PLAIN_1.",
        "Words: {p}nc::REQ_1, other::PLAIN_1, PLAIN_1::x, {p}PLAIN_1.",
    ),
]


def _rewrite(content: str, prefix: str, known_ids: list[str]) -> dict[str, Any]:
    need = {"id": "PLAIN_1", "content": content, "description": content}
    import_prefix_link_edit({"PLAIN_1": need}, prefix, [], known_ids=known_ids)
    return need


@pytest.mark.parametrize("form", ["trie", "alternation"])
@pytest.mark.parametrize("prefix", ["SUP::", "SUP_"])
@pytest.mark.parametrize(("content", "expected"), ROWS)
def test_content_rewrite(content: str, expected: str, prefix: str, form: str):
    known_ids = FILE_IDS + (DEEP_IDS if form == "alternation" else [])
    need = _rewrite(content, prefix, known_ids)
    assert need["content"] == expected.format(p=prefix)
    assert need["description"] == expected.format(p=prefix)


@pytest.mark.parametrize("form", ["trie", "alternation"])
def test_neither_end_of_a_joined_id_is_rewritten(form: str):
    """With ``REQ_1`` an id of the file too, ``other::nc::REQ_1`` keeps both ends."""
    known_ids = [*FILE_IDS, "REQ_1"] + (DEEP_IDS if form == "alternation" else [])
    need = _rewrite("other::nc::REQ_1, nc::REQ_1, REQ_1", "SUP::", known_ids)
    assert need["content"] == "other::nc::REQ_1, SUP::nc::REQ_1, SUP::REQ_1"


SOURCE = {
    "current_version": "1.0",
    "versions": {
        "1.0": {
            "needs": {
                "nc::REQ_1": {"id": "nc::REQ_1", "type": "req", "title": "Req one"},
                "PLAIN_1": {"id": "PLAIN_1", "type": "spec", "title": "Plain"},
                "PLAIN_2": {
                    "id": "PLAIN_2",
                    "type": "spec",
                    "title": "Plain 2",
                    "content": (
                        "Words: nc::REQ_1, other::PLAIN_1, PLAIN_1::x, PLAIN_1 and "
                        ":need:`nc::REQ_1` and :need:`PLAIN_1`."
                    ),
                },
            }
        }
    },
}

CONF = """\
extensions = ["sphinx_needs"]
needs_build_json = True
"""

INDEX = """\
Import
======

.. needimport:: source.json
   :id_prefix: SUP::
"""


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "files": [
                (Path("conf.py"), CONF),
                (Path("index.rst"), INDEX),
                (Path("source.json"), json.dumps(SOURCE)),
            ],
        }
    ],
    indirect=True,
)
def test_needimport_content(test_app: SphinxTestApp):
    app = test_app
    app.build()

    data = json.loads(Path(app.outdir, "needs.json").read_text(encoding="utf-8"))
    needs = data["versions"][data["current_version"]]["needs"]
    assert needs["SUP::PLAIN_2"]["content"] == (
        "Words: SUP::nc::REQ_1, other::PLAIN_1, PLAIN_1::x, SUP::PLAIN_1 and "
        ":need:`SUP::nc::REQ_1` and :need:`SUP::PLAIN_1`."
    )
