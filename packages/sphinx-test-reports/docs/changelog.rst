:hide-navigation:

Changelog
=========

Unreleased
----------
:Released: under development

.. _`release:1.4.0`:

1.4.0
-----
:Released: 16.06.2026

This release adds Sphinx-Needs 8 support and the ability to map JUnit XML
``<properties>`` onto Sphinx-Needs fields and links. It also registers every
field that Sphinx-Test-Reports adds with a typed schema, so unset fields no
longer trigger false-positive ``unevaluatedProperties: false`` schema-validation
warnings, and it fixes JUnit ``<error>`` test cases being reported as passed.

* Feature: Map JUnit XML ``<properties>`` to Sphinx-Needs fields and links via
  the new ``tr_property_link_types`` and ``tr_extra_options`` options.
  `#135 <https://github.com/useblocks/sphinx-test-reports/pull/135>`_
* Improvement: Support Sphinx-Needs 8 by registering fields through the new
  ``add_field`` API, falling back to ``add_extra_option`` on older versions.
  `#133 <https://github.com/useblocks/sphinx-test-reports/pull/133>`_
* Bugfix: Register ``file``, ``suite``, ``case``, ``case_name``,
  ``case_parameter`` and ``classname`` with a typed (string) schema so they
  default to an unset/``None`` value and are stripped before schema validation.
  Previously they were registered untyped and defaulted to ``""``, which caused
  false-positive ``Unevaluated properties are not allowed`` warnings on needs
  that did not set them when a schema used ``unevaluatedProperties: false``.
  `#133 <https://github.com/useblocks/sphinx-test-reports/pull/133>`_
* Bugfix: Handle the JUnit ``<error>`` result state in ``parse_testcase()``;
  ``<error>`` test cases were previously misclassified as ``passed``.
  `#134 <https://github.com/useblocks/sphinx-test-reports/pull/134>`_
* Testing: Run the test suite against Sphinx-Needs 6.3.0.
  `#130 <https://github.com/useblocks/sphinx-test-reports/pull/130>`_
* Testing: Add a regression test that a strict schema ignores unpopulated
  Sphinx-Test-Reports fields.
  `#137 <https://github.com/useblocks/sphinx-test-reports/pull/137>`_
* Docs: Clarify the Sphinx-Needs type names (``testfile``, ``testsuite``,
  ``testcase``) versus the hyphenated directives.
  `#136 <https://github.com/useblocks/sphinx-test-reports/pull/136>`_
* Docs: Note that numeric ``cases`` filtering requires Sphinx-Needs >= 6.
  `#139 <https://github.com/useblocks/sphinx-test-reports/pull/139>`_

.. _`release:1.3.2`:

1.3.2
-----
:Released: 13.11.2025

This release improves Sphinx-Test-Reports compatibility with Sphinx and
fixes some Sphinx related deprecation warnings.

* Bugfix: Fix deprecation warnings with Sphinx 8.
  `#128 <https://github.com/useblocks/sphinx-test-reports/pull/128>`_

.. _`release:1.3.1`:

1.3.1
-----
:Released: 02.10.2025
:Full Changelog: `v1.3.0...v1.3.1 <https://github.com/useblocks/sphinx-test-reports/compare/1.3.0...ac4d771777b0af46919acf31f7cd34178d0b46d5>`__

* Support Sphinx-Needs 6 schema validation
  `#122 <https://github.com/useblocks/sphinx-test-reports/pull/122>`_

1.3.0
-----
:Released: 28.09.2025

This release makes Sphinx-Test-Reports compatible with Sphinx-Needs 5.1 and
introduces several maintenance improvements.

* Improvement: Support for Sphinx-Needs 5.1.
  `#119 <https://github.com/useblocks/sphinx-test-reports/pull/119>`_
* Bugfix: Fix plantuml on RTD.
  `#115 <https://github.com/useblocks/sphinx-test-reports/pull/115>`_
* Maintenance: Removed py38 from classifiers.
  `#116 <https://github.com/useblocks/sphinx-test-reports/pull/116>`_
* Maintenance: Activate mypy.
  `#113 <https://github.com/useblocks/sphinx-test-reports/pull/113>`_
* Maintenance: Remove baumpfleger.
  `#112 <https://github.com/useblocks/sphinx-test-reports/pull/112>`_
* Maintenance: Clean makefile.
  `#111 <https://github.com/useblocks/sphinx-test-reports/pull/111>`_
* Maintenance: Use flit.
  `#110 <https://github.com/useblocks/sphinx-test-reports/pull/110>`_
* Maintenance: Added all_good job.
  `#109 <https://github.com/useblocks/sphinx-test-reports/pull/109>`_
* Maintenance: Add standard hooks.
  `#106 <https://github.com/useblocks/sphinx-test-reports/pull/106>`_
* Maintenance: Add yamlfmt.
  `#105 <https://github.com/useblocks/sphinx-test-reports/pull/105>`_
* Maintenance: Introduce ruff.
  `#104 <https://github.com/useblocks/sphinx-test-reports/pull/104>`_
* Maintenance: Add taplo pre-commit.
  `#103 <https://github.com/useblocks/sphinx-test-reports/pull/103>`_


1.2.0
-----
:Released: 27.03.2025

* Improvement: Introducing :ref:`tr_extra_options` for setting custom options in all derrived
  test-cases from ``test-file`` and co.
  `#96 <https://github.com/useblocks/sphinx-test-reports/issues/96>`_
* Improvement: JSON-Parser allows to set custom options in test-cases, like ``status`` or even ``id``.
  See :ref:`tr_json_mapping` for examples. `#99 <https://github.com/useblocks/sphinx-test-reports/issues/99>`_

1.1.0
-----
:Released: 17.01.2025

* Bugfix: Compatible with Sphinx-Needs >= 4.0.
* Bugfix: Path handling is os independent.
* Improvement: Referenced target_option in `tr_link` can contain a comma separated list.
* Improvement: The new :ref:`json_parser` is introduced.
* Improvement: Template file encoding could be configured. See :ref:`tr_import_encoding`.
  `#60 <https://github.com/useblocks/sphinx-test-reports/issues/60>`_
*  Improvement: Supporting JSON files containing test results: :ref:`json_parser`.
*  Improvement: Implemented :ref:`tr_json_mapping` config option for JSON mapping.

1.0.2
-----
:Released: 21.12.2022 🎄

* Bugfix: Links in `test-suite` and co. do not raise error.
  `#51 <https://github.com/useblocks/sphinx-test-reports/issues/51>`_
* Improvement: Allows empty text and message fields, which allows integration of ctest junit files
  `#49 <https://github.com/useblocks/sphinx-test-reports/issues/49>`_

1.0.1
-----
:Released: 04.11.2022

* Improvement: ID length can be configured to avoid conflicts. See :ref:`tr_suite_id_length` and :ref:`tr_case_id_length`.
  `#45 <https://github.com/useblocks/sphinx-test-reports/issues/45>`_
* Bugfix: Multiple testsuites get documented correctly.
  `#40 <https://github.com/useblocks/sphinx-test-reports/issues/40>`_

1.0.0
-----
:Released: 26.09.2022

* Improvement: Supporting `Sphinx-Needs <https://sphinx-needs.readthedocs.io/en/latest/>`__ ``>= 1.01`` only.
* Improvement: Migrated nosetests to pytest.

0.3.7
-----
:Released: 09.06.2022

* Improvement: Nested test suites are supported (like in Robot Framework 5.0)
  `#30 <https://github.com/useblocks/sphinx-test-reports/issues/30>`_

0.3.6
-----
:Released: 12.11.2021

* Improvement: Added support for parallel modes.
  `#20 <https://github.com/useblocks/sphinx-test-reports/issues/20>`_
* Improvement: Support getting skipped tests.
  `#18 <https://github.com/useblocks/sphinx-test-reports/issues/18>`_

0.3.5
-----
:Released: 18.06.2021

* Bugfix: Minor bugfixes

0.3.4
-----
:Released: 30.04.2021 (Recalled, contains major bugs)

* Bugfix: Removed Sphinx 4 deprecation warnings

0.3.3
-----
* Improvement: Added :ref:`test-report` directive.
* Improvement: Introduces :ref:`tr_file`, :ref:`tr_suite` and :ref:`tr_case` options to customize names.
* Improvement: Not found files will throw warning instead of exception so that build goes on.
* Improvement: Provides css_classes ``tr_passed``, ``tr_failure``, ``tr_skipped`` to colorize needs and their rows in tables.
* Bugfix: Stabilised extension initialisation phase.


0.3.1
-----
* Improvement: Support of case and table colors based on ``result``.
* Bugfix: Hash-Id for autogenerated test-cases size was increased.


0.3.0
-----
* Improvement: Using `sphinx-needs <https://sphinx-needs.readthedocs.io/en/latest/>`_ for data representation
  and filtering.
* Improvement: New directives :ref:`test-file`, :ref:`test-suite` and :ref:`test-case`.
* Improvement: New possibilities to :ref:`filter test data <filter>`.
* Improvement: Much better documentation.

0.2.1
-----
* Skipped support für Python < 3.5.
* Bugfix: junit-file-format of pytest > 5.1.0 supported. `#8 <https://github.com/useblocks/sphinx-test-reports/issues/8>`_


0.2.0
-----

**Initial start for the changelog**

* Improvement: added directive ``:test-env:`` to take tox-envreport.json as input and create a table.
