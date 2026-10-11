"""``sphinx_needs.exchange``: reading the envelope of a needs exchange file (needs.json).

The module returns what it finds -- a ``Document``, a selected ``Version``, its
``Record`` values and ``Diagnostic`` values -- and raises one ``ExchangeError`` for a
source no record can be read from. It knows nothing of the reading project: these
documents are small and inline, and no Sphinx application is built.
"""

from __future__ import annotations

import ast
import importlib
import json
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest


@pytest.fixture
def nx() -> ModuleType:
    """The module under test, imported per test so that each test fails on its own
    while the module does not exist."""
    return importlib.import_module("sphinx_needs.exchange")


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


# ------------------------------------------------------------------------------------
# the source: parse and load


def test_parse_reads_an_object(nx):
    doc = nx.parse(json.dumps(envelope({"A": record("A")})))
    assert doc.data["current_version"] == "1.0"


def test_parse_reads_utf8_bytes(nx):
    doc = nx.parse(json.dumps(envelope({"A": record("A", title="é")})).encode("utf-8"))
    assert doc.select_version(None).records()[0].fields["title"] == "é"


@pytest.mark.parametrize(
    ("text", "code"),
    [
        pytest.param("{ not json", "invalid_json", id="invalid_json"),
        pytest.param(b"\xff\xfe{}", "invalid_json", id="not_utf8"),
        pytest.param("[1, 2]", "not_an_object", id="list"),
        pytest.param('"text"', "not_an_object", id="string"),
    ],
)
def test_parse_refuses(nx, text, code):
    with pytest.raises(nx.ExchangeError) as info:
        nx.parse(text)
    assert info.value.code == code
    assert isinstance(info.value, Exception)


def test_invalid_json_names_the_decoder_error(nx):
    try:
        json.loads("{ not json")
    except json.JSONDecodeError as err:
        expected = f"not valid JSON: {err}"
    with pytest.raises(nx.ExchangeError) as info:
        nx.parse("{ not json")
    assert info.value.message == expected
    assert str(info.value) == expected


def test_load_reads_utf8(nx, tmp_path: Path):
    path = tmp_path / "needs.json"
    path.write_text(
        json.dumps(envelope({"A": record("A", title="Grüße")}), ensure_ascii=False),
        encoding="utf-8",
    )
    doc = nx.load(str(path))
    assert doc.select_version(None).records()[0].fields["title"] == "Grüße"


def test_load_of_a_missing_file_is_invalid_json(nx, tmp_path: Path):
    with pytest.raises(nx.ExchangeError) as info:
        nx.load(str(tmp_path / "absent.json"))
    assert info.value.code == "invalid_json"


# ------------------------------------------------------------------------------------
# selecting a version


def test_select_current_version(nx):
    doc = nx.parse(
        json.dumps(
            {
                "current_version": "2.0",
                "versions": {
                    "1.0": {"needs": {"V1": record("V1")}},
                    "2.0": {"needs": {"V2": record("V2")}},
                },
            }
        )
    )
    version = doc.select_version(None)
    assert version.name == "2.0"
    assert [r.key for r in version.records()] == ["V2"]
    assert [r.key for r in doc.select_version("1.0").records()] == ["V1"]


def test_a_requested_version_needs_no_current_version(nx):
    doc = nx.parse(json.dumps({"versions": {"1.0": {"needs": {"A": record("A")}}}}))
    assert doc.select_version("1.0").name == "1.0"


@pytest.mark.parametrize(
    ("data", "requested", "code", "message"),
    [
        pytest.param(
            {"current_version": "1.0"},
            None,
            "versions_missing",
            "'versions' is missing or not an object",
            id="versions_absent",
        ),
        pytest.param(
            {"current_version": "1.0", "versions": []},
            None,
            "versions_missing",
            "'versions' is missing or not an object",
            id="versions_not_object",
        ),
        pytest.param(
            {"versions": {"1.0": {"needs": {}}}},
            None,
            "current_version_missing",
            "no version is requested and 'current_version' is missing, empty or not a string",
            id="current_absent",
        ),
        pytest.param(
            {"current_version": "", "versions": {"1.0": {"needs": {}}}},
            None,
            "current_version_missing",
            "no version is requested and 'current_version' is missing, empty or not a string",
            id="current_empty",
        ),
        pytest.param(
            {"current_version": 1.0, "versions": {"1.0": {"needs": {}}}},
            None,
            "current_version_missing",
            "no version is requested and 'current_version' is missing, empty or not a string",
            id="current_number",
        ),
        pytest.param(
            {"current_version": "3.0", "versions": {"1.0": {"needs": {}}}},
            None,
            "version_not_found",
            "Version 3.0 not found in the file: ['1.0']",
            id="current_not_found",
        ),
        pytest.param(
            {"current_version": "1.0", "versions": {"1.0": {"needs": {}}}},
            "9.9",
            "version_not_found",
            "Version 9.9 not found in the file: ['1.0']",
            id="requested_not_found",
        ),
        pytest.param(
            {"current_version": "1.0", "versions": {}},
            None,
            "version_not_found",
            "Version 1.0 not found in the file: []",
            id="versions_empty",
        ),
        pytest.param(
            {"current_version": "1.0", "versions": {"1.0": {"needs_amount": 0}}},
            None,
            "needs_missing",
            "Version 1.0 has no 'needs' object",
            id="needs_absent",
        ),
        pytest.param(
            {"current_version": "1.0", "versions": {"1.0": {"needs": []}}},
            None,
            "needs_missing",
            "Version 1.0 has no 'needs' object",
            id="needs_not_object",
        ),
        pytest.param(
            {"current_version": "1.0", "versions": {"1.0": "x"}},
            None,
            "needs_missing",
            "Version 1.0 has no 'needs' object",
            id="version_not_object",
        ),
    ],
)
def test_select_version_refuses(nx, data, requested, code, message):
    doc = nx.parse(json.dumps(data))
    with pytest.raises(nx.ExchangeError) as info:
        doc.select_version(requested)
    assert (info.value.code, info.value.message) == (code, message)


# ------------------------------------------------------------------------------------
# records and their diagnostics


def test_a_record_that_is_not_an_object_is_skipped(nx):
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
    ("given", "diagnostics"),
    [
        pytest.param({"id": "A"}, [], id="same"),
        pytest.param({}, [], id="absent"),
        pytest.param(
            {"id": "OTHER"},
            [
                (
                    "id_mismatch",
                    "the need keyed 'A' has the id 'OTHER'; the key is its id",
                )
            ],
            id="other_string",
        ),
        pytest.param(
            {"id": 5},
            [("id_mismatch", "the need keyed 'A' has the id 5; the key is its id")],
            id="number",
        ),
        pytest.param(
            {"id": None},
            [("id_mismatch", "the need keyed 'A' has the id None; the key is its id")],
            id="null",
        ),
    ],
)
def test_the_key_is_the_id(nx, given, diagnostics):
    fields = {"type": "req", "title": "t", **given}
    (rec,) = (
        nx.parse(json.dumps(envelope({"A": fields}))).select_version(None).records()
    )
    assert rec.key == "A"
    assert rec.fields["id"] == "A"
    assert [(d.code, d.message) for d in rec.diagnostics] == diagnostics
    assert all(d.path == "versions.1.0.needs.A.id" for d in rec.diagnostics)


@pytest.mark.parametrize(
    ("given", "expected"),
    [
        pytest.param(
            {"description": "legacy"}, {"content": "legacy"}, id="description_only"
        ),
        pytest.param(
            {"description": "legacy", "content": ""},
            {"content": "legacy"},
            id="content_empty",
        ),
        pytest.param(
            {"description": "legacy", "content": "kept"},
            {"content": "kept", "description": "legacy"},
            id="content_given",
        ),
    ],
)
def test_legacy_description_is_the_content(nx, given, expected):
    (rec,) = (
        nx.parse(json.dumps(envelope({"A": record("A", **given)})))
        .select_version(None)
        .records()
    )
    assert {
        k: rec.fields[k] for k in ("content", "description") if k in rec.fields
    } == (expected)
    assert rec.diagnostics == ()


def test_map_legacy_keys_in_place(nx):
    fields = {"description": "legacy"}
    nx.map_legacy_keys(fields)
    assert fields == {"content": "legacy"}


SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "properties": {
        "status": {"type": ["string", "null"], "default": None},
        "priority": {"type": ["string", "null"], "default": "medium"},
        "tags": {"type": "array", "default": []},
        "no_default": {"type": "string"},
    },
}


def test_schema_defaults_are_merged_under_the_record(nx):
    version = nx.parse(
        json.dumps(
            envelope(
                {"A": record("A"), "B": record("B", priority="high")},
                needs_schema=SCHEMA,
                needs_defaults_removed=True,
            )
        )
    ).select_version(None)
    a, b = version.records()
    assert (a.fields["priority"], a.fields["status"], a.fields["tags"]) == (
        "medium",
        None,
        [],
    )
    assert "no_default" not in a.fields
    assert b.fields["priority"] == "high"
    assert version.diagnostics == ()
    # each record has its own copy of a default
    a.fields["tags"].append("x")
    assert version.records()[1].fields["tags"] == []


def test_schema_defaults_can_be_left_out(nx):
    version = nx.parse(
        json.dumps(envelope({"A": record("A")}, needs_schema=SCHEMA))
    ).select_version(None)
    assert "priority" not in version.records(apply_schema_defaults=False)[0].fields


def test_without_a_schema_no_defaults(nx):
    version = nx.parse(json.dumps(envelope({"A": record("A")}))).select_version(None)
    assert "priority" not in version.records()[0].fields
    assert version.diagnostics == ()


def test_defaults_removed_without_a_schema(nx):
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


def test_a_3x_shaped_version(nx):
    """A version a 3.x writer wrote: a schema and stripped defaults, but no
    ``creator``, and the legacy ``full_title`` on each record."""
    version = nx.parse(
        json.dumps(
            envelope(
                {"A": record("A", full_title="the full title")},
                needs_schema=SCHEMA,
                needs_defaults_removed=True,
                needs_amount=1,
            )
        )
    ).select_version(None)
    (rec,) = version.records()
    assert rec.fields["full_title"] == "the full title"
    assert rec.diagnostics == ()
    assert version.diagnostics == ()


def test_records_keep_the_file_order(nx):
    needs = {key: record(key) for key in ("C", "A", "B")}
    version = nx.parse(json.dumps(envelope(needs))).select_version(None)
    assert [r.key for r in version.records()] == ["C", "A", "B"]


def test_records_do_not_alter_the_document(nx):
    doc = nx.parse(json.dumps(envelope({"A": {"description": "x"}})))
    doc.select_version(None).records()[0].fields["title"] = "changed"
    assert doc.data["versions"]["1.0"]["needs"]["A"] == {"description": "x"}


# ------------------------------------------------------------------------------------
# the module imports nothing but the standard library


def test_imports_only_the_standard_library():
    source = Path(
        str(Path(__file__).parents[1]), "src", "sphinx_needs", "exchange.py"
    ).read_text(encoding="utf-8")
    imported: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            assert node.level == 0, "a relative import reaches into the package"
            assert node.module is not None
            imported.add(node.module.split(".")[0])
    assert imported, "the walk found no import at all"
    assert imported <= sys.stdlib_module_names, sorted(
        imported - sys.stdlib_module_names
    )
