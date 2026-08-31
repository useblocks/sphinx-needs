"""Unit tests for the MiniJinja adapter in :mod:`sphinx_needs._jinja`."""

from __future__ import annotations

import pytest
from minijinja import TemplateError

from sphinx_needs._jinja import (
    compile_template,
    render_template_string,
)


def test_render_template_string_default_delimiters():
    result = render_template_string(
        "{{ title }} ({{ id }})",
        {"title": "My title", "id": "ID_1"},
        autoescape=False,
    )
    assert result == "My title (ID_1)"


def test_render_template_string_custom_delimiters():
    """The ``[[``/``]]`` syntax used by the inline ``:need:`` role text."""
    result = render_template_string(
        "[[ title ]] ([[ id ]])",
        {"title": "My title", "id": "ID_1"},
        autoescape=False,
        variable_start_string="[[",
        variable_end_string="]]",
    )
    assert result == "My title (ID_1)"


def test_compile_template_custom_delimiters():
    template = compile_template(
        "[[ title | upper ]]",
        autoescape=False,
        variable_start_string="[[",
        variable_end_string="]]",
    )
    assert template.render({"title": "My title"}) == "MY TITLE"


def test_compile_template_custom_delimiters_keep_block_syntax():
    """Only the variable delimiters change; control structures stay ``{% %}``."""
    template = compile_template(
        "[[ id ]]{% if is_part %}.[[ id_part ]]{% endif %}",
        autoescape=False,
        variable_start_string="[[",
        variable_end_string="]]",
    )
    assert template.render({"id": "ID_1", "id_part": "p", "is_part": True}) == "ID_1.p"
    assert template.render({"id": "ID_1", "id_part": "", "is_part": False}) == "ID_1"


def test_compile_template_cache_is_keyed_on_delimiters():
    """Same source with different delimiters must not collide in the cache."""
    default = compile_template("{{ id }}", autoescape=False)
    custom = compile_template(
        "{{ id }}",
        autoescape=False,
        variable_start_string="[[",
        variable_end_string="]]",
    )
    # With ``[[``/``]]`` delimiters, ``{{ id }}`` is literal text.
    assert default.render({"id": "ID_1"}) == "ID_1"
    assert custom.render({"id": "ID_1"}) == "{{ id }}"


def test_compile_template_invalid_syntax_raises():
    with pytest.raises(TemplateError):
        compile_template("{{ unclosed ", autoescape=False)


def test_wordwrap_is_minijinjas_native_filter():
    """``wordwrap`` comes from the minijinja wheel, not from a Python filter.

    sphinx-needs used to register its own ``textwrap``-based ``wordwrap``
    because the wheel shipped without minijinja-contrib's ``wordwrap`` Cargo
    feature.  The 2.24 wheel compiles it, the Python filter is gone, and this
    test pins the native one in the exact shape
    :data:`~sphinx_needs.defaults.DEFAULT_DIAGRAM_TEMPLATE` calls it —
    ``width`` as a KEYWORD, since the native filter takes no positional width.
    """
    result = render_template_string(
        "**{{ title|wordwrap(width=15, wrapstring='**\\n**') }}**",
        {"title": "A very long need title that must be wrapped"},
        autoescape=False,
    )
    assert result == "**A very long**\n**need title that**\n**must be wrapped**"


def test_wordwrap_rejects_a_positional_width():
    """The native filter is keyword-only, unlike jinja2's ``wordwrap``.

    This is the upgrade's one user-visible break, so it is pinned rather than
    left to be rediscovered: a custom ``needs_diagram_template`` written for
    jinja2 (or for the Python filter this replaced) fails the build until its
    ``wordwrap(15)`` becomes ``wordwrap(width=15)``.
    """
    with pytest.raises(TemplateError, match="too many arguments"):
        render_template_string(
            "{{ title|wordwrap(15) }}", {"title": "a b c"}, autoescape=False
        )


def test_wordwrap_preserves_existing_newlines():
    """Each line wraps independently, as the Python filter did before it."""
    result = render_template_string(
        "{{ v|wordwrap(width=5) }}", {"v": "aaa bbb\n\nccc ddd"}, autoescape=False
    )
    assert result == "aaa\nbbb\n\nccc\nddd"


def test_wordwrap_breaks_after_a_hyphen_unlike_python_textwrap():
    """The changelog's ``(changed output)`` behaviour, pinned.

    The native filter starts the fragment after a hyphen on a fresh line,
    where Python's ``textwrap`` back-filled the current line with its head
    (giving ``abc-de\\nfghij`` here).  This is the one assertion that
    separates the native filter from any ``textwrap``-based replacement,
    so it turns red if a future wheel silently reverts to textwrap-style
    hyphen filling.
    """
    result = render_template_string(
        "{{ v|wordwrap(width=6) }}", {"v": "abc-defghij"}, autoescape=False
    )
    assert result == "abc-\ndefghi\nj"
