"""Jinja2-compatible template rendering adapter using MiniJinja.

This module provides a thin wrapper around MiniJinja for rendering Jinja2 templates,
centralizing all template rendering logic in one place.
"""

from __future__ import annotations

import textwrap
from typing import Any

from minijinja import Environment

# Module-level cached environments for performance
_CACHED_ENV: Environment | None = None
_CACHED_ENV_AUTOESCAPE: Environment | None = None


def _wordwrap_filter(value: str, width: int = 79, wrapstring: str = "\n") -> str:
    """Jinja2-compatible wordwrap filter.

    Wraps text to specified width, inserting wrapstring between wrapped lines.
    This uses Python's textwrap module to match Jinja2's wordwrap behavior.

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

    # Use textwrap.wrap which matches jinja2's behavior
    # break_on_hyphens=True is the Python/Jinja2 default
    lines = textwrap.wrap(
        value,
        width=width,
        break_long_words=True,
        break_on_hyphens=True,
    )

    return wrapstring.join(lines)


def _setup_builtin_filters(env: Environment) -> None:
    """Register filters missing from minijinja-py's compiled feature set.

    The minijinja-py wheel currently ships without the ``wordwrap`` Cargo
    feature of minijinja-contrib, so ``|wordwrap`` is unavailable by default.
    This registers a Python-side replacement.  This function can be removed
    once minijinja-py enables the ``wordwrap`` feature upstream.
    """
    env.add_filter("wordwrap", _wordwrap_filter)


def _get_cached_env(autoescape: bool) -> Environment:
    """Get or create a cached Environment instance.

    For performance, we cache module-level Environment instances to avoid
    recreating them on every render call. This is safe because the Environment
    is stateless for rendering purposes.

    Thread safety: Benign race condition - if multiple threads check for None
    simultaneously, worst case is creating extra Environment instances. Sphinx
    parallel builds use processes, not threads, so this is not a concern.

    :param autoescape: Whether to enable autoescaping.
    :return: A cached Environment instance.
    """
    global _CACHED_ENV, _CACHED_ENV_AUTOESCAPE

    if autoescape:
        if _CACHED_ENV_AUTOESCAPE is None:
            env = Environment()
            env.auto_escape_callback = lambda _name: True
            _setup_builtin_filters(env)
            _CACHED_ENV_AUTOESCAPE = env
        return _CACHED_ENV_AUTOESCAPE
    else:
        if _CACHED_ENV is None:
            env = Environment()
            _setup_builtin_filters(env)
            _CACHED_ENV = env
        return _CACHED_ENV


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
        # If custom functions are needed, create a new Environment
        # This is only used in needuml.py and is relatively infrequent
        env = Environment()
        if autoescape:
            env.auto_escape_callback = lambda _name: True
        _setup_builtin_filters(env)
        for name, func in functions.items():
            # Use add_global instead of add_function (same behavior, better type stubs)
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
