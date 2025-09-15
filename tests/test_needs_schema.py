import pytest

from sphinx_needs.functions.functions import (
    DynamicFunctionParsed,
    FunctionParsingException,
)
from sphinx_needs.needs_schema import (
    DynamicFunctionArray,
    FieldSchema,
    FieldValue,
    _split_list_with_dyn_funcs,
)


@pytest.mark.parametrize(
    "type_,item_type,nullable,default,expected",
    [
        ("string", None, False, None, {"type": "string"}),
        ("string", None, True, None, {"type": ["string", "null"], "default": None}),
        ("boolean", None, False, None, {"type": "boolean"}),
        ("boolean", None, True, None, {"type": ["boolean", "null"], "default": None}),
        ("integer", None, False, None, {"type": "integer"}),
        ("integer", None, True, None, {"type": ["integer", "null"], "default": None}),
        ("number", None, False, None, {"type": "number"}),
        ("number", None, True, None, {"type": ["number", "null"], "default": None}),
        (
            "array",
            "string",
            False,
            None,
            {"type": "array", "items": {"type": "string"}},
        ),
        (
            "array",
            "string",
            True,
            None,
            {"type": ["array", "null"], "items": {"type": "string"}, "default": None},
        ),
        (
            "array",
            "boolean",
            False,
            None,
            {"type": "array", "items": {"type": "boolean"}},
        ),
        (
            "array",
            "boolean",
            True,
            None,
            {"type": ["array", "null"], "items": {"type": "boolean"}, "default": None},
        ),
        (
            "array",
            "integer",
            False,
            None,
            {"type": "array", "items": {"type": "integer"}},
        ),
        (
            "array",
            "integer",
            True,
            None,
            {"type": ["array", "null"], "items": {"type": "integer"}, "default": None},
        ),
        (
            "array",
            "number",
            False,
            None,
            {"type": "array", "items": {"type": "number"}},
        ),
        (
            "array",
            "number",
            True,
            None,
            {"type": ["array", "null"], "items": {"type": "number"}, "default": None},
        ),
        ("string", None, False, "a", {"type": "string", "default": "a"}),
        ("boolean", None, False, True, {"type": "boolean", "default": True}),
        ("integer", None, False, 1, {"type": "integer", "default": 1}),
        ("number", None, False, 1.0, {"type": "number", "default": 1.0}),
    ],
)
def test_json_schema(type_, item_type, nullable, default, expected):
    field = FieldSchema(
        name="test_field",
        type=type_,
        item_type=item_type,
        nullable=nullable,
        default=default,
    )
    assert field.json_schema() == expected


@pytest.mark.parametrize(
    "type_,item_type,nullable,input,result",
    [
        ("string", None, False, "test", True),
        ("string", None, False, None, False),
        ("string", None, False, 1, False),
        ("string", None, True, "test", True),
        ("string", None, True, None, True),
        ("string", None, True, 1, False),
        ("boolean", None, False, True, True),
        ("boolean", None, False, False, True),
        ("boolean", None, False, None, False),
        ("boolean", None, False, 1, False),
        ("boolean", None, True, True, True),
        ("boolean", None, True, False, True),
        ("boolean", None, True, None, True),
        ("boolean", None, True, 1, False),
        ("integer", None, False, 1, True),
        ("integer", None, False, -1, True),
        ("integer", None, False, 0, True),
        ("integer", None, False, None, False),
        ("integer", None, False, 1.5, False),
        ("integer", None, False, "1", False),
        ("integer", None, True, 1, True),
        ("integer", None, True, -1, True),
        ("integer", None, True, 0, True),
        ("integer", None, True, None, True),
        ("integer", None, True, 1.5, False),
        ("integer", None, True, "1", False),
        ("number", None, False, 1, True),
        ("number", None, False, 1.5, True),
        ("number", None, False, -1.5, True),
        ("number", None, False, 0.0, True),
        ("number", None, False, 1.0e10, True),
        ("number", None, False, None, False),
        ("number", None, False, "1.5", False),
        ("number", None, True, 1.5, True),
        ("number", None, True, -1.5, True),
        ("number", None, True, 0.0, True),
        ("number", None, True, 1.0e10, True),
        ("number", None, True, None, True),
        ("number", None, True, "1.5", False),
        ("array", "string", False, ["a", "b", "c"], True),
        ("array", "string", False, [], True),
        ("array", "string", False, None, False),
        ("array", "string", False, ["a", 1, "c"], False),
        ("array", "string", True, ["a", "b", "c"], True),
        ("array", "string", True, [], True),
        ("array", "string", True, None, True),
        ("array", "string", True, ["a", 1, "c"], False),
        ("array", "boolean", False, [True, False, True], True),
        ("array", "boolean", False, [], True),
        ("array", "boolean", False, None, False),
        ("array", "boolean", False, [True, 1, False], False),
        ("array", "boolean", True, [True, False, True], True),
        ("array", "boolean", True, [], True),
        ("array", "boolean", True, None, True),
        ("array", "boolean", True, [True, 1, False], False),
        ("array", "integer", False, [1, -1, 0], True),
        ("array", "integer", False, [], True),
        ("array", "integer", False, None, False),
        ("array", "integer", False, [1, 2.5, 3], False),
        ("array", "integer", True, [1, -1, 0], True),
        ("array", "integer", True, [], True),
        ("array", "integer", True, None, True),
        ("array", "integer", True, [1, 2.5, 3], False),
        ("array", "number", False, [1.5, -1.5, 0.0], True),
        ("array", "number", False, [], True),
        ("array", "number", False, None, False),
        ("array", "number", False, [1.5, "2.5", 3.0], False),
        ("array", "number", True, [1.5, -1.5, 0.0], True),
        ("array", "number", True, [], True),
        ("array", "number", True, None, True),
        ("array", "number", True, [1.5, "2.5", 3.0], False),
    ],
)
def test_type_check(type_, item_type, nullable, input, result):
    field = FieldSchema(
        name="test_field",
        type=type_,
        item_type=item_type,
        nullable=nullable,
    )
    assert field.type_check(input) is result


@pytest.mark.parametrize(
    "type_,item_type,allow_df,input,expected",
    [
        ("string", None, False, "", ""),
        ("string", None, False, "test", "test"),
        ("string", None, False, "[[test()]]", "[[test()]]"),
        ("boolean", None, False, "", True),
        ("boolean", None, False, "true", True),
        ("boolean", None, False, "yes", True),
        ("boolean", None, False, "false", False),
        ("boolean", None, False, "no", False),
        ("integer", None, False, "1", 1),
        ("number", None, False, "1", 1.0),
        ("number", None, False, "1.5", 1.5),
        ("array", "string", False, "", []),
        ("array", "string", False, "a,b ; c", ["a", "b", "c"]),
        (
            "array",
            "boolean",
            False,
            " true , yes , no,false ",
            [True, True, False, False],
        ),
        ("array", "integer", False, "1,2, 3", [1, 2, 3]),
        ("array", "number", False, "1,1.5,2.5,3.5", [1.0, 1.5, 2.5, 3.5]),
    ],
)
def test_convert_directive_option_value(type_, item_type, allow_df, input, expected):
    field = FieldSchema(
        name="test_field",
        type=type_,
        item_type=item_type,
        allow_dynamic_functions=allow_df,
    )
    assert field.convert_directive_option(input) == FieldValue(expected)


@pytest.mark.parametrize(
    "type_,item_type,input,expected",
    [
        (
            "string",
            None,
            "[[test()]]",
            DynamicFunctionParsed(name="test", args=(), kwargs=()),
        ),
        (
            "string",
            None,
            "x [[test()]]y[[other()]]z[[more()",
            DynamicFunctionArray(
                (
                    "x ",
                    DynamicFunctionParsed(name="test", args=(), kwargs=()),
                    "y",
                    DynamicFunctionParsed(name="other", args=(), kwargs=()),
                    "z",
                    DynamicFunctionParsed(name="more", args=(), kwargs=()),
                )
            ),
        ),
        (
            "boolean",
            None,
            "[[test()]]",
            DynamicFunctionParsed(name="test", args=(), kwargs=()),
        ),
        (
            "integer",
            None,
            "[[test()]]",
            DynamicFunctionParsed(name="test", args=(), kwargs=()),
        ),
        (
            "number",
            None,
            "[[ test() ]]",
            DynamicFunctionParsed(name="test", args=(), kwargs=()),
        ),
        (
            "array",
            "string",
            "[[test()]]",
            DynamicFunctionArray(
                (DynamicFunctionParsed(name="test", args=(), kwargs=()),)
            ),
        ),
        (
            "array",
            "string",
            "a, [[test()]], c",
            DynamicFunctionArray(
                (
                    "a",
                    DynamicFunctionParsed(name="test", args=(), kwargs=()),
                    "c",
                )
            ),
        ),
        (
            "array",
            "boolean",
            "true, [[test()]], false",
            DynamicFunctionArray(
                (
                    True,
                    DynamicFunctionParsed(name="test", args=(), kwargs=()),
                    False,
                )
            ),
        ),
        (
            "array",
            "integer",
            "1, [[test()]], 3",
            DynamicFunctionArray(
                (
                    1,
                    DynamicFunctionParsed(name="test", args=(), kwargs=()),
                    3,
                )
            ),
        ),
        (
            "array",
            "number",
            "1.5, [[ test() ]], 3.5",
            DynamicFunctionArray(
                (
                    1.5,
                    DynamicFunctionParsed(name="test", args=(), kwargs=()),
                    3.5,
                )
            ),
        ),
    ],
)
def test_convert_directive_option_df(type_, item_type, input, expected):
    field = FieldSchema(
        name="test_field",
        type=type_,
        item_type=item_type,
        allow_dynamic_functions=True,
    )
    assert field.convert_directive_option(input) == expected


@pytest.mark.parametrize(
    "type_,item_type,allow_df,input",
    [
        ("boolean", None, False, "a"),
        ("boolean", None, False, "[[test()]]"),
        ("integer", None, False, "a"),
        ("integer", None, False, "1.5"),
        ("integer", None, False, "[[test()]]"),
        ("number", None, False, "a"),
        ("number", None, False, "[[test()]]"),
        ("array", "boolean", False, "a, false"),
        ("array", "boolean", False, "true, [[test()]], false"),
        ("array", "integer", False, "a, 1"),
        ("array", "integer", False, "1, [[test()]], 3"),
        ("array", "number", False, "a, 1"),
        ("array", "number", False, "1.5, [[ test() ]], 3.5"),
        ("array", "number", False, "1.5, a[[ test() ]], 3.5"),
        ("array", "number", False, "1.5, [[ test() ]]b, 3.5"),
    ],
)
def test_convert_directive_option_value_errors(type_, item_type, allow_df, input):
    field = FieldSchema(
        name="test_field",
        type=type_,
        item_type=item_type,
        allow_dynamic_functions=allow_df,
    )
    with pytest.raises(ValueError):
        field.convert_directive_option(input)


@pytest.mark.parametrize(
    "type_,item_type,input",
    [
        ("boolean", None, "[[test(]]"),
        ("integer", None, "[[test(]]"),
        ("number", None, "[[test(]]"),
        ("array", "string", "true, [[test(]], false"),
        ("array", "boolean", "true, [[test(]], false"),
        ("array", "integer", "1, [[test(]], 3"),
        ("array", "number", "1.5, [[ test( ]], 3.5"),
    ],
)
def test_convert_directive_option_df_errors(type_, item_type, input):
    field = FieldSchema(
        name="test_field",
        type=type_,
        item_type=item_type,
        allow_dynamic_functions=True,
    )
    with pytest.raises(FunctionParsingException):
        field.convert_directive_option(input)


@pytest.mark.parametrize(
    "text, expected",
    [
        (None, []),
        ("a", [[("a", False, False)]]),
        ("a,", [[("a", False, False)]]),
        ("[[a]]", [[("a", True, False)]]),
        ("a,b", [[("a", False, False)], [("b", False, False)]]),
        ("a, b", [[("a", False, False)], [("b", False, False)]]),
        ("a,b,", [[("a", False, False)], [("b", False, False)]]),
        ("a|b", [[("a", False, False)], [("b", False, False)]]),
        ("a| b", [[("a", False, False)], [("b", False, False)]]),
        ("a|b,", [[("a", False, False)], [("b", False, False)]]),
        ("a;b", [[("a", False, False)], [("b", False, False)]]),
        ("a; b", [[("a", False, False)], [("b", False, False)]]),
        ("a;b,", [[("a", False, False)], [("b", False, False)]]),
        (
            "a,b|c;d,",
            [
                [("a", False, False)],
                [("b", False, False)],
                [("c", False, False)],
                [("d", False, False)],
            ],
        ),
        ("[[x,y]],b", [[("x,y", True, False)], [("b", False, False)]]),
        (
            "a,[[x,y]],b",
            [[("a", False, False)], [("x,y", True, False)], [("b", False, False)]],
        ),
        ("a,[[x,y", [[("a", False, False)], [("x,y", True, True)]]),
        ("a,[[x,y]", [[("a", False, False)], [("x,y", True, True)]]),
        ("[[a]]b", [[("a", True, False), ("b", False, False)]]),
        ("b[[a]]", [[("b", False, False), ("a", True, False)]]),
        (
            "[[a]]b[[c]]d",
            [
                [
                    ("a", True, False),
                    ("b", False, False),
                    ("c", True, False),
                    ("d", False, False),
                ]
            ],
        ),
        ("[[a;]],", [[("a;", True, False)]]),
        (
            "a,b;c",
            [[("a", False, False)], [("b", False, False)], [("c", False, False)]],
        ),
        (
            "[[a]],[[b]];[[c]]",
            [[("a", True, False)], [("b", True, False)], [("c", True, False)]],
        ),
        (
            " a ,, b; c ",
            [[("a", False, False)], [("b", False, False)], [("c", False, False)]],
        ),
        (
            " [[a]] ,, [[b]] ; [[c]] ",
            [[("a", True, False)], [("b", True, False)], [("c", True, False)]],
        ),
        (
            "a,[[b]];c",
            [[("a", False, False)], [("b", True, False)], [("c", False, False)]],
        ),
        (
            " a ,, [[b;]] ; c ",
            [[("a", False, False)], [("b;", True, False)], [("c", False, False)]],
        ),
    ],
)
def test_split_list_with_dyn_funcs(text, expected):
    assert list(_split_list_with_dyn_funcs(text)) == expected
