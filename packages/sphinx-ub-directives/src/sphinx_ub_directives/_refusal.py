"""Depth 1, and only declared inputs (contract §7.10).

Refusal happens during the REAL parse of a template's output, keyed on the inserted
lines: every line a template inserts carries the directive's own ``(source, line)``, and
nested bodies inherit it, so a directive lookup is on output exactly when the document's
current position is one a template inserted (or while output of the other markup is
parsed, which happens synchronously). A refused directive renders nothing and is
reported; the rest of the output renders.

One wrapper of ``docutils.parsers.rst.directives.directive`` is installed per process; it
is inert outside template output.
"""

from __future__ import annotations

import contextlib
from collections.abc import Callable, Iterable, Iterator
from contextvars import ContextVar
from typing import Any

from docutils import nodes
from docutils.parsers.rst import Directive, directives
from sphinx.environment import BuildEnvironment

from ._log import warn

#: ``env.temp_data`` key: ``{(source, line): use}`` for the lines a template inserted.
LINES = "ub_directives_lines"
#: The use whose output is being parsed synchronously (cross-markup, MyST).
ACTIVE: ContextVar[str | None] = ContextVar("ub_directives_active", default=None)
#: Set while output is parsed only to see its structure: every directive is inert.
INERT: ContextVar[bool] = ContextVar("ub_directives_inert", default=False)
#: Set while this package notes its own dependencies.
OWN: ContextVar[bool] = ContextVar("ub_directives_own", default=False)

#: The directives that always read outside content.
ALWAYS = frozenset(
    {
        "autoattribute",
        "autoclass",
        "autodata",
        "autodecorator",
        "autoexception",
        "autofunction",
        "automethod",
        "automodule",
        "autoproperty",
        "include",
        "literalinclude",
        "needimport",
        "needservice",
        "src-trace",
    }
)
#: sphinx-test-reports' directives (they read a report file).
TEST_REPORTS = frozenset(
    {"test-file", "test-suite", "test-case", "test-report", "test-results", "test-env"}
)
#: The directives that read outside content with one of these options.
WITH_OPTION = {
    "csv-table": ("file", "url"),
    "raw": ("file", "url"),
    "needreport": ("template",),
}
#: The directives that read a file when given an argument.
WITH_ARGUMENT = frozenset({"graphviz", "mermaid", "plantuml", "uml"})
#: A need directive's options that read a template.
NEED_TEMPLATE_OPTIONS = ("template", "pre_template", "post_template", "jinja_content")

#: What a preset's class carries (set by ``_presets``): its base's name, the option keys
#: it merges in (defaults and forced), and whether it supplies a default argument.
PRESET_BASE = "ub_directives_base"
PRESET_KEYS = "ub_directives_preset_keys"
PRESET_ARGUMENT = "ub_directives_preset_argument"

#: The marker a template directive's class carries.
TEMPLATE_MARKER = "ub_directives_template"


def active_use(document: Any) -> str | None:
    """The template use whose output ``document`` is parsing right now, if any."""
    use = ACTIVE.get()
    if use is not None:
        return use
    env = getattr(getattr(document, "settings", None), "env", None)
    if env is None:
        return None
    lines = env.temp_data.get(LINES)
    if not lines:
        return None
    key = (
        getattr(document, "current_source", None),
        getattr(document, "current_line", None),
    )
    use = lines.get(key)
    return use if isinstance(use, str) else None


@contextlib.contextmanager
def parsing(use: str) -> Iterator[None]:
    """Mark output of ``use`` as being parsed synchronously."""
    token = ACTIVE.set(use)
    try:
        yield
    finally:
        ACTIVE.reset(token)


@contextlib.contextmanager
def inert() -> Iterator[None]:
    """Make every directive inert: parsed, never run, so a structural look at output
    (does it hold a heading?) has no side effect -- no need is made, no file is read."""
    token = INERT.set(True)
    try:
        yield
    finally:
        INERT.reset(token)


@contextlib.contextmanager
def own() -> Iterator[None]:
    """Mark this package's own dependency notes (the backstop ignores them)."""
    token = OWN.set(True)
    try:
        yield
    finally:
        OWN.reset(token)


class _AnyOptions(dict[str, Callable[[str | None], Any]]):
    """An option spec accepting every option, as raw text."""

    def __bool__(self) -> bool:
        return True

    def __getitem__(self, key: str) -> Callable[[str | None], Any]:
        return lambda text: text

    def __contains__(self, key: object) -> bool:
        return True


class _Inert(Directive):
    optional_arguments = 99
    final_argument_whitespace = True
    has_content = True
    option_spec = _AnyOptions()

    def run(self) -> list[nodes.Node]:
        # one inline placeholder: a substitution definition (whose directive this may be)
        # needs some content to be one, and the structural look must see it (§7.9)
        return [nodes.inline("", "inert")]


#: Directives whose body is not markup: the structural pass never reads their body as a
#: page would (title-like text in a code-block is no title, §7.8).
LITERAL_BODIES = frozenset(
    {
        "code-block",
        "code",
        "sourcecode",
        "code-cell",
        "literalinclude",
        "highlight",
        "math",
        "raw",
        "csv-table",
        "parsed-literal",
        "graphviz",
        "digraph",
        "graph",
        "mermaid",
        "plantuml",
        "uml",
        "needuml",
        "needarch",
        "doctest",
        "testcode",
        "testoutput",
        "productionlist",
        "ub-template",
        "jinja",
        "eval-rst",
    }
)


def _known_markup(name: str, cls: type[Directive] | None, language_module: Any) -> bool:
    """Whether the structural pass reads a directive's body as markup: a directive some
    loaded extension registers, that is no template directive and has no literal body."""
    if cls is None or getattr(cls, TEMPLATE_MARKER, False):
        return False
    lower, _merged, _argument = canonical(name, cls, language_module)
    return lower not in LITERAL_BODIES


def parses_body(name: str, app: Any) -> bool:
    """:func:`_known_markup` for a MyST fence name, looked up the way Sphinx would."""
    from ._presets import lookup

    found = lookup(app, name)
    return found is not None and _known_markup(name, found[0], None)


class _InertParsing(Directive):
    """An inert directive that reads its body as markup, so the structural pass finds a
    section title inside a ``note`` (or any container) the output writes (§7.8)."""

    optional_arguments = 99
    final_argument_whitespace = True
    has_content = True
    option_spec = _AnyOptions()

    def run(self) -> list[nodes.Node]:
        if type(self.state).__name__ == "SubstitutionDef":
            # a substitution definition takes inline content only (§7.9 must still see it)
            return [nodes.inline("", "inert")]
        holder = nodes.container()
        self.state.nested_parse(
            self.content, self.content_offset, holder, match_titles=True
        )
        return [holder]


def _refuser(name: str, use: str, code: str, why: str) -> type[Directive]:
    class Refused(Directive):
        optional_arguments = 99
        final_argument_whitespace = True
        has_content = True
        option_spec = _AnyOptions()

        def run(self) -> list[nodes.Node]:
            env = self.state.document.settings.env
            warn(code, use, why.format(name=name), location=(env.docname, self.lineno))
            return []

    return Refused


def _conditional(
    real: type[Directive] | None,
    name: str,
    use: str,
    refused: Callable[[Directive], bool],
) -> type[Directive]:
    """``real``, refused when ``refused(self)``; a directive no extension provides is
    the unknown directive it would have been."""
    base = real if real is not None else Directive
    attrs: dict[str, Any] = {}
    if real is None:
        attrs.update(
            optional_arguments=99,
            final_argument_whitespace=True,
            has_content=True,
            option_spec=_AnyOptions(),
        )

    def run(self: Directive) -> list[nodes.Node]:
        if refused(self):
            env = self.state.document.settings.env
            warn(
                "template_output_reads_file",
                use,
                f"the rendered text holds a {name!r} directive that reads a file; a "
                "template's output reads only what the template declares",
                location=(env.docname, self.lineno),
            )
            return []
        if real is None:
            error = self.state_machine.reporter.error(
                f'Unknown directive type "{name}".', line=self.lineno
            )
            return [error]
        return list(real.run(self))

    attrs["run"] = run
    cls = type(f"Conditional_{name}", (base,), attrs)
    assert issubclass(cls, Directive)
    return cls


def _is_need_directive(cls: type[Directive] | None) -> bool:
    if cls is None:
        return False
    try:
        from sphinx_needs.directives.need import NeedDirective
    except ImportError:
        return False
    return issubclass(cls, NeedDirective)


def test_report_names(env: Any) -> frozenset[str]:
    """The sphinx-test-reports directives of this project (§7.10): with the extension
    loaded, the names it is configured to register; else its defaults."""
    config = getattr(env, "config", None)
    configured: set[str] = set()
    for confval in ("tr_file", "tr_suite", "tr_case"):
        value = getattr(config, confval, None) if config is not None else None
        first = value[0] if isinstance(value, list | tuple) and value else None
        if isinstance(first, str):
            configured.add(first.lower())
    if not configured:
        return TEST_REPORTS
    return frozenset({"test-report", "test-results", "test-env", *configured})


def canonical(
    name: str, cls: type[Directive] | None, language_module: Any
) -> tuple[str, frozenset[str], bool]:
    """The name a lookup of ``name`` is judged by, the option keys a preset merges in, and
    whether it supplies an argument (§7.10): a preset is judged as its BASE written with its
    merged options; a localized docutils name as the directive it translates."""
    lower = name.lower()
    base = getattr(cls, PRESET_BASE, None) if cls is not None else None
    if isinstance(base, str):
        keys = getattr(cls, PRESET_KEYS, None)
        merged: frozenset[str] = frozenset(
            str(k) for k in (keys if isinstance(keys, frozenset) else ())
        )
        return str(base).lower(), merged, getattr(cls, PRESET_ARGUMENT, False) is True
    table = getattr(language_module, "directives", None)
    translated = table.get(lower) if isinstance(table, dict) else None
    if isinstance(translated, str):
        lower = translated
    return lower, frozenset(str(k) for k in ()), False


def _refusal(
    name: str,
    cls: type[Directive] | None,
    use: str,
    language_module: Any = None,
    env: Any = None,
) -> type[Directive] | None:
    """The class a lookup of ``name`` on output of ``use`` resolves to, or ``None`` when
    the directive is allowed."""
    if cls is not None and getattr(cls, TEMPLATE_MARKER, False):
        return _refuser(
            name.lower(),
            use,
            "template_nested_expansion",
            "the rendered text holds a {name!r} directive; a template's output is not "
            "expanded again",
        )
    lower, merged, argument = canonical(name, cls, language_module)
    shown = name.lower()
    if lower in ALWAYS or lower in test_report_names(env):
        return _refuser(
            shown,
            use,
            "template_output_reads_file",
            "the rendered text holds a {name!r} directive that reads a file; a "
            "template's output reads only what the template declares",
        )

    def has(d: Directive, keys: Iterable[str]) -> bool:
        return any(k in d.options or k in merged for k in keys)

    if lower in WITH_OPTION:
        keys = WITH_OPTION[lower]
        return _conditional(cls, shown, use, lambda d: has(d, keys))
    if lower in WITH_ARGUMENT:
        return _conditional(
            cls,
            shown,
            use,
            lambda d: argument or bool(d.arguments and d.arguments[0].strip()),
        )
    if _is_need_directive(cls):
        return _conditional(cls, shown, use, lambda d: has(d, NEED_TEMPLATE_OPTIONS))
    return None


def _scoped(cls: type[Directive], use: str) -> type[Directive]:
    """``cls``, run with ``use`` marked active: a directive of the output runs after the
    output's lines are read (the state machine has read ahead into docutils' padding by
    then), so the dependency backstop learns the use from the run, not the position."""

    def run(self: Directive) -> Any:
        with parsing(use):
            return cls.run(self)

    scoped = type(cls.__name__, (cls,), {"run": run})
    assert issubclass(scoped, Directive)
    return scoped


def install() -> None:
    """Wrap the directive lookup (once per process) and the dependency note."""
    original = directives.directive
    if getattr(original, TEMPLATE_MARKER, False):
        return

    def directive(
        name: str, language_module: Any, document: Any
    ) -> tuple[Any, list[Any]]:
        if INERT.get():
            cls, _messages = original(name, language_module, document)
            return (
                _InertParsing if _known_markup(name, cls, language_module) else _Inert
            ), []
        cls, messages = original(name, language_module, document)
        use = active_use(document)
        if use is None:
            return cls, messages
        env = getattr(getattr(document, "settings", None), "env", None)
        refused = _refusal(name, cls, use, language_module, env)
        if refused is None:
            return (_scoped(cls, use) if cls is not None else None), messages
        return refused, []

    setattr(directive, TEMPLATE_MARKER, True)
    setattr(directives, "directive", directive)  # noqa: B010 - the stubs type it narrowly

    note = BuildEnvironment.note_dependency

    def note_dependency(
        self: BuildEnvironment, filename: Any, *args: Any, **kwargs: Any
    ) -> None:
        note(self, filename, *args, **kwargs)
        if OWN.get():
            return
        use = ACTIVE.get()
        if use is not None:
            warn(
                "template_reads_dependency",
                use,
                f"a directive in the rendered text read {filename}, which the template "
                "did not declare; this is the project's responsibility (only a Sphinx "
                "build runs such a directive)",
                location=self.docname,
            )

    BuildEnvironment.note_dependency = note_dependency  # type: ignore[method-assign]
