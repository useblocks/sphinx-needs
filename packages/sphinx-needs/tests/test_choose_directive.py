"""Tests for the ``.. choose::``, ``.. when::`` and ``.. otherwise::`` directives."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import NamedTuple

import pytest
from docutils import nodes

from sphinx_needs.data import SphinxNeedsData
from sphinx_needs.directives.needchoose import _BranchPlaceholder, _ChooseBody
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


def _not_direct(kind: str) -> str:
    """The warning about a branch of the kind ``kind`` inside another directive."""
    return (
        f"'{kind}' directive is not a direct child of its 'choose' "
        "(it is inside another directive)" + _SKIP
    )


def _included(kind: str) -> str:
    """The warning about a branch of the kind ``kind`` that an include supplies."""
    return (
        f"'{kind}' supplied through an include is not supported "
        "(write the branches in the body of the 'choose')" + _SKIP
    )


_NOT_DIRECT = _not_direct("when")
_INCLUDED_BRANCH = _included("when")
_ONLY_BRANCHES = (
    "'choose' directive may contain only 'when' and 'otherwise' directives and comments"
)
_NO_BRANCH = "'choose' directive has no 'when' or 'otherwise'"
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
                "'otherwise' directive takes no condition" + _SKIP,
                "   .. otherwise:: var.debug",
            ),
        ),
    ),
    "paragraph in the body": _Expected(
        ".. choose::\n\n"
        "   .. when:: True\n\n      SKIPPED_BRANCH\n\n"
        "   A stray paragraph.\n",
        (
            (
                _ONLY_BRANCHES + ", got <paragraph>" + _SKIP,
                "   A stray paragraph.",
            ),
        ),
    ),
    # exactly one warning: the branch in the note is not a stray, it is in a choose body
    "note wrapping a branch": _Expected(
        ".. choose::\n\n"
        "   .. note::\n\n      .. when:: True\n\n         SKIPPED_IN_NOTE\n",
        (("got <note>" + _SKIP, "   .. note::"),),
    ),
    # a directive that returns the nodes of its content (a true `if`, `rst-class`)
    # would hand its branches to the choose: a branch must be written directly in it
    "branches inside a true if": _Expected(
        ".. choose::\n\n"
        "   .. if:: var.debug\n\n"
        "      .. when:: var.arch == 'x86'\n\n         SKIPPED_X86\n\n"
        "      .. otherwise::\n\n         SKIPPED_DEFAULT_FROM_IF\n",
        ((_NOT_DIRECT, "      .. when:: var.arch == 'x86'"),),
    ),
    "branch inside rst-class": _Expected(
        ".. choose::\n\n"
        "   .. rst-class:: special\n\n"
        "      .. when:: var.arch == 'abc'\n\n         SKIPPED_FROM_RST_CLASS\n",
        ((_NOT_DIRECT, "      .. when:: var.arch == 'abc'"),),
    ),
    # the warnings name the kind of the branch
    "otherwise inside a true if": _Expected(
        ".. choose::\n\n"
        "   .. when:: False\n\n      SKIPPED_FALSE\n\n"
        "   .. if:: var.debug\n\n"
        "      .. otherwise::\n\n         SKIPPED_DEFAULT_FROM_IF\n",
        ((_not_direct("otherwise"), "      .. otherwise::"),),
    ),
    # a line of one to three punctuation characters makes docutils emit an INFO
    # message, which is never shown, before the paragraph: the paragraph is reported
    "rule line between branches": _Expected(
        ".. choose::\n\n"
        "   .. when:: var.arch == 'x86'\n\n      SKIPPED_X86\n\n"
        "   ---\n\n"
        "   .. otherwise::\n\n      SKIPPED_DEFAULT\n",
        (("got <paragraph>" + _SKIP, "   ---"),),
    ),
    "three dots in the body": _Expected(
        ".. choose::\n\n   ...\n\n   .. otherwise::\n\n      SKIPPED_DEFAULT\n",
        (("got <paragraph>" + _SKIP, "   ..."),),
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
    # two independent mistakes, two warnings: a choose written directly in another
    # choose's body, whose taken branch holds a loose branch. The taken branch is
    # parsed outside every choose body, so the loose branch is reported and cannot
    # become a branch of the OUTER choose, which then has none.
    "branch loose in the taken branch of a misplaced choose": _Expected(
        ".. choose::\n\n"
        "   .. choose::\n\n"
        "      .. when:: True\n\n"
        "         .. when:: True\n\n            SKIPPED_LOOSE\n",
        (
            ("'when' directive outside a 'choose'", "         .. when:: True"),
            (_NO_BRANCH, ".. choose::"),
        ),
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
    # the branches of a choose are written in its body: an include may not supply them,
    # and the warning points at the branch in the included file
    "branches from an include": _Expected(
        ".. choose::\n\n   .. include:: branches.txt\n",
        ((_INCLUDED_BRANCH, '.. when:: var.arch == "xyz"'),),
        extra=(("branches.txt", _BRANCHES_TXT),),
        located_in="branches.txt",
    ),
    # the structure is checked before any condition: a true branch written in place
    # before the included ones is not taken either
    "a branch from an include after a true branch": _Expected(
        ".. choose::\n\n"
        "   .. when:: True\n\n      SKIPPED_IN_PLACE\n\n"
        "   .. include:: branches.txt\n",
        ((_INCLUDED_BRANCH, '.. when:: var.arch == "xyz"'),),
        extra=(("branches.txt", _BRANCHES_TXT),),
        located_in="branches.txt",
    ),
    "an otherwise from an include": _Expected(
        ".. choose::\n\n"
        "   .. when:: False\n\n      SKIPPED_FALSE\n\n"
        "   .. include:: otherwise.txt\n",
        ((_included("otherwise"), ".. otherwise::"),),
        extra=(("otherwise.txt", ".. otherwise::\n\n   SKIPPED_FROM_INCLUDE\n"),),
        located_in="otherwise.txt",
    ),
    # content outside a branch is parsed with the body, so the need directive runs;
    # the choose removes the need again
    "need directly in the body": _Expected(
        ".. choose::\n\n"
        "   .. req:: Directly in the choose body\n      :id: REQ_DIRECT\n\n"
        "   .. when:: True\n\n      SKIPPED\n",
        # named after the need, not the target without a line that it emits first
        (("got <Need>" + _SKIP, "   .. req:: Directly in the choose body"),),
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
def test_choose_warnings(test_app, expected: _Expected):
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
        assert warning.endswith(" [needs.choose]"), warning
    html = Path(app.outdir, "index.html").read_text()
    assert [word for word in expected.taken if word not in html] == []
    assert "SKIPPED" not in html
    assert sorted(SphinxNeedsData(app.env).get_needs_view()) == list(expected.needs)
    _assert_no_choose_nodes(app)


@pytest.mark.parametrize(
    "test_app",
    [
        _project(
            ".. choose::\n\n"
            "   .. when:: var.arch == 'x86'\n\n      SKIPPED_X86\n\n"
            "   ---\n\n"
            "   .. otherwise::\n\n      SKIPPED_DEFAULT\n",
            extra=(("docutils.conf", "[general]\nreport_level: 1\n"),),
        )
    ],
    indirect=True,
)
def test_choose_info_message_is_never_a_reported_error(test_app, monkeypatch):
    """An INFO message in the body is not taken for an error docutils reported.

    With ``report_level: 1`` in the project's ``docutils.conf`` the INFO before the
    paragraph of a ``---`` line is shown, but as information, not as a warning,
    so the paragraph must still be reported: otherwise the choose would vanish
    with ``-W`` green. ``sphinx-build`` points ``DOCUTILSCONFIG`` at the project's
    ``docutils.conf``; this in-process build does it by hand.
    """
    app = test_app
    monkeypatch.setenv("DOCUTILSCONFIG", str(Path(app.srcdir, "docutils.conf")))
    app.build()
    (warning,) = build_warnings(app)
    source = Path(app.srcdir, "index.rst").read_text()
    assert warning.startswith(
        f"<srcdir>/index.rst:{_line_of(source, '   ---')}: WARNING: "
    ), warning
    assert "got <paragraph>" + _SKIP in warning, warning
    assert warning.endswith(" [needs.choose]"), warning
    assert "SKIPPED" not in Path(app.outdir, "index.html").read_text()
    # the INFO itself was shown, so the setting took effect
    assert "Unexpected possible title overline or transition" in app._status.getvalue()


@pytest.mark.parametrize(
    ("test_app", "error"),
    [
        (
            _project(
                ".. choose::\n\n"
                "   .. cas:: True\n\n      SKIPPED\n\n"
                "   .. otherwise::\n\n      SKIPPED_DEFAULT\n"
            ),
            'Unknown directive type "cas"',
        ),
        (
            _project(
                ".. choose::\n\n"
                "   Title\n   -----\n\n"
                "   .. when:: True\n\n      SKIPPED\n"
            ),
            "Unexpected section title",
        ),
    ],
    ids=["typo in a directive name", "section title in the body"],
    indirect=["test_app"],
)
def test_choose_body_error_reported_once(test_app, error: str):
    """A mistake docutils reports in the body skips the choose and warns only once."""
    app = test_app
    app.build()
    (warning,) = build_warnings(app)
    assert error in warning
    assert "needs.choose" not in warning
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
def test_choose_rollback_removes_only_the_stray_needs(test_app):
    """The rollback removes the needs the body created, the newest ones, and no other.

    The needs written before the ``choose``, in its own document and in an earlier one,
    are older entries of the same mapping, and must survive.
    """
    app = test_app
    app.build()
    (warning,) = build_warnings(app)
    source = Path(app.srcdir, "index.rst").read_text()
    line = _line_of(source, "   .. req:: Directly in the choose body")
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
            "   .. choose::\n\n"
            "      .. otherwise::\n\n         SKIPPED_X\n\n"
            "      .. boom::\n\n"
            ".. when:: True\n\n   SKIPPED_LOOSE_AFTER\n",
            conf=_SWALLOW_CONF,
        )
    ],
    indirect=True,
)
def test_choose_restores_its_depth_when_its_body_raises(test_app):
    """An exception out of a ``choose`` body leaves no ``choose`` open behind it.

    A directive of the project catches what a directive in the body raised;
    the ``when`` after it is outside every ``choose`` and must still be reported,
    rather than collected as a placeholder that would reach the writer.
    """
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
        "got <paragraph>" + _SKIP,
        "A stray paragraph.",
    ),
    "paragraph in the body, colons": (
        "::::{choose}\n:::{when} True\nSKIPPED\n:::\n\nA stray paragraph.\n::::\n",
        "got <paragraph>" + _SKIP,
        None,
    ),
    # an HTML comment is raw HTML, not a comment
    "html comment between branches, backticks": (
        "````{choose}\n```{when} False\nSKIPPED\n```\n\n<!-- an HTML comment -->\n\n"
        "```{otherwise}\nSKIPPED_DEFAULT\n```\n````\n",
        "got <raw>" + _SKIP,
        "<!-- an HTML comment -->",
    ),
    "html comment between branches, colons": (
        "::::{choose}\n:::{when} False\nSKIPPED\n:::\n\n<!-- an HTML comment -->\n\n"
        ":::{otherwise}\nSKIPPED_DEFAULT\n:::\n::::\n",
        "got <raw>" + _SKIP,
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
        "'otherwise' directive takes no condition" + _SKIP,
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
    # an `{eval-rst}` block is parsed by docutils into a document of its own,
    # so the branch in it is not a direct child of the choose
    "branch inside eval-rst, backticks": (
        "````{choose}\n```{eval-rst}\n.. when:: True\n\n   SKIPPED_FROM_EVAL_RST\n```\n"
        "````\n",
        _NOT_DIRECT,
        ".. when:: True",
    ),
    "branch inside eval-rst, colons": (
        "::::{choose}\n```{eval-rst}\n.. when:: True\n\n   SKIPPED_FROM_EVAL_RST\n```\n"
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
def test_choose_warnings_in_myst(test_app, text: str, line: str | None):
    """The MyST spellings warn once each and fail closed, as in reStructuredText."""
    app = test_app
    app.build()
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
    """In MyST too, a branch an ``{include}`` supplies is refused, in the included file.

    MyST reports the lines of an included file one late (the branch on line 1 is
    reported on line 2, with colon and backtick fences alike), so only the file is
    asserted.
    """
    app = test_app
    app.build()
    (warning,) = build_warnings(app)
    assert warning.startswith("<srcdir>/branches.txt:"), warning
    assert _INCLUDED_BRANCH in warning, warning
    assert warning.endswith(" [needs.choose]"), warning
    assert "SKIPPED" not in Path(app.outdir, "index.html").read_text()
    _assert_no_choose_nodes(app)
