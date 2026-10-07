# @Test suite for the need id reference record, TEST_NEED_ID_REF_1, test, [IMPL_LNK_1]
"""The :class:`NeedIdRef` record: plain data that survives JSON unchanged."""

import json
from pathlib import Path

import pytest

from sphinx_codelinks.analyse.analyse import SourceAnalyse
from sphinx_codelinks.analyse.references import NeedIdRef, need_id_ref_records
from sphinx_codelinks.config import OneLineCommentStyle, SourceAnalyseConfig

FULL = NeedIdRef(
    need_id="A::B::C.d",
    project="src",
    marker="@need-ids:",
    path="src/refs.cpp",
    root="src_dir",
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
        "root",
        "lineno",
        "start_column",
        "end_column",
        "scope",
        "scope_rows",
        "remote_url",
        "local_url",
    }


def test_record_ignores_unknown_keys() -> None:
    """A newer producer's key (slice 2 plans ``relation``) does not break a reader."""
    data = FULL.to_dict() | {"relation": "implements"}
    assert NeedIdRef.from_dict(data) == FULL


@pytest.mark.parametrize(
    ("key", "value"),
    [
        pytest.param("path", "/etc/passwd", id="absolute-path"),
        pytest.param("lineno", "3", id="lineno-as-string"),
        pytest.param("lineno", True, id="lineno-as-bool"),
        pytest.param("path", "C:/src/a.cpp", id="drive"),
        pytest.param("path", "C:\\src\\a.cpp", id="windows-drive-path"),
        pytest.param("path", "../outside.cpp", id="dotdot"),
        pytest.param("path", "src/../x.cpp", id="dotdot-inside"),
        pytest.param("need_id", 5, id="int-id"),
        pytest.param("need_id", "", id="empty-id"),
        pytest.param("root", "home", id="unknown-root"),
    ],
)
def test_record_checks_its_invariants(key: str, value: object) -> None:
    data = FULL.to_dict() | {key: value}
    with pytest.raises(ValueError, match=repr(key)):
        NeedIdRef.from_dict(data)


@pytest.mark.parametrize("path", ["a:b.cpp", "we\\ird.cpp", "src\\a.cpp", "x..y.cpp"])
def test_record_accepts_legal_posix_names(path: str) -> None:
    """``:`` and ``\\`` are legal POSIX name characters: what the producer can emit for
    such a file reads back."""
    record = FULL.to_dict() | {"path": path}
    assert NeedIdRef.from_dict(json.loads(json.dumps(record))).path == path


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
    assert first.root == "git"
    assert first.remote_url == "remote:refs.cpp:1"
    assert first.local_url == "local:refs.cpp:1"
    assert NeedIdRef.from_dict(json.loads(json.dumps(first.to_dict()))) == first


def test_a_need_ids_comment_is_never_a_one_line_need(tmp_path: Path) -> None:
    """On the default one-line style (start sequence ``@``) a comment starting with
    the ``@need-ids:`` marker is a reference, never a need (ubCode's precedence); a
    real one-line need beside it still parses."""
    src = tmp_path / "src"
    src.mkdir()
    source = src / "refs.cpp"
    source.write_text(
        "// @need-ids: REQ_001, IMPL_X\n"
        "void a() {}\n"
        "// @A real one-line need, IMPL_REAL\n"
        "void b() {}\n",
        encoding="utf-8",
    )
    analyse = SourceAnalyse(
        SourceAnalyseConfig(
            src_files=[source], src_dir=src, git_root=tmp_path, get_oneline_needs=True
        )
    )
    analyse.run()

    refs = need_id_ref_records(analyse.need_id_refs, project="src", root=tmp_path)
    assert [ref.need_id for ref in refs] == ["REQ_001", "IMPL_X"]
    assert [need.need["id"] for need in analyse.oneline_needs] == ["IMPL_REAL"]


def test_scope_is_the_first_line_only(tmp_path: Path) -> None:
    """A 100-line function: ``scope`` is its signature, ``scope_rows`` spans it all."""
    src = tmp_path / "src"
    src.mkdir()
    body = "".join(f"    x += {n};\n" for n in range(98))
    source = src / "big.cpp"
    source.write_text(
        f"// @need-ids: REQ_1\nint big(int x) {{   \n{body}}}\n", encoding="utf-8"
    )
    analyse = SourceAnalyse(
        SourceAnalyseConfig(src_files=[source], src_dir=src, git_root=tmp_path)
    )
    analyse.run()

    (record,) = need_id_ref_records(analyse.need_id_refs, project="p", root=tmp_path)
    assert record.scope == "int big(int x) {"
    assert record.scope_rows == (2, 101)


def _analyse(tmp_path: Path, text: str, **config: object) -> SourceAnalyse:
    src = tmp_path / "src"
    src.mkdir(exist_ok=True)
    source = src / "mixed.cpp"
    source.write_text(text, encoding="utf-8")
    analyse = SourceAnalyse(
        SourceAnalyseConfig(
            src_files=[source],
            src_dir=src,
            git_root=tmp_path,
            get_oneline_needs=True,
            **config,  # ty: ignore[invalid-argument-type]
        )
    )
    analyse.run()
    return analyse


def test_a_need_and_a_marker_in_one_comment_are_both_kept(tmp_path: Path) -> None:
    """Only a line that STARTS with the marker is withheld from the one-line parser: a
    one-line need ahead of a marker on the same line keeps its need and gives the
    reference; in one block comment, a need line and a marker line keep theirs, on
    their own rows."""
    bracketed = _analyse(
        tmp_path,
        "// [[impl one, IMPL_001]] @need-ids: REQ_001\nvoid a() {}\n",
        oneline_comment_style=OneLineCommentStyle(
            start_sequence="[[", end_sequence="]]"
        ),
    )
    assert [need.need["id"] for need in bracketed.oneline_needs] == ["IMPL_001"]
    assert [ref.need_ids for ref in bracketed.need_id_refs] == [["REQ_001"]]

    block = _analyse(
        tmp_path,
        "// @need-ids: REQ_001, IMPL_X\n"
        "void a() {}\n"
        "// @Real need, IMPL_REAL\n"
        "void b() {}\n"
        "/*\n"
        " * @need-ids: REQ_002, IMPL_Y\n"
        " * @Second real, IMPL_TWO\n"
        " */\n"
        "void c() {}\n"
        "// see @need-ids: REQ_003, IMPL_Z\n"
        "/*\n"
        " * @Third real, IMPL_THREE\n"
        " * @need-ids: REQ_004\n"
        " */\n"
        "void d() {}\n",
    )
    needs = {
        need.need["id"]: need.source_map["start"]["row"] + 1
        for need in block.oneline_needs
    }
    assert needs == {"IMPL_REAL": 3, "IMPL_TWO": 7, "IMPL_THREE": 12}
    refs = {
        tuple(ref.need_ids): ref.source_map["start"]["row"] + 1
        for ref in block.need_id_refs
    }
    assert refs == {
        ("REQ_001", "IMPL_X"): 1,
        ("REQ_002", "IMPL_Y"): 6,
        ("REQ_003", "IMPL_Z"): 10,
        ("REQ_004",): 13,
    }


def test_only_a_line_starting_with_the_marker_is_a_reference_line(
    tmp_path: Path,
) -> None:
    """Pins the current rule: decoration and whitespace may precede the marker; a word
    may not (``// see @need-ids: X`` is not withheld from the one-line parser -- which
    ignores it anyway -- and its references are still extracted, as above)."""
    analyse = _analyse(tmp_path, "// nothing\n")
    assert analyse._is_need_id_refs_line("// @need-ids: X")
    assert analyse._is_need_id_refs_line(" * @need-ids: X")
    assert analyse._is_need_id_refs_line("# @need-ids: X")
    assert not analyse._is_need_id_refs_line("// see @need-ids: X")
    assert not analyse._is_need_id_refs_line("// [[a, B]] @need-ids: X")
