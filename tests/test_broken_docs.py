import os
from pathlib import Path

import pytest
from sphinx.testing.util import SphinxTestApp
from sphinx.util.console import strip_colors


def get_warnings(app: SphinxTestApp):
    return (
        strip_colors(app._warning.getvalue())
        .replace(str(app.srcdir) + os.path.sep, "<srcdir>/")
        .splitlines()
    )


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "srcdir": "doc_test/doc_basic",
            "confoverrides": {"needs_id_required": True},
            "no_plantuml": True,
        }
    ],
    indirect=True,
)
def test_id_required_build_html(test_app: SphinxTestApp):
    test_app.build()
    assert get_warnings(test_app) == [
        "<srcdir>/index.rst:8: WARNING: Need could not be created: No ID defined, but 'needs_id_required' is set to True. [needs.create_need]"
    ]


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "html", "srcdir": "doc_test/broken_doc", "no_plantuml": True}],
    indirect=True,
)
def test_duplicate_id(test_app: SphinxTestApp):
    test_app.build()
    assert get_warnings(test_app) == [
        "<srcdir>/index.rst:11: WARNING: Need could not be created: A need with ID 'SP_TOO_001' already exists. [needs.create_need]"
    ]
    html = (test_app.outdir / "index.html").read_text()
    assert "<h1>BROKEN DOCUMENT" in html
    assert "SP_TOO_001" in html


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "html", "srcdir": "doc_test/broken_links", "no_plantuml": True}],
    indirect=True,
)
def test_broken_links(test_app: SphinxTestApp):
    app = test_app
    app.build()

    assert get_warnings(test_app) == [
        "<srcdir>/index.rst:12: WARNING: Need 'SP_TOO_002' has unknown outgoing link 'NOT_WORKING_LINK' in field 'links' [needs.link_outgoing]",
        "<srcdir>/index.rst:21: WARNING: linked need BROKEN_LINK not found [needs.link_ref]",
    ]


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "srcdir": "doc_test/broken_statuses",
            "no_plantuml": True,
        }
    ],
    indirect=True,
)
def test_broken_statuses(test_app: SphinxTestApp):
    test_app.build()
    assert get_warnings(test_app) == [
        'WARNING: Config option "needs_statuses" is deprecated. Please use "needs_options.status.schema.enum" to define custom status field enum constraints. [needs.deprecated]',
        "ERROR: Need 'SP_TOO_002' has schema violations:",
        "  Severity:       violation",
        "  Field:          status",
        "  Need path:      SP_TOO_002",
        "  Schema path:    options > schema > properties > status > enum",
        '  Schema message: "NOT_ALLOWED" is not one of "open" or "implemented" [sn_schema_violation.option_fail]',
    ]


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "srcdir": "doc_test/broken_syntax_doc",
            "no_plantuml": True,
        }
    ],
    indirect=True,
)
def test_broken_syntax(test_app: SphinxTestApp):
    test_app.build()

    assert get_warnings(test_app) == [
        "<srcdir>/index.rst:19: WARNING: Need could not be created: 'collapse' value is invalid: Cannot convert 'other' to boolean [needs.create_need]",
    ]

    html = Path(test_app.outdir, "index.html").read_text()
    assert "SP_TOO_001" in html
    assert "SP_TOO_002" in html
    assert "SP_TOO_003" not in html


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "html", "srcdir": "doc_test/broken_tags", "no_plantuml": True}],
    indirect=True,
)
def test_broken_tags(test_app: SphinxTestApp):
    test_app.build()
    assert get_warnings(test_app) == [
        'WARNING: Config option "needs_tags" is deprecated. Please use "needs_options.tags.schema.items.enum" to define custom tags field enum constraints. [needs.deprecated]',
        "ERROR: Need 'SP_TOO_003' has schema violations:",
        "  Severity:       violation",
        "  Field:          tags.2",
        "  Need path:      SP_TOO_003",
        "  Schema path:    options > schema > properties > tags > items > enum",
        '  Schema message: "BROKEN" is not one of "new" or "security" [sn_schema_violation.option_fail]',
    ]
