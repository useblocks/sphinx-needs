import json
import os
from pathlib import Path

import pytest
from sphinx import version_info
from sphinx.util.console import strip_colors
from syrupy.filters import props

from sphinx_needs.exceptions import FunctionParsingException
from sphinx_needs.functions.functions import (
    DynamicFunctionParsed,
    NeedAttribute,
)


@pytest.mark.parametrize(
    "func_str,expected_name,expected_args,expected_kwargs",
    [
        ("my_function()", "my_function", (), ()),
        ("my_function(1, 2, 3.0)", "my_function", (1, 2, 3.0), ()),
        ('my_function("a", "b", "c")', "my_function", ("a", "b", "c"), ()),
        ("my_function(True, False)", "my_function", (True, False), ()),
        ("my_function(need.a)", "my_function", (NeedAttribute("a"),), ()),
        (
            'my_function(1, "a", True)',
            "my_function",
            (1, "a", True),
            (),
        ),
        (
            'my_function(1, "a", True, kwarg1=2, kwarg2=3.0, kwarg3="b", kwarg4=False, kwarg5=need.b)',
            "my_function",
            (1, "a", True),
            (
                ("kwarg1", 2),
                ("kwarg2", 3.0),
                ("kwarg3", "b"),
                ("kwarg4", False),
                ("kwarg5", NeedAttribute("b")),
            ),
        ),
        (
            'my_function(kwarg1=[1, 2, 3], kwarg2=[1.0, 2.0, 3.0], kwarg3=["a", "b", "c"], kwarg4=[True, False])',
            "my_function",
            (),
            (
                ("kwarg1", [1, 2, 3]),
                ("kwarg2", [1.0, 2.0, 3.0]),
                ("kwarg3", ["a", "b", "c"]),
                ("kwarg4", [True, False]),
            ),
        ),
    ],
)
def test_dynamic_function_from_string(
    func_str, expected_name, expected_args, expected_kwargs
):
    dynamic_func = DynamicFunctionParsed.from_string(func_str, allow_need=True)

    assert dynamic_func.name == expected_name
    assert dynamic_func.args == expected_args
    assert dynamic_func.kwargs == expected_kwargs


@pytest.mark.parametrize(
    "func_str,error_message",
    [
        ("", "Error parsing dynamic function: Not a function call"),
        ("x.", "Error parsing dynamic function: Not a function call"),
        ("xx", "Error parsing dynamic function: Not a function call"),
        (
            "dunc(None)",
            "Error parsing dynamic function 'dunc': Unsupported arg 0 value type",
        ),
        (
            "dunc([None])",
            "Error parsing dynamic function 'dunc': Unsupported arg 0 item 0 value type",
        ),
        (
            "dunc(x)",
            "Error parsing dynamic function 'dunc': Unsupported arg 0 value type",
        ),
        (
            "dunc(1, x.y)",
            "Error parsing dynamic function 'dunc': Unsupported arg 1 value type",
        ),
        (
            "dunc(func())",
            "Error parsing dynamic function 'dunc': Unsupported arg 0 value type",
        ),
        (
            "dunc(x=x)",
            "Error parsing dynamic function 'dunc': Unsupported kwarg 'x' value type",
        ),
        (
            "dunc(1, y=x.y)",
            "Error parsing dynamic function 'dunc': Unsupported kwarg 'y' value type",
        ),
        (
            "dunc(z=func())",
            "Error parsing dynamic function 'dunc': Unsupported kwarg 'z' value type",
        ),
        (
            "dunc(x=None)",
            "Error parsing dynamic function 'dunc': Unsupported kwarg 'x' value type",
        ),
        (
            "dunc(x=[None])",
            "Error parsing dynamic function 'dunc': Unsupported kwarg 'x' item 0 value type",
        ),
        (
            "dunc([need.x])",
            "Error parsing dynamic function 'dunc': Unsupported arg 0 item 0 value type",
        ),
        (
            "dunc(x=[1, need.x])",
            "Error parsing dynamic function 'dunc': Unsupported kwarg 'x' item 1 value type",
        ),
    ],
)
def test_dynamic_function_from_string_fail(func_str, error_message):
    with pytest.raises(FunctionParsingException, match=error_message):
        DynamicFunctionParsed.from_string(func_str, allow_need=True)


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "srcdir": "doc_test/doc_dynamic_functions",
            "no_plantuml": True,
        }
    ],
    indirect=True,
)
def test_doc_dynamic_functions(test_app, snapshot):
    app = test_app
    app.build()

    warnings = strip_colors(
        app._warning.getvalue().replace(str(app.srcdir) + os.sep, "srcdir/")
    ).splitlines()
    assert warnings == [
        'srcdir/index.rst:11: WARNING: The `need_func` role is deprecated. Replace with :ndf:`copy("id")` instead. [needs.deprecated]',
        "srcdir/index.rst:23: WARNING: Need could not be created: 'tags' value is invalid: only one string, dynamic function or variant function allowed per array item. [needs.create_need]",
        'srcdir/index.rst:40: WARNING: The `need_func` role is deprecated. Replace with :ndf:`copy("id")` instead. [needs.deprecated]',
        'srcdir/index.rst:44: WARNING: The `need_func` role is deprecated. Replace with :ndf:`copy("id")` instead. [needs.deprecated]',
        "srcdir/index.rst:46: WARNING: Need could not be created: Extra option 'test_func' is invalid: Error parsing dynamic function 'test': Unsupported arg 0 value type [needs.create_need]",
        "srcdir/index.rst:52: WARNING: Need could not be created: Extra option 'test_func' is invalid: Error parsing dynamic function 'test': Unsupported arg 0 value type [needs.create_need]",
        'srcdir/index.rst:9: WARNING: The [[copy("id")]] syntax in need content is deprecated. Replace with :ndf:`copy("id")` instead. [needs.deprecated]',
        "srcdir/index.rst:33: WARNING: The [[copy('id')]] syntax in need content is deprecated. Replace with :ndf:`copy('id')` instead. [needs.deprecated]",
        "srcdir/index.rst:38: WARNING: The [[copy('id')]] syntax in need content is deprecated. Replace with :ndf:`copy('id')` instead. [needs.deprecated]",
        "srcdir/index.rst:44: WARNING: Error while executing function 'copy': Need not found [needs.dynamic_function]",
        "srcdir/index.rst:44: WARNING: Error while executing function 'copy': Need not found [needs.dynamic_function]",
    ]

    json_data = Path(app.outdir, "needs.json").read_text()
    needs = json.loads(json_data)
    assert needs == snapshot(exclude=props("created", "project", "creator"))


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "srcdir": "doc_test/doc_df_calc_sum",
            "no_plantuml": True,
        }
    ],
    indirect=True,
)
def test_doc_df_calc_sum(test_app):
    app = test_app
    app.build()
    warnings = strip_colors(app._warning.getvalue()).splitlines()
    assert warnings == []
    html = Path(app.outdir, "index.html").read_text()
    assert "43210" in html  # all hours
    assert "3210" in html  # hours of linked needs
    assert "210" in html  # hours of filtered needs


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "srcdir": "doc_test/doc_df_check_linked_values",
            "no_plantuml": True,
        }
    ],
    indirect=True,
)
def test_doc_df_linked_values(test_app):
    app = test_app
    app.build()
    warnings = strip_colors(app._warning.getvalue()).splitlines()
    assert warnings == []
    html = Path(app.outdir, "index.html").read_text()
    assert "all_good" in html
    assert "all_bad" not in html
    assert "all_awesome" in html


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "srcdir": "doc_test/doc_df_user_functions",
            "no_plantuml": True,
        }
    ],
    indirect=True,
)
def test_doc_df_user_functions(test_app):
    app = test_app
    app.build()

    warnings = strip_colors(
        app._warning.getvalue().replace(str(app.srcdir) + os.sep, "srcdir/")
    ).splitlines()
    # print(warnings)
    expected = [
        "srcdir/index.rst:10: WARNING: Error while resolving dynamic values for field 'status', of need 'TEST_2': dynamic function value <class 'object'> is not of type 'string' [needs.dynamic_function]",
        "srcdir/index.rst:8: WARNING: The [[my_own_function()]] syntax in need content is deprecated. Replace with :ndf:`my_own_function()` instead. [needs.deprecated]",
        "srcdir/index.rst:14: WARNING: The [[bad_function()]] syntax in need content is deprecated. Replace with :ndf:`bad_function()` instead. [needs.deprecated]",
        "srcdir/index.rst:14: WARNING: Return value of function 'bad_function' is of type <class 'object'>. Allowed are str, int, float, list [needs.dynamic_function]",
        "srcdir/index.rst:16: WARNING: The [[invalid]] syntax in need content is deprecated. Replace with :ndf:`invalid` instead. [needs.deprecated]",
        "srcdir/index.rst:16: WARNING: Error parsing dynamic function: Not a function call [needs.dynamic_function]",
        "srcdir/index.rst:18: WARNING: The [[unknown()]] syntax in need content is deprecated. Replace with :ndf:`unknown()` instead. [needs.deprecated]",
        "srcdir/index.rst:18: WARNING: Unknown function 'unknown' [needs.dynamic_function]",
    ]
    if version_info >= (7, 3):
        warn = "WARNING: cannot cache unpickable configuration value: 'needs_functions' (because it contains a function, class, or module object)"
        if version_info >= (8, 0):
            warn += " [config.cache]"
        if version_info >= (8, 2):
            warn = warn.replace("unpickable", "unpickleable")
        expected.insert(0, warn)
    assert warnings == expected

    html = Path(app.outdir, "index.html").read_text()
    assert "Awesome" in html
