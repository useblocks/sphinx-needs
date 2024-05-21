from __future__ import annotations

from sphinx.util import logging
from sphinx.util.logging import SphinxLoggerAdapter


def get_logger(name: str) -> SphinxLoggerAdapter:
    return logging.getLogger(name)
