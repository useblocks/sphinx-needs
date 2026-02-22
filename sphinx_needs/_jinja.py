"""Jinja2-compatible template rendering adapter using MiniJinja.

This module provides a thin wrapper around MiniJinja for rendering Jinja2 templates,
centralizing all template rendering logic in one place.
"""

from __future__ import annotations

import textwrap
from functools import lru_cache
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

    Cached per ``autoescape`` value.  Safe because the returned
    ``Environment`` is not mutated after creation.  ``lru_cache`` ensures
    that concurrent calls for the same key return the same instance
    (Python's GIL protects the cache dict).  Note that the
    ``Environment`` object itself is **not** thread-safe — this is
    acceptable because Sphinx builds are single-threaded.

    The cache persists for the lifetime of the process (e.g. across
    rebuilds in ``sphinx-autobuild``).  This is fine because the
    environments are stateless (no per-build data).

    :param autoescape: Whether to enable autoescaping.
    :return: A cached Environment instance.
    """
    return _new_env(autoescape)


def render_template_string(
    template_string: str,
    context: dict[str, Any],
    *,
    autoescape: bool,
    new_env: bool = False,
) -> str:
    """Render a Jinja template string with the given context.

    :param template_string: The Jinja template string to render.
    :param context: Dictionary containing template variables.
    :param autoescape: Whether to enable autoescaping.
    :param new_env: If True, create a fresh Environment instead of using
        the shared cached one.  This is required when rendering happens
        *inside* a Python callback invoked by an ongoing ``render_str`` on
        the cached Environment (e.g. needuml's ``{{ uml() }}`` callbacks),
        because MiniJinja's ``Environment`` holds a non-reentrant lock
        during ``render_str``.
    :return: The rendered template as a string.
    """
    env = _new_env(autoescape) if new_env else _get_cached_env(autoescape)
    return env.render_str(template_string, **context)


class CompiledTemplate:
    """A pre-compiled template for efficient repeated rendering.

    Use :func:`compile_template` to create instances.  The template source
    is parsed and compiled once; each :meth:`render` call only executes the
    already-compiled template, avoiding the per-call parse overhead of
    :func:`render_template_string` / ``Environment.render_str``.

    This is useful when the same template is rendered many times in a loop
    with different contexts (e.g. per-need in external needs loading,
    per-cell in needtable string-link rendering, per-need in constraint
    error messages, or per-node in PlantUML diagram generation).
    """

    __slots__ = ("_env",)

    _TEMPLATE_NAME = "__compiled__"

    def __init__(self, env: Environment) -> None:
        self._env = env

    def render(self, context: dict[str, Any]) -> str:
        """Render the compiled template with the given context.

        :param context: Dictionary containing template variables.
        :return: The rendered template as a string.
        """
        return self._env.render_template(self._TEMPLATE_NAME, **context)


@lru_cache(maxsize=32)
def compile_template(
    template_string: str,
    *,
    autoescape: bool,
) -> CompiledTemplate:
    """Compile a template string for efficient repeated rendering.

    The returned :class:`CompiledTemplate` parses the source once;
    subsequent :meth:`~CompiledTemplate.render` calls skip parsing entirely.
    Use this instead of :func:`render_template_string` when the same
    template is rendered in a tight loop with varying contexts.

    Results are cached by ``(template_string, autoescape)`` so that
    multiple call sites sharing the same template (e.g.
    ``needs_config.diagram_template``) only compile once per build.

    The cache persists for the lifetime of the process.  This is safe
    because compiled templates are keyed by their source text and are
    stateless.

    :param template_string: The Jinja template string to compile.
    :param autoescape: Whether to enable autoescaping.
    :return: A compiled template that can be rendered with different contexts.
    """
    env = _new_env(autoescape)
    env.add_template(CompiledTemplate._TEMPLATE_NAME, template_string)
    return CompiledTemplate(env)
