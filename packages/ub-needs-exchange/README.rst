ub-needs-exchange
=================

A library for the sphinx-needs family, which the extensions pull in -- not a Sphinx
extension, and nothing to add to ``conf.py``.

It is the record of the **needs.json** exchange format: the file sphinx-needs' ``needs``
builder writes, its ``needimport`` directive and ``needs_external_needs`` option read, and
ubCode both writes and reads. It holds the part of that format more than one tool reads,
so that it is read one way:

- **the envelope** -- the ``project``, the ``current_version``, the ``versions``, and a
  ``format_version``;
- **selecting a version** -- the one asked for, or the file's current one;
- **the records** -- each keyed by its id, with the legacy ``description`` read as
  ``content`` and the version's ``needs_schema`` defaults merged under it.

Standard library only: no Sphinx, no docutils, no sibling distribution. A converter or a
build action that runs without the documentation toolchain can use it.

Reading a file
--------------

.. code-block:: python

   from ub_needs_exchange import ExchangeError, load

   try:
       version = load("needs.json").select_version(None)  # or a version's name
   except ExchangeError as err:
       err.code       # what is wrong, e.g. "version_not_found"
       err.message    # for a person
   else:
       records = version.records()
       for record in records:
           record.key        # the need's id
           record.fields     # its fields, schema defaults merged under them
       version.diagnostics   # findings about the version -- report them, or not
       [d for r in records for d in r.diagnostics]   # findings about each record

Every refusal is an ``ExchangeError`` whose ``code`` names the rule that was broken; every
finding is a ``Diagnostic`` with a ``code``, the ``path`` of what was found in the file,
and a ``message``.

Consumers decide the policy
---------------------------

This package decides nothing a consumer has reason to decide differently: which fields a
project defines and which of a record's keys it takes, the ids it accepts, the prefix it
adds, how a record becomes a need, and whether a finding deserves a warning are each
tool's own.

The contract
------------

``design/exchange-contract.md`` is the normative specification, and
``tests/fixtures/needs_json_reading_conformance.toml`` is its executable half: a corpus of
needs.json files and expected results that this package's suite runs, and that ubCode is
to vendor and run against its own readers.
