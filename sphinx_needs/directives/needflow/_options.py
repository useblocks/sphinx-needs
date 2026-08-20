"""The portable ``needflow`` option vocabulary.

Every option collected here expresses an *intent* -- a layout direction, what to label
an edge with, what a legend describes -- and never the syntax of one particular engine.
Each engine then spells that intent in its own language, so a document written with these
options renders on any engine rather than only on the one its author happened to use.

Where an engine cannot express an intent, it degrades rather than fails: a plainer
diagram beats a failed build.  The degradation is graded, and the grade decides who
hears about it:

1. *Silent best-effort* -- a decorative nearest form exists.
2. *Warn once per project* -- a named intent has no counterpart on this engine
   (``:direction: up`` on PlantUML, which has no bottom-up primitive).
3. *Warn per directive* -- the author made a mistake (an option that disagrees with the
   engine configuration it is written beside).
4. *Error* -- a closed enumeration was violated, which docutils reports as the option
   is parsed.

Nothing here may warn unless the author actually used the feature: an option-free
build stays silent.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Literal, get_args

from docutils.parsers.rst import directives

from sphinx_needs.data import GraphvizStyleType
from sphinx_needs.logging import WarningSubTypes, get_logger, log_warning

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

LegendPlacement = Literal["internal", "external"]
"""Where a legend is asked to be drawn."""


#: The keys a ``needs_flow_legends`` entry may set.
_LEGEND_KEYS = frozenset(("parts", "placement"))

#: The placement an engine of this build uses when a legend does not ask for one.
#:
#: ``placement`` unset means "the engine's default placement" rather than any fixed
#: value, because the honest answer differs per engine: both engines here can draw a
#: types legend inside the picture and have always done so, while an engine with no
#: legend construct at all has only the external table to default to.  Writing the rule
#: this way is what keeps two tools describing one contract instead of each documenting
#: its own answer as if it were universal.
ENGINE_DEFAULT_PLACEMENT: LegendPlacement = "internal"


@dataclass(frozen=True)
class LegendSpec:
    """A resolved legend configuration."""

    parts: tuple[LegendPart, ...] = ("types",)
    """Which sections the legend describes, **in the order they are shown**.

    Order is part of the contract, not an artefact of how the list was written: a
    reader scanning two diagrams should find the same section in the same place, so
    ``["links", "types"]`` puts links first and stays that way on every engine.
    """

    placement: LegendPlacement | None = None
    """Where the legend is asked to go, or ``None`` for the engine's own default.

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
        placement = self.placement or ENGINE_DEFAULT_PLACEMENT
        return placement == "internal" and self.parts == ("types",)


#: The legend a diagram gets when nothing names one.
#:
#: Both engines here can draw a types legend inside the diagram, and both have always
#: done so for a bare ``:show_legend:``, so that is the default and a bare option keeps
#: drawing byte-identically to before this option took a key at all. An engine with no
#: good in-diagram legend resolves the same preference to the external table.
ENGINE_DEFAULT_LEGEND = LegendSpec()


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
    bare ``:show_link_names:`` still means what it always did.  docutils hands a
    valueless option ``None`` or ``''`` depending on how it was written, and both mean
    bare.

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
    project_default: str,
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
    ``:direction: Right`` is accepted while the same word in ``conf.py`` would otherwise
    warn and fall back to something else entirely.  That asymmetry is internal to
    Sphinx-Needs, and it would also make two implementations of this vocabulary
    disagree.  The warning still quotes the value as it was written, so it can be found
    in ``conf.py``.

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
        if str(name) != str(name).strip() or not str(name).strip():
            # `:show_legend:` strips its value, and an empty one means "no name given",
            # so such a name can never be matched however the author writes it; keeping
            # it would leave a legend that silently never appears, and would pad the
            # "available:" list of an unknown-key warning with untypable names
            log_warning(
                LOGGER,
                f"legend {name!r} in 'needs_flow_legends' can never be selected, "
                "because a name is matched with surrounding whitespace removed and "
                "an empty one means no name was given; it is ignored",
                "config",
                location=location,
                once=True,
            )
            continue
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
        raw_parts = spec.get("parts", ["types"])
        if not isinstance(raw_parts, (list, tuple)):
            # a scalar is the shape this mistake actually takes, and both scalars fail
            # badly if let through: a number is not iterable at all, and a string
            # iterates character by character, warning about single letters and then
            # quietly drawing the default legend instead of the one that was asked for.
            # Only a list is accepted -- a second accepted spelling would have to mean
            # the same thing in both tools forever, and `parts` is ordered, which a
            # single name cannot express
            log_warning(
                LOGGER,
                f"'parts' of legend {name!r} must be a list, e.g. "
                f'parts = ["types"], but is {type(raw_parts).__name__}',
                "config",
                location=location,
                once=True,
            )
            raw_parts = ["types"]
        parts: list[LegendPart] = []
        for raw in raw_parts:
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
        placement: LegendPlacement | None = None
        if (raw_placement := spec.get("placement")) is not None:
            candidate = str(raw_placement).strip().lower()
            if candidate not in get_args(LegendPlacement):
                log_warning(
                    LOGGER,
                    f"unknown placement {raw_placement!r} of legend {name!r}, "
                    f"allowed values: {', '.join(get_args(LegendPlacement))}",
                    "config",
                    location=location,
                    once=True,
                )
            else:
                placement = candidate  # type: ignore[assignment]
        compiled[str(name)] = LegendSpec(
            parts=tuple(parts) or ("types",), placement=placement
        )
    return compiled


def resolve_legend(
    present: bool,
    option_key: str,
    project_key: Any,
    compiled: Mapping[str, LegendSpec],
    *,
    location: LocationType,
) -> LegendSpec | None:
    """Decide which legend a diagram shows, if any.

    Whether there is a legend is decided by the directive alone -- the configuration
    only ever says *which* one -- so a project default cannot give a legend to a diagram
    that never asked for one, and the key namespace needs no value meaning "off" that
    a legend could accidentally be named after.

    *Which* one is a chain, not a switch: the option, then the configuration, then the
    engine's own legend. A key that names nothing is **treated as unset**, which is the
    rule the rest of this vocabulary already follows -- an unusable
    ``needs_flow_show_links`` string warns and then behaves as though it had not been
    written -- so it warns and hands on to the next step rather than replacing it. A
    typo in one directive must not silently cost the project the legend it configured.

    The two steps warn differently because they are different mistakes. An option key is
    the directive's own text, so it is reported there, every time. A project key is one
    ``conf.py`` line, so it is reported once for the whole build; repeating it at every
    needflow would bury the directive-level warnings an author can act on.

    Both keys are coerced before they are matched, so a configuration value that is not a
    string at all names nothing and hands on, exactly as a misspelt one does -- rather than
    reaching :meth:`str.strip` and ending the build. The read-time check coerces the same
    way, so the two still emit the same text and Sphinx's ``once`` filter collapses them.

    :param present: Whether ``:show_legend:`` was given at all.
    :param option_key: The key the option named, empty when written bare.
    :param project_key: The ``needs_flow_show_legend`` configuration value, which the
        configuration hands through unchanged and so need not be a string.
    :param compiled: The configured legends, from :func:`compile_legends`.
    :param location: Where to report an unknown option key.
    :return: The legend to draw, or ``None`` for no legend.
    """
    if not present:
        return None
    # the steps of the chain, each with the tier its own mistake belongs to: the option
    # is authored per directive and reported there every time, the configuration is one
    # `conf.py` line and reported once for the build
    steps: tuple[tuple[str, str, WarningSubTypes, LocationType, bool], ...] = (
        (option_key.strip(), "", "needflow", location, False),
        (
            str(project_key).strip(),
            " of 'needs_flow_show_legend'",
            "config",
            None,
            True,
        ),
    )
    for key, named, subtype, where, once in steps:
        if not key:
            continue
        if (found := compiled.get(key)) is not None:
            return found
        warn_unknown_legend_key(
            key, compiled, named=named, subtype=subtype, location=where, once=once
        )
    return ENGINE_DEFAULT_LEGEND


def warn_unknown_legend_key(
    key: str,
    compiled: Mapping[str, LegendSpec],
    *,
    named: str,
    subtype: WarningSubTypes,
    location: LocationType,
    once: bool,
) -> None:
    """Report a legend name that ``needs_flow_legends`` does not define.

    Shared by the read-time check and the per-diagram resolution so that the two emit
    the *same* text: Sphinx's ``once`` filter dedupes on the message, so identical
    wording is what lets the read-time warning -- which knows no directive -- win, and
    keeps a ``conf.py`` mistake from being reported against an ``index.rst`` line.

    :param key: The name that was asked for.
    :param compiled: The configured legends, from :func:`compile_legends`.
    :param named: Where the name came from, as a phrase, empty for a directive option.
    :param subtype: The warning subtype to report under.
    :param location: Where to report it, ``None`` for the project.
    :param once: Whether to report it only once for the build.
    """
    known = ", ".join(sorted(compiled)) or "none are defined"
    log_warning(
        LOGGER,
        f"legend key {key!r}{named} is not defined in 'needs_flow_legends' "
        f"(available: {known})",
        subtype,
        location=location,
        once=once,
    )


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
    *,
    direction: str,
    show_links: bool | str,
    legends: Mapping[str, Any],
    show_legend: Any,
) -> None:
    """Report every unusable needflow configuration value, once, as it is read.

    Checking these as a diagram is drawn means a project that misconfigures one and
    happens to have no needflow is never told.  The checks are the same functions the
    resolution uses, and they warn only once for a given message, so a project with
    needflows hears about a bad value exactly once rather than twice -- and hears it
    against ``conf.py`` rather than against whichever directive happened to be drawn
    first, because this call has no directive location to attach.

    :param direction: The ``needs_flow_direction`` value.
    :param show_links: The ``needs_flow_show_links`` value.
    :param legends: The ``needs_flow_legends`` value.
    :param show_legend: The ``needs_flow_show_legend`` value, which the configuration
        hands through unchanged and so need not be a string.
    """
    validated_config_enum(
        direction,
        get_args(FlowDirection),
        "down",
        name="needs_flow_direction",
        location=None,
    )
    validated_config_show_links(show_links, location=None)
    compiled = compile_legends(legends, location=None)
    # coerced rather than trusted: `types: (str,)` makes Sphinx warn about a wrong type and
    # then hand the raw value through, so a non-string reached `str.strip` and ended the
    # build with a traceback -- which is precisely what this function exists to prevent, and
    # what every sibling key here already guards against
    if (key := str(show_legend).strip()) and key not in compiled:
        warn_unknown_legend_key(
            key,
            compiled,
            named=" of 'needs_flow_show_legend'",
            subtype="config",
            location=None,
            once=True,
        )
