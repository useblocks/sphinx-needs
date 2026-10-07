.. _changelog:

Changelog
=========

Unreleased
----------

Fixed
.....

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
