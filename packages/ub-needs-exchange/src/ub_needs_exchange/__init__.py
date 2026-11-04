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
    CONTENT_NOT_OBJECT,
    CURRENT_VERSION_MISSING,
    DEFAULTS_REMOVED_WITHOUT_SCHEMA,
    DRAFT_HAS_VERSIONS,
    DUPLICATE_ID,
    FIELDS_NOT_OBJECT,
    FORMAT_VERSION,
    FORMAT_VERSION_INVALID,
    FORMAT_VERSION_UNSUPPORTED,
    HOP_INVALID,
    ID_MISMATCH,
    ID_MISSING,
    ID_NOT_STRING,
    INVALID_JSON,
    LINK_INVALID,
    LINKS_NOT_OBJECT,
    NEEDS_MISSING,
    NOT_AN_OBJECT,
    PROJECT_INVALID,
    RECORD_NOT_OBJECT,
    SOURCE_NOT_A_LIST,
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
    "CONTENT_NOT_OBJECT",
    "CURRENT_VERSION_MISSING",
    "DEFAULTS_REMOVED_WITHOUT_SCHEMA",
    "DRAFT_HAS_VERSIONS",
    "DUPLICATE_ID",
    "FIELDS_NOT_OBJECT",
    "FORMAT_VERSION",
    "FORMAT_VERSION_INVALID",
    "FORMAT_VERSION_UNSUPPORTED",
    "HOP_INVALID",
    "ID_MISMATCH",
    "ID_MISSING",
    "ID_NOT_STRING",
    "INVALID_JSON",
    "LINKS_NOT_OBJECT",
    "LINK_INVALID",
    "NEEDS_MISSING",
    "NOT_AN_OBJECT",
    "PROJECT_INVALID",
    "RECORD_NOT_OBJECT",
    "SOURCE_NOT_A_LIST",
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
