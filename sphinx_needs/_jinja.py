"""Jinja2-compatible template rendering adapter using MiniJinja.

This module provides a thin wrapper around MiniJinja for rendering Jinja2 templates,
centralizing all template rendering logic in one place.
"""

from __future__ import annotations

import textwrap
from functools import lru_cache
from pathlib import Path
from typing import Any

from minijinja import Environment


def _wordwrap_filter(value: str, width: int = 79, wrapstring: str = "\n") -> str:
    """Jinja2-compatible wordwrap filter.

    Wraps text to specified width, inserting wrapstring between wrapped lines.
    This uses Python's textwrap module to match Jinja2's wordwrap behavior.

    Like Jinja2, this preserves existing newlines and wraps each line independently.

    Note: minijinja-contrib has a Rust-native wordwrap filter (since 2.12),
    but it is gated behind the optional ``wordwrap`` Cargo feature flag.
    The minijinja-py 2.15.1 wheel does not enable that feature
    (see minijinja-py/Cargo.toml — only ``pycompat`` and ``html_entities``
    are enabled from minijinja-contrib).  Once a future minijinja-py release
    enables the ``wordwrap`` feature, this custom filter can be removed.
    Upstream tracking: https://github.com/mitsuhiko/minijinja — no issue
    filed yet; consider opening one.
    """
    if not value:
        return value

    # Preserve newlines by wrapping each line independently (matches Jinja2)
    wrapped_lines = []
    for line in value.splitlines():
        # Use textwrap.wrap which matches jinja2's behavior
        # break_on_hyphens=True is the Python/Jinja2 default
        wrapped = textwrap.wrap(
            line,
            width=width,
            break_long_words=True,
            break_on_hyphens=True,
        )
        # textwrap.wrap returns empty list for empty strings, preserve empty lines
        wrapped_lines.extend(wrapped or [""])

    return wrapstring.join(wrapped_lines)


def _setup_builtin_filters(env: Environment) -> None:
    """Register filters missing from minijinja-py's compiled feature set.

    The minijinja-py wheel currently ships without the ``wordwrap`` Cargo
    feature of minijinja-contrib, so ``|wordwrap`` is unavailable by default.
    This registers a Python-side replacement.  This function can be removed
    once minijinja-py enables the ``wordwrap`` feature upstream.
    """
    env.add_filter("wordwrap", _wordwrap_filter)


def _new_env(autoescape: bool) -> Environment:
    """Create a new Environment with standard setup (filters, autoescape).

    :param autoescape: Whether to enable autoescaping.
    :return: A new Environment instance.
    """
    env = Environment()
    if autoescape:
        env.auto_escape_callback = lambda _name: True
    _setup_builtin_filters(env)
    return env


@lru_cache(maxsize=2)
def _get_cached_env(autoescape: bool) -> Environment:
    """Get or create a cached Environment instance (no custom functions).

    Cached per autoescape value. Safe because the Environment is not
    mutated after creation. Using lru_cache ensures thread safety.

    :param autoescape: Whether to enable autoescaping.
    :return: A cached Environment instance.
    """
    return _new_env(autoescape)


@lru_cache(maxsize=2)
def _get_base_env_for_functions(autoescape: bool) -> Environment:
    """Get a cached base Environment for the functions= code path.

    This env is mutated via add_global() on each call, but only with a
    fixed set of keys (need, uml, flow, filter, import, ref) whose
    values are overwritten each time, so no stale state leaks between calls.

    This optimization is important because needuml diagrams call
    render_template_string(functions={...}) recursively - each {{ uml("ID") }}
    in a template triggers another render, so a diagram with N needs would
    create N throwaway environments without this cache.

    :param autoescape: Whether to enable autoescaping.
    :return: A cached Environment instance (will be mutated).
    """
    return _new_env(autoescape)


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
    if functions:
        # Use cached base environment and overwrite globals
        # The functions dict keys are always the same (need, uml, flow, filter, import, ref)
        # so we can safely reuse the environment and just update the global values
        env = _get_base_env_for_functions(autoescape)
        for name, func in functions.items():
            # Use add_global instead of add_function (same behavior, better type stubs)
            # Overwrites any previous value for this key
            env.add_global(name, func)
    else:
        # For the common case (no custom functions), use cached Environment
        env = _get_cached_env(autoescape)

    return env.render_str(template_string, **context)


def render_template_file(
    template_path: str,
    context: dict[str, Any],
    *,
    autoescape: bool = True,
    functions: dict[str, Any] | None = None,
) -> str:
    """Render a Jinja template from a file path.

    :param template_path: Path to the template file.
    :param context: Dictionary containing template variables.
    :param autoescape: Whether to enable autoescaping (default: True).
    :param functions: Optional dictionary of custom functions to register.
    :return: The rendered template as a string.
    """
    content = Path(template_path).read_text(encoding="utf-8")
    return render_template_string(
        content, context, autoescape=autoescape, functions=functions
    )
