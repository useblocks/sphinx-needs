"""Tests for the ``.. match::`` and ``.. case::`` directives."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import NamedTuple

import pytest
from docutils import nodes

from sphinx_needs.data import SphinxNeedsData
from sphinx_needs.directives.needmatch import _CasePlaceholder, _MatchBody
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


def _assert_no_match_nodes(app) -> None:
    """Neither private node class reaches a pickled doctree or the need-node cache."""
    private = (_CasePlaceholder, _MatchBody)
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
    [{"buildername": "html", "srcdir": "doc_test/doc_match_directive"}],
    indirect=True,
)
def test_match_directive(test_app):
    """First true case wins, the default, needs, sections, nesting and includes.

    The project builds without a single warning,
    although a case after a taken one has a condition that is not Python
    and another names an unknown key: neither is ever evaluated.
    """
    app = test_app
    app.build()
    assert_no_warnings(app)

    html = Path(app.outdir, "index.html").read_text()
    taken = [
        "TAKEN_P1_FIRST",
        "TAKEN_P2_DEFAULT",
        "TAKEN_P2B_AFTER_MATCH",
        "TAKEN_P4_SECTION_BODY",
        "TAKEN_P5_OUTER",
        "TAKEN_P5_INNER_DEFAULT",
        "TAKEN_P5B_IN_NEED",
        "TAKEN_X1_INCLUDED_MATCH_DEFAULT",
        "TAKEN_X2_INCLUDED_TEXT",
        "TAKEN_X2_AFTER_INCLUDE",
        "TAKEN_X2_AFTER_MATCH",
    ]
    assert [word for word in taken if word not in html] == []
    # each taken case is rendered once
    assert [word for word in taken if html.count(f"<p>{word}</p>") != 1] == []
    assert "SKIPPED_" not in html

    # the needs of the cases that are not taken are never created
    needs = SphinxNeedsData(app.env).get_needs_view()
    assert sorted(needs) == ["REQ_HOST", "REQ_P3_TAKEN", "REQ_X2_INCLUDED"]
    # the need of the taken case knows the line it was written on
    source = Path(app.srcdir, "index.rst").read_text()
    assert needs["REQ_P3_TAKEN"]["lineno"] == _line_of(
        source, "      .. req:: In the taken case"
    )

    # a heading in the taken case is a section of the document, nested where it stands
    sections = _section_titles(app, "index")
    assert [
        "MATCH Test",
        "P4 sections in the taken case",
        "P4 conditional heading",
    ] in sections
    assert not [path for path in sections if "P4 skipped heading" in path]

    # the need with a match in its content is extracted on the other page
    other = Path(app.outdir, "other.html").read_text()
    assert "TAKEN_P5B_IN_NEED" in other
    assert "SKIPPED_" not in other

    _assert_no_match_nodes(app)


# Each mistake warns once, at the line that has it, and skips the whole match


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


_SKIP = "; the whole match is skipped"

_NOT_DIRECT = (
    "'case' directive is not a direct child of its 'match' (it is inside another "
    "directive)" + _SKIP
)
_INCLUDED_CASE = (
    "'case' supplied through an include is not supported "
    "(write the cases in the body of the 'match')" + _SKIP
)
_CASES_TXT = (
    '.. case:: var.arch == "xyz"\n\n   SKIPPED_X1_FROM_INCLUDE\n\n'
    ".. case::\n\n   SKIPPED_X1_DEFAULT_FROM_INCLUDE\n"
)

_WARNINGS = {
    "default not last": _Expected(
        ".. match::\n\n"
        "   .. case::\n\n      SKIPPED_DEFAULT\n\n"
        "   .. case:: True\n\n      SKIPPED_TRUE\n",
        (
            (
                "'match' directive has a default 'case' (a 'case' with no condition) "
                "that is not its last 'case'" + _SKIP,
                "   .. case::",
            ),
        ),
    ),
    "two defaults": _Expected(
        ".. match::\n\n"
        "   .. case:: False\n\n      SKIPPED_FALSE\n\n"
        "   .. case::\n\n      SKIPPED_D1\n\n"
        # the second default is refused (its directive line ends in spaces, which the
        # parser strips: it is a default like the first)
        "   .. case::  \n\n      SKIPPED_D2\n",
        (
            (
                "'match' directive has more than one default 'case' (a 'case' with "
                "no condition)" + _SKIP,
                "   .. case::  ",
            ),
        ),
    ),
    "paragraph in the body": _Expected(
        ".. match::\n\n"
        "   .. case:: True\n\n      SKIPPED_CASE\n\n"
        "   A stray paragraph.\n",
        (
            (
                "'match' directive may contain only 'case' directives and comments, "
                "got <paragraph>" + _SKIP,
                "   A stray paragraph.",
            ),
        ),
    ),
    # exactly one warning: the case inside the note is not a stray, it is in a match body
    "note wrapping a case": _Expected(
        ".. match::\n\n"
        "   .. note::\n\n      .. case:: True\n\n         SKIPPED_IN_NOTE\n",
        (("got <note>" + _SKIP, "   .. note::"),),
    ),
    # a directive that returns the nodes of its content (a true `if`, `rst-class`)
    # would hand its cases to the match: a case must be written directly in it
    "cases inside a true if": _Expected(
        ".. match::\n\n"
        "   .. if:: var.debug\n\n"
        "      .. case:: var.arch == 'x86'\n\n         SKIPPED_X86\n\n"
        "      .. case::\n\n         SKIPPED_DEFAULT_FROM_IF\n",
        ((_NOT_DIRECT, "      .. case:: var.arch == 'x86'"),),
    ),
    "case inside rst-class": _Expected(
        ".. match::\n\n"
        "   .. rst-class:: special\n\n"
        "      .. case:: var.arch == 'abc'\n\n         SKIPPED_FROM_RST_CLASS\n",
        ((_NOT_DIRECT, "      .. case:: var.arch == 'abc'"),),
    ),
    # a line of one to three punctuation characters makes docutils emit an INFO
    # message, which is never shown, before the paragraph: the paragraph is reported
    "rule line between cases": _Expected(
        ".. match::\n\n"
        "   .. case:: var.arch == 'x86'\n\n      SKIPPED_X86\n\n"
        "   ---\n\n"
        "   .. case::\n\n      SKIPPED_DEFAULT\n",
        (("got <paragraph>" + _SKIP, "   ---"),),
    ),
    "three dots in the body": _Expected(
        ".. match::\n\n   ...\n\n   .. case::\n\n      SKIPPED_DEFAULT\n",
        (("got <paragraph>" + _SKIP, "   ..."),),
    ),
    "case outside a match": _Expected(
        "Para.\n\n.. case:: True\n\n   SKIPPED_STRAY\n",
        (
            (
                "'case' directive outside a 'match' (a 'case' must be a direct child "
                "of a 'match'); its content is skipped",
                ".. case:: True",
            ),
        ),
    ),
    # the counterpart of an orphan `else`: a default case outside every match
    "default case outside a match": _Expected(
        "Para.\n\n.. case::\n\n   SKIPPED_STRAY_DEFAULT\n",
        (("'case' directive outside a 'match'", ".. case::"),),
    ),
    "case loose in the taken case": _Expected(
        ".. match::\n\n"
        "   .. case:: True\n\n      TAKEN_OUTER\n\n"
        "      .. case:: True\n\n         SKIPPED_LOOSE\n",
        (("'case' directive outside a 'match'", "      .. case:: True"),),
        taken=("TAKEN_OUTER",),
    ),
    # two independent mistakes, two warnings: a match written directly in another
    # match's body, whose taken case holds a loose case. The taken case is parsed
    # outside every match body, so the loose case is reported and cannot become a case
    # of the OUTER match, which then has none.
    "case loose in the taken case of a misplaced match": _Expected(
        ".. match::\n\n"
        "   .. match::\n\n"
        "      .. case:: True\n\n"
        "         .. case:: True\n\n            SKIPPED_LOOSE\n",
        (
            ("'case' directive outside a 'match'", "         .. case:: True"),
            ("'match' directive has no 'case'", ".. match::"),
        ),
    ),
    "unevaluable first case poisons the default": _Expected(
        ".. match::\n\n"
        "   .. case:: this is not python !!!\n\n      SKIPPED_1\n\n"
        "   .. case:: True\n\n      SKIPPED_2\n\n"
        "   .. case::\n\n      SKIPPED_DEFAULT\n",
        (
            (
                "'case' directive expression failed: 'this is not python !!!' — ",
                "   .. case:: this is not python !!!",
            ),
        ),
    ),
    "unknown key in a later case": _Expected(
        ".. match::\n\n"
        "   .. case:: var.arch == 'xyz'\n\n      SKIPPED_1\n\n"
        "   .. case:: var.no_such_key == 1\n\n      SKIPPED_2\n\n"
        "   .. case::\n\n      SKIPPED_DEFAULT\n",
        (
            (
                "'case' directive expression failed: 'var.no_such_key == 1' — "
                "Unknown variant key: var.no_such_key",
                "   .. case:: var.no_such_key == 1",
            ),
        ),
    ),
    "builtins blocked": _Expected(
        ".. match::\n\n"
        "   .. case:: __import__('os').system('echo pwned')\n\n      SKIPPED\n\n"
        "   .. case::\n\n      SKIPPED_DEFAULT\n",
        (
            (
                "'case' directive expression failed: "
                "\"__import__('os').system('echo pwned')\" — "
                "name '__import__' is not defined",
                "   .. case:: __import__('os').system('echo pwned')",
            ),
        ),
    ),
    "non-bool is coerced and taken": _Expected(
        ".. match::\n\n"
        "   .. case:: var.count\n\n      TAKEN_NONBOOL\n\n"
        "   .. case::\n\n      SKIPPED_DEFAULT\n",
        (
            (
                "'case' directive expression did not return a bool, got int: 5 "
                "(coercing to bool): 'var.count'",
                "   .. case:: var.count",
            ),
        ),
        taken=("TAKEN_NONBOOL",),
    ),
    "empty string condition": _Expected(
        '.. match::\n\n   .. case:: ""\n\n      SKIPPED_EMPTY\n\n'
        "   .. case::\n\n      TAKEN_DEFAULT\n",
        (
            (
                "'case' directive expression did not return a bool, got str: '' "
                "(coercing to bool): '\"\"'",
                '   .. case:: ""',
            ),
        ),
        taken=("TAKEN_DEFAULT",),
    ),
    "match with an argument": _Expected(
        ".. match:: var.arch\n\n   .. case:: True\n\n      SKIPPED\n",
        (
            (
                "'match' directive takes no argument, got 'var.arch' "
                "(write a condition on each 'case')" + _SKIP,
                ".. match:: var.arch",
            ),
        ),
    ),
    "empty match": _Expected(
        ".. match::\n\nTAKEN_AFTER_EMPTY\n",
        (("'match' directive has no 'case'", ".. match::"),),
        taken=("TAKEN_AFTER_EMPTY",),
    ),
    "only comments": _Expected(
        ".. match::\n\n   .. just a comment\n\n   .. and another\n",
        (("'match' directive has no 'case'", ".. match::"),),
    ),
    "variant data not configured": _Expected(
        ".. match::\n\n"
        "   .. case:: var.arch == 'abc'\n\n      SKIPPED_1\n\n"
        "   .. case::\n\n      SKIPPED_DEFAULT\n",
        (
            (
                "'match' directive used but needs_variant_data is not configured"
                + _SKIP,
                ".. match::",
            ),
        ),
        conf=_CONF_NO_VARIANT_DATA,
    ),
    # nothing is evaluated here, and still the match warns and renders nothing:
    # the "used but not configured" rule holds for every match
    "variant data not configured, only a default": _Expected(
        ".. match::\n\n   .. case::\n\n      SKIPPED_DEFAULT_ONLY\n",
        (
            (
                "'match' directive used but needs_variant_data is not configured"
                + _SKIP,
                ".. match::",
            ),
        ),
        conf=_CONF_NO_VARIANT_DATA,
    ),
    # the structure is checked before the configuration: a match that is wrong in both
    # ways gets the one structural warning, at the case, and its body is still parsed
    "variant data not configured, and a misplaced default": _Expected(
        ".. match::\n\n"
        "   .. case::\n\n      SKIPPED_DEFAULT\n\n"
        "   .. case:: var.arch == 'abc'\n\n      SKIPPED_ABC\n",
        (
            (
                "'match' directive has a default 'case' (a 'case' with no condition) "
                "that is not its last 'case'" + _SKIP,
                "   .. case::",
            ),
        ),
        conf=_CONF_NO_VARIANT_DATA,
    ),
    # the cases of a match are written in its body: an include may not supply them,
    # and the warning points at the case in the included file
    "cases from an include": _Expected(
        ".. match::\n\n   .. include:: cases.txt\n",
        ((_INCLUDED_CASE, '.. case:: var.arch == "xyz"'),),
        extra=(("cases.txt", _CASES_TXT),),
        located_in="cases.txt",
    ),
    # the structure is checked before any condition: a true case written in place
    # before the included ones is not taken either
    "a case from an include after a true case": _Expected(
        ".. match::\n\n"
        "   .. case:: True\n\n      SKIPPED_IN_PLACE\n\n"
        "   .. include:: cases.txt\n",
        ((_INCLUDED_CASE, '.. case:: var.arch == "xyz"'),),
        extra=(("cases.txt", _CASES_TXT),),
        located_in="cases.txt",
    ),
    # content outside a case is parsed with the body, so the need directive runs;
    # the match removes the need again
    "need directly in the body": _Expected(
        ".. match::\n\n"
        "   .. req:: Directly in the match body\n      :id: REQ_DIRECT\n\n"
        "   .. case:: True\n\n      SKIPPED\n",
        # named after the need, not the target without a line that it emits first
        (("got <Need>" + _SKIP, "   .. req:: Directly in the match body"),),
    ),
    # a case that is not taken is never parsed, exactly as the body of a false `if`
    "errors in an untaken case are never reported": _Expected(
        ".. match::\n\n"
        "   .. case:: True\n\n      TAKEN_E\n\n"
        "      .. req:: In the taken case\n         :id: REQ_TAKEN\n\n"
        "   .. case:: False\n\n"
        "      .. match::\n\n"
        "         .. case:: invalid !!!\n\n            SKIPPED\n\n"
        "      .. nosuchdirective::\n\n"
        "      .. req:: In the case that is not taken\n         :id: REQ_SKIPPED\n",
        (),
        taken=("TAKEN_E",),
        needs=("REQ_TAKEN",),
    ),
}


@pytest.mark.parametrize(
    ("test_app", "expected"),
    [
        (_project(case.body, conf=case.conf, extra=case.extra), case)
        for case in _WARNINGS.values()
    ],
    ids=list(_WARNINGS),
    indirect=["test_app"],
)
def test_match_warnings(test_app, expected: _Expected):
    """Each mistake warns exactly once, at the offending line, and fails closed."""
    app = test_app
    app.build()
    warnings = build_warnings(app)
    assert len(warnings) == len(expected.warnings), warnings
    source = Path(app.srcdir, expected.located_in).read_text()
    for warning, (text, line) in zip(warnings, expected.warnings, strict=True):
        assert warning.startswith(
            f"<srcdir>/{expected.located_in}:{_line_of(source, line)}: WARNING: "
        ), warning
        assert text in warning, warning
        assert warning.endswith(" [needs.match]"), warning
    html = Path(app.outdir, "index.html").read_text()
    assert [word for word in expected.taken if word not in html] == []
    assert "SKIPPED" not in html
    assert sorted(SphinxNeedsData(app.env).get_needs_view()) == list(expected.needs)
    _assert_no_match_nodes(app)


@pytest.mark.parametrize(
    ("test_app", "error"),
    [
        (
            _project(
                ".. match::\n\n"
                "   .. cas:: True\n\n      SKIPPED\n\n"
                "   .. case::\n\n      SKIPPED_DEFAULT\n"
            ),
            'Unknown directive type "cas"',
        ),
        (
            _project(
                ".. match::\n\n"
                "   Title\n   -----\n\n"
                "   .. case:: True\n\n      SKIPPED\n"
            ),
            "Unexpected section title",
        ),
    ],
    ids=["typo in a directive name", "section title in the body"],
    indirect=["test_app"],
)
def test_match_body_error_reported_once(test_app, error: str):
    """A mistake docutils reports in the body skips the match without a second warning."""
    app = test_app
    app.build()
    (warning,) = build_warnings(app)
    assert error in warning
    assert "needs.match" not in warning
    html = Path(app.outdir, "index.html").read_text()
    assert "SKIPPED" not in html


@pytest.mark.parametrize(
    "test_app",
    [
        _project(
            "Para.\n\n.. case:: True\n\n   SKIPPED_STRAY\n",
            conf=_CONF + "suppress_warnings = ['needs.match']\n",
        )
    ],
    indirect=True,
)
def test_match_warnings_are_suppressible(test_app):
    """Every ``match`` / ``case`` warning is of the ``needs.match`` type."""
    app = test_app
    app.build()
    assert_no_warnings(app)
    assert "SKIPPED" not in Path(app.outdir, "index.html").read_text()


@pytest.mark.parametrize(
    "test_app",
    [
        _project(
            ".. req:: Written before the match\n   :id: REQ_BEFORE\n\n"
            ".. match::\n\n"
            "   .. req:: Directly in the match body\n      :id: REQ_STRAY\n\n"
            "   .. case::\n\n      SKIPPED_DEFAULT\n\n"
            ".. req:: Written after the match\n   :id: REQ_AFTER\n",
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
def test_match_rollback_removes_only_the_stray_needs(test_app):
    """The rollback removes the needs the body created, the newest ones, and no other.

    The needs written before the ``match``, in its own document and in an earlier one,
    are older entries of the same mapping, and must survive.
    """
    app = test_app
    app.build()
    (warning,) = build_warnings(app)
    source = Path(app.srcdir, "index.rst").read_text()
    line = _line_of(source, "   .. req:: Directly in the match body")
    assert warning.startswith(f"<srcdir>/index.rst:{line}: WARNING: "), warning
    assert "got <Need>" in warning
    needs = SphinxNeedsData(app.env).get_needs_view()
    assert sorted(needs) == ["REQ_AFTER", "REQ_BEFORE", "REQ_EARLIER"]


_SWALLOW_CONF = (
    _CONF
    + """
from docutils import nodes
from sphinx.util.docutils import SphinxDirective


class Boom(SphinxDirective):
    def run(self):
        raise RuntimeError("boom")


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
    app.add_directive("boom", Boom)
    app.add_directive("swallow", Swallow)
"""
)


@pytest.mark.parametrize(
    "test_app",
    [
        _project(
            ".. swallow::\n\n"
            "   .. match::\n\n"
            "      .. case::\n\n         SKIPPED_X\n\n"
            "      .. boom::\n\n"
            ".. case:: True\n\n   SKIPPED_LOOSE_AFTER\n",
            conf=_SWALLOW_CONF,
        )
    ],
    indirect=True,
)
def test_match_restores_its_depth_when_its_body_raises(test_app):
    """An exception out of a ``match`` body leaves no ``match`` open behind it.

    A directive of the project catches what a directive in the body raised;
    the ``case`` after it is outside every ``match`` and must still be reported,
    rather than collected as a placeholder that would reach the writer.
    """
    app = test_app
    app.build()
    (warning,) = build_warnings(app)
    source = Path(app.srcdir, "index.rst").read_text()
    line = _line_of(source, ".. case:: True")
    assert warning.startswith(f"<srcdir>/index.rst:{line}: WARNING: "), warning
    assert "'case' directive outside a 'match'" in warning
    html = Path(app.outdir, "index.html").read_text()
    assert "SWALLOWED" in html
    assert "SKIPPED" not in html


# One condition language: `case` evaluates exactly what `if` does

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
                ".. match::\n\n"
                f"   .. case:: {expression}\n\n      CASE_TAKEN\n"
            ),
            expression,
            verdict,
        )
        for expression, verdict in _EXPRESSIONS.items()
    ],
    ids=list(_EXPRESSIONS),
    indirect=["test_app"],
)
def test_case_conditions_are_if_conditions(test_app, expression: str, verdict):
    """``if`` and ``case`` give every condition the same verdict and the same warnings.

    Only the directive name and the warning type differ,
    because both directives go through one evaluator.
    """
    app = test_app
    app.build()
    html = Path(app.outdir, "index.html").read_text()
    assert ("IF_TAKEN" in html) is bool(verdict)
    assert ("CASE_TAKEN" in html) is bool(verdict)

    warnings = build_warnings(app)
    if_warnings = [w for w in warnings if w.endswith(" [needs.if]")]
    case_warnings = [w for w in warnings if w.endswith(" [needs.match]")]
    assert len(if_warnings) + len(case_warnings) == len(warnings), warnings
    assert len(if_warnings) == len(case_warnings), warnings
    # an unevaluable condition warns, and so does a result that is not a bool
    assert bool(if_warnings) is (verdict is None or expression in _NON_BOOL)
    source = Path(app.srcdir, "index.rst").read_text()
    for if_warning, case_warning in zip(if_warnings, case_warnings, strict=True):
        assert if_warning.startswith(
            f"<srcdir>/index.rst:{_line_of(source, f'.. if:: {expression}')}: "
        ), if_warning
        assert case_warning.startswith(
            f"<srcdir>/index.rst:{_line_of(source, f'   .. case:: {expression}')}: "
        ), case_warning
        assert _strip_location_and_type(if_warning).startswith("'if' directive ")
        assert _strip_location_and_type(case_warning) == _strip_location_and_type(
            if_warning
        ).replace("'if' directive ", "'case' directive ", 1)


# MyST Markdown

_MYST_HAPPY = """\
```{toctree}
other
```

## Colon fences

::::{match}
:::{case} var.arch == "abc"
TAKEN_M1_FIRST
:::
:::{case} var.debug
SKIPPED_M1_SECOND_TRUE
:::
:::{case} this is not python !!!
SKIPPED_M1_INVALID_SYNTAX
:::
:::{case}
SKIPPED_M1_DEFAULT
:::
::::

## Comments between cases

::::{match}
:::{case} var.arch == "xyz"
SKIPPED_M2_FALSE
:::

% a MyST comment between two cases

+++

:::{case}
TAKEN_M2_DEFAULT
:::
::::

## Backtick fences, and needs in cases

`````{match}
````{case} var.arch == "xyz"
```{req} In a case that is not taken
:id: REQ_M3_SKIPPED
```
````
````{case} var.arch == "abc"
TAKEN_M3

```{req} In the taken case
:id: REQ_M3_TAKEN
```
````
`````

## A section in the taken case

::::{match}
:::{case} var.debug
### M4 conditional heading

TAKEN_M4_SECTION_BODY
:::
::::

## Nested match, one more fence character per level

::::::{match}
:::::{case} var.debug
TAKEN_M5_OUTER

::::{match}
:::{case} var.arch == "xyz"
SKIPPED_M5_INNER
:::
:::{case}
TAKEN_M5_INNER_DEFAULT
:::
::::
:::::
:::::{case}
SKIPPED_M5_OUTER
:::::
::::::

## A default whose fence line ends in spaces is a default

::::{match}
:::{case} False
SKIPPED_M6
:::
:::{case}\x20\x20\x20
TAKEN_M6_DEFAULT
:::
::::

## Match in the content of a need

:::::{req} Host with match content
:id: REQ_M_HOST

::::{match}
:::{case} var.arch == "xyz"
SKIPPED_M7_IN_NEED
:::
:::{case} var.arch == "abc"
TAKEN_M7_IN_NEED
:::
::::
:::::

## A whole match in an included file

```{include} included_match.txt
```
"""

_MYST_INCLUDED_MATCH = """\
::::{match}
:::{case} var.arch == "xyz"
SKIPPED_M8_IN_INCLUDED_MATCH
:::
:::{case}
TAKEN_M8_INCLUDED_MATCH_DEFAULT
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
            extra=(("included_match.txt", _MYST_INCLUDED_MATCH),),
        )
    ],
    indirect=True,
)
def test_match_in_myst(test_app):
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
        "TAKEN_M8_INCLUDED_MATCH_DEFAULT",
    ]
    assert [word for word in taken if word not in html] == []
    assert "SKIPPED_" not in html

    needs = SphinxNeedsData(app.env).get_needs_view()
    assert sorted(needs) == ["REQ_M3_TAKEN", "REQ_M_HOST"]
    # MyST gives a directive a content offset relative to its own line, which the
    # match re-bases for the case it takes: the need knows its true line
    source = Path(app.srcdir, "index.md").read_text()
    assert needs["REQ_M3_TAKEN"]["lineno"] == _line_of(
        source, "```{req} In the taken case"
    )

    assert [
        "Test",
        "A section in the taken case",
        "M4 conditional heading",
    ] in _section_titles(app, "index")

    other = Path(app.outdir, "other.html").read_text()
    assert "TAKEN_M7_IN_NEED" in other
    assert "SKIPPED_" not in other

    _assert_no_match_nodes(app)


# MyST reports a directive nested in a colon fence one line late (its own quirk, the
# same for a `{note}` in a `{note}`), so only the backtick spellings assert a line
_MYST_WARNINGS = {
    "case outside a match, backticks": (
        "Para.\n\n```{case} True\nSKIPPED_STRAY\n```\n",
        "'case' directive outside a 'match'",
        "```{case} True",
    ),
    "default case outside a match, backticks": (
        "Para.\n\n```{case}\nSKIPPED_STRAY_DEFAULT\n```\n",
        "'case' directive outside a 'match'",
        "```{case}",
    ),
    "case outside a match, colons": (
        "Para.\n\n:::{case} True\nSKIPPED_STRAY\n:::\n",
        "'case' directive outside a 'match'",
        None,
    ),
    "case loose in the taken case, backticks": (
        "`````{match}\n````{case} True\nTAKEN_OUTER\n\n"
        "```{case} True\nSKIPPED_LOOSE\n```\n````\n`````\n",
        "'case' directive outside a 'match'",
        "```{case} True",
    ),
    "paragraph in the body, backticks": (
        "````{match}\n```{case} True\nSKIPPED\n```\n\nA stray paragraph.\n````\n",
        "got <paragraph>" + _SKIP,
        "A stray paragraph.",
    ),
    "paragraph in the body, colons": (
        "::::{match}\n:::{case} True\nSKIPPED\n:::\n\nA stray paragraph.\n::::\n",
        "got <paragraph>" + _SKIP,
        None,
    ),
    # an HTML comment is raw HTML, not a comment
    "html comment between cases, backticks": (
        "````{match}\n```{case} False\nSKIPPED\n```\n\n<!-- an HTML comment -->\n\n"
        "```{case}\nSKIPPED_DEFAULT\n```\n````\n",
        "got <raw>" + _SKIP,
        "<!-- an HTML comment -->",
    ),
    "html comment between cases, colons": (
        "::::{match}\n:::{case} False\nSKIPPED\n:::\n\n<!-- an HTML comment -->\n\n"
        ":::{case}\nSKIPPED_DEFAULT\n:::\n::::\n",
        "got <raw>" + _SKIP,
        None,
    ),
    "match with an argument, backticks": (
        "````{match} var.arch\n```{case} True\nSKIPPED\n```\n````\n",
        "'match' directive takes no argument, got 'var.arch'",
        "````{match} var.arch",
    ),
    "match with an argument, colons": (
        "::::{match} var.arch\n:::{case} True\nSKIPPED\n:::\n::::\n",
        "'match' directive takes no argument, got 'var.arch'",
        None,
    ),
    "unevaluable condition, backticks": (
        "````{match}\n```{case} invalid !!!\nSKIPPED\n```\n"
        "```{case}\nSKIPPED_DEFAULT\n```\n````\n",
        "'case' directive expression failed: 'invalid !!!'",
        "```{case} invalid !!!",
    ),
    "unevaluable condition, colons": (
        "::::{match}\n:::{case} invalid !!!\nSKIPPED\n:::\n"
        ":::{case}\nSKIPPED_DEFAULT\n:::\n::::\n",
        "'case' directive expression failed: 'invalid !!!'",
        None,
    ),
    # an `{eval-rst}` block is parsed by docutils into a document of its own,
    # so the case in it is not a direct child of the match
    "case inside eval-rst, backticks": (
        "````{match}\n```{eval-rst}\n.. case:: True\n\n   SKIPPED_FROM_EVAL_RST\n```\n"
        "````\n",
        _NOT_DIRECT,
        ".. case:: True",
    ),
    "case inside eval-rst, colons": (
        "::::{match}\n```{eval-rst}\n.. case:: True\n\n   SKIPPED_FROM_EVAL_RST\n```\n"
        "::::\n",
        _NOT_DIRECT,
        None,
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
def test_match_warnings_in_myst(test_app, text: str, line: str | None):
    """The MyST spellings warn once each and fail closed, as in reStructuredText."""
    app = test_app
    app.build()
    (warning,) = build_warnings(app)
    assert text in warning, warning
    assert warning.endswith(" [needs.match]"), warning
    if line is not None:
        source = Path(app.srcdir, "index.md").read_text()
        assert warning.startswith(
            f"<srcdir>/index.md:{_line_of(source, line)}: WARNING: "
        ), warning
    assert "SKIPPED" not in Path(app.outdir, "index.html").read_text()
    _assert_no_match_nodes(app)


@pytest.mark.skipif(not _HAS_MYST, reason="needs myst-parser")
@pytest.mark.parametrize(
    "test_app",
    [
        _project(
            "::::{match}\n:::{case} True\nSKIPPED_IN_PLACE\n:::\n\n"
            "```{include} cases.txt\n```\n::::\n",
            conf=_CONF_MYST,
            myst=True,
            extra=(
                (
                    "cases.txt",
                    ':::{case} var.arch == "xyz"\nSKIPPED_X1_FROM_INCLUDE\n:::\n'
                    ":::{case}\nSKIPPED_X1_DEFAULT_FROM_INCLUDE\n:::\n",
                ),
            ),
        )
    ],
    indirect=True,
)
def test_match_refuses_included_cases_in_myst(test_app):
    """In MyST too, a ``case`` an ``{include}`` supplies is refused, in the included file.

    MyST reports the lines of an included file one late (the case on line 1 is
    reported on line 2, with colon and backtick fences alike), so only the file is
    asserted.
    """
    app = test_app
    app.build()
    (warning,) = build_warnings(app)
    assert warning.startswith("<srcdir>/cases.txt:"), warning
    assert _INCLUDED_CASE in warning, warning
    assert warning.endswith(" [needs.match]"), warning
    assert "SKIPPED" not in Path(app.outdir, "index.html").read_text()
    _assert_no_match_nodes(app)
