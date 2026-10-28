"""The package's one way of reporting a finding.

Every finding is a Sphinx warning of type ``ub_directives`` whose subtype is the bare
contract code (``design/directives-contract.md`` §8), so ``suppress_warnings =
["ub_directives.<code>"]`` silences one. The message starts with its ATTRIBUTION in
brackets -- the ``ubproject.toml`` path of a configuration finding, or the directive a
finding at a use is attributed to -- which is what the conformance runners compare
(§1.3); the rest of the message is for people.
"""

from __future__ import annotations

from typing import Any

from sphinx.util import logging

LOGGER = logging.getLogger("sphinx_ub_directives")

#: The warning type every finding of this package carries.
WARNING_TYPE = "ub_directives"


def warn(code: str, attribution: str, message: str, location: Any = None) -> None:
    """Report one finding.

    :param code: The bare contract code, used as the warning subtype.
    :param attribution: The ``ubproject.toml`` path, or the directive's name.
    :param message: The human half of the message.
    :param location: Where Sphinx should say it is (a docname and line, or a path).
    """
    LOGGER.warning(
        f"[{attribution}] {message}",
        type=WARNING_TYPE,
        subtype=code,
        location=location,
    )
