.. _changelog:

Changelog
=========

Unreleased
----------

The first release, as **1.0.0**: the shared reader for ``ubproject.toml`` across the
sphinx-needs family and ubCode. It has no consumers yet -- sphinx-test-reports,
sphinx-needs, sphinx-mounts and sphinx-codelinks adopt it one release each, after this one
is published.

- **Find, load, select, anchor.** ``find_project_config`` walks up from a directory to the
  repository root (outside a repository, to the distribution root) and returns the first
  ``ubproject.toml``; ``load_toml`` reads it, reporting every failure as an
  ``UbprojectError`` naming the file; ``select_table`` picks a dotted table such as
  ``tool.acme.needs``; ``anchor`` joins a relative path onto the file's directory and
  never resolves it.
- **The** ``[variants]`` **table.** ``read_variants`` reads ``[variants] data`` (an inline
  table) and ``[variants] data_file`` (one path), falling back to the legacy
  ``[needs] variant_data`` and ``[needs] variant_data_file``. The location is chosen whole:
  when both are set, ``[variants]`` is read and each ignored ``[needs]`` key is reported.
  Findings are returned as ``Diagnostic`` values -- ``variant_data_location``,
  ``variant_data_legacy_location`` and ``variants_unknown_key`` -- and never logged, so
  each consumer decides what they are worth.
- **One copy of the variant-data merge.** ``validate_variant_data``,
  ``load_variant_data_file``, ``deep_merge`` and ``resolve_variant_data``, replacing the
  copies in sphinx-needs and sphinx-mounts. ``resolve_variant_data`` always returns a new
  mapping, and every error names the dotted path and the rule it broke.
- **Standard library only.** No Sphinx, no docutils and no sibling distribution, so tools
  that run without the documentation toolchain can use it.
- **A conformance corpus**, ``tests/fixtures/ubproject_reading_conformance.toml``: the
  executable half of the reading contract, held canonically here and vendored by ubCode.
