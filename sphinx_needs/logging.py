from __future__ import annotations

from docutils.nodes import Node
from sphinx import version_info
from sphinx.util import logging
from sphinx.util.logging import SphinxLoggerAdapter


def get_logger(name: str) -> SphinxLoggerAdapter:
    return logging.getLogger(name)


def log_warning(
    logger: SphinxLoggerAdapter,
    message: str,
    subtype: str | None,
    /,
    location: str | tuple[str | None, int | None] | Node | None,
    *,
    color: str | None = None,
    once: bool = False,
) -> None:
    # Since sphinx in v7.3, sphinx will show warning types if `show_warning_types=True` is set,
    # and in v8.0 this was made the default.
    if version_info < (8,):
        if subtype:
            message += f" [needs.{subtype}]"
        else:
            message += " [needs]"

    logger.warning(
        message,
        type="needs",
        subtype=subtype,
        location=location,
        color=color,
        once=once,
    )
