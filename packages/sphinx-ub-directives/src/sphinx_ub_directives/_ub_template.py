"""``ub-template``, the generic template directive (contract §6)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from docutils import nodes
from docutils.parsers.rst import Directive, directives

from . import _engine, _refusal
from ._config import resolved
from ._engine import Root
from ._log import warn
from ._templates import (
    app_of,
    context_value,
    expand,
    file_markup,
    host_markup,
    note,
    variants,
)

NAME = "ub-template"


class UbTemplate(Directive):
    """Render the body, or a ``:file:``, with a named context, ``:ctx:`` and ``var``."""

    optional_arguments = 1
    final_argument_whitespace = True
    has_content = True
    option_spec = {
        "file": directives.unchanged,
        "ctx": directives.unchanged,
        "debug": directives.flag,
        "raw": directives.unchanged,
    }

    def run(self) -> list[nodes.Node]:
        env = self.state.document.settings.env
        location = (env.docname, self.lineno)
        app = app_of()
        reading = resolved(app)
        if not reading["ub_template_enabled"]:
            warn(
                "template_switched_off",
                NAME,
                "ub-template renders only when [parse] ub_template_enabled is true in "
                "ubproject.toml; it renders nothing here",
                location=location,
            )
            return []
        raw = self.options.get("raw")
        if raw is not None and not raw.strip():
            warn(
                "template_option_invalid",
                NAME,
                "the 'raw' option needs an output format, e.g. ':raw: html'",
                location=location,
            )
            return []
        root = Root(Path(env.srcdir))
        context: dict[str, Any] = {}
        if self.arguments:
            name = self.arguments[0].strip()
            contexts = reading["template_contexts"]
            if name not in contexts or name == "var":
                warn(
                    "template_context_unknown",
                    NAME,
                    f"no context is named {name!r}",
                    location=location,
                )
                return []
            try:
                data = context_value(env, root, name, contexts[name])
                if "var" in data:
                    msg = (
                        "it has a top-level var key, and var is always the variant data"
                    )
                    raise ValueError(msg)
            except ValueError as error:
                warn(
                    "template_context_invalid",
                    NAME,
                    f"the context {name!r} cannot be used: {error}",
                    location=location,
                )
                return []
            context.update(data)
        if "ctx" in self.options:
            try:
                inline = json.loads(self.options["ctx"] or "")
                if not isinstance(inline, dict):
                    msg = "it is not a JSON object"
                    raise ValueError(msg)
                _engine.check_data(inline, "ctx")
                if "var" in inline:
                    msg = "it has a var key, and var is always the variant data"
                    raise ValueError(msg)
            except ValueError as error:
                warn(
                    "template_context_invalid",
                    NAME,
                    f"the 'ctx' option cannot be used: {error}",
                    location=location,
                )
                return []
            context.update(inline)
        context["var"] = variants(app)
        file = self.options.get("file")
        if file:
            if self.content:
                warn(
                    "template_option_invalid",
                    NAME,
                    "both the 'file' option and a body are given; the body is ignored",
                    location=location,
                )
            if file.startswith("/"):
                path = root.resolve(file)
            else:
                candidate = Path(env.doc2path(env.docname)).parent / file
                path = candidate if root.contains(candidate) else None
            if path is None:
                note(env, root.path / file.lstrip("/"))
                warn(
                    "template_outside_root",
                    NAME,
                    f"the template {file} is outside the source root; it is not read",
                    location=location,
                )
                return []
            note(env, path)
            try:
                source = root.read(path)
            except (OSError, UnicodeDecodeError) as error:
                warn(
                    "template_missing",
                    NAME,
                    f"the template {file} cannot be read: {error}",
                    location=location,
                )
                return []
            markup = file_markup(file) or host_markup(self)
            identity, name = f"file:{path}", file
        else:
            source = "\n".join(self.content)
            markup = host_markup(self)
            identity, name = (
                f"inline:{env.docname}:{self.lineno}",
                f"{env.docname}:{self.lineno}",
            )
        return expand(
            self,
            use=NAME,
            identity=identity,
            source=source,
            name=name,
            context=context,
            root=root,
            markup=markup,
            raw=raw,
            debug="debug" in self.options,
        )


setattr(UbTemplate, _refusal.TEMPLATE_MARKER, True)
