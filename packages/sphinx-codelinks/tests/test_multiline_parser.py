# @Test suite for multi-line need runs and prefixes and grammar, TEST_MLN_1, test, [IMPL_MLN_1, IMPL_MLN_2]
"""Unit tests of ``analyse/multiline_parser.py``: run formation, prefix stripping by
comment kind, and the block grammar on logical lines.

The comment nodes here are synthetic: the module reads only ``.text``, ``.type``,
``.start_point.row``, ``.start_point.column`` and ``is_libclang``.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from sphinx_codelinks.analyse.analyse import SourceAnalyse
from sphinx_codelinks.analyse.models import SourceComment, WarningSubTypeEnum
from sphinx_codelinks.analyse.multiline_parser import (
    LogicalLine,
    blank_rows,
    form_runs,
    open_rest,
    parse_run,
)
from sphinx_codelinks.config import MultilineNeedsConfig, SourceAnalyseConfig
from sphinx_codelinks.source_discover.config import CommentType


def _node(text: str, row: int, column: int = 0, kind: str = "comment") -> SourceComment:
    node = SimpleNamespace(
        text=text.encode("utf-8"),
        type=kind,
        start_point=SimpleNamespace(row=row, column=column),
    )
    return SourceComment(node)  # ty: ignore[invalid-argument-type]


def _libclang(text: str, row: int) -> SourceComment:
    node = SimpleNamespace(
        text=text.encode("utf-8"),
        start_point=SimpleNamespace(row=row),
        is_libclang=True,
    )
    return SourceComment(node)  # ty: ignore[invalid-argument-type]


def _texts(run) -> list[str]:
    return [line.text for line in run.lines]


def _lines(*texts: str, first_row: int = 0) -> list[LogicalLine]:
    return [LogicalLine(first_row + i, 0, text) for i, text in enumerate(texts)]


CONFIG = MultilineNeedsConfig()


# --- run formation ----------------------------------------------------------------------


def test_consecutive_line_comments_with_one_delimiter_form_one_run() -> None:
    runs = form_runs([_node("// a", 0), _node("// b", 1), _node("// c", 2)])

    assert [_texts(run) for run in runs] == [["a", "b", "c"]]


def test_a_gap_of_one_row_splits_a_run() -> None:
    runs = form_runs([_node("// a", 0), _node("// b", 2)])

    assert [_texts(run) for run in runs] == [["a"], ["b"]]


def test_a_change_of_delimiter_splits_a_run() -> None:
    runs = form_runs([_node("/// a", 0), _node("// b", 1), _node("//! c", 2)])

    assert [_texts(run) for run in runs] == [["a"], ["b"], ["c"]]


def test_a_comment_after_code_neither_starts_nor_continues_a_run() -> None:
    source = ["int x; // a", "// b", "// c", "f(); // d"]
    comments = [
        _node("// a", 0, 7),
        _node("// b", 1),
        _node("// c", 2),
        _node("// d", 3, 5),
    ]

    runs = form_runs(comments, source)

    assert [_texts(run) for run in runs] == [["a"], ["b", "c"], ["d"]]


def test_the_comments_are_read_in_source_order() -> None:
    """tree-sitter's captures are not in source order."""
    runs = form_runs([_node("// c", 2), _node("// a", 0), _node("// b", 1)])

    assert [_texts(run) for run in runs] == [["a", "b", "c"]]


def test_a_block_comment_is_a_run_of_its_own() -> None:
    runs = form_runs([_node("// a", 0), _node("/* b */", 1), _node("// c", 2)])

    assert [_texts(run) for run in runs] == [["a"], [" b "], ["c"]]


def test_libclang_comments_form_runs_from_their_rows() -> None:
    """A libclang comment has no column: what precedes it is read from its row."""
    source = ["// a", "// b", "int x; // c", "// d"]
    comments = [
        _libclang("// a", 0),
        _libclang("// b", 1),
        _libclang("// c", 2),
        _libclang("// d", 3),
    ]

    runs = form_runs(comments, source)

    assert [_texts(run) for run in runs] == [["a", "b"], ["c"], ["d"]]
    assert runs[1].lines[0].col == len("int x; // ")


def test_libclang_comments_without_their_rows_count_as_alone() -> None:
    runs = form_runs([_libclang("// a", 0), _libclang("// b", 1)])

    assert [_texts(run) for run in runs] == [["a", "b"]]


# --- prefix stripping -------------------------------------------------------------------


def test_a_line_comment_loses_its_delimiter_and_one_space() -> None:
    (run,) = form_runs([_node("//   indented", 3, 4)], ["    //   indented"])

    assert run.lines == [LogicalLine(3, 7, "  indented")]


def test_a_rust_doc_comment_loses_its_trailing_newline() -> None:
    (run,) = form_runs([_node("/// a\n", 0, kind="line_comment")])

    assert _texts(run) == ["a"]


def test_the_doxygen_leader_is_stripped_when_every_line_has_one() -> None:
    text = "/**\n * @need req: T\n *\n * Some *emphasis* here.\n * * item\n */"

    (run,) = form_runs([_node(text, 0)])

    assert _texts(run) == ["@need req: T", "", "Some *emphasis* here.", "* item"]
    assert [line.row for line in run.lines] == [1, 2, 3, 4]
    assert run.lines[0].col == len(" * ")


@pytest.mark.parametrize(
    "text",
    [
        pytest.param(
            "/**\n * @need req: T\n * @endneed\n ***/", id="stars_before_the_closer"
        ),
        pytest.param(
            "/*********\n * @need req: T\n * @endneed\n *********/", id="full_banner"
        ),
    ],
)
def test_delimiter_only_banner_rows_are_dropped_before_the_leader_test(
    text: str,
) -> None:
    """A row holding only the opener's or the closer's stars is a delimiter, not a line
    without a leader."""
    (run,) = form_runs([_node(text, 0)])

    assert _texts(run) == ["@need req: T", "@endneed"]
    assert [line.row for line in run.lines] == [1, 2]


def test_no_leader_is_stripped_when_one_line_lacks_it() -> None:
    """The every-line rule: a star that is not a leader on every line is content."""
    text = "/*\n * @need req: T\n   Some *emphasis* here.\n */"

    (run,) = form_runs([_node(text, 0)])

    assert _texts(run) == [" * @need req: T", "   Some *emphasis* here."]


def test_an_emphasis_line_is_not_a_leader() -> None:
    text = "/*\n*emphasis* first\n*more* second\n*/"

    (run,) = form_runs([_node(text, 0)])

    assert _texts(run) == ["*emphasis* first", "*more* second"]


def test_a_one_row_block_comment_keeps_its_text() -> None:
    (run,) = form_runs([_node("/* @need req: T @endneed */", 0, 2)])

    assert run.lines == [LogicalLine(0, 4, " @need req: T @endneed ")]


def test_a_docstring_is_unquoted_and_dedented_like_cleandoc() -> None:
    text = 'r"""First line.\n\n    @need impl: T\n      deeper\n    """'

    (run,) = form_runs([_node(text, 5, 4, kind="expression_statement")])

    assert _texts(run) == ["First line.", "", "@need impl: T", "  deeper", ""]
    assert run.lines[0].col == 4 + len('r"""')
    assert run.lines[2] == LogicalLine(7, 4, "@need impl: T")


def test_a_comment_without_a_delimiter_is_read_unstripped() -> None:
    (run,) = form_runs([_libclang("@need req: T", 0)])

    assert _texts(run) == ["@need req: T"]


# --- the grammar ------------------------------------------------------------------------


def test_a_block_with_options_and_a_body() -> None:
    lines = [
        LogicalLine(1, 3, "@need[md] req: A title"),
        LogicalLine(2, 3, ":id: REQ_1"),
        LogicalLine(3, 3, ":links: A, B"),
        LogicalLine(4, 3, ""),
        LogicalLine(5, 3, "  Body *text*."),
        LogicalLine(6, 3, "    deeper"),
        LogicalLine(7, 3, ""),
        LogicalLine(8, 3, "@endneed"),
    ]

    result = parse_run(lines, CONFIG)

    (block,) = result.blocks
    assert block.need == {
        "type": "req",
        "title": "A title",
        "id": "REQ_1",
        "links": "A, B",
        "content": "Body *text*.\n  deeper",
        "doctype": ".md",
    }
    assert block.markup == "md"
    assert (block.open_row, block.open_col) == (1, 3)
    assert (block.close_row, block.end_col) == (8, 3 + len("@endneed"))
    assert block.option_rows == {"id": 3, "links": 4}
    assert block.content_start == (5, 5)
    assert result.issues == []
    assert result.claimed_rows == set(range(1, 9))


def test_the_open_word_must_be_a_whole_word() -> None:
    assert open_rest("@need req: T", "@need") == " req: T"
    assert open_rest("  @need[md] req: T", "@need") == "[md] req: T"
    assert open_rest("@need", "@need") == ""
    assert open_rest("@need-ids: REQ_1", "@need") is None
    assert open_rest("@needle", "@need") is None
    assert open_rest("see @need req: T", "@need") is None


def test_a_reference_line_is_not_an_open_line() -> None:
    result = parse_run(_lines("@need-ids: REQ_1"), CONFIG)

    assert (result.blocks, result.issues, result.claimed_rows) == ([], [], set())


@pytest.mark.parametrize(
    "open_line",
    [
        "@need",
        "@need req",
        "@need req:Title",
        "@need [md] req: T",
        "@need this: or that",
    ],
)
def test_a_malformed_open_line_is_refused_and_consumed(open_line: str) -> None:
    """The last one is no exception: its ``this`` is a type and ``or that`` the title.
    A line is refused only when no ``<type>:`` follows the open word."""
    result = parse_run(_lines(open_line, "@param a, b", "@endneed"), CONFIG)

    if open_line == "@need this: or that":
        assert [block.need["type"] for block in result.blocks] == ["this"]
    else:
        assert result.blocks == []
        assert [(issue.kind, issue.row) for issue in result.issues] == [
            (WarningSubTypeEnum.multiline_need_header, 0)
        ]
    assert result.claimed_rows == {0, 1, 2}


def test_an_unterminated_block_is_refused_and_ends_the_scan() -> None:
    result = parse_run(_lines("@need req: A", "@need req: B", "body"), CONFIG)

    assert result.blocks == []
    assert [(issue.kind, issue.row) for issue in result.issues] == [
        (WarningSubTypeEnum.multiline_need_unterminated, 0)
    ]
    assert result.claimed_rows == set()


def test_the_one_line_form_is_refused_and_claims_its_own_row() -> None:
    """Its row is hidden from the one-line parser, which would otherwise mint a need
    from a title holding a comma, or warn a second time."""
    result = parse_run(_lines("@need req: T, with comma @endneed", "next"), CONFIG)

    assert [(issue.kind, issue.row) for issue in result.issues] == [
        (WarningSubTypeEnum.multiline_need_oneline_form, 0)
    ]
    assert result.claimed_rows == {0}


def test_an_unknown_markup_falls_back_to_the_default() -> None:
    result = parse_run(_lines("@need[xyz] req: T", "@endneed"), CONFIG)

    (block,) = result.blocks
    assert (block.markup, block.need["doctype"]) == ("rst", ".rst")
    assert [issue.kind for issue in result.issues] == [
        WarningSubTypeEnum.multiline_need_markup
    ]


def test_a_continuation_line_joins_its_option_with_one_space() -> None:
    lines = _lines(
        "@need req: T", ":links:", "  A,", "  B", ":status: open", "@endneed"
    )

    (block,) = parse_run(lines, CONFIG).blocks

    assert block.need["links"] == "A, B"
    assert block.need["status"] == "open"


def test_a_duplicate_option_keeps_the_first_value_and_drops_its_continuation() -> None:
    lines = _lines("@need req: T", ":id: A", ":id: B", "   more", "@endneed")

    result = parse_run(lines, CONFIG)

    (block,) = result.blocks
    assert block.need["id"] == "A"
    assert block.need["content"] == ""
    assert [(issue.kind, issue.row) for issue in result.issues] == [
        (WarningSubTypeEnum.multiline_need_duplicate_option, 2)
    ]


@pytest.mark.parametrize("key", ["type", "title", "content", "doctype"])
def test_an_option_naming_a_record_key_is_a_duplicate(key: str) -> None:
    lines = _lines("@need req: T", f":{key}: other", "", "Body.", "@endneed")

    result = parse_run(lines, CONFIG)

    (block,) = result.blocks
    assert (block.need["type"], block.need["title"]) == ("req", "T")
    assert (block.need["content"], block.need["doctype"]) == ("Body.", ".rst")
    assert [issue.kind for issue in result.issues] == [
        WarningSubTypeEnum.multiline_need_duplicate_option
    ]


def test_the_first_line_that_is_not_an_option_starts_the_body() -> None:
    """No blank line is needed; a blank line ends the options too."""
    (block,) = parse_run(
        _lines("@need req: T", ":id: A", "Body.", ":not: an option", "@endneed"),
        CONFIG,
    ).blocks

    assert block.need == {
        "type": "req",
        "title": "T",
        "id": "A",
        "content": "Body.\n:not: an option",
        "doctype": ".rst",
    }


def test_an_escaped_close_is_body_text_without_its_backslash() -> None:
    lines = _lines("@need req: T", "", "\\@endneed", "\\@need stays", "@endneed")

    (block,) = parse_run(lines, CONFIG).blocks

    assert block.need["content"] == "@endneed\n\\@need stays"


def test_an_indented_escape_loses_its_backslash_and_keeps_its_indentation() -> None:
    """The escape mirrors the close test, which ignores indentation: so the close word
    can be shown inside an indented block of the body."""
    lines = _lines("@need req: T", "", "Example::", "", "    \\@endneed", "@endneed")

    (block,) = parse_run(lines, CONFIG).blocks

    assert block.need["content"] == "Example::\n\n    @endneed"


def test_a_nested_open_is_body_text_and_noted() -> None:
    lines = _lines("@need req: T", "", "@need req: inner", "@endneed")

    result = parse_run(lines, CONFIG)

    (block,) = result.blocks
    assert block.need["content"] == "@need req: inner"
    assert [(issue.kind, issue.row) for issue in result.issues] == [
        (WarningSubTypeEnum.multiline_need_nested_open, 2)
    ]


def test_the_close_line_may_be_indented() -> None:
    (block,) = parse_run(
        _lines("@need req: T", "", "Body.", "   @endneed  "), CONFIG
    ).blocks

    assert block.end_col == 3 + len("@endneed")


def test_two_blocks_in_one_run() -> None:
    lines = _lines("@need req: A", "@endneed", "between", "@need req: B", "@endneed")

    result = parse_run(lines, CONFIG)

    assert [block.need["title"] for block in result.blocks] == ["A", "B"]
    assert result.claimed_rows == {0, 1, 3, 4}


def test_the_project_markers_and_markups() -> None:
    config = MultilineNeedsConfig(
        start_sequence="@spec",
        end_sequence="@endspec",
        default_markup="myst",
        markups={"myst": ".md"},
    )

    result = parse_run(_lines("@need req: X", "@spec req: Y", "@endspec"), config)

    (block,) = result.blocks
    assert (block.need["title"], block.markup, block.need["doctype"]) == (
        "Y",
        "myst",
        ".md",
    )


# --- precedence -------------------------------------------------------------------------


def test_blank_rows_keeps_the_line_count() -> None:
    text = "/**\n * @need req: A, B\n * @endneed\n * @Other, ID\n */"

    blanked = blank_rows(text, 10, {11, 12})

    assert blanked == "/**\n\n\n * @Other, ID\n */"
    assert blanked.count("\n") == text.count("\n")


# --- through the analysis ---------------------------------------------------------------


def _analysis(
    tmp_path: Path, name: str, source: str | bytes, comment_type: CommentType
) -> SourceAnalyse:
    """An analysis of one file with every extractor on, not yet run."""
    src_path = tmp_path / name
    if isinstance(source, bytes):
        src_path.write_bytes(source)
    else:
        src_path.write_text(source, encoding="utf-8")
    analyse = SourceAnalyse(
        SourceAnalyseConfig(
            src_files=[src_path],
            src_dir=tmp_path,
            comment_type=comment_type,
            get_oneline_needs=True,
            get_multiline_needs=True,
        ),
        name="p",
    )
    analyse.git_remote_url = None
    analyse.git_commit_rev = None
    return analyse


RUST_RUN = (
    "/// Parses things.\n"
    "/// @need impl: Rust block\n"
    "/// :id: IMPL_RUST\n"
    "/// @endneed\n"
    "fn parse() {}\n"
)


def test_a_rust_doc_comment_spans_only_its_own_row(tmp_path: Path) -> None:
    """A ``///`` node's text ends with its newline; it still covers one row, so the row
    above the open line neither holds claimed rows nor stands for the block."""
    analyse = _analysis(tmp_path, "lib.rs", RUST_RUN, CommentType.rust)
    analyse.create_src_objects()

    claimed = analyse.extract_multiline_needs()

    rows = {
        comment.node.start_point.row: claimed.get(id(comment), set())
        for comment in analyse.src_comments
    }
    assert rows == {0: set(), 1: {1}, 2: {2}, 3: {3}}
    (need,) = analyse.multiline_needs
    assert need.source_comment.node.start_point.row == 1
