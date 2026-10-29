"""Reading the tables from ``ubproject.toml``, and from ``conf.py`` (contract §2, §2.5).

The tables are read once, at ``config-inited``, into the confval
``ub_directives_resolved`` -- registered ``rebuild="env"``, so a change to any of them
changes a configuration value and Sphinx re-reads every document, exactly as
``needs_from_toml`` gets it. What is stored is plain, picklable data: the raw tables and
where each came from. Checking them is each mechanism's own business.

Four confvals mirror the tables (§2.5, Sphinx only). A key the file's ``[parse]`` table
SETS replaces the confval's value whole (sphinx-needs' per-key rule), unless the confval
was given with ``-D``; a ``conf.py`` value must be one TOML could have written.
"""

from __future__ import annotations

import datetime
from pathlib import Path
from typing import Any

from sphinx.application import Sphinx
from sphinx.config import Config
from sphinx.errors import ConfigError

from ub_project import ProjectConfigError, find_project_config, load_toml, select_table

from ._log import warn

#: The name of the confval holding what was read.
CONFVAL = "ub_directives_resolved"

#: The tables this package reads, under ``[parse]``.
TABLES = ("directive_presets", "directive_templates", "template_contexts")

#: The ``conf.py`` confval of each ``[parse]`` key (§2.5).
CONFVALS = {
    "directive_presets": "ub_directive_presets",
    "directive_templates": "ub_directive_templates",
    "template_contexts": "ub_template_contexts",
    "ub_template_enabled": "ub_template_enabled",
}

#: The signed 64-bit range: what a TOML integer can be.
_I64 = range(-(2**63), 2**63)


def empty() -> dict[str, Any]:
    """What a project without ``ubproject.toml`` (or without the tables) reads."""
    return {
        "file": None,
        "directive_presets": {},
        "directive_templates": {},
        "template_contexts": {},
        "ub_template_enabled": False,
        "variants": None,
        "extend": False,
        # where each table (and the switch) was read from: the TOML file, or conf.py
        "sources": dict.fromkeys(CONFVALS),
    }


def project_file(app: Sphinx) -> Path | None:
    """The one file the tables are read from: sphinx-needs' ``needs_from_toml`` when it
    is set, so both read the same file, else the one ub-project finds from the
    ``confdir``."""
    confdir = Path(app.confdir)
    from_toml = getattr(app.config, "needs_from_toml", None)
    if isinstance(from_toml, str) and from_toml:
        return confdir / from_toml
    return find_project_config(confdir)


def _toml_value(value: Any, where: str) -> Any:
    """A ``conf.py`` value as the TOML that could have written it (§2.5), or a
    :class:`~sphinx.errors.ConfigError` naming the confval and the key path.

    Insertion order is file order; a tuple is a list."""
    if isinstance(value, dict):
        converted = {}
        for key, item in value.items():
            if not isinstance(key, str):
                msg = f"{where}: the key {key!r} is not a string, which every ubproject.toml key is"
                raise ConfigError(msg)
            converted[key] = _toml_value(item, f"{where}[{key!r}]")
        return converted
    if isinstance(value, list | tuple):
        return [
            _toml_value(item, f"{where}[{index}]") for index, item in enumerate(value)
        ]
    if isinstance(value, bool | str | float | datetime.date | datetime.time):
        return value
    if isinstance(value, int):
        if value not in _I64:
            msg = f"{where}: {value} is outside the signed 64-bit range ubproject.toml integers have"
            raise ConfigError(msg)
        return value
    if callable(value) or not isinstance(
        value, type(None) | set | frozenset | bytes | Path
    ):
        msg = (
            f"{where}: {value!r} is not a value ubproject.toml can hold -- contexts and the "
            "other tables are data only, never a function or a Python object (see the "
            "'Migrating from sphinx-jinja2' page)"
        )
        raise ConfigError(msg)
    msg = f"{where}: {value!r} is not a value ubproject.toml can hold"
    raise ConfigError(msg)


def _from_confpy(config: Config) -> dict[str, Any]:
    """The four confvals, each checked and converted (§2.5)."""
    values: dict[str, Any] = {}
    for key, confval in CONFVALS.items():
        value = getattr(config, confval)
        if key == "ub_template_enabled":
            if not isinstance(value, bool):
                msg = f"{confval}: {value!r} must be True or False"
                raise ConfigError(msg)
            values[key] = value
            continue
        if not isinstance(value, dict):
            msg = f"{confval}: {value!r} must be a dict of entries, as [parse] {key} is a table"
            raise ConfigError(msg)
        values[key] = _toml_value(value, confval)
    return values


def read(app: Sphinx, config: Config) -> None:
    """``config-inited``: read the tables into :data:`CONFVAL` -- ``conf.py``'s four
    confvals first, then every key the project file's ``[parse]`` sets, whole, except a
    confval given with ``-D`` (§2.5)."""
    resolved = empty()
    confpy = str(Path(app.confdir) / "conf.py")
    for key, value in _from_confpy(config).items():
        resolved[key] = value
        resolved["sources"][key] = confpy
    overridden = set(getattr(config, "overrides", {}) or {})
    path = project_file(app)
    if path is not None and path.is_file():
        try:
            data = load_toml(path)
            parse = select_table(data, "parse") or {}
            declared: dict[str, Any] = {}
            for table in TABLES:
                value = parse.get(table)
                if value is None:
                    continue
                if not isinstance(value, dict):
                    msg = f"{path}: [parse] {table} must be a table of entries"
                    raise ConfigError(msg)
                declared[table] = value
            if "ub_template_enabled" in parse:
                enabled = parse["ub_template_enabled"]
                if not isinstance(enabled, bool):
                    msg = f"{path}: [parse] ub_template_enabled must be true or false"
                    raise ConfigError(msg)
                declared["ub_template_enabled"] = enabled
            for key, value in declared.items():
                if CONFVALS[key] in overridden:
                    continue
                resolved[key] = value
                resolved["sources"][key] = str(path)
            resolved["file"] = str(path)
            resolved["variants"] = _variants(data, path)
            # about the FILE's own tables only, whatever conf.py adds (§2.1)
            resolved["extend"] = "extend" in data and any(
                declared.get(t) for t in TABLES
            )
        except ProjectConfigError as error:
            raise ConfigError(str(error)) from error
    setattr(config, CONFVAL, resolved)


def _variants(data: dict[str, Any], path: Path) -> dict[str, Any] | None:
    """The variant data for ``var`` when sphinx-needs is NOT loaded: ub-project's read of
    the file, or ``None`` when it cannot be read (sphinx-needs then reports nothing either,
    since it is not loaded; the template sees an empty ``var``)."""
    from ub_project import read_variants

    try:
        return dict(read_variants(data, path).data)
    except ProjectConfigError:
        return None


def report(app: Sphinx) -> None:
    """``builder-inited``: the findings of the reading itself (§2.1), once per build."""
    reading = resolved(app)
    if reading.get("extend"):
        warn(
            "extend_unsupported",
            "extend",
            f"{Path(reading['file']).name} has an extend key; a Sphinx build reads this "
            "one file only, so the tables it would inherit are not read",
            location=reading["file"],
        )


def resolved(app: Sphinx) -> dict[str, Any]:
    """What :func:`read` stored, or an empty reading."""
    value = getattr(app.config, CONFVAL, None)
    return value if isinstance(value, dict) else empty()


def setup(app: Sphinx) -> None:
    """Register the confval and the reader."""
    app.add_config_value(CONFVAL, empty(), "env", types=(dict,))
    for key, confval in CONFVALS.items():
        if key == "ub_template_enabled":
            app.add_config_value(confval, False, "env", types=(bool,))
        else:
            app.add_config_value(confval, {}, "env", types=(dict,))
    # after sphinx-needs has read `needs_from_toml` (priority 10), so the same file is read
    app.connect("config-inited", read, priority=20)
    app.connect("builder-inited", report)
