"""Jinja2-compatible template rendering adapter using MiniJinja.

This module provides a thin wrapper around MiniJinja for rendering Jinja2 templates,
centralizing all template rendering logic in one place.
"""

from __future__ import annotations

from typing import Any, cast

from minijinja import Environment


def _wordwrap_filter(value: str, width: int = 79, wrapstring: str = "\n") -> str:
    """Jinja2-compatible wordwrap filter.

    Wraps text to specified width, inserting wrapstring between wrapped lines.
    This mimics the behavior of Jinja2's wordwrap filter.
    """
    words = value.split()
    if not words:
        return value

    lines = []
    current_line: list[str] = []
    current_length = 0

    for word in words:
        word_length = len(word)
        # +1 for the space before the word (except for the first word in a line)
        space_needed = word_length + (1 if current_line else 0)

        if current_length + space_needed <= width or not current_line:
            # Word fits on current line or it's the first word
            current_line.append(word)
            current_length += space_needed
        else:
            # Start a new line
            lines.append(" ".join(current_line))
            current_line = [word]
            current_length = word_length

    # Add the last line
    if current_line:
        lines.append(" ".join(current_line))

    return wrapstring.join(lines)


def _setup_builtin_filters(env: Environment) -> None:
    """Add Jinja2-compatible built-in filters to the environment."""
    env.add_filter("wordwrap", _wordwrap_filter)


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

    # Add built-in filters
    _setup_builtin_filters(env)

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
