"""Regression tests for the ``lineno`` a need records for its own directive.

A directive's ``self.lineno`` counts the lines of what the *parser* was handed, which
stops being the lines of the file as soon as anything has put text into it. Three
ordinary things do: Sphinx prepends ``rst_prolog`` to every document it parses, and
both docutils' ``.. include::`` and sphinx-needs' own ``.. list2need::`` splice text
in mid-parse with ``StateMachine.insert_input``. Each one advances the counter by the
length of the text it added, the shifts compound, and a need directive after them used
to record its real line *plus* all of that drift -- routinely past the end of the
file. That is issue #1349.

``NeedDirective`` now takes the line from ``self.get_source_info()``, the
``SphinxDirective`` accessor that maps that counter back onto a real
``(source, line)`` pair. It is the same accessor the warning path (``get_location()``)
is built on, so a need's recorded ``lineno`` and the line sphinx-needs' own warnings
print for that need are now the same number.

The projects are built inline (``files``) so that each case's input sits next to the
line numbers it produces.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

import pytest
from sphinx.testing.util import SphinxTestApp

from sphinx_needs.api import get_needs_view

PROLOG = """\
.. |project| replace:: The Project
.. |release| replace:: 1.2.3
"""
"""A two-line ``rst_prolog``.

Sphinx prepends it, plus a blank line, to every document it parses, which is what
shifts the line counter for the whole of :data:`INDEX`.
"""

CONF = f"""\
extensions = ["sphinx_needs"]
needs_types = [
    dict(directive="req", title="Requirement", prefix="R_", color="#BFD8D2", style="node"),
    dict(directive="spec", title="Specification", prefix="S_", color="#FEDCD2", style="node"),
]
needs_id_regex = r"^[A-Za-z0-9_.\\-]+$"
rst_prolog = {PROLOG!r}
# the fragment is spliced into index.rst by ``.. include::``; excluding it keeps
# Sphinx from also reading it as a document of its own and duplicating its need.
exclude_patterns = ["fragment.rst"]
"""

INDEX = """\
TEST DOCUMENT
=============

.. req:: Before anything else
   :id: LN-FIRST

.. include:: fragment.rst

.. req:: After the include
   :id: LN-AFTER-INCLUDE

.. list2need::
   :types: req, spec

   * (LN-GENERATED-A) First item
   * (LN-GENERATED-B) Second item

.. req:: After the list
   :id: LN-AFTER-LIST2NEED
"""
"""One document carrying all three sources of drift, in the order they compound.

``LN-FIRST`` is on line 4, ``LN-AFTER-INCLUDE`` on line 9 and ``LN-AFTER-LIST2NEED``
on line 18; each of the three is preceded by one more insertion than the last.
"""

FRAGMENT = """\
A section inside the fragment
-----------------------------

.. spec:: Inside the include
   :id: LN-INSIDE-INCLUDE

Prose that makes the fragment several lines longer than the one line the
``.. include::`` directive occupies in the including document.
"""
""":data:`INDEX` includes this. ``LN-INSIDE-INCLUDE`` is on line 4 **of this file**."""


def params(conf: str = CONF, index: str = INDEX, **extra: str) -> dict[str, object]:
    """Build the :func:`test_app` parameters for a single case."""
    files = [(Path("conf.py"), conf), (Path("index.rst"), index)]
    files.extend((Path(name), text) for name, text in extra.items())
    return {"buildername": "html", "files": files, "no_plantuml": True}


def needs(app: SphinxTestApp) -> dict[str, dict[str, Any]]:
    """The built needs as plain dictionaries, keyed by id."""
    return {k: {**v} for k, v in get_needs_view(app).items()}


@pytest.mark.parametrize(
    "test_app",
    [params(**{"fragment.rst": FRAGMENT})],
    indirect=True,
)
def test_inserted_text_no_longer_shifts_the_recorded_lineno(test_app: SphinxTestApp):
    """Every ordinary need directive records the line it is written on (#1349).

    The three needs asserted first sit after one, two and three such insertions
    respectively, so before this fix each was wrong by a larger amount than the one
    before it: lines 4, 9 and 18 were recorded as 7, 24 and 47 -- and this document is
    nineteen lines long.
    """
    app = test_app
    app.build()
    built = needs(app)

    # ``rst_prolog`` alone already shifts this one; it is the original report in #1349.
    assert built["LN-FIRST"]["lineno"] == 4

    # ... and the ``.. include::`` above it adds the length of the included file.
    assert built["LN-AFTER-INCLUDE"]["lineno"] == 9

    # ... and the ``.. list2need::`` above *that* adds the length of the text it
    # generated, which is what put this need's recorded line past the end of the file.
    assert built["LN-AFTER-LIST2NEED"]["lineno"] == 18

    # A need written inside the included file gets its line *within that file*, which
    # is the location sphinx-needs' warnings already report for it. ``docname``
    # deliberately still names the including document, so for this need alone the pair
    # spans two files -- as it must until needs can record a source path of their own.
    assert built["LN-INSIDE-INCLUDE"]["lineno"] == 4
    assert built["LN-INSIDE-INCLUDE"]["docname"] == "index"

    # NOTE: current behaviour. The needs list2need *generates* are re-parsed from a
    # block whose source is the document but whose offsets restart at 1, so they record
    # their position inside that generated block rather than the line of the list item
    # that produced them. That is where their warnings already point, and it is no
    # worse than before; it is fixed by giving the needs their line at construction
    # time instead of round-tripping them through the parser.
    assert built["LN-GENERATED-A"]["lineno"] == 1
    assert built["LN-GENERATED-B"]["lineno"] == 7


MYST_CONF = """\
extensions = ["sphinx_needs", "myst_parser"]
needs_types = [
    dict(directive="req", title="Requirement", prefix="R_", color="#BFD8D2", style="node"),
]
needs_id_regex = r"^[A-Za-z0-9_.\\-]+$"
"""

FENCE = "```"

MYST_INDEX = f"""\
# Test document

Some prose.

{FENCE}{{req}} A need in a Markdown document
:id: LN-MD
{FENCE}
"""

requires_myst = pytest.mark.skipif(
    importlib.util.find_spec("myst_parser") is None,
    reason="myst-parser is not installed",
)


@requires_myst
@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "files": [(Path("conf.py"), MYST_CONF), (Path("index.md"), MYST_INDEX)],
            "no_plantuml": True,
        }
    ],
    indirect=True,
)
def test_a_markdown_need_keeps_the_lineno_it_always_had(test_app: SphinxTestApp):
    """Pin that the fix is a no-op for Markdown hosts.

    myst-parser hands directives a ``MockStateMachine`` whose ``get_source_and_line``
    returns the line it was given, so ``get_source_info()`` resolves to exactly the
    flat counter it replaced. Markdown needs are unaffected by this change -- neither
    helped nor harmed -- and this test is here to keep it that way.
    """
    app = test_app
    app.build()
    built = needs(app)
    assert built["LN-MD"]["lineno"] == 5
