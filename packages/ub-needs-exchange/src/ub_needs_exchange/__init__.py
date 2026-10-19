"""The record of the needs.json exchange format, and its reader.

One implementation of reading the file every tool of the sphinx-needs family exchanges
needs through -- for sphinx-needs' ``needimport`` and ``needs_external_needs``, and for
ubCode, which is to be held to the same behaviour through the conformance corpus
in this package's tests. Standard library only: no Sphinx, no docutils, no sibling
distribution.

It decides no policy. Which fields a project defines, which ids it accepts, whether a
finding is worth a warning, and how a record becomes a need are each consumer's to
decide; this package returns what it found and raises an error for a file no record can
be read from.
"""

from ub_needs_exchange.reader import (
    CURRENT_VERSION_MISSING,
    DEFAULTS_REMOVED_WITHOUT_SCHEMA,
    FORMAT_VERSION,
    FORMAT_VERSION_INVALID,
    FORMAT_VERSION_UNSUPPORTED,
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

__version__ = "1.1.0"

__all__ = [
    "CURRENT_VERSION_MISSING",
    "DEFAULTS_REMOVED_WITHOUT_SCHEMA",
    "FORMAT_VERSION",
    "FORMAT_VERSION_INVALID",
    "FORMAT_VERSION_UNSUPPORTED",
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
    "__version__",
    "load",
    "map_legacy_keys",
    "parse",
]
