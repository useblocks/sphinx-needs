ub-test-reports
===============

A tool for the sphinx-needs family -- not a Sphinx extension, and nothing to add to
``conf.py``.

It turns test results into needs without running Sphinx, and holds everything about test
reports that does not need a documentation build:

- **the parsers** -- JUnit XML (pytest, googletest, ctest, nose and friends) and
  tox-envreport style JSON;
- **the result vocabulary** -- one spelling for every outcome, whichever report it came
  from;
- **deterministic case IDs** -- the same case gets the same need ID in every run;
- **the** ``[test_reports]`` **model** of ``ubproject.toml``, read through ``ub-project``;
- **the converter** -- the ``test-reports build needs`` command, which writes a
  ``needs.json`` that sphinx-needs can import;
- **the pytest plugin** -- ``-p ub_test_reports.pytest_plugin``, which shapes the JUnit XML
  pytest writes (source locations, per-case properties for traceability).

Install the converter with::

    pip install ub-test-reports

and the pytest plugin with::

    pip install "ub-test-reports[pytest]"

To show the same reports inside a Sphinx documentation build, install the extension,
``sphinx-test-reports``, which depends on this package.

Documentation: the "Without Sphinx" section of https://sphinx-test-reports.readthedocs.io/en/latest/
