.. _changelog:

Changelog
=========

.. _`release:1.1.0`:

1.1.0
-----

:Released: 2026-09-30

One addition, for the consumer that is next in line. sphinx-needs is about to read its
variant data through this package, and a sphinx-needs project may keep its configuration
under a prefix (``needs_from_toml_table``); such a project now has a place for
``[variants]`` too. ubCode is unaffected -- it has no prefix -- and the conformance corpus
gains three cases (57 to 60), all Python-only, so a vendored copy is due a refresh but
its runner skips them.

- **``[variants]`` under a consumer's prefix.** ``read_variants`` takes
  ``variants_table``, the path of ``[variants]`` as ``needs_table`` is the path of
  ``[needs]``, so a consumer that nests its configuration (``[tool.acme.needs]`` in a
  ``pyproject.toml``, where a top-level ``[variants]`` is not allowed) reads
  ``[tool.acme.variants]`` beside it; diagnostic paths and messages name the table there.
  The default, and every existing call, is unchanged.

.. _`release:1.0.0`:

1.0.0
-----

:Released: 2026-09-30

The first release, as **1.0.0**: the shared reader for ``ubproject.toml`` across the
sphinx-needs family and ubCode. It has no consumers yet -- sphinx-test-reports,
sphinx-needs, sphinx-mounts and sphinx-codelinks will adopt it one release each, after this one
is published.

- **Find, load, select, anchor.** ``find_project_config`` walks up from a directory to the
  repository root (outside a repository, to the distribution root) and returns the first
  ``ubproject.toml``; ``load_toml`` reads it, reporting every failure as a
  ``ProjectConfigError`` naming the file; ``select_table`` picks a dotted table such as
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
  ``load_variant_data_file``, ``deep_merge`` and ``resolve_variant_data``, to replace the
  copies in sphinx-needs and sphinx-mounts once they adopt it. ``resolve_variant_data`` always returns a new
  mapping; every value error names the dotted path and every file error names the file,
  each with the rule it broke.
- **Standard library only.** No Sphinx, no docutils and no sibling distribution, so tools
  that run without the documentation toolchain can use it.
- **A conformance corpus**, ``tests/fixtures/ubproject_reading_conformance.toml``: the
  executable half of the reading contract, held canonically here, which ubCode is to
  vendor.
