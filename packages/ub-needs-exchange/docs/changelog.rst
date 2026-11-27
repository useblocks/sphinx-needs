.. _changelog:

Changelog
=========

Unreleased
----------

- **The needs.json draft "2a2" replaces "2a1" (experimental).**
  ``select_version(..., drafts=("2a2",))`` reads the draft ``"2a2"``, which is ``"2a1"``
  with two changes. A need's parts are a section of the record beside its content,
  ``"parts": [{"id": "zeta", "text": "…"}, {"id": "alpha", "text": "…"}]``, projected to
  format 1's ``parts`` in the section's order and read whether the record has a content
  or not; ``content.parts`` is no longer read. An entry that is not an object of a string
  ``id`` and a string ``text`` is dropped (``part_invalid``, path
  ``needs.<i>.parts.<j>``), a later entry of an id read is skipped
  (``duplicate_part_id``, path ``needs.<i>.parts.<j>.id``), a ``parts`` that is not an
  array is not read (``parts_not_a_list``, path ``needs.<i>.parts``), each a finding of
  the record, which is read; an entry whose id is empty is handed on, for the reading
  project to refuse the need; an unknown key of an entry (``anchor`` among them) is
  ignored. And a link to the empty part, ``{"id": "B", "part": ""}``, is spelled ``B.``,
  as format 1 writes it, where it was spelled ``B``, a link to the need (changed output).
  A ``"2a1"`` file is refused as every later format is (``format_version_unsupported``),
  and ``drafts=("2a1",)`` names a draft this reader does not know (``ValueError``): the
  draft's API is experimental, and nothing is aliased. Three constants are new and
  re-exported, ``PARTS_NOT_A_LIST``, ``PART_INVALID`` and ``DUPLICATE_PART_ID``; no public
  name carried ``2a1``. The contract is ``design/v2a2-draft.md`` (was ``v2a1-draft.md``)
  and the corpus ``tests/fixtures/needs_json_2a2_draft_conformance.toml`` (was
  ``needs_json_2a1_draft_conformance.toml``), 92 cases (was 78); the shared reading corpus
  is unchanged.

- **``namespace_prefix``: the text that joins an id to a namespace.**
  ``namespace_prefix(["SUP"])`` is ``"SUP::"`` (and ``""`` for the empty namespace), so a
  caller that puts a namespace in front of ids -- every id of a file, say -- never spells
  the separator itself, and gets the namespace checked: a segment that is not a segment
  is refused as ``join_id`` refuses it. Put before an id that can be joined, the prefix
  gives exactly what ``join_id`` gives (``SUP::nc::REQ_1``, in the namespace
  ``SUP::nc``); put before one that cannot (``a::::b``, ``:X``), it gives a plain id
  outside the namespace, and what that costs is the caller's to decide.
  ``design/exchange-contract.md`` §14 rule 10 states the two laws, and
  ``tests/fixtures/need_id_conformance.toml`` has a fourth table, ``[[prefix]]``.

.. _`release:1.2.0`:

1.2.0
-----

:Released: 2026-11-19

The grammar of a need id is new: ``ub_needs_exchange.need_id`` splits an id that holds
``::`` into a namespace and a local id, and names the problem of one that does not split
cleanly, held to a conformance corpus of its own. A draft needs.json, format "2a1", is
read on opt-in (experimental). Two fixes change what a file reads as: a record's legacy
``description`` is its content only when the record has no ``content``, and a 2a1 link
whose condition starts with ``[`` and ends with ``]`` is spelled so that it reads back as
written. Sphinx-Needs 9.3.0 requires this release.

- **The grammar of a need id: ``ub_needs_exchange.need_id``.** An id that holds ``::``
  splits at its last ``::`` into a namespace -- one or more segments, each of ASCII
  letters, ASCII digits, ``_`` and ``-`` -- and a local id:
  ``split_id("nc::m2::REQ_1")`` is ``(("nc", "m2"), "REQ_1")``. An id that does not split
  cleanly (``nc::``, ``a::::b``, ``std::vector<int>::size``) is a plain id, and
  ``id_problem`` names its class (``empty_local``, ``empty_segment``,
  ``segment_character``); splitting never raises. ``join_id``, ``parse_namespace``,
  ``format_namespace`` and ``is_segment`` complete it, all re-exported from the package.
  The package splits no record's id on its own: the reader is unchanged.
  ``design/exchange-contract.md`` §14 states the grammar, and
  ``tests/fixtures/need_id_conformance.toml`` is its corpus, which ubCode vendors.
- **A draft "2a1" link object whose condition starts with ``[`` and ends with ``]`` is
  spelled with one space after its opening brackets** (``{"id": "B", "condition": "[x]
  == a[0]"}`` is ``B[[ [x] == a[0]]]``, was ``B[[[x] == a[0]]]``), as sphinx-needs'
  format-1 writer now spells it, so that sphinx-needs reads it back as the same link
  (changed output). ``design/v2a1-draft.md`` §5.1 drops the condition exception to the
  round trip, and the draft's corpus has two new cases,
  ``a-condition-that-ends-in-a-bracket`` and
  ``a-condition-that-starts-and-ends-with-a-bracket-is-spelled-with-a-space``.
- **A record's legacy ``description`` is its ``content`` only when the record has no
  ``content``** -- after the schema defaults are merged --, as in every needs.json
  sphinx-needs wrote before 4.0; a record with a ``content``, even an empty one, keeps its
  ``description`` (changed output). 1.1.0 renamed it over any ``content`` Python treats as
  false (``""``, ``null``, ``0``, ``false``, ``[]``, ``{}``), so a field or link type named
  ``description`` on a need without content -- which every writer since 4.0 writes as
  ``"content": ""``, or as the schema's ``content`` default, unless told to leave
  ``content`` out -- was read as the content. A file written with ``content`` left out
  reads as a pre-4.0 one, as it did.
- **Read without the defaults, the same.** ``Version.records(apply_schema_defaults=False)``
  maps a record as the merge would: where the schema gives ``content`` a default, no
  record's ``description`` is renamed, where 1.1.0 renamed it on the unmerged record.
- **The contract and the corpus.** ``design/exchange-contract.md`` §6.3 and §9 say so. Of
  the corpus, the seven cases whose ``content`` is present but falsy keep the
  ``description`` and are renamed to say so (``description-fills-an-empty-content`` is
  now ``an-empty-content-keeps-the-description``,
  ``a-content-default-does-not-hide-the-description`` is now
  ``a-content-default-keeps-the-description``, and so on), and
  ``a-modern-record-keeps-an-empty-content-and-its-description`` is new.
- **A draft needs.json, format "2a1", is read on opt-in (experimental).**
  ``Document.select_version(requested, drafts=("2a1",))`` reads a ``"2a1"`` file -- one
  version, no ``versions`` or ``current_version``, a ``project`` object whose ``version``
  names it, and ``needs`` an array of records of an ``id``, a ``type``, ``fields``,
  ``links``, ``content`` and ``source`` --; without ``drafts`` such a file is refused
  exactly as before. Each record is handed out in the shape a format-1 record has (its
  fields, its links spelled as format 1 writes them, ``content``, ``doctype``, ``parts``,
  and ``docname``, ``sections``, ``section_name`` and ``signature`` from the page it is
  placed on), and its hops, as the
  file has them, in the new ``Record.source`` (``()`` for a format-1 record);
  ``Version.format_version`` says which format a version is read as. The draft's
  findings and refusals have codes of their own (``draft_has_versions``,
  ``duplicate_id`` -- the first record of an id is read --, ``field_reserved``,
  ``hop_invalid``, ...), and
  an unknown name in ``drafts`` is a ``ValueError``. The draft may change or be removed
  in any release while it is one, and a file of it is readable only by the release that
  wrote it. Its contract is ``design/v2a1-draft.md`` and its corpus
  ``tests/fixtures/needs_json_2a1_draft_conformance.toml``, both this package's own: the
  shared corpus, which ubCode vendors, is unchanged, and still refuses ``"2a1"``.

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
