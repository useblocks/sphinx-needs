import ast
import inspect

from sphinx_needs.data import NeedsCoreFields, NeedsInfoType


def test_consistent():
    """
    Ideally NeedsCoreFields and NeedsInfoType would be merged, so there is no duplication,
    but I'm not sure this is possible (to encode both the static and dynamic data required).
    So at least here, we check that they are consistent with each other.
    """
    assert set(NeedsCoreFields).issubset(set(NeedsInfoType.__annotations__))

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
