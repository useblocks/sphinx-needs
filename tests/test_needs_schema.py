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
    field = FieldSchema(
        name="test_field",
        type=type_,
        item_type=item_type,
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
    field = FieldSchema(
        name="test_field",
        type=type_,
        item_type=item_type,
        allow_dynamic_functions=allow_df,
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
    field = FieldSchema(
        name="test_field",
        type=type_,
        item_type=item_type,
        allow_dynamic_functions=True,
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
    field = FieldSchema(
        name="test_field",
        type=type_,
        item_type=item_type,
        allow_variant_functions=True,
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
    field = FieldSchema(
        name="test_field",
        type=type_,
        item_type=item_type,
        allow_dynamic_functions=allow_df,
        allow_variant_functions=allow_vf,
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
