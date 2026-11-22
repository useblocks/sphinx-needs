"""A needtable with ``:show_parts:`` lists a need part once, under its need.

A filter tests needs and parts alike, so a filter that matched a need and its part gave
the part a row of its own AND a ``:show_parts:`` row under its need: listed twice. With
``:show_parts:``, a part the filter matched gets no row of its own when its need is a row
(it is listed under its need); a matched part whose need is not a row keeps its own row.
That is decided before the sort and the ``max_items`` cap, so the cap counts the entries
as they are shown. A table without ``:show_parts:`` does not change.

The project has eight needs, five of them ``open`` with a part each or two (one nested,
one imported, one external), and a ``closed`` need with a part of its own.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from lxml import html as html_parser
from sphinx.application import Sphinx

from sphinx_needs_testkit import build_warnings

CONF = """\
extensions = ["sphinx_needs"]
needs_external_needs = [
    {"base_url": "http://example.org/", "json_path": "external.json"},
]
needs_views_include_parts = True
"""

IMPORTED = {
    "current_version": "1.0",
    "versions": {
        "1.0": {
            "needs": {
                "IMP_1": {
                    "id": "IMP_1",
                    "type": "req",
                    "title": "Imported",
                    "status": "open",
                    "content": "Marks :np:`(ip) imported part`.",
                }
            }
        }
    },
}

EXTERNAL = {
    "current_version": "1.0",
    "versions": {
        "1.0": {
            "needs": {
                "EXT_1": {
                    "id": "EXT_1",
                    "type": "req",
                    "title": "External",
                    "status": "open",
                    "content": "",
                    "parts": {"e1": {"id": "e1", "content": "external part"}},
                }
            }
        }
    },
}

INDEX = """\
Parts
=====

.. toctree::

   tables

.. req:: Alpha
   :id: REQ_A
   :status: open

   First :np:`(p1) brake fast` and :np:`(p2) steer well`.

   .. spec:: Nested
      :id: SPEC_N
      :status: open

      :np:`(n1) nested part`

.. req:: Beta
   :id: REQ_B
   :status: closed

   :np:`(b1) closed part`

.. test:: Test one
   :id: TEST_1
   :status: open
   :links: REQ_A.p1, REQ_B

.. spec:: Collector
   :id: COLL_1
   :status: draft

.. test:: Checker
   :id: TEST_2
   :status: done
   :links: REQ_A.p1, SPEC_N

.. needimport:: imported.json
"""

TABLES = """\
Tables
======

.. container:: open-show-parts

   .. needtable::
      :filter: status == 'open'
      :columns: id;title;status
      :show_parts:
      :style: table

.. container:: open-no-show-parts

   .. needtable::
      :filter: status == 'open'
      :columns: id;title;status
      :style: table

.. container:: part-without-its-need

   .. needtable::
      :filter: content == 'closed part' or id_parent == 'REQ_A'
      :columns: id;title
      :show_parts:
      :style: table

.. container:: capped

   .. needtable::
      :filter: status == 'open'
      :columns: id;title
      :show_parts:
      :max_items: 3
      :style: table
"""


def project() -> list[dict[str, object]]:
    return [
        {
            "buildername": "html",
            "files": [
                (Path("conf.py"), CONF),
                (Path("index.rst"), INDEX),
                (Path("tables.rst"), TABLES),
                (Path("imported.json"), json.dumps(IMPORTED)),
                (Path("external.json"), json.dumps(EXTERNAL)),
            ],
        }
    ]


def _rows(app: Sphinx, name: str) -> list[tuple[str, str, list[str]]]:
    """The rows of the table in the container of class *name*: each its need id, its
    row class (``need`` or ``need_part``) and the text of its cells."""
    page = Path(app.outdir, "tables.html").read_text(encoding="utf-8")
    (container,) = html_parser.fromstring(page).xpath(
        f'//div[contains(concat(" ", normalize-space(@class), " "), " {name} ")]'
    )
    return [
        (
            row.get("data-need-id"),
            "need_part" if "need_part" in row.get("class").split() else "need",
            [" ".join(cell.text_content().split()) for cell in row.xpath("./td")],
        )
        for row in container.xpath(".//tr[@data-need-id]")
    ]


def _ids(app: Sphinx, name: str) -> list[str]:
    return [need_id for need_id, _, _ in _rows(app, name)]


@pytest.mark.parametrize("test_app", project(), indirect=True)
def test_show_parts_lists_each_part_once_under_its_need(test_app: Sphinx) -> None:
    """15 rows were 10: each of the five parts the filter matched was listed twice."""
    test_app.build()
    assert _ids(test_app, "open-show-parts") == [
        "EXT_1",
        "EXT_1.e1",
        "IMP_1",
        "IMP_1.ip",
        "REQ_A",
        "REQ_A.p1",
        "REQ_A.p2",
        "SPEC_N",
        "SPEC_N.n1",
        "TEST_1",
    ]


@pytest.mark.parametrize("test_app", project(), indirect=True)
def test_a_part_under_its_need_shows_its_text_and_parent(test_app: Sphinx) -> None:
    """Each part row is the ``:show_parts:`` row: its id with the part prefix, its text."""
    test_app.build()
    rows = _rows(test_app, "open-show-parts")
    assert rows[4:7] == [
        ("REQ_A", "need", ["REQ_A", "Alpha", "open"]),
        ("REQ_A.p1", "need_part", ["→ REQ_A.p1", "→ brake fast", "open"]),
        ("REQ_A.p2", "need_part", ["→ REQ_A.p2", "→ steer well", "open"]),
    ]


@pytest.mark.parametrize("test_app", project(), indirect=True)
def test_a_matched_part_whose_need_is_not_a_row_keeps_its_row(
    test_app: Sphinx,
) -> None:
    """``REQ_B`` does not pass, its part ``b1`` does: ``b1`` is listed, once. ``REQ_A``'s
    parts, matched too, are listed under ``REQ_A`` alone."""
    test_app.build()
    assert _ids(test_app, "part-without-its-need") == [
        "REQ_A",
        "REQ_A.p1",
        "REQ_A.p2",
        "REQ_B.b1",
    ]


@pytest.mark.parametrize("test_app", project(), indirect=True)
def test_the_cap_counts_the_entries_as_shown(test_app: Sphinx) -> None:
    """``:max_items: 3`` keeps three needs, each with its parts, of five entries."""
    test_app.build()
    assert build_warnings(test_app) == [
        "<srcdir>/tables.rst:29: WARNING: needtable: showing the first 3 of 5 needs,"
        " due to the max_items limit. [needs.max_items]"
    ]
    assert _ids(test_app, "capped") == [
        "EXT_1",
        "EXT_1.e1",
        "IMP_1",
        "IMP_1.ip",
        "REQ_A",
        "REQ_A.p1",
        "REQ_A.p2",
    ]
    page = Path(test_app.outdir, "tables.html").read_text(encoding="utf-8")
    assert "Showing the first 3 of 5 needs" in " ".join(page.split())


@pytest.mark.parametrize("test_app", project(), indirect=True)
def test_a_table_without_show_parts_does_not_change(test_app: Sphinx) -> None:
    """The control: without ``:show_parts:`` a part the filter matched is a row of its
    own, as before, with its address and its text."""
    test_app.build()
    assert _rows(test_app, "open-no-show-parts") == [
        ("EXT_1", "need", ["EXT_1", "External", "open"]),
        ("EXT_1.e1", "need_part", ["→ EXT_1.e1", "→ external part", "open"]),
        ("IMP_1", "need", ["IMP_1", "Imported", "open"]),
        ("IMP_1.ip", "need_part", ["→ IMP_1.ip", "→ imported part", "open"]),
        ("REQ_A", "need", ["REQ_A", "Alpha", "open"]),
        ("REQ_A.p1", "need_part", ["→ REQ_A.p1", "→ brake fast", "open"]),
        ("REQ_A.p2", "need_part", ["→ REQ_A.p2", "→ steer well", "open"]),
        ("SPEC_N", "need", ["SPEC_N", "Nested", "open"]),
        ("SPEC_N.n1", "need_part", ["→ SPEC_N.n1", "→ nested part", "open"]),
        ("TEST_1", "need", ["TEST_1", "Test one", "open"]),
    ]
