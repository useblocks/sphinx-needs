"""Characterization tests for the ``.. list2need::`` directive.

:file:`test_list2need.py` covers the happy path over the ``doc_list2need`` fixture
project. This module is different in kind: it pins the directive's behaviour on the
inputs that fixture project does not contain -- ids, inline options, the delimiter,
continuation lines, level skips, build-aborting inputs, and the Markdown host.

These tests describe what the directive does **today**. Several of the pinned
behaviours are surprising, and a few are outright defects; they are recorded here as
they are, not as endorsements, so that a future change to the implementation shows up
as a deliberate edit to an assertion rather than as a silent change in what users'
documents produce. Assertions that pin such a behaviour carry a
``# NOTE: current behaviour; see PR discussion`` comment.

The projects are built inline (``files``) rather than as ``doc_test/`` directories, so
that every case's input sits next to the output it produces.
"""

from __future__ import annotations

import hashlib
import importlib.util
import re
from pathlib import Path
from typing import Any

import pytest
from sphinx.errors import SphinxError, SphinxWarning
from sphinx.testing.util import SphinxTestApp
from sphinx.util.console import strip_colors

from sphinx_needs.api import get_needs_view

CONF = """\
extensions = ["sphinx_needs"]
needs_types = [
    dict(directive="req", title="Requirement", prefix="R_", color="#BFD8D2", style="node"),
    dict(directive="spec", title="Specification", prefix="S_", color="#FEDCD2", style="node"),
    dict(directive="test", title="Test Case", prefix="T_", color="#DF744A", style="node"),
]
needs_id_regex = r"^[A-Za-z0-9_.\\-]+$"
"""
"""The configuration every case in this module builds against.

``needs_id_regex`` is permissive but **anchored at both ends**, so that an id the
directive derives from prose -- which contains spaces and brackets -- is rejected by
:func:`~sphinx_needs.api.need.add_need` and the effect is visible, rather than being
waved through by a regex that only constrains the first character.
"""


def project(body: str, conf: str = CONF, **extra: str) -> list[tuple[Path, str]]:
    """Build the inline project for a single case.

    :param body: The reStructuredText to place under the title of ``index.rst``.
    :param conf: The content of ``conf.py``.
    :param extra: Further documents, by file name.
    :return: The ``files`` payload for the :func:`test_app` fixture.
    """
    files = [
        (Path("conf.py"), conf),
        (Path("index.rst"), f"TEST DOCUMENT\n=============\n{body}"),
    ]
    files.extend((Path(name), text) for name, text in extra.items())
    return files


def params(body: str, conf: str = CONF, **extra: str) -> dict[str, object]:
    """Build the :func:`test_app` parameters for a single case."""
    return {
        "buildername": "html",
        "files": project(body, conf, **extra),
        "no_plantuml": True,
    }


def needs(app: SphinxTestApp) -> dict[str, dict[str, Any]]:
    """The built needs as plain dictionaries, keyed by id."""
    return {k: {**v} for k, v in get_needs_view(app).items()}


def warnings(app: SphinxTestApp) -> str:
    """Every warning the build emitted, as one string.

    ``app.warning_list`` is captured by the fixture before the test builds, so the
    stream itself has to be read back afterwards.
    """
    return strip_colors(app._warning.getvalue())


# ---------------------------------------------------------------------------
# ids
# ---------------------------------------------------------------------------

IDS = """
.. list2need::
   :types: req, spec

   * (ID-LEADING) A leading id in brackets
   * Some (parenthetical) title text
   * (REQ-1) The system (as defined) shall work
   * (AAA)(BBB) Two bracketed groups
   * ()Empty parentheses title
   * A title with no parentheses
   *NoSpaceAfterBullet
"""


@pytest.mark.parametrize("test_app", [params(IDS)], indirect=True)
def test_id_capture(test_app: SphinxTestApp):
    """Pin how ``(...)`` in an item's title becomes -- or fails to become -- the id.

    The id is found with ``ID_REGEX.search(title)``, so it is matched **anywhere** in
    the title rather than only as a prefix, its character class permits brackets and
    spaces, and its ``+`` is greedy. Every row below follows from those three facts.
    """
    app = test_app
    app.build()
    built = needs(app)

    # A leading id in brackets is used, and is removed from the title.
    assert built["ID-LEADING"]["title"] == "A leading id in brackets"

    # NOTE: current behaviour; see PR discussion.
    # The search is not anchored, so a mid-title parenthetical becomes the id and is
    # deleted from the title -- which is left with the double space it stood in.
    assert built["parenthetical"]["title"] == "Some  title text"

    # NOTE: current behaviour; see PR discussion.
    # ``[^"'=\n]+`` admits brackets and the ``+`` is greedy, so the match runs from the
    # first "(" to the last ")". The id that produces contains spaces and brackets, so
    # ``needs_id_regex`` rejects it and the need is never created.
    assert "REQ-1" not in built
    assert (
        "Given ID 'REQ-1) The system (as defined' does not match configured regex"
        in warnings(app)
    )

    # NOTE: current behaviour; see PR discussion.
    # Two adjacent bracketed groups are captured as one id for the same reason.
    assert "AAA" not in built
    assert "Given ID 'AAA)(BBB' does not match configured regex" in warnings(app)

    # NOTE: current behaviour; see PR discussion.
    # The inner group is optional, so a literal "()" matches with no id. It is stripped
    # from the title and the need falls through to an automatically generated id --
    # see :func:`test_empty_parentheses_select_a_second_auto_id_function`.
    assert built["R_2E24B"]["title"] == "Empty parentheses title"

    # No brackets at all: list2need hashes the title itself.
    assert built["R_93AAC"]["title"] == "A title with no parentheses"

    # The space after the bullet is optional: ``\\s*`` in LINE_REGEX is ``*``-quantified,
    # so the text may start immediately after the ``*``.
    assert built["R_DEF68"]["title"] == "NoSpaceAfterBullet"


AUTO_ID = """
.. list2need::
   :types: req, spec

   * The auto id is a hash of this title
"""


@pytest.mark.parametrize(
    ("test_app", "expected"),
    [
        (params(AUTO_ID), "R_53475"),
        (
            params(AUTO_ID, conf=CONF + "needs_id_length = 3\n"),
            "R_534",
        ),
    ],
    ids=["default-length", "length-3"],
    indirect=["test_app"],
)
def test_auto_id_is_a_hash_of_the_title_alone(test_app: SphinxTestApp, expected: str):
    """Pin the generated id formula: ``prefix + sha1(title).upper()[:needs_id_length]``.

    The input is the title *only* -- not the content, the document name, the need's
    position in the list, or the need type (of which only the ``prefix`` is used). The
    id is therefore stable across rebuilds and across reordering the list, and changes
    whenever the title does.
    """
    app = test_app
    app.build()
    title = "The auto id is a hash of this title"
    length = len(expected) - len("R_")
    assert expected == "R_" + hashlib.sha1(title.encode()).hexdigest().upper()[:length]
    assert needs(app)[expected]["title"] == title


EMPTY_PARENS = """
.. list2need::
   :types: req, spec

   * ()Alpha title
   * Beta title
"""


@pytest.mark.parametrize("test_app", [params(EMPTY_PARENS)], indirect=True)
def test_empty_parentheses_match_the_plain_hash_by_default(test_app: SphinxTestApp):
    """Under the default configuration the two auto-id paths produce the same id.

    Writing ``()`` suppresses the ``:id:`` line in the generated need, which sends the
    need down :func:`~sphinx_needs.api.need._make_hashed_id` instead of list2need's own
    ``make_hashed_id``. The two agree here, which is why the split is normally
    invisible -- see the companion test for the configuration that separates them.
    """
    app = test_app
    app.build()
    built = needs(app)
    assert built["R_D1EC6"]["title"] == "Alpha title"
    assert built["R_C1440"]["title"] == "Beta title"


@pytest.mark.parametrize(
    "test_app",
    [params(EMPTY_PARENS, conf=CONF + "needs_id_from_title = True\n")],
    indirect=True,
)
def test_empty_parentheses_select_a_second_auto_id_function(test_app: SphinxTestApp):
    """Pin that ``()`` selects a *different* id function, observable under config.

    ``needs_id_from_title`` is honoured by :func:`~sphinx_needs.api.need._make_hashed_id`
    and ignored by list2need's own ``make_hashed_id``, so the same list yields two id
    schemes at once, chosen by two characters of punctuation in the title.
    """
    app = test_app
    app.build()
    built = needs(app)
    # NOTE: current behaviour; see PR discussion.
    assert built["R_ALPHA"]["title"] == "Alpha title"
    assert built["R_C1440"]["title"] == "Beta title"


COLLIDING = """
.. list2need::
   :types: req, spec

   * Same title in one list
   * Same title in one list
   * Duplicate title in two documents

.. list2need::
   :types: req, spec

   * Shared title at two levels
     * Shared title at two levels

.. toctree::

   other
"""

OTHER = """\
OTHER
=====

.. list2need::
   :types: req, spec

   * Duplicate title in two documents
"""


@pytest.mark.parametrize(
    "test_app", [params(COLLIDING, **{"other.rst": OTHER})], indirect=True
)
def test_equal_titles_collide_unless_the_type_prefix_differs(test_app: SphinxTestApp):
    """Pin which equal titles produce the same generated id, and which do not.

    Neither the document nor the item's position feeds the hash, so equal titles of the
    same type collide wherever they are written. The type contributes its prefix,
    though, so the same title at two levels of one list is safe -- which is the only
    reason nested lists of repeated titles work at all.
    """
    app = test_app
    app.build()
    built = needs(app)

    # NOTE: current behaviour; see PR discussion.
    # Twice in the same list: the second need is dropped.
    assert "A need with ID 'R_C6376' already exists" in warnings(app)
    assert built["R_C6376"]["title"] == "Same title in one list"

    # NOTE: current behaviour; see PR discussion.
    # Once in each of two documents: likewise, and the survivor is the first read.
    assert "A need with ID 'R_1776A' already exists" in warnings(app)
    assert built["R_1776A"]["docname"] == "index"

    # The same title at two levels is safe, because the prefixes differ. Both needs are
    # created, from one hash and two prefixes, and nothing is reported.
    assert built["R_E8D5C"]["type"] == "req"
    assert built["S_E8D5C"]["type"] == "spec"
    assert built["S_E8D5C"]["parent_need"] == "R_E8D5C"
    assert "E8D5C" not in warnings(app)


# ---------------------------------------------------------------------------
# inline ``((options))``
# ---------------------------------------------------------------------------

OPTIONS = """
.. list2need::
   :types: req, spec

   * (OPT-DOUBLE) Double quoted ((status="open"))
   * (OPT-SINGLE) Single quoted ((status='open'))
   * (OPT-MISMATCH) Mismatched quotes ((status='open"))
   * (OPT-GREEDY) Title ((status="open")) middle ((tags="z"))
   * (OPT-SPLIT) Delimiter inside a value ((tags="a.b"))
"""


@pytest.mark.parametrize("test_app", [params(OPTIONS)], indirect=True)
def test_inline_options(test_app: SphinxTestApp):
    """Pin how the ``((name="value"))`` option area is found and parsed.

    Two properties drive every row: the option area is matched with the greedy
    ``\\(\\((.*)\\)\\)``, and it is searched on ``title + content`` -- that is, *after*
    the delimiter has already split the line.
    """
    app = test_app
    app.build()
    built = needs(app)

    # Both quote characters the documentation advertises work.
    assert built["OPT-DOUBLE"]["status"] == "open"
    assert built["OPT-SINGLE"]["status"] == "open"

    # NOTE: current behaviour; see PR discussion.
    # The opening and closing quote are not required to match.
    assert built["OPT-MISMATCH"]["status"] == "open"

    # NOTE: current behaviour; see PR discussion.
    # The greedy area spans from the first "((" to the last "))", so the prose between
    # two option regions is swallowed: "middle" is deleted from the title and the
    # second region's name is read as the option "((tags".
    assert built["OPT-GREEDY"]["title"] == "Title"
    assert built["OPT-GREEDY"]["status"] == "open"
    assert "Unknown option '((tags'" in warnings(app)

    # NOTE: current behaviour; see PR discussion.
    # The options are extracted after the delimiter split, so a "." inside a value has
    # already cut the line in two: the option area is removed from neither half, and
    # the value itself lost the delimiter.
    assert built["OPT-SPLIT"]["title"] == 'Delimiter inside a value ((tags="a'
    assert built["OPT-SPLIT"]["content"] == 'b"))'
    assert built["OPT-SPLIT"]["tags"] == ["ab"]


UNQUOTED_OPTION = """
.. list2need::
   :types: req, spec

   * (OPT-UNQUOTED) Unquoted ((status=open))
"""


@pytest.mark.parametrize("test_app", [params(UNQUOTED_OPTION)], indirect=True)
def test_an_unquoted_option_value_is_dropped_without_a_diagnostic(
    test_app: SphinxTestApp,
):
    """Pin that an unquoted option value is discarded, and that nothing is reported.

    ``OPTIONS_REGEX`` requires the value to be quoted, so ``status=open`` matches no
    pair at all and the option simply never exists.

    The project holds this one item and nothing else, so asserting that the whole
    warning stream is empty is what pins the *silence*: any diagnostic sphinx-needs
    might grow for this input would fail here, whether or not it named the need.
    """
    app = test_app
    app.build()
    # NOTE: current behaviour; see PR discussion.
    assert needs(app)["OPT-UNQUOTED"]["status"] is None
    assert warnings(app) == ""


# ---------------------------------------------------------------------------
# ``:delimiter:``
# ---------------------------------------------------------------------------

DELIMITERS = """
.. list2need::
   :types: req, spec

   * (DEL-DEFAULT) The system shall support v1.2 of the protocol

.. list2need::
   :types: req, spec
   :delimiter: ;

   * (DEL-CUSTOM) The system shall support v1.2 of the protocol; and this is content

.. list2need::
   :types: req, spec
   :delimiter: ::

   * (DEL-MULTI) A title:: and this is content

.. list2need::
   :types: req, spec
   :delimiter:

   * (DEL-EMPTY) A title. and this is content
"""


@pytest.mark.parametrize("test_app", [params(DELIMITERS)], indirect=True)
def test_delimiter(test_app: SphinxTestApp):
    """Pin the title/content split, which is a plain :meth:`str.split`.

    Only the first occurrence separates the two, the delimiter itself is dropped at the
    joint, and later occurrences survive in the content.
    """
    app = test_app
    app.build()
    built = needs(app)

    # NOTE: current behaviour; see PR discussion.
    # The default delimiter is ".", and there is no way to escape one, so any full stop
    # in a title truncates it -- version numbers, "e.g.", file names.
    assert built["DEL-DEFAULT"]["title"] == "The system shall support v1"
    assert built["DEL-DEFAULT"]["content"] == "2 of the protocol"

    # A custom delimiter leaves full stops alone.
    assert (
        built["DEL-CUSTOM"]["title"] == "The system shall support v1.2 of the protocol"
    )
    assert built["DEL-CUSTOM"]["content"] == "and this is content"

    # It is a string split, not a character split, so multi-character values work.
    assert built["DEL-MULTI"]["title"] == "A title"
    assert built["DEL-MULTI"]["content"] == "and this is content"

    # NOTE: current behaviour; see PR discussion.
    # An empty ``:delimiter:`` is falsy, so it silently falls back to "." rather than
    # disabling the split.
    assert built["DEL-EMPTY"]["title"] == "A title"
    assert built["DEL-EMPTY"]["content"] == "and this is content"


# ---------------------------------------------------------------------------
# list structure: continuation lines and nesting
# ---------------------------------------------------------------------------

CONTINUATIONS = """
.. list2need::
   :types: req, spec

   * (CON-INDENT) A title
     alpha beta gamma
   * (CON-COLUMN0) A title
   alpha beta gamma
   * (CON-BLANK) A title. first paragraph

     second paragraph
   * (CON-COLON) A title
     :status: open
"""


@pytest.mark.parametrize("test_app", [params(CONTINUATIONS)], indirect=True)
def test_continuation_lines(test_app: SphinxTestApp):
    """Pin how a line that does not start with ``*`` is appended to the item above it.

    The continuation branch of ``LINE_REGEX`` is ``[\\S\\*]*(?P<more_text>.*)``, whose
    leading class is simply ``\\S``: at position 0 it eats the first run of
    non-whitespace before ``more_text`` starts.
    """
    app = test_app
    app.build()
    built = needs(app)

    # An indented continuation line loses nothing: the leading space stops ``\\S*``.
    assert built["CON-INDENT"]["content"] == "alpha beta gamma"

    # NOTE: current behaviour; see PR discussion.
    # A continuation line at column 0 of the list silently loses its first
    # whitespace-delimited token, though the documented rule is that the whole line is
    # added to the item above.
    assert built["CON-COLUMN0"]["content"] == "beta gamma"

    # A blank line is a continuation line too, which is how paragraph breaks survive.
    assert built["CON-BLANK"]["content"] == "first paragraph\n\nsecond paragraph"

    # NOTE: current behaviour; see PR discussion.
    # A continuation line starting with ":" is not an option. It is indented by a
    # further three spaces before being appended, which keeps it out of the generated
    # need's option block and leaves it in the body as a field list.
    assert built["CON-COLON"]["content"] == "   :status: open"
    assert built["CON-COLON"]["status"] is None


NESTED = """
.. list2need::
   :types: req, spec
   :presentation: nested
   :links-down: links

   * (NST-PARENT) Parent
     * (NST-CHILD) Child
"""

STANDALONE = """
.. list2need::
   :types: req, spec
   :presentation: standalone
   :links-down: links

   * (STA-PARENT) Parent
     * (STA-CHILD) Child
"""


@pytest.mark.parametrize("test_app", [params(NESTED)], indirect=True)
def test_presentation_nested_puts_the_child_inside_the_parent(test_app: SphinxTestApp):
    """Pin that ``nested`` makes the child need part of the parent's content.

    The generated text for each item is indented by three spaces per level, so the
    child's directive is parsed inside the parent's content block. ``links-down``
    is set as well, and is therefore redundant with the visible nesting.
    """
    app = test_app
    app.build()
    built = needs(app)
    assert built["NST-CHILD"]["parent_need"] == "NST-PARENT"
    assert built["NST-PARENT"]["links"] == ["NST-CHILD"]
    # The child is nested by being re-parsed inside the parent's content.
    assert built["NST-PARENT"]["content"] == ".. spec::  Child\n   :id: NST-CHILD"


@pytest.mark.parametrize("test_app", [params(STANDALONE)], indirect=True)
def test_presentation_standalone_leaves_the_needs_unnested(test_app: SphinxTestApp):
    """Pin that ``standalone`` emits every need at column 0, related only by links."""
    app = test_app
    app.build()
    built = needs(app)
    assert built["STA-CHILD"]["parent_need"] is None
    assert built["STA-PARENT"]["links"] == ["STA-CHILD"]
    assert built["STA-PARENT"]["content"] == ""


LEVEL_SKIP = """
.. list2need::
   :types: req, spec, test
   :presentation: standalone
   :links-down: links, links

   * (SKIP-A) Parent A
     * (SKIP-B) Child B of A
   * (SKIP-D) Parent D
       * (SKIP-G) Level two under D, skipping level one
"""


@pytest.mark.parametrize("test_app", [params(LEVEL_SKIP)], indirect=True)
def test_a_skipped_level_redirects_links_down_into_another_subtree(
    test_app: SphinxTestApp,
):
    """Pin what ``links-down`` produces when an item skips an indentation level.

    Nothing validates that the level sequence increases by at most one, and
    ``get_down_needs`` walks forward until it meets an item of *exactly* the current
    level. A skipped level therefore lets the walk run past the de-indent that ends the
    subtree, so the link sets below are simultaneously incomplete and wrong.
    """
    app = test_app
    app.build()
    built = needs(app)

    assert built["SKIP-A"]["links"] == ["SKIP-B"]

    # NOTE: current behaviour; see PR discussion.
    # SKIP-B is under SKIP-A and SKIP-G is under SKIP-D, yet B links down to G ...
    assert built["SKIP-B"]["links"] == ["SKIP-G"]
    # ... and SKIP-D, whose child SKIP-G actually is, links to nothing.
    assert built["SKIP-D"]["links"] == []
    assert built["SKIP-G"]["links"] == []


# ---------------------------------------------------------------------------
# inputs that abort the build
# ---------------------------------------------------------------------------


def abort_params(directive: str) -> dict[str, object]:
    """Build the :func:`test_app` parameters for a build-aborting list2need."""
    return params(f"\n.. list2need::\n   {directive}\n")


ABORTS = [
    pytest.param(
        abort_params(":types: req, spec\n\n   - Dash bullet item"),
        IndexError,
        "list index out of range",
        id="dash-bullet",
    ),
    pytest.param(
        abort_params(":types: req, spec\n\n   1. Numbered bullet item"),
        IndexError,
        "list index out of range",
        id="numbered-bullet",
    ),
    pytest.param(
        abort_params(":types: req, spec\n\n   Not a bullet at all"),
        IndexError,
        "list index out of range",
        id="non-bullet-first-line",
    ),
    pytest.param(
        abort_params(":types: req, spec\n\n   * Parent\n   \t* Tab indented child"),
        IndentationError,
        "Indentation for list must be always a multiply of 2.",
        id="tab-indent",
    ),
    pytest.param(
        abort_params(
            ":types: req, spec\n\n   * Parent\n    * Three space indented child"
        ),
        IndentationError,
        "Indentation for list must be always a multiply of 2.",
        id="odd-indent",
    ),
    pytest.param(
        abort_params(":types: req, spec\n\n   * First\n   *\n   * Third"),
        AttributeError,
        "'NoneType' object has no attribute 'lstrip'",
        id="bare-bullet",
    ),
    pytest.param(
        abort_params("\n   * (X) A title"),
        SphinxWarning,
        "types must be set.",
        id="missing-types",
    ),
    pytest.param(
        abort_params(":types: nosuchtype\n\n   * (X) A title"),
        SphinxError,
        "Unknown type configured: nosuchtype",
        id="unknown-type",
    ),
    pytest.param(
        abort_params(":types: req\n\n   * (X) Parent\n     * (Y) Child"),
        SphinxWarning,
        "No need type defined for indentation level 1.",
        id="level-deeper-than-types",
    ),
    pytest.param(
        abort_params(
            ":types: req, spec, test\n   :links-down: links"
            "\n\n   * (X) A\n     * (Y) B\n       * (Z) C"
        ),
        SphinxWarning,
        "Not enough links-down defined for indentation level 2.",
        id="links-down-shortfall",
    ),
    pytest.param(
        abort_params(":types: req, spec\n   :presentation: bogus\n\n   * (X) A title"),
        SphinxWarning,
        "'presentation' must be 'nested' or 'standalone'",
        id="bad-presentation",
    ),
]


@pytest.mark.parametrize(
    ("test_app", "exception", "message"), ABORTS, indirect=["test_app"]
)
def test_malformed_input_aborts_the_build(
    test_app: SphinxTestApp, exception: type[Exception], message: str
):
    """Pin that these eleven inputs abort the whole build rather than warning.

    Each raises out of ``List2NeedDirective.run`` -- six of them a bare Python
    exception -- so Sphinx stops with a traceback and no location, and the rest of the
    project is never built. They are pinned by exception type and message because that
    is all a caller can currently observe.
    """
    with pytest.raises(exception, match=re.escape(message)):
        test_app.build()


# ---------------------------------------------------------------------------
# host: the directive works in reStructuredText only
# ---------------------------------------------------------------------------

MYST_CONF = CONF.replace('["sphinx_needs"]', '["sphinx_needs", "myst_parser"]')

FENCE = "```"

MYST_INDEX = f"""\
# Test document

{FENCE}{{list2need}}
:types: req, spec

* (MD-A) A need on level one
  * (MD-B) A sub need
{FENCE}

{FENCE}{{req}} A control need
:id: MD-CONTROL
{FENCE}
"""

MYST_EVAL_RST_INDEX = f"""\
# Test document

{FENCE}{{eval-rst}}
.. list2need::
   :types: req, spec

   * (MD-A) A need on level one
     * (MD-B) A sub need
{FENCE}
"""


def myst_params(index: str) -> dict[str, object]:
    """Build the :func:`test_app` parameters for a Markdown-hosted case."""
    return {
        "buildername": "html",
        "files": [(Path("conf.py"), MYST_CONF), (Path("index.md"), index)],
        "no_plantuml": True,
    }


requires_myst = pytest.mark.skipif(
    importlib.util.find_spec("myst_parser") is None,
    reason="myst-parser is not installed",
)
"""Skip a Markdown-hosted case when myst-parser is absent.

The projects below name ``myst_parser`` in their ``extensions``, so the application
cannot even be created without it. The check therefore has to be a mark, which pytest
evaluates before the ``test_app`` fixture builds anything.
"""


@requires_myst
@pytest.mark.parametrize("test_app", [myst_params(MYST_INDEX)], indirect=True)
def test_the_directive_does_not_run_in_a_markdown_document(test_app: SphinxTestApp):
    """Pin that a ``{list2need}`` fence in a MyST document creates no needs.

    The directive's one host-specific call is ``state_machine.insert_input``, which
    myst-parser's mock state machine does not implement. The bespoke line grammar never
    runs, so the error names a myst-parser internal rather than anything the author
    wrote, and the list produces nothing. A need directive in the same document is
    unaffected, which locates the fault precisely.
    """
    app = test_app
    app.build()
    built = needs(app)

    # NOTE: current behaviour; see PR discussion.
    assert "MD-A" not in built
    assert "MD-B" not in built
    assert (
        "Directive 'list2need' cannot be mocked: MockingError: MockStateMachine has "
        "not yet implemented attribute 'insert_input'" in warnings(app)
    )
    assert built["MD-CONTROL"]["title"] == "A control need"


@requires_myst
@pytest.mark.parametrize("test_app", [myst_params(MYST_EVAL_RST_INDEX)], indirect=True)
def test_a_markdown_document_can_reach_the_directive_through_eval_rst(
    test_app: SphinxTestApp,
):
    """Pin the workaround available to MyST users today.

    Inside an ``{eval-rst}`` fence the block is handed to a real reStructuredText
    parse, so ``insert_input`` exists and the directive behaves as it does in an
    ``.rst`` document.
    """
    app = test_app
    app.build()
    built = needs(app)
    assert built["MD-A"]["title"] == "A need on level one"
    assert built["MD-B"]["parent_need"] == "MD-A"
    assert built["MD-A"]["doctype"] == ".md"


# ---------------------------------------------------------------------------
# line numbers
# ---------------------------------------------------------------------------

LINENOS = """
.. req:: Before the list
   :id: LN-BEFORE

.. list2need::
   :types: req, spec

   * (LN-A) First item
   * (LN-B) Second item. With content

.. req:: After the list
   :id: LN-AFTER
"""


@pytest.mark.parametrize("test_app", [params(LINENOS)], indirect=True)
def test_a_list2need_shifts_the_line_numbers_after_it(test_app: SphinxTestApp):
    """Pin the recorded ``lineno`` of the needs around a list2need directive.

    The generated needs are pushed back into the parser with ``insert_input``, which
    advances the state machine's flat line counter by the length of the generated text.
    Every ``lineno`` from the directive onwards is therefore offset, including that of
    ordinary need directives written after it, and the offset compounds with each
    list2need in a document. This is sphinx-needs issue #1349.

    The values below are wrong -- they are the real line number plus the drift -- and
    are pinned so that a change to the mechanism is visible here rather than only in
    users' ``needs.json``.
    """
    app = test_app
    app.build()
    built = needs(app)

    # Before the directive, the line number is correct.
    assert built["LN-BEFORE"]["lineno"] == 4

    # NOTE: current behaviour; see PR discussion (#1349).
    # LN-A is written on line 10 and LN-B on line 11.
    assert built["LN-A"]["lineno"] == 14
    assert built["LN-B"]["lineno"] == 20

    # NOTE: current behaviour; see PR discussion (#1349).
    # LN-AFTER is an ordinary need directive, written on line 13.
    assert built["LN-AFTER"]["lineno"] == 27
