"""``ub_needs_exchange``: what the conformance corpus cannot state.

Every rule of reading a needs exchange file (needs.json) is pinned by the corpus,
``tests/fixtures/needs_json_reading_conformance.toml``, which ``test_conformance.py`` runs
and ubCode is to vendor. A corpus case compares codes, paths and values; what it cannot
state is tested here: the messages (sphinx-needs prints them in its warnings), bytes that
are not UTF-8, files that cannot be read, a ``null`` default (TOML has no null), the
``apply_schema_defaults`` option, and which objects a record shares with the document.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

import ub_needs_exchange as nx
from ub_needs_exchange import reader


def envelope(
    needs: Any, *, version: str = "1.0", current: Any = "1.0", **version_keys: Any
) -> dict[str, Any]:
    """A one-version document."""
    return {
        "project": "source",
        "current_version": current,
        "versions": {version: {"needs": needs, **version_keys}},
    }


def record(need_id: str, **fields: Any) -> dict[str, Any]:
    return {"id": need_id, "type": "req", "title": f"title {need_id}", **fields}


def test_the_package_exports_the_reader():
    assert set(nx.__all__) == {*reader.__all__, "__version__"}
    assert all(getattr(nx, name) is getattr(reader, name) for name in reader.__all__)


# ------------------------------------------------------------------------------------
# the source: parse and load


def test_parse_reads_utf8_bytes():
    doc = nx.parse(json.dumps(envelope({"A": record("A", title="é")})).encode("utf-8"))
    assert doc.select_version(None).records()[0].fields["title"] == "é"


def test_parse_refuses_bytes_that_are_not_utf8():
    with pytest.raises(nx.ExchangeError) as info:
        nx.parse(b"\xff\xfe{}")
    assert info.value.code == "invalid_json"
    assert info.value.message.startswith("not valid UTF-8: ")
    assert isinstance(info.value, Exception)


def test_invalid_json_names_the_decoder_error():
    try:
        json.loads("{ not json")
    except json.JSONDecodeError as err:
        expected = f"not valid JSON: {err}"
    with pytest.raises(nx.ExchangeError) as info:
        nx.parse("{ not json")
    assert info.value.message == expected
    assert str(info.value) == expected


def test_the_top_level_message():
    with pytest.raises(nx.ExchangeError) as info:
        nx.parse("[1, 2]")
    assert (info.value.code, info.value.message) == (
        "not_an_object",
        "the top level is not a JSON object",
    )


def test_load_reads_utf8(tmp_path: Path):
    path = tmp_path / "needs.json"
    path.write_text(
        json.dumps(envelope({"A": record("A", title="Grüße")}), ensure_ascii=False),
        encoding="utf-8",
    )
    doc = nx.load(str(path))
    assert doc.select_version(None).records()[0].fields["title"] == "Grüße"


def test_load_of_a_missing_file_is_invalid_json(tmp_path: Path):
    with pytest.raises(nx.ExchangeError) as info:
        nx.load(str(tmp_path / "absent.json"))
    assert info.value.code == "invalid_json"
    assert info.value.message.startswith("cannot be read: ")


def test_load_of_a_file_that_is_not_utf8_is_invalid_json(tmp_path: Path):
    path = tmp_path / "needs.json"
    path.write_bytes(b'{"current_version": "\xff"}')
    with pytest.raises(nx.ExchangeError) as info:
        nx.load(path)
    assert info.value.code == "invalid_json"
    assert info.value.message.startswith("not valid UTF-8: ")


def test_a_byte_order_mark_is_invalid_json(tmp_path: Path):
    text = "\ufeff" + json.dumps(envelope({"A": record("A")}))
    path = tmp_path / "needs.json"
    path.write_text(text, encoding="utf-8")
    for read in (
        lambda: nx.parse(text),
        lambda: nx.parse(text.encode("utf-8")),
        lambda: nx.load(path),
    ):
        with pytest.raises(nx.ExchangeError) as info:
            read()
        assert info.value.code == "invalid_json"


def test_utf16_bytes_are_invalid_json():
    with pytest.raises(nx.ExchangeError) as info:
        nx.parse(json.dumps(envelope({"A": record("A")})).encode("utf-16"))
    assert info.value.code == "invalid_json"


def test_a_duplicated_key_keeps_its_last_value():
    """At the top level and in ``versions`` too, not only in a record (the corpus's case)."""
    text = (
        '{"current_version": "2.0", "versions": {"1.0": {"needs": {"A": {}}}, '
        '"1.0": {"needs": {"B": {}}}}, "current_version": "1.0"}'
    )
    version = nx.parse(text).select_version(None)
    assert version.name == "1.0"
    assert [r.key for r in version.records()] == ["B"]


# ------------------------------------------------------------------------------------
# the messages of a refusal


@pytest.mark.parametrize(
    ("data", "requested", "code", "message"),
    [
        pytest.param(
            {"current_version": "1.0"},
            None,
            "versions_missing",
            "'versions' is missing or not an object",
            id="versions_missing",
        ),
        pytest.param(
            {"versions": {"1.0": {"needs": {}}}},
            None,
            "current_version_missing",
            "no version is requested and 'current_version' is missing, empty or not a string",
            id="current_version_missing",
        ),
        pytest.param(
            {"current_version": "3.0", "versions": {"1.0": {"needs": {}}}},
            None,
            "version_not_found",
            "Version '3.0' not found in the file: ['1.0']",
            id="current_not_found",
        ),
        pytest.param(
            {"current_version": "1.0", "versions": {"1.0": {"needs": {}}}},
            "9.9",
            "version_not_found",
            "Version '9.9' not found in the file: ['1.0']",
            id="requested_not_found",
        ),
        pytest.param(
            {"current_version": "1.0", "versions": {"1.0": "x"}},
            None,
            "needs_missing",
            "Version 1.0 has no 'needs' object",
            id="needs_missing",
        ),
    ],
)
def test_select_version_refuses(data, requested, code, message):
    doc = nx.parse(json.dumps(data))
    with pytest.raises(nx.ExchangeError) as info:
        doc.select_version(requested)
    assert (info.value.code, info.value.message) == (code, message)


@pytest.mark.parametrize(
    ("stated", "shown"),
    [
        pytest.param("1", "'1'", id="string"),
        pytest.param(0, "0", id="zero"),
        pytest.param(1.0, "1.0", id="float"),
        pytest.param(True, "True", id="bool"),
        pytest.param(None, "None", id="null"),
    ],
)
def test_a_format_version_that_is_not_a_positive_integer_refuses_the_file(
    stated, shown
):
    data = {"format_version": stated, **envelope({"A": record("A")})}
    with pytest.raises(nx.ExchangeError) as info:
        nx.parse(json.dumps(data)).select_version(None)
    assert (info.value.code, info.value.message) == (
        "format_version_invalid",
        f"'format_version' is {shown}, not an integer of 1 or more",
    )


# ------------------------------------------------------------------------------------
# the messages of a finding


def test_a_later_format_version_is_read_as_the_first():
    data = {"format_version": 2, **envelope({"A": record("A")})}
    version = nx.parse(json.dumps(data)).select_version(None)
    assert [r.key for r in version.records()] == ["A"]
    assert version.diagnostics == (
        nx.Diagnostic(
            code="format_version_unsupported",
            path="format_version",
            message=(
                "the file is of format version 2; this reader reads format version 1, "
                "and reads the file as that"
            ),
        ),
    )


def test_a_record_that_is_not_an_object_is_skipped():
    version = nx.parse(
        json.dumps(envelope({"STR_001": "just a string", "A": record("A")}))
    ).select_version(None)
    assert [r.key for r in version.records()] == ["A"]
    assert version.diagnostics == (
        nx.Diagnostic(
            code="record_not_object",
            path="versions.1.0.needs.STR_001",
            message="the need 'STR_001' is not an object; it is skipped",
        ),
    )


@pytest.mark.parametrize(
    ("given", "message"),
    [
        pytest.param(
            "OTHER",
            "the need keyed 'A' has the id 'OTHER'; the key is its id",
            id="other_string",
        ),
        pytest.param(
            5, "the need keyed 'A' has the id 5; the key is its id", id="number"
        ),
        pytest.param(
            None, "the need keyed 'A' has the id None; the key is its id", id="null"
        ),
    ],
)
def test_the_key_is_the_id(given, message):
    fields = {"type": "req", "title": "t", "id": given}
    (rec,) = (
        nx.parse(json.dumps(envelope({"A": fields}))).select_version(None).records()
    )
    assert (rec.key, rec.fields["id"]) == ("A", "A")
    assert rec.diagnostics == (
        nx.Diagnostic(
            code="id_mismatch", path="versions.1.0.needs.A.id", message=message
        ),
    )


def test_defaults_removed_without_a_schema():
    version = nx.parse(
        json.dumps(envelope({"A": record("A")}, needs_defaults_removed=True))
    ).select_version(None)
    assert len(version.records()) == 1
    assert version.diagnostics == (
        nx.Diagnostic(
            code="defaults_removed_without_schema",
            path="versions.1.0.needs_defaults_removed",
            message=(
                "Version 1.0 was written without its default values "
                "('needs_defaults_removed') and has no 'needs_schema' to restore them "
                "from; the reading project's defaults are used"
            ),
        ),
    )


# ------------------------------------------------------------------------------------
# records: what the API offers beyond the corpus

SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "properties": {
        "status": {"type": ["string", "null"], "default": None},
        "priority": {"type": ["string", "null"], "default": "medium"},
        "tags": {"type": "array", "default": []},
    },
}


def test_map_legacy_keys_in_place():
    fields = {"description": "legacy"}
    nx.map_legacy_keys(fields)
    assert fields == {"content": "legacy"}


def test_a_null_default_is_merged():
    (rec,) = (
        nx.parse(json.dumps(envelope({"A": record("A")}, needs_schema=SCHEMA)))
        .select_version(None)
        .records()
    )
    assert "status" in rec.fields
    assert rec.fields["status"] is None


def test_schema_defaults_can_be_left_out():
    version = nx.parse(
        json.dumps(envelope({"A": record("A")}, needs_schema=SCHEMA))
    ).select_version(None)
    assert "priority" not in version.records(apply_schema_defaults=False)[0].fields
    assert version.records()[0].fields["priority"] == "medium"


def test_records_do_not_alter_the_document():
    doc = nx.parse(json.dumps(envelope({"A": {"description": "x"}})))
    doc.select_version(None).records()[0].fields["title"] = "changed"
    assert doc.data["versions"]["1.0"]["needs"]["A"] == {"description": "x"}


def test_a_default_is_one_object_in_every_record():
    """The values are shared, not copied (the contract's section 6.6): a reader replaces a
    value rather than changing it in place."""
    doc = nx.parse(
        json.dumps(envelope({"A": record("A"), "B": record("B")}, needs_schema=SCHEMA))
    )
    a, b = doc.select_version(None).records()
    schema_tags = doc.data["versions"]["1.0"]["needs_schema"]["properties"]["tags"]
    assert a.fields["tags"] is b.fields["tags"] is schema_tags["default"]
