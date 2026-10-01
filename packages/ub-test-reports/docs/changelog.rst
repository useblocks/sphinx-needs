.. _changelog:

Changelog
=========

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
