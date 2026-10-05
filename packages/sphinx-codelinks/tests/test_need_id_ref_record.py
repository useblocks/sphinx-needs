# @Test suite for the need id reference record, TEST_NEED_ID_REF_1, test, [IMPL_LNK_1]
"""The :class:`NeedIdRef` record: plain data that survives JSON unchanged."""

import json
from pathlib import Path

import pytest

from sphinx_codelinks.analyse.analyse import SourceAnalyse
from sphinx_codelinks.analyse.references import NeedIdRef, need_id_ref_records
from sphinx_codelinks.config import SourceAnalyseConfig

FULL = NeedIdRef(
    need_id="A::B::C.d",
    project="src",
    marker="@need-ids:",
    path="src/refs.cpp",
    lineno=4,
    start_column=14,
    end_column=31,
    scope="int helper(int a) { return a + 1; }",
    scope_rows=(5, 5),
    remote_url="https://github.com/o/r/blob/" + "a" * 40 + "/src/refs.cpp#L4",
    local_url="src/refs.cpp#L4",
)


@pytest.mark.parametrize(
    "record",
    [
        pytest.param(FULL, id="every-field"),
        pytest.param(
            NeedIdRef(
                need_id="REQ_1",
                project="p",
                marker="@need-ids:",
                path="a.py",
                lineno=1,
                start_column=12,
                end_column=17,
            ),
            id="optional-fields-unset",
        ),
    ],
)
def test_record_round_trips_through_json_byte_for_byte(record: NeedIdRef) -> None:
    """``to_dict`` -> ``json`` -> ``from_dict`` -> ``to_dict`` -> ``json`` is the
    identity, and gives back an equal record: nothing in it is not data."""
    text = json.dumps(record.to_dict(), sort_keys=True)
    again = NeedIdRef.from_dict(json.loads(text))
    assert again == record
    assert json.dumps(again.to_dict(), sort_keys=True) == text
    assert set(json.loads(text)) == {
        "need_id",
        "project",
        "marker",
        "path",
        "lineno",
        "start_column",
        "end_column",
        "scope",
        "scope_rows",
        "remote_url",
        "local_url",
    }


def test_record_refuses_unknown_keys() -> None:
    data = FULL.to_dict() | {"relation": "implements"}
    with pytest.raises(ValueError, match="relation"):
        NeedIdRef.from_dict(data)


def test_records_from_an_analysis(tmp_path: Path) -> None:
    """One record per id; the ids pass through untouched (``::`` and ``.`` included);
    the path is relative and POSIX; the line, the columns and the scope are kept."""
    src = tmp_path / "src"
    src.mkdir()
    source = src / "refs.cpp"
    source.write_text(
        "// @need-ids: A::B::C.d, REQ_1\nvoid implements_a() {}\n", encoding="utf-8"
    )
    analyse = SourceAnalyse(
        SourceAnalyseConfig(src_files=[source], src_dir=src, git_root=tmp_path)
    )
    analyse.run()

    records = need_id_ref_records(
        analyse.need_id_refs,
        project="src",
        root=tmp_path,
        remote_url=lambda path, line: f"remote:{path.name}:{line}",
        local_url=lambda path, line: f"local:{path.name}:{line}",
    )

    assert [record.need_id for record in records] == ["A::B::C.d", "REQ_1"]
    first = records[0]
    assert first.project == "src"
    assert first.marker == "@need-ids:"
    assert first.path == "src/refs.cpp"
    assert first.lineno == 1
    assert (first.start_column, first.end_column) == (13, 29)
    assert first.scope == "void implements_a() {}"
    assert first.scope_rows == (2, 2)
    assert first.remote_url == "remote:refs.cpp:1"
    assert first.local_url == "local:refs.cpp:1"
    assert NeedIdRef.from_dict(json.loads(json.dumps(first.to_dict()))) == first
