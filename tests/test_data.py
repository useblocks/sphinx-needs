import ast
import inspect
from typing import ForwardRef

from sphinx_needs.data import NeedsCoreFields, NeedsInfoType


def test_consistent():
    """
    Ideally NeedsCoreFields and NeedsInfoType would be merged, so there is no duplication,
    but I'm not sure this is possible (to encode both the static and dynamic data required).
    So at least here, we check that they are consistent with each other.
    """
    # check fields are consistent
    assert set(NeedsCoreFields).issubset(set(NeedsInfoType.__annotations__))

    # check field types are consistent with schema
    for field, data in NeedsCoreFields.items():
        if not (schema := data.get("schema")):
            continue
        type_ = NeedsInfoType.__annotations__[field]
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
        elif type_str == "list[str]":
            assert schema["type"] == "array", field
            assert schema["items"]["type"] == "string", field
        elif type_str == "dict[str, str]":
            assert schema["type"] == "object", field
            assert schema["additionalProperties"]["type"] == "string", field
        elif type_str.startswith("dict["):
            assert schema["type"] == "object", field
        else:
            raise ValueError(f"Unknown type: {type_str!r} for {field!r}")

    # check descriptions are consistent
    source = inspect.getsource(NeedsInfoType)
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
