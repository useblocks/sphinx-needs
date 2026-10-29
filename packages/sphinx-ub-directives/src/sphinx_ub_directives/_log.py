"""The package's one way of reporting a finding.

Every finding is a Sphinx warning of type ``ub_directives`` whose subtype is the bare
contract code (``design/directives-contract.md`` §8), so ``suppress_warnings =
["ub_directives.<code>"]`` silences one. The message starts with its ATTRIBUTION in
brackets -- the ``ubproject.toml`` path of a configuration finding, or the directive a
finding at a use is attributed to -- which is what the conformance runners compare
(§1.3); the rest of the message is for people.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from sphinx.util import logging

LOGGER = logging.getLogger("sphinx_ub_directives")

#: The warning type every finding of this package carries.
WARNING_TYPE = "ub_directives"


def file_location(file: str, attribution: str) -> str:
    """``file:line`` for a configuration finding (L3): the line of the deepest table
    header of ``attribution``'s path that the file writes, else line 1. (Sphinx reads a
    location without a ``:`` as a document name.)"""
    try:
        lines = Path(file).read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError):
        return f"{file}:1"
    segments = attribution.split(".")
    if Path(file).name == "conf.py":
        # a table from conf.py: the line that sets its confval (§2.5)
        confval = {
            "directive_presets": "ub_directive_presets",
            "directive_templates": "ub_directive_templates",
            "template_contexts": "ub_template_contexts",
        }.get(segments[1] if len(segments) > 1 else "", "")
        # the LAST line that assigns it -- plain, annotated, augmented, a method call or an
        # item -- with the name ending there (never a longer name it is a prefix of)
        assigns = (
            re.compile(rf"{re.escape(confval)}\s*(=|:|\+=|\.|\[)") if confval else None
        )
        found = [
            number
            for number, line in enumerate(lines, start=1)
            if assigns is not None and assigns.match(line.lstrip())
        ]
        return f"{file}:{found[-1] if found else 1}"
    for length in range(len(segments), 0, -1):
        header = "[" + ".".join(segments[:length]) + "]"
        for number, line in enumerate(lines, start=1):
            if line.strip() == header:
                return f"{file}:{number}"
    return f"{file}:1"


def warn(code: str, attribution: str, message: str, location: Any = None) -> None:
    """Report one finding.

    :param code: The bare contract code, used as the warning subtype.
    :param attribution: The ``ubproject.toml`` path, or the directive's name.
    :param message: The human half of the message.
    :param location: Where Sphinx should say it is (a docname and line, or a path).
    """
    if isinstance(location, str):
        location = file_location(location, attribution)
    LOGGER.warning(
        f"[{attribution}] {message}",
        type=WARNING_TYPE,
        subtype=code,
        location=location,
    )
