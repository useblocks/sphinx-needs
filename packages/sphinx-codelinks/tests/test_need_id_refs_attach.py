# @Test suite for attaching need id references, TEST_NEED_ID_REFS_ATTACH_1, test, [IMPL_LNK_1]
""":func:`attach_need_id_refs` over plain records and plain needs: no build involved,
which is the point -- it is the seam a pre-analysed input file will feed."""

from typing import Any

from sphinx_codelinks.analyse.references import NeedIdRef
from sphinx_codelinks.sphinx_extension.need_id_refs import attach_need_id_refs

SHA = "a" * 40


def _ref(need_id: str, lineno: int, **kwargs: Any) -> NeedIdRef:
    path = kwargs.pop("path", "src/refs.cpp")
    values: dict[str, Any] = {
        "need_id": need_id,
        "project": "src",
        "marker": "@need-ids:",
        "path": path,
        "lineno": lineno,
        "start_column": 13,
        "end_column": 20,
        "remote_url": f"https://example.com/blob/{SHA}/{path}#L{lineno}",
    }
    values.update(kwargs)
    return NeedIdRef(**values)


def _needs(*ids: str, docname: str = "index") -> dict[str, dict[str, Any]]:
    return {need_id: {"docname": docname, "code_url": None} for need_id in ids}


def test_one_entry_per_reference_sorted_and_deduplicated() -> None:
    """Overlapping directives give every record twice; the list carries each once,
    in ``(path, lineno, start_column)`` order whatever order the records came in."""
    refs = [_ref("REQ_1", 9), _ref("REQ_1", 3), _ref("REQ_1", 3), _ref("REQ_1", 9)]
    refs.append(_ref("REQ_1", 1, path="a/first.cpp"))
    needs = _needs("REQ_1", "REQ_2")

    result = attach_need_id_refs(refs, needs, fields={"src": "code_url"})

    assert needs["REQ_1"]["code_url"] == [
        f"https://example.com/blob/{SHA}/a/first.cpp#L1",
        f"https://example.com/blob/{SHA}/src/refs.cpp#L3",
        f"https://example.com/blob/{SHA}/src/refs.cpp#L9",
    ]
    assert needs["REQ_2"]["code_url"] is None
    assert result.attached == {"src": 3}
    assert result.unknown == []


def test_unknown_ids_are_reported_not_attached() -> None:
    needs = _needs("REQ_1")
    result = attach_need_id_refs(
        [_ref("REQ_1", 1), _ref("NOSUCH", 5)], needs, fields={"src": "code_url"}
    )
    assert [(ref.need_id, ref.path, ref.lineno) for ref in result.unknown] == [
        ("NOSUCH", "src/refs.cpp", 5)
    ]
    assert result.attached == {"src": 1}


def test_ids_are_matched_as_written() -> None:
    """``::`` and ``.`` are part of the id: nothing is split or normalised."""
    needs = _needs("A::B::C.d")
    result = attach_need_id_refs(
        [_ref("A::B::C.d", 2), _ref("A::B::C", 2)], needs, fields={"src": "code_url"}
    )
    assert needs["A::B::C.d"]["code_url"] == [
        f"https://example.com/blob/{SHA}/src/refs.cpp#L2"
    ]
    assert [ref.need_id for ref in result.unknown] == ["A::B::C"]


def test_two_projects_naming_one_field_share_the_list() -> None:
    needs = _needs("REQ_1")
    attach_need_id_refs(
        [_ref("REQ_1", 4, project="one"), _ref("REQ_1", 2, project="two")],
        needs,
        fields={"one": "code_url", "two": "code_url"},
    )
    assert needs["REQ_1"]["code_url"] == [
        f"https://example.com/blob/{SHA}/src/refs.cpp#L2",
        f"https://example.com/blob/{SHA}/src/refs.cpp#L4",
    ]


def test_projects_without_a_field_are_ignored() -> None:
    needs = _needs("REQ_1")
    result = attach_need_id_refs(
        [_ref("REQ_1", 4, project="off"), _ref("NOSUCH", 2, project="off")],
        needs,
        fields={"src": "code_url"},
    )
    assert needs["REQ_1"]["code_url"] is None
    assert result.attached == {}
    assert result.unknown == []


def test_local_url_is_relative_to_the_needs_document() -> None:
    """Without a remote URL the local one is used, relative to the document the need
    is in -- as ``local-url`` is relative to the document of the need it is on."""
    refs = [_ref("REQ_1", 3, remote_url=None, local_url="src/refs.cpp#L3")]
    for docname, expected in [
        ("index", "src/refs.cpp#L3"),
        ("sub/deep", "../src/refs.cpp#L3"),
    ]:
        needs = _needs("REQ_1", docname=docname)
        attach_need_id_refs(refs, needs, fields={"src": "code_url"})
        assert needs["REQ_1"]["code_url"] == [expected]
