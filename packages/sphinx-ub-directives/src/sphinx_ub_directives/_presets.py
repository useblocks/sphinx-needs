"""Directive presets: ``[parse.directive_presets.<name>]`` (contract §3).

At ``builder-inited`` -- after every extension's ``config-inited``, so need types and
sphinx-design's directives are registered, and before any document is read -- every
entry is checked (§3.1-§3.3), every base class is snapshotted, and each accepted preset
is registered as a subclass of its base (§3.5).
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from decimal import Decimal
from importlib import import_module
from typing import Any, cast

from docutils.parsers.rst import Directive, directives
from sphinx.application import Sphinx

from ub_project.project import render_path

from . import _refusal
from ._config import resolved
from ._log import warn

#: The keys an entry may have.
ENTRY_KEYS = frozenset(
    {"base", "description", "argument", "options", "append_options", "force_options"}
)
#: The option tables, in the order they are checked (§3.3).
VERBS = ("options", "append_options", "force_options")
#: The need directive's own options, besides the type's fields and links.
NEED_META_OPTIONS = frozenset(
    {
        "id",
        "status",
        "tags",
        "collapse",
        "delete",
        "jinja_content",
        "hide",
        "title_from_content",
        "style",
        "layout",
        "template",
        "pre_template",
        "post_template",
        "constraints",
    }
)

Converter = Callable[[Any], Any]


@dataclass
class Base:
    """What a preset is based on."""

    #: The name the base is registered under (the need type, or the directive's name).
    name: str
    #: The class registered under it, snapshotted before any preset is registered.
    cls: type[Directive]
    #: Whether the base is a need type.
    need_type: bool = False
    #: The domain the base was found in, if any (a self-preset is registered there).
    domain: str | None = None


@dataclass
class Preset:
    """One accepted preset."""

    name: str
    base: Base
    self_preset: bool
    argument: str | None
    texts: dict[str, dict[str, str]] = field(default_factory=dict)


def _lookup_docutils(name: str) -> type[Directive] | None:
    """The docutils-registered directive ``name`` (lower case), loading a lazy built-in."""
    registry = cast("dict[str, Any]", getattr(directives, "_directives"))  # noqa: B009
    registered = registry.get(name)
    if registered is not None:
        return cast("type[Directive]", registered)
    lazy_registry = cast(
        "dict[str, tuple[str, str]]",
        getattr(directives, "_directive_registry"),  # noqa: B009
    )
    lazy = lazy_registry.get(name)
    if lazy is None:
        return None
    module_name, class_name = lazy
    try:
        module = import_module(f"docutils.parsers.rst.directives.{module_name}")
    except ImportError:
        return None
    found = getattr(module, class_name, None)
    return cast("type[Directive] | None", found)


def lookup(app: Sphinx, name: str) -> tuple[type[Directive], str | None] | None:
    """The directive ``name`` resolves to in a Sphinx build, and its domain: a qualified
    name in its domain; otherwise the primary domain, then ``std``, then docutils'
    registry -- the order Sphinx's own lookup takes."""
    name = name.lower()
    env = app.env
    if ":" in name:
        domain_name, _, local = name.partition(":")
        try:
            domain = env.get_domain(domain_name)
        except Exception:
            return None
        local_found = domain.directive(local)
        if local_found is None:
            return None
        return cast("type[Directive]", local_found), domain_name
    primary = str(app.config.primary_domain or "")
    for domain_name in dict.fromkeys([primary, "std"]):
        if not domain_name:
            continue
        try:
            domain = env.get_domain(domain_name)
        except Exception:
            continue
        in_domain = domain.directive(name)
        if in_domain is not None:
            return cast("type[Directive]", in_domain), domain_name
    found = _lookup_docutils(name)
    return (found, None) if found is not None else None


def need_types(app: Sphinx) -> list[str]:
    """The need types' directive names, as sphinx-needs registered them (empty when it is
    not loaded)."""
    if "sphinx_needs" not in app.extensions:
        return []
    from sphinx_needs.config import NeedsSphinxConfig

    return [str(t["directive"]) for t in NeedsSphinxConfig(app.config).types]


def need_options(app: Sphinx) -> frozenset[str]:
    """The options a need directive takes: its own, and the configured fields and links."""
    from sphinx_needs.config import NeedsSphinxConfig

    config = NeedsSphinxConfig(app.config)
    names = set(NEED_META_OPTIONS) | {"links"}
    names.update(config.fields)
    for option in config.extra_options:
        names.add(option if isinstance(option, str) else str(option["name"]))
    for link in config.extra_links:
        names.add(str(link["option"]))
    return frozenset(names)


def float_text(value: float) -> str:
    """A float as option text (§3.1.1): the shortest decimal that reads back as the same
    float, with no exponent, and ``.0`` appended when it is integral."""
    text = format(Decimal(repr(value)), "f")
    return text if "." in text else f"{text}.0"


def _text(value: object, converter: Converter | None) -> str | None:
    """A TOML scalar as option text (§3.1.1), or ``None`` when it cannot be one."""
    if isinstance(value, bool):
        if converter is directives.flag:
            return "" if value else None
        return "true" if value else "false"
    if isinstance(value, float):
        return float_text(value)
    if isinstance(value, int):
        return str(value)
    if isinstance(value, str):
        return value
    return None


class Resolver:
    """The once-per-build check of every entry (§3.1-§3.3)."""

    def __init__(self, app: Sphinx, table: Mapping[str, Any], file: str | None) -> None:
        self.app = app
        self.table = table
        self.location = file
        self.types = need_types(app)
        #: the template directives of the project (§3.2.5: none is a preset base)
        self.template_names = {"ub-template"} | {
            str(n).lower() for n in resolved(app)["directive_templates"]
        }
        self._need_options: frozenset[str] | None = None

    def warn(self, code: str, segments: Iterable[str], message: str) -> None:
        warn(code, render_path(tuple(segments)), message, location=self.location)

    def base_of(self, name: str, base: str) -> Base | str:
        """The base an entry names, or why it names none."""
        exact = [t for t in self.types if t == base]
        if exact and exact[0] != exact[0].lower():
            return (
                f"the need type {base!r} is spelled with upper-case letters, which a "
                "Sphinx build cannot use as a directive, so it is no preset base"
            )
        lowered = [t for t in self.types if t == base.lower()]
        if lowered:
            cls = _lookup_docutils(lowered[0])
            if cls is not None:
                return Base(lowered[0], cls, need_type=True)
        if base.lower() in self.template_names:
            return f"{base!r} is a template directive, which is no preset base"
        found = lookup(self.app, base)
        if found is None:
            return f"{base!r} names no directive this project knows"
        cls, domain = found
        if getattr(cls, _refusal.TEMPLATE_MARKER, False):
            return f"{base!r} is a template directive, which is no preset base"
        return Base(base.lower(), cls, domain=domain)

    def taken(self, name: str) -> bool:
        """Whether ``name`` is already a directive of the project."""
        lowered = name.lower()
        return any(t.lower() == lowered for t in self.types) or (
            lookup(self.app, lowered) is not None
        )

    def need_option_names(self) -> frozenset[str]:
        if self._need_options is None:
            self._need_options = need_options(self.app)
        return self._need_options

    def resolve(self) -> list[Preset]:
        """Every accepted preset, each failure reported once at its path."""
        prefix = ("parse", "directive_presets")
        names = sorted(self.table)
        # [A6] names compare case-insensitively: the first spelling in key order is
        # used, and ONE finding is reported at the second
        groups: dict[str, list[str]] = {}
        for name in names:
            groups.setdefault(name.lower(), []).append(name)
        kept = []
        for spellings in groups.values():
            kept.append(spellings[0])
            if len(spellings) > 1:
                self.warn(
                    "directive_preset_name_taken",
                    (*prefix, spellings[1]),
                    f"presets {', '.join(map(repr, spellings))} differ only in case, and "
                    f"directive names do not; {spellings[0]!r} is used",
                )
        entries: dict[str, Mapping[str, Any]] = {}
        for name in kept:
            entry = self.table[name]
            path = (*prefix, name)
            if not isinstance(entry, Mapping):
                self.warn(
                    "directive_preset_invalid_value",
                    path,
                    f"the preset {name!r} is not a table",
                )
                continue
            problems = False
            for key in sorted(entry):
                if key not in ENTRY_KEYS:
                    self.warn(
                        "directive_preset_unknown_key",
                        (*path, key),
                        f"{key!r} is not a preset key (one of "
                        f"{', '.join(sorted(ENTRY_KEYS))}); it is ignored",
                    )
            for key in ("base", "description"):
                if key in entry and not isinstance(entry[key], str):
                    self.warn(
                        "directive_preset_invalid_value",
                        path,
                        f"the preset {name!r}: {key} must be a string",
                    )
                    problems = True
            for verb in VERBS:
                if verb in entry and not isinstance(entry[verb], Mapping):
                    self.warn(
                        "directive_preset_invalid_value",
                        path,
                        f"the preset {name!r}: {verb} must be a table",
                    )
                    problems = True
            if problems:
                continue
            base = entry.get("base")
            if not isinstance(base, str) or not base.strip():
                self.warn(
                    "directive_preset_unknown_base",
                    path,
                    f"the preset {name!r} names no base",
                )
                continue
            entries[name] = entry
        # which names a preset may take: [A5] needs to know the accepted non-self names
        self_names = {
            n for n, e in entries.items() if n.lower() == str(e["base"]).strip().lower()
        }
        free = {n.lower() for n in entries if n not in self_names and not self.taken(n)}
        presets = []
        # [A4] every base is resolved (snapshotted) before anything is registered
        for name, entry in entries.items():
            preset = self.check(name, entry, name in self_names, free)
            if preset is not None:
                presets.append(preset)
        return presets

    def check(
        self,
        name: str,
        entry: Mapping[str, Any],
        self_preset: bool,
        free: set[str],
    ) -> Preset | None:
        path = ("parse", "directive_presets", name)
        base_name = str(entry["base"]).strip()
        if not self_preset and base_name.lower() in free:
            self.warn(
                "directive_preset_base_is_preset",
                (*path, "base"),
                f"the base {base_name!r} is another preset; presets do not chain",
            )
            return None
        base = self.base_of(name, base_name)
        if isinstance(base, str):
            self.warn("directive_preset_unknown_base", (*path, "base"), base)
            return None
        if not self_preset and self.taken(name):
            self.warn(
                "directive_preset_name_taken",
                path,
                f"{name!r} is already a directive of this project; a preset of that "
                f"name would replace it (name it as its base, {name!r}, for defaults)",
            )
            return None
        ok = True
        spec = base.cls.option_spec
        seen: dict[str, str] = {}
        texts: dict[str, dict[str, str]] = {verb: {} for verb in VERBS}
        for verb in VERBS:
            for key in sorted(entry.get(verb, {})):
                value = entry[verb][key]
                where = (*path, verb, key)
                if key in seen:
                    self.warn(
                        "directive_preset_option_conflict",
                        where,
                        f"{key!r} is already in {seen[key]}",
                    )
                    ok = False
                    continue
                seen[key] = verb
                if (base.need_type and key == "id") or (
                    not base.need_type and key == "name" and spec and "name" in spec
                ):
                    self.warn(
                        "directive_preset_identity_option",
                        where,
                        f"{key!r} identifies each use; a preset cannot set it",
                    )
                    ok = False
                    continue
                converter = self.converter(base, key)
                if converter is None:
                    self.warn(
                        "directive_preset_unknown_option",
                        where,
                        f"the base {base.name!r} has no option {key!r}",
                    )
                    ok = False
                    continue
                if verb == "append_options" and not (
                    key == "class" or key.startswith("class-")
                ):
                    self.warn(
                        "directive_preset_append_not_list",
                        where,
                        f"append_options is for class options only, not {key!r}",
                    )
                    ok = False
                    continue
                text = _text(value, converter)
                if text is None:
                    why = (
                        "a flag cannot be switched off by a preset"
                        if value is False
                        else "a value must be a string, boolean or number"
                    )
                    self.warn("directive_preset_invalid_value", where, why)
                    ok = False
                    continue
                if not base.need_type:
                    try:
                        converter(
                            text if converter is directives.flag else text or None
                        )
                    except (ValueError, TypeError, AttributeError) as error:
                        self.warn(
                            "directive_preset_invalid_value",
                            where,
                            f"{text!r} is not a value of {key!r}: {error}",
                        )
                        ok = False
                        continue
                texts[verb][key] = text
        argument = entry.get("argument")
        argument_text: str | None = None
        if argument is not None:
            if isinstance(argument, bool) or not isinstance(
                argument, str | int | float
            ):
                self.warn(
                    "directive_preset_invalid_value",
                    (*path, "argument"),
                    "argument must be a string or a number",
                )
                ok = False
            else:
                argument_text = str(argument).strip() or None
                if argument_text is not None and (
                    base.cls.required_arguments + base.cls.optional_arguments == 0
                ):
                    self.warn(
                        "directive_preset_argument_not_accepted",
                        (*path, "argument"),
                        f"the base {base.name!r} takes no argument",
                    )
                    ok = False
        if not ok:
            return None
        return Preset(name, base, self_preset, argument_text, texts)

    def converter(self, base: Base, key: str) -> Converter | None:
        """The base's converter for option ``key``, or ``None`` when it takes no such
        option."""
        if base.need_type:
            return (lambda text: text) if key in self.need_option_names() else None
        spec = base.cls.option_spec
        if not spec:
            return None
        try:
            return cast("Converter", spec[key])
        except KeyError:
            return None


def _option_spec(base_spec: Any, forced: Iterable[str]) -> Any:
    """[A2] A mapping that behaves as the base's, except that the FORCED keys map to
    ``unchanged`` -- so an authored value the base would reject still reaches ``run()``
    and is reported as forced. A subclass of the base's own mapping type, so sphinx-needs'
    ``DummyOptionSpec`` keeps accepting any key."""
    forced_keys = frozenset(forced)
    parent: type[dict[str, Any]] = type(base_spec) if base_spec is not None else dict

    def getitem(self: dict[str, Any], key: str) -> Any:
        if key in forced_keys:
            return directives.unchanged
        return parent.__getitem__(self, key)

    def contains(self: dict[str, Any], key: object) -> bool:
        return key in forced_keys or parent.__contains__(self, key)

    def get(self: dict[str, Any], key: str, default: Any = None) -> Any:
        return getitem(self, key) if contains(self, key) else default

    forced_spec = type(
        "ForcedSpec",
        (parent,),
        {
            "__getitem__": getitem,
            "__contains__": contains,
            "get": get,
            "__bool__": lambda self: True,
        },
    )
    return forced_spec(base_spec or {})


def preset_class(preset: Preset) -> type[Directive]:
    """The directive class a preset is registered as (§3.5)."""
    base = preset.base
    base_spec = base.cls.option_spec
    defaults, appends, forced = (preset.texts[verb] for verb in VERBS)
    attrs: dict[str, Any] = {}
    if preset.argument is not None:
        attrs["required_arguments"] = 0
        attrs["optional_arguments"] = max(
            1, base.cls.required_arguments + base.cls.optional_arguments
        )
        attrs["final_argument_whitespace"] = base.cls.final_argument_whitespace
    if forced:
        attrs["option_spec"] = _option_spec(base_spec, forced)

    def converter(key: str) -> Converter:
        if base.need_type or not base_spec:
            return lambda text: text
        return cast("Converter", base_spec[key])

    def convert(key: str, text: str) -> Any:
        conv = converter(key)
        if conv is directives.flag:
            return conv(None)
        return conv(text or None)

    def run(self: Directive) -> Any:
        if not self.arguments and preset.argument is not None:
            self.arguments = [preset.argument]
        for key in sorted({*defaults, *appends, *forced}):
            if key in defaults:
                if key not in self.options:
                    self.options[key] = convert(key, defaults[key])
            elif key in appends:
                written = self.options.get(key) or []
                self.options[key] = [*convert(key, appends[key]), *written]
            else:
                if key in self.options:
                    env = self.state.document.settings.env
                    owner = (
                        f"the project defaults for {base.name!r} "
                        f"([parse.directive_presets.{preset.name}])"
                        if preset.self_preset
                        else f"the preset {preset.name!r}"
                    )
                    warn(
                        "preset_forced_option",
                        preset.name.lower(),
                        f"the option {key!r} is fixed by {owner} to {forced[key]!r}; "
                        "the value written here is not used",
                        location=(env.docname, self.lineno),
                    )
                self.options[key] = convert(key, forced[key])
        self.name = base.name
        return base.cls.run(self)

    attrs["run"] = run
    # what the output refusal judges a preset by (§7.10): its base, with its merged options
    attrs[_refusal.PRESET_BASE] = base.name
    attrs[_refusal.PRESET_KEYS] = frozenset({*defaults, *forced})
    attrs[_refusal.PRESET_ARGUMENT] = preset.argument is not None
    safe = re.sub(r"\W", "_", preset.name)
    cls = type(f"Preset_{safe}", (base.cls,), attrs)
    assert issubclass(cls, Directive)
    return cls


def register(app: Sphinx) -> None:
    """``builder-inited``: check every entry and register the accepted presets."""
    reading = resolved(app)
    table = reading["directive_presets"]
    # process state: a build without presets must not see a previous build's (D12)
    _SELF_PRESETS[:] = []
    if not table:
        return
    source = reading["sources"].get("directive_presets") or reading["file"]
    presets = Resolver(app, table, source).resolve()
    # [A4] the classes are built from the snapshotted bases before registering any
    classes = [(preset, preset_class(preset)) for preset in presets]
    _SELF_PRESETS[:] = []
    for preset, cls in classes:
        if preset.self_preset and preset.base.domain is not None:
            app.add_directive_to_domain(
                preset.base.domain, preset.base.name, cls, override=True
            )
        else:
            app.add_directive(preset.name.lower(), cls, override=preset.self_preset)
            if preset.self_preset:
                _SELF_PRESETS.append((preset.name.lower(), cls, source))


#: The self-presets registered in the docutils registry this build (§3.4.7).
_SELF_PRESETS: list[tuple[str, type[Directive], str | None]] = []


def check_replaced(app: Sphinx, *_args: Any) -> None:
    """``env-before-read-docs``: warn once per self-preset whose directive another
    extension registered over it after ``builder-inited`` (§3.4.7)."""
    registry = cast("dict[str, Any]", getattr(directives, "_directives"))  # noqa: B009
    for name, cls, file in _SELF_PRESETS:
        if registry.get(name) is not cls:
            warn(
                "preset_base_replaced",
                render_path(("parse", "directive_presets", name)),
                f"another extension registered {name!r} after the presets were, so the "
                "project defaults of this self-preset are not applied",
                location=file,
            )
