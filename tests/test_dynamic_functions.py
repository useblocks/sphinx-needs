import json
import os
from pathlib import Path

import pytest
from sphinx import version_info
from sphinx.util.console import strip_colors
from syrupy.filters import props


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
        'srcdir/index.rst:40: WARNING: The `need_func` role is deprecated. Replace with :ndf:`copy("id")` instead. [needs.deprecated]',
        'srcdir/index.rst:44: WARNING: The `need_func` role is deprecated. Replace with :ndf:`copy("id")` instead. [needs.deprecated]',
        "srcdir/index.rst:23: WARNING: Dynamic function in list field 'tags' is surrounded by text that will be omitted: \"[[copy('title')]]omitted\" [needs.dynamic_function]",
        'srcdir/index.rst:9: WARNING: The [[copy("id")]] syntax in need content is deprecated. Replace with :ndf:`copy("id")` instead. [needs.deprecated]',
        'srcdir/index.rst:27: WARNING: The [[copy("tags")]] syntax in need content is deprecated. Replace with :ndf:`copy("tags")` instead. [needs.deprecated]',
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
    [{"buildername": "html", "srcdir": "doc_test/doc_df_calc_sum"}],
    indirect=True,
)
def test_doc_df_calc_sum(test_app):
    app = test_app
    app.build()
    html = Path(app.outdir, "index.html").read_text()
    assert "43210" in html  # all hours
    assert "3210" in html  # hours of linked needs
    assert "210" in html  # hours of filtered needs


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "html", "srcdir": "doc_test/doc_df_check_linked_values"}],
    indirect=True,
)
def test_doc_df_linked_values(test_app):
    app = test_app
    app.build()
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
        "srcdir/index.rst:10: WARNING: Return value of function 'bad_function' is of type <class 'object'>. Allowed are str, int, float, list [needs.dynamic_function]",
        "srcdir/index.rst:8: WARNING: The [[my_own_function()]] syntax in need content is deprecated. Replace with :ndf:`my_own_function()` instead. [needs.deprecated]",
        "srcdir/index.rst:14: WARNING: The [[bad_function()]] syntax in need content is deprecated. Replace with :ndf:`bad_function()` instead. [needs.deprecated]",
        "srcdir/index.rst:14: WARNING: Return value of function 'bad_function' is of type <class 'object'>. Allowed are str, int, float, list [needs.dynamic_function]",
        "srcdir/index.rst:16: WARNING: The [[invalid]] syntax in need content is deprecated. Replace with :ndf:`invalid` instead. [needs.deprecated]",
        "srcdir/index.rst:16: WARNING: Function string 'invalid' could not be parsed: Given dynamic function string is not a valid python call. Got: invalid [needs.dynamic_function]",
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
