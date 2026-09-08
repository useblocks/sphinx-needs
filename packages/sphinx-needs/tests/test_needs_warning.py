import pytest
from sphinx import version_info

from sphinx_needs_testkit import build_warnings


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "srcdir": "doc_test/doc_needs_warnings",
        }
    ],
    indirect=True,
)
def test_needs_warnings(test_app):
    app = test_app
    app.build()

    # stdout warnings
    warning_records = build_warnings(app)

    expected = [
        "WARNING: 'invalid_status' in 'needs_warnings' is already registered. [needs.config]",
        "WARNING: api_warning_filter: failed\n"
        "\t\tfailed needs: 1 (TC_002)\n"
        "\t\tused filter: status == 'example_2' [needs.warnings]",
        "WARNING: api_warning_func: failed\n"
        "\t\tfailed needs: 1 (TC_003)\n"
        "\t\tused filter: custom_warning_func [needs.warnings]",
        "WARNING: invalid_status: failed\n"
        "\t\tfailed needs: 2 (SP_TOO_001, US_63252)\n"
        "\t\tused filter: status not in ['open', 'closed', 'done', 'example_2', 'example_3'] [needs.warnings]",
        "WARNING: type_match: failed\n"
        "\t\tfailed needs: 1 (TC_001)\n"
        "\t\tused filter: my_custom_warning_check [needs.warnings]",
    ]

    if version_info >= (8, 2):
        expected.insert(
            1,
            "WARNING: cannot cache unpickleable configuration value: 'needs_warnings' (because it contains a function, class, or module object) [config.cache]",
        )
    elif version_info >= (8, 0):
        expected.insert(
            1,
            "WARNING: cannot cache unpickable configuration value: 'needs_warnings' (because it contains a function, class, or module object) [config.cache]",
        )
    elif version_info >= (7, 3):
        expected.insert(
            1,
            "WARNING: cannot cache unpickable configuration value: 'needs_warnings' (because it contains a function, class, or module object)",
        )

    assert warning_records == expected


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "srcdir": "doc_test/doc_needs_warnings_return_status_code",
        }
    ],
    indirect=True,
)
def test_needs_warnings_return_status_code(test_app):
    """Every check this project fails is reported through Sphinx's warning logger.

    That is the sphinx-needs claim, and it is what makes ``-W`` fail such a build. The
    exit codes ``-W`` and ``--keep-going`` produce are Sphinx's own contract -- they
    changed in 8.1 -- so they are not asserted here.
    """
    app = test_app
    app.build()

    # nothing is reported through the status stream instead
    assert "WARNING" not in app._status.getvalue()

    expected = [
        "WARNING: invalid_status: failed\n"
        "\t\tfailed needs: 2 (SP_TOO_001, US_63252)\n"
        "\t\tused filter: status not in ['open', 'closed', 'done', 'example_2', 'example_3'] [needs.warnings]",
        "WARNING: type_match: failed\n"
        "\t\tfailed needs: 1 (TC_001)\n"
        "\t\tused filter: my_custom_warning_check [needs.warnings]",
    ]

    if version_info >= (8, 2):
        expected.insert(
            0,
            "WARNING: cannot cache unpickleable configuration value: 'needs_warnings' (because it contains a function, class, or module object) [config.cache]",
        )
    elif version_info >= (8, 0):
        expected.insert(
            0,
            "WARNING: cannot cache unpickable configuration value: 'needs_warnings' (because it contains a function, class, or module object) [config.cache]",
        )
    elif version_info >= (7, 3):
        expected.insert(
            0,
            "WARNING: cannot cache unpickable configuration value: 'needs_warnings' (because it contains a function, class, or module object)",
        )

    assert build_warnings(app) == expected


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "files": [
                (
                    "index.rst",
                    "Test\n====\n\n.. story:: A story\n   :id: US_001\n",
                ),
                (
                    "conf.py",
                    """
extensions = ["sphinx_needs"]
needs_types = [
    {
        "directive": "story",
        "title": "User Story",
        "prefix": "US_",
        "color": "#BFD8D2",
        "style": "node",
    },
]
needs_warnings = {"unknown_filter": 42}
""",
                ),
            ],
        }
    ],
    indirect=True,
)
def test_needs_warnings_unknown_filter_type(test_app):
    """A filter that is neither a string nor a callable is reported, not raised."""
    app = test_app
    app.build()

    warning_records = build_warnings(app)

    assert warning_records == [
        "WARNING: Unknown needs warnings filter 42! [needs.config]"
    ]
