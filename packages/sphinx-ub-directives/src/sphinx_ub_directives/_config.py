"""Reading the tables from ``ubproject.toml`` (contract §2).

The tables are read once, at ``config-inited``, into the confval
``ub_directives_resolved`` -- registered ``rebuild="env"``, so a change to any of them
changes a configuration value and Sphinx re-reads every document, exactly as
``needs_from_toml`` gets it. What is stored is plain, picklable data: the raw tables and
where they came from. Checking them is each mechanism's own business.
"""

from __future__ import annotations

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


def read(app: Sphinx, config: Config) -> None:
    """``config-inited``: read the tables into :data:`CONFVAL`."""
    resolved = empty()
    path = project_file(app)
    if path is not None and path.is_file():
        try:
            data = load_toml(path)
            parse = select_table(data, "parse") or {}
            for table in TABLES:
                value = parse.get(table)
                if value is None:
                    continue
                if not isinstance(value, dict):
                    msg = f"{path}: [parse] {table} must be a table of entries"
                    raise ConfigError(msg)
                resolved[table] = value
            enabled = parse.get("ub_template_enabled", False)
            if not isinstance(enabled, bool):
                msg = f"{path}: [parse] ub_template_enabled must be true or false"
                raise ConfigError(msg)
            resolved["ub_template_enabled"] = enabled
            resolved["file"] = str(path)
            resolved["variants"] = _variants(data, path)
            resolved["extend"] = "extend" in data and any(resolved[t] for t in TABLES)
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
    # after sphinx-needs has read `needs_from_toml` (priority 10), so the same file is read
    app.connect("config-inited", read, priority=20)
    app.connect("builder-inited", report)
