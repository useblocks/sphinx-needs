.. _changelog:

Changelog
=========

Unreleased
----------

- **A version can say its ids are namespaced.** ``"namespaced_ids": true`` in a version
  object says that each of its ids, and each link target written in it, is a namespace of
  one or more segments and a local id, joined by ``::`` and split at the last ``::``; any
  other value, or none, says nothing, and a ``namespaced_ids`` of the envelope marks no
  version. ``Version.namespaced_ids`` reads it, ``True`` only for the JSON ``true``, and
  the new ``split_id`` splits an id by the rule the contract fixes --
  ``split_id("a::b::X")`` is ``(("a", "b"), "X")``, an id with no ``::`` is
  ``((), id)``, and an id that breaks the grammar raises ``ValueError``. Records keep
  their ids as written, and nothing is reported for one that does not split: the
  package reads the marker and leaves acting on it to each consumer. Nothing writes the
  key yet. ``design/exchange-contract.md`` §5.4 states it, and the corpus has 102 cases,
  ten of them new, with the expectation keys ``namespaced_ids``, ``split`` and
  ``unsplittable``.

.. _`release:1.1.0`:

1.1.0
-----

:Released: 2026-10-19

A needs.json whose ``format_version`` names a later format is refused with its own code,
where 1.0.0 read an integer above 1 as format 1 and reported it, and refused a pre-release
string as not a format version: the format a file states is what tells a later format of
needs.json from this one, and what a later format's records mean is not this reader's to
guess.

- **A later ``format_version`` refuses the file.** An integer above 1, such as ``2``, or a
  pre-release of a format -- a format number of 1 or more, ``a``, ``b`` or ``rc``, and a
  pre-release number of 1 or more, each written in the digits ``0``–``9`` without leading
  zeros, as in ``"2a1"``, ``"2b1"`` or ``"2rc1"`` -- raises ``ExchangeError`` with the
  code ``format_version_unsupported``, which 1.0.0 gave, for an integer, as a
  ``Diagnostic`` of a file it read on. It is checked before anything else in the
  envelope, so a file of a later format that has no ``versions`` is refused for its
  format, not as ``versions_missing``. Absent or ``1``, the file is read as before, and
  any other value is still ``format_version_invalid``. A consumer that looked for
  ``format_version_unsupported`` among ``Version.diagnostics`` meets it as a refusal
  instead.
- **Both messages spell the value as JSON writes it** -- ``"2a1"``, ``2``, ``2.0``,
  ``true``, ``null``, a character outside ASCII as itself and a lone surrogate as its
  escape -- where 1.0.0 used Python's spelling (``'1'``, ``True``, ``None``).
- **The contract and the corpus.** ``design/exchange-contract.md`` §3.1 and §8 say so,
  withdrawing 1.0.0's "a later format is to stay readable as this one", and the corpus
  has 92 cases: ``format-version-above-1-is-read-as-1`` is now
  ``format-version-above-1-is-refused``, ``every-finding-of-a-file-is-reported`` is read
  at ``format_version`` 1, and eighteen cases are new. Nothing writes the key yet.

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
