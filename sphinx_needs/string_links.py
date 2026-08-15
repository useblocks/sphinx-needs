"""Validation and compilation of :ref:`needs_string_links` configurations.

A *string link* turns a field value such as ``AB-1`` into a hyperlink, by
searching it with a regular expression and rendering the captured groups into a
url template and a name template.

The configurations are validated and compiled once per build during
``config-inited``, rather than lazily while a need is rendered. This means an
unusable configuration — a missing key, a regular expression that does not
compile, a template that does not parse — is reported as a ``needs.string_link``
warning naming the offending entry, and skipped, instead of aborting the build
from inside the renderer with a bare ``KeyError``.

The compiled objects deliberately never touch the Sphinx configuration: the
configuration is deep-copied and pickled (for parallel builds), and compiled
regular expressions and templates do not survive that. Only plain data is
written back to ``needs_string_links``; the compiled form is memoised by the
configuration's own strings in :func:`_compile_string_link`, in the same way
:func:`~sphinx_needs._jinja.compile_template` memoises template sources.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from typing import TYPE_CHECKING, Any, Final, cast

from sphinx_needs._jinja import CompiledTemplate, compile_template
from sphinx_needs.config import _NEEDS_CONFIG, NeedsSphinxConfig, StringLinkConf
from sphinx_needs.data import NeedsCoreFields
from sphinx_needs.logging import get_logger, log_warning

if TYPE_CHECKING:
    from collections.abc import Callable, Container

    from sphinx.application import Sphinx
    from sphinx.config import Config

LOGGER = get_logger(__name__)

_CONF_KEYS: Final = frozenset({"regex", "link_url", "link_name", "options"})
"""The keys a single ``needs_string_links`` entry must define."""

_OPTIONS_TYPES: Final = (list, tuple, set, frozenset)
"""The collection spellings accepted for an entry's ``options``."""


@dataclass(frozen=True)
class CompiledStringLink:
    """A validated ``needs_string_links`` entry, ready to be applied to a value."""

    name: str
    """The name the entry was given in the configuration, used in messages."""
    regex: re.Pattern[str]
    """The compiled regular expression, searched (unanchored) in each value."""
    url_template: CompiledTemplate
    """The compiled ``link_url`` template."""
    name_template: CompiledTemplate
    """The compiled ``link_name`` template."""
    options: tuple[str, ...]
    """The need fields this entry applies to."""


@lru_cache(maxsize=32)
def _compile_string_link(
    name: str,
    regex: str | re.Pattern[str],
    link_url: str,
    link_name: str,
    options: tuple[str, ...],
) -> CompiledStringLink:
    """Compile a single, already validated configuration entry.

    Memoised on the entry's own strings, so that the two renderers
    (the need meta area and ``needtable`` cells) share one compiled object
    for the whole build.

    :param name: The name of the configuration entry.
    :param regex: The regular expression source, or an already-compiled pattern.
    :param link_url: The url template source.
    :param link_name: The link name template source.
    :param options: The need fields the entry applies to.
    :return: The compiled entry.
    :raises re.error: If the regular expression does not compile.
    :raises Exception: If one of the templates does not parse.
    """
    return CompiledStringLink(
        name=name,
        regex=re.compile(regex),
        url_template=compile_template(link_url, autoescape=False),
        name_template=compile_template(link_name, autoescape=False),
        options=options,
    )


def compiled_string_links(
    needs_config: NeedsSphinxConfig,
) -> dict[str, CompiledStringLink]:
    """Get the compiled form of every usable ``needs_string_links`` entry.

    :func:`compile_string_links` has already validated and compiled each of these at
    ``config-inited``, so a failure here means the two disagreed. That should be
    impossible -- both paths compile the same strings -- but it decides whether a
    user's links render, so it is reported rather than swallowed.

    :param needs_config: The sphinx-needs configuration.
    :return: The compiled entries, keyed by their configuration name.
    """
    compiled: dict[str, CompiledStringLink] = {}
    for name, conf in needs_config.string_links.items():
        try:
            compiled[name] = _compile_string_link(
                name,
                conf["regex"],
                conf["link_url"],
                conf["link_name"],
                tuple(conf["options"]),
            )
        except Exception as exc:
            log_warning(
                LOGGER,
                f"needs_string_links[{name!r}]: passed validation but failed to "
                f"compile ({exc}), skipping; its links will not render.",
                "string_link",
                None,
            )
            continue
    return compiled


def string_link_field_names(needs_config: NeedsSphinxConfig) -> set[str]:
    """Get the union of the need fields named by every ``needs_string_links`` entry.

    A field in this set has its value split on ``,`` and ``;`` before the
    entries are applied, whether or not any of them ends up matching.

    :param needs_config: The sphinx-needs configuration.
    :return: The names of the fields string links apply to.
    """
    names: set[str] = set()
    for conf in needs_config.string_links.values():
        names.update(conf["options"])
    return names


def split_string_link_value(value: str) -> list[str]:
    """Split a field value into the items string links are applied to.

    The value is split on ``,`` and ``;`` and each item is stripped;
    items that are empty once stripped are dropped, so that ``AB-1, , AB-2``
    is two items rather than three.

    :param value: The raw field value.
    :return: The items to render.
    """
    return [item for raw in re.split(r",|;", value) if (item := raw.strip())]


def _validate_conf(
    conf: Any,
    *,
    known_fields: Container[str],
    warn: Callable[[str], None],
) -> StringLinkConf | None:
    """Validate a single ``needs_string_links`` entry.

    :param conf: The raw entry, as written by the user.
    :param known_fields: The registered need field names.
    :param warn: Called with a message for every problem found.
    :return: The validated entry, or ``None`` if it must be skipped.
    """
    if not isinstance(conf, dict):
        warn(f"must be a dict, got {conf!r}, skipping.")
        return None

    if missing := sorted(_CONF_KEYS - set(conf)):
        warn(
            f"missing required key(s) {', '.join(repr(k) for k in missing)} "
            f"(required: {', '.join(sorted(_CONF_KEYS))}), skipping."
        )
        return None

    if unknown := sorted(set(conf) - _CONF_KEYS):
        # warn, but keep the entry: a typo in an extra key must not silently
        # take a working link away with it
        warn(
            f"unknown key(s) {', '.join(repr(k) for k in unknown)} "
            f"(allowed: {', '.join(sorted(_CONF_KEYS))}), ignored."
        )

    for key in ("link_url", "link_name"):
        if not isinstance(conf[key], str):
            warn(f"{key!r} must be a string, got {conf[key]!r}, skipping.")
            return None

    # an already-compiled pattern is accepted: `re.compile` passes one straight back,
    # keeping whatever flags it was built with
    if not isinstance(conf["regex"], (str, re.Pattern)):
        warn(
            f"'regex' must be a string or a compiled pattern, "
            f"got {conf['regex']!r}, skipping."
        )
        return None

    options = conf["options"]
    if not isinstance(options, _OPTIONS_TYPES) or not all(
        isinstance(option, str) for option in options
    ):
        # `options` is only ever membership-tested, so any of the four collection
        # spellings is fine; a bare string is not, because it is accepted by neither
        # of the two membership tests it has to pass, and a mapping is not either.
        warn(
            f"'options' must be a list of strings "
            f"(a tuple, set or frozenset is also accepted), got {options!r}, skipping."
        )
        return None

    if not options:
        warn("'options' is empty, so this entry can never apply.")

    for option in options:
        if option not in known_fields:
            warn(
                f"'options' names {option!r}, which is not a registered need field, "
                "so it can never match."
            )

    try:
        re.compile(conf["regex"])
    except Exception as exc:
        # not just `re.error`: `a{99999999999}` raises OverflowError, and a deeply
        # nested pattern can raise RecursionError. Any of them must warn, not abort
        # the build -- this runs at `config-inited`, so it fires even with no needs.
        warn(f"'regex' is not a valid regular expression ({exc}), skipping.")
        return None

    for key in ("link_url", "link_name"):
        try:
            compile_template(conf[key], autoescape=False)
        except Exception as exc:
            warn(f"{key!r} is not a valid template ({exc}), skipping.")
            return None

    if not isinstance(options, list):
        # normalise to plain data for the rebound configuration; a set has no order of
        # its own, so sort it rather than let the config value vary between processes
        normalised = list(options) if isinstance(options, tuple) else sorted(options)
        return cast(StringLinkConf, {**conf, "options": normalised})
    return cast(StringLinkConf, conf)


def compile_string_links(_app: Sphinx, config: Config) -> None:
    """Validate ``needs_string_links``, and compile every usable entry.

    Connected to ``config-inited`` at priority 551,
    i.e. after the need fields have been registered
    and before the configuration is checked.
    Invalid entries are warned about and skipped,
    so that a single bad entry never costs the user the rest of their build.

    :param config: The Sphinx configuration.
    """
    needs_config = NeedsSphinxConfig(config)
    confs = needs_config.string_links
    # the type check has to come first: a *falsy* non-dict -- `[]`, `""`, `0` -- would
    # otherwise leave through the emptiness check unvalidated, and then die on `.items()`
    if not isinstance(confs, dict):
        log_warning(
            LOGGER,
            f"needs_string_links must be a dict, got {confs!r}.",
            "string_link",
            None,
        )
        needs_config.string_links = {}
        return
    if not confs:
        return

    known_fields = {*NeedsCoreFields, *_NEEDS_CONFIG.fields}
    validated: dict[str, StringLinkConf] = {}
    for name, conf in confs.items():

        def warn(message: str, name: Any = name) -> None:
            log_warning(
                LOGGER,
                f"needs_string_links[{name!r}]: {message}",
                "string_link",
                None,
            )

        if (
            checked := _validate_conf(conf, known_fields=known_fields, warn=warn)
        ) is not None:
            validated[name] = checked

    if validated != confs:
        # rebind, never mutate: the dict may still be the user's own conf.py object
        needs_config.string_links = validated

    # compile eagerly, so that the work is not repeated per rendered need
    compiled_string_links(needs_config)
