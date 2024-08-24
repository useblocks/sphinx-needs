from __future__ import annotations

from docutils.nodes import Node
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
    # TODO respect show_warning_types
    logger.warning(
        message + f" [needs.{subtype}]",
        type="needs",
        subtype=subtype,
        location=location,
        color=color,
        once=once,
    )
