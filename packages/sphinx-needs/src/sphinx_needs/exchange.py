"""Deprecated: the needs exchange file (``needs.json``) reader is :mod:`ub_needs_exchange`.

sphinx-needs 9.0.0 shipped the reader as this module; it has since moved to the
``ub-needs-exchange`` library, which sphinx-needs depends on, with one addition -- a
top-level ``format_version`` is now read (the package's contract, section 3.1). This module is kept
through sphinx-needs 9.x so that an import of it keeps working, and is removed in 10.0:
import :mod:`ub_needs_exchange` instead. Every name it exports is the package's own
object, so ``sphinx_needs.exchange.ExchangeError is ub_needs_exchange.ExchangeError``.
"""

from __future__ import annotations

import warnings

from ub_needs_exchange import (
    CURRENT_VERSION_MISSING,
    DEFAULTS_REMOVED_WITHOUT_SCHEMA,
    ID_MISMATCH,
    INVALID_JSON,
    NEEDS_MISSING,
    NOT_AN_OBJECT,
    RECORD_NOT_OBJECT,
    VERSION_NOT_FOUND,
    VERSIONS_MISSING,
    Diagnostic,
    Document,
    ExchangeError,
    Record,
    Version,
    load,
    map_legacy_keys,
    parse,
)

# the names sphinx-needs 9.0.0 exported, and no others
__all__ = (
    "CURRENT_VERSION_MISSING",
    "DEFAULTS_REMOVED_WITHOUT_SCHEMA",
    "ID_MISMATCH",
    "INVALID_JSON",
    "NEEDS_MISSING",
    "NOT_AN_OBJECT",
    "RECORD_NOT_OBJECT",
    "VERSIONS_MISSING",
    "VERSION_NOT_FOUND",
    "Diagnostic",
    "Document",
    "ExchangeError",
    "Record",
    "Version",
    "load",
    "map_legacy_keys",
    "parse",
)

warnings.warn(
    "sphinx_needs.exchange is deprecated and will be removed in sphinx-needs 10.0; "
    "import ub_needs_exchange instead",
    DeprecationWarning,
    stacklevel=2,
)
