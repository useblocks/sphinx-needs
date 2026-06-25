"""
Regression tests for needs_string_links option handling.

Before the fix, a field declared only via needs_string_links["options"] (and NOT
also registered in needs_fields / needs_extra_options) caused NeedDirective.run()
to emit a spurious "Unknown option '<field>'" warning (needs.directive) because the
match block had no case for string-link option names.
"""

from pathlib import Path

import pytest

_GITHUB_STRING_LINKS_CONF = (
    "extensions = ['sphinx_needs']\n"
    "needs_string_links = {\n"
    "    'github_issue': {\n"
    "        'regex': r'^(?P<value>[0-9]+)$',\n"
    "        'link_url': 'https://github.com/useblocks/sphinx-needs/issues/{{value}}',\n"
    "        'link_name': 'GitHub #{{value}}',\n"
    "        'options': ['github'],\n"
    "    }\n"
    "}\n"
)


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "files": [
                (Path("conf.py"), _GITHUB_STRING_LINKS_CONF),
                (
                    Path("index.rst"),
                    "Test\n====\n\n"
                    ".. req:: A requirement with a github field\n"
                    "   :id: REQ_001\n"
                    "   :github: 42\n\n"
                    "   Content here.\n",
                ),
            ],
        }
    ],
    indirect=True,
)
def test_string_links_option_not_declared_in_needs_fields_no_warning(test_app):
    """
    A field listed in needs_string_links options must NOT produce an
    'Unknown option' warning even when it is not also declared in needs_fields.

    Regression: sphinx-needs 8.x emitted needs.directive warning for such fields.
    """
    app = test_app
    app.build()
    warnings = app._warning.getvalue()
    assert "Unknown option 'github'" not in warnings


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "needs",
            "files": [
                (Path("conf.py"), _GITHUB_STRING_LINKS_CONF),
                (
                    Path("index.rst"),
                    "Test\n====\n\n"
                    ".. req:: A requirement with a github field\n"
                    "   :id: REQ_001\n"
                    "   :github: 42\n\n"
                    "   Content here.\n",
                ),
            ],
        }
    ],
    indirect=True,
)
def test_string_links_option_value_stored_as_extra(test_app):
    """
    The value of a needs_string_links option field must be stored in the needs
    data so the render-time link substitution can apply.  Use the needs builder
    (which outputs needs.json) to inspect the raw stored value without depending
    on which fields the default HTML layout chooses to display.
    """
    import json

    app = test_app
    app.build()
    needs_json = json.loads(Path(app.outdir, "needs.json").read_text())
    req = needs_json["versions"][""]["needs"]["REQ_001"]
    assert req.get("github") == "42"


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "files": [
                (Path("conf.py"), _GITHUB_STRING_LINKS_CONF),
                (
                    Path("index.rst"),
                    "Test\n====\n\n"
                    ".. req:: A requirement with an unknown option\n"
                    "   :id: REQ_002\n"
                    "   :truly_unknown_field: some-value\n\n"
                    "   Content here.\n",
                ),
            ],
        }
    ],
    indirect=True,
)
def test_truly_unknown_option_still_warns(test_app):
    """
    A field that is neither in needs_fields nor in needs_string_links options
    must still emit the 'Unknown option' warning (guard test for the fix).
    """
    app = test_app
    app.build()
    warnings = app._warning.getvalue()
    assert "Unknown option 'truly_unknown_field'" in warnings
