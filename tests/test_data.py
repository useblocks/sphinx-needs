import ast
import inspect
from typing import ForwardRef

from sphinx_needs.data import (
    NeedsContentInfoType,
    NeedsCoreFields,
    NeedsInfoComputedType,
    NeedsInfoType,
    NeedsSourceInfoType,
)


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
