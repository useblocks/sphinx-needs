"""Unit tests for the gate a ``choose`` reads its body's top-level lines through.

No Sphinx application: the gate is a pure function of the body's lines.
It must accept every spelling of a branch and a comment that the parser accepts,
and refuse, at its index, every other top-level line, so that nothing but branches
and comments is ever parsed in a ``choose`` body.
"""

from __future__ import annotations

import pytest

from sphinx_needs.directives.needchoose import _gate, _Stray

# reStructuredText, as docutils gives a directive its content: dedented, tabs expanded

_RST_ACCEPTED: dict[str, list[str]] = {
    "branches and blank lines": [
        ".. when:: var.arch == 'arm'",
        "",
        "   ARM content.",
        "",
        ".. otherwise::",
        "",
        "   Other content.",
    ],
    "an empty body": [],
    "comments between branches": [
        ".. a comment",
        ".. when:: var.debug",
        "",
        "   Content.",
        "",
        ".. another comment",
    ],
    "a comment with an indented continuation": [
        ".. a comment",
        "   that goes on",
        "",
        "   and on",
        ".. otherwise::",
    ],
    "a condition continued on the next line": [
        ".. when:: var.arch ==",
        "   'arm'",
        "",
        "   Content.",
    ],
    "two spaces after the dots": ["..  when:: var.debug", "   Content."],
    "names in another case": [
        ".. When:: var.debug",
        "   A.",
        ".. OTHERWISE::",
        "   B.",
    ],
    "a space before the double colon": [".. when :: var.debug", "   Content."],
    "an empty comment followed by its indented text": [
        "..",
        "   the text of the comment",
        ".. otherwise::",
    ],
    "an empty comment then a blank line then a branch": [
        "..",
        "",
        ".. when:: var.debug",
        "   Content.",
    ],
    "a comment that starts with the word when": [
        ".. when we migrate, drop this",
        ".. when:: var.debug",
    ],
    "a branch whose content holds anything": [
        ".. when:: var.debug",
        "",
        "   A paragraph.",
        "",
        "   .. include:: other.rst",
        "",
        "   Heading",
        "   -------",
    ],
}

_RST_STRAYS: dict[str, tuple[list[str], _Stray]] = {
    "a paragraph": (
        [".. when:: var.debug", "   Content.", "", "A stray paragraph."],
        _Stray(3, None),
    ),
    "a target": ([".. _label:", ".. otherwise::"], _Stray(0, None)),
    "a substitution definition": (
        [".. |sub| image:: picture.png", ".. otherwise::"],
        _Stray(0, None),
    ),
    "a footnote": ([".. [1] A footnote.", ".. otherwise::"], _Stray(0, None)),
    "a citation": ([".. [CIT2002] A citation.", ".. otherwise::"], _Stray(0, None)),
    "an include": (
        [".. when:: var.debug", "   Content.", ".. include:: other.rst"],
        _Stray(2, None),
    ),
    "a false if": ([".. if:: False", "", "   .. when:: True"], _Stray(0, None)),
    "a note": ([".. note::", "", "   .. when:: True"], _Stray(0, None)),
    "default-role": ([".. default-role:: math", ".. otherwise::"], _Stray(0, None)),
    "a misspelt branch": ([".. wehn:: True", "   Content."], _Stray(0, None)),
    "a heading": (["Title", "-----", "", ".. when:: True"], _Stray(0, None)),
    "a transition": ([".. when:: True", "   A.", "", "---"], _Stray(3, None)),
    "three dots": (["...", ".. otherwise::"], _Stray(0, None)),
    "an anonymous target": (
        ["__ https://example.com", ".. otherwise::"],
        _Stray(0, None),
    ),
    "an indented first line": (
        ["   A block quote.", ".. when:: True"],
        _Stray(0, None),
    ),
    "a block quote after an empty comment": (
        ["..", "", "   .. req:: A need", ".. otherwise::"],
        _Stray(2, None),
    ),
    "the end-of-inclusion comment": (
        ['.. end of inclusion from "other.rst"', ".. otherwise::"],
        _Stray(0, None),
    ),
    "when with one colon": ([".. when: var.debug", "   Content."], _Stray(0, "when")),
    "When with one colon": ([".. When: var.debug", "   Content."], _Stray(0, "when")),
    "when, a space, one colon": ([".. when : var.debug"], _Stray(0, "when")),
    # docutils allows one space before `::`; with two the line is a comment
    "when with two spaces before the double colon": (
        [".. when  :: var.debug", "   A."],
        _Stray(0, "when"),
    ),
    "when without the space after the double colon": (
        [".. when::var.debug", "   Content."],
        _Stray(0, "when"),
    ),
    "otherwise with one colon": (
        [".. when:: var.debug", "   A.", ".. otherwise:", "   B."],
        _Stray(2, "otherwise"),
    ),
    "an empty comment whose text is a one-colon branch": (
        ["..", "   when: var.debug", ".. otherwise::"],
        _Stray(0, "when"),
    ),
}

# MyST, as myst-parser gives a directive its content

_MYST_ACCEPTED: dict[str, list[str]] = {
    "colon branches": [
        ":::{when} var.arch == 'arm'",
        "ARM content.",
        ":::",
        ":::{otherwise}",
        "Other content.",
        ":::",
    ],
    "backtick branches": [
        "```{when} var.debug",
        "Content.",
        "```",
        "```{otherwise}",
        "```",
    ],
    "a space before the name": ["::: {when} var.debug", "Content.", ":::"],
    "a name in another case": [":::{When} var.debug", "Content.", ":::"],
    "an opener indented three spaces": ["   :::{when} var.debug", "Content.", ":::"],
    "a closer indented three spaces": [
        ":::{when} var.debug",
        "Content.",
        "   :::",
        ":::{otherwise}",
        "Other.",
        ":::",
    ],
    "a closer followed by spaces and tabs": ["```{when} var.debug", "A.", "``` \t"],
    "a longer closer": [":::{when} var.debug", "A.", "::::::"],
    "a shorter fence nested in a branch": [
        "::::{when} var.debug",
        ":::{note}",
        "A note.",
        ":::",
        "::::",
    ],
    "a longer fence opened in a branch does not close it": [
        ":::{when} var.debug",
        "::::{note} A note.",
        "Content.",
        ":::",
    ],
    "comments and block breaks": [
        "% a comment",
        "+++",
        "+++ a block break with text",
        "++++",
        ":::{when} var.debug",
        ":::",
        "% when we migrate, drop this",
    ],
    "blank lines of spaces and tabs": ["", "  ", "\t", ":::{otherwise}", ":::"],
    "a tilde branch": ["~~~{when} var.debug", "Content.", "~~~"],
    "a backtick in a tilde fence's info": ["~~~{when} `var.debug`", "A.", "~~~"],
    "an indented comment": ["  % a comment", ":::{otherwise}", ":::"],
    "an indented block break": [" +++", ":::{otherwise}", ":::"],
    "a spaced block break": ["+ + +", "+  +\t+ text", ":::{otherwise}", ":::"],
    "a closer indented four spaces does not close": [
        ":::{when} var.debug",
        "    :::",
        "still the branch's",
        ":::",
    ],
    # markdown-it needs a `|` in the header line for a table
    "a delimiter row under an opener without a bar": [
        ":::{when} var.debug",
        "|---|---|",
        ":::",
    ],
    "an opener with a bar but no delimiter row after it": [
        ":::{when} var.a | var.b",
        "",
        "|---|---|",
        ":::",
    ],
    "an unclosed branch runs to the end": [
        ":::{when} var.debug",
        "Content.",
        "```{include} other.md",
    ],
}

_MYST_STRAYS: dict[str, tuple[list[str], _Stray]] = {
    "a paragraph": ([":::{when} var.debug", ":::", "", "A stray."], _Stray(3, None)),
    "a heading": (["# Heading", ":::{otherwise}", ":::"], _Stray(0, None)),
    "an html comment": (
        ["<!-- a comment -->", ":::{otherwise}", ":::"],
        _Stray(0, None),
    ),
    "eval-rst": (["```{eval-rst}", ".. when:: True", "```"], _Stray(0, None)),
    "an include": (["```{include} other.md", "```"], _Stray(0, None)),
    # a closer must be of the opener's fence character, not only long enough
    "a colon run inside a backtick branch closes nothing": (
        [
            "```{when} var.debug",
            ":::",
            "::::{when} x",
            "```",
            "```{include} other.md",
            "```",
        ],
        _Stray(4, None),
    ),
    # markdown-it tries its `table` rule before any fence: a table header, no branch
    "an opener a table swallows": (
        [
            ":::{when} var.debug | var.debug",
            "|---|---|",
            "",
            "```{req} A need",
            "```",
            ":::",
        ],
        _Stray(0, None),
    ),
    "an opener a table with aligned cells swallows": (
        ["```{when} var.a | var.b", " :--- | ---: ", "```"],
        _Stray(0, None),
    ),
    "no space after the name": ([":::{when}var.debug", "A.", ":::"], _Stray(0, None)),
    "a backtick in a backtick fence's info": (
        ["```{when} `var.debug`", "A.", "```"],
        _Stray(0, None),
    ),
    "an opener indented four spaces": (
        ["    :::{when} var.debug", "A."],
        _Stray(0, None),
    ),
    "an include after a closer indented three spaces": (
        [":::{when} var.debug", "Content.", "   :::", "```{include} other.md", "```"],
        _Stray(3, None),
    ),
    "a stray after a nested shorter fence's closer": (
        ["::::{when} var.debug", ":::{note}", "A.", ":::", "::::", "A stray."],
        _Stray(5, None),
    ),
    "a closer with text after it closes nothing": (
        [":::{when} var.debug", "A.", "::: x", "```{include} other.md"],
        None,
    ),
    "two pluses": (["++", ":::{otherwise}", ":::"], _Stray(0, None)),
    "a list item": (["+ an item", ":::{otherwise}", ":::"], _Stray(0, None)),
    "a comment indented four spaces": (
        ["    % code", ":::{otherwise}", ":::"],
        _Stray(0, None),
    ),
    "when with one colon": (
        ["% when: var.debug", ":::{otherwise}", ":::"],
        _Stray(0, "when"),
    ),
    "When, a space, one colon": (["% When : var.debug"], _Stray(0, "when")),
    "otherwise with one colon in a block break": (
        [":::{when} var.debug", ":::", "+++ otherwise:"],
        _Stray(2, "otherwise"),
    ),
    "when with one colon in an indented comment": (["   % when: x"], _Stray(0, "when")),
    "otherwise with one colon in a spaced block break": (
        ["+ + + otherwise:"],
        _Stray(0, "otherwise"),
    ),
}


@pytest.mark.parametrize("lines", list(_RST_ACCEPTED.values()), ids=list(_RST_ACCEPTED))
def test_rst_gate_accepts(lines: list[str]):
    """Every spelling of a branch and a comment that docutils accepts passes."""
    assert _gate(lines, syntax="rst") is None


@pytest.mark.parametrize(
    ("lines", "stray"), list(_RST_STRAYS.values()), ids=list(_RST_STRAYS)
)
def test_rst_gate_refuses(lines: list[str], stray: _Stray):
    """Every other top-level line is refused, at its index."""
    assert _gate(lines, syntax="rst") == stray


@pytest.mark.parametrize(
    "lines", list(_MYST_ACCEPTED.values()), ids=list(_MYST_ACCEPTED)
)
def test_myst_gate_accepts(lines: list[str]):
    """Every spelling of a branch fence, a comment and a block break MyST accepts passes."""
    assert _gate(lines, syntax="myst") is None


@pytest.mark.parametrize(
    ("lines", "stray"), list(_MYST_STRAYS.values()), ids=list(_MYST_STRAYS)
)
def test_myst_gate_refuses(lines: list[str], stray: _Stray | None):
    """Every other top-level line is refused, at its index.

    The gate never thinks it is inside a branch where MyST is not: a line that only
    looks like a closer, with text after it, closes nothing (so what follows is
    still the branch's, as it is MyST's).
    """
    assert _gate(lines, syntax="myst") == stray


def test_myst_gate_without_colon_fence():
    """Without the ``colon_fence`` extension a ``:::`` line opens nothing: a stray."""
    lines = [":::{when} var.debug", "Content.", ":::"]
    assert _gate(lines, syntax="myst", colon_fence=False) == _Stray(0, None)
    assert (
        _gate(["```{when} var.debug", "```"], syntax="myst", colon_fence=False) is None
    )


def test_myst_gate_without_fence():
    """With ``fence`` disabled, a backtick or tilde line opens nothing: a stray."""
    for marker in ("```", "~~~"):
        lines = [f"{marker}{{when}} var.debug", "Content.", marker]
        assert _gate(lines, syntax="myst", fence=False) == _Stray(0, None)
    assert _gate([":::{when} var.debug", ":::"], syntax="myst", fence=False) is None


def test_myst_gate_without_comments_or_block_breaks():
    """With ``myst_line_comment`` or ``myst_block_break`` disabled, the line is text."""
    assert _gate(["% a comment"], syntax="myst", comment=False) == _Stray(0, None)
    assert _gate(["+++"], syntax="myst", block_break=False) == _Stray(0, None)
    assert _gate(["% a comment", "+++"], syntax="myst") is None


# With markdown-it's `code` rule disabled no line is an indented code block, so
# indentation bounds none of the constructs the gate mirrors: (lines, the gate's
# answer without the rule, its answer with it, the default)
_WITHOUT_CODE: dict[str, tuple[list[str], _Stray | None, _Stray | None]] = {
    "a closer indented four spaces closes": (
        [":::{when} var.debug", "A.", "    :::", "A stray."],
        _Stray(3, None),
        None,
    ),
    "a closer led by a tab closes": (
        [":::{when} var.debug", "A.", "\t:::", "A stray."],
        _Stray(3, None),
        None,
    ),
    "an opener indented four spaces opens": (
        ["    :::{when} var.debug", "A.", ":::"],
        None,
        _Stray(0, None),
    ),
    "a comment indented four spaces": (
        ["    % a comment", ":::{otherwise}", ":::"],
        None,
        _Stray(0, None),
    ),
    "a block break indented four spaces": (
        ["    +++", ":::{otherwise}", ":::"],
        None,
        _Stray(0, None),
    ),
    "an opener over a delimiter row indented four spaces": (
        [":::{when} var.a | var.b", "    |---|---|", ":::"],
        _Stray(0, None),
        None,
    ),
}


@pytest.mark.parametrize(
    ("lines", "without_code", "with_code"),
    list(_WITHOUT_CODE.values()),
    ids=list(_WITHOUT_CODE),
)
def test_myst_gate_without_code(
    lines: list[str], without_code: _Stray | None, with_code: _Stray | None
):
    """Without the ``code`` rule, a construct indented four columns or more is live.

    markdown-it-py's ``is_code_block`` is false for every line once the ``code`` rule
    is disabled, so a fence, a closer, a delimiter row, a ``%`` comment or a ``+++``
    block break counts at any indentation; with the rule (the default) the same body
    gives the gate's usual answer.
    """
    assert _gate(lines, syntax="myst", code=False) == without_code
    assert _gate(lines, syntax="myst") == with_code
