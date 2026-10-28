"""Template directives: contexts and ``var`` (contract §4), declared template directives
(§5), and what both template forms share -- rendering, the breaker and the splice (§7).
``ub-template`` itself is :mod:`._ub_template`.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from importlib import import_module
from pathlib import Path
from typing import Any

from docutils import nodes
from docutils.parsers.rst import Directive
from docutils.statemachine import StringList
from docutils.utils import new_document
from sphinx.application import Sphinx

from . import _engine, _refusal
from ._config import resolved
from ._engine import Failure, Root
from ._log import warn
from ._presets import lookup, need_types

#: Template file suffixes that declare a markup (§5.1.2).
MARKUP_SUFFIXES = {
    ".rst.j2": "rst",
    ".rst.jinja": "rst",
    ".md.j2": "md",
    ".md.jinja": "md",
}
#: The per-page breaker's key in ``env.temp_data`` (§7.6), and its limit.
BREAKER = "ub_directives_breaker"
BREAKER_LIMIT = 3
#: The limit codes the breaker counts.
LIMIT_CODES = frozenset({"template_output_limit", "template_compute_limit"})


#: The application of the build in progress (set at ``builder-inited``): directives reach
#: it here rather than through the deprecated ``env.app``.
APP: list[Sphinx] = []


def app_of() -> Sphinx:
    return APP[-1]


def observe(text: str) -> None:
    """Called with the text of every use whose output joins the page, in document order:
    the conformance runner's seam. Does nothing in a build."""


def file_markup(name: str) -> str | None:
    """The markup a template file's name declares, if any."""
    lower = name.lower()
    return next(
        (m for suffix, m in MARKUP_SUFFIXES.items() if lower.endswith(suffix)), None
    )


# --- contexts and var -----------------------------------------------------------------


def note(env: Any, path: Path) -> None:
    """Note ``path`` as a dependency of the current page (§7.11)."""
    with _refusal.own():
        env.note_dependency(str(path))


def context_value(env: Any, root: Root, name: str, spec: Any) -> Any:
    """One context's data (§4.1-§4.3), read and checked.

    :raises ValueError: Saying why the context cannot be used.
    """
    if not isinstance(spec, Mapping):
        msg = f"the context {name!r} is not a table"
        raise ValueError(msg)
    if set(spec) == {"file"} and isinstance(spec["file"], str):
        relative = spec["file"]
        path = root.resolve(relative)
        if path is None:
            note(env, root.path / relative.lstrip("/"))
            msg = f"its file {relative} is outside the source root"
            raise ValueError(msg)
        note(env, path)
        try:
            text = root.read(path)
        except (OSError, UnicodeDecodeError) as error:
            msg = f"its file {relative} cannot be read ({error})"
            raise ValueError(msg) from error
        return _engine.parse_data(text, "".join(Path(relative).suffixes[-1:]), relative)
    _engine.check_data(spec, name)
    return spec


def variants(app: Sphinx) -> Mapping[str, Any]:
    """``var`` (§4.6): what ``.. if::`` evaluates against when sphinx-needs is loaded,
    else ub-project's read of the file."""
    if "sphinx_needs" in app.extensions:
        data = getattr(app.config, "needs_variant_data", None)
        return data if isinstance(data, Mapping) else {}
    data = resolved(app)["variants"]
    return data if isinstance(data, Mapping) else {}


# --- the shared tail: render, breaker, splice -----------------------------------------


def host_markup(directive: Directive) -> str:
    """The markup of the page a directive is in."""
    return "md" if getattr(directive.state, "_renderer", None) is not None else "rst"


def expand(
    directive: Directive,
    *,
    use: str,
    identity: str,
    source: str,
    name: str,
    context: Mapping[str, Any],
    root: Root,
    markup: str,
    raw: str | None = None,
    debug: bool = False,
) -> list[nodes.Node]:
    """Render and splice one use; report what fails (§7)."""
    env = directive.state.document.settings.env
    location = (env.docname, directive.lineno)
    breaker: dict[str, dict[str, Any]] = env.temp_data.setdefault(BREAKER, {})
    entry = breaker.setdefault(identity, {"failed": set(), "first": None})
    key = _engine.input_key(identity, source, context)
    if len(entry["failed"]) >= BREAKER_LIMIT and key not in entry["failed"]:
        warn(
            "template_disabled",
            use,
            f"the template {name} is not rendered here: it already hit a limit with "
            f"{BREAKER_LIMIT} different inputs in this page (first at line {entry['first']})",
            location=location,
        )
        return []
    try:
        rendered = _engine.render(source, name, context, root)
    except Failure as failure:
        if failure.code in LIMIT_CODES:
            entry["failed"].add(key)
            entry["first"] = entry["first"] or directive.lineno
        warn(failure.code, use, failure.message, location=location)
        return []
    finally:
        for path in root.reads:
            note(env, path)
    text = rendered.text
    if raw is not None:
        observe(text)
        return [nodes.raw("", text, format=raw)]
    return splice(directive, use=use, text=text, markup=markup, debug=debug)


def splice(
    directive: Directive, *, use: str, text: str, markup: str, debug: bool
) -> list[nodes.Node]:
    """Join the output to the page (§7.8-§7.10)."""
    env = directive.state.document.settings.env
    location = (env.docname, directive.lineno)
    host = host_markup(directive)
    debug_nodes: list[nodes.Node] = [nodes.literal_block(text, text)] if debug else []
    if markup == host == "rst":
        found_source, found_line = directive.state_machine.get_source_and_line(
            directive.lineno
        )
        source = str(found_source)
        line = int(found_line or directive.lineno)
        lines = text.splitlines()
        if debug:
            lines += [
                "",
                "::",
                "",
                *(f"   {x}" if x else "" for x in text.splitlines()),
                "",
            ]
        env.temp_data.setdefault(_refusal.LINES, {})[(source, line)] = use
        observe(text)
        directive.state_machine.insert_input(
            StringList(lines, items=[(source, line - 1)] * len(lines)), source
        )
        return []
    if markup == host == "md":
        observe(text)
        renderer: Any = getattr(directive.state, "_renderer")  # noqa: B009
        with _refusal.parsing(use):
            renderer.nested_render_text(text, directive.lineno)
        return debug_nodes
    # the other markup: parsed on its own, and allowed without headings (§7.9). A first,
    # inert parse looks for a heading, so a refused output makes no need and reads nothing
    with _refusal.inert():
        structure = _parse_other(directive, text, markup, use)
    if structure is None:
        return []
    if any(True for _ in structure.findall(nodes.section)):
        warn(
            "template_markup_heading",
            use,
            f"the template writes {'MyST Markdown' if markup == 'md' else 'reStructuredText'}, "
            "and this page is the other markup: its output may not hold a heading, so it "
            "renders nothing here",
            location=location,
        )
        return []
    fragment = _parse_other(directive, text, markup, use)
    if fragment is None:
        return []
    observe(text)
    document = directive.state.document
    for attribute in ("ids", "nameids", "nametypes"):
        for name, value in getattr(fragment, attribute).items():
            getattr(document, attribute).setdefault(name, value)
    return [*fragment.children, *debug_nodes]


def _parse_other(
    directive: Directive, text: str, markup: str, use: str
) -> nodes.document | None:
    """``text`` parsed in ``markup`` into a document of its own, or ``None`` (reported)
    when this project cannot parse that markup."""
    document = directive.state.document
    env = document.settings.env
    fragment = new_document(document["source"], document.settings)
    if markup == "md":
        if "myst_parser" not in app_of().extensions:
            warn(
                "template_markup_unsupported",
                use,
                "the template writes MyST Markdown, and this project does not load "
                "myst_parser",
                location=(env.docname, directive.lineno),
            )
            return None
        # imported by name: myst-parser is optional, and absent from the type-check floor
        parser: Any = import_module("myst_parser.parsers.sphinx_").MystParser()
    else:
        from sphinx.parsers import RSTParser

        parser = RSTParser()
        parser.set_application(app_of())
    with _refusal.parsing(use):
        parser.parse(text, fragment)
    return fragment


# --- declared template directives -----------------------------------------------------


def declaration_problem(
    app: Sphinx, name: str, spec: Any, names: list[str]
) -> str | None:
    """Why a declaration cannot be used (§5.1), or ``None``."""
    lower = name.lower()
    if not isinstance(spec, Mapping):
        return f"the template directive {name!r} is not a table"
    if any(t.lower() == lower for t in need_types(app)):
        return f"{name!r} is already a need type"
    if lookup(app, lower) is not None:
        return f"{name!r} is already a directive ({lower!r}); a template directive cannot redefine it"
    first = next(n for n in names if n.lower() == lower)
    if first != name:
        return (
            f"{name!r} differs only in case from {first!r}, and directive names do not"
        )
    has_template, has_body = "template" in spec, "body" in spec
    if has_template == has_body:
        return f"the template directive {name!r} gives {'both' if has_template else 'neither'} of template and body"
    template, body = spec.get("template"), spec.get("body")
    if (has_template and not isinstance(template, str)) or (
        has_body and not isinstance(body, str)
    ):
        return f"the template directive {name!r}: template and body must be strings"
    markup = spec.get("markup")
    if markup is not None and markup not in ("rst", "md"):
        return (
            f'the template directive {name!r}: markup {markup!r} is not "rst" or "md"'
        )
    from_file = file_markup(template) if isinstance(template, str) else None
    if markup is not None and from_file is not None and markup != from_file:
        return f"the template directive {name!r}: markup is {markup!r} but its template file is {from_file}"
    return None


class _RawOptions(dict[str, Callable[[str | None], Any]]):
    """Every option, as its raw text: the signature is checked in ``run()`` (§5.3)."""

    def __bool__(self) -> bool:
        return True

    def __getitem__(self, key: str) -> Callable[[str | None], Any]:
        return lambda text: text if text is not None else ""

    def __contains__(self, key: object) -> bool:
        return True


def declared_class(app: Sphinx, name: str, spec: Mapping[str, Any]) -> type[Directive]:
    """The directive a declaration is registered as."""
    use = name.lower()
    options_spec: Mapping[str, Any] = spec.get("options") or {}
    argument_spec = spec.get("argument")
    content = bool(spec.get("content", False))
    template = spec.get("template")
    markup = (
        spec.get("markup")
        or (file_markup(template) if isinstance(template, str) else None)
        or "rst"
    )

    def signature(self: Directive) -> list[str]:
        breaches = []
        for option in sorted(self.options):
            if option not in options_spec:
                declared = ", ".join(map(repr, options_spec)) or "none"
                breaches.append(f"has no option {option!r} (it declares {declared})")
        for option, option_spec in options_spec.items():
            given = self.options.get(option)
            option_spec = option_spec if isinstance(option_spec, Mapping) else {}
            if option_spec.get("flag"):
                if given:
                    breaches.append(f"the flag {option!r} takes no value")
                continue
            value = given if given is not None else option_spec.get("default")
            choices = option_spec.get("choices")
            if value is not None and choices is not None and value not in choices:
                breaches.append(
                    f"the option {option!r} is {value!r}; it may be one of {choices}"
                )
            if value is None and option_spec.get("required"):
                breaches.append(f"needs the option {option!r}")
        if argument_spec is None and self.arguments:
            breaches.append("takes no argument")
        if (
            isinstance(argument_spec, Mapping)
            and argument_spec.get("required")
            and not self.arguments
        ):
            breaches.append("needs an argument")
        if not content and self.content:
            breaches.append("takes no body")
        return breaches

    def run(self: Directive) -> list[nodes.Node]:
        env = self.state.document.settings.env
        location = (env.docname, self.lineno)
        breaches = signature(self)
        if breaches:
            for breach in breaches:
                warn(
                    "template_signature",
                    use,
                    f"the template directive {use!r} {breach}",
                    location=location,
                )
            return []
        root = Root(Path(env.srcdir))
        reading = resolved(app)
        contexts: dict[str, Any] = {}
        for context_name, context_spec in reading["template_contexts"].items():
            if context_name == "var":
                continue
            try:
                contexts[context_name] = context_value(
                    env, root, context_name, context_spec
                )
            except ValueError as error:
                warn(
                    "template_context_invalid",
                    use,
                    f"the context {context_name!r} cannot be used: {error}",
                    location=location,
                )
                return []
        options: dict[str, Any] = {}
        for option, option_spec in options_spec.items():
            option_spec = option_spec if isinstance(option_spec, Mapping) else {}
            if option_spec.get("flag"):
                options[option] = option in self.options
            else:
                options[option] = self.options.get(option, option_spec.get("default"))
        context: dict[str, Any] = {
            "argument": self.arguments[0] if self.arguments else None,
            "options": options,
        }
        if content:
            context["body"] = "\n".join(self.content)
        context["contexts"] = contexts
        context["var"] = variants(app)
        if isinstance(template, str):
            path = root.resolve(template)
            if path is None:
                note(env, root.path / template.lstrip("/"))
                warn(
                    "template_outside_root",
                    use,
                    f"the template {template} of {use!r} is outside the source root; it is not read",
                    location=location,
                )
                return []
            note(env, path)
            try:
                source = root.read(path)
            except (OSError, UnicodeDecodeError) as error:
                warn(
                    "template_missing",
                    use,
                    f"the template {template} of {use!r} cannot be read: {error}",
                    location=location,
                )
                return []
            template_name = template
        else:
            source = str(spec.get("body"))
            template_name = f"[parse.directive_templates.{name}]"
        return expand(
            self,
            use=use,
            identity=f"declared:{use}",
            source=source,
            name=template_name,
            context=context,
            root=root,
            markup=markup,
        )

    attrs: dict[str, Any] = {
        "required_arguments": 0,
        "optional_arguments": 1,
        "final_argument_whitespace": True,
        "has_content": True,
        "option_spec": _RawOptions(),
        "run": run,
        _refusal.TEMPLATE_MARKER: True,
    }
    cls = type(f"Declared_{use.replace('-', '_')}", (Directive,), attrs)
    assert issubclass(cls, Directive)
    return cls


def register(app: Sphinx) -> None:
    """``builder-inited``: report the context and declaration findings once (§4.7, §5.1),
    and register every usable declaration."""
    APP[:] = [app]
    reading = resolved(app)
    location = reading["file"]
    if "var" in reading["template_contexts"]:
        warn(
            "template_context_reserved",
            "parse.template_contexts.var",
            "a context cannot be named var: var is the project's variant data in every "
            "template; this context is not read",
            location=location,
        )
    declarations = reading["directive_templates"]
    names = sorted(declarations)
    accepted = []
    for name in names:
        problem = declaration_problem(app, name, declarations[name], names)
        if problem is not None:
            from ub_project.project import render_path

            warn(
                "directive_template_invalid",
                render_path(("parse", "directive_templates", name)),
                f"{problem}; it is ignored",
                location=location,
            )
            continue
        accepted.append(name)
    for name in accepted:
        app.add_directive(name.lower(), declared_class(app, name, declarations[name]))
