.. _changelog:

Changelog
=========

Unreleased
----------

New and Improved
................

- ✨ ``ub_test_reports.identity.case_name_and_parameter(case)`` gives a parsed test case's
  ``case_name`` and ``case_parameter`` by one rule: the parameter in the name's ``[…]``
  (pytest's ``test_x[3]``), else Google Test's ``value_param``, else its ``type_param``,
  and both as ``"<type_param>, <value_param>"``
  (`#2390 <https://github.com/useblocks/sphinx-needs/issues/2390>`__). The converter and
  sphinx-test-reports' directives share it. ``split_case_name`` is unchanged.

Changed
.......

- 👌 ``ub_test_reports.fields`` says which kinds of need carry each field: ``need_kinds(name,
  role)`` over ``NEED_KINDS`` (``file``, ``suite``, ``case``), with the new ``FILE_NEED_FIELDS``
  and ``SUITE_NEED_FIELDS`` beside ``CASE_FIELDS`` -- the tables ubCode's ``ubc_test_reports``
  has -- so sphinx-test-reports declares each field on the need types that carry it
  (`#2372 <https://github.com/useblocks/sphinx-needs/issues/2372>`__). The converter's output is
  unchanged by it: it writes test cases, and its ``needs_schema`` declares the test-case fields.

- 👌 The ``test-reports build needs`` converter writes ``null`` in ``case_file``, ``case_line``
  (or the fields ``source_file_option`` and ``source_line_option`` name) and ``case_parameter``
  where the report gives no source file, no line or no parameter, where it wrote ``""``
  (changed output; `#2372 <https://github.com/useblocks/sphinx-needs/issues/2372>`__), as its
  ``needs_schema`` already declared them nullable. **API change:** ``split_case_name`` now
  returns ``tuple[str, str | None]``: ``None`` for the parameter of a name pytest did not
  parameterise (``""`` stays the parameter of an empty ``[]``), so a caller that concatenated
  or compared the parameter as a string handles ``None``. A filter written ``case_line == ''`` no longer matches such a case: write
  ``case_line is None`` (or ``not case_line``) instead. sphinx-test-reports' directives write
  the same.

Fixed
.....

- 🐛 The ``test-reports build needs`` converter writes a Google Test case's parameter in
  ``case_parameter``, where it wrote no value for any Google Test case
  (`#2390 <https://github.com/useblocks/sphinx-needs/issues/2390>`__): a value-parameterised
  case's ``value_param`` (``1``, ``(1, 2)``), a typed case's ``type_param`` (``int``), and
  for a test registered with both through ``testing::RegisterTest``, the type first
  (``int, 42``), each verbatim. Google Test writes the parameter beside the name, never in
  it. ``case_name`` keeps the name as given (``Value/0``), and no id moves.

- 🐛 The documented ``filterwarnings`` line that silences the pytest plugin's start-up notice,
  ``ignore::ub_test_reports.pytest_plugin.TestReportsConfigWarning``, crashed pytest 9.2 and
  later at start-up with a ``PytestAssertRewriteWarning`` traceback ("Module already imported
  so cannot be rewritten") when the plugin is loaded with ``-p`` and warnings are errors, and
  added that warning to every run's summary when they are not.
  pytest 9.2 resolves the filter -- importing the plugin -- before it loads the ``-p``
  plugins. The plugin module now opts out of pytest's assertion rewriting (it has no
  ``assert`` to rewrite), so the line works on every pytest again; nothing changes in your
  configuration.

.. _`release:1.1.0`:

1.1.0
-----

:Released: 2026-10-14

A bug-fix release for the converter and the parsers. A report the parsers cannot read is
one typed ``ReportReadError`` naming the file and the position, where lxml's and the JSON
decoder's own exceptions escaped, so a caller's ``except ValueError`` or ``SyntaxError`` no
longer catches it (`#2156 <https://github.com/useblocks/sphinx-needs/pull/2156>`__);
cases beside nested test suites are no longer dropped
(`#2149 <https://github.com/useblocks/sphinx-needs/pull/2149>`__); two link properties mapped
onto one field merge (`#2119 <https://github.com/useblocks/sphinx-needs/pull/2119>`__); and
report text stays inside its literal blocks whatever line breaks it holds
(`#2179 <https://github.com/useblocks/sphinx-needs/pull/2179>`__). sphinx-test-reports 3.0.0
requires it.

Fixed
.....

- 🐛 The ``test-reports build needs`` converter keeps a test case's message, text and
  captured output inside the literal blocks it writes into the ``needs.json``, whatever
  line-break characters they hold (a carriage return, NEL, LINE SEPARATOR, …); text after
  such a character used to be read as reStructuredText by a build importing the file.
  `#2179 <https://github.com/useblocks/sphinx-needs/pull/2179>`__

- 🐛 The JSON parser now reads report files as UTF-8 explicitly, so non-ASCII test names and
  messages do not depend on the process locale on Windows.
  `#2024 <https://github.com/useblocks/sphinx-needs/pull/2024>`__

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
