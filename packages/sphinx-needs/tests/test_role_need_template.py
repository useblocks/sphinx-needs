from pathlib import Path

import pytest

from sphinx_needs.roles.need_ref import _is_legacy_format_template


@pytest.mark.parametrize(
    "template,expected",
    [
        # Legacy str.format syntax.
        ("[{id}] {title}", True),
        ("{title:*^20s}", True),
        ("{content:.30}", True),
        ("{title} ({id})", True),
        # Jinja syntax (not legacy).
        ("{{ title }} ({{ id }})", False),
        ("{% if is_need %}[NEED]{% endif %}", False),
        ("{{ title }} {# comment #}", False),
        # Ambiguous escaped-brace form is treated as Jinja.
        ("{{literal}}", False),
        # Plain text with no placeholders.
        ("just text", False),
        ("", False),
    ],
)
def test_is_legacy_format_template(template, expected):
    assert _is_legacy_format_template(template) is expected


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "html", "srcdir": "doc_test/doc_role_need_template"}],
    indirect=True,
)
def test_doc_build_html(test_app):
    app = test_app
    app.build()
    warnings = app._warning.getvalue()
    # No template-rendering warnings should be emitted for valid templates.
    assert "link_text" not in warnings
    assert "needs_role_need_template" not in warnings
    html = Path(app.outdir, "index.html").read_text()
    assert "ROLE NEED TEMPLATE" in html

    # A plain need reference: {% if is_need %} branch is taken, is_part is
    # false, id/id_complete/id_parent resolve to the need id, id_part is empty
    # and the {{ type | upper }} filter is applied.
    assert (
        "[NEED] [SP_TOO_001] [SP_TOO_001] [SP_TOO_001] [] "
        "[SPEC] [SP_TOO_001] Command line interface (implemented) Specification/spec - test;test2 - SP_TOO_002 -  - "
        "The Tool awesome shall have a command line interface." in html
    )
    assert (
        "[NEED] [IM_TOO_001] [IM_TOO_001] [IM_TOO_001] [] "
        "[IMPL] [IM_TOO_001] Command line implementation (implemented) Implementation/impl -  -  -  - "
        "Implements command line interface." in html
    )

    # A need-part reference: the {% if is_part %} branch is taken, id_complete
    # carries the ``ID.part`` string, id_parent stays the parent need id and
    # id_part is the part id.
    assert (
        "[NEEDPART][SP_TOO_001.cli] [SP_TOO_001.cli] [SP_TOO_001] [cli] "
        "[SPEC] [SP_TOO_001.cli]  Command parser support (implemented) Specification/spec"
        in html
    )

    # Explicit inline templates ``[[ ... ]]`` are rendered as Jinja too, using
    # ``[[``/``]]`` as the variable delimiters (so filters work there as well).
    assert '<em class="xref need">IMPL</em>' in html
    assert '<em class="xref need"> COMMAND PARSER SUPPORT</em>' in html


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "html", "srcdir": "doc_test/doc_role_need_template_legacy"}],
    indirect=True,
)
def test_doc_build_html_legacy_format_template(test_app):
    """A legacy str.format template keeps working but warns about deprecation."""
    app = test_app
    app.build()
    warnings = app._warning.getvalue()
    assert "deprecated str.format syntax" in warnings
    html = Path(app.outdir, "index.html").read_text()
    # Rendered via str.format (not left as literal ``{id}`` text).
    assert "[SP_TOO_001] Command line interface (implemented)" in html
    assert "{id}" not in html


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "html", "srcdir": "doc_test/doc_role_need_template_invalid"}],
    indirect=True,
)
def test_doc_build_html_invalid_template(test_app):
    """An invalid Jinja template warns once and falls back to ``title (id)``."""
    app = test_app
    app.build()
    warnings = app._warning.getvalue()
    assert "needs_role_need_template could not be compiled" in warnings
    html = Path(app.outdir, "index.html").read_text()
    # Fallback representation is used instead of crashing the build.
    assert "Command line interface (SP_TOO_001)" in html
