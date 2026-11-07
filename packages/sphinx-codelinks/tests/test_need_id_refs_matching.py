"""How reference markers are found on a comment line, clause by clause.

A match of a marker needs a word boundary after a marker that ends in a word character;
at one index the longest marker wins and the scan resumes after it; each match's ids
run to the next match on the line; every match yields its references; and a line is a
reference line when its first match has nothing alphanumeric before it. With a field
per marker, two markers on one line must not share their ids, or one reference lands in
two fields.
"""

from pathlib import Path

import pytest

from sphinx_codelinks.analyse.analyse import SourceAnalyse, find_marker_matches
from sphinx_codelinks.config import NeedIdRefsConfig, SourceAnalyseConfig

SATISFIES = "\\satisfies"
VERIFIES = "\\verifies"
VERIFIESALL = "\\verifiesall"


def _analyse(tmp_path: Path, markers: list[str]) -> SourceAnalyse:
    """An analysis over one empty C++ file, for its ``extract_marker``."""
    source = tmp_path / "empty.cpp"
    source.write_text("", encoding="utf-8")
    return SourceAnalyse(
        SourceAnalyseConfig(
            src_files=[source],
            src_dir=tmp_path,
            git_root=tmp_path,
            need_id_refs_config=NeedIdRefsConfig(markers=markers),
        )
    )


def _extract(tmp_path: Path, markers: list[str], text: str) -> list[tuple]:
    return list(_analyse(tmp_path, markers).extract_marker(text))


# R3.1 -- a match, and the word boundary after a word-final marker


@pytest.mark.parametrize(
    ("line", "matched"),
    [
        pytest.param("\\verifies REQ_1", True, id="space-after"),
        pytest.param("\\verifies", True, id="line-ends"),
        pytest.param("\\verifies,REQ_1", True, id="punctuation-after"),
        pytest.param("\\verifiesall REQ_1", False, id="letter-after"),
        pytest.param("\\verifies_x REQ_1", False, id="underscore-after"),
        pytest.param("\\verifies2 REQ_1", False, id="digit-after"),
        pytest.param("\\verifiesé REQ_1", False, id="non-ascii-letter-after"),
        pytest.param("x\\verifies REQ_1", True, id="no-condition-before"),
    ],
)
def test_a_word_final_marker_needs_a_boundary_after_it(
    line: str, matched: bool
) -> None:
    """``\\verifies`` ends in a word character, so a word character after it means
    the text is another word, which the marker does not match."""
    assert bool(find_marker_matches(line, [VERIFIES])) is matched


@pytest.mark.parametrize(
    "line",
    ["@need-ids:REQ_1", "@need-ids:x", "@need-ids:_"],
)
def test_a_marker_ending_in_punctuation_needs_no_boundary(line: str) -> None:
    """``:`` is not a word character: the id may follow the marker directly."""
    assert find_marker_matches(line, ["@need-ids:"]) == [("@need-ids:", 0, 10)]


def test_a_boundary_failure_does_not_hide_a_later_occurrence() -> None:
    """The first occurrence fails the boundary; the scan still finds the second."""
    line = "\\verifiesall A \\verifies B"
    assert find_marker_matches(line, [VERIFIES]) == [(VERIFIES, 15, 24)]


def test_an_empty_marker_never_matches() -> None:
    assert find_marker_matches("anything", [""]) == []


# R3.2 -- longest at one index, then resume after the match


def test_the_longest_marker_wins_at_one_index() -> None:
    line = "\\verifiesall REQ_3"
    for markers in ([VERIFIES, VERIFIESALL], [VERIFIESALL, VERIFIES]):
        assert find_marker_matches(line, markers) == [(VERIFIESALL, 0, 12)]


def test_the_longest_marker_wins_even_without_a_boundary_rule() -> None:
    """``@x`` and ``@x:`` both match at 0 (``:`` is no word character): the longer
    one wins, whatever the configuration order."""
    for markers in (["@x", "@x:"], ["@x:", "@x"]):
        assert find_marker_matches("@x: A", markers) == [("@x:", 0, 3)]


def test_matches_never_overlap() -> None:
    """The scan resumes at the end of a match: ``ab`` inside ``xab`` is not matched."""
    assert find_marker_matches("xab", ["xab", "ab"]) == [("xab", 0, 3)]


def test_matches_are_listed_left_to_right() -> None:
    line = "\\verifies A \\satisfies B"
    assert find_marker_matches(line, [SATISFIES, VERIFIES]) == [
        (VERIFIES, 0, 9),
        (SATISFIES, 12, 22),
    ]


def test_first_only_stops_at_the_first_match() -> None:
    line = "\\verifies A \\satisfies B"
    assert find_marker_matches(line, [SATISFIES, VERIFIES], first_only=True) == [
        (VERIFIES, 0, 9)
    ]


# R3.3 -- ids run to the next match; the ids' own handling is unchanged


def test_ids_stop_at_the_next_match(tmp_path: Path) -> None:
    text = "\\satisfies REQ_1 \\verifies REQ_2"
    assert _extract(tmp_path, [SATISFIES, VERIFIES], text) == [
        (SATISFIES, ["REQ_1"], 0, 11, 16),
        (VERIFIES, ["REQ_2"], 0, 27, 32),
    ]


def test_the_block_comment_end_is_stripped_from_the_last_match_only(
    tmp_path: Path,
) -> None:
    text = "/* \\satisfies REQ_1 \\verifies REQ_2 */"
    assert _extract(tmp_path, [SATISFIES, VERIFIES], text) == [
        (SATISFIES, ["REQ_1"], 0, 14, 19),
        (VERIFIES, ["REQ_2"], 0, 30, 35),
    ]


def test_a_closer_before_the_next_match_is_an_id(tmp_path: Path) -> None:
    """Only the last segment can end a block comment; ``*/`` elsewhere is text."""
    text = "\\satisfies REQ_1 */ \\verifies REQ_2"
    assert _extract(tmp_path, [SATISFIES, VERIFIES], text)[0][1] == ["REQ_1", "*/"]


def test_a_match_without_ids_yields_nothing_and_ends_the_previous_ids(
    tmp_path: Path,
) -> None:
    """``\\verifies`` holds no id, but still ends ``\\satisfies``' ids."""
    text = "\\satisfies REQ_1, REQ_2 \\verifies"
    assert _extract(tmp_path, [SATISFIES, VERIFIES], text) == [
        (SATISFIES, ["REQ_1", "REQ_2"], 0, 11, 23),
    ]


def test_commas_and_whitespace_split_ids_within_a_segment(tmp_path: Path) -> None:
    text = "\\satisfies A,B  C , D \\verifies E"
    assert [ids for _, ids, *_ in _extract(tmp_path, [SATISFIES, VERIFIES], text)] == [
        ["A", "B", "C", "D"],
        ["E"],
    ]


def test_a_rejected_prefix_is_not_a_match_and_its_text_is_no_id(
    tmp_path: Path,
) -> None:
    """``\\verifiesall REQ_2`` with marker ``\\verifies`` yields no reference, where
    the old rule read the ids ``all`` and ``REQ_2``."""
    assert _extract(tmp_path, [VERIFIES], "\\verifiesall REQ_2") == []


# R3.4 -- every match yields its references, columns per match


def test_the_same_marker_twice_yields_both(tmp_path: Path) -> None:
    text = "\\satisfies REQ_1 \\satisfies REQ_2"
    assert _extract(tmp_path, [SATISFIES], text) == [
        (SATISFIES, ["REQ_1"], 0, 11, 16),
        (SATISFIES, ["REQ_2"], 0, 28, 33),
    ]


def test_matches_on_several_rows_keep_their_row(tmp_path: Path) -> None:
    text = "\\satisfies A \\verifies B\n  \\verifies C"
    assert [
        (marker, ids, row) for marker, ids, row, *_ in _extract(
            tmp_path, [SATISFIES, VERIFIES], text
        )
    ] == [(SATISFIES, ["A"], 0), (VERIFIES, ["B"], 0), (VERIFIES, ["C"], 1)]


@pytest.mark.parametrize(
    "text",
    [
        "// @need-ids: REQ_1, REQ_2",
        "/* @need-ids: REQ_1 REQ_2 */",
        "// see @need-ids: REQ_1",
        "// @need-ids: REQ_1 */",
        "/* @need-ids: */",
        "// @need-ids:REQ_1",
    ],
)
def test_one_occurrence_extracts_as_before(tmp_path: Path, text: str) -> None:
    """R3.6: one marker occurrence, no word character after a word-final marker --
    the old rule's result exactly (``find``, ids to the end of the line)."""
    marker = "@need-ids:"
    idx = text.find(marker)
    after = text[idx + len(marker) :]
    ids_text = after.strip()
    if ids_text.endswith("*/"):
        ids_text = ids_text[:-2].rstrip()
    ids = ids_text.replace(",", " ").split()
    start = idx + len(marker) + len(after) - len(after.lstrip())
    expected = [(marker, ids, 0, start, start + len(ids_text))] if ids else []
    assert _extract(tmp_path, [marker], text) == expected


# R3.5 -- the reference-line test uses the same match


@pytest.mark.parametrize(
    ("line", "is_reference"),
    [
        pytest.param("// \\verifies REQ_1", True, id="marker-first"),
        pytest.param("// \\verifiesall REQ_1", False, id="prefix-is-no-match"),
        pytest.param(
            "// \\verifiesall REQ_1 \\verifies REQ_2", False, id="prefix-is-text"
        ),
        pytest.param("// see \\verifies REQ_1", False, id="word-before"),
        pytest.param(
            "// \\satisfies A see \\verifies B", True, id="second-match-after-word"
        ),
    ],
)
def test_the_reference_line_test_uses_the_first_match(
    tmp_path: Path, line: str, is_reference: bool
) -> None:
    analyse = _analyse(tmp_path, [SATISFIES, VERIFIES])
    assert analyse._is_need_id_refs_line(line) is is_reference
