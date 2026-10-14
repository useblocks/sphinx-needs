.. _changelog:

Changelog
=========

.. _`release:1.0.0`:

1.0.0
-----

:Released: 2026-10-14

The first release, as **1.0.0**: the record of the needs.json exchange format, and the one
reader of it the sphinx-needs family is to share -- the reader sphinx-needs 9.0.0 shipped as
``sphinx_needs.exchange``, with a top-level ``format_version`` now read. It comes with the
format's contract and a conformance corpus ubCode is to vendor; sphinx-needs is to read
through it from its next release.

- **The reader.** ``load`` / ``parse`` a needs.json into a ``Document``,
  ``Document.select_version`` the version asked for (or the file's ``current_version``),
  and ``Version.records()`` its need records, each keyed by its id, with the legacy
  ``description`` read as ``content`` and the version's ``needs_schema`` defaults merged
  under it. A file no record can be read from raises ``ExchangeError`` with a code; what is
  read nonetheless is reported as ``Diagnostic`` values -- a code and the place in the
  file -- and never logged. Moved from ``sphinx_needs.exchange`` (sphinx-needs
  9.0.0) with one addition -- a top-level ``format_version`` is now read (the next entry;
  contract §3.1); sphinx-needs is to read through it, and ``sphinx_needs.exchange`` to
  become a deprecated alias of it, in its next release.
- **``format_version``.** The reader accepts a top-level ``format_version``: absent is
  format 1, the only one there is. A value above 1 is read as format 1 and reported
  (``format_version_unsupported``); anything but an integer of 1 or more refuses the file
  (``format_version_invalid``). Nothing writes the key yet.
- **The contract.** ``design/exchange-contract.md`` is the normative description of the
  format as it is read, and ``tests/fixtures/needs_json_reading_conformance.toml`` its
  executable half, which ubCode is to vendor: 74 cases, all of the ``document`` layer --
  what the reader owns, with no project. The ``ingest`` layer, what each tool's readers
  decide of a record, is defined in the corpus's header for the cases to come.

Standard library only: no Sphinx, no docutils, no sibling distribution.
