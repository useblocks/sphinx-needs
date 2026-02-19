"""Jinja2-compatible template rendering adapter using MiniJinja.

This module provides a thin wrapper around MiniJinja for rendering Jinja2 templates,
centralizing all template rendering logic in one place.
"""

from __future__ import annotations

from typing import Any, cast

from minijinja import Environment


def render_template_string(
    template_string: str,
    context: dict[str, Any],
    *,
    autoescape: bool = True,
    functions: dict[str, Any] | None = None,
) -> str:
    """Render a Jinja template string with the given context.

    :param template_string: The Jinja template string to render.
    :param context: Dictionary containing template variables.
    :param autoescape: Whether to enable autoescaping (default: True).
    :param functions: Optional dictionary of custom functions to register.
    :return: The rendered template as a string.
    """
    env = Environment()
    if autoescape:
        # Set auto_escape_callback to always return True for all templates
        env.auto_escape_callback = lambda _name: True
    if functions:
        for name, func in functions.items():
            env.add_function(name, func)
    return cast(str, env.render_str(template_string, **context))


def render_template_file(
    template_path: str,
    context: dict[str, Any],
    *,
    autoescape: bool = True,
) -> str:
    """Render a Jinja template from a file path.

    :param template_path: Path to the template file.
    :param context: Dictionary containing template variables.
    :param autoescape: Whether to enable autoescaping (default: True).
    :return: The rendered template as a string.
    """
    from pathlib import Path

    content = Path(template_path).read_text(encoding="utf-8")
    return render_template_string(content, context, autoescape=autoescape)
