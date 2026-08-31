"""Jinja2-compatible template rendering adapter using MiniJinja.

This module provides a thin wrapper around MiniJinja for rendering Jinja2 templates,
centralizing all template rendering logic in one place.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from minijinja import Environment, TemplateError

_WORDWRAP_WIDTH_HINT = (
    "hint: if this is the wordwrap filter rejecting a positional width — "
    "MiniJinja's built-in wordwrap takes its width only by name: "
    "write wordwrap(width=15), not wordwrap(15). "
    "(sphinx-needs' former Python-side wordwrap accepted the jinja2 positional form.)"
)


def _hinted(err: TemplateError, template_string: str) -> TemplateError | None:
    """Build a hinted copy of ``err`` for a positional-``wordwrap`` failure.

    The switch from sphinx-needs' Python-side ``wordwrap`` to MiniJinja's
    built-in made the jinja2 spelling ``wordwrap(15)`` a ``too many
    arguments`` error, which surfaces as an unlocated build abort.  Appending
    the migration hint here — the one choke point every template render goes
    through — makes that failure actionable on every surface at once.

    :param err: The error a render raised.
    :param template_string: The template source that was being rendered.
    :return: A ``TemplateError`` with the hint appended, or ``None`` when the
        error is not the positional-``wordwrap`` shape (the caller should
        re-raise the original unchanged).
    """
    if "too many arguments" in str(err) and "wordwrap(" in template_string:
        return TemplateError(f"{err}\n{_WORDWRAP_WIDTH_HINT}")
    return None


def _new_env(
    autoescape: bool,
    variable_start_string: str = "{{",
    variable_end_string: str = "}}",
) -> Environment:
    """Create a new Environment with standard setup (delimiters, autoescape).

    No filters are registered here: MiniJinja's own built-ins (including
    ``wordwrap``, native since the minijinja 2.24 wheel) are all this
    package uses.

    :param autoescape: Whether to enable autoescaping.
    :param variable_start_string: Delimiter that opens a variable expression
        (default ``"{{"``).  Override to render templates that use a
        different syntax, e.g. ``"[["`` for the inline ``:need:`` role text.
    :param variable_end_string: Delimiter that closes a variable expression
        (default ``"}}"``).
    :return: A new Environment instance.
    """
    env = Environment(
        variable_start_string=variable_start_string,
        variable_end_string=variable_end_string,
    )
    if autoescape:
        env.auto_escape_callback = lambda _name: True
    return env


@lru_cache(maxsize=4)
def _get_cached_env(
    autoescape: bool,
    variable_start_string: str = "{{",
    variable_end_string: str = "}}",
) -> Environment:
    """Get or create a cached Environment instance (no custom functions).

    Cached per ``(autoescape, variable_start_string, variable_end_string)``.
    Safe because the returned
    ``Environment`` is not mutated after creation.  ``lru_cache`` ensures
    that concurrent calls for the same key return the same instance
    (Python's GIL protects the cache dict).  Note that the
    ``Environment`` object itself is **not** thread-safe — this is
    acceptable because Sphinx builds are single-threaded.

    The cache persists for the lifetime of the process (e.g. across
    rebuilds in ``sphinx-autobuild``).  This is fine because the
    environments are stateless (no per-build data).

    :param autoescape: Whether to enable autoescaping.
    :param variable_start_string: Delimiter that opens a variable expression.
    :param variable_end_string: Delimiter that closes a variable expression.
    :return: A cached Environment instance.
    """
    return _new_env(autoescape, variable_start_string, variable_end_string)


def render_template_string(
    template_string: str,
    context: dict[str, Any],
    *,
    autoescape: bool,
    new_env: bool = False,
    variable_start_string: str = "{{",
    variable_end_string: str = "}}",
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
    :param variable_start_string: Delimiter that opens a variable expression
        (default ``"{{"``).
    :param variable_end_string: Delimiter that closes a variable expression
        (default ``"}}"``).
    :return: The rendered template as a string.
    """
    env = (
        _new_env(autoescape, variable_start_string, variable_end_string)
        if new_env
        else _get_cached_env(autoescape, variable_start_string, variable_end_string)
    )
    try:
        return env.render_str(template_string, **context)
    except TemplateError as err:
        if (hinted := _hinted(err, template_string)) is not None:
            raise hinted from err
        raise


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

    __slots__ = ("_env", "_source")

    _TEMPLATE_NAME = "__compiled__"

    def __init__(self, env: Environment, source: str) -> None:
        self._env = env
        # kept only so a render failure can be matched against the source
        # (see _hinted); rendering itself uses the template compiled into env
        self._source = source

    def render(self, context: dict[str, Any]) -> str:
        """Render the compiled template with the given context.

        :param context: Dictionary containing template variables.
        :return: The rendered template as a string.
        """
        try:
            return self._env.render_template(self._TEMPLATE_NAME, **context)
        except TemplateError as err:
            if (hinted := _hinted(err, self._source)) is not None:
                raise hinted from err
            raise


@lru_cache(maxsize=32)
def compile_template(
    template_string: str,
    *,
    autoescape: bool,
    variable_start_string: str = "{{",
    variable_end_string: str = "}}",
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
    :param variable_start_string: Delimiter that opens a variable expression
        (default ``"{{"``).  Override to compile templates that use a
        different syntax, e.g. ``"[["`` for the inline ``:need:`` role text.
    :param variable_end_string: Delimiter that closes a variable expression
        (default ``"}}"``).
    :return: A compiled template that can be rendered with different contexts.
    """
    env = _new_env(autoescape, variable_start_string, variable_end_string)
    env.add_template(CompiledTemplate._TEMPLATE_NAME, template_string)
    return CompiledTemplate(env, template_string)
