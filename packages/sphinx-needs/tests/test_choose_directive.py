"""Tests for the ``.. choose::``, ``.. when::`` and ``.. otherwise::`` directives."""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path
from typing import NamedTuple

import pytest
from docutils import nodes

from sphinx_needs.data import SphinxNeedsData
from sphinx_needs.directives.needchoose import (
    ChooseDirective,
    OtherwiseDirective,
    _absolute_location,
    _BranchPlaceholder,
    _ChooseBody,
)
from sphinx_needs_testkit import assert_no_warnings, build_warnings

_NEEDS_TYPES = (
    "needs_types = [{'directive': 'req', 'title': 'Requirement',"
    " 'prefix': 'REQ_', 'color': '#BFD8D2'}]\n"
)
_VARIANT_DATA = (
    "needs_variant_data = {'arch': 'abc', 'debug': True, 'count': 5,"
    " 'tags': ['a', 'b'], 'build': {'features': ['f1', 'f2']}}\n"
)
_CONF = "extensions = ['sphinx_needs']\n" + _VARIANT_DATA + _NEEDS_TYPES
_CONF_NO_VARIANT_DATA = "extensions = ['sphinx_needs']\n" + _NEEDS_TYPES
_CONF_MYST = (
    "extensions = ['sphinx_needs', 'myst_parser']\n"
    "myst_enable_extensions = ['colon_fence']\n" + _VARIANT_DATA + _NEEDS_TYPES
)
# a variant value whose truth value cannot be taken, as a NumPy array's cannot: an `int`,
# so that the variant-data validation passes it, pickled as the plain `int` (Sphinx pickles
# the configuration, and a class defined in `conf.py` cannot be found by name again)
_CONF_AMBIGUOUS = (
    "extensions = ['sphinx_needs']\n"
    "class Ambiguous(int):\n"
    "    def __bool__(self):\n"
    "        raise ValueError('The truth value of an array with more than one element'\n"
    "                         ' is ambiguous')\n"
    "    def __reduce__(self):\n"
    "        return (int, (int(self),))\n"
    "needs_variant_data = {'matrix': Ambiguous(3)}\n" + _NEEDS_TYPES
)

_HAS_MYST = importlib.util.find_spec("myst_parser") is not None


def _project(
    body: str,
    /,
    *,
    conf: str = _CONF,
    myst: bool = False,
    other: str | None = None,
    extra: tuple[tuple[str, str], ...] = (),
) -> dict[str, object]:
    """An inline project whose root document is a title followed by ``body``.

    :param body: The source after the title.
    :param conf: The ``conf.py``.
    :param myst: Write the documents as MyST Markdown (``.md``) rather than RST.
    :param other: The source of a second document, ``other``, if there is one.
    :param extra: Further files, as ``(name, text)``, such as files to include.
    """
    suffix, title = (".md", "# Test\n\n") if myst else (".rst", "Test\n====\n\n")
    files = [(Path("conf.py"), conf), (Path("index" + suffix), title + body)]
    if other is not None:
        files.append((Path("other" + suffix), other))
    files.extend((Path(name), text) for name, text in extra)
    return {"buildername": "html", "files": files}


def _line_of(source: str, text: str) -> int:
    """The 1-based number of the one line of ``source`` that is exactly ``text``."""
    lines = [i for i, line in enumerate(source.splitlines(), 1) if line == text]
    assert len(lines) == 1, f"{text!r} is on lines {lines}"
    return lines[0]


def _assert_no_choose_nodes(app) -> None:
    """Neither private node class reaches a pickled doctree or the need-node cache."""
    private = (_BranchPlaceholder, _ChooseBody)
    for docname in sorted(app.env.found_docs):
        doctree = app.env.get_doctree(docname)
        assert [
            n for n in doctree.findall(nodes.Element) if isinstance(n, private)
        ] == []
    data = SphinxNeedsData(app.env)
    for need_id in data.get_needs_view():
        need_node = data.get_need_node(need_id)
        assert need_node is not None, need_id
        assert [
            n for n in need_node.findall(nodes.Element) if isinstance(n, private)
        ] == [], need_id


def _section_titles(app, docname: str) -> list[list[str]]:
    """The title path of every section of a document, outermost first."""
    paths = []
    for section in app.env.get_doctree(docname).findall(nodes.section):
        path = []
        node = section
        while isinstance(node, nodes.section):
            path.insert(0, node[0].astext())
            node = node.parent
        paths.append(path)
    return paths


# The happy paths, reStructuredText


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "html", "srcdir": "doc_test/doc_choose_directive"}],
    indirect=True,
)
def test_choose_directive(test_app):
    """First true branch wins, the otherwise, needs, sections, nesting and includes.

    The project builds without a single warning,
    although a branch after a taken one has a condition that is not Python
    and another names an unknown key: neither is ever evaluated.
    """
    app = test_app
    app.build()
    assert_no_warnings(app)

    html = Path(app.outdir, "index.html").read_text()
    taken = [
        "TAKEN_P1_FIRST",
        "TAKEN_P2_DEFAULT",
        "TAKEN_P2B_AFTER_CHOOSE",
        "TAKEN_P4_SECTION_BODY",
        "TAKEN_P5_OUTER",
        "TAKEN_P5_INNER_DEFAULT",
        "TAKEN_P5B_IN_NEED",
        "TAKEN_X1_INCLUDED_CHOOSE_DEFAULT",
        "TAKEN_X2_INCLUDED_TEXT",
        "TAKEN_X2_AFTER_INCLUDE",
        "TAKEN_X2_AFTER_CHOOSE",
    ]
    assert [word for word in taken if word not in html] == []
    # each taken branch is rendered once
    assert [word for word in taken if html.count(f"<p>{word}</p>") != 1] == []
    assert "SKIPPED_" not in html

    # the needs of the branches that are not taken are never created
    needs = SphinxNeedsData(app.env).get_needs_view()
    assert sorted(needs) == ["REQ_HOST", "REQ_P3_TAKEN", "REQ_X2_INCLUDED"]
    # the need of the taken branch knows the line it was written on
    source = Path(app.srcdir, "index.rst").read_text()
    assert needs["REQ_P3_TAKEN"]["lineno"] == _line_of(
        source, "      .. req:: In the taken branch"
    )

    # a heading in the taken branch is a section of the document, nested where it stands
    sections = _section_titles(app, "index")
    assert [
        "CHOOSE Test",
        "P4 sections in the taken branch",
        "P4 conditional heading",
    ] in sections
    assert not [path for path in sections if "P4 skipped heading" in path]

    # the need with a choose in its content is extracted on the other page
    other = Path(app.outdir, "other.html").read_text()
    assert "TAKEN_P5B_IN_NEED" in other
    assert "SKIPPED_" not in other

    _assert_no_choose_nodes(app)


# Each mistake warns once, at the line that has it, and skips the whole choose


class _Expected(NamedTuple):
    """What a build of ``body`` must report and render."""

    body: str
    #: per warning, in order: a substring, and the source line the warning must name
    warnings: tuple[tuple[str, str], ...]
    #: words that must be rendered (and no word starting ``SKIPPED_`` may be)
    taken: tuple[str, ...] = ()
    #: the ids the needs view must hold
    needs: tuple[str, ...] = ()
    conf: str = _CONF
    #: further files of the project, as ``(name, text)``
    extra: tuple[tuple[str, str], ...] = ()
    #: the file the warnings are located in
    located_in: str = "index.rst"


_SKIP = "; the whole choose is skipped"


def _stray(text: str) -> str:
    """The warning about a line of the body that is neither a branch nor a comment.

    The gate refuses it before anything in the body is parsed, at its line,
    and names its text.
    """
    return (
        "'choose' directive may contain only 'when' and 'otherwise' directives and "
        f"comments, got {text!r}" + _SKIP
    )


_NO_BRANCH = "'choose' directive has no 'when' or 'otherwise'"


def _branch_like(kind: str, write: str) -> str:
    """The warning about a comment that begins with ``kind`` and a colon."""
    return (
        f"'choose' directive has a comment that begins with '{kind}:' "
        f"(a branch written with one colon? write {write})" + _SKIP
    )


_WHEN_LIKE = _branch_like("when", "'.. when:: <condition>'")
_OTHERWISE_LIKE = _branch_like("otherwise", "'.. otherwise::'")
# under MyST the hint names the fence
_WHEN_LIKE_MYST = _branch_like("when", "a '{when} <condition>' fence")
_OTHERWISE_LIKE_MYST = _branch_like("otherwise", "an '{otherwise}' fence")
_BRANCHES_TXT = (
    '.. when:: var.arch == "xyz"\n\n   SKIPPED_X1_FROM_INCLUDE\n\n'
    ".. otherwise::\n\n   SKIPPED_X1_DEFAULT_FROM_INCLUDE\n"
)

_WARNINGS = {
    "otherwise not last": _Expected(
        ".. choose::\n\n"
        "   .. otherwise::\n\n      SKIPPED_DEFAULT\n\n"
        "   .. when:: True\n\n      SKIPPED_TRUE\n",
        (
            (
                "'choose' directive has an 'otherwise' that is not its last branch"
                + _SKIP,
                "   .. otherwise::",
            ),
        ),
    ),
    "two otherwise": _Expected(
        ".. choose::\n\n"
        "   .. when:: False\n\n      SKIPPED_FALSE\n\n"
        "   .. otherwise::\n\n      SKIPPED_D1\n\n"
        # the second otherwise is refused as a second one: its directive line ends in
        # spaces, which is no condition, so it is not refused as having one
        "   .. otherwise::  \n\n      SKIPPED_D2\n",
        (
            (
                "'choose' directive has more than one 'otherwise'" + _SKIP,
                "   .. otherwise::  ",
            ),
        ),
    ),
    # the check order: the condition faults, in document order, come before the count
    # and the position of the `otherwise`, which come in that order
    "two otherwise, then a when without a condition": _Expected(
        ".. choose::\n\n"
        "   .. otherwise::\n\n      SKIPPED_D1\n\n"
        "   .. otherwise::\n\n      SKIPPED_D2\n\n"
        "   .. when::\n\n      SKIPPED_FORGOTTEN_CONDITION\n",
        (
            (
                "'when' directive has no condition (use 'otherwise' for the default)"
                + _SKIP,
                "   .. when::",
            ),
        ),
    ),
    "an otherwise with a condition, a when, then a bare otherwise": _Expected(
        ".. choose::\n\n"
        "   .. otherwise:: var.debug\n\n      SKIPPED_FIRST\n\n"
        "   .. when:: var.arch == 'abc'\n\n      SKIPPED_ABC\n\n"
        "   .. otherwise::\n\n      SKIPPED_LAST\n",
        (
            (
                "'otherwise' directive takes no condition, got 'var.debug'" + _SKIP,
                "   .. otherwise:: var.debug",
            ),
        ),
    ),
    # both bare: the first line ends in spaces only so that the two lines differ
    "two bare otherwise and nothing else": _Expected(
        ".. choose::\n\n"
        "   .. otherwise::  \n\n      SKIPPED_D1\n\n"
        "   .. otherwise::\n\n      SKIPPED_D2\n",
        (
            (
                "'choose' directive has more than one 'otherwise'" + _SKIP,
                "   .. otherwise::",
            ),
        ),
    ),
    # a forgotten condition on the last `when` would make a catch-all of it: refused,
    # since the default is written as an `otherwise`
    "when without a condition": _Expected(
        ".. choose::\n\n"
        "   .. when:: var.arch == 'xyz'\n\n      SKIPPED_XYZ\n\n"
        "   .. when::\n\n      SKIPPED_FORGOTTEN_CONDITION\n",
        (
            (
                "'when' directive has no condition (use 'otherwise' for the default)"
                + _SKIP,
                "   .. when::",
            ),
        ),
    ),
    # a true condition: an `otherwise` that took it as a `when` would render it
    "otherwise with a condition": _Expected(
        ".. choose::\n\n"
        "   .. when:: var.arch == 'xyz'\n\n      SKIPPED_XYZ\n\n"
        "   .. otherwise:: var.debug\n\n      SKIPPED_OTHERWISE\n",
        (
            (
                "'otherwise' directive takes no condition, got 'var.debug'" + _SKIP,
                "   .. otherwise:: var.debug",
            ),
        ),
    ),
    # the condition faults are in document order: the otherwise's comes first here
    "an otherwise with a condition, then a when without one": _Expected(
        ".. choose::\n\n"
        "   .. otherwise:: var.debug\n\n      SKIPPED_FIRST\n\n"
        "   .. when::\n\n      SKIPPED_FORGOTTEN_CONDITION\n",
        (
            (
                "'otherwise' directive takes no condition, got 'var.debug'" + _SKIP,
                "   .. otherwise:: var.debug",
            ),
        ),
    ),
    # the children are checked before the condition faults: the stray paragraph after
    # a when without a condition is what is reported
    "a when without a condition, then a stray paragraph": _Expected(
        ".. choose::\n\n"
        "   .. when::\n\n      SKIPPED_FORGOTTEN_CONDITION\n\n"
        "   A stray paragraph.\n",
        ((_stray("A stray paragraph."), "   A stray paragraph."),),
    ),
    # a branch written with one colon is a comment that swallows the content under it;
    # comments are accepted, so for the variant it was written for (`abc`) the choose
    # would render its otherwise, silently
    "when with one colon": _Expected(
        ".. choose::\n\n"
        "   .. when: var.arch == 'abc'\n\n      SKIPPED_SWALLOWED_BRANCH\n\n"
        "   .. otherwise::\n\n      SKIPPED_OTHERWISE\n",
        ((_WHEN_LIKE, "   .. when: var.arch == 'abc'"),),
    ),
    "otherwise with one colon": _Expected(
        ".. choose::\n\n"
        "   .. when:: var.arch == 'xyz'\n\n      SKIPPED_XYZ\n\n"
        "   .. otherwise:\n\n      SKIPPED_SWALLOWED_OTHERWISE\n",
        ((_OTHERWISE_LIKE, "   .. otherwise:"),),
    ),
    # the rule is case-insensitive, as directive names are
    "When with one colon, capitalised": _Expected(
        ".. choose::\n\n"
        "   .. When: var.arch == 'abc'\n\n      SKIPPED_SWALLOWED_BRANCH\n\n"
        "   .. otherwise::\n\n      SKIPPED_OTHERWISE\n",
        ((_WHEN_LIKE, "   .. When: var.arch == 'abc'"),),
    ),
    # and tolerates whitespace before the colon
    "when with a space before one colon": _Expected(
        ".. choose::\n\n"
        "   .. when : var.arch == 'abc'\n\n      SKIPPED_SWALLOWED_BRANCH\n\n"
        "   .. otherwise::\n\n      SKIPPED_OTHERWISE\n",
        ((_WHEN_LIKE, "   .. when : var.arch == 'abc'"),),
    ),
    # docutils allows one space before `::`: with two the line is a comment that would
    # swallow the branch, refused by the one-colon rule
    "when with two spaces before the colons": _Expected(
        ".. choose::\n\n"
        "   .. when  :: var.debug\n\n      SKIPPED_SWALLOWED_BRANCH\n\n"
        "   .. otherwise::\n\n      SKIPPED_OTHERWISE\n",
        ((_WHEN_LIKE, "   .. when  :: var.debug"),),
    ),
    # docutils needs a space (or the end of the line) after `::` for a directive
    "when without the space after ::": _Expected(
        ".. choose::\n\n"
        "   .. when::var.arch == 'abc'\n\n      SKIPPED_SWALLOWED_BRANCH\n\n"
        "   .. otherwise::\n\n      SKIPPED_OTHERWISE\n",
        ((_WHEN_LIKE, "   .. when::var.arch == 'abc'"),),
    ),
    # the control: a comment that merely begins with the word is accepted
    "a comment that starts with the word when": _Expected(
        ".. choose::\n\n"
        "   .. when we migrate, drop this\n\n"
        "   .. when:: var.arch == 'abc'\n\n      TAKEN_AFTER_WORD_COMMENT\n\n"
        "   .. otherwise::\n\n      SKIPPED_OTHERWISE\n",
        (),
        taken=("TAKEN_AFTER_WORD_COMMENT",),
    ),
    # it is a fault of a child, found with the others in document order, before the
    # condition faults: after a when without a condition, the comment is reported
    "a when without a condition, then a when with one colon": _Expected(
        ".. choose::\n\n"
        "   .. when::\n\n      SKIPPED_FORGOTTEN_CONDITION\n\n"
        "   .. when: var.debug\n\n      SKIPPED_SWALLOWED_BRANCH\n",
        ((_WHEN_LIKE, "   .. when: var.debug"),),
    ),
    "paragraph in the body": _Expected(
        ".. choose::\n\n"
        "   .. when:: True\n\n      SKIPPED_BRANCH\n\n"
        "   A stray paragraph.\n",
        ((_stray("A stray paragraph."), "   A stray paragraph."),),
    ),
    # a directive in the body is refused at its own line, before it runs: the branch
    # in the note is never reached
    "note wrapping a branch": _Expected(
        ".. choose::\n\n"
        "   .. note::\n\n      .. when:: True\n\n         SKIPPED_IN_NOTE\n",
        ((_stray(".. note::"), "   .. note::"),),
    ),
    # a directive that would hand the nodes of its content to the choose (a true `if`,
    # `rst-class`) is refused the same way: a branch must be written directly in it
    "branches inside a true if": _Expected(
        ".. choose::\n\n"
        "   .. if:: var.debug\n\n"
        "      .. when:: var.arch == 'x86'\n\n         SKIPPED_X86\n\n"
        "      .. otherwise::\n\n         SKIPPED_DEFAULT_FROM_IF\n",
        ((_stray(".. if:: var.debug"), "   .. if:: var.debug"),),
    ),
    "branch inside rst-class": _Expected(
        ".. choose::\n\n"
        "   .. rst-class:: special\n\n"
        "      .. when:: var.arch == 'abc'\n\n         SKIPPED_FROM_RST_CLASS\n",
        ((_stray(".. rst-class:: special"), "   .. rst-class:: special"),),
    ),
    "otherwise inside a true if": _Expected(
        ".. choose::\n\n"
        "   .. when:: False\n\n      SKIPPED_FALSE\n\n"
        "   .. if:: var.debug\n\n"
        "      .. otherwise::\n\n         SKIPPED_DEFAULT_FROM_IF\n",
        ((_stray(".. if:: var.debug"), "   .. if:: var.debug"),),
    ),
    # a directive that produces no node used to pass unnoticed: a false `if` hid the
    # branches in it and the otherwise was taken; now it is refused like any other
    "a false if in the body": _Expected(
        ".. choose::\n\n"
        "   .. if:: False\n\n"
        "      .. when:: True\n\n         SKIPPED_IN_FALSE_IF\n\n"
        "   .. otherwise::\n\n      SKIPPED_OTHERWISE\n",
        ((_stray(".. if:: False"), "   .. if:: False"),),
    ),
    "default-role in the body": _Expected(
        ".. choose::\n\n"
        "   .. default-role:: math\n\n"
        "   .. otherwise::\n\n      SKIPPED_OTHERWISE\n",
        ((_stray(".. default-role:: math"), "   .. default-role:: math"),),
    ),
    # a target and a substitution definition are not comments
    "a label in the body": _Expected(
        ".. choose::\n\n"
        "   .. _label_in_the_body:\n\n"
        "   .. otherwise::\n\n      SKIPPED_OTHERWISE\n",
        ((_stray(".. _label_in_the_body:"), "   .. _label_in_the_body:"),),
    ),
    "a substitution definition in the body": _Expected(
        ".. choose::\n\n"
        "   .. |sub| replace:: text\n\n"
        "   .. otherwise::\n\n      SKIPPED_OTHERWISE\n",
        ((_stray(".. |sub| replace:: text"), "   .. |sub| replace:: text"),),
    ),
    # an empty comment ends at the blank line after it: the indented block that follows
    # would be a block quote of the body, and the need in it would run
    "a block quote after an empty comment": _Expected(
        ".. choose::\n\n"
        "   ..\n\n"
        "      .. req:: In a block quote\n         :id: REQ_QUOTED\n\n"
        "   .. otherwise::\n\n      SKIPPED_OTHERWISE\n",
        # the stray's text keeps its indentation (the body is dedented by three)
        ((_stray("   .. req:: In a block quote"), "      .. req:: In a block quote"),),
    ),
    # a line of one to three punctuation characters would make docutils emit an INFO
    # message and a paragraph; it is refused before docutils sees it
    "rule line between branches": _Expected(
        ".. choose::\n\n"
        "   .. when:: var.arch == 'x86'\n\n      SKIPPED_X86\n\n"
        "   ---\n\n"
        "   .. otherwise::\n\n      SKIPPED_DEFAULT\n",
        ((_stray("---"), "   ---"),),
    ),
    "three dots in the body": _Expected(
        ".. choose::\n\n   ...\n\n   .. otherwise::\n\n      SKIPPED_DEFAULT\n",
        ((_stray("..."), "   ..."),),
    ),
    "when outside a choose": _Expected(
        "Para.\n\n.. when:: True\n\n   SKIPPED_STRAY\n",
        (
            (
                "'when' directive outside a 'choose' (a 'when' must be a direct child "
                "of a 'choose'); its content is skipped",
                ".. when:: True",
            ),
        ),
    ),
    # the counterpart of an orphan `else`: an otherwise outside every choose
    "otherwise outside a choose": _Expected(
        "Para.\n\n.. otherwise::\n\n   SKIPPED_STRAY_DEFAULT\n",
        (
            (
                "'otherwise' directive outside a 'choose' (an 'otherwise' must be a "
                "direct child of a 'choose'); its content is skipped",
                ".. otherwise::",
            ),
        ),
    ),
    "branch loose in the taken branch": _Expected(
        ".. choose::\n\n"
        "   .. when:: True\n\n      TAKEN_OUTER\n\n"
        "      .. when:: True\n\n         SKIPPED_LOOSE\n",
        (("'when' directive outside a 'choose'", "      .. when:: True"),),
        taken=("TAKEN_OUTER",),
    ),
    # a choose written directly in another choose's body is a stray of the outer one,
    # refused before it runs: one warning, and the loose branch in its taken branch is
    # never reached
    "branch loose in the taken branch of a misplaced choose": _Expected(
        ".. choose::\n\n"
        "   .. choose::\n\n"
        "      .. when:: True\n\n"
        "         .. when:: True\n\n            SKIPPED_LOOSE\n",
        ((_stray(".. choose::"), "   .. choose::"),),
    ),
    "unevaluable first branch poisons the otherwise": _Expected(
        ".. choose::\n\n"
        "   .. when:: this is not python !!!\n\n      SKIPPED_1\n\n"
        "   .. when:: True\n\n      SKIPPED_2\n\n"
        "   .. otherwise::\n\n      SKIPPED_DEFAULT\n",
        (
            (
                "'when' directive expression failed: 'this is not python !!!' — ",
                "   .. when:: this is not python !!!",
            ),
        ),
    ),
    "unknown key in a later branch": _Expected(
        ".. choose::\n\n"
        "   .. when:: var.arch == 'xyz'\n\n      SKIPPED_1\n\n"
        "   .. when:: var.no_such_key == 1\n\n      SKIPPED_2\n\n"
        "   .. otherwise::\n\n      SKIPPED_DEFAULT\n",
        (
            (
                "'when' directive expression failed: 'var.no_such_key == 1' — "
                "Unknown variant key: var.no_such_key",
                "   .. when:: var.no_such_key == 1",
            ),
        ),
    ),
    "builtins blocked": _Expected(
        ".. choose::\n\n"
        "   .. when:: __import__('os').system('echo pwned')\n\n      SKIPPED\n\n"
        "   .. otherwise::\n\n      SKIPPED_DEFAULT\n",
        (
            (
                "'when' directive expression failed: "
                "\"__import__('os').system('echo pwned')\" — "
                "name '__import__' is not defined",
                "   .. when:: __import__('os').system('echo pwned')",
            ),
        ),
    ),
    # taking the truth value of the result may raise as well (a NumPy array's does):
    # the condition is unevaluable, as for any expression that fails, and poisons the
    # choose; it is not also reported as a result that is not a bool
    "a truth value that raises poisons the otherwise": _Expected(
        ".. choose::\n\n"
        "   .. when:: var.matrix\n\n      SKIPPED_AMBIGUOUS\n\n"
        "   .. when:: True\n\n      SKIPPED_TRUE\n\n"
        "   .. otherwise::\n\n      SKIPPED_DEFAULT\n",
        (
            (
                "'when' directive expression failed: 'var.matrix' — "
                "The truth value of an array with more than one element is ambiguous",
                "   .. when:: var.matrix",
            ),
        ),
        conf=_CONF_AMBIGUOUS,
    ),
    "non-bool is coerced and taken": _Expected(
        ".. choose::\n\n"
        "   .. when:: var.count\n\n      TAKEN_NONBOOL\n\n"
        "   .. otherwise::\n\n      SKIPPED_DEFAULT\n",
        (
            (
                "'when' directive expression did not return a bool, got int: 5 "
                "(coercing to bool): 'var.count'",
                "   .. when:: var.count",
            ),
        ),
        taken=("TAKEN_NONBOOL",),
    ),
    "empty string condition": _Expected(
        '.. choose::\n\n   .. when:: ""\n\n      SKIPPED_EMPTY\n\n'
        "   .. otherwise::\n\n      TAKEN_DEFAULT\n",
        (
            (
                "'when' directive expression did not return a bool, got str: '' "
                "(coercing to bool): '\"\"'",
                '   .. when:: ""',
            ),
        ),
        taken=("TAKEN_DEFAULT",),
    ),
    "choose with an argument": _Expected(
        ".. choose:: var.arch\n\n   .. when:: True\n\n      SKIPPED\n",
        (
            (
                "'choose' directive takes no argument, got 'var.arch' "
                "(write a condition on each 'when')" + _SKIP,
                ".. choose:: var.arch",
            ),
        ),
    ),
    "empty choose": _Expected(
        ".. choose::\n\nTAKEN_AFTER_EMPTY\n",
        ((_NO_BRANCH, ".. choose::"),),
        taken=("TAKEN_AFTER_EMPTY",),
    ),
    "only comments": _Expected(
        ".. choose::\n\n   .. just a comment\n\n   .. and another\n",
        ((_NO_BRANCH, ".. choose::"),),
    ),
    "variant data not configured": _Expected(
        ".. choose::\n\n"
        "   .. when:: var.arch == 'abc'\n\n      SKIPPED_1\n\n"
        "   .. otherwise::\n\n      SKIPPED_DEFAULT\n",
        (
            (
                "'choose' directive used but needs_variant_data is not configured"
                + _SKIP,
                ".. choose::",
            ),
        ),
        conf=_CONF_NO_VARIANT_DATA,
    ),
    # nothing is evaluated here, and still the choose warns and renders nothing:
    # the "used but not configured" rule holds for every choose
    "variant data not configured, only an otherwise": _Expected(
        ".. choose::\n\n   .. otherwise::\n\n      SKIPPED_DEFAULT_ONLY\n",
        (
            (
                "'choose' directive used but needs_variant_data is not configured"
                + _SKIP,
                ".. choose::",
            ),
        ),
        conf=_CONF_NO_VARIANT_DATA,
    ),
    # the structure is checked before the configuration: a choose that is wrong in both
    # ways gets the one structural warning, at the branch, and its body is still parsed
    "variant data not configured, and a misplaced otherwise": _Expected(
        ".. choose::\n\n"
        "   .. otherwise::\n\n      SKIPPED_DEFAULT\n\n"
        "   .. when:: var.arch == 'abc'\n\n      SKIPPED_ABC\n",
        (
            (
                "'choose' directive has an 'otherwise' that is not its last branch"
                + _SKIP,
                "   .. otherwise::",
            ),
        ),
        conf=_CONF_NO_VARIANT_DATA,
    ),
    # and a when without a condition is a structural mistake too, warned at the when
    "variant data not configured, and a when without a condition": _Expected(
        ".. choose::\n\n   .. when::\n\n      SKIPPED_FORGOTTEN_CONDITION\n",
        (
            (
                "'when' directive has no condition (use 'otherwise' for the default)"
                + _SKIP,
                "   .. when::",
            ),
        ),
        conf=_CONF_NO_VARIANT_DATA,
    ),
    # the branches of a choose are written in its body: an include in it is refused at
    # its own line, in the host, and the included file is never read
    "branches from an include": _Expected(
        ".. choose::\n\n   .. include:: branches.txt\n",
        ((_stray(".. include:: branches.txt"), "   .. include:: branches.txt"),),
        extra=(("branches.txt", _BRANCHES_TXT),),
    ),
    # the two other exits that may report a location in an included file:
    # an evaluation fault inside a choose the include holds, and a stray branch
    "an unevaluable when in an included choose": _Expected(
        ".. include:: inc.txt\n",
        (("'when' directive expression failed", "   .. when:: invalid !!!"),),
        extra=(
            (
                "inc.txt",
                ".. choose::\n\n   .. when:: invalid !!!\n\n      SKIPPED_INC\n\n"
                "   .. otherwise::\n\n      SKIPPED_INC_DEFAULT\n",
            ),
        ),
        located_in="inc.txt",
    ),
    "a stray when in an included file": _Expected(
        ".. include:: stray.txt\n",
        (("'when' directive outside a 'choose'", ".. when:: True"),),
        extra=(("stray.txt", ".. when:: True\n\n   SKIPPED_STRAY\n"),),
        located_in="stray.txt",
    ),
    # the gate and the structural checks report through the same helper, whose
    # location must be absolute as well: a stray, and a branch fault, in a choose an
    # include holds (docutils gives the included file a cwd-relative path)
    "a stray in an included choose": _Expected(
        ".. include:: stray_body.txt\n",
        ((_stray("A stray paragraph."), "   A stray paragraph."),),
        extra=(
            (
                "stray_body.txt",
                ".. choose::\n\n   A stray paragraph.\n\n"
                "   .. otherwise::\n\n      SKIPPED_STRAY_BODY\n",
            ),
        ),
        located_in="stray_body.txt",
    ),
    "a when without a condition in an included choose": _Expected(
        ".. include:: bare_when.txt\n",
        (
            (
                "'when' directive has no condition (use 'otherwise' for the default)",
                "   .. when::",
            ),
        ),
        extra=(
            (
                "bare_when.txt",
                ".. choose::\n\n   .. when::\n\n      SKIPPED_BARE_IN_INCLUDE\n",
            ),
        ),
        located_in="bare_when.txt",
    ),
    # the body is read before any condition: a true branch written in place before
    # the include is not taken either
    "a branch from an include after a true branch": _Expected(
        ".. choose::\n\n"
        "   .. when:: True\n\n      SKIPPED_IN_PLACE\n\n"
        "   .. include:: branches.txt\n",
        ((_stray(".. include:: branches.txt"), "   .. include:: branches.txt"),),
        extra=(("branches.txt", _BRANCHES_TXT),),
    ),
    "an otherwise from an include": _Expected(
        ".. choose::\n\n"
        "   .. when:: False\n\n      SKIPPED_FALSE\n\n"
        "   .. include:: otherwise.txt\n",
        ((_stray(".. include:: otherwise.txt"), "   .. include:: otherwise.txt"),),
        extra=(("otherwise.txt", ".. otherwise::\n\n   SKIPPED_FROM_INCLUDE\n"),),
    ),
    # content outside a branch is refused before it is parsed: the need never exists
    "need directly in the body": _Expected(
        ".. choose::\n\n"
        "   .. req:: Directly in the choose body\n      :id: REQ_DIRECT\n\n"
        "   .. when:: True\n\n      SKIPPED\n",
        (
            (
                _stray(".. req:: Directly in the choose body"),
                "   .. req:: Directly in the choose body",
            ),
        ),
    ),
    # a branch that is not taken is never parsed, exactly as the body of a false `if`
    "errors in an untaken branch are never reported": _Expected(
        ".. choose::\n\n"
        "   .. when:: True\n\n      TAKEN_E\n\n"
        "      .. req:: In the taken branch\n         :id: REQ_TAKEN\n\n"
        "   .. when:: False\n\n"
        "      .. choose::\n\n"
        "         .. when:: invalid !!!\n\n            SKIPPED\n\n"
        "      .. nosuchdirective::\n\n"
        "      .. req:: In the branch that is not taken\n         :id: REQ_SKIPPED\n",
        (),
        taken=("TAKEN_E",),
        needs=("REQ_TAKEN",),
    ),
}


@pytest.mark.parametrize(
    ("test_app", "expected"),
    [
        (_project(row.body, conf=row.conf, extra=row.extra), row)
        for row in _WARNINGS.values()
    ],
    ids=list(_WARNINGS),
    indirect=["test_app"],
)
def test_choose_warnings(test_app, expected: _Expected, monkeypatch):
    """Each mistake warns exactly once, at the offending line, and fails closed.

    Built from the source directory: docutils then records an included file relative
    to the working directory (``branches.txt`` rather than an absolute path), which is
    what the warnings must make absolute again, and what a build from a project's
    own directory gives in practice.
    """
    app = test_app
    monkeypatch.chdir(app.srcdir)
    app.build()
    warnings = build_warnings(app)
    assert len(warnings) == len(expected.warnings), warnings
    source = Path(app.srcdir, expected.located_in).read_text()
    for warning, (text, line) in zip(warnings, expected.warnings, strict=True):
        assert warning.startswith(
            f"<srcdir>/{expected.located_in}:{_line_of(source, line)}: WARNING: "
        ), warning
        assert text in warning, warning
        assert warning.endswith(" [needs.choose]"), warning
    html = Path(app.outdir, "index.html").read_text()
    assert [word for word in expected.taken if word not in html] == []
    assert "SKIPPED" not in html
    assert sorted(SphinxNeedsData(app.env).get_needs_view()) == list(expected.needs)
    _assert_no_choose_nodes(app)


@pytest.mark.parametrize(
    ("test_app", "line"),
    [
        (
            _project(
                ".. choose::\n\n"
                "   .. when:: var.arch == 'x86'\n\n      SKIPPED_X86\n\n"
                f"   {line}\n\n"
                "   .. otherwise::\n\n      SKIPPED_DEFAULT\n",
                extra=(("docutils.conf", f"[general]\nreport_level: {level}\n"),),
            ),
            line,
        )
        for level, line in ((1, "---"), (4, ".. wehn:: True"))
    ],
    ids=["a rule line, report level 1", "a misspelt directive, report level 4"],
    indirect=["test_app"],
)
def test_choose_refuses_a_stray_whatever_the_report_level(test_app, line, monkeypatch):
    """A stray line is refused by the ``choose`` itself, before docutils parses it.

    So the project's ``report_level`` (in its ``docutils.conf``) changes nothing:
    at level 1 the INFO docutils would give a ``---`` line never appears, and at
    level 4, which hides every docutils error, a misspelt branch is still refused
    with a warning rather than letting the ``otherwise`` render with ``-W`` green.
    ``sphinx-build`` points ``DOCUTILSCONFIG`` at the project's ``docutils.conf``;
    this in-process build does it by hand.
    """
    app = test_app
    monkeypatch.setenv("DOCUTILSCONFIG", str(Path(app.srcdir, "docutils.conf")))
    app.build()
    (warning,) = build_warnings(app)
    source = Path(app.srcdir, "index.rst").read_text()
    assert warning.startswith(
        f"<srcdir>/index.rst:{_line_of(source, f'   {line}')}: WARNING: "
    ), warning
    assert _stray(line) in warning, warning
    assert warning.endswith(" [needs.choose]"), warning
    assert "SKIPPED" not in Path(app.outdir, "index.html").read_text()
    # docutils never saw the line
    assert "Unexpected possible title overline" not in app._status.getvalue()


@pytest.mark.parametrize(
    ("test_app", "line", "error"),
    [
        (
            _project(
                ".. choose::\n\n"
                "   .. cas:: True\n\n      SKIPPED\n\n"
                "   .. otherwise::\n\n      SKIPPED_DEFAULT\n"
            ),
            ".. cas:: True",
            'Unknown directive type "cas"',
        ),
        (
            _project(
                ".. choose::\n\n"
                "   Title\n   -----\n\n"
                "   .. when:: True\n\n      SKIPPED\n"
            ),
            "Title",
            "Unexpected section title",
        ),
    ],
    ids=["typo in a directive name", "section title in the body"],
    indirect=["test_app"],
)
def test_choose_body_mistake_reported_once(test_app, line: str, error: str):
    """A mistake in the body is refused once, by the ``choose``, at its line.

    docutils never parses the line, so its own error for it never appears.
    """
    app = test_app
    app.build()
    (warning,) = build_warnings(app)
    source = Path(app.srcdir, "index.rst").read_text()
    assert warning.startswith(
        f"<srcdir>/index.rst:{_line_of(source, f'   {line}')}: WARNING: "
    ), warning
    assert _stray(line) in warning, warning
    assert error not in warning
    html = Path(app.outdir, "index.html").read_text()
    assert "SKIPPED" not in html


@pytest.mark.parametrize(
    "test_app",
    [
        _project(
            "Para.\n\n.. when:: True\n\n   SKIPPED_STRAY\n",
            conf=_CONF + "suppress_warnings = ['needs.choose']\n",
        )
    ],
    indirect=True,
)
def test_choose_warnings_are_suppressible(test_app):
    """Every warning of the three directives is of the ``needs.choose`` type."""
    app = test_app
    app.build()
    assert_no_warnings(app)
    assert "SKIPPED" not in Path(app.outdir, "index.html").read_text()


@pytest.mark.parametrize(
    "test_app",
    [
        _project(
            ".. req:: Written before the choose\n   :id: REQ_BEFORE\n\n"
            ".. choose::\n\n"
            "   .. req:: Directly in the choose body\n      :id: REQ_STRAY\n\n"
            "   .. otherwise::\n\n      SKIPPED_DEFAULT\n\n"
            ".. req:: Written after the choose\n   :id: REQ_AFTER\n",
            # read before `index`, so its need is older than every need of `index`
            extra=(
                (
                    "aaa.rst",
                    ":orphan:\n\nEarlier\n=======\n\n"
                    ".. req:: In an earlier document\n   :id: REQ_EARLIER\n",
                ),
            ),
        )
    ],
    indirect=True,
)
def test_choose_body_stray_need_never_runs(test_app):
    """A need written directly in the body is refused before it is created.

    Nothing in the body runs, so there is nothing to undo: the needs written before
    the ``choose``, in its own document and in an earlier one, and after it are all
    there, and the stray one never existed.
    """
    app = test_app
    app.build()
    (warning,) = build_warnings(app)
    source = Path(app.srcdir, "index.rst").read_text()
    line = _line_of(source, "   .. req:: Directly in the choose body")
    assert warning.startswith(f"<srcdir>/index.rst:{line}: WARNING: "), warning
    assert _stray(".. req:: Directly in the choose body") in warning
    needs = SphinxNeedsData(app.env).get_needs_view()
    assert sorted(needs) == ["REQ_AFTER", "REQ_BEFORE", "REQ_EARLIER"]


_SWALLOW_CONF = (
    _CONF
    + """
from docutils import nodes
from sphinx.util.docutils import SphinxDirective


class Swallow(SphinxDirective):
    has_content = True

    def run(self):
        node = nodes.container()
        try:
            self.state.nested_parse(self.content, self.content_offset, node)
        except RuntimeError:
            return [nodes.paragraph(text="SWALLOWED")]
        return [node]


def setup(app):
    app.add_directive("swallow", Swallow)
"""
)


@pytest.mark.parametrize(
    "test_app",
    [
        _project(
            ".. swallow::\n\n"
            "   .. choose::\n\n"
            "      .. otherwise::\n\n         SKIPPED_X\n\n"
            ".. when:: True\n\n   SKIPPED_LOOSE_AFTER\n",
            conf=_SWALLOW_CONF,
        )
    ],
    indirect=True,
)
def test_choose_restores_its_depth_when_its_body_raises(test_app, monkeypatch):
    """An exception out of a ``choose`` body leaves no ``choose`` open behind it.

    Only the branch directives run while the body is parsed, so the exception is
    made to come from one: the ``otherwise`` raises, and a directive of the project
    catches it. The ``when`` after it is outside every ``choose`` and must still be
    reported, rather than collected as a placeholder that would reach the writer.
    """

    def boom(self):
        raise RuntimeError("boom")

    monkeypatch.setattr(OtherwiseDirective, "run", boom)
    app = test_app
    app.build()
    (warning,) = build_warnings(app)
    source = Path(app.srcdir, "index.rst").read_text()
    line = _line_of(source, ".. when:: True")
    assert warning.startswith(f"<srcdir>/index.rst:{line}: WARNING: "), warning
    assert "'when' directive outside a 'choose'" in warning
    html = Path(app.outdir, "index.html").read_text()
    assert "SWALLOWED" in html
    assert "SKIPPED" not in html


_TAB_PARENT = "The parent of a 'tab-item' should be a 'tab-set'"


@pytest.mark.parametrize(
    "test_app",
    [
        _project(
            ".. tab-set::\n\n"
            "   .. if:: var.debug\n\n"
            "      .. tab-item:: IF_TAB\n\n         TAKEN_IF_TAB_BODY\n\n"
            ".. tab-set::\n\n"
            "   .. choose::\n\n"
            "      .. when:: var.debug\n\n"
            "         .. tab-item:: WHEN_TAB\n\n            TAKEN_WHEN_TAB_BODY\n\n"
            "      .. otherwise::\n\n         SKIPPED_TAB\n\n"
            ".. tab-set::\n\n"
            "   .. tab-item:: CHOOSE_INSIDE_TAB\n\n"
            "      .. choose::\n\n"
            "         .. when:: var.debug\n\n            TAKEN_INSIDE_TAB\n",
            conf=_CONF.replace(
                "extensions = ['sphinx_needs']",
                "extensions = ['sphinx_needs', 'sphinx_design']",
            ),
        )
    ],
    indirect=True,
)
def test_tab_item_in_the_taken_when_warns_as_in_a_true_if(test_app):
    """A ``tab-item`` in the taken branch warns exactly as one in a true ``if`` does.

    The content of the taken branch, like the body of a true ``if``, is parsed into
    a detached container, so sphinx-design's ``tab-item`` does not see the
    ``tab-set`` around the directive and warns about its parent. This pins the
    limitation the docs of both directives describe, with the same warning for both,
    and the remedy they give: a ``choose`` inside the ``tab-item`` does not warn.
    """
    # no skip: sphinx-design is in the shared `test` group, and if it ever leaves it,
    # this test must fail rather than stop pinning the documented limitation
    import sphinx_design  # noqa: F401

    app = test_app
    app.build()
    warnings = build_warnings(app)
    assert len(warnings) == 2, warnings
    source = Path(app.srcdir, "index.rst").read_text()
    if_warning, when_warning = warnings
    assert if_warning.startswith(
        f"<srcdir>/index.rst:{_line_of(source, '      .. tab-item:: IF_TAB')}: WARNING: "
    ), if_warning
    assert when_warning.startswith(
        f"<srcdir>/index.rst:{_line_of(source, '         .. tab-item:: WHEN_TAB')}: "
        "WARNING: "
    ), when_warning
    assert _TAB_PARENT in if_warning, if_warning
    assert (
        if_warning.split(": WARNING: ", 1)[1] == when_warning.split(": WARNING: ", 1)[1]
    )
    html = Path(app.outdir, "index.html").read_text()
    for word in ("TAKEN_IF_TAB_BODY", "TAKEN_WHEN_TAB_BODY", "TAKEN_INSIDE_TAB"):
        assert word in html, word
    assert "SKIPPED" not in html
    _assert_no_choose_nodes(app)


# One condition language: `when` evaluates exactly what `if` does

_EXPRESSIONS = {
    # expression: whether it is true (None: it cannot be evaluated)
    "var.arch == 'abc'": True,
    "var.arch == 'xyz'": False,
    "var.debug": True,
    "not var.debug": False,
    "var.count > 10": False,
    "'f1' in var.build.features": True,
    "var.count": True,
    "var.tags": True,
    '""': False,
    "var.no_such_key == 1": None,
    "var.build.no_such_key": None,
    "invalid syntax !!!": None,
    "__import__('os').system('echo pwned')": None,
    "1 / 0": None,
}
#: the expressions whose value is not a bool, which warn and are then used
_NON_BOOL = {"var.count", "var.tags", '""'}


def _strip_location_and_type(warning: str) -> str:
    """The message of a warning record, without its location and its type."""
    message = warning.split(": WARNING: ", 1)[1]
    return message.rsplit(" [needs.", 1)[0]


@pytest.mark.parametrize(
    ("test_app", "expression", "verdict"),
    [
        (
            _project(
                f".. if:: {expression}\n\n   IF_TAKEN\n\n"
                ".. choose::\n\n"
                f"   .. when:: {expression}\n\n      WHEN_TAKEN\n"
            ),
            expression,
            verdict,
        )
        for expression, verdict in _EXPRESSIONS.items()
    ],
    ids=list(_EXPRESSIONS),
    indirect=["test_app"],
)
def test_when_conditions_are_if_conditions(test_app, expression: str, verdict):
    """``if`` and ``when`` give every condition the same verdict and the same warnings.

    Only the directive name and the warning type differ,
    because both directives go through one evaluator.
    """
    app = test_app
    app.build()
    html = Path(app.outdir, "index.html").read_text()
    assert ("IF_TAKEN" in html) is bool(verdict)
    assert ("WHEN_TAKEN" in html) is bool(verdict)

    warnings = build_warnings(app)
    if_warnings = [w for w in warnings if w.endswith(" [needs.if]")]
    when_warnings = [w for w in warnings if w.endswith(" [needs.choose]")]
    assert len(if_warnings) + len(when_warnings) == len(warnings), warnings
    assert len(if_warnings) == len(when_warnings), warnings
    # an unevaluable condition warns, and so does a result that is not a bool
    assert bool(if_warnings) is (verdict is None or expression in _NON_BOOL)
    source = Path(app.srcdir, "index.rst").read_text()
    for if_warning, when_warning in zip(if_warnings, when_warnings, strict=True):
        assert if_warning.startswith(
            f"<srcdir>/index.rst:{_line_of(source, f'.. if:: {expression}')}: "
        ), if_warning
        assert when_warning.startswith(
            f"<srcdir>/index.rst:{_line_of(source, f'   .. when:: {expression}')}: "
        ), when_warning
        assert _strip_location_and_type(if_warning).startswith("'if' directive ")
        assert _strip_location_and_type(when_warning) == _strip_location_and_type(
            if_warning
        ).replace("'if' directive ", "'when' directive ", 1)


# MyST Markdown

_MYST_HAPPY = """\
```{toctree}
other
```

## Colon fences

::::{choose}
:::{when} var.arch == "abc"
TAKEN_M1_FIRST
:::
:::{when} var.debug
SKIPPED_M1_SECOND_TRUE
:::
:::{when} this is not python !!!
SKIPPED_M1_INVALID_SYNTAX
:::
:::{otherwise}
SKIPPED_M1_DEFAULT
:::
::::

## Comments between branches

::::{choose}
:::{when} var.arch == "xyz"
SKIPPED_M2_FALSE
:::

% a MyST comment between two branches

+++

:::{otherwise}
TAKEN_M2_DEFAULT
:::
::::

## Backtick fences, and needs in branches

`````{choose}
````{when} var.arch == "xyz"
```{req} In a branch that is not taken
:id: REQ_M3_SKIPPED
```
````
````{when} var.arch == "abc"
TAKEN_M3

```{req} In the taken branch
:id: REQ_M3_TAKEN
```
````
`````

## A section in the taken branch

::::{choose}
:::{when} var.debug
### M4 conditional heading

TAKEN_M4_SECTION_BODY
:::
::::

## Nested choose, one more fence character per level

::::::{choose}
:::::{when} var.debug
TAKEN_M5_OUTER

::::{choose}
:::{when} var.arch == "xyz"
SKIPPED_M5_INNER
:::
:::{otherwise}
TAKEN_M5_INNER_DEFAULT
:::
::::
:::::
:::::{otherwise}
SKIPPED_M5_OUTER
:::::
::::::

## An otherwise whose fence line ends in spaces has no condition

::::{choose}
:::{when} False
SKIPPED_M6
:::
:::{otherwise}\x20\x20\x20
TAKEN_M6_DEFAULT
:::
::::

## Choose in the content of a need

:::::{req} Host with choose content
:id: REQ_M_HOST

::::{choose}
:::{when} var.arch == "xyz"
SKIPPED_M7_IN_NEED
:::
:::{when} var.arch == "abc"
TAKEN_M7_IN_NEED
:::
::::
:::::

## A whole choose in an included file

```{include} included_choose.txt
```
"""

_MYST_INCLUDED_CHOOSE = """\
::::{choose}
:::{when} var.arch == "xyz"
SKIPPED_M8_IN_INCLUDED_CHOOSE
:::
:::{otherwise}
TAKEN_M8_INCLUDED_CHOOSE_DEFAULT
:::
::::
"""


@pytest.mark.skipif(not _HAS_MYST, reason="needs myst-parser")
@pytest.mark.parametrize(
    "test_app",
    [
        _project(
            _MYST_HAPPY,
            conf=_CONF_MYST,
            myst=True,
            other="# Other\n\n```{needextract}\n:filter: id == 'REQ_M_HOST'\n```\n",
            extra=(("included_choose.txt", _MYST_INCLUDED_CHOOSE),),
        )
    ],
    indirect=True,
)
def test_choose_in_myst(test_app):
    """Colon and backtick fences, comments, needs, sections, nesting, needextract."""
    app = test_app
    app.build()
    assert_no_warnings(app)

    html = Path(app.outdir, "index.html").read_text()
    taken = [
        "TAKEN_M1_FIRST",
        "TAKEN_M2_DEFAULT",
        "TAKEN_M3",
        "TAKEN_M4_SECTION_BODY",
        "TAKEN_M5_OUTER",
        "TAKEN_M5_INNER_DEFAULT",
        "TAKEN_M6_DEFAULT",
        "TAKEN_M7_IN_NEED",
        "TAKEN_M8_INCLUDED_CHOOSE_DEFAULT",
    ]
    assert [word for word in taken if word not in html] == []
    assert "SKIPPED_" not in html

    needs = SphinxNeedsData(app.env).get_needs_view()
    assert sorted(needs) == ["REQ_M3_TAKEN", "REQ_M_HOST"]
    # MyST gives a directive a content offset relative to its own line, which the
    # choose re-bases for the branch it takes: the need knows its true line
    source = Path(app.srcdir, "index.md").read_text()
    assert needs["REQ_M3_TAKEN"]["lineno"] == _line_of(
        source, "```{req} In the taken branch"
    )

    assert [
        "Test",
        "A section in the taken branch",
        "M4 conditional heading",
    ] in _section_titles(app, "index")

    other = Path(app.outdir, "other.html").read_text()
    assert "TAKEN_M7_IN_NEED" in other
    assert "SKIPPED_" not in other

    _assert_no_choose_nodes(app)


# MyST reports a directive nested in a colon fence one line late (its own quirk, the
# same for a `{note}` in a `{note}`), so only the backtick spellings assert a line
_MYST_WARNINGS = {
    "when outside a choose, backticks": (
        "Para.\n\n```{when} True\nSKIPPED_STRAY\n```\n",
        "'when' directive outside a 'choose'",
        "```{when} True",
    ),
    "otherwise outside a choose, backticks": (
        "Para.\n\n```{otherwise}\nSKIPPED_STRAY_DEFAULT\n```\n",
        "'otherwise' directive outside a 'choose' (an 'otherwise' must be a direct "
        "child of a 'choose'); its content is skipped",
        "```{otherwise}",
    ),
    "when outside a choose, colons": (
        "Para.\n\n:::{when} True\nSKIPPED_STRAY\n:::\n",
        "'when' directive outside a 'choose'",
        None,
    ),
    "branch loose in the taken branch, backticks": (
        "`````{choose}\n````{when} True\nTAKEN_OUTER\n\n"
        "```{when} True\nSKIPPED_LOOSE\n```\n````\n`````\n",
        "'when' directive outside a 'choose'",
        "```{when} True",
    ),
    "paragraph in the body, backticks": (
        "````{choose}\n```{when} True\nSKIPPED\n```\n\nA stray paragraph.\n````\n",
        _stray("A stray paragraph."),
        "A stray paragraph.",
    ),
    "paragraph in the body, colons": (
        "::::{choose}\n:::{when} True\nSKIPPED\n:::\n\nA stray paragraph.\n::::\n",
        _stray("A stray paragraph."),
        None,
    ),
    # an HTML comment is raw HTML, not a comment
    "html comment between branches, backticks": (
        "````{choose}\n```{when} False\nSKIPPED\n```\n\n<!-- an HTML comment -->\n\n"
        "```{otherwise}\nSKIPPED_DEFAULT\n```\n````\n",
        _stray("<!-- an HTML comment -->"),
        "<!-- an HTML comment -->",
    ),
    "html comment between branches, colons": (
        "::::{choose}\n:::{when} False\nSKIPPED\n:::\n\n<!-- an HTML comment -->\n\n"
        ":::{otherwise}\nSKIPPED_DEFAULT\n:::\n::::\n",
        _stray("<!-- an HTML comment -->"),
        None,
    ),
    "choose with an argument, backticks": (
        "````{choose} var.arch\n```{when} True\nSKIPPED\n```\n````\n",
        "'choose' directive takes no argument, got 'var.arch'",
        "````{choose} var.arch",
    ),
    "choose with an argument, colons": (
        "::::{choose} var.arch\n:::{when} True\nSKIPPED\n:::\n::::\n",
        "'choose' directive takes no argument, got 'var.arch'",
        None,
    ),
    "when without a condition, backticks": (
        "````{choose}\n```{when} var.arch == 'xyz'\nSKIPPED_XYZ\n```\n"
        "```{when}\nSKIPPED_FORGOTTEN_CONDITION\n```\n````\n",
        "'when' directive has no condition (use 'otherwise' for the default)" + _SKIP,
        "```{when}",
    ),
    # a fence line that ends in spaces gives a blank condition, which is none
    "when with a blank condition, colons": (
        "::::{choose}\n:::{when} var.arch == 'xyz'\nSKIPPED_XYZ\n:::\n"
        ":::{when}\x20\x20\x20\nSKIPPED_BLANK_CONDITION\n:::\n::::\n",
        "'when' directive has no condition (use 'otherwise' for the default)" + _SKIP,
        None,
    ),
    # MyST would fold the text into the content of a directive without an argument
    "otherwise with a condition, backticks": (
        "````{choose}\n```{when} var.arch == 'xyz'\nSKIPPED_XYZ\n```\n"
        "```{otherwise} var.debug\nSKIPPED_OTHERWISE\n```\n````\n",
        "'otherwise' directive takes no condition, got 'var.debug'" + _SKIP,
        "```{otherwise} var.debug",
    ),
    # the check order, as in reStructuredText
    "two otherwise, then a when without a condition, backticks": (
        "````{choose}\n```{otherwise}\nSKIPPED_D1\n```\n```{otherwise}\nSKIPPED_D2\n```\n"
        "```{when}\nSKIPPED_FORGOTTEN_CONDITION\n```\n````\n",
        "'when' directive has no condition (use 'otherwise' for the default)" + _SKIP,
        "```{when}",
    ),
    "an otherwise with a condition, a when, then a bare otherwise, backticks": (
        "````{choose}\n```{otherwise} var.debug\nSKIPPED_FIRST\n```\n"
        "```{when} var.arch == 'abc'\nSKIPPED_ABC\n```\n"
        "```{otherwise}\nSKIPPED_LAST\n```\n````\n",
        "'otherwise' directive takes no condition, got 'var.debug'" + _SKIP,
        "```{otherwise} var.debug",
    ),
    "an otherwise with a condition, then a when without one, backticks": (
        "````{choose}\n```{otherwise} var.debug\nSKIPPED_FIRST\n```\n"
        "```{when}\nSKIPPED_FORGOTTEN_CONDITION\n```\n````\n",
        "'otherwise' directive takes no condition, got 'var.debug'" + _SKIP,
        "```{otherwise} var.debug",
    ),
    "unevaluable condition, backticks": (
        "````{choose}\n```{when} invalid !!!\nSKIPPED\n```\n"
        "```{otherwise}\nSKIPPED_DEFAULT\n```\n````\n",
        "'when' directive expression failed: 'invalid !!!'",
        "```{when} invalid !!!",
    ),
    "unevaluable condition, colons": (
        "::::{choose}\n:::{when} invalid !!!\nSKIPPED\n:::\n"
        ":::{otherwise}\nSKIPPED_DEFAULT\n:::\n::::\n",
        "'when' directive expression failed: 'invalid !!!'",
        None,
    ),
    # a `%` line is a comment in MyST, under the same rule; the hint names the fence
    "when with one colon, % comment": (
        "````{choose}\n% when: var.arch == 'abc'\n"
        "```{otherwise}\nSKIPPED_OTHERWISE\n```\n````\n",
        _WHEN_LIKE_MYST,
        "% when: var.arch == 'abc'",
    ),
    "otherwise with one colon, % comment": (
        "````{choose}\n```{when} var.arch == 'xyz'\nSKIPPED_XYZ\n```\n"
        "% otherwise:\n````\n",
        _OTHERWISE_LIKE_MYST,
        "% otherwise:",
    ),
    # the control: accepted, and its branch is taken (no warning)
    "a % comment that starts with the word when": (
        "````{choose}\n% when we migrate, drop this\n"
        "```{when} var.arch == 'abc'\nTAKEN_AFTER_WORD_COMMENT\n```\n"
        "```{otherwise}\nSKIPPED_OTHERWISE\n```\n````\n",
        None,
        None,
    ),
    # an `{eval-rst}` block is a fence of another directive: refused at its line
    "branch inside eval-rst, backticks": (
        "````{choose}\n```{eval-rst}\n.. when:: True\n\n   SKIPPED_FROM_EVAL_RST\n```\n"
        "````\n",
        _stray("```{eval-rst}"),
        "```{eval-rst}",
    ),
    "branch inside eval-rst, colons": (
        "::::{choose}\n```{eval-rst}\n.. when:: True\n\n   SKIPPED_FROM_EVAL_RST\n```\n"
        "::::\n",
        _stray("```{eval-rst}"),
        None,
    ),
    # an opener indented four spaces is a code block: refused, named with its indentation
    "an opener indented four spaces": (
        "````{choose}\n    :::{when} var.debug\nSKIPPED\n:::\n````\n",
        _stray("    :::{when} var.debug"),
        "    :::{when} var.debug",
    ),
    # MyST takes the first word of the info string as the directive: with no space
    # after the braces it is no directive, so no branch
    "a branch fence without a space after the name": (
        "````{choose}\n```{when}True\nSKIPPED\n```\n````\n",
        _stray("```{when}True"),
        "```{when}True",
    ),
}


@pytest.mark.skipif(not _HAS_MYST, reason="needs myst-parser")
@pytest.mark.parametrize(
    ("test_app", "text", "line"),
    [
        (_project(body, conf=_CONF_MYST, myst=True), text, line)
        for body, text, line in _MYST_WARNINGS.values()
    ],
    ids=list(_MYST_WARNINGS),
    indirect=["test_app"],
)
def test_choose_warnings_in_myst(
    test_app, text: str | None, line: str | None, monkeypatch
):
    """The MyST spellings warn once each and fail closed, as in reStructuredText.

    A row without a text is a control: it gives no warning, and its branch is taken.
    Built from the source directory, as the reStructuredText rows are.
    """
    app = test_app
    monkeypatch.chdir(app.srcdir)
    app.build()
    if text is None:
        assert build_warnings(app) == []
        html = Path(app.outdir, "index.html").read_text()
        assert "TAKEN_" in html
        assert "SKIPPED" not in html
        _assert_no_choose_nodes(app)
        return
    (warning,) = build_warnings(app)
    assert text in warning, warning
    assert warning.endswith(" [needs.choose]"), warning
    if line is not None:
        source = Path(app.srcdir, "index.md").read_text()
        assert warning.startswith(
            f"<srcdir>/index.md:{_line_of(source, line)}: WARNING: "
        ), warning
    assert "SKIPPED" not in Path(app.outdir, "index.html").read_text()
    _assert_no_choose_nodes(app)


@pytest.mark.skipif(not _HAS_MYST, reason="needs myst-parser")
@pytest.mark.parametrize(
    "test_app",
    [
        _project(
            "::::{choose}\n:::{when} True\nSKIPPED_IN_PLACE\n:::\n\n"
            "```{include} branches.txt\n```\n::::\n",
            conf=_CONF_MYST,
            myst=True,
            extra=(
                (
                    "branches.txt",
                    ':::{when} var.arch == "xyz"\nSKIPPED_X1_FROM_INCLUDE\n:::\n'
                    ":::{otherwise}\nSKIPPED_X1_DEFAULT_FROM_INCLUDE\n:::\n",
                ),
            ),
        )
    ],
    indirect=True,
)
def test_choose_refuses_included_branches_in_myst(test_app):
    """In MyST too, an ``{include}`` in the body is refused at its line, in the host.

    The included file is never read.
    """
    app = test_app
    app.build()
    (warning,) = build_warnings(app)
    source = Path(app.srcdir, "index.md").read_text()
    line = _line_of(source, "```{include} branches.txt")
    assert warning.startswith(f"<srcdir>/index.md:{line}: WARNING: "), warning
    assert _stray("```{include} branches.txt") in warning, warning
    assert warning.endswith(" [needs.choose]"), warning
    assert "SKIPPED" not in Path(app.outdir, "index.html").read_text()
    _assert_no_choose_nodes(app)


@pytest.mark.skipif(not _HAS_MYST, reason="needs myst-parser")
@pytest.mark.parametrize(
    "test_app",
    [
        _project(
            "````{choose}\n{{ branches }}\n```{otherwise}\nSKIPPED_OTHERWISE\n```\n````\n",
            conf=_CONF_MYST.replace(
                "['colon_fence']", "['colon_fence', 'substitution']"
            )
            + "myst_substitutions = {'branches': "
            "':::{when} True\\nSKIPPED_FROM_SUBSTITUTION\\n:::'}\n",
            myst=True,
        )
    ],
    indirect=True,
)
def test_choose_refuses_a_substitution_in_myst(test_app):
    """A substitution reference in the body is a line of text to the ``choose``.

    It is refused at its line, so the branches its definition holds are never taken,
    and neither is the ``otherwise``.
    """
    app = test_app
    app.build()
    (warning,) = build_warnings(app)
    source = Path(app.srcdir, "index.md").read_text()
    line = _line_of(source, "{{ branches }}")
    assert warning.startswith(f"<srcdir>/index.md:{line}: WARNING: "), warning
    assert _stray("{{ branches }}") in warning, warning
    assert "SKIPPED" not in Path(app.outdir, "index.html").read_text()
    _assert_no_choose_nodes(app)


_HOST_NEED = "```{req} Host\n:id: REQ_HOST\n:status: open\n```\n\n"


@pytest.mark.skipif(not _HAS_MYST, reason="needs myst-parser")
@pytest.mark.parametrize(
    "test_app",
    [
        _project(
            _HOST_NEED + "::::{choose}\n:::{when} var.debug | var.debug\n|---|---|\n\n"
            "(leak-label-table)=\n"
            "```{req} Smuggled by a table\n:id: REQ_SMUGGLED_TABLE\n```\n\n"
            "```{needextend} REQ_HOST\n:status: LEAKED_BY_TABLE\n```\n:::\n::::\n",
            conf=_CONF_MYST,
            myst=True,
        )
    ],
    indirect=True,
)
def test_choose_refuses_an_opener_a_table_swallows_in_myst(test_app):
    """An opener with a ``|`` and a delimiter row under it is a table to markdown-it.

    markdown-it tries its ``table`` rule before any fence, so the lines after the
    would-be opener are parsed in the body: the opener is refused instead, and the
    need and the ``needextend`` under it never run.
    """
    app = test_app
    app.build()
    (warning,) = build_warnings(app)
    source = Path(app.srcdir, "index.md").read_text()
    line = _line_of(source, ":::{when} var.debug | var.debug")
    assert warning.startswith(f"<srcdir>/index.md:{line}: WARNING: "), warning
    assert _stray(":::{when} var.debug | var.debug") in warning, warning
    needs = SphinxNeedsData(app.env).get_needs_view()
    assert sorted(needs) == ["REQ_HOST"]
    assert needs["REQ_HOST"]["status"] == "open"
    _assert_no_choose_nodes(app)


def _front_matter_project(front_matter: str, body: str, /) -> dict[str, object]:
    """A MyST project whose root document starts with ``front_matter`` (YAML)."""
    text = f"---\n{front_matter}---\n# Test\n\n{body}"
    return {
        "buildername": "html",
        "files": [(Path("conf.py"), _CONF_MYST), (Path("index.md"), text)],
    }


_V6D_BODY = (
    "::::{choose}\n% a comment, a paragraph here\n"
    ":::{otherwise}\nSKIPPED_OTHERWISE\n:::\n::::\n\n"
    "::::{choose}\n+++\n:::{otherwise}\nTAKEN_BREAK_STILL_A_COMMENT\n:::\n::::\n"
)


@pytest.mark.skipif(not _HAS_MYST, reason="needs myst-parser")
@pytest.mark.parametrize(
    ("test_app", "stray", "taken"),
    [
        (
            # the front matter replaces the global extensions: no colons
            _front_matter_project(
                'myst:\n  enable_extensions: ["substitution"]\n',
                "`````{choose}\n:::{when} True\n"
                "```{req} Smuggled by front matter\n:id: REQ_SMUGGLED\n```\n"
                ":::\n`````\n",
            ),
            ":::{when} True",
            (),
        ),
        (
            _project(
                "::::{choose}\n```{when} True\n"
                ":::{req} Smuggled by disable_syntax\n:id: REQ_SMUGGLED\n:::\n"
                "```\n::::\n",
                conf=_CONF_MYST + "myst_disable_syntax = ['fence']\n",
                myst=True,
            ),
            "```{when} True",
            (),
        ),
        (
            # the front matter disables fences, conf.py does not
            _front_matter_project(
                'myst:\n  disable_syntax: ["fence"]\n',
                "::::{choose}\n```{when} True\n"
                ":::{req} Smuggled by the front matter\n:id: REQ_SMUGGLED\n:::\n"
                "```\n::::\n",
            ),
            "```{when} True",
            (),
        ),
        (
            # a backtick branch in the same file is still taken
            _project(
                "````{choose}\n:::{when} True\n"
                "```{req} Smuggled by disable_syntax\n:id: REQ_SMUGGLED\n```\n"
                ":::\n````\n\n"
                "````{choose}\n```{when} var.debug\nTAKEN_BACKTICK\n```\n````\n",
                conf=_CONF_MYST + "myst_disable_syntax = ['colon_fence']\n",
                myst=True,
            ),
            ":::{when} True",
            ("TAKEN_BACKTICK",),
        ),
        (
            # the `%` line is a paragraph; the block break is still a comment
            _project(
                _V6D_BODY,
                conf=_CONF_MYST + "myst_disable_syntax = ['myst_line_comment']\n",
                myst=True,
            ),
            "% a comment, a paragraph here",
            ("TAKEN_BREAK_STILL_A_COMMENT",),
        ),
        (
            _front_matter_project(
                'myst:\n  disable_syntax: ["myst_line_comment"]\n', _V6D_BODY
            ),
            "% a comment, a paragraph here",
            ("TAKEN_BREAK_STILL_A_COMMENT",),
        ),
        (
            # the `+++` line is a paragraph; the `%` line is still a comment
            _project(
                "::::{choose}\n+++\n:::{otherwise}\nSKIPPED_OTHERWISE\n:::\n::::\n\n"
                "::::{choose}\n% still a comment\n"
                ":::{otherwise}\nTAKEN_COMMENT_STILL_A_COMMENT\n:::\n::::\n",
                conf=_CONF_MYST + "myst_disable_syntax = ['myst_block_break']\n",
                myst=True,
            ),
            "+++",
            ("TAKEN_COMMENT_STILL_A_COMMENT",),
        ),
    ],
    ids=[
        "colon fences off in the front matter",
        "fences disabled",
        "fences disabled in the front matter",
        "colon fences disabled",
        "line comments disabled",
        "line comments disabled in the front matter",
        "block breaks disabled",
    ],
    indirect=["test_app"],
)
def test_choose_reads_the_documents_myst_config(
    test_app, stray: str, taken: tuple[str, ...]
):
    """A branch, a comment or a block break counts only if the document's parser has it.

    The document's configuration is the global one merged with its front matter
    (whose ``enable_extensions`` replaces the global list), and ``disable_syntax``
    can switch a fence kind, line comments or block breaks off: such a line is a
    stray, so a need under an opener the parser does not have, which the parser
    would run, never exists; the rest of the file is read as usual.
    """
    app = test_app
    app.build()
    (warning,) = build_warnings(app)
    source = Path(app.srcdir, "index.md").read_text()
    assert warning.startswith(
        f"<srcdir>/index.md:{_line_of(source, stray)}: WARNING: "
    ), warning
    assert _stray(stray) in warning, warning
    assert sorted(SphinxNeedsData(app.env).get_needs_view()) == []
    html = Path(app.outdir, "index.html").read_text()
    assert [word for word in taken if word not in html] == []
    assert "SKIPPED" not in html
    _assert_no_choose_nodes(app)


_C1_CLOSER = (
    "::::{choose}\n:::{when} False\nSKIPPED_WHEN\n    :::\n"
    "```{req} Smuggled past a closer\n:id: REQ_SMUGGLED_CLOSER\n```\n"
    "```{needextend} REQ_HOST\n:status: LEAKED_BY_CLOSER\n```\n:::\n::::\n\n"
)
_C1_TABLE = (
    "::::{choose}\n:::{when} var.debug | var.debug\n    |---|---|\n\n"
    "```{req} Smuggled past an indented delimiter row\n:id: REQ_SMUGGLED_TABLE\n```\n"
    ":::\n::::\n"
)


@pytest.mark.skipif(not _HAS_MYST, reason="needs myst-parser")
@pytest.mark.parametrize(
    ("test_app", "strays"),
    [
        (
            _project(
                _HOST_NEED + _C1_CLOSER + _C1_TABLE,
                conf=_CONF_MYST + "myst_disable_syntax = ['code']\n",
                myst=True,
            ),
            (
                "```{req} Smuggled past a closer",
                ":::{when} var.debug | var.debug",
            ),
        ),
        (
            _front_matter_project(
                'myst:\n  disable_syntax: ["code"]\n', _HOST_NEED + _C1_CLOSER
            ),
            ("```{req} Smuggled past a closer",),
        ),
    ],
    ids=["the code rule disabled", "the code rule disabled in the front matter"],
    indirect=["test_app"],
)
def test_choose_without_the_code_rule_in_myst(test_app, strays: tuple[str, ...]):
    """Without markdown-it's ``code`` rule, indentation bounds no construct.

    A closer indented four spaces then closes the branch, so the fence after it is
    a stray of the body; a delimiter row indented four spaces makes the opener above
    it a table header. Nothing under either runs: the host need keeps its status.
    """
    app = test_app
    app.build()
    warnings = build_warnings(app)
    assert len(warnings) == len(strays), warnings
    source = Path(app.srcdir, "index.md").read_text()
    for warning, stray in zip(warnings, strays, strict=True):
        assert warning.startswith(
            f"<srcdir>/index.md:{_line_of(source, stray)}: WARNING: "
        ), warning
        assert _stray(stray) in warning, warning
    needs = SphinxNeedsData(app.env).get_needs_view()
    assert sorted(needs) == ["REQ_HOST"]
    assert needs["REQ_HOST"]["status"] == "open"
    assert "SKIPPED" not in Path(app.outdir, "index.html").read_text()
    _assert_no_choose_nodes(app)


@pytest.mark.skipif(not _HAS_MYST, reason="needs myst-parser")
@pytest.mark.parametrize(
    "test_app",
    [
        _project(
            "::::{choose}\n~~~{when} var.debug\nTAKEN_TILDE\n~~~\n::::\n\n"
            "::::{choose}\n  % an indented comment\n"
            ":::{otherwise}\nTAKEN_INDENTED_COMMENT\n:::\n::::\n\n"
            "::::{choose}\n+ + +\n:::{otherwise}\nTAKEN_SPACED_BREAK\n:::\n::::\n\n"
            "::::{choose}\n +++\n:::{otherwise}\nTAKEN_INDENTED_BREAK\n:::\n::::\n",
            conf=_CONF_MYST,
            myst=True,
        )
    ],
    indirect=True,
)
def test_choose_accepts_the_myst_spellings_myst_accepts(test_app):
    """A tilde branch, an indented ``%`` comment and indented or spaced block breaks."""
    app = test_app
    app.build()
    assert_no_warnings(app)
    html = Path(app.outdir, "index.html").read_text()
    taken = ["TAKEN_TILDE", "TAKEN_INDENTED_COMMENT", "TAKEN_SPACED_BREAK"]
    taken.append("TAKEN_INDENTED_BREAK")
    assert [word for word in taken if word not in html] == []
    _assert_no_choose_nodes(app)


@pytest.mark.parametrize(
    "test_app",
    [
        _project(
            ".. choose::\n\n"
            "   .. req:: Stray need\n      :id: REQ_UNGATED\n\n"
            "   .. otherwise::\n\n      SKIPPED_OTHERWISE\n"
        )
    ],
    indirect=True,
)
def test_choose_fails_closed_under_another_parser(test_app, monkeypatch):
    """Under a parser the gate cannot read, the ``choose`` is refused unread."""
    monkeypatch.setattr(ChooseDirective, "_syntax", lambda self: None)
    app = test_app
    app.build()
    (warning,) = build_warnings(app)
    source = Path(app.srcdir, "index.rst").read_text()
    assert warning.startswith(
        f"<srcdir>/index.rst:{_line_of(source, '.. choose::')}: WARNING: "
    ), warning
    assert (
        "'choose' directive is supported under reStructuredText and MyST only" + _SKIP
        in warning
    ), warning
    assert "SKIPPED" not in Path(app.outdir, "index.html").read_text()
    assert sorted(SphinxNeedsData(app.env).get_needs_view()) == []


def test_absolute_location():
    """A ``<source>:<line>`` location is reported with an absolute source.

    docutils gives an included file a path relative to the working directory
    whenever the two share their first two path components (a checkout under
    ``/tmp`` with its builds under ``/tmp``), which would read ``../…`` in a warning.
    A node is left to Sphinx, which makes its source absolute itself.
    """
    relative = os.path.join("..", "x", "branches.txt")
    assert _absolute_location(f"{relative}:1") == f"{os.path.abspath(relative)}:1"
    absolute = os.path.abspath("index.rst")
    assert _absolute_location(f"{absolute}:7") == f"{absolute}:7"
    node = nodes.paragraph()
    assert _absolute_location(node) is node
