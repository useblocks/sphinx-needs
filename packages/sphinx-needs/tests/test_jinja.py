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
