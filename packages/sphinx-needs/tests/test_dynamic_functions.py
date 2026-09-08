import json
from pathlib import Path

import pytest
from sphinx import version_info
from syrupy.filters import props

from sphinx_needs.exceptions import FunctionParsingException
from sphinx_needs.functions.functions import (
    DynamicFunctionParsed,
    NeedAttribute,
)
from sphinx_needs_testkit import assert_no_warnings, build_warnings


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
        }
    ],
    indirect=True,
)
def test_doc_dynamic_functions(test_app, snapshot):
    app = test_app
    app.build()

    warning_records = build_warnings(app)
    assert warning_records == [
        "<srcdir>/index.rst:21: WARNING: Need could not be created: 'tags' value is invalid: only one string, dynamic function or variant function allowed per array item. [needs.create_need]",
        "<srcdir>/index.rst:42: WARNING: Need could not be created: Field 'test_func' is invalid: Error parsing dynamic function 'test': Unsupported arg 0 value type [needs.create_need]",
        "<srcdir>/index.rst:48: WARNING: Need could not be created: Field 'test_func' is invalid: Error parsing dynamic function 'test': Unsupported arg 0 value type [needs.create_need]",
        "<srcdir>/index.rst:40: WARNING: Error while executing function 'copy': Need not found [needs.dynamic_function]",
    ]

    html = Path(app.outdir, "index.html").read_text()
    # since 9.0.0 ``[[...]]`` in a need's CONTENT is plain text, and only the ``ndf`` role runs
    # a dynamic function there.  Sphinx's smartquotes transform has already curled the quotes by
    # the time the text is rendered -- which is what the removed scan used to undo before it ran
    # the call, and one of the reasons the syntax was surprising.
    assert "This is id [[copy(\u201cid\u201d)]]" in html
    assert "This is the best id SP_TOO_001" in html
    assert "nested id [[copy(\u2018id\u2019)]]" in html
    assert "nested id best TEST_6" in html
    # a link's URI is left alone too
    assert "href=\"http://www.[[copy('id')]]\"" in html

    json_data = Path(app.outdir, "needs.json").read_text()
    needs = json.loads(json_data)
    assert needs == snapshot(exclude=props("created", "project", "creator"))


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "srcdir": "doc_test/doc_df_calc_sum",
        }
    ],
    indirect=True,
)
def test_doc_df_calc_sum(test_app):
    app = test_app
    app.build()
    assert_no_warnings(app)
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
        }
    ],
    indirect=True,
)
def test_doc_df_linked_values(test_app):
    app = test_app
    app.build()
    assert_no_warnings(app)
    html = Path(app.outdir, "index.html").read_text()
    assert "all_good" in html
    assert "all_bad" not in html
    assert "all_awesome" in html


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "srcdir": "doc_test/doc_df_links_from_content",
        }
    ],
    indirect=True,
)
def test_doc_df_links_from_content(test_app, snapshot):
    app = test_app
    app.build()
    warning_records = build_warnings(app)
    assert warning_records == [
        "<srcdir>/index.rst:51: WARNING: links_from_content: no stored node for need 'unknown1' [needs.dynamic_function]",
        "<srcdir>/index.rst:51: WARNING: links_from_content: no stored node for need 'unknown2' [needs.dynamic_function]",
        "<srcdir>/index.rst:57: WARNING: Error while executing function 'links_from_content': No need found for links_from_content [needs.dynamic_function]",
        "WARNING: links_from_content: no stored node for need 'unknown3' [needs.dynamic_function]",
    ]

    json_data = Path(app.outdir, "needs.json").read_text()
    needs = json.loads(json_data)
    assert needs == snapshot(exclude=props("created", "project", "creator"))


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "srcdir": "doc_test/doc_df_user_functions",
        }
    ],
    indirect=True,
)
def test_doc_df_user_functions(test_app):
    app = test_app
    app.build()

    warning_records = build_warnings(app)
    # print(warnings)
    expected = [
        "<srcdir>/index.rst:12: WARNING: Error while resolving dynamic values for field 'status', of need 'TEST_2': dynamic function value <class 'object'> is not of type 'string' [needs.dynamic_function]",
        "<srcdir>/index.rst:16: WARNING: Return value of function 'bad_function' is of type <class 'object'>. Allowed are str, int, float, list [needs.dynamic_function]",
        "<srcdir>/index.rst:18: WARNING: Error parsing dynamic function: Not a function call [needs.dynamic_function]",
        "<srcdir>/index.rst:20: WARNING: Unknown function 'unknown' [needs.dynamic_function]",
    ]
    if version_info >= (7, 3):
        warn = "WARNING: cannot cache unpickable configuration value: 'needs_functions' (because it contains a function, class, or module object)"
        if version_info >= (8, 0):
            warn += " [config.cache]"
        if version_info >= (8, 2):
            warn = warn.replace("unpickable", "unpickleable")
        expected.insert(0, warn)
    assert warning_records == expected

    html = Path(app.outdir, "index.html").read_text()
    assert "Awesome" in html
    # the same call written as ``[[...]]`` in the content is plain text since 9.0.0
    assert "[[my_own_function()]] is not a dynamic function here" in html


# -- the ``need_func`` role, removed in 9.0.0 --------------------------------
#
# It was deprecated in 4.0.0 together with ``[[...]]`` in a need's content, and
# ``ndf`` replaces both.  Nothing registers it any more, so a document that still
# writes it gets docutils' own diagnostic for a role that does not exist.

NEED_FUNC_CONF = """\
extensions = ["sphinx_needs"]
"""

NEED_FUNC_INDEX = """\
Removed role
============

.. req:: One
   :id: R_ONE

   This is id :need_func:`[[copy("id")]]`
"""


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "files": [
                (Path("conf.py"), NEED_FUNC_CONF),
                (Path("index.rst"), NEED_FUNC_INDEX),
            ],
        }
    ],
    indirect=True,
)
def test_need_func_role_removed(test_app):
    app = test_app
    app.build()

    warning_records = build_warnings(app)
    assert len(warning_records) == 1, warning_records
    assert 'Unknown interpreted text role "need_func"' in warning_records[0]
