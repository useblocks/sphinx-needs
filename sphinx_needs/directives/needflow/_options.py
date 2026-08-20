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
from typing import Any, Literal, get_args

from docutils.parsers.rst import directives

from sphinx_needs.data import GraphvizStyleType
from sphinx_needs.logging import get_logger, log_warning

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


def validate_flow_config(*, direction: str) -> None:
    """Report every unusable needflow configuration value, once, as it is read.

    Checking these as a diagram is drawn means a project that misconfigures one and
    happens to have no needflow is never told.  The checks are the same functions the
    resolution uses, and they warn only once for a given message, so a project with
    needflows hears about a bad value exactly once rather than twice -- and hears it
    against ``conf.py`` rather than against whichever directive happened to be drawn
    first, because this call has no directive location to attach.

    :param direction: The ``needs_flow_direction`` value.
    """
    validated_config_enum(
        direction,
        get_args(FlowDirection),
        "down",
        name="needs_flow_direction",
        location=None,
    )
