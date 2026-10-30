"""A hidden need is located exactly as a visible need in the same place is (#2398).

``sections``, ``signature`` and ``parent_needs`` come from the need's place in the
doctree, and ``:hide:`` does not move it there: one project is built twice, once with
``:hide:`` on every need marked ``%HIDE%`` and once without, and each need's location
must be the same in both builds. The positions are the ones a hidden need can be in:
first in a container (``only``, ``note``, a parent need's content, a function's body),
after a title, after a paragraph, after a hidden or a visible need, a row of hidden
needs, and after a sibling inside a parent need or a function.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from docutils import nodes
from sphinx.application import Sphinx
from sphinx.testing.util import SphinxTestApp

from sphinx_needs.data import SphinxNeedsData
from sphinx_needs.directives.need import _location_before
from sphinx_needs.nodes import Need
from sphinx_needs_testkit import assert_no_warnings

_PROJECT = """\
Top
===

First in only
-------------

.. only:: html

   .. req:: First in an only
      :id: ONLY_FIRST
      %HIDE%

First in note
-------------

.. note::

   .. req:: First in a note
      :id: NOTE_FIRST
      %HIDE%

First in parent
---------------

.. req:: Parent A
   :id: PARENT_A

   .. req:: First in a parent need
      :id: PARENT_FIRST
      %HIDE%

First in function
-----------------

.. py:function:: first_f(x)

   .. req:: First in a function
      :id: FUNC_FIRST
      %HIDE%

After title
-----------

.. req:: After a title
   :id: AFTER_TITLE
   %HIDE%

After paragraph
---------------

A paragraph.

.. req:: After a paragraph
   :id: AFTER_PARA
   %HIDE%

After hidden
------------

.. req:: Always hidden
   :id: PRE_HIDDEN
   :hide:

.. req:: After a hidden need
   :id: AFTER_HIDDEN
   %HIDE%

After visible
-------------

.. req:: Always visible
   :id: PRE_VISIBLE

.. req:: After a visible need
   :id: AFTER_VISIBLE
   %HIDE%

Row of five
-----------

.. container::

   .. req:: Row 1
      :id: ROW_1
      %HIDE%

   .. req:: Row 2
      :id: ROW_2
      %HIDE%

   .. req:: Row 3
      :id: ROW_3
      %HIDE%

   .. req:: Row 4
      :id: ROW_4
      %HIDE%

   .. req:: Row 5
      :id: ROW_5
      %HIDE%

Parent after sibling
--------------------

.. req:: Parent B
   :id: PARENT_B

   .. req:: A visible sibling
      :id: SIB_VISIBLE

   .. req:: In a parent need, after a visible sibling
      :id: PARENT_AFTER_VISIBLE
      %HIDE%

   .. req:: A hidden sibling
      :id: SIB_HIDDEN
      :hide:

   .. req:: In a parent need, after a hidden sibling
      :id: PARENT_AFTER_HIDDEN
      %HIDE%

Function after sibling
----------------------

.. py:function:: sib_f(x)

   .. req:: A hidden sibling in a function
      :id: FUNC_SIB
      :hide:

   .. req:: In a function, after a hidden sibling
      :id: FUNC_AFTER_HIDDEN
      %HIDE%
"""

_FIELDS = ("sections", "signature", "parent_needs")


def _write(srcdir: Path, *, hide: bool) -> None:
    """Write the project, ``%HIDE%`` read as ``:hide:`` or as nothing."""
    srcdir.mkdir(parents=True)
    srcdir.joinpath("conf.py").write_text('extensions = ["sphinx_needs"]\n')
    text = _PROJECT.replace("%HIDE%", ":hide:") if hide else _PROJECT
    srcdir.joinpath("index.rst").write_text(
        "".join(line for line in text.splitlines(True) if "%HIDE%" not in line)
    )


def _locations(
    make_app: Callable[..., SphinxTestApp], srcdir: Path, *, hide: bool
) -> dict[str, dict[str, Any]]:
    """Build the project; every need's location fields and its ``parent_needs_back``."""
    _write(srcdir, hide=hide)
    app = make_app("html", srcdir=srcdir, freshenv=True)
    try:
        app.build()
        assert_no_warnings(app)
        return {
            need_id: {
                **{field: need[field] for field in _FIELDS},
                "parent_needs_back": need["parent_needs_back"],
            }
            for need_id, need in SphinxNeedsData(app.env).get_needs_view().items()
        }
    finally:
        app.cleanup()


_BUILDS: dict[bool, dict[str, dict[str, Any]]] = {}
"""The two builds, made once per process (a session's worker) and shared by the tests."""


@pytest.fixture
def builds(
    make_app: Callable[..., SphinxTestApp], tmp_path: Path
) -> dict[bool, dict[str, dict[str, Any]]]:
    """The project built with and without ``:hide:``."""
    if not _BUILDS:
        _BUILDS.update(
            (hide, _locations(make_app, tmp_path / f"hide_{hide}", hide=hide))
            for hide in (False, True)
        )
    return _BUILDS


_HIDDEN = [
    "ONLY_FIRST",
    "NOTE_FIRST",
    "PARENT_FIRST",
    "FUNC_FIRST",
    "AFTER_TITLE",
    "AFTER_PARA",
    "AFTER_HIDDEN",
    "AFTER_VISIBLE",
    "ROW_1",
    "ROW_2",
    "ROW_3",
    "ROW_4",
    "ROW_5",
    "PARENT_AFTER_VISIBLE",
    "PARENT_AFTER_HIDDEN",
    "FUNC_AFTER_HIDDEN",
]


@pytest.mark.parametrize("need_id", _HIDDEN)
def test_a_hidden_need_is_located_as_a_visible_one(
    builds: dict[bool, dict[str, dict[str, Any]]], need_id: str
):
    """The need's ``sections``, ``signature`` and ``parent_needs`` with ``:hide:`` equal
    those without it."""
    visible, hidden = builds[False][need_id], builds[True][need_id]
    assert {field: hidden[field] for field in _FIELDS} == {
        field: visible[field] for field in _FIELDS
    }


@pytest.mark.parametrize(
    ("need_id", "location"),
    [
        ("PRE_HIDDEN", (("After hidden", "Top"), None, [])),
        ("SIB_HIDDEN", (("Parent after sibling", "Top"), None, ["PARENT_B"])),
        ("FUNC_SIB", (("Function after sibling", "Top"), "sib_f", [])),
    ],
)
def test_a_need_hidden_in_both_builds_is_where_it_is(
    builds: dict[bool, dict[str, dict[str, Any]]],
    need_id: str,
    location: tuple[tuple[str, ...], str | None, list[str]],
):
    """A need with ``:hide:`` in both builds, so not compared across them: its location
    is its place's (after a title; after a sibling in a parent need; first in a
    function's body)."""
    for build in builds.values():
        need = build[need_id]
        assert (tuple(need["sections"]), need["signature"], need["parent_needs"]) == (
            location
        )


def test_hiding_a_need_changes_no_back_link(
    builds: dict[bool, dict[str, dict[str, Any]]],
):
    """Every need's ``parent_needs_back`` is the same with and without ``:hide:``: a
    hidden need is the child of its real parent and of no sibling."""
    for build in builds.values():
        assert build["PARENT_A"]["parent_needs_back"] == ["PARENT_FIRST"]
        assert build["PARENT_B"]["parent_needs_back"] == [
            "PARENT_AFTER_HIDDEN",
            "PARENT_AFTER_VISIBLE",
            "SIB_HIDDEN",
            "SIB_VISIBLE",
        ]
    assert {
        need_id: need["parent_needs_back"] for need_id, need in builds[True].items()
    } == {need_id: need["parent_needs_back"] for need_id, need in builds[False].items()}


def test_the_visible_build_is_where_the_needs_are(
    builds: dict[bool, dict[str, dict[str, Any]]],
):
    """The reference the hidden build is compared with: each need's innermost section,
    its function, and its parent need, without ``:hide:``."""
    visible = builds[False]
    assert {
        need_id: (need["sections"], need["signature"], need["parent_needs"])
        for need_id, need in visible.items()
        if need_id not in {"PRE_HIDDEN", "SIB_HIDDEN", "FUNC_SIB"}
    } == {
        "ONLY_FIRST": (("First in only", "Top"), None, []),
        "NOTE_FIRST": (("First in note", "Top"), None, []),
        "PARENT_A": (("First in parent", "Top"), None, []),
        "PARENT_FIRST": (("First in parent", "Top"), None, ["PARENT_A"]),
        "FUNC_FIRST": (("First in function", "Top"), "first_f", []),
        "AFTER_TITLE": (("After title", "Top"), None, []),
        "AFTER_PARA": (("After paragraph", "Top"), None, []),
        "PRE_VISIBLE": (("After visible", "Top"), None, []),
        "AFTER_HIDDEN": (("After hidden", "Top"), None, []),
        "AFTER_VISIBLE": (("After visible", "Top"), None, []),
        **{f"ROW_{n}": (("Row of five", "Top"), None, []) for n in range(1, 6)},
        "PARENT_B": (("Parent after sibling", "Top"), None, []),
        "SIB_VISIBLE": (("Parent after sibling", "Top"), None, ["PARENT_B"]),
        "PARENT_AFTER_VISIBLE": (("Parent after sibling", "Top"), None, ["PARENT_B"]),
        "PARENT_AFTER_HIDDEN": (("Parent after sibling", "Top"), None, ["PARENT_B"]),
        "FUNC_AFTER_HIDDEN": (("Function after sibling", "Top"), "sib_f", []),
    }


def test_locating_a_hidden_need_leaves_the_doctree_unchanged(
    make_app: Callable[..., SphinxTestApp], tmp_path: Path
):
    """The walk for a hidden need starts at the position before its node without
    placing anything there: the doctree reads the same before and after it, for every
    hidden need of the project -- among them a first child, a need after a need, and a
    need in a parent need. It is called before sphinx-needs' own walk, which takes the
    hidden needs out.
    """
    unchanged: dict[str, bool] = {}

    def probe(app: Sphinx, doctree: nodes.document) -> None:
        for node in list(doctree.findall(Need)):
            if node.get("hidden"):
                before = doctree.pformat()
                _location_before(node)
                unchanged[node["refid"]] = doctree.pformat() == before

    _write(tmp_path / "src", hide=True)
    app = make_app("html", srcdir=tmp_path / "src", freshenv=True)
    try:
        app.connect("doctree-read", probe, priority=100)
        app.build()
        assert_no_warnings(app)
    finally:
        app.cleanup()
    assert {
        "ONLY_FIRST",
        "AFTER_VISIBLE",
        "PARENT_FIRST",
        "PARENT_AFTER_HIDDEN",
    } <= set(unchanged)
    assert [need_id for need_id, same in unchanged.items() if not same] == []
