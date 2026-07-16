import ast
import inspect
import json
import os
import re
from pathlib import Path
from typing import Any, ForwardRef

import pytest

import sphinx_needs
from sphinx_needs.data import (
    NeedsContentInfoType,
    NeedsCoreFields,
    NeedsInfoComputedType,
    NeedsInfoType,
    NeedsSourceInfoType,
    core_fields_manifest,
)
from sphinx_needs.need_item import NeedItem, NeedsContent

# The full ordered set of axes every core-field manifest entry must materialize.
_MANIFEST_BOOL_AXES = (
    "add_to_field_schema",
    "allow_default",
    "allow_extend",
    "allow_df",
    "allow_variants",
    "deprecate_df",
    "show_in_layout",
    "settable_in_directive",
    "mutable_after_creation",
    "exclude_external",
    "exclude_import",
    "exclude_json",
)


def _make_core() -> NeedsInfoType:
    """Build a minimal, valid ``NeedsInfoType`` (all core keys present)."""
    return {
        "id": "abc",
        "type": "type",
        "type_name": "type title",
        "type_prefix": "type prefix",
        "type_color": "#000000",
        "type_style": "node",
        "status": None,
        "tags": ["tag1"],
        "constraints": ("const1",),
        "title": "title",
        "collapse": False,
        "arch": {},
        "style": None,
        "layout": None,
        "hide": False,
        "external_css": "external_link",
        "has_dead_links": False,
        "has_forbidden_dead_links": False,
        "sections": (),
        "signature": None,
    }


def _make_item() -> NeedItem:
    """Build a minimal ``NeedItem`` with no constraint results computed yet."""
    return NeedItem(
        core=_make_core(),
        content=NeedsContent(doctype=".rst", content="content"),
        extras={},
        links={},
        source=None,
    )


def _sample_value(schema: dict[str, Any]) -> Any:
    """Return a type-appropriate sample value for a core-field JSON schema."""
    type_ = schema["type"]
    if isinstance(type_, list):
        type_ = type_[0]  # the non-null variant
    return {
        "string": "x",
        "integer": 1,
        "number": 1.0,
        "boolean": True,
        "array": ["x"],
        "object": {},
    }[type_]


def test_consistent():
    """
    Ideally NeedsCoreFields and NeedsInfoType would be merged, so there is no duplication,
    but I'm not sure this is possible (to encode both the static and dynamic data required).
    So at least here, we check that they are consistent with each other.
    """
    all_keys = [
        *NeedsInfoType.__annotations__,
        *NeedsSourceInfoType.__annotations__,
        *NeedsContentInfoType.__annotations__,
        *NeedsInfoComputedType.__annotations__,
    ]
    if len(all_keys) != len(set(all_keys)):
        duplicates = sorted(key for key in set(all_keys) if all_keys.count(key) > 1)
        raise ValueError(
            f"NeedsInfoType, NeedsSourceInfoType, NeedsContentInfoType, NeedsInfoComputedType keys must be unique: {duplicates}"
        )
    # check fields are consistent
    core_fields = set(NeedsCoreFields)
    diff = core_fields.symmetric_difference(all_keys)
    assert not diff, (
        "NeedsCoreFields and NeedsInfoType/NeedsSourceInfoType/NeedsContentInfoType/NeedsInfoComputedType should have the same fields"
        f" (difference: {diff})"
    )

    # check field types are consistent with schema
    for field, data in NeedsCoreFields.items():
        if not (schema := data.get("schema")):
            continue
        type_ = (
            NeedsInfoType.__annotations__[field]
            if field in NeedsInfoType.__annotations__
            else NeedsSourceInfoType.__annotations__[field]
            if field in NeedsSourceInfoType.__annotations__
            else NeedsContentInfoType.__annotations__[field]
            if field in NeedsContentInfoType.__annotations__
            else NeedsInfoComputedType.__annotations__[field]
        )
        assert isinstance(type_, ForwardRef)
        type_str = type_.__forward_arg__
        if type_str.startswith("Required"):
            type_str = type_str[9:-1]
        if type_str == "str" or type_str == "str | Text":
            assert schema["type"] == "string", field
        elif type_str == "int":
            assert schema["type"] == "integer", field
        elif type_str == "bool":
            assert schema["type"] == "boolean", field
        elif type_str in ("str | None", "None | str"):
            assert schema["type"] == ["string", "null"], field
        elif type_str in ("int | None", "None | int"):
            assert schema["type"] == ["integer", "null"], field
        elif type_str in ("bool | None", "None | bool"):
            assert schema["type"] == ["boolean", "null"], field
        elif type_str == "list[str]" or type_str == "tuple[str, ...]":
            assert schema["type"] == "array", field
            assert schema["items"]["type"] == "string", field
        elif type_str == "dict[str, str]":
            assert schema["type"] == "object", field
            assert schema["additionalProperties"]["type"] == "string", field
        elif type_str.startswith("dict[") or type_str.startswith("Mapping["):
            assert schema["type"] == "object", field
        elif type_str.startswith("None | dict[") or type_str.startswith(
            "None | Mapping["
        ):
            assert schema["type"] == ["object", "null"], field
        else:
            raise ValueError(f"Unknown type: {type_str!r} for {field!r}")

    # check descriptions are consistent
    for class_ in (
        NeedsInfoType,
        NeedsSourceInfoType,
        NeedsContentInfoType,
        NeedsInfoComputedType,
    ):
        source = inspect.getsource(class_)
        klass = ast.parse(source).body[0]
        descriptions = {}
        for i, node in enumerate(klass.body):
            if (
                isinstance(node, ast.AnnAssign)
                and len(klass.body) > i + 1
                and isinstance(klass.body[i + 1], ast.Expr)
            ):
                desc = " ".join(
                    [li.strip() for li in klass.body[i + 1].value.value.splitlines()]
                )
                descriptions[node.target.id] = desc.strip()
        for field, desc in descriptions.items():
            if field in NeedsCoreFields:
                assert NeedsCoreFields[field]["description"] == desc, field


def test_namespace_matches_typeddict_membership():
    """The ``namespace`` axis must match which TypedDict actually declares each field.

    This pins the ``namespace`` metadata to the real structural partition, so the
    two cannot silently diverge (e.g. if a field is moved between TypedDicts).
    """
    members = {
        "core": set(NeedsInfoType.__annotations__),
        "source": set(NeedsSourceInfoType.__annotations__),
        "content": set(NeedsContentInfoType.__annotations__),
        "computed": set(NeedsInfoComputedType.__annotations__),
    }
    # the four partitions must be disjoint and cover every core field exactly once
    seen: set[str] = set()
    for keys in members.values():
        assert not (seen & keys), seen & keys
        seen |= keys
    assert seen == set(NeedsCoreFields)

    for name, params in NeedsCoreFields.items():
        namespace = params["namespace"]
        assert name in members[namespace], (name, namespace)
        for other, keys in members.items():
            if other != namespace:
                assert name not in keys, (name, namespace, other)


def test_settable_in_directive_matches_directive_options():
    """The ``settable_in_directive`` axis must match the ``need`` directive's options.

    The truth is the ``match key:`` block in ``NeedDirective.run``, mirrored by the
    ``_CORE_DIRECTIVE_OPTIONS`` constant, plus the ``title`` argument and the ``type``
    directive name. Asserting equality keeps the catalog and the directive in sync.
    """
    from sphinx_needs.directives.need import _CORE_DIRECTIVE_OPTIONS

    settable = {
        name
        for name, params in NeedsCoreFields.items()
        if params.get("settable_in_directive", False)
    }
    assert settable == _CORE_DIRECTIVE_OPTIONS | {"title", "type"}


@pytest.mark.parametrize("name", list(NeedsCoreFields))
def test_mutable_after_creation_matches_setitem_guards(name: str):
    """The ``mutable_after_creation`` axis must match ``NeedItem.__setitem__`` guards.

    Behavioural probe: on a fresh need item (before any constraint results are
    computed) attempt to set each core field, and assert a write is rejected
    exactly when the flag is absent/False.

    Note: ``constraints`` is mutable until ``constraints_results`` is computed,
    so setting it here (results still ``None``) is accepted (flag ``True``).
    """
    mutable = NeedsCoreFields[name].get("mutable_after_creation", False)
    value = _sample_value(NeedsCoreFields[name]["schema"])
    item = _make_item()
    if mutable:
        item[name] = value  # must not raise
    else:
        with pytest.raises(KeyError):
            item[name] = value


def test_computed_namespace_matches_recompute_output():
    """The ``computed`` namespace must equal the keys ``_recompute`` writes.

    ``NeedsInfoComputedType`` membership (which ``test_namespace_matches_typeddict_membership``
    ties to the ``namespace`` axis) must match exactly the set of keys populated by
    ``NeedItem._recompute``, and those keys must be readable on a fresh item.
    """
    computed = {
        name
        for name, params in NeedsCoreFields.items()
        if params["namespace"] == "computed"
    }
    assert computed == set(NeedsInfoComputedType.__annotations__)

    item = _make_item()
    # _recompute writes exactly the computed keys into the private _computed dict
    assert set(item._computed) == computed
    # and every computed key is readable on the item without raising
    for name in computed:
        _ = item[name]


def test_core_fields_manifest_structure():
    """``core_fields_manifest`` must materialize every axis for every field."""
    manifest = core_fields_manifest()
    assert manifest["manifest_version"] == 1
    assert manifest["generator"] == f"sphinx-needs {sphinx_needs.__version__}"

    fields = manifest["fields"]
    assert set(fields) == set(NeedsCoreFields)
    assert len(fields) == len(NeedsCoreFields)

    required = ("namespace", "storage_class", "population_phase")
    for name, entry in fields.items():
        for axis in (*required, *_MANIFEST_BOOL_AXES, "description", "schema"):
            assert axis in entry, (name, axis)
        # booleans are always materialized (absent-in-catalog -> False)
        for axis in _MANIFEST_BOOL_AXES:
            assert isinstance(entry[axis], bool), (name, axis)
        assert entry["namespace"] == NeedsCoreFields[name]["namespace"]

    # tuple defaults are normalized to lists for JSON
    assert fields["sections"]["schema"]["default"] == []
    # the whole manifest is JSON-serializable
    json.dumps(manifest)


def test_core_fields_json_up_to_date():
    """The shipped ``core_fields.json`` must never drift from ``core_fields_manifest``.

    Regenerate with ``UPDATE_CORE_FIELDS_JSON=1 pytest tests/test_data.py``.
    The ``generator`` version is normalized before comparison, since it records the
    version at generation time rather than tracking the running version.
    """
    path = Path(sphinx_needs.__file__).parent / "core_fields.json"
    generated = (
        json.dumps(
            core_fields_manifest(), indent=2, ensure_ascii=False, sort_keys=False
        )
        + "\n"
    )
    if os.environ.get("UPDATE_CORE_FIELDS_JSON"):
        path.write_text(generated, encoding="utf-8")

    shipped = path.read_text(encoding="utf-8")

    def _norm(text: str) -> str:
        return re.sub(
            r'"generator": "sphinx-needs [^"]*"',
            '"generator": "sphinx-needs <version>"',
            text,
        )

    assert _norm(shipped) == _norm(generated), (
        "sphinx_needs/core_fields.json is out of date; regenerate with "
        "UPDATE_CORE_FIELDS_JSON=1 pytest tests/test_data.py"
    )
    assert json.loads(shipped)["generator"].startswith("sphinx-needs ")
