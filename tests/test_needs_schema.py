import pytest

from sphinx_needs.exceptions import FunctionParsingException
from sphinx_needs.functions.functions import (
    DynamicFunctionParsed,
)
from sphinx_needs.needs_schema import (
    FieldFunctionArray,
    FieldLiteralValue,
    FieldSchema,
    ListItemType,
    _split_list,
    _split_string,
    inherit_schema,
)
from sphinx_needs.variants import VariantFunctionParsed


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
    schema = {"type": type_}
    if item_type is not None:
        schema["items"] = {"type": item_type}
    field = FieldSchema(
        name="test_field",
        schema=schema,
        nullable=nullable,
        allow_defaults=True,
        default=FieldLiteralValue(default) if default is not None else None,
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
    schema = {"type": type_}
    if item_type is not None:
        schema["items"] = {"type": item_type}
    field = FieldSchema(
        name="test_field",
        schema=schema,
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
        ("array", "integer", False, "1,2, 3, 3_000", [1, 2, 3, 3000]),
        (
            "array",
            "number",
            False,
            "1,1.5,2.5,3.5,3_000,3.5e2,3.5e-2",
            [1.0, 1.5, 2.5, 3.5, 3000.0, 350, 0.035],
        ),
    ],
)
def test_convert_directive_option_value(type_, item_type, allow_df, input, expected):
    schema = {"type": type_}
    if item_type is not None:
        schema["items"] = {"type": item_type}
    field = FieldSchema(
        name="test_field",
        schema=schema,
        parse_dynamic_functions=allow_df,
    )
    assert field.convert_directive_option(input) == FieldLiteralValue(expected)


@pytest.mark.parametrize(
    "type_,item_type,input,expected",
    [
        (
            "string",
            None,
            "[[test()]]",
            FieldFunctionArray(
                (DynamicFunctionParsed(name="test", args=(), kwargs=()),)
            ),
        ),
        (
            "string",
            None,
            "x [[test()]]y[[other()]]z[[more()",
            FieldFunctionArray(
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
            FieldFunctionArray(
                (DynamicFunctionParsed(name="test", args=(), kwargs=()),)
            ),
        ),
        (
            "integer",
            None,
            "[[test()]]",
            FieldFunctionArray(
                (DynamicFunctionParsed(name="test", args=(), kwargs=()),)
            ),
        ),
        (
            "number",
            None,
            "[[ test() ]]",
            FieldFunctionArray(
                (DynamicFunctionParsed(name="test", args=(), kwargs=()),)
            ),
        ),
        (
            "array",
            "string",
            "[[test()]]",
            FieldFunctionArray(
                (DynamicFunctionParsed(name="test", args=(), kwargs=()),)
            ),
        ),
        (
            "array",
            "string",
            "a, [[test()]], c",
            FieldFunctionArray(
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
            FieldFunctionArray(
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
            FieldFunctionArray(
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
            FieldFunctionArray(
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
    schema = {"type": type_}
    if item_type is not None:
        schema["items"] = {"type": item_type}
    field = FieldSchema(
        name="test_field",
        schema=schema,
        parse_dynamic_functions=True,
    )
    assert field.convert_directive_option(input) == expected


@pytest.mark.parametrize(
    "type_,item_type,input,expected",
    [
        (
            "string",
            None,
            "<<a:b,c>>",
            FieldFunctionArray((VariantFunctionParsed((("a", False, "b"),), "c"),)),
        ),
        (
            "string",
            None,
            "x <<a:b,c>>y<<[x]:y>>z<<v",
            FieldFunctionArray(
                (
                    "x ",
                    VariantFunctionParsed((("a", False, "b"),), "c"),
                    "y",
                    VariantFunctionParsed((("x", True, "y"),), None),
                    "z",
                    VariantFunctionParsed((), "v"),
                )
            ),
        ),
        (
            "boolean",
            None,
            "<<a:true,false>>",
            FieldFunctionArray((VariantFunctionParsed((("a", False, True),), False),)),
        ),
        (
            "integer",
            None,
            "<<a:2,4>>",
            FieldFunctionArray((VariantFunctionParsed((("a", False, 2),), 4),)),
        ),
        (
            "number",
            None,
            "<< a:2.5,4.5 >>",
            FieldFunctionArray((VariantFunctionParsed((("a", False, 2.5),), 4.5),)),
        ),
        (
            "array",
            "string",
            "<<test>>",
            FieldFunctionArray((VariantFunctionParsed((), "test"),)),
        ),
        (
            "array",
            "string",
            "a, <<test>>, c",
            FieldFunctionArray(
                (
                    "a",
                    VariantFunctionParsed((), "test"),
                    "c",
                )
            ),
        ),
        (
            "array",
            "boolean",
            "true, <<a:yes,no>>, false",
            FieldFunctionArray(
                (
                    True,
                    VariantFunctionParsed((("a", False, True),), False),
                    False,
                )
            ),
        ),
        (
            "array",
            "integer",
            "1, <<a:2,4>>, 3",
            FieldFunctionArray(
                (
                    1,
                    VariantFunctionParsed((("a", False, 2),), 4),
                    3,
                )
            ),
        ),
        (
            "array",
            "number",
            "1.5, << a:2.5,4.5 >>, 3.5",
            FieldFunctionArray(
                (
                    1.5,
                    VariantFunctionParsed((("a", False, 2.5),), 4.5),
                    3.5,
                )
            ),
        ),
    ],
)
def test_convert_directive_option_vf(type_, item_type, input, expected):
    schema = {"type": type_}
    if item_type is not None:
        schema["items"] = {"type": item_type}
    field = FieldSchema(
        name="test_field",
        schema=schema,
        parse_variants=True,
    )
    assert field.convert_directive_option(input) == expected


@pytest.mark.parametrize(
    "type_,item_type,allow_df,allow_vf,input",
    [
        ("boolean", None, False, False, "a"),
        ("boolean", None, False, False, "[[test()]]"),
        ("boolean", None, False, True, "<<a:b>>"),
        ("integer", None, False, False, "a"),
        ("integer", None, False, False, "1.5"),
        ("integer", None, False, False, "[[test()]]"),
        ("integer", None, False, True, "<<a:b>>"),
        ("number", None, False, False, "a"),
        ("number", None, False, False, "[[test()]]"),
        ("number", None, False, True, "<<a:b>>"),
        ("array", "boolean", False, False, "a, false"),
        ("array", "boolean", False, False, "true, [[test()]], false"),
        ("array", "boolean", False, True, "<<a:b>>"),
        ("array", "integer", False, False, "a, 1"),
        ("array", "integer", False, False, "1, [[test()]], 3"),
        ("array", "integer", False, True, "<<a:b>>"),
        ("array", "number", False, False, "a, 1"),
        ("array", "number", False, False, "1.5, [[ test() ]], 3.5"),
        ("array", "number", False, False, "1.5, a[[ test() ]], 3.5"),
        ("array", "number", False, False, "1.5, [[ test() ]]b, 3.5"),
        ("array", "number", False, True, "<<a:b>>"),
    ],
)
def test_convert_directive_option_value_errors(
    type_, item_type, allow_df, allow_vf, input
):
    schema = {"type": type_}
    if item_type is not None:
        schema["items"] = {"type": item_type}
    field = FieldSchema(
        name="test_field",
        schema=schema,
        parse_dynamic_functions=allow_df,
        parse_variants=allow_vf,
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
    schema = {"type": type_}
    if item_type is not None:
        schema["items"] = {"type": item_type}
    field = FieldSchema(
        name="test_field",
        schema=schema,
        parse_dynamic_functions=True,
    )
    with pytest.raises(FunctionParsingException):
        field.convert_directive_option(input)


@pytest.mark.parametrize(
    "text, expected",
    [
        (None, []),
        ("a", [[("a", ListItemType.STD)]]),
        ("a,", [[("a", ListItemType.STD)]]),
        ("[[a]]", [[("a", ListItemType.DF)]]),
        ("<<a>>", [[("a", ListItemType.VF)]]),
        ("a,b", [[("a", ListItemType.STD)], [("b", ListItemType.STD)]]),
        ("a, b", [[("a", ListItemType.STD)], [("b", ListItemType.STD)]]),
        ("a,b,", [[("a", ListItemType.STD)], [("b", ListItemType.STD)]]),
        ("a|b", [[("a", ListItemType.STD)], [("b", ListItemType.STD)]]),
        ("a| b", [[("a", ListItemType.STD)], [("b", ListItemType.STD)]]),
        ("a|b,", [[("a", ListItemType.STD)], [("b", ListItemType.STD)]]),
        ("a;b", [[("a", ListItemType.STD)], [("b", ListItemType.STD)]]),
        ("a; b", [[("a", ListItemType.STD)], [("b", ListItemType.STD)]]),
        ("a;b,", [[("a", ListItemType.STD)], [("b", ListItemType.STD)]]),
        (
            "a,b|c;d,",
            [
                [("a", ListItemType.STD)],
                [("b", ListItemType.STD)],
                [("c", ListItemType.STD)],
                [("d", ListItemType.STD)],
            ],
        ),
        (
            " a ,, b; c ",
            [
                [("a", ListItemType.STD)],
                [("b", ListItemType.STD)],
                [("c", ListItemType.STD)],
            ],
        ),
        ("[[x,y]],b", [[("x,y", ListItemType.DF)], [("b", ListItemType.STD)]]),
        (
            "a,[[x,y]],b",
            [
                [("a", ListItemType.STD)],
                [("x,y", ListItemType.DF)],
                [("b", ListItemType.STD)],
            ],
        ),
        ("a,[[x,y", [[("a", ListItemType.STD)], [("x,y", ListItemType.DF_U)]]),
        ("a,[[x,y]", [[("a", ListItemType.STD)], [("x,y", ListItemType.DF_U)]]),
        ("[[a]]b", [[("a", ListItemType.DF), ("b", ListItemType.STD)]]),
        ("b[[a]]", [[("b", ListItemType.STD), ("a", ListItemType.DF)]]),
        (
            "[[a]]b[[c]]d",
            [
                [
                    ("a", ListItemType.DF),
                    ("b", ListItemType.STD),
                    ("c", ListItemType.DF),
                    ("d", ListItemType.STD),
                ]
            ],
        ),
        ("[[a;]],", [[("a;", ListItemType.DF)]]),
        (
            "a,b;c",
            [
                [("a", ListItemType.STD)],
                [("b", ListItemType.STD)],
                [("c", ListItemType.STD)],
            ],
        ),
        (
            "[[a]],[[b]];[[c]]",
            [
                [("a", ListItemType.DF)],
                [("b", ListItemType.DF)],
                [("c", ListItemType.DF)],
            ],
        ),
        (
            " [[a]] ,, [[b]] ; [[c]] ",
            [
                [("a", ListItemType.DF)],
                [("b", ListItemType.DF)],
                [("c", ListItemType.DF)],
            ],
        ),
        (
            "a,[[b]];c",
            [
                [("a", ListItemType.STD)],
                [("b", ListItemType.DF)],
                [("c", ListItemType.STD)],
            ],
        ),
        (
            " a ,, [[b;]] ; c ",
            [
                [("a", ListItemType.STD)],
                [("b;", ListItemType.DF)],
                [("c", ListItemType.STD)],
            ],
        ),
        ("<<x,y>>,b", [[("x,y", ListItemType.VF)], [("b", ListItemType.STD)]]),
        (
            "a,<<x,y>>,b",
            [
                [("a", ListItemType.STD)],
                [("x,y", ListItemType.VF)],
                [("b", ListItemType.STD)],
            ],
        ),
        ("a,<<x,y", [[("a", ListItemType.STD)], [("x,y", ListItemType.VF_U)]]),
        ("a,<<x,y>", [[("a", ListItemType.STD)], [("x,y", ListItemType.VF_U)]]),
        ("<<a>>b", [[("a", ListItemType.VF), ("b", ListItemType.STD)]]),
        ("b<<a>>", [[("b", ListItemType.STD), ("a", ListItemType.VF)]]),
        (
            "<<a>>b<<c>>d",
            [
                [
                    ("a", ListItemType.VF),
                    ("b", ListItemType.STD),
                    ("c", ListItemType.VF),
                    ("d", ListItemType.STD),
                ]
            ],
        ),
        ("<<a;>>,", [[("a;", ListItemType.VF)]]),
        (
            "<<a>>,<<b>>;<<c>>",
            [
                [("a", ListItemType.VF)],
                [("b", ListItemType.VF)],
                [("c", ListItemType.VF)],
            ],
        ),
        (
            " <<a>> ,, <<b>> ; <<c>> ",
            [
                [("a", ListItemType.VF)],
                [("b", ListItemType.VF)],
                [("c", ListItemType.VF)],
            ],
        ),
        (
            "a,<<b>>;c",
            [
                [("a", ListItemType.STD)],
                [("b", ListItemType.VF)],
                [("c", ListItemType.STD)],
            ],
        ),
        (
            " a ,, <<b;>> ; c ",
            [
                [("a", ListItemType.STD)],
                [("b;", ListItemType.VF)],
                [("c", ListItemType.STD)],
            ],
        ),
        (
            " a << b >> c [[ d ]] e ",
            [
                [
                    ("a ", ListItemType.STD),
                    (" b ", ListItemType.VF),
                    (" c ", ListItemType.STD),
                    (" d ", ListItemType.DF),
                    (" e", ListItemType.STD),
                ],
            ],
        ),
        (
            "a,[[b]],<<c>>;d",
            [
                [("a", ListItemType.STD)],
                [("b", ListItemType.DF)],
                [("c", ListItemType.VF)],
                [("d", ListItemType.STD)],
            ],
        ),
    ],
)
def test_split_list(text, expected):
    assert list(_split_list(text, True, True)) == expected


@pytest.mark.parametrize(
    "text, expected",
    [
        ("", [("", ListItemType.STD)]),
        ("a", [("a", ListItemType.STD)]),
        ("[[a]]", [("a", ListItemType.DF)]),
        ("<<a>>", [("a", ListItemType.VF)]),
        ("[[a]", [("a", ListItemType.DF_U)]),
        ("<<a>", [("a", ListItemType.VF_U)]),
        ("[[a", [("a", ListItemType.DF_U)]),
        ("<<a", [("a", ListItemType.VF_U)]),
        (
            " a << b >> c [[ d ]] e ",
            [
                ("a ", ListItemType.STD),
                (" b ", ListItemType.VF),
                (" c ", ListItemType.STD),
                (" d ", ListItemType.DF),
                (" e", ListItemType.STD),
            ],
        ),
        (
            "a,[[b]],<<c>>;d",
            [
                ("a,", ListItemType.STD),
                ("b", ListItemType.DF),
                (",", ListItemType.STD),
                ("c", ListItemType.VF),
                (";d", ListItemType.STD),
            ],
        ),
    ],
)
def test_split_string(text, expected):
    assert _split_string(text, True, True) == expected


@pytest.mark.parametrize(
    "parent_schema,child_schema,expected",
    [
        # String: const constraint - child inherits parent const
        (
            {"type": "string", "const": "value"},
            {"type": "string"},
            {"type": "string", "const": "value"},
        ),
        # String: const constraint - child has same const (valid)
        (
            {"type": "string", "const": "value"},
            {"type": "string", "const": "value"},
            {"type": "string", "const": "value"},
        ),
        # String: enum constraint - child inherits parent enum
        (
            {"type": "string", "enum": ["a", "b", "c"]},
            {"type": "string"},
            {"type": "string", "enum": ["a", "b", "c"]},
        ),
        # String: enum constraint - child enum is subset (valid)
        (
            {"type": "string", "enum": ["a", "b", "c"]},
            {"type": "string", "enum": ["a", "b"]},
            {"type": "string", "enum": ["a", "b"]},
        ),
        # String: pattern constraint - child inherits pattern
        (
            {"type": "string", "pattern": "^[a-z]+$"},
            {"type": "string"},
            {"type": "string", "pattern": "^[a-z]+$"},
        ),
        # String: pattern constraint - child has same pattern (valid)
        (
            {"type": "string", "pattern": "^[a-z]+$"},
            {"type": "string", "pattern": "^[a-z]+$"},
            {"type": "string", "pattern": "^[a-z]+$"},
        ),
        # String: format constraint - child inherits format
        (
            {"type": "string", "format": "email"},
            {"type": "string"},
            {"type": "string", "format": "email"},
        ),
        # String: format constraint - child has same format (valid)
        (
            {"type": "string", "format": "email"},
            {"type": "string", "format": "email"},
            {"type": "string", "format": "email"},
        ),
        # String: minLength constraint - child inherits minLength
        (
            {"type": "string", "minLength": 5},
            {"type": "string"},
            {"type": "string", "minLength": 5},
        ),
        # String: minLength constraint - child has equal or greater minLength (valid)
        (
            {"type": "string", "minLength": 5},
            {"type": "string", "minLength": 10},
            {"type": "string", "minLength": 10},
        ),
        # String: maxLength constraint - child inherits maxLength
        (
            {"type": "string", "maxLength": 20},
            {"type": "string"},
            {"type": "string", "maxLength": 20},
        ),
        # String: maxLength constraint - child has equal or smaller maxLength (valid)
        (
            {"type": "string", "maxLength": 20},
            {"type": "string", "maxLength": 10},
            {"type": "string", "maxLength": 10},
        ),
        # String: multiple constraints combined
        (
            {"type": "string", "minLength": 5, "maxLength": 20, "pattern": "^[a-z]+$"},
            {"type": "string", "minLength": 8, "maxLength": 15},
            {"type": "string", "minLength": 8, "maxLength": 15, "pattern": "^[a-z]+$"},
        ),
        # Boolean: const constraint - child inherits parent const
        (
            {"type": "boolean", "const": True},
            {"type": "boolean"},
            {"type": "boolean", "const": True},
        ),
        # Boolean: const constraint - child has same const (valid)
        (
            {"type": "boolean", "const": False},
            {"type": "boolean", "const": False},
            {"type": "boolean", "const": False},
        ),
        # Integer: const constraint - child inherits parent const
        (
            {"type": "integer", "const": 42},
            {"type": "integer"},
            {"type": "integer", "const": 42},
        ),
        # Integer: const constraint - child has same const (valid)
        (
            {"type": "integer", "const": 42},
            {"type": "integer", "const": 42},
            {"type": "integer", "const": 42},
        ),
        # Integer: enum constraint - child inherits parent enum
        (
            {"type": "integer", "enum": [1, 2, 3]},
            {"type": "integer"},
            {"type": "integer", "enum": [1, 2, 3]},
        ),
        # Integer: enum constraint - child enum is subset (valid)
        (
            {"type": "integer", "enum": [1, 2, 3]},
            {"type": "integer", "enum": [1, 3]},
            {"type": "integer", "enum": [1, 3]},
        ),
        # Integer: minimum constraint - child inherits minimum
        (
            {"type": "integer", "minimum": 10},
            {"type": "integer"},
            {"type": "integer", "minimum": 10},
        ),
        # Integer: minimum constraint - child has equal or greater minimum (valid)
        (
            {"type": "integer", "minimum": 10},
            {"type": "integer", "minimum": 20},
            {"type": "integer", "minimum": 20},
        ),
        # Integer: maximum constraint - child inherits maximum
        (
            {"type": "integer", "maximum": 100},
            {"type": "integer"},
            {"type": "integer", "maximum": 100},
        ),
        # Integer: maximum constraint - child has equal or smaller maximum (valid)
        (
            {"type": "integer", "maximum": 100},
            {"type": "integer", "maximum": 50},
            {"type": "integer", "maximum": 50},
        ),
        # Integer: exclusiveMinimum constraint - child inherits exclusiveMinimum
        (
            {"type": "integer", "exclusiveMinimum": 0},
            {"type": "integer"},
            {"type": "integer", "exclusiveMinimum": 0},
        ),
        # Integer: exclusiveMinimum constraint - child has equal or greater (valid)
        (
            {"type": "integer", "exclusiveMinimum": 0},
            {"type": "integer", "exclusiveMinimum": 10},
            {"type": "integer", "exclusiveMinimum": 10},
        ),
        # Integer: exclusiveMaximum constraint - child inherits exclusiveMaximum
        (
            {"type": "integer", "exclusiveMaximum": 100},
            {"type": "integer"},
            {"type": "integer", "exclusiveMaximum": 100},
        ),
        # Integer: exclusiveMaximum constraint - child has equal or smaller (valid)
        (
            {"type": "integer", "exclusiveMaximum": 100},
            {"type": "integer", "exclusiveMaximum": 50},
            {"type": "integer", "exclusiveMaximum": 50},
        ),
        # Integer: multipleOf constraint - child inherits multipleOf
        (
            {"type": "integer", "multipleOf": 5},
            {"type": "integer"},
            {"type": "integer", "multipleOf": 5},
        ),
        # Integer: multipleOf constraint - child is multiple of parent (valid)
        (
            {"type": "integer", "multipleOf": 5},
            {"type": "integer", "multipleOf": 10},
            {"type": "integer", "multipleOf": 10},
        ),
        # Integer: multiple constraints combined
        (
            {"type": "integer", "minimum": 10, "maximum": 100, "multipleOf": 5},
            {"type": "integer", "minimum": 20, "maximum": 80},
            {"type": "integer", "minimum": 20, "maximum": 80, "multipleOf": 5},
        ),
        # Number: const constraint - child inherits parent const
        (
            {"type": "number", "const": 3.14},
            {"type": "number"},
            {"type": "number", "const": 3.14},
        ),
        # Number: const constraint - child has same const (valid)
        (
            {"type": "number", "const": 3.14},
            {"type": "number", "const": 3.14},
            {"type": "number", "const": 3.14},
        ),
        # Number: enum constraint - child inherits parent enum
        (
            {"type": "number", "enum": [1.5, 2.5, 3.5]},
            {"type": "number"},
            {"type": "number", "enum": [1.5, 2.5, 3.5]},
        ),
        # Number: enum constraint - child enum is subset (valid)
        (
            {"type": "number", "enum": [1.5, 2.5, 3.5]},
            {"type": "number", "enum": [1.5, 3.5]},
            {"type": "number", "enum": [1.5, 3.5]},
        ),
        # Number: minimum constraint - child inherits minimum
        (
            {"type": "number", "minimum": 0.0},
            {"type": "number"},
            {"type": "number", "minimum": 0.0},
        ),
        # Number: minimum constraint - child has equal or greater minimum (valid)
        (
            {"type": "number", "minimum": 0.0},
            {"type": "number", "minimum": 10.5},
            {"type": "number", "minimum": 10.5},
        ),
        # Number: maximum constraint - child inherits maximum
        (
            {"type": "number", "maximum": 100.0},
            {"type": "number"},
            {"type": "number", "maximum": 100.0},
        ),
        # Number: maximum constraint - child has equal or smaller maximum (valid)
        (
            {"type": "number", "maximum": 100.0},
            {"type": "number", "maximum": 50.5},
            {"type": "number", "maximum": 50.5},
        ),
        # Number: exclusiveMinimum constraint - child inherits exclusiveMinimum
        (
            {"type": "number", "exclusiveMinimum": 0.0},
            {"type": "number"},
            {"type": "number", "exclusiveMinimum": 0.0},
        ),
        # Number: exclusiveMinimum constraint - child has equal or greater (valid)
        (
            {"type": "number", "exclusiveMinimum": 0.0},
            {"type": "number", "exclusiveMinimum": 10.5},
            {"type": "number", "exclusiveMinimum": 10.5},
        ),
        # Number: exclusiveMaximum constraint - child inherits exclusiveMaximum
        (
            {"type": "number", "exclusiveMaximum": 100.0},
            {"type": "number"},
            {"type": "number", "exclusiveMaximum": 100.0},
        ),
        # Number: exclusiveMaximum constraint - child has equal or smaller (valid)
        (
            {"type": "number", "exclusiveMaximum": 100.0},
            {"type": "number", "exclusiveMaximum": 50.5},
            {"type": "number", "exclusiveMaximum": 50.5},
        ),
        # Number: multipleOf constraint - child inherits multipleOf
        (
            {"type": "number", "multipleOf": 0.5},
            {"type": "number"},
            {"type": "number", "multipleOf": 0.5},
        ),
        # Number: multipleOf constraint - child is multiple of parent (valid)
        (
            {"type": "number", "multipleOf": 0.5},
            {"type": "number", "multipleOf": 1.5},
            {"type": "number", "multipleOf": 1.5},
        ),
        # Number: multiple constraints combined
        (
            {"type": "number", "minimum": 0.0, "maximum": 100.0, "multipleOf": 0.5},
            {"type": "number", "minimum": 10.0, "maximum": 90.0},
            {"type": "number", "minimum": 10.0, "maximum": 90.0, "multipleOf": 0.5},
        ),
        # Array: minItems constraint - child inherits minItems
        (
            {"type": "array", "items": {"type": "string"}, "minItems": 2},
            {"type": "array", "items": {"type": "string"}},
            {"type": "array", "items": {"type": "string"}, "minItems": 2},
        ),
        # Array: minItems constraint - child has equal or greater minItems (valid)
        (
            {"type": "array", "items": {"type": "string"}, "minItems": 2},
            {"type": "array", "items": {"type": "string"}, "minItems": 5},
            {"type": "array", "items": {"type": "string"}, "minItems": 5},
        ),
        # Array: maxItems constraint - child inherits maxItems
        (
            {"type": "array", "items": {"type": "string"}, "maxItems": 10},
            {"type": "array", "items": {"type": "string"}},
            {"type": "array", "items": {"type": "string"}, "maxItems": 10},
        ),
        # Array: maxItems constraint - child has equal or smaller maxItems (valid)
        (
            {"type": "array", "items": {"type": "string"}, "maxItems": 10},
            {"type": "array", "items": {"type": "string"}, "maxItems": 5},
            {"type": "array", "items": {"type": "string"}, "maxItems": 5},
        ),
        # Array: uniqueItems constraint - child inherits uniqueItems
        (
            {"type": "array", "items": {"type": "string"}, "uniqueItems": True},
            {"type": "array", "items": {"type": "string"}},
            {"type": "array", "items": {"type": "string"}, "uniqueItems": True},
        ),
        # Array: uniqueItems constraint - child has same value (valid)
        (
            {"type": "array", "items": {"type": "string"}, "uniqueItems": True},
            {"type": "array", "items": {"type": "string"}, "uniqueItems": True},
            {"type": "array", "items": {"type": "string"}, "uniqueItems": True},
        ),
        # Array: minContains constraint - child inherits minContains
        (
            {"type": "array", "items": {"type": "string"}, "minContains": 1},
            {"type": "array", "items": {"type": "string"}},
            {"type": "array", "items": {"type": "string"}, "minContains": 1},
        ),
        # Array: minContains constraint - child has equal or greater (valid)
        (
            {"type": "array", "items": {"type": "string"}, "minContains": 1},
            {"type": "array", "items": {"type": "string"}, "minContains": 2},
            {"type": "array", "items": {"type": "string"}, "minContains": 2},
        ),
        # Array: maxContains constraint - child inherits maxContains
        (
            {"type": "array", "items": {"type": "string"}, "maxContains": 5},
            {"type": "array", "items": {"type": "string"}},
            {"type": "array", "items": {"type": "string"}, "maxContains": 5},
        ),
        # Array: maxContains constraint - child has equal or smaller (valid)
        (
            {"type": "array", "items": {"type": "string"}, "maxContains": 5},
            {"type": "array", "items": {"type": "string"}, "maxContains": 3},
            {"type": "array", "items": {"type": "string"}, "maxContains": 3},
        ),
        # Array: contains constraint - child inherits contains
        (
            {
                "type": "array",
                "items": {"type": "string"},
                "contains": {"type": "string", "pattern": "^test"},
            },
            {"type": "array", "items": {"type": "string"}},
            {
                "type": "array",
                "items": {"type": "string"},
                "contains": {"type": "string", "pattern": "^test"},
            },
        ),
        # Array: multiple constraints combined
        (
            {
                "type": "array",
                "items": {"type": "integer"},
                "minItems": 2,
                "maxItems": 10,
            },
            {
                "type": "array",
                "items": {"type": "integer"},
                "minItems": 3,
                "maxItems": 8,
            },
            {
                "type": "array",
                "items": {"type": "integer"},
                "minItems": 3,
                "maxItems": 8,
            },
        ),
        # Array: nested item constraints inherited
        (
            {"type": "array", "items": {"type": "string", "minLength": 3}},
            {"type": "array", "items": {"type": "string"}},
            {"type": "array", "items": {"type": "string", "minLength": 3}},
        ),
        # Array: nested item constraints narrowed
        (
            {
                "type": "array",
                "items": {"type": "string", "minLength": 3, "maxLength": 20},
            },
            {
                "type": "array",
                "items": {"type": "string", "minLength": 5, "maxLength": 15},
            },
            {
                "type": "array",
                "items": {"type": "string", "minLength": 5, "maxLength": 15},
            },
        ),
        # Type inference: child missing type inherits from parent
        (
            {"type": "string", "minLength": 5},
            {},
            {"type": "string", "minLength": 5},
        ),
        # Number: multipleOf with floats (tests precision fix - 0.2 is a multiple of 0.1)
        (
            {"type": "number", "multipleOf": 0.1},
            {"type": "number", "multipleOf": 0.2},
            {"type": "number", "multipleOf": 0.2},
        ),
        # Number: multipleOf with floats (0.3 is a multiple of 0.1)
        (
            {"type": "number", "multipleOf": 0.1},
            {"type": "number", "multipleOf": 0.3},
            {"type": "number", "multipleOf": 0.3},
        ),
        # String: const in parent enum is valid
        (
            {"type": "string", "enum": ["a", "b", "c"]},
            {"type": "string", "const": "b"},
            {"type": "string", "enum": ["a", "b", "c"], "const": "b"},
        ),
        # String: new pattern when parent has no pattern (valid regex)
        (
            {"type": "string"},
            {"type": "string", "pattern": "^[a-z]+$"},
            {"type": "string", "pattern": "^[a-z]+$"},
        ),
    ],
)
def test_inherit_schema_valid(parent_schema, child_schema, expected):
    """Test valid schema inheritance cases."""
    inherit_schema(parent_schema, child_schema)
    assert child_schema == expected


@pytest.mark.parametrize(
    "parent_schema,child_schema,error_match",
    [
        # String: const mismatch
        (
            {"type": "string", "const": "value1"},
            {"type": "string", "const": "value2"},
            r"Child 'const' value.*does not match parent 'const' value",
        ),
        # String: enum not subset
        (
            {"type": "string", "enum": ["a", "b"]},
            {"type": "string", "enum": ["a", "c"]},
            r"Child 'enum' values.*are not a subset",
        ),
        # String: pattern mismatch
        (
            {"type": "string", "pattern": "^[a-z]+$"},
            {"type": "string", "pattern": "^[A-Z]+$"},
            r"Child 'pattern'.*does not match parent 'pattern'",
        ),
        # String: format mismatch
        (
            {"type": "string", "format": "email"},
            {"type": "string", "format": "uri"},
            r"Child 'format'.*does not match parent 'format'",
        ),
        # String: minLength too small
        (
            {"type": "string", "minLength": 10},
            {"type": "string", "minLength": 5},
            r"Child 'minLength'.*is less than parent 'minLength'",
        ),
        # String: maxLength too large
        (
            {"type": "string", "maxLength": 20},
            {"type": "string", "maxLength": 30},
            r"Child 'maxLength'.*is greater than parent 'maxLength'",
        ),
        # Boolean: const mismatch
        (
            {"type": "boolean", "const": True},
            {"type": "boolean", "const": False},
            r"Child 'const' value.*does not match parent 'const' value",
        ),
        # Integer: const mismatch
        (
            {"type": "integer", "const": 42},
            {"type": "integer", "const": 43},
            r"Child 'const' value.*does not match parent 'const' value",
        ),
        # Integer: enum not subset
        (
            {"type": "integer", "enum": [1, 2, 3]},
            {"type": "integer", "enum": [1, 4]},
            r"Child 'enum' values.*are not a subset",
        ),
        # Integer: minimum too small
        (
            {"type": "integer", "minimum": 10},
            {"type": "integer", "minimum": 5},
            r"Child 'minimum'.*is less than parent 'minimum'",
        ),
        # Integer: maximum too large
        (
            {"type": "integer", "maximum": 100},
            {"type": "integer", "maximum": 150},
            r"Child 'maximum'.*is greater than parent 'maximum'",
        ),
        # Integer: exclusiveMinimum too small
        (
            {"type": "integer", "exclusiveMinimum": 10},
            {"type": "integer", "exclusiveMinimum": 5},
            r"Child 'exclusiveMinimum'.*is less than parent 'exclusiveMinimum'",
        ),
        # Integer: exclusiveMaximum too large
        (
            {"type": "integer", "exclusiveMaximum": 100},
            {"type": "integer", "exclusiveMaximum": 150},
            r"Child 'exclusiveMaximum'.*is greater than parent 'exclusiveMaximum'",
        ),
        # Integer: multipleOf not a multiple
        (
            {"type": "integer", "multipleOf": 5},
            {"type": "integer", "multipleOf": 7},
            r"Child 'multipleOf'.*must be a multiple of parent 'multipleOf'",
        ),
        # Number: const mismatch
        (
            {"type": "number", "const": 3.14},
            {"type": "number", "const": 2.71},
            r"Child 'const' value.*does not match parent 'const' value",
        ),
        # Number: enum not subset
        (
            {"type": "number", "enum": [1.5, 2.5]},
            {"type": "number", "enum": [1.5, 3.5]},
            r"Child 'enum' values.*are not a subset",
        ),
        # Number: minimum too small
        (
            {"type": "number", "minimum": 10.0},
            {"type": "number", "minimum": 5.0},
            r"Child 'minimum'.*is less than parent 'minimum'",
        ),
        # Number: maximum too large
        (
            {"type": "number", "maximum": 100.0},
            {"type": "number", "maximum": 150.0},
            r"Child 'maximum'.*is greater than parent 'maximum'",
        ),
        # Number: exclusiveMinimum too small
        (
            {"type": "number", "exclusiveMinimum": 10.0},
            {"type": "number", "exclusiveMinimum": 5.0},
            r"Child 'exclusiveMinimum'.*is less than parent 'exclusiveMinimum'",
        ),
        # Number: exclusiveMaximum too large
        (
            {"type": "number", "exclusiveMaximum": 100.0},
            {"type": "number", "exclusiveMaximum": 150.0},
            r"Child 'exclusiveMaximum'.*is greater than parent 'exclusiveMaximum'",
        ),
        # Number: multipleOf not a multiple
        (
            {"type": "number", "multipleOf": 0.5},
            {"type": "number", "multipleOf": 0.7},
            r"Child 'multipleOf'.*must be a multiple of parent 'multipleOf'",
        ),
        # Array: minItems too small
        (
            {"type": "array", "items": {"type": "string"}, "minItems": 5},
            {"type": "array", "items": {"type": "string"}, "minItems": 3},
            r"Child 'minItems'.*is less than parent 'minItems'",
        ),
        # Array: maxItems too large
        (
            {"type": "array", "items": {"type": "string"}, "maxItems": 10},
            {"type": "array", "items": {"type": "string"}, "maxItems": 15},
            r"Child 'maxItems'.*is greater than parent 'maxItems'",
        ),
        # Array: uniqueItems too permissive
        (
            {"type": "array", "items": {"type": "string"}, "uniqueItems": True},
            {"type": "array", "items": {"type": "string"}, "uniqueItems": False},
            r"Child 'uniqueItems' constraint cannot be less restrictive",
        ),
        # Array: minContains too small
        (
            {"type": "array", "items": {"type": "string"}, "minContains": 2},
            {"type": "array", "items": {"type": "string"}, "minContains": 1},
            r"Child 'minContains'.*is less than parent 'minContains'",
        ),
        # Array: maxContains too large
        (
            {"type": "array", "items": {"type": "string"}, "maxContains": 5},
            {"type": "array", "items": {"type": "string"}, "maxContains": 8},
            r"Child 'maxContains'.*is greater than parent 'maxContains'",
        ),
        # Array: contains constraint mismatch
        (
            {
                "type": "array",
                "items": {"type": "string"},
                "contains": {"type": "string", "pattern": "^test"},
            },
            {
                "type": "array",
                "items": {"type": "string"},
                "contains": {"type": "string", "pattern": "^other"},
            },
            r"Child 'contains' constraint does not match parent 'contains' constraint",
        ),
        # Array: nested item constraint violation (minLength too small)
        (
            {"type": "array", "items": {"type": "string", "minLength": 10}},
            {"type": "array", "items": {"type": "string", "minLength": 5}},
            r"Child 'minLength'.*is less than parent 'minLength'",
        ),
        # Array: nested item constraint violation (maxLength too large)
        (
            {"type": "array", "items": {"type": "string", "maxLength": 20}},
            {"type": "array", "items": {"type": "string", "maxLength": 30}},
            r"Child 'maxLength'.*is greater than parent 'maxLength'",
        ),
        # Type mismatch: string vs integer
        (
            {"type": "string"},
            {"type": "integer"},
            r"Child 'type'.*does not match parent 'type'",
        ),
        # Type mismatch: integer vs number
        (
            {"type": "integer"},
            {"type": "number"},
            r"Child 'type'.*does not match parent 'type'",
        ),
        # Type mismatch: boolean vs string
        (
            {"type": "boolean"},
            {"type": "string"},
            r"Child 'type'.*does not match parent 'type'",
        ),
        # Array: item type mismatch
        (
            {"type": "array", "items": {"type": "string"}},
            {"type": "array", "items": {"type": "integer"}},
            r"'items' inheritance: Child 'type'.*does not match parent 'type'",
        ),
        # Invalid child schema (not a dict)
        (
            {"type": "string"},
            "not a dict",
            r"Child schema must be a dictionary",
        ),
        # String: const not in parent enum
        (
            {"type": "string", "enum": ["a", "b", "c"]},
            {"type": "string", "const": "d"},
            r"Child 'const' value 'd' is not in parent 'enum' values",
        ),
        # Integer: const not in parent enum
        (
            {"type": "integer", "enum": [1, 2, 3]},
            {"type": "integer", "const": 4},
            r"Child 'const' value 4 is not in parent 'enum' values",
        ),
        # Number: const not in parent enum
        (
            {"type": "number", "enum": [1.0, 2.0, 3.0]},
            {"type": "number", "const": 4.0},
            r"Child 'const' value 4\.0 is not in parent 'enum' values",
        ),
        # Number: multipleOf not a multiple (using floats to test precision fix)
        (
            {"type": "number", "multipleOf": 0.1},
            {"type": "number", "multipleOf": 0.25},
            r"Child 'multipleOf' 0\.25 must be a multiple of parent 'multipleOf' 0\.1",
        ),
    ],
)
def test_inherit_schema_invalid(parent_schema, child_schema, error_match):
    """Test invalid schema inheritance cases that should raise ValueError."""
    with pytest.raises(ValueError, match=error_match):
        inherit_schema(parent_schema, child_schema)
