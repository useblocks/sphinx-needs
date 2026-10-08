# @Test suite for the source order of marked content on one row, TEST_ANA_ORDER_1, test, [IMPL_LNK_1, IMPL_ONE_1]
"""Marked content on one row is listed in source order, on every run (#2150).

Tree-sitter hands the comments of a file over in an order that differs between two
parses of the same source, so two entries on one row used to come out in a different
order from run to run. Each construction is analysed ``RUNS`` times in one process: every
run must give the same order, and that order must be the source order -- by row, then
by column.
"""

from pathlib import Path
from typing import Any

import pytest

from sphinx_codelinks.analyse.analyse import SourceAnalyse
from sphinx_codelinks.config import (
    NeedIdRefsConfig,
    OneLineCommentStyle,
    SourceAnalyseConfig,
)
from sphinx_codelinks.source_discover.config import CommentType

RUNS = 20
ROWS = 15

#: the ``[[``...``]]`` style of the corpus case ``positions-need_and_ref_on_one_row``
BRACKETS = {
    "start_sequence": "[[",
    "end_sequence": "]]",
    "needs_fields": [
        {"name": "id"},
        {"name": "title"},
        {"name": "type", "default": "impl"},
        {"name": "links", "type": "list[str]", "default": []},
    ],
}


def _rows(template: str) -> str:
    return "".join(template.format(i=i) + "\n" for i in range(ROWS))


#: name -> (source, configuration keywords); every row holds two comments
CONSTRUCTIONS: dict[str, tuple[str, dict[str, Any]]] = {
    "two_need_refs": (
        _rows("/* @need-ids: REQ_A{i} */ /* @need-ids: REQ_B{i} */"),
        {"get_need_id_refs": True},
    ),
    "two_needs": (
        _rows("/* @A{i}, IMPL_A{i}, impl */ /* @B{i}, IMPL_B{i}, impl */"),
        {"get_oneline_needs": True},
    ),
    "need_then_ref": (
        _rows("/* [[IMPL_X{i}, X]] */ /* @need-ids: REQ_{i} */"),
        {
            "get_oneline_needs": True,
            "get_need_id_refs": True,
            "oneline_comment_style": OneLineCommentStyle(**BRACKETS),
        },
    ),
    "ref_then_need": (
        _rows("/* @need-ids: REQ_{i} */ /* [[IMPL_X{i}, X]] */"),
        {
            "get_oneline_needs": True,
            "get_need_id_refs": True,
            "oneline_comment_style": OneLineCommentStyle(**BRACKETS),
        },
    ),
}


def _analyse(root: Path, source: str, **config: Any) -> SourceAnalyse:
    path = root / "case.cpp"
    path.write_bytes(source.encode("utf-8"))
    analyse = SourceAnalyse(
        SourceAnalyseConfig(
            src_files=[path],
            src_dir=root,
            comment_type=CommentType.cpp,
            **config,
        )
    )
    analyse.git_remote_url = None
    analyse.git_commit_rev = None
    analyse.run(log_summary=False)
    return analyse


def _starts(entries: list[Any]) -> list[tuple[int, int]]:
    return [
        (entry.source_map["start"]["row"], entry.source_map["start"]["column"])
        for entry in entries
    ]


@pytest.mark.parametrize("name", CONSTRUCTIONS)
def test_one_row_is_listed_in_source_order_every_run(tmp_path: Path, name: str) -> None:
    """``all_marked_content`` -- what ``marked_content.json`` holds -- is in source
    order on every run; so is ``oneline_needs``, the order ``src-trace`` creates the
    needs in."""
    source, config = CONSTRUCTIONS[name]
    runs = [_analyse(tmp_path, source, **config) for _ in range(RUNS)]

    orders = [_starts(run.all_marked_content) for run in runs]
    assert len(orders[0]) == 2 * ROWS
    assert orders[0] == sorted(orders[0])
    assert all(order == orders[0] for order in orders)

    needs = [_starts(run.oneline_needs) for run in runs]
    assert needs[0] == sorted(needs[0])
    assert all(order == needs[0] for order in needs)


def test_a_reference_and_a_need_starting_at_one_position_list_the_reference_first(
    tmp_path: Path,
) -> None:
    """Two entries can start at one position only with overlapping markers, which the
    configuration check does not refuse today: here a need-id marker that ends with the
    one-line start sequence. Such a tie is listed references first, then one-line needs
    (then multi-line needs) -- the rule ubCode's parity harness mirrors. This case goes
    when overlapping markers become a configuration error.

    Two references tying (one marker a suffix of another) need no case: they are of one
    kind, and keep the marker order of the configuration through the stable sort.
    """
    analyse = _analyse(
        tmp_path,
        "// x ref[[IMPL_T, Tie]]\nvoid f() {}\n",
        get_oneline_needs=True,
        get_need_id_refs=True,
        oneline_comment_style=OneLineCommentStyle(**BRACKETS),
        need_id_refs_config=NeedIdRefsConfig(markers=["ref[["]),
    )

    assert [
        (entry.type.value, entry.source_map["start"])
        for entry in analyse.all_marked_content
    ] == [
        ("need-id-refs", {"row": 0, "column": 10}),
        ("need", {"row": 0, "column": 10}),
    ]
