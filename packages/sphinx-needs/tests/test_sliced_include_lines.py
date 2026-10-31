"""A need in a sliced include records its line in the file, not in the slice (#2428).

docutils hands the parser an include's slice (``:start-line:``, ``:start-after:``) as its
own input, numbered from the slice's first line, so the state machine reports a line of
the slice. A need records its ``lineno``, and its file hop its lines, in the file
instead: sphinx-needs recovers the slice's start from the include's options in
``document.include_log``. docutils' own messages keep the slice's line.

Every case is built on the docutils the environment has: the sphinx-8 cell runs this
module on docutils 0.21, whose ``include_log`` orders the options differently, and the
default environment on 0.22.
"""

from __future__ import annotations

import importlib.util
from collections.abc import Callable
from pathlib import Path

import pytest
from docutils.statemachine import StateMachine, StringList
from sphinx.testing.util import SphinxTestApp

from sphinx_needs.data import SphinxNeedsData
from sphinx_needs_testkit import assert_no_warnings

CONF = """\
extensions = [{extensions}]
needs_types = [
    {{"directive": "req", "title": "Req", "prefix": "R_", "color": "#fff", "style": "node"}}
]
exclude_patterns = ["frag*", "_build"]
"""

FRAGMENT = """\
Fragment header line A
Fragment header line B

START-HERE

.. req:: Plain need
   :id: REQ_PLAIN

.. req:: Content need
   :id: REQ_CONTENT

   Some content.

.. req:: Outer need
   :id: REQ_OUTER

   .. req:: Inner need
      :id: REQ_INNER

      Inner content.

.. list2need::
   :types: req

   * (REQ_LIST_A) First list need
   * (REQ_LIST_B) Second list need

END-HERE
trailing
"""
"""The lines below are the fragment's own, which every need records, sliced or not."""

TRUE_LINES: dict[str, tuple[int, tuple[int, int]]] = {
    # id: (lineno, the file hop's start and end line)
    "REQ_PLAIN": (6, (6, 7)),
    "REQ_CONTENT": (9, (9, 12)),
    "REQ_OUTER": (14, (14, 20)),
    "REQ_INNER": (17, (17, 20)),
    "REQ_LIST_A": (25, (25, 25)),
    "REQ_LIST_B": (26, (26, 26)),
}

SLICED = pytest.mark.xfail(
    strict=True, reason="#2428: a need in a slice records the slice's line"
)

VARIANTS = [
    pytest.param([], id="control"),
    pytest.param([":start-line: 3"], id="start-line", marks=SLICED),
    pytest.param([":start-after: START-HERE"], id="start-after", marks=SLICED),
    pytest.param(
        [":start-line: 3", ":start-after: START-HERE"],
        id="start-line+start-after",
        marks=SLICED,
    ),
    pytest.param([":end-line: 28"], id="end-line"),
    pytest.param([":end-before: END-HERE"], id="end-before"),
]


def _project(
    root: Path,
    fragment: str,
    options: list[str],
    *,
    extensions: tuple[str, ...] = ("sphinx_needs",),
    encoding: str = "utf-8",
) -> Path:
    """Write a project whose ``index.rst`` includes ``frag.rst`` with ``options``."""
    root.mkdir(parents=True, exist_ok=True)
    (root / "conf.py").write_text(
        CONF.format(extensions=", ".join(repr(e) for e in extensions)),
        encoding="utf-8",
    )
    (root / "frag.rst").write_bytes(fragment.encode(encoding))
    (root / "index.rst").write_text(
        "Host\n====\n\nHost paragraph.\n\n.. include:: frag.rst\n"
        + "".join(f"   {option}\n" for option in options),
        encoding="utf-8",
    )
    return root


def _lines(
    make_app: Callable[..., SphinxTestApp], srcdir: Path
) -> dict[str, tuple[int | None, tuple[int | None, int | None] | None]]:
    """Every need's ``lineno``, and its ``frag.rst`` hop's lines (``None`` if no such hop)."""
    app = make_app("html", srcdir=srcdir, freshenv=True)
    try:
        app.build()
        assert_no_warnings(app)
        result: dict[str, tuple[int | None, tuple[int | None, int | None] | None]] = {}
        for need_id, need in SphinxNeedsData(app.env).get_needs_view().items():
            hop = next(
                (
                    h.physical
                    for h in need.source.hops
                    if h.physical is not None and h.physical.path == "frag.rst"
                ),
                None,
            )
            result[need_id] = (
                need["lineno"],
                None if hop is None else (hop.start_line, hop.end_line),
            )
        return result
    finally:
        app.cleanup()


@pytest.mark.parametrize("options", VARIANTS)
def test_a_need_in_a_slice_records_its_file_line(
    make_app: Callable[..., SphinxTestApp], tmp_path: Path, options: list[str]
) -> None:
    """A plain need, one with content, a nested need and a ``list2need`` item record
    the fragment's own lines, whatever the include slices; the file hop has them too,
    since the file holds each need's text there."""
    srcdir = _project(tmp_path / "project", FRAGMENT, options)
    assert _lines(make_app, srcdir) == {
        need_id: (lineno, hop) for need_id, (lineno, hop) in TRUE_LINES.items()
    }


FORM_FEED_ABOVE = (
    "Header A\n"
    "\f\n"  # one line of the file, two for ``str.splitlines``
    "Header C\n"
    "\n"
    ".. req:: Below a form feed\n"
    "   :id: REQ_FF_ABOVE\n"
)

FORM_FEED_INSIDE = (
    "Header A\n"
    "Header B\n"
    "\n"
    "\f\n"
    "\n"
    ".. req:: After a form feed in the slice\n"
    "   :id: REQ_FF_INSIDE\n"
)


@pytest.mark.parametrize(
    ("fragment", "start_line", "need_id", "line"),
    [
        pytest.param(FORM_FEED_ABOVE, 3, "REQ_FF_ABOVE", 5, id="above", marks=SLICED),
        pytest.param(
            FORM_FEED_INSIDE, 2, "REQ_FF_INSIDE", 6, id="inside", marks=SLICED
        ),
    ],
)
def test_a_form_feed_is_no_line_break_of_the_file(
    make_app: Callable[..., SphinxTestApp],
    tmp_path: Path,
    fragment: str,
    start_line: int,
    need_id: str,
    line: int,
) -> None:
    """docutils clips ``:start-line:`` by ``str.splitlines``, which breaks a line at a
    form feed, and numbers a file's lines with a form feed as a space (as the hops read
    the file): the need's line is the file's.

    Above the slice, ``:start-line: 3`` skips two lines of the file, not three. Inside
    it, docutils 0.22 joins the clipped lines with ``\\n``, so the slice holds a line
    the file does not: lines after the form feed are one further from the file's than
    those before it.
    """
    srcdir = _project(tmp_path / "project", fragment, [f":start-line: {start_line}"])
    assert _lines(make_app, srcdir)[need_id] == (line, (line, line + 1))


@pytest.mark.skipif(
    importlib.util.find_spec("sphinx_test_reports") is None,
    # sphinx-test-reports is a workspace sibling, not a dependency: the release
    # workflow's compat cell runs this suite against the released dependencies alone
    reason="sphinx-test-reports is not installed",
)
@pytest.mark.parametrize("options", VARIANTS[:2])
def test_a_test_file_in_a_slice_records_its_file_line(
    make_app: Callable[..., SphinxTestApp], tmp_path: Path, options: list[str]
) -> None:
    """sphinx-test-reports' ``test-file`` records its line through
    ``NeedItemSource.from_directive``, as a need directive does."""
    fragment = (
        "skipped 1\n"
        "skipped 2\n"
        "skipped 3\n"
        "\n"
        "Kept.\n"
        "\n"
        ".. test-file:: Test file\n"
        "   :file: report.xml\n"
        "   :id: TF_FILE1\n"
    )
    srcdir = _project(
        tmp_path / "project",
        fragment,
        options,
        extensions=("sphinx_needs", "sphinx_test_reports"),
    )
    (srcdir / "report.xml").write_text(
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<testsuites><testsuite name="suite" tests="1" errors="0" failures="0"'
        ' skipped="0" time="0.1"><testcase classname="mod" name="test_one"'
        ' time="0.1"/></testsuite></testsuites>\n',
        encoding="utf-8",
    )
    with (srcdir / "conf.py").open("a", encoding="utf-8") as conf:
        conf.write("tr_rootdir = __import__('os').path.dirname(__file__)\n")
    assert _lines(make_app, srcdir)["TF_FILE1"] == (7, (7, 9))


def test_a_docutils_that_numbers_the_slice_itself_is_not_counted_twice(
    make_app: Callable[..., SphinxTestApp],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """docutils' ``insert_input`` numbers the slice from its start (its own TODO says
    so); one that numbered it from the file's line would give the true line already,
    and nothing is added to it."""

    def insert_input(self: StateMachine, input_lines: list[str], source: str) -> None:
        # what a fixed docutils would do for this project's ``:start-line: 3``
        offset = 3 if source.endswith("frag.rst") else 0
        self.input_lines.insert(
            self.line_offset + 1,
            "",
            source="internal padding after " + source,
            offset=len(input_lines),
        )
        self.input_lines.insert(
            self.line_offset + 1,
            "",
            source="internal padding before " + source,
            offset=-1,
        )
        self.input_lines.insert(
            self.line_offset + 2,
            StringList(
                input_lines,
                items=[(source, offset + i) for i in range(len(input_lines))],
            ),
        )

    monkeypatch.setattr(StateMachine, "insert_input", insert_input)
    srcdir = _project(tmp_path / "project", FRAGMENT, [":start-line: 3"])
    assert _lines(make_app, srcdir) == dict(TRUE_LINES.items())


LATIN_1 = "Caf\xe9 header\nskipped\nskipped\n\n.. req:: Latin-1\n   :id: REQ_LATIN\n"


@pytest.mark.parametrize(
    ("options", "encoding"),
    [
        pytest.param(
            [":start-line: 3", ":encoding: latin-1"], "latin-1", id="encoding"
        ),
        pytest.param([":start-line: 3", ":parser: rst"], "utf-8", id="parser"),
    ],
)
def test_where_the_slice_cannot_be_recovered_the_slice_line_stays(
    make_app: Callable[..., SphinxTestApp],
    tmp_path: Path,
    options: list[str],
    encoding: str,
) -> None:
    """A fragment the project's ``source_encoding`` cannot read, and a ``:parser:``
    include (parsed into a document of its own), keep the line the state machine
    gives, the slice's: today's value, and no file hop line."""
    srcdir = _project(tmp_path / "project", LATIN_1, options, encoding=encoding)
    lineno, hop = _lines(make_app, srcdir)["REQ_LATIN"]
    assert lineno == 2
    assert hop in {None, (None, None)}
