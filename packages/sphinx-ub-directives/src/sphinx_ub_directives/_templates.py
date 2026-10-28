"""Template directives: contexts and ``var`` (contract §4), declared template directives
(§5), and what both template forms share -- rendering, the breaker and the splice (§7).
``ub-template`` itself is :mod:`._ub_template`.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Callable, Mapping
from importlib import import_module
from pathlib import Path
from typing import Any

from docutils import nodes
from docutils.parsers.rst import Directive
from docutils.parsers.rst import Parser as RstParser
from docutils.statemachine import StringList
from docutils.utils import Reporter, new_document
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


#: Parsed context files, keyed by path and CONTENT digest (L9, fix round 2): every
#: declared use reads every context, and data is plain and never changed once read, so one
#: parse per file content is shared by the uses of a process. The file is still read each
#: time (a size- and mtime-keyed memo served stale data after a same-size edit).
_FILE_DATA: dict[tuple[str, str], dict[str, Any]] = {}


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
        key = (str(path), hashlib.sha256(text.encode("utf-8")).hexdigest())
        if key not in _FILE_DATA:
            _FILE_DATA[key] = _engine.read_data(
                text, "".join(Path(relative).suffixes[-1:]), relative
            )
        return _FILE_DATA[key]
    try:
        _engine.check_data(spec, name)
    except RecursionError as error:
        msg = f"{name} is nested deeper than {_engine.MAX_DEPTH} levels"
        raise ValueError(msg) from error
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
    if has_heading(directive, text, markup):
        warn(
            "template_heading",
            use,
            "the output holds a section title, which template output may not hold "
            "(headings in template output are not supported in this version); it renders "
            "nothing. Write a rubric instead, or put the heading in the page",
            location=location,
        )
        return []
    if markup == "md" and _md_front_matter(directive, text):
        warn(
            "template_markup_construct",
            use,
            "the output starts with front matter, which belongs to a whole document; it "
            "renders nothing",
            location=location,
        )
        return []
    if markup != host:
        return _splice_other(directive, use=use, text=text, markup=markup, debug=debug)
    debug_nodes: list[nodes.Node] = [nodes.literal_block(text, text)] if debug else []
    if host == "rst":
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
    observe(text)
    renderer: Any = getattr(directive.state, "_renderer")  # noqa: B009
    with _refusal.parsing(use):
        renderer.nested_render_text(text, directive.lineno)
    return debug_nodes


# --- no section title in output (§7.8) -------------------------------------------------


def _silent(document: nodes.document) -> None:
    """Give a throwaway document a reporter that discards (§7.9: the inert parse)."""
    document.reporter = Reporter(document["source"], 5, 5, stream=False)


def has_heading(directive: Directive, text: str, markup: str) -> bool:
    """Whether ``text`` (in ``markup``) holds a section title anywhere (§7.8), found by an
    inert parse: no directive runs, nothing is read, nothing is registered."""
    if markup == "rst":
        return _rst_has_heading(directive, text)
    return _md_has_heading(directive, text)


def _rst_has_heading(directive: Directive, text: str) -> bool:
    """Whether reStructuredText ``text`` holds a section title anywhere: an inert parse in
    which every nested body may hold titles (so a title in a block quote or a note is a
    ``section`` node, not an error), judged by structure alone -- a transition is no title."""
    document = directive.state.document
    fragment = new_document(document["source"], document.settings)
    _silent(fragment)
    with _refusal.inert():
        RstParser().parse(text, fragment)
    return any(True for _ in fragment.findall(nodes.section))


_OPTION_LINE = re.compile(r"^:[\w-]+:")


def _fence_body(content: str) -> str:
    """A MyST directive fence's body, without its leading options (`:key: value` lines,
    or a `---`-fenced YAML block)."""
    lines = content.splitlines()
    if lines and lines[0].strip() == "---":
        closing = next(
            (i for i in range(1, len(lines)) if lines[i].strip() == "---"), None
        )
        if closing is not None:
            lines = lines[closing + 1 :]
    while lines and _OPTION_LINE.match(lines[0]):
        lines = lines[1:]
    return "\n".join(lines)


def _md_has_heading(directive: Directive, text: str) -> bool:
    md = _md_parser(directive)
    if md is None:
        return False  # this project cannot parse Markdown; the real parse says so
    return _md_tokens_have_heading(directive, md, text)


def _md_front_matter(directive: Directive, text: str) -> bool:
    """Whether Markdown ``text`` starts with front matter (§7.9)."""
    md = _md_parser(directive)
    if md is None:
        return False
    tokens = md.parse(text + "\n", {})
    return bool(tokens) and str(tokens[0].type) == "front_matter"


def _md_tokens_have_heading(directive: Directive, md: Any, text: str) -> bool:
    for token in md.parse(text + "\n", {}):
        if token.type == "heading_open":
            return True
        info = (
            (token.info or "").strip() if token.type in ("fence", "colon_fence") else ""
        )
        if not info.startswith("{") or "}" not in info:
            continue
        name = info[1:].split("}", 1)[0].strip().lower()
        body = _fence_body(token.content)
        if name == "eval-rst":
            if _rst_has_heading(directive, body):
                return True
        elif _refusal.parses_body(name, app_of()) and _md_tokens_have_heading(
            directive, md, body
        ):
            return True
    return False


def _md_parser(directive: Directive) -> Any:
    """A markdown-it parser configured as the project's MyST, or ``None`` without
    myst-parser."""
    renderer: Any = getattr(directive.state, "_renderer", None)
    if renderer is not None:
        return renderer.md
    app = app_of()
    if "myst_parser" not in app.extensions:
        return None
    mdit = import_module("myst_parser.parsers.mdit")
    sphinx_renderer = import_module(
        "myst_parser.mdit_to_docutils.sphinx_"
    ).SphinxRenderer
    config = getattr(app.env, "myst_config")  # noqa: B009 - myst-parser sets it
    return mdit.create_md_parser(config, sphinx_renderer)


# --- the other markup (§7.9) ----------------------------------------------------------


def _construct(fragment: nodes.document) -> str | None:
    """A construct that registers in the whole document, if output of the other markup
    holds one (§7.9)."""
    if any(True for _ in fragment.findall(nodes.substitution_definition)):
        return "a substitution definition"
    if any(True for _ in fragment.findall(nodes.citation)):
        return "a citation"
    if any(True for _ in fragment.findall(nodes.footnote)):
        return "a footnote"
    return None


def _splice_other(
    directive: Directive, *, use: str, text: str, markup: str, debug: bool
) -> list[nodes.Node]:
    env = directive.state.document.settings.env
    location = (env.docname, directive.lineno)
    written = "MyST Markdown" if markup == "md" else "reStructuredText"
    # a first, inert parse looks at the structure, so a refused output makes no need
    with _refusal.inert():
        structure = _parse_other(directive, text, markup, use, silent=True)
    if structure is None:
        return []
    construct = _construct(structure)
    if construct is not None:
        warn(
            "template_markup_construct",
            use,
            f"the template writes {written}, and this page is the other markup: its output "
            f"may not hold {construct}, which belongs to a whole document; it renders nothing",
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
    debug_nodes: list[nodes.Node] = [nodes.literal_block(text, text)] if debug else []
    return [*fragment.children, *debug_nodes]


def _parse_other(
    directive: Directive, text: str, markup: str, use: str, *, silent: bool = False
) -> nodes.document | None:
    """``text`` parsed in ``markup`` into a document of its own, or ``None`` (reported)
    when this project cannot parse that markup. reStructuredText is parsed undecorated:
    no ``rst_prolog`` or ``rst_epilog`` (§7.9)."""
    document = directive.state.document
    env = document.settings.env
    fragment = new_document(document["source"], document.settings)
    if silent:
        _silent(fragment)
    parser: Any
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
        parser = import_module("myst_parser.parsers.sphinx_").MystParser()
    else:
        parser = RstParser()
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
    shape = _shape_problem(spec)
    if shape is not None:
        return f"the template directive {name!r}: {shape}"
    return None


#: The keys of a declaration, of its argument, and of one of its options (§5.1).
DECLARATION_KEYS = frozenset(
    {"template", "body", "markup", "description", "argument", "content", "options"}
)
ARGUMENT_KEYS = frozenset({"required", "description"})
OPTION_KEYS = frozenset({"required", "default", "choices", "flag", "description"})


def _shape_problem(spec: Mapping[str, Any]) -> str | None:
    """The first field of a declaration that has the wrong shape (§5.1), if any."""
    for key in ("markup", "description"):
        if key in spec and not isinstance(spec[key], str):
            return f"{key} must be a string"
    if "content" in spec and not isinstance(spec["content"], bool):
        return "content must be true or false"
    argument = spec.get("argument")
    if argument is not None:
        if not isinstance(argument, Mapping):
            return "argument must be a table"
        if "required" in argument and not isinstance(argument["required"], bool):
            return "argument.required must be true or false"
        if "description" in argument and not isinstance(argument["description"], str):
            return "argument.description must be a string"
    options = spec.get("options", {})
    if not isinstance(options, Mapping):
        return "options must be a table"
    for option, option_spec in options.items():
        if not isinstance(option_spec, Mapping):
            return f"the option {option!r} must be a table"
        for key in ("required", "flag"):
            if key in option_spec and not isinstance(option_spec[key], bool):
                return f"the option {option!r}: {key} must be true or false"
        for key in ("default", "description"):
            if key in option_spec and not isinstance(option_spec[key], str):
                return f"the option {option!r}: {key} must be a string"
        choices = option_spec.get("choices")
        if choices is not None and not (
            isinstance(choices, list) and all(isinstance(c, str) for c in choices)
        ):
            return f"the option {option!r}: choices must be an array of strings"
    return None


def unknown_keys(spec: Mapping[str, Any]) -> list[tuple[str, ...]]:
    """The key paths of a (well-shaped) declaration that §5.1 does not define."""
    found: list[tuple[str, ...]] = [
        (key,) for key in spec if key not in DECLARATION_KEYS
    ]
    argument = spec.get("argument")
    if isinstance(argument, Mapping):
        found += [("argument", key) for key in argument if key not in ARGUMENT_KEYS]
    for option, option_spec in (spec.get("options") or {}).items():
        found += [
            ("options", option, key) for key in option_spec if key not in OPTION_KEYS
        ]
    return found


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
        for segments in unknown_keys(declarations[name]):
            from ub_project.project import render_path

            warn(
                "directive_template_unknown_key",
                render_path(("parse", "directive_templates", name, *segments)),
                f"{segments[-1]!r} is not a key of a template directive's declaration "
                "here; it is ignored",
                location=location,
            )
        accepted.append(name)
    for name in accepted:
        app.add_directive(name.lower(), declared_class(app, name, declarations[name]))
