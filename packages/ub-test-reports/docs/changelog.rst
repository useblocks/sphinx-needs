.. _changelog:

Changelog
=========

Unreleased
----------

Fixed
.....

- 🐛 The ``test-reports build needs`` converter keeps a test case's message, text and
  captured output inside the literal blocks it writes into the ``needs.json``, whatever
  line-break characters they hold (a carriage return, NEL, LINE SEPARATOR, …); text after
  such a character used to be read as reStructuredText by a build importing the file.
  `#2179 <https://github.com/useblocks/sphinx-needs/pull/2179>`__

- 🐛 The JSON parser now reads report files as UTF-8 explicitly, so non-ASCII test names and
  messages do not depend on the process locale on Windows.

- 🐛 Two ``--link-property`` flags (or two ``[test_reports.build.needs] link_properties``
  entries) that map different XML properties onto the SAME link field now merge (as the
  build's ``tr_property_link_types`` does): the converter writes the values of every mapped
  property, in mapping order, each id once at its first appearance. Before, the last
  mapped property overwrote the field, so a case carrying only an earlier one lost its
  links. As part of the same rule, a value repeated within one property is now written
  once (sphinx-needs sorts and de-duplicates every link list it reads, so an imported need
  shows the same set either way). The field is still written, empty, for a case carrying
  none of the mapped properties.
  `#2058 <https://github.com/useblocks/sphinx-needs/issues/2058>`__,
  `#2119 <https://github.com/useblocks/sphinx-needs/pull/2119>`__

- 🐛 The JUnit parser keeps the ``<testcase>`` children of a ``<testsuite>`` that also holds
  nested ``<testsuite>`` elements. It dropped them, so ``test-reports build needs`` never
  exported those cases; **a report of that shape now gains needs**, one per such case, with
  ``suite`` set to the name of the suite the case is directly in. Reports whose suites hold
  either cases or nested suites, never both, convert exactly as before.
  `#2050 <https://github.com/useblocks/sphinx-needs/issues/2050>`__,
  `#2149 <https://github.com/useblocks/sphinx-needs/pull/2149>`__

- 🐛 The JUnit parser raises one typed error, ``ReportReadError`` (an ``Exception``, in
  ``ub_test_reports.errors`` and importable from ``ub_test_reports.junitparser``), for a
  report it cannot read: malformed XML (the message is the path, lxml's line and column,
  then lxml's sentence), bytes that are not valid in the report's encoding, and a numeric
  attribute that is not a number (``<testsuite> attribute tests="abc" is not an integer``,
  ``<testcase> attribute time="1,5" is not a number`` -- the report is refused as a whole).
  These escaped as lxml's ``XMLSyntaxError`` / ``OSError`` and a bare ``ValueError``. The
  ``test-reports`` converter still exits 1 on such a report; its ``error:`` line now reads
  ``error: <path> (line 1, column 34): Opening and ending tag mismatch: testcase line 1 and
  testsuite`` for malformed XML (it was lxml's sentence with lxml's ``(<file>, line 1)``
  suffix), the path and the position each said once.
  `#2052 <https://github.com/useblocks/sphinx-needs/issues/2052>`__,
  `#2156 <https://github.com/useblocks/sphinx-needs/pull/2156>`__

- 🐛 The JSON parser raises the same ``ReportReadError`` for a report that is not valid
  JSON (``<path> (line 1, column 11): Expecting value``), not UTF-8 (``<path> is not valid
  UTF-8 (invalid continuation byte at byte 14)``), whose top level is not a list of test
  suites (``<path>: the JSON report is not a list of test suites (got an object)``), or one
  of whose suites is not an object (``<path>: test suite 0 is not an object (got a
  number)``). The first two escaped as ``json.JSONDecodeError`` / ``UnicodeDecodeError``;
  the other two were walked as if they were suites, every field its default. A JSON report
  saved with a UTF-8 byte-order mark is read now (it was refused, ``Unexpected UTF-8
  BOM``), as ``test-env`` reads its file. The ``test-reports`` converter reads JUnit XML
  only and is unchanged by this.
  `#2052 <https://github.com/useblocks/sphinx-needs/issues/2052>`__,
  `#2156 <https://github.com/useblocks/sphinx-needs/pull/2156>`__

- 🐛 An empty ``<testsuites/>`` is an empty report: the parser returns no suites, where it
  raised ``AttributeError: no such child: testsuite``, and ``test-reports build needs``
  writes an empty ``needs.json`` with its "no test cases found" warning and exits 0, where
  it exited 1.
  `#2052 <https://github.com/useblocks/sphinx-needs/issues/2052>`__,
  `#2156 <https://github.com/useblocks/sphinx-needs/pull/2156>`__

- 🐛 ``JUnitFileMissing`` and ``JsonFileMissing`` derive from ``Exception``, not
  ``BaseException``, so a caller's ``except Exception`` catches a missing report. The
  converter checks the path itself first and prints ``error: no such file: <path>`` as
  before.
  `#2052 <https://github.com/useblocks/sphinx-needs/issues/2052>`__,
  `#2156 <https://github.com/useblocks/sphinx-needs/pull/2156>`__

.. _`release:1.0.0`:

1.0.0
-----

:Released: 2026-10-01

The first release of ub-test-reports: the Sphinx-free half of sphinx-test-reports as a distribution
of its own, so that a build action or a test run can install the ``test-reports`` converter and the
pytest plugin without the documentation toolchain. sphinx-test-reports 3.0.0 depends on it.

- 1.0.0 is the first release: the converter, the pytest plugin, the parsers, the result
  vocabulary, the deterministic IDs and the ``[test_reports]`` model, moved out of
  sphinx-test-reports 2.0.0 unchanged; the plugin is ``-p ub_test_reports.pytest_plugin``,
  and its warning prefix and pluggy registration name now say ``ub_test_reports`` (the
  extension's changelog lists both); its wire names are unchanged.
