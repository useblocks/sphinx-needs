.. _changelog:

Changelog
=========

Unreleased
----------

Fixed
.....

- 🐛 Multiple properties mapped onto the same link field in ``link_properties`` now merge their values
  instead of overwriting each other, preserving mapping order and deduplicating IDs (:issue:`2058`).
- 🐛 The JSON parser now reads report files as UTF-8 explicitly, so non-ASCII test names and
  messages do not depend on the process locale on Windows.

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
