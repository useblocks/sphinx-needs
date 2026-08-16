"""The portable ``needflow`` option vocabulary.

Every option collected here expresses an *intent* -- a layout direction, what to label
an edge with, which named style applies to which needs -- and never the syntax of one
particular engine.  Each engine then spells that intent in its own language, so a
document written with these options renders on any engine rather than only on the one
its author happened to use.

Where an engine cannot express an intent, it degrades rather than fails: a plainer
diagram beats a failed build.  The degradation is graded, and the grade decides who
hears about it:

1. *Silent best-effort* -- a decorative nearest form exists (a thick border drawn as a
   bold line).
2. *Warn once per project* -- a named intent has no counterpart on this engine
   (``:direction: up`` on PlantUML, which has no bottom-up primitive).
3. *Warn per directive* -- the author made a mistake (a style class that is not
   configured).
4. *Error* -- a closed enumeration was violated, which docutils reports as the option
   is parsed.

Nothing here may warn unless the author actually used the feature: an option-free
build stays silent.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, replace
from typing import Any, Literal, get_args

from docutils.parsers.rst import directives

from sphinx_needs.data import GraphvizStyleType
from sphinx_needs.exceptions import VariantParsingException
from sphinx_needs.logging import get_logger, log_warning
from sphinx_needs.variants import VariantFunctionParsed, match_variants_all

LOGGER = get_logger(__name__)

#: The location accepted by the warning machinery.
LocationType = Any


FlowDirection = Literal["down", "up", "right", "left"]
"""The direction a diagram flows in, as an intent rather than an engine token."""

#: Every spelling accepted by ``:direction:``, mapped to the neutral value.
#: The two-letter forms are the tokens Graphviz and Mermaid users already know, and are
#: accepted so that they do not have to be unlearned.
DIRECTION_ALIASES: Mapping[str, FlowDirection] = {
    "down": "down",
    "up": "up",
    "right": "right",
    "left": "left",
    "tb": "down",
    "td": "down",
    "bt": "up",
    "lr": "right",
    "rl": "left",
}

#: The axis mate of each direction, i.e. the same axis drawn the other way round.
#: PlantUML has ``top to bottom direction`` and ``left to right direction`` and nothing
#: else -- ``bottom to top direction`` and ``right to left direction`` are syntax
#: errors -- so a reversed direction degrades to its mate there.
_AXIS_MATE: Mapping[FlowDirection, FlowDirection] = {
    "down": "down",
    "up": "down",
    "right": "right",
    "left": "right",
}

#: The Graphviz ``rankdir`` token for each direction.  Graphviz supports all four.
GRAPHVIZ_RANKDIR: Mapping[FlowDirection, str] = {
    "down": "TB",
    "up": "BT",
    "right": "LR",
    "left": "RL",
}

#: The PlantUML statement for each direction it can actually draw.
_PLANTUML_DIRECTION: Mapping[FlowDirection, str] = {
    "down": "top to bottom direction",
    "right": "left to right direction",
}


LinkLabels = Literal["none", "outgoing", "incoming", "type"]
"""What to write on an edge, if anything."""

LegendPart = Literal["types", "links"]
"""A section of the out-of-diagram legend."""


#: The keys a ``needs_flow_legends`` entry may set.
_LEGEND_KEYS = frozenset(("parts", "placement"))


@dataclass(frozen=True)
class LegendSpec:
    """A resolved legend configuration."""

    parts: tuple[LegendPart, ...] = ("types",)
    """Which sections the legend describes, in the order they are shown."""

    placement: str = "internal"
    """Where the legend is asked to go: ``internal`` or ``external``.

    This is a *preference*, not a requirement. An engine that cannot draw a good legend
    inside the diagram renders the external table instead, silently: the two carry
    identical information and differ only in where they sit, which makes the
    substitution a decorative nearest form rather than an intent that went unhonoured.
    """

    @property
    def internal(self) -> bool:
        """Whether this legend can actually be drawn inside the diagram.

        Neither in-diagram legend here can describe link types, so a legend that asks
        for them is drawn beside the diagram whatever it would have preferred.
        """
        return self.placement == "internal" and self.parts == ("types",)


def direction_option(argument: str) -> FlowDirection:
    """Parse the ``:direction:`` option value.

    :param argument: The raw option value.
    :return: The neutral direction.
    :raises ValueError: If the value is not a known direction (a closed enumeration,
        which docutils reports against the directive).
    """
    value = directives.choice(
        (argument or "").strip().lower(), tuple(DIRECTION_ALIASES)
    )
    return DIRECTION_ALIASES[value]


def show_link_names_option(argument: str | None) -> LinkLabels:
    """Parse the ``:show_link_names:`` option value.

    The option began as a bare flag meaning "label edges with the outgoing title", which
    is exactly one of the values below -- so it is widened rather than replaced, and a
    bare ``:show_link_names:`` still means what it always did.  docutils hands a valueless
    option ``None`` or ``''`` depending on how it was written, and both mean bare.

    :param argument: The raw option value, ``None`` or empty when written bare.
    :return: What to label edges with.
    :raises ValueError: If the value is not a known kind of label.
    """
    if not (value := (argument or "").strip().lower()):
        return "outgoing"
    return directives.choice(value, get_args(LinkLabels))  # type: ignore[no-any-return]


def show_legend_option(argument: str | None) -> str:
    """Parse the ``:show_legend:`` option value.

    The option takes the *key* of a legend configuration, or nothing at all. It never
    takes the sections inline: a project is free to name its legends whatever it likes,
    and an inline vocabulary would mean a legend called ``types`` collided with the
    section called ``types`` and needed a precedence rule nobody should have to learn.
    One namespace, no reserved words.

    :param argument: The raw option value, ``None`` or empty when written bare.
    :return: The key, or ``""`` when written bare.
    """
    return (argument or "").strip()


def plantuml_direction(
    direction: FlowDirection,
    config_direction: FlowDirection | None,
    *,
    location: LocationType,
) -> str | None:
    """Compute the PlantUML statement that realises a direction, if one is needed.

    PlantUML draws only two of the four directions, so a reversed one degrades to its
    axis mate and is warned about once for the whole project (tier 2): the diagram is
    still drawn, on the right axis, just not reversed.

    Nothing is emitted for a diagram that is already drawn the way it asks to be, so
    that a diagram which does not use the option keeps exactly the source it had
    before the option existed.

    :param direction: The resolved direction.
    :param config_direction: The direction the engine config blob already sets, if any,
        which has to be overridden even when the resolved direction is the default.
    :param location: Where to report the degradation.
    :return: The statement to emit, or ``None`` if none is needed.
    """
    drawn = _AXIS_MATE[direction]
    if drawn != direction:
        log_warning(
            LOGGER,
            f"the plantuml engine cannot draw {direction!r}, "
            f"so the diagram is drawn {drawn!r} instead",
            "needflow",
            location=location,
            once=True,
        )
    if drawn == config_direction or (drawn == "down" and config_direction is None):
        # already how the diagram is drawn, whether because PlantUML draws that way by
        # default or because the config blob already said so, and restating it would
        # move the bytes of a diagram that never asked for anything
        return None
    return _PLANTUML_DIRECTION[drawn]


def graphviz_rankdir(
    direction: FlowDirection, config_direction: FlowDirection | None
) -> str | None:
    """Compute the Graphviz ``rankdir`` value for a direction, if one is needed.

    Graphviz draws all four directions, so nothing degrades here.

    :param direction: The resolved direction.
    :param config_direction: The direction the engine config blob already sets, if any.
    :return: The ``rankdir`` value to emit, or ``None`` if none is needed.
    """
    if direction == config_direction or (
        direction == "down" and config_direction is None
    ):
        # already how the diagram is drawn, whether because Graphviz draws that way by
        # default or because the config blob already said so, and restating it would
        # move the bytes of a diagram that never asked for anything
        return None
    return GRAPHVIZ_RANKDIR[direction]


def plantuml_config_direction(config: str) -> FlowDirection | None:
    """Detect the direction a PlantUML config blob sets, if any.

    The blob is raw PlantUML, so this is a text search rather than a parse; it exists
    only to notice a disagreement with an explicit ``:direction:`` and to know when a
    default direction has to be restated in order to win.

    :param config: The resolved config text.
    :return: The direction the blob sets, or ``None``.
    """
    lowered = config.lower()
    for direction, statement in _PLANTUML_DIRECTION.items():
        if statement in lowered:
            return direction
    return None


def graphviz_config_direction(style: GraphvizStyleType) -> FlowDirection | None:
    """Detect the direction a Graphviz config blob sets, if any (see above).

    ``rankdir`` is a graph attribute, so a blob can set it either as a bare top level
    statement (the ``root`` section) or inside a ``graph [...]`` block -- and the
    shipped ``lefttoright``/``toptobottom`` configs use the latter.  The emitter writes
    ``root`` first and ``graph`` after it, and the later statement wins, so the sections
    are consulted in that same order of increasing authority.

    :param style: The resolved Graphviz style.
    :return: The direction the blob's ``rankdir`` sets, or ``None``.
    """
    found: FlowDirection | None = None
    for section in ("root", "graph"):
        attributes = style.get(section, {})
        if not isinstance(attributes, Mapping):
            continue
        rankdir = str(attributes.get("rankdir", "")).strip().upper()
        for direction, token in GRAPHVIZ_RANKDIR.items():
            if rankdir == token:
                found = direction
    return found


def resolve_direction(
    option: FlowDirection | None,
    config_direction: FlowDirection | None,
    project_default: FlowDirection,
    *,
    location: LocationType,
) -> FlowDirection:
    """Decide which direction a diagram is drawn in.

    An explicit option always wins -- over the engine config blob it is written beside,
    and over the project default.  The blob is a preamble of defaults and the option a
    per-element value, which is the same precedence the engines already give them.
    A disagreement between the two is reported, because it is the one case where the
    author has plainly said two different things.

    :param option: The ``:direction:`` option, ``None`` if it was not given.
    :param config_direction: The direction the engine config blob sets, if any.
    :param project_default: The ``needs_flow_direction`` configuration value.
    :param location: Where to report a disagreement.
    :return: The direction to draw.
    """
    if option is not None:
        if config_direction is not None and config_direction != option:
            log_warning(
                LOGGER,
                f"the engine config sets a {config_direction!r} layout, which "
                f"disagrees with the direction {option!r}; the option is used",
                "needflow",
                location=location,
            )
        return option
    if config_direction is not None:
        return config_direction
    return validated_config_enum(  # type: ignore[return-value]
        project_default,
        get_args(FlowDirection),
        "down",
        name="needs_flow_direction",
        location=None,
    )


#: The engines a needflow can actually be drawn with here.
ENGINES = ("plantuml", "graphviz")

#: The engines a document may name.
#:
#: ``mermaid`` is reserved rather than drawable: ubCode draws needflows with it, and a
#: document naming it must not become unportable the moment it is rendered here -- so it
#: is accepted and degrades to a drawable engine, instead of discarding the directive.
ACCEPTED_ENGINES = (*ENGINES, "mermaid")


def validated_config_enum(
    value: str,
    allowed: tuple[str, ...],
    default: str,
    *,
    name: str,
    location: LocationType,
) -> str:
    """Check a configured value against a closed enumeration, without failing the build.

    An out-of-enum value is a mistake in one line of ``conf.py``, not a reason to end a
    build with a traceback: every value here reaches a lookup table sooner or later, and
    reaching one unchecked is how a typo becomes a ``KeyError``.  The value is reported
    once, with the allowed values, and the documented default is used instead.

    Case and surrounding whitespace are ignored, which is what the matching *option*
    already does -- docutils' ``choice`` lowercases and strips before matching, so
    ``:show_link_names: Outgoing`` has always been accepted while the same word in
    ``conf.py`` warned and fell back to something else entirely.  That asymmetry was
    internal to Sphinx-Needs, and it also made the two implementations of this vocabulary
    disagree, since ubCode normalises both halves.  The warning still quotes the value as
    it was written, so it can be found in ``conf.py``.

    :param value: The configured value.
    :param allowed: The values the configuration accepts.
    :param default: The value to fall back to.
    :param name: The configuration key, for the message.
    :param location: Where to report the value, if anywhere.
    :return: The normalised value, or the default if it is not usable.
    """
    if (normalised := str(value).strip().lower()) in allowed:
        return normalised
    log_warning(
        LOGGER,
        f"Invalid {name!r} value {value!r}, "
        f"allowed values: {', '.join(allowed)}; {default!r} is used",
        "config",
        location=location,
        once=True,
    )
    return default


def resolve_engine(
    option: str | None, project_default: str, *, location: LocationType
) -> str:
    """Decide which engine draws a diagram, without ever failing the build.

    An engine this build cannot run is not a reason to lose the diagram.  ``mermaid`` is
    an accepted name that nothing here can draw, so it degrades to a drawable engine with
    one warning for the project (tier 2); an outright unusable configuration value has
    already been reported when the configuration was read
    (:func:`~sphinx_needs.needs.load_config`), so it degrades silently rather than
    repeating itself once per diagram.

    :param option: The ``:engine:`` option, ``None`` if it was not given.
    :param project_default: The ``needs_flow_engine`` configuration value.
    :param location: Where to report an engine that cannot be drawn with.
    :return: The engine to draw with.
    """
    # normalised the same way as everywhere else, so that a configured "PlantUML" means
    # what `:engine: PlantUML` has always meant (docutils' `choice` lowercases for us)
    engine = (option if option is not None else str(project_default)).strip().lower()
    if engine in ENGINES:
        return engine
    if engine == "mermaid":
        log_warning(
            LOGGER,
            f"the {engine!r} engine is not available in Sphinx-Needs, "
            f"so the diagram is drawn with {ENGINES[0]!r} instead",
            "needflow",
            location=location,
            once=True,
        )
    return ENGINES[0]


#: The legend a diagram gets when nothing names one.
#:
#: Both engines here can draw a types legend inside the diagram, and both have always
#: done so for a bare ``:show_legend:``, so that is the default and a bare option keeps
#: drawing byte-identically to before this option took a key at all. An engine with no
#: good in-diagram legend resolves the same preference to the external table.
ENGINE_DEFAULT_LEGEND = LegendSpec()


def compile_legends(
    legends: Mapping[str, Any], *, location: LocationType
) -> dict[str, LegendSpec]:
    """Turn the ``needs_flow_legends`` configuration into resolved legend specifications.

    :param legends: The ``needs_flow_legends`` configuration value.
    :param location: Where to report an unusable entry.
    :return: The usable legend configurations, by name.
    """
    compiled: dict[str, LegendSpec] = {}
    if not isinstance(legends, Mapping):
        log_warning(
            LOGGER,
            f"'needs_flow_legends' must be a mapping of names to legend configurations, "
            f"but is {type(legends).__name__}",
            "config",
            location=location,
            once=True,
        )
        return compiled
    for name, spec in legends.items():
        if not isinstance(spec, Mapping):
            log_warning(
                LOGGER,
                f"legend {name!r} in 'needs_flow_legends' must be a mapping, "
                f"but is {type(spec).__name__}",
                "config",
                location=location,
                once=True,
            )
            continue
        if unknown := set(spec) - _LEGEND_KEYS:
            log_warning(
                LOGGER,
                f"unknown key(s) {sorted(unknown)} of legend {name!r} in "
                f"'needs_flow_legends', allowed keys: {', '.join(sorted(_LEGEND_KEYS))}",
                "config",
                location=location,
                once=True,
            )
        parts: list[LegendPart] = []
        for raw in spec.get("parts", ["types"]):
            part = str(raw).strip().lower()
            if part not in get_args(LegendPart):
                log_warning(
                    LOGGER,
                    f"unknown legend section {raw!r} of legend {name!r}, "
                    f"allowed values: {', '.join(get_args(LegendPart))}",
                    "config",
                    location=location,
                    once=True,
                )
                continue
            if part not in parts:
                parts.append(part)  # type: ignore[arg-type]
        placement = str(spec.get("placement", "internal")).strip().lower()
        if placement not in ("internal", "external"):
            log_warning(
                LOGGER,
                f"unknown placement {spec.get('placement')!r} of legend {name!r}, "
                "allowed values: internal, external",
                "config",
                location=location,
                once=True,
            )
            placement = "internal"
        compiled[name] = LegendSpec(
            parts=tuple(parts) or ("types",), placement=placement
        )
    return compiled


def resolve_legend(
    present: bool,
    option_key: str,
    project_key: str,
    compiled: Mapping[str, LegendSpec],
    *,
    location: LocationType,
) -> LegendSpec | None:
    """Decide which legend a diagram shows, if any.

    Whether there is a legend is decided by the directive alone -- the configuration
    only ever says *which* one -- so a project default cannot give a legend to a diagram
    that never asked for one, and the key namespace needs no value meaning "off" that
    a legend could accidentally be named after.

    :param present: Whether ``:show_legend:`` was given at all.
    :param option_key: The key the option named, empty when written bare.
    :param project_key: The ``needs_flow_show_legend`` configuration value.
    :param compiled: The configured legends, from :func:`compile_legends`.
    :param location: Where to report an unknown key.
    :return: The legend to draw, or ``None`` for no legend.
    """
    if not present:
        return None
    if not (key := option_key or project_key.strip()):
        return ENGINE_DEFAULT_LEGEND
    if (found := compiled.get(key)) is not None:
        return found
    known = ", ".join(sorted(compiled)) or "none are defined"
    log_warning(
        LOGGER,
        f"legend key {key!r} is not defined in 'needs_flow_legends' "
        f"(available: {known})",
        "needflow",
        location=location,
    )
    return ENGINE_DEFAULT_LEGEND


def validated_config_show_links(
    value: bool | str, *, location: LocationType
) -> LinkLabels:
    """Check the configured project default for edge labels.

    The value was a boolean before it named a kind of label, and both spellings stay
    valid: ``True`` is the ``outgoing`` it has always drawn and ``False`` is ``none``.
    An unusable string warns once and falls back, like every other enumerated value.

    Anything that is neither a string nor a boolean is read for its truth, because that
    is what a value declared ``bool`` for years actually did: ``1`` drew labels and drew
    them silently, so it still does. Only a *string* is held to the enumeration, since a
    string is someone naming a value rather than leaning on truthiness.

    :param value: The ``needs_flow_show_links`` configuration value.
    :param location: Where to report an unusable value, if anywhere.
    :return: What to label edges with by default.
    """
    if not isinstance(value, str):
        return "outgoing" if value else "none"
    return validated_config_enum(  # type: ignore[return-value]
        str(value),
        get_args(LinkLabels),
        "none",
        name="needs_flow_show_links",
        location=location,
    )


def resolve_link_labels(
    option: LinkLabels | None, project_default: bool | str
) -> LinkLabels:
    """Decide what a diagram's edges are labelled with.

    Only an unset option consults the configuration, so a diagram always has the last
    word -- which it did not before the option took a value: the flag and the
    configuration were OR-ed together, so a project that turned labels on left no way of
    turning them off again for one diagram.

    :param option: The ``:show_link_names:`` option, ``None`` if it was not given.
    :param project_default: The ``needs_flow_show_links`` configuration value.
    :return: What to label edges with.
    """
    if option is not None:
        return option
    return validated_config_show_links(project_default, location=None)


def validate_flow_config(
    *, engine: str, direction: str, show_links: bool | str
) -> None:
    """Report every unusable needflow configuration value, once, as it is read.

    Checking these as a diagram is drawn means a project that misconfigures one and
    happens to have no needflow is never told.  The checks are the same functions the
    resolution uses, and they warn only once for a given message, so a project with
    needflows hears about a bad value exactly once rather than twice.

    :param engine: The ``needs_flow_engine`` value.
    :param direction: The ``needs_flow_direction`` value.
    :param show_links: The ``needs_flow_show_links`` value.
    """
    validated_config_enum(
        engine, ACCEPTED_ENGINES, "plantuml", name="needs_flow_engine", location=None
    )
    validated_config_enum(
        direction,
        get_args(FlowDirection),
        "down",
        name="needs_flow_direction",
        location=None,
    )
    validated_config_show_links(show_links, location=None)


@dataclass(frozen=True)
class StyleProps:
    """The resolved presentation properties of a style class.

    The property set is closed: an engine specific escape is the job of
    ``needs_flow_engine_config``, not of a style class, so that a class means the same
    thing wherever the document is rendered.  Every property is ``None`` when no rule
    set it, which is what lets a later rule override only what it actually mentions.
    """

    fill: str | None = None
    """Background colour, without a leading ``#``."""
    border: str | None = None
    """Outline colour, without a leading ``#``."""
    border_width: int | None = None
    """Outline width, in engine specific units, where ``1`` is the normal width."""
    border_style: Literal["solid", "dashed", "dotted"] | None = None
    """How the outline is drawn."""
    text_color: str | None = None
    """Label colour, without a leading ``#``."""
    shape: str | None = None
    """The neutral shape name, see :data:`SHAPES`."""

    def overlay(self, other: StyleProps) -> StyleProps:
        """Apply another rule's properties on top of these.

        Only the properties the other rule actually sets are taken, so declarations
        cascade the way CSS ones do: later wins, per property, not wholesale.

        :param other: The later rule.
        :return: The combined properties.
        """
        return replace(
            self,
            **{name: value for name, value in vars(other).items() if value is not None},
        )


#: The neutral shape vocabulary.
#:
#: Each member is drawable by every engine, either directly or as a near enough form;
#: the names say what the shape *is* rather than what one engine calls it.
SHAPES: Mapping[str, None] = dict.fromkeys(
    (
        "rectangle",
        "rounded",
        "circle",
        "ellipse",
        "diamond",
        "hexagon",
        "cylinder",
        "document",
        "folder",
        "box3d",
    )
)

#: Legacy PlantUML element keywords accepted wherever a neutral shape is expected.
#:
#: These are the values ``needs_types[].style`` has always held, so a project moving to
#: the neutral vocabulary can move a value across unchanged and have it keep its
#: meaning.  Derived from the PlantUML "nestable elements" list.
SHAPE_ALIASES: Mapping[str, str] = {
    "agent": "rectangle",
    "artifact": "document",
    "card": "rounded",
    "component": "rectangle",
    "database": "cylinder",
    "file": "document",
    "folder": "folder",
    "frame": "rectangle",
    "hexagon": "hexagon",
    "node": "box3d",
    "package": "folder",
    "queue": "cylinder",
    "rectangle": "rectangle",
    "stack": "rectangle",
    "storage": "ellipse",
    "usecase": "ellipse",
}

#: How each neutral shape is drawn in PlantUML.
#:
#: PlantUML's nestable elements are a short list, so several shapes have no exact
#: counterpart and take the nearest one silently (tier 1); ``diamond`` has no near form
#: at all and is warned about (tier 2, see :func:`plantuml_shape`).
PLANTUML_SHAPES: Mapping[str, str] = {
    "rectangle": "rectangle",
    "rounded": "card",
    "circle": "usecase",
    "ellipse": "usecase",
    "hexagon": "hexagon",
    "cylinder": "database",
    "document": "artifact",
    "folder": "folder",
    "box3d": "node",
}

#: How each neutral shape is drawn in Graphviz, which has one for every member.
#:
#: ``rounded`` is a box with a style rather than a shape of its own, which the emitter
#: handles; the shape recorded here is the box.
GRAPHVIZ_SHAPES: Mapping[str, str] = {
    "rectangle": "rectangle",
    "rounded": "box",
    "circle": "circle",
    "ellipse": "ellipse",
    "diamond": "diamond",
    "hexagon": "hexagon",
    "cylinder": "cylinder",
    "document": "note",
    "folder": "folder",
    "box3d": "box3d",
}


def plantuml_shape(shape: str, *, location: LocationType) -> str:
    """Translate a neutral shape into a PlantUML element keyword.

    :param shape: The neutral shape name.
    :param location: Where to report a shape PlantUML cannot draw.
    :return: The element keyword to emit.
    """
    if (keyword := PLANTUML_SHAPES.get(shape)) is not None:
        return keyword
    log_warning(
        LOGGER,
        f"the plantuml engine has no {shape!r} shape, so a rectangle is drawn instead",
        "needflow",
        location=location,
        once=True,
    )
    return "rectangle"


#: The closed set of properties a style class may set.
_STYLE_PROPERTIES = frozenset(
    ("fill", "border", "border_width", "border_style", "text_color", "shape")
)

#: The style classes Sphinx-Needs defines itself.
#:
#: ``highlight`` is the class form of the ``:highlight:`` option, and is rendered by
#: each engine in the red outline it has always drawn for it, rather than through the
#: property machinery -- so moving from the option to the class changes nothing about
#: the diagram.
BUILTIN_STYLE_CLASSES = frozenset(("highlight",))


def compile_style_classes(
    styles: Mapping[str, Any], *, location: LocationType
) -> dict[str, StyleProps]:
    """Turn the ``needs_flow_styles`` configuration into resolved properties.

    This runs once per diagram rather than once per need, so a mistake in the
    configuration is reported against the directive that asked for the class, and not
    once for every need that the rule happened to match.

    :param styles: The ``needs_flow_styles`` configuration value.
    :param location: Where to report an unusable class.
    :return: The usable classes, by name.
    """
    compiled: dict[str, StyleProps] = {}
    if not isinstance(styles, Mapping):
        log_warning(
            LOGGER,
            f"'needs_flow_styles' must be a mapping of class names to properties, "
            f"but is {type(styles).__name__}",
            "config",
            location=location,
            once=True,
        )
        return compiled
    for name, props in styles.items():
        if not isinstance(props, Mapping):
            log_warning(
                LOGGER,
                f"style class {name!r} in 'needs_flow_styles' must be a mapping of "
                f"properties, but is {type(props).__name__}",
                "config",
                location=location,
                once=True,
            )
            continue
        values: dict[str, Any] = {}
        for key, value in props.items():
            if key not in _STYLE_PROPERTIES:
                log_warning(
                    LOGGER,
                    f"unknown property {key!r} of style class {name!r} in "
                    f"'needs_flow_styles', allowed properties: "
                    f"{', '.join(sorted(_STYLE_PROPERTIES))}",
                    "config",
                    location=location,
                    once=True,
                )
                continue
            if (
                coerced := _coerce_style_value(key, value, name, location=location)
            ) is not None:
                values[key] = coerced
        compiled[name] = StyleProps(**values)
    return compiled


def _coerce_style_value(
    key: str, value: Any, class_name: str, *, location: LocationType = None
) -> Any:
    """Validate and normalise a single style property value.

    :param key: The property name, already known to be part of the closed set.
    :param value: The configured value.
    :param class_name: The style class the property belongs to, for the message.
    :param location: Where to report an unusable value.
    :return: The normalised value, or ``None`` if it is unusable.
    """
    if key in ("fill", "border", "text_color"):
        return str(value).strip().lstrip("#") or None
    if key == "border_width":
        try:
            return int(value)
        except (TypeError, ValueError):
            log_warning(
                LOGGER,
                f"'border_width' of style class {class_name!r} must be a number, "
                f"but is {value!r}",
                "config",
                location=location,
                once=True,
            )
            return None
    if key == "border_style":
        if (style := str(value).strip().lower()) in ("solid", "dashed", "dotted"):
            return style
        log_warning(
            LOGGER,
            f"unknown 'border_style' {value!r} of style class {class_name!r}, "
            "allowed values: solid, dashed, dotted",
            "config",
            location=location,
            once=True,
        )
        return None
    # key == "shape"
    return resolve_shape(value, class_name=class_name, location=location)


def resolve_shape(
    value: Any, *, class_name: str | None = None, location: LocationType = None
) -> str | None:
    """Normalise a shape name, accepting the legacy PlantUML keywords as aliases.

    :param value: The configured shape.
    :param class_name: The style class the shape belongs to, if any, for the message.
    :param location: Where to report an unknown shape.
    :return: The neutral shape name, or ``None`` if it is not a known shape.
    """
    shape = str(value).strip().lower()
    if shape in SHAPES:
        return shape
    if (aliased := SHAPE_ALIASES.get(shape)) is not None:
        return aliased
    where = f" of style class {class_name!r}" if class_name else ""
    log_warning(
        LOGGER,
        f"unknown shape {value!r}{where}, allowed values: {', '.join(SHAPES)}",
        "config",
        location=location,
        once=True,
    )
    return None


def _rule_class_names(values: Iterable[Any]) -> list[str]:
    """Split the values a rule list matched into individual class names.

    The variant syntax gathers everything after the last filter into a single trailing
    value, so ``[open]:a, b, c`` hands back ``"b, c"`` as one string.  A class name can
    never contain a comma, so splitting on one recovers the classes the author wrote
    and keeps them in the order they wrote them -- which is the order the cascade needs.

    :param values: The values matched, in declaration order.
    :return: The class names, in declaration order, without blanks.
    """
    return [
        name
        for value in values
        for raw in str(value).split(",")
        if (name := raw.strip())
    ]


def declared_style_classes(rules: str) -> list[str]:
    """Every class name a rule list mentions, whatever its filter matches.

    Whether a rule *applies* depends on the need, but which classes it *names* does not,
    so an unknown name can be -- and is -- reported once for the directive that wrote it
    rather than once for every need it was tried against.

    :param rules: The ``:styles:`` option value, in the variant syntax.
    :return: The class names, in declaration order, with duplicates kept.
    """
    if not rules:
        return []
    try:
        parsed = VariantFunctionParsed.from_string(rules, allow_semicolon=True)
    except VariantParsingException:
        # the value is unparseable, which `resolve_styles` reports as it evaluates
        return []
    values = [value for _, _, value in parsed.expressions]
    if parsed.final_value is not None:
        values.append(parsed.final_value)
    return _rule_class_names(values)


def warn_unknown_style_classes(
    rules: str, compiled: Mapping[str, StyleProps], *, location: LocationType
) -> None:
    """Report the classes a diagram names but the configuration does not define.

    :param rules: The ``:styles:`` option value, in the variant syntax.
    :param compiled: The configured classes, from :func:`compile_style_classes`.
    :param location: The directive that named them.
    """
    for name in dict.fromkeys(declared_style_classes(rules)):
        if name not in BUILTIN_STYLE_CLASSES and name not in compiled:
            log_warning(
                LOGGER,
                f"style class {name!r} is not defined in 'needs_flow_styles'",
                "needflow",
                location=location,
            )


def resolve_styles(
    rules: str,
    compiled: Mapping[str, StyleProps],
    *,
    context: dict[str, Any],
    variants: Mapping[str, str],
    location: LocationType,
) -> tuple[StyleProps, bool]:
    """Apply the ``:styles:`` rules of a diagram to one need.

    Every rule whose filter matches contributes, in the order the rules were written,
    and a later rule overrides an earlier one property by property -- the cascade a
    reader already knows from CSS.  The built-in ``highlight`` class is carried
    separately, because each engine draws it in the form it has always used; a later
    rule that sets an outline colour of its own displaces it, as the cascade requires.

    :param rules: The ``:styles:`` option value, in the variant syntax.
    :param compiled: The configured classes, from :func:`compile_style_classes`.
    :param context: The need's filter context, in which the filters are evaluated.
    :param variants: The ``needs_variants`` configuration.
    :param location: Where to report an unknown class.
    :return: The resolved properties, and whether the need is highlighted.
    """
    props = StyleProps()
    highlighted = False
    for name in _rule_class_names(
        match_variants_all(rules, context, dict(variants), location=location)
    ):
        if name in BUILTIN_STYLE_CLASSES:
            highlighted = True
            continue
        if (found := compiled.get(name)) is None:
            # already reported once for the directive by `warn_unknown_style_classes`
            continue
        if found.border is not None:
            # a later outline colour displaces the built-in highlight, per the cascade
            highlighted = False
        props = props.overlay(found)
    return props, highlighted


LineStyle = Literal["solid", "dashed", "dotted", "thick", "invisible"]
"""How a line between two needs is drawn."""

ArrowStyle = Literal["normal", "none", "open", "circle", "cross", "both"]
"""Which arrow heads a line carries.

The members are the ones every engine can draw; anything beyond them would be
expressible in one engine's syntax only, which is what the engine config is for.
"""

#: The legacy PlantUML line keywords, mapped onto the neutral vocabulary.
#: ``needs_links[].style`` has always held these, so a project can move a value across
#: unchanged and have it keep its meaning.
LINE_ALIASES: Mapping[str, LineStyle] = {
    "": "solid",
    "solid": "solid",
    "dashed": "dashed",
    "dotted": "dotted",
    "bold": "thick",
    "thick": "thick",
    "hidden": "invisible",
    "invisible": "invisible",
}

#: How each neutral line is written in PlantUML, inside the ``[...]`` of an arrow.
_PLANTUML_LINES: Mapping[LineStyle, str] = {
    "solid": "",
    "dashed": "dashed",
    "dotted": "dotted",
    "thick": "bold",
    "invisible": "hidden",
}

#: How each neutral line is written as a Graphviz ``style``.
_GRAPHVIZ_LINES: Mapping[LineStyle, str] = {
    "solid": "solid",
    "dashed": "dashed",
    "dotted": "dotted",
    "thick": "bold",
    "invisible": "invis",
}

#: How each neutral arrow is written in PlantUML, as a (start, end) token pair.
#: PlantUML has no crossed head, so ``cross`` degrades to a plain one (see
#: :func:`plantuml_arrow`).
_PLANTUML_ARROWS: Mapping[ArrowStyle, tuple[str, str]] = {
    "normal": ("-", "->"),
    "none": ("-", "-"),
    "open": ("-", "->"),
    "circle": ("-", "-o"),
    "cross": ("-", "->"),
    "both": ("<", "->"),
}

#: How each neutral arrow is written as Graphviz attributes.
_GRAPHVIZ_ARROWS: Mapping[ArrowStyle, tuple[tuple[str, str], ...]] = {
    "normal": (("arrowhead", "normal"),),
    "none": (("arrowhead", "none"),),
    "open": (("arrowhead", "vee"),),
    "circle": (("arrowhead", "odot"),),
    "cross": (("arrowhead", "tee"),),
    "both": (("dir", "both"), ("arrowtail", "normal"), ("arrowhead", "normal")),
}


def resolve_line(line: str) -> LineStyle | None:
    """Decide how a line is drawn, preferring the neutral value over the legacy one.

    An unset -- or unrecognised -- neutral value hands the decision back to the
    deprecated ``style``/``style_part``, which each engine then emits exactly as it
    always has, rather than guessing at what was meant.

    :param line: The configured ``line`` (or ``part_line``), empty if unset.
    :return: The neutral line style, or ``None`` if the legacy value is to be emitted
        as it always has been.
    """
    if line and (resolved := LINE_ALIASES.get(line.strip().lower())) is not None:
        return resolved
    return None


def legacy_style_color(style: str) -> str | None:
    """Pick the color out of a deprecated ``style``/``style_part`` value.

    That value is a compound: a color token and any number of line keywords, comma
    separated.  The neutral vocabulary splits the two apart, so a link type migrated one
    key at a time needs the half it has not migrated yet to keep working.

    :param style: The deprecated value, possibly empty.
    :return: The color token, or ``None`` if the value carries none.
    """
    for raw in style.split(","):
        if (token := raw.strip()).startswith("#"):
            return token
    return None


def resolve_arrow(arrow: str) -> ArrowStyle | None:
    """Decide which arrow heads a line carries.

    :param arrow: The configured ``arrow``, empty if unset.
    :return: The neutral arrow style, or ``None`` if the legacy start/end tokens are
        to be emitted as they always have been.
    """
    if not arrow:
        return None
    value = arrow.strip().lower()
    return value if value in get_args(ArrowStyle) else None  # type: ignore[return-value]


def plantuml_line(line: LineStyle) -> str:
    """Write a neutral line style as PlantUML.

    :param line: The neutral line style.
    :return: What to put inside the ``[...]`` of the arrow, empty for a plain line.
    """
    return _PLANTUML_LINES[line]


def plantuml_arrow(arrow: ArrowStyle, *, location: LocationType) -> tuple[str, str]:
    """Write a neutral arrow style as a PlantUML (start, end) token pair.

    :param arrow: The neutral arrow style.
    :param location: Where to report an arrow PlantUML cannot draw.
    :return: The start and end tokens of the arrow.
    """
    if arrow == "cross":
        log_warning(
            LOGGER,
            "the plantuml engine has no crossed arrow head, "
            "so a plain one is drawn instead",
            "needflow",
            location=location,
            once=True,
        )
    return _PLANTUML_ARROWS[arrow]


def graphviz_line(line: LineStyle) -> str:
    """Write a neutral line style as a Graphviz ``style`` value.

    :param line: The neutral line style.
    :return: The ``style`` value.
    """
    return _GRAPHVIZ_LINES[line]


def graphviz_arrow(arrow: ArrowStyle) -> tuple[tuple[str, str], ...]:
    """Write a neutral arrow style as Graphviz attributes.

    :param arrow: The neutral arrow style.
    :return: The attributes to add.
    """
    return _GRAPHVIZ_ARROWS[arrow]
