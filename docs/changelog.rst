.. _ubCode: https://ubcode.useblocks.com/

.. _changelog:

Changelog
=========

6.0.0
-----

:Released: 28.09.2025
:Full Changelog: `v5.1.0...v6.0.0 <https://github.com/useblocks/sphinx-needs/compare/5.1.0...fc765b4ea6fdf79ad146cf2ce66e084178de3a9f>`__

This release introduces strong typing for extra option fields to the Sphinx-Needs codebase.
This affects needs read from RST sources (or others like .md), but also imported/exported needs
of needs.json files.

The default type for extra options is still ``string``, so existing configuration should work
as before. Type errors are detected early once each need is fully resolved, i.e. after
reading in the sources and evaluating :ref:`needs_global_options` (defaults),
:ref:`needextend`, :ref:`variants <needs_variant_support>` and :ref:`dynamic_functions`.
Errors in the typing system lead to needs not being created.

The release also introduces a new :ref:`schema_validation` system that integrates
into the strong typing. It is JSON schema compliant in large parts with custom extensions
to support network validation.

The core of Sphinx-Needs had to be refactored in large parts to enable these changes.
The following are the main user-facing changes:

- ♻️ Allow for typed ``needs_extra_options`` fields :pr:`1516`

  The ``needs_extra_options`` configuration option was extended to support schema information.
  The field ``schema.type`` globally sets the type for the field. Users can select between
  ``string``, ``number`` (float), ``integer``, ``boolean`` and ``array``. For the ``array`` type
  another keyword ``schema.items.type`` defines the list items type.

  Examples in TOML configuration:

  .. code-block:: toml

     [[needs.extra_options]]
     name = "priority"
     description = "Priority level, 1-5 where 1 is highest and 5 is lowest"
     schema.type = "integer"
     schema.minimum = 1
     schema.maximum = 5

     [[needs.extra_options]]
     name = "asil"
     description = "Automotive Safety Integrity Level"
     schema.type = "string"
     schema.enum = ["QM", "A", "B", "C", "D"]

  **Key Changes:**

  - Strong typing for ``needs_extra_options`` with JSON schema validation
  - Delayed resolution for dynamic functions, needextend, defaults, and variants
  - Automatic type coercion from string inputs (directive options) to proper types
  - Missing fields are set to ``None`` (null in JSON)
  - needs.json import/export with type validation and coercion; empty ``""`` field values
    of existing needs.json files of type ``integer`` are coerced to ``0``, and for
    type ``number`` to ``0.0`` for backwards compatibility. Empty strings for ``boolean``
    fields are coerced to ``True`` as this is often used as a flag.
  - Integration with schema validation system. The same fields for :ref:`supported_data_types`
    can be set in the definition, so they are set globally for that field.

  The implementation strives to be as backwards compatible as possible. See below for details.

- ✨ Schema validation :pr:`1467`

  The PR adds a fast, declarative and versatile JSON schema based need validation.
  The schema is defined in the :ref:`needs_schema_definitions` configuration option or
  as JSON format passed via :ref:`needs_schema_definitions_from_json`.

  **Key Features:**

  - JSON Schema standard compliance using ``$defs`` and ``$ref`` for reusable sub-schemas
  - Fully typed implementation with runtime validation of schema definitions
  - Auto-injection of default string type when not specified
  - Select mechanism, comparable to database queries to select need nodes for validation.
  - Root ``validate`` key with ``local`` and ``network`` sub-sections for validation types.
    The split enables IDE extensions such as `ubCode`_ to validate-on-type for need-local
    changes and also run network validation once the index is fully built.
  - Debug mechanism using :ref:`needs_schema_debug_active` to check why validations pass or fail.
    4 files are written per validation: original need, reduced need, applied schema and
    a result file with user and validation message. File naming pattern is
    ``<need_id>__<schema_path>__<validation_rule>.<json|txt>``. Nested graph-validations are also
    dumped.
  - String regex pattern constraints with cross-engine compatibility
  - Semantic equivalence to JSON Schema spec for array ``items``, ``minItems``, ``maxItems``,
    ``contains``, ``minContains``, and ``maxContains``

  The new validation can replace :ref:`needs_warnings`, :ref:`needs_constraints`,
  :ref:`needs_id_regex`, :ref:`needs_statuses`, and :ref:`needs_tags` in the future.

  The implementation of the new strong typing and schema validation into `ubCode`_ is on the
  immediate roadmap.

- 👌 Write schema violations into a JSON file :pr:`1503`

  Schema validation violations are now exported to a JSON file (``schema_violations.json``)
  for external tooling integration and automated quality assurance workflows. This enables
  CI/CD systems and external analysis tools to programmatically process validation results.

- Always generate schema violations.json report file :pr:`1511`

**These PRs were part of the internal changes:**

- 🧪 Move to snapshot testing for test_schema :pr:`1519`
- 🔧 Add ``VariantFunctionParsed`` dataclass :pr:`1515`
- 🔧 Add ``DynamicFunctionParsed`` dataclass :pr:`1514`
- ♻️ Auto-compute certain need fields :pr:`1496`
- ♻️ Set some core need fields to nullable :pr:`1488`
- 🔧 Split import item filtering to separate function :pr:`1484`
- ♻️ Lazily assess directive options :pr:`1482`
- 🧪 Improve test for need parts :pr:`1507`
- 👌 Improve need part processing :pr:`1469`
- 🔧 Centralise allowed variant core need fields :pr:`1424`
- ✨ Add ``is_import`` need field :pr:`1429`

  New field to identify needs that were imported from external sources.

**Breaking Changes**

- :ref:`Variants <needs_variant_support>` have to be wrapped with ``<< >>``. This allows
  for a safer parsing strategy and support for usage in array elements.
- The variant delimiter has changed to only allow ``,``. Formerly also ``;`` was possible.
- 🐛 Fix: disallow need variants for list type fields :pr:`1489`

  Variants no longer supported in list-type fields due to parsing instability.
  This feature might be re-introduced in future.
  The new syntax ``<< >>`` would make this much easier.

- ‼️ remove parsing of deprecated ``needs_global_options`` format :pr:`1517`

  Removes support for the deprecated legacy format of
  ``needs_global_options``. The system now only accepts the dictionary format
  introduced in version 5.1.0. Projects using the old format will receive a warning
  that the configuration is not a ``dict`` and the parsing will be skipped entirely.
  Users must migrate to the new explicit format for global options to continue working.

- ‼️ Improve needs default field application (via needs_global_options) :pr:`1478`

  Previously defaults would be applied to any fields of a need with a "falsy" value,
  e.g. ``None``, ``False``, ``0``, ``""``, ``[]``. This is an issue if the user wants to
  specifically set fields to these values, without them being overridden by defaults.
  Therefore, now defaults are only applied to fields with a missing or None value.

- ‼️ Disallow ``add_extra_option`` overriding an internal field :pr:`1477`

  Needs are stored in a flat dictionary as of now, so they cannot overlap.

- ♻️ Store needs as ``NeedItem`` / ``NeedPartItem``, rather than standard ``dict`` :pr:`1485`

  Replaces standard dictionary storage with specialized ``NeedItem`` and ``NeedPartItem`` classes.
  This allows better encapsulation and control over data mutation.

  This is breaking for any users doing "non-API" modifications or additions to the needs data,
  i.e. directly adding dict items.
  It should not change interactions with standard APIs like ``add_need`` or filter strings.

  These PRs are also related:

  - ♻️ Improve storage of part data on NeedItem :pr:`1509`
  - 🔧 Improve storage of content generation on ``NeedItem`` :pr:`1506`
  - 🔧 Improve storage of constraint results on ``NeedItem`` :pr:`1504`
  - 👌 Capture more information about modifications on ``NeedItem`` :pr:`1502`
  - ♻️ split off ``source`` fields in ``NeedItem`` internal data :pr:`1491`
  - ♻️ split ``NeedItem`` internal data into core, extras, links and backlinks :pr:`1490`

- ⬆️ Drop Python 3.9 :pr:`1468`
- ⬆️ Drop Sphinx<7.4, test against Python 3.13 :pr:`1447`

**Further improvements and fixes**

- 🔧 Improve plantuml check + add tests :pr:`1521`

  PlantUML extension detection now uses ``app.extensions`` for better compatibility with dynamic
  registration. Thanks to @AlexanderLanin for the initial implementation.

- ♻️ Warn for missing needimport files :pr:`1510`

  Missing :ref:`needimport` files now emit warnings instead of throwing exceptions, making
  it possible to ignore the problem for specific use cases.

- 🐛 Avoid leaking auth credentials for ext. need warnings :pr:`1512`
- ♻️ Exclude ``is_need`` / ``is_part`` from ``needs.json`` output :pr:`1505`

  It doesn't make sense to have these, since only needs are written, not parts.
  Also, these fields are "thrown away" when passing in external/import needs.json.

  These fields are only really used during processing, within filter contexts, when filtering
  across both needs and parts.

- 👌 Reset directive option specs at start of build :pr:`1448`

  Internal fix to reset directive options for consistent builds & testing.

- 🐛 Warn on dynamic function with surrounding text :pr:`1426`

  Added warning when dynamic functions are used for a list type with surrounding text
  as the surrounding text will be silently ignored.

- Allow ``collapse`` and ``hide`` in ``needs_global_options`` :pr:`1456`
- 🔧 Allow template global_options :pr:`1454`
- 👌 Re-allow dynamic functions for ``layout`` field :pr:`1423`
- 🔧 Allow pre/post template ``global_options`` :pr:`1428`

**Minor documentation updates**

- 📚 Clarify c.this_doc() for needextend :pr:`1475`
- 📚 Fix needs_extra_links name :pr:`1501`
- 📚 Format configuration.rst :pr:`1473`
- 📚 Fix escape sequences :pr:`1470`

**Infrastructure**

- 🔧 benchmark group non win32 :pr:`1450`
- 🐛 Fix cyclic imports :pr:`1443`
- 🔧 Added yamlfmt pre-commit :pr:`1446`
- 🔧 Use ubuntu-latest in CI :pr:`1439`
- 📚 update tox version to py39 :pr:`1438`

5.1.0
-----

:Released: 06.03.2025
:Full Changelog: `v5.0.0...v5.1.0 <https://github.com/useblocks/sphinx-needs/compare/5.0.0...9ad91a92c68899f750081f6d683473080a567cad>`__

The :ref:`needs_global_options` configuration option has been updated to a new format,
to be more explicit and to allow for future improvements :pr:`1413`.
The old format is currently still supported, but will emit a warning.
Additionally, checks are put in place to ensure that the keys used are from the allowed set (:pr:`1410`).:

- any ``needs_extra_options`` field
- any ``needs_extra_links`` field
- ``status``
- ``layout``
- ``style``
- ``tags``
- ``constraints``

.. code-block:: python
   :caption: Old format

   needs_global_options = {
      "field1": "a",
      "field2": ("a", 'status == "done"'),
      "field3": ("a", 'status == "done"', "b"),
      "field4": [
         ("a", 'status == "done"'),
         ("b", 'status == "ongoing"'),
         ("c", 'status == "other"', "d"),
      ],
   }

.. code-block:: python
   :caption: New format

   needs_global_options = {
      "field1": {"default": "a"},
      "field2": {"predicates": [('status == "done"', "a")]},
      "field3": {
         "predicates": [('status == "done"', "a")],
         "default": "b",
      },
      "field4": {
         "predicates": [
               ('status == "done"', "a"),
               ('status == "ongoing"', "b"),
               ('status == "other"', "c"),
         ],
         "default": "d",
      },
   }

5.0.0
-----

:Released: 18.02.2025
:Full Changelog: `v4.2.0...v5.0.0 <https://github.com/useblocks/sphinx-needs/compare/4.2.0...5.0.0>`__

This release includes a number of changes,
to bring more clarity to the needs data structure and post-processing steps.
In most cases it should not be breaking,
but may be in some corner cases.

- ✨ Add ``c.this_doc()`` check for use in directive ``:filter:`` option :pr:`1393` and :pr:`1405`

  This allows for filtering of needs only in the same document as the
  directive itself, e.g.

  .. code-block:: rst

    .. needextend:: c.this_doc() and status is None
       :status: open

  This works for all common filtered directives, see :ref:`filter_current_page`

- ♻️ Remove ``full_title`` need field and only trim generated titles :pr:`1407`

  The existence of both ``title`` and ``full_title`` is confusing and unnecessary (in most cases these are equal), and so ``full_title`` is removed.

  Trimming (when :ref:`needs_max_title_length` is set) is now only applied to auto-generated titles,
  as per the documentation in :ref:`needs_title_from_content`

- ♻️ Make ``needextend`` argument declarative :pr:`1391`

  The argument for ``needextend`` can refer to either a single need ID or
  filter function.
  Currently, the format cannot be known until all needs have been
  processed, and it is resolved during post-processing.
  This is problematic for (a) user readability, (b) improving processing
  performance and issue feedback

  This PR slightly modifies the argument processing to allow for two
  "explicit" formats:

  - ``<ID>``, if the argument is enclosed in ``<>`` it is always processed as a single ID
  - ``"filter string"``, if the argument is enclosed in ``""`` it is always processed as a filter string

  See :ref:`needextend` for more information.

- ♻️ Remove back link manipulation from ``needextend`` :pr:`1386`

  Back links are computed at the end of the need post-processing, after
  ``needextend`` have been applied.

  Back links should always be in-sync with forward links, therefore it
  doesn't make sense to modify back links in this way.

- ♻️ Do not process dynamic functions on internal need fields :pr:`1387` and :pr:`1406`

  For most "internal" need fields it does not make sense that these would
  be dynamic, and anyway this would fail since their values are not string
  types.

  Dynamic function processing is now skipped, for core fields that
  should not be altered by the user.
  The following fields are allowed to contain dynamic functions:

  - ``status``
  - ``tags``
  - ``style``
  - ``constraints``
  - all ``needs_extra_options``
  - all ``needs_extra_links``
  - all ``needs_global_options``

- ♻️ Remove ``delete`` from internal needs and ``needs.json`` :pr:`1347`

  The ``:delete:`` option on a need directive deletes a need before
  creating/storing it, therefore it is impossible for it to be
  anything other than ``False``.
  Storing the field on a need is misleading, because it suggests that the
  need will be deleted, which is not possible with the current sphinx-needs logic.

- 👌 Add type warnings of extra options in external/import reads :pr:`1389`

  Currently, the value of all extra options is expected to be a string;
  other types are not supported in various aspects of sphinx-needs (such
  as ``needextend``, dynamic functions and filtering), and in-fact are
  already silently converted to strings during the reads.

  The warnings ``needs.mistyped_external_values`` and ``needs.mistyped_import_values`` are added for non-string values,
  for ``needs_external_needs`` and ``needimport`` sources respectively.

- 🔧 Synchronize list splitting behaviour in ``need`` and ``needextend`` directives :pr:`1385`

4.2.0
-----

:Released: 07.01.2025
:Full Changelog: `v4.1.0...v4.2.0 <https://github.com/useblocks/sphinx-needs/compare/4.1.0...4.2.0>`__

- ⬆️ Drop Python 3.8 and Sphinx 6
- ✨ Add :ref:`needs_import_keys` configuration :pr:`1379`
- 👌 Allow ``filter-func`` in ``needpie`` to have multiple dots in the import path :pr:`1350`
- 🐛 Make external paths relative to ``confdir``, not ``srcdir`` :pr:`1378`
- 🔧 Release needs data mutation lock at end of process :pr:`1359`
- 🔧 Add ``lineno`` to default output of ``needs.json`` :pr:`1346`

4.1.0
-----

:Released: 28.10.2024
:Full Changelog: `v4.0.0...v4.1.0 <https://github.com/useblocks/sphinx-needs/compare/4.0.0...4.1.0>`__

New
...

- ✨ Add `needs_from_toml` configuration :pr:`1337`

  Configuration can now be loaded from a TOML file, using the `needs_from_toml` configuration option.
  See :ref:`needs_from_toml` for more information.

- ✨ Allow configuring description of extra options in ``needs_extra_options`` :pr:`1338`

  The ``needs_extra_options`` configuration option now supports dict items with a ``name`` and ``description`` key,
  See :ref:`needs_extra_options` for more information.

Fixes
.....

- 🐛 Fix clickable links to needs in ``needflow``, when using the ``graphviz`` engine :pr:`1339`
- 🐛 Allow sphinx-needs to run without ``sphinxcontrib.plantuml`` installed :pr:`1328`
- 🔧 Remove some internal fields from needs layout :pr:`1330`
- 🔧 Merge defaults into user-defined configuration earlier (to avoid sphinx warnings) :pr:`1341`


4.0.0
-----

:Released: 09.10.2024
:Full Changelog: `v3.0.0...v4.0.0 <https://github.com/useblocks/sphinx-needs/compare/3.0.0...4.0.0>`__

Breaking Changes
................

This commit contains a number of breaking changes:

Improvements to filtering at scale
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

For large projects, the filtering of needs in analytical directives such as :ref:`needtable`, :ref:`needuml`, etc, can be slow due to
requiring an ``O(N)`` scan of all needs to determine which to include.

To address this, the storage of needs has been refactored to allow for pre-indexing of common need keys, such as ``id``, ``status``, ``tags``, etc, after the read/collection phase.
Filter strings such as ``id == "my_id"`` are then pre-processed to take advantage of these indexes and allow for ``O(1)`` filtering of needs, see the :ref:`filter_string_performance` section for more information.

This change has required changes to the internal API and stricter control on the access to and modification of need data, which may affect custom extensions that modified needs data directly:

- Access to internal data from the Sphinx `env` object has been made private
- Needs data during the write phase is exposed with either the read-only :class:`.NeedsView` or :class:`.NeedsAndPartsListView`, depending on the context.
- Access to needs data, during the write phase, can now be achieved via :func:`.get_needs_view`
- Access to mutable needs should generally be avoided outside of the formal means, but for back-compatibility the following :external+sphinx:ref:`Sphinx event callbacks <events>` are now available:

  - ``needs-before-post-processing``: callbacks ``func(app, needs)`` are called just before the needs are post-processed (e.g. processing dynamic functions and back links)
  - ``needs-before-sealing``: callbacks ``func(app, needs)`` just after post-processing, and before the needs are changed to read-only

Additionally, to identify any long running filters,
the :ref:`needs_uml_process_max_time`, :ref:`needs_filter_max_time` and :ref:`needs_debug_filters` configuration options have been added.

Key changes were made in: 

- ♻️ Replace need dicts/lists with views (with fast filtering) in :pr:`1281`
- 🔧 split ``filter_needs`` func by needs type in :pr:`1276`
- 🔧 Make direct access to ``env`` attributes private in :pr:`1310`
- 👌 Move sorting to end of ``process_filters`` in :pr:`1257`
- 🔧 Improve ``process_filters`` function in :pr:`1256`
- 🔧 Improve internal API for needs access in :pr:`1255`
- 👌 Add ``needs_uml_process_max_time`` configuration in :pr:`1314`
- ♻️ Add ``needs_filter_max_time`` / ``needs_debug_filters``, deprecate ``export_id`` in :pr:`1309`

Improved warnings
~~~~~~~~~~~~~~~~~

sphinx-needs is designed to be durable and only except when absolutely necessary.
Any non-fatal issues during the build are logged as Sphinx warnings.
The warnings types have been improved and stabilised to provide more information and context, see :ref:`config-warnings` for more information.

Additionally, the :func:`.add_need` function will now only raise the singular exception :class:`.InvalidNeedException` for all need creation issues.

Key changes were made in:

- 👌 Warn on unknown need keys in external/import sources in :pr:`1316`
- ♻️  Extract ``generate_need`` from ``add_need`` & consolidate warnings in :pr:`1318`

Improved ``needs.json``
~~~~~~~~~~~~~~~~~~~~~~~

A  number of output need fields have been changed, to simplify the output.
Key changes were made in:

- 🔧  change type of need fields with ``bool | None`` to just ``bool`` in :pr:`1293`
- ♻️ Remove ``target_id`` core need field in :pr:`1315`
- ♻️ Output ``content`` in ``needs.json`` not ``description`` in :pr:`1312`
- 👌 Add ``creator`` key to ``needs.json`` in :pr:`1311`

Replacement of ``[[...]]`` and ``need_func`` in need content
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The parsing of the ``[[...]]`` dynamic function syntax in need content could cause confusion and unexpected behaviour.
This has been deprecated in favour of the new, more explicit :ref:`ndf role <ndf>`, which also deprecates the ``need_func`` role.

See :pr:`1269` and :pr:`1266` for more information.

Removed deprecation
~~~~~~~~~~~~~~~~~~~

The deprecated ``needfilter`` directive is now removed (:pr:`1308`)

New and improved features
.........................

- ✨ add ``tags`` option for ``list2need`` directive in :pr:`1296`
- ✨ Add ``ids`` option for ``needimport`` in :pr:`1292`
- 👌 Allow ``ref`` in ``needuml`` to handle need parts in :pr:`1222`
- 👌 Improve parsing of need option lists with dynamic functions in :pr:`1272`
- 👌 Improve warning for needextract incompatibility with external needs in :pr:`1325`
- 🔧 Set ``env_version`` for sphinx extension in :pr:`1313`

Bug Fixes
.........

- 🐛 Fix removal of ``Needextend`` nodes in :pr:`1298`
- 🐛 Fix ``usage`` numbers  in ``needreport`` in :pr:`1285`
- 🐛 Fix ``parent_need`` propagation from external/imported needs in :pr:`1286`
- 🐛 Fix ``need_part`` with multi-line content in :pr:`1284`
- 🐛 Fix dynamic functions in ``needextract`` need in :pr:`1273`
- 🐛 Disallow dynamic functions ``[[..]]`` in literal content in :pr:`1263`
- 🐛 fix parts defined in nested needs in :pr:`1265`
- 🐛 Handle malformed ``filter-func`` option value in :pr:`1254`
- 🐛 Pass ``needs`` to ``highlight`` filter of ``graphviz`` `needflow` in :pr:`1274`
- 🐛 Fix parts title for ``needflow`` with ``graphviz`` engine in :pr:`1280`
- 🐛 Fix ``need_count`` division by 0 in :pr:`1324`

3.0.0
-----

:Released: 28.08.2024
:Full Changelog: `v2.1.0...v3.0.0 <https://github.com/useblocks/sphinx-needs/compare/2.1.0...59cc6bf>`__

This release includes a number of new features and improvements, as well as some bug fixes.

Updated dependencies
....................

- sphinx: ``>=5.0,<8`` to ``>=6.0,<9``
- requests: ``^2.25.1`` to ``^2.32``
- requests-file: ``^1.5.1`` to ``^2.1``
- sphinx-data-viewer: ``^0.1.1`` to ``^0.1.5``

Documentation and CSS styling
..............................

The documentation theme has been completely updated, and a tutorial added.

To improve ``sphinx-needs`` compatibility across different Sphinx HTML themes,
the CSS for needs etc has been modified substantially, and so,
if you have custom CSS for your needs, you may need to update it.

See :ref:`install_theme` for more information on how to setup CSS for different themes,
and :pr:`1178`, :pr:`1181`, :pr:`1182` and :pr:`1184` for the changes.

``needflow`` improvements
..........................

The use of `Graphviz <https://graphviz.org/>`__ as the underlying engine for `needflow` diagrams, in addition to the default `PlantUML <http://plantuml.com>`__,
is now allowed via the global :ref:`needs_flow_engine` configuration option, or the per-diagram :ref:`engine <needflow_engine>` option.

The intention being to simplify and improve performance of graph builds, since ``plantuml`` has issues with JVM initialisation times and reliance on a third-party sphinx extension.

See :ref:`needflow` for more information,
and :pr:`1235` for the changes.

additional improvements:

- ✨ Allow setting an ``alt`` text for ``needflow`` images
- ✨ Allow creating a ``needflow`` from a ``root_id`` in :pr:`1186`
- ✨ Add ``border_color`` option for ``needflow`` in :pr:`1194`

``needs.json`` improvements
............................

A ``needs_schema`` is now included in the ``needs.json`` file (per version), which is a JSON schema for the data structure of a single need.

This includes defaults for each field, and can be used in combination with the :ref:`needs_json_remove_defaults` configuration option to remove these defaults from each individual need.

Together with the new automatic minifying of the ``needs.json`` file, this can reduce the file size by down to 1/8th of its previous size.

The :ref:`needs_json_exclude_fields` configuration option can also be used to modify the excluded need fields from the ``needs.json`` file,
and backlinks are now included in the ``needs.json`` file by default.

See :ref:`needs_builder_format` for more information,
and :pr:`1230`, :pr:`1232`, :pr:`1233` for the changes.

Additionally, the ``content_node``, ``content_id`` fields are removed from the internal need data structure (see :pr:`1241` and :pr:`1242`).

Additional improvements
.......................

- 👌 Capture filter processing times when using ``needs_debug_measurement=True`` in :pr:`1240`
- 👌 Allow ``style`` and ``color`` fields to be omitted for ``needs_types`` items and a default used in :pr:`1185`
- 👌 Allow ``collapse`` / ``delete`` / ``jinja_content`` directive options to be flags in :pr:`1188`
- 👌 Improve ``need-extend``; allow dynamic functions in lists in :pr:`1076`
- 👌 Add collapse button to ``clean_xxx`` layouts in :pr:`1187`

- 🐛 fix warnings for duplicate needs in parallel builds in :pr:`1223`
- 🐛 Fix rendering of ``needextract`` needs and use warnings instead of exceptions in :pr:`1243` and :pr:`1249`

2.1.0
-----

:Released: 08.05.2024
:Full Changelog: `v2.0.0...v2.1.0 <https://github.com/useblocks/sphinx-needs/compare/2.0.0...2.1.0>`__

Improvements
............

- 👌 Default to warning for missing ``needextend`` ID in :pr:`1066`
- 👌 Make ``needtable`` titles more permissive in :pr:`1102`
- 👌 Add ``filter_warning`` directive option, to replace default warning text in :pr:`1093`
- 👌 Improve and test github ``needservice`` directive in :pr:`1113`
- 👌 Improve warnings for invalid filters (add source location and subtype) in :pr:`1128`
- 👌 Exclude external needs from ``needs_id_regex`` check in :pr:`1108`
- 👌 Fail and emit warning on filters that do not return a boolean result in :pr:`964`
- 👌 Improve ``Need`` node creation and content parsing in :pr:`1168`
- 👌 Add loading message to ``permalink.html`` in :pr:`1081`
- 👌 Remove hard-coding of ``completion`` and ``duration`` need fields in :pr:`1127`

Bug fixes
.........

- 🐛 Image layout function in :pr:`1135`
- 🐛 Centralise splitting of need ID in :pr:`1101`
- 🐛 Centralise need missing link reporting in :pr:`1104`

Internal improvements
......................

- 🔧 Use future annotations in all modules in :pr:`1111`
- 🔧 Replace black/isort/pyupgrade/flake8 with ruff in :pr:`1080`

- 🔧 Add better typing for ``extra_links`` config variable in :pr:`1131`
- 🔧 Centralise need parts creation and strongly type needs in :pr:`1129`
- 🔧 Fix typing of need docname/lineno in :pr:`1134`
- 🔧 Type ``ExternalSource`` config dict in :pr:`1115`
- 🔧 Enforce type checking in ``needuml.py`` in :pr:`1116`
- 🔧 Enforce type checking in ``api/need.py`` in :pr:`1117`
- 🔧 Add better typing for ``global_options`` config variable in :pr:`1120`

- 🔧 Move dead link need fields to internals in :pr:`1119`
- 🔧 Remove usage of ``hide_status`` and ``hide_tags`` in :pr:`1130`
- 🔧 Remove ``hidden`` field from ``extra_options`` in :pr:`1124`
- 🔧 Remove ``constraints`` from ``extra_options`` in :pr:`1123`
- 🔧 Remove use of deprecated ``needs_extra_options`` as ``dict`` in :pr:`1126`

2.0.0
-----

:Released: 13.11.2023
:Full Changelog: `1.3.0...v2.0.0 <https://github.com/useblocks/sphinx-needs/compare/1.3.0...faba19e>`__

This release is focussed on improving the internal code-base and its build time performance, as well as improved build warnings and other functionality improvements / fixes.  

Changed
.......

* Add Sphinx 7 support and drop Python 3.7 (:pr:`1056`).
  Sphinx 5, 6, 7 and Python 3.8 to 3.11 are now fully supported and tested.
* The ``matplotlib`` dependency (for ``needbar`` and ``needpie`` plots) is now optional, and should be installed with ``sphinx-needs[plotting]``, see :ref:`installation`  (:pr:`1061`)
* The ``NeedsBuilder`` format name is changed to ``needs`` (:pr:`978`)

New
...

* Added Builder :ref:`needs_id_builder` and config option :ref:`needs_build_json_per_id` in ``conf.py`` (:pr:`960`)
* Added ``needs_reproducible_json`` config option for the needs builder, see :ref:`needs_build_json` (:pr:`1065`)
* Added error messages for constraint failures (:pr:`1036`)

Improved
........

Performance: 

* General performance improvement (up to 50%) and less memory consumption (~40%).
* ``external_needs`` now uses cached templates to save generation time.
* Improved performance for :ref:`needextend` with single needs.
* Improved performance by memoizing the inline parse in ``build_need`` (:pr:`968`)
* Remove ``deepcopy`` of needs data (:pr:`1033`)
* Optimize ``needextend`` filter_needs usage (:pr:`1030`)
* Improve performance of needs builders by skipping document post-transforms (:pr:`1054`)

Other:

* Improve sphinx warnings (:pr:`975`, :pr:`982`)
  All warnings are now suffixed with ``[needs]``, and can be suppressed (see `suppress_warnings <https://www.sphinx-doc.org/en/master/usage/configuration.html#confval-suppress_warnings>`_)
* Improve logging for static file copies (:pr:`992`)
* Improve removal of hidden need nodes (:pr:`1013`)
* Improve ``process_constraints`` function (:pr:`1015`)
* Allow ``needextend`` directive to use dynamic functions (:pr:`1052`)
* Remove some unnecessary keys from output ``needs.json`` (:pr:`1053`)

Fixed
.....

* Fix gantt chart rendering (:pr:`984`)
* Fix ``execute_func`` (:pr:`994`)
* Fix adding sections to hidden needs (:pr:`995`)
* Fix ``NeedImport`` logic (:pr:`1006`)
* Fix creation of need title nodes (:pr:`1008`)
* Fix logic for ``process_needextend`` function (:pr:`1037`)
* Fix usage of reST syntax in prefix parameter of meta (:pr:`1046`)

Internal
........

* 🔧 Centralise access to sphinx-needs config to ``NeedsSphinxConfig``  (:pr:`998`)
* 🔧 Centralise sphinx ``env`` data access to ``SphinxNeedsData`` (:pr:`987`)
* 🔧 Consolidate needs data post-processing into ``post_process_needs_data`` function  (:pr:`1039`)
* 🔧 Add strict type checking (:pr:`1000`, :pr:`1002`, :pr:`1042`)
* 🔧 Replace ``Directive`` with ``SphinxDirective`` (:pr:`986`)
* 🔧 Remove ``unwrap`` function (:pr:`1017`)
* 🔧 Add ``remove_node_from_tree`` utility function (:pr:`1063`)
* ♻️ Refactor needs post-processing function signatures (:pr:`1040`)

* 📚 Simplify Sphinx-Needs docs builds (:pr:`972`)
* 📚 Always use headless plantuml (:pr:`983`)
* 📚 Add intersphinx (:pr:`991`)
* 📚 Add outline of extension logic (:pr:`1012`)
* 📚 Fixed extra links example (:pr:`1016`)

* 🧪 Remove boilerplate from test build ``conf.py`` files (:pr:`989`, :pr:`990`)
* 🧪 Add headless java to test builds (:pr:`988`)
* 🧪 Add snapshot testing (:pr:`1019`, :pr:`1020`, :pr:`1059`)
* 🧪 Make documentation builds fail on warnings (:pr:`1005`)
* 🧪 Add testing of JS scripts using Cypress integrated into PyTest (:pr:`1051`)
* 🧪 Add code coverage to CI testing (:pr:`1067`)

1.3.0
-----
Released: 16.08.2023

* Improvement: Configuration option :ref:`needs_debug_measurement` added, which creates a runtime report
  for debugging purposes.
  (:pr:`917`)
* Bugfix: Replace hardcoded `index` with config value `root_doc`.
  (:pr:`877`)
* Bugfix: Fix unbounded memory usage in pickle environment.
  (:pr:`912`)
* Bugfix: Supports "None" body in Github services.
  (:issue:`903`)
* Removed esbonio for :ref:`ide`.
* Removed configuration option **needs_ide_snippets_id** to support custom need ID for :ref:`ide` snippets.
* Removed configuration **needs_ide_directive_snippets** to support custom directive snippets for IDE features.
* Provided new IDE support option: VsCode extension
  `Sphinx-Needs-VsCode <https://marketplace.visualstudio.com/items?itemName=useblocks.sphinx-needs-vscode>`_.
* Improvement: Added configuration option :ref:`needs_report_dead_links`, which can deactivate log messages of
  outgoing dead links.
  (:issue:`920`)
* Improvement: Configuration option :ref:`needs_allow_unsafe_filters` added, which allows unsafe filter for
  :ref:`filter_func`.
  (:issue:`831`)

1.2.2
-----
Released: 08.02.2023

* Bugfix: Changed needed version of jsonschema-lib to be not so strict.
  (:pr:`871`)

1.2.1
-----
Released: 08.02.2023

* Bugfix: Fixed pygls version compatibility.
  (:pr:`867`,
  :pr:`865`)

1.2.0
-----
Released: 24.01.2023

* Bugfix: Allowing newer versions of jsonschema.
  (:pr:`848`)
* Improvement: Adds :ref:`list2need` directive, which allows to create simple needs from list.
  (:issue:`854`)


1.1.1
-----
Released: 21.12.2022

* Bugfix: Removed outdated JS codes that handles the collapse button.
  (:issue:`840`)
* Improvement: Write autogenerated images into output folder
  (:issue:`413`)
* Improvement: Added vector output support to need figures.
  (:issue:`815`).
* Improvement: Introduce the jinja function `ref` for :ref:`needuml`.
  (:issue:`789`)
* Bugfix: Needflow fix bug in child need handling.
  (:issue:`785`).
* Bugfix: Needextract handles image and download directives correctly.
  (:issue:`818`).
* Bugfix: Needextract handles substitutions correctly.
  (:issue:`835`).

1.1.0
-----
Released: 22.11.2022

* Bugfix: Expand/Collapse button does not work.
  (:issue:`795`).
* Bugfix: `singlehtml` and `latex` related builders are working again.
  (:issue:`796`).
* Bugfix: Needextend throws the same information 3 times as part of a single warning.
  (:issue:`747`).
* Improvement: Memory consumption and runtime improvements
  (:issue:`790`).
* Improvement: Obfuscate HTTP authentication credentials from log output.
  (:issue:`759`)
* Bugfix: needflow: nested needs on same level throws PlantUML error.
  (:issue:`799`)

1.0.3
-----
Released: 08.11.2022


* Improvement: Fixed :ref:`needextend` error handling by adding a strict-mode option to it.
  (:issue:`747`)
* Improvement: Fixed issue with handling needs-variants by default.
  (:issue:`776`)
* Improvement: Performance fix needs processing.
  (:issue:`756`)
* Improvement: Performance fix for needflow.
  (:issue:`760`)
* Improvement: Fixed rendering issue with the debug layout.
  (:issue:`721`)
* Improvement: Added :ref:`needs_show_link_id`.
* Improvement: Supported arguments as filter string for :ref:`needextract`.
  (:issue:`688`)
* Improvement: Added :ref:`needs_render_context` configuration option which enables you to use custom data as the
  context when rendering Jinja templates or strings.
  (:issue:`704`)
* Improvement: Supported ``target_url`` for :ref:`needs_external_needs`.
  (:issue:`701`)
* Bugfix: Fixed needuml key shown in need meta data by providing internal need option `arch`.
  (:issue:`687`)
* Improvement: Included child needs inside their parent need for :ref:`needflow`.
  (:issue:`714`)
* Improvement: Supported generate need ID from title with :ref:`needs_id_from_title`.
  (:issue:`692`)
* Improvement: Supported download ``needs.json`` for :ref:`needimport`.
  (:issue:`715`)
* Bugfix: Fixed import() be included in needarch.
  (:issue:`730`)
* Bugfix: Needuml: uml() call circle leads to an exception :ref:`needarch_ex_loop`.
  (:issue:`731`)
* Improvement: needarch provide need() function to get "need data".
  (:issue:`732`)
* Improvement: needuml - flow() shall return plantuml text without newline.
  (:issue:`737`)
* Bugfix: Needuml used but "sphinxcontrib.plantuml" not installed leads to exception
  (:issue:`742`)
* Improvement: better documentation of mixing orientation and coloring in needs_extra_links
  (:issue:`764`)
* Bugfix: Needarch: Fixed import() function to work with new implemented flow() (#737).
  (:issue:`752`)
* Bugfix: Needtable: generate id for nodes.table
  (:issue:`434`)
* Improvement: Updated pantuml in test folder to same version as in doc folder
  (:issue:`765`)

1.0.2
-----
Released: 22.09.2022


* Improvement: Added support for variants handling for need options.
  (:issue:`671`)
* Improvement: Added Jinja support for need content via the :ref:`jinja_content` option.
  (:issue:`678`)
* Improvement: Added checks and warnings for :ref:`needimport` and :ref:`needs_external_needs`.
  (:issue:`624`)
* Improvement: Support for :ref:`needs_string_links` in :ref:`needtable`.
  (:issue:`535`)
* Improvement: Added `key` option for :ref:`needuml`.
* Bugfix: Removed default setting `allowmixing` for :ref:`needuml`.
  (:issue:`649`)
* Bugfix: Fixed the collapse button issue for needs including nested needs.
  (:issue:`659`)
* Bugfix: Fixed :ref:`needextract` filter options issue involved with :ref:`need_part`.
  (:issue:`651`)
* Improvement: Added `save` option for :ref:`needuml`.
* Improvement: Added builder :ref:`needumls_builder` and config option :ref:`needs_build_needumls` in `conf.py`.
* Improvement: Added `filter` function for :ref:`needuml`.
* Improvement: Renamed jinja function `need` to `flow` for :ref:`needuml`.
* Improvement: Added directive :ref:`needarch`.
* Improvement: Added configuration option **needs_ide_snippets_id** to support custom need ID for :ref:`ide` snippets.
* Improvement: Provides jinja function :ref:`needarch_jinja_import` for :ref:`needarch` to execute :ref:`needuml_jinja_uml`
  automatically for all the links defined in the need :ref:`need_links` options.
* Improvement: Added configuration **needs_ide_directive_snippets** to support custom directive snippets for IDE features.
  (:issue:`640`)
* Bugfix: Updated pip install URLs in Dockerfile.
  (:issue:`673`)
* Improvement: Providing IDE features support for **ide_myst**.

1.0.1
-----
Released: 11.07.2022

* Notice: **Sphinx <5.0 is no longer supported.**
* Notice: **Docutils <0.18.1 is no longer supported.**
* Improvement: Provides :ref:`needuml` for powerful, reusable Need objects.
* Improvement: Provides :ref:`needreport` for documenting configuration used in a **Sphinx-Needs** project's **conf.py**.
* Improvement: Provides initial support for Sphinx-Needs IDE language features.
  (:pr:`584`)
* Improvement: Support snippet for auto directive completion for Sphinx-Needs IDE language features.
* Improvement: Added `show_top_sum` to :ref:`Needbar <needbar>` and make it possible to rotate the bar labels.
  (:issue:`516`)
* Improvement: Added `needs_constraints` option. Constraints can be set for individual needs and describe properties
  a need has to meet.
* Improvement: Added customizable link text of :ref:`Need <needref>`.
  (`#439 <https://github.com/useblocks/sphinx-needs/discussions/439>`_)
* Bugfix: Fixed lsp needs.json path check.
  (:issue:`603`,
  :issue:`633`)
* Bugfix: Support embedded needs in embedded needs.
  (:issue:`486`)
* Bugfix: Correct references in :ref:`needtables <needtable>` to be external or internal instead of always external.
* Bugfix: Correct documentation and configuration in :ref:`need_tags` to *list* type.
* Bugfix: Handle overlapping labels in :ref:`needpie`.
  (:issue:`498`)
* Bugfix: :ref:`needimport` uses source-folder for relative path calculation (instead of confdir).

0.7.9
-----
Released: 10.05.2022

* Improvement: Add permanent link layout function.
  (:issue:`390`)
* Improvement: Support for **Sphinx-Needs** Docker Image.
  (:issue:`531`)
* Bugfix: :ref:`needextract` not correctly rendering nested :ref:`needs <need>`.
  (:issue:`329`)

0.7.8
-----
Released: 29.03.2022

* Improvement: Provides line number info for needs node.
  (:issue:`499`)
* Bugfix: :ref:`needpie` causing a crash in some cases on newer matplotlib versions.
  (:issue:`513`,
  :issue:`517`)
* Bugfix: :ref:`needpie` takes need-parts in account for filtering.
  (:issue:`514`)
* Bugfix: Empty and invalid ``need.json`` files throw user-friendly exceptions.
  (:issue:`441`)


0.7.7
-----
Released: 04.03.2022

* Bugfix: ``need`` role supporting lower and upper IDs.
  (:issue:`508`)
* Bugfix: Correct image registration to support build via Sphinx API.
  (:issue:`505`)
* Bugfix: Correct css/js file registration on windows.
  (:issue:`455`)

0.7.6
-----
Released: 28.02.2022

* Improvement: :ref:`filter_func` support arguments.
  (:issue:`429`)
* Improvement: Adds :ref:`needs_build_json` config option to build ``needs.json`` in parallel to other output formats.
  (:issue:`485`)
* Improvement: Migrate tests to Pytest and Sphinx internal testing structure.
  (:issue:`471`)
* Bugfix: :ref:`needs_builder` supports incremental build (no doctree deletion).
  (:issue:`481`)
* Bugfix: :ref:`needs_external_needs` working with :ref:`role_need`.
  (:issue:`483`)

0.7.5
-----
Released: 21.01.2022

* Improvement: :ref:`needbar` is introduced
  (:issue:`452`)
* Improvement: :ref:`needs_external_needs` supports relative path for ``base_url``.
* Improvement: ``needs.json`` schema gets checked during a :ref:`needimport`
  (:issue:`456`)
* Improvement: Supports :ref:`filter_func` for :ref:`needpie`
  (:issue:`400`)
* Bugfix: Changed :ref:`needgantt` strftime format string according to C89 defined value.
  (:issue:`445`)
* Bugfix: :ref:`needpie` option :legend: is correctls rendered
  (:issue:`448`)
* Bugfix: :ref:`needpie` figures are closed after creation, to free memory and suppress matplotlib warning
  (:issue:`450`)
* Bugfix: Added implementation for simple_footer grid in Layouts Grids
  (:issue:`457`)
* Bugfix: Changed :ref:`needs_external_needs` Fix issue when loading needs from URL.
  (:issue:`459`)
* Bugfix: Changed :ref:`needs_external_needs` getting from URL was using parameter related to local file.
  (:issue:`458`)

0.7.4
-----
Released: 30.11.2021

* Improvement: Adds :ref:`needservice_debug` flag for :ref:`needservice`.
* Improvement: Better css table handling.
* Improvement: Adds :ref:`needtable_class` to :ref:`needtable` to set own css classes for tables.
  (:issue:`421`)
* Improvement: Adds :ref:`needs_string_links` to support easy string2link transformations.
  (:issue:`404`)
* Improvement: Adds :ref:`needtable_colwidths` to :ref:`needtable` directive, to allow the definition of column widths.
  (:issue:`402`)

0.7.3
-----
Released: 08.11.2021

* Improvement: Schema check for ``need.json`` files implemented.
* Improvement: New option for ``needtable`` and co: :ref:`filter_func`, which allows to reference and use python code
  as filter code from external files
  (:issue:`340`)
* Bugfix: Fixed :ref:`needs_builder` handling warnings about missing needs.json when :ref:`needs_file` not configured
  (:issue:`340`)
* Bugfix: unstable build with :ref:`needs_external_needs`
  (:issue:`399`)
* Bugfix: :ref:`needs_external_needs` reads external need status now and warnings gets not checked for
  :ref:`needs_external_needs`
  (:issue:`375`)

0.7.2
-----
Released: 08.10.2021

* Improvement: New config option :ref:`needs_builder_filter` to define a filter for the needs builder.
  (:issue:`342`)
* Improvement: Added option ``json_path`` for :ref:`needs_external_needs` to support external needs from local ``needs.json`` files.
  (:issue:`339`)
* Improvement: Providing :ref:`needs_table_classes` to allow to set custom table css classes, to better support
  themes like ReadTheDocs.
  (:issue:`305`)
* Improvement: Supporting user defined filter code function for :ref:`needs_warnings`
  (:issue:`345`)
* Improvement: Supporting caption for :ref:`needtable`
  (:issue:`348`)
* Improvement: New config option :ref:`needs_filter_data` to allow to use custom data inside a :ref:`filter_string`
  (:issue:`317`)
* Improvement: API to register warnings
  (:issue:`343`)
* Bugfix: Scrolling tables improved and ReadTheDocs Tables fixed
  (:issue:`305`)
* Bugfix: :ref:`needtable` need parts 'id' column is not linked
  (:issue:`336`)
* Bugfix: :ref:`needtable` need parts 'incoming' column is empty
  (:issue:`336`)
* Bugfix: :ref:`needs_warnings` not written to error log.
  (:issue:`344`)
* Improvement: Providing :ref:`needs_warnings_always_warn` to raise sphinx-warnings for each not passed :ref:`needs_warnings`.
  (:issue:`344`)
* Bugfix: :ref:`needimport` relative path not consistent to Sphinx default directives.
  (:issue:`351`)

0.7.1
-----
Released: 21.07.2021

* Improvement: Support for parallel sphinx-build when using ``-j`` option
  (:issue:`319`)
* Improvement: Better ``eval()`` handling for filter strings
  (:issue:`328`)
* Improvement: Internal :ref:`performance measurement <performance>` script
* Improvement: :ref:`Profiling support <profiling>` for selected functions

0.7.0
-----
Released: 06.07.2021

* Improvement: Providing :ref:`needs_external_needs` to allow usage and referencing of external needs.
  (:issue:`137`)
* Improvement: New directive :ref:`needextend` to modify or extend existing needs.
  (:issue:`282`)
* Improvement: Allowing :ref:`needtable_custom_titles` for :ref:`needtable`.
  (:issue:`299`)
* Bugfix: :ref:`needextend` does not support usage of internal options.
  (:issue:`318`)
* Bugfix: :ref:`needtable` shows attributes with value ``False`` again.
* Bugfix: ``:hide:`` and ``:collapse: True`` are working inside :ref:`needimport`.
  (:issue:`284`,
  :issue:`294`)
* Bugfix: :ref:`needpie` amount labels get calculated correctly.
  (:issue:`297`)

0.6.3
-----
Released: 18.06.2021

* Improvement: Dead links (references to not found needs) are supported and configurable by :ref:`allow_dead_links`.
  (:issue:`116`)
* Improvement: Introducing :ref:`need_func` to execute :ref:`dynamic_functions` inline.
  (:issue:`133`)
* Improvement: Support for :ref:`!multiline_option` in templates.
* Bugfix: needflow: links  for need-parts get correctly calculated.
  (:issue:`205`)
* Bugfix: CSS update for ReadTheDocsTheme to show tables correctly.
  (:issue:`263`)
* Bugfix: CSS fix for needtable :ref:`needtable_style_row`.
  (:issue:`195`)
* Bugfix: ``current_need`` var is accessible in all need-filters.
  (:issue:`169`)
* Bugfix: Sets defaults for color and style of need type configuration, if not set by user.
  (:issue:`151`)
* Bugfix: :ref:`needtable` shows horizontal scrollbar for tables using datatables style.
  (:issue:`271`)
* Bugfix: Using ``id_complete`` instead of ``id`` in filter code handling.
  (:issue:`156`)
* Bugfix: Dynamic Functions registration working for external extensions.
  (:issue:`288`)

0.6.2
-----
Released: 30.04.2021

* Improvement: Parent needs of nested needs get collected and are available in filters.
  (:issue:`249`)
* Bugfix: Copying static files during sphinx build is working again.
  (:issue:`252`)
* Bugfix: Link function for layouts setting correct text.
  (:issue:`251`)


0.6.1
-----
Released: 23.04.2021

* Support: Removes support for Sphinx version <3.0 (Sphinx 2.x may still work, but it gets not tested).
* Improvement: Internal change to poetry, nox and github actions.
  (:issue:`216`)
* Bugfix: Need-service calls get mocked during tests, so that tests don't need reachable external services any more.
* Bugfix: No warning is thrown any more, if :ref:`needservice` can't find a service config in **conf.py**
  (:issue:`168`)
* Bugfix: Needs nodes get ``ids`` set directly, to avoid empty ids given by sphinx or other extensions for need-nodes.
  (:issue:`193`)
* Bugfix: :ref:`needimport` supports extra options and extra fields.
  (:issue:`227`)
* Bugfix: Checking for ending `/` of given github api url.
  (:issue:`187`)
* Bugfix: Using correct indention for pre and post_template function of needs.
* Bugfix: Certain log message don't use python internal `id` any more.
  (:issue:`225`)
* Bugfix: JS-code for meta area collapse is working again.
  (:issue:`242`)


0.6.0
-----

* Improvement: Directive :ref:`needservice` added, which allow to include data from external services like Jira or github.
  See also :ref:`services`
  (:issue:`163`)
* Improvement: :ref:`github_service` added to fetch issues, pr or commits from GitHub or GitHub Enterprise.
* Bugfix: Role :ref:`role_need_outgoing` shows correct link instead of *None*
  (:issue:`160`)


0.5.6
-----

* Bugfix: Dynamic function registration via API supports new internal function handling
  (:issue:`147`)
* Bugfix: Deactivated linked gantt elements in :ref:`needgantt`, as PlantUML does not support them in its
  latest version (not beta).

0.5.5
-----
* Improvement: Added :ref:`needsequence` directive. (:issue:`144`)
* Improvement: Added :ref:`needgantt` directive. (:issue:`146`)
* Improvement: Added two new need-options: :ref:`need_duration` and :ref:`need_completion`
* Improvement: Configuration option :ref:`needs_duration_option` and :ref:`needs_completion_option` added
* Bugfix: Using of `tags.has() <https://www.sphinx-doc.org/en/master/usage/configuration.html#conf-tags>`_ in
  **conf.py** does not raise an exception any more. (:issue:`142`)
* Improvement: Clean up of internal configuration handling and avoiding needs_functions to get pickled by sphinx.


0.5.4
-----
* Improvement: Added options :ref:`need_pre_template` and :ref:`need_post_template` for needs. (:issue:`139`)
* Bugfix: Setting correct default value for :ref:`needs_statuses` (:issue:`136`)
* Bugfix: Dynamic functions can be used in links (text and url) now.

0.5.3
-----
* Improvement: Added ``transparent`` for transparent background to needflow configurations.
* Improvement: :ref:`needflow` uses directive argument as caption now.
* Improvement: Added option :ref:`needflow_align` to align needflow images.
* Improvement: Added option :ref:`needflow_scale` to scale needflow images. (:issue:`127`)
* Improvement: Added option :ref:`needflow_highlight` to :ref:`needflow`. (:issue:`128`)
* Improvement: :ref:`need_count` supports :ref:`ratio calculation <need_count_ratio>`. (:issue:`131`)
* Improvement: :ref:`needlist`, :ref:`needtable` and :ref:`needflow` support :ref:`filter_code`. (:issue:`132`)
* Improvement: :ref:`needflow` caption is a link to the original image file. (:issue:`129`)
* Bugfix: :ref:`need_template` can now be set via :ref:`needs_global_options`.
* Bugfix: Setting correct urls for needs in :ref:`needflow` charts.
* Bugfix: Setting correct image candidates (:issue:`134`)

0.5.2
-----
* Improvement: **Sphinx-Needs** configuration gets checked before build. (:issue:`118`)
* Improvement: ``meta_links_all`` :ref:`layout function <layout_functions>` now supports an exclude parameter
* Improvement: :ref:`needflow`'s :ref:`connection line and arrow type <needflow_style_start>` can be configured.
* Improvement: Configurations added for :ref:`needflow`. Use :ref:`needs_flow_configs` to define them and :ref:`needflow_config` for activation.
* Improvement: :ref:`needflow` option :ref:`needflow_debug` added, which prints the generated PlantUML code after the flowchart.
* Improvement: Supporting Need-Templates by providing need option :ref:`need_template` and
  configuration option :ref:`needs_template_folder`. (:issue:`119`)
* Bugfix: :ref:`needs_global_options` handles None values correctly. ``style`` can now be set.
* Bugfix: :ref:`needs_title_from_content` takes ``\n`` and ``.`` as delimiter.
* Bugfix: Setting css-attribute ``white-space: normal`` for all need-tables, which is set badly in some sphinx-themes.
  (Yes, I'm looking at you *ReadTheDocs theme*...)
* Bugfix: ``meta_all`` :ref:`layout function <layout_functions>` also outputs extra links and the `no_links`
  parameter now works as expected
* Bugfix: Added need-type as css-class back on need. Css class name is ``needs_type_(need_type attribute)``.
  (:issue:`124`)
* Bugfix: Need access inside list comprehensions in :ref:`filter_string` is now working.

0.5.1
-----
* Improvement: Added :ref:`needextract` directive to mirror existing needs for special outputs. (:issue:`66`)
* Improvement: Added new styles ``discreet`` and ``discreet_border``.
* Bugfix: Some minor css fixes for new layout system.

0.5.0
-----

* Improvement: Introduction of needs :ref:`layouts_styles`.
* Improvement: Added config options :ref:`needs_layouts` and :ref:`needs_default_layout`.
* Improvement: Added :ref:`needpie` which draws pie-charts based on :ref:`filter_string`.
* Improvement: Added config option :ref:`needs_warnings`. (:issue:`110`)
* Bugfix: Need css style name is now based on need-type and not on the longer, whitespace-containing type name.
  Example: ``need-test`` instead of not valid ``need-test case``. (:issue:`108`)
* Bugfix: No more exception raise if ``copy`` value not set inside :ref:`needs_extra_links`.
* Improvement: Better log message, if required id is missing. (:issue:`112`)

* Removed: Configuration option :ref:`!needs_collapse_details`. This is now realized by :ref:`layouts`.
* Removed: Configuration option :ref:`!needs_hide_options`. This is now realized by :ref:`layouts`.
* Removed: Need option :ref:`!need_hide_status`. This is now realized by :ref:`layouts`.
* Removed: Need option :ref:`!need_hide_tags`. This is now realized by :ref:`layouts`.

**WARNING**: This version changes a lot the html output and therefore the needed css selectors. So if you are using
custom css definitions you need to update them.

0.4.3
-----

* Improvement: Role :ref:`role_need` supports standard sphinx-ref syntax. Example: ``:need:`custom name <need_id>```
* Improvement: Added :ref:`global_option_filters` to set values of global options only under custom circumstances.
* Improvement: Added sorting to :ref:`needtable`. See :ref:`needtable_sort` for details.
* Improvement: Added dynamic function :ref:`links_content` to calculated links to other needs automatically from need-content.
  (:issue:`98`)
* Improvement: Dynamic function :ref:`copy` supports uppercase and lowercase transformation.
* Improvement: Dynamic function :ref:`copy` supports filter_string.
* Bugfix: Fixed corrupted :ref:`dynamic_functions` handling for ``tags`` and other list options.
  (:issue:`100`)
* Bugfix: Double entries for same need in :ref:`needtable` fixed. (:issue:`93`)

0.4.2
-----

* Improvement: Added ``signature`` information to need-object. Usable inside :ref:`filter_string`.
  Mainly needed by `Sphinx-Test-Reports <https://sphinx-test-reports.readthedocs.io/en/latest/>`_ to link imported
  test cases to needs documented by
  `sphinx-autodoc <https://www.sphinx-doc.org/en/master/usage/extensions/autodoc.html>`_.

0.4.1
-----
* Improvement: Added :ref:`need_style` option to allow custom styles for needs.
* Improvement: Added :ref:`needtable_style_row` option to allow custom styles for table rows and columns.


0.4.0
-----
* Improvement: Provides API for other sphinx-extensions. See :ref:`api` for documentation.
* Improvement: Added :ref:`support` page.
* Bugfix: Fixed deprecation warnings to support upcoming Sphinx3.0 API.

0.3.15
------
* Improvement: In filter operations, all needs can be accessed  by using keyword ``needs``.
* Bugfix: Removed prefix from normal needs for needtable (:issue:`97`)

0.3.14
------
* Improvement: Added config option :ref:`needs_role_need_max_title_length` to define the maximum title length of
  referenced needs. (:issue:`95`)

0.3.13
------
* Bugfix: Filters on needs with ``id_parent`` or ``id_complete`` do not raise an exception any more and filters
  gets executed correctly.

0.3.12
------
* Improvement: Tables can be sorted by any alphanumeric option. (:issue:`92`)
* Improvement: :ref:`need_part` are now embedded in their parent need, if :ref:`needflow` is used. (:issue:`83`)
* Bugfix: Links to :ref:`need_part` are no longer rendered to parent need, instead the link goes directly to the need_part. (:issue:`91`)
* Bugfix: Links in :ref:`needflow` get shown again by default (:issue:`90`)


0.3.11
------
* Improvement: Added config option :ref:`needs_extra_links` to define additional link types like *blocks*, *tested by* and more.
  Supports also style configuration and custom presentation names for links.
* Improvement: Added :ref:`!export_id` option for filter directives to export results of filters to ``needs.json``.
* Improvement: Added config option :ref:`needs_flow_show_links` and related needflow option :ref:`needflow_show_link_names`.
* Improvement: Added config option :ref:`needs_flow_link_types` and related needflow option :ref:`needflow_link_types`.
* Bugfix: Unicode handling for Python 2.7 fixed. (:issue:`86`)

0.3.10
------
* Bugfix: **type** was missing in output of builder :ref:`needs_builder` (:issue:`79`)
* Bugfix: **needs_functions** parameter in *conf.py* created a sphinx error, if
  containing python methods. Internal workaround added, so that usage of own
  :ref:`dynamic_functions` stays the same as in prior versions (:issue:`78`)


0.3.9
-----
* Bugfix: Grubby tag/link strings in needs, which define empty links/tags, produce a warning now.
* Bugfix: Better logging of document location, if a filter string is not valid.
* Bugfix: Replaced all print-statements with sphinx warnings.

0.3.8
-----

* Improvement: :ref:`need_part` has now attributes `id_parent` and `id_complete`, which can be referenced
  in :ref:`filter_string`.
* Improvement: :ref:`needtable` supports presentation of filtered :ref:`need_part` (without showing parent need).

0.3.7
-----
* Improvement: :ref:`filter_string` now supports the filtering of :ref:`need_part`.
* Improvement: The ID of a need is now printed as link, which can easily be used for sharing. (:issue:`75`)
* Bugfix: Filter functionality in different directives are now using the same internal filter function.
* Bugfix: Reused IDs for a :ref:`need_part` are now detected and a warning gets printed. (:issue:`74`)

0.3.6
-----
* Improvement: Added needtable option :ref:`needtable_show_parts`.
* Improvement: Added configuration option :ref:`needs_part_prefix`.
* Improvement: Added docname to output file of builder :ref:`needs_builder`
* Bugfix: Added missing needs_import template to MANIFEST.ini.

0.3.5
-----
* Bugfix: A :ref:`need_part` without a given ID gets a random id based on its content now.
* Bugfix: Calculation of outgoing links does not crash, if need_parts are involved.


0.3.4
-----
* Bugfix: Need representation in PDFs were broken (e.g. all meta data on one line).


0.3.3
-----
* Bugfix: Latex and Latexpdf are working again.

0.3.2
-----
* Bugfix: Links to parts of needs (:ref:`need_part`) are now stored and presented as *links incoming* of target link.

0.3.1
-----
* Improvement: Added dynamic function :ref:`check_linked_values`.
* Improvement: Added dynamic function :ref:`calc_sum`.
* Improvement: Added role :ref:`need_count`, which shows the amount of found needs for a given filter-string.
* Bugfix: Links to :ref:`need_part` in :ref:`needflow` are now shown correctly as extra line between
   need_parts containing needs.
* Bugfix: Links to :ref:`need_part` in :ref:`needtable` are now shown and linked correctly in tables.

0.3.0
-----
* Improvement: :ref:`dynamic_functions` are now available to support calculation of need values.
* Improvement: :ref:`needs_functions` can be used to register and use own dynamic functions.
* Improvement: Added :ref:`needs_global_options` to set need values globally for all needs.
* Improvement: Added :ref:`!needs_hide_options` to hide specific options of all needs.
* Bugfix: Removed needs are now deleted from existing needs.json (:issue:`68`)
* Removed: :ref:`!needs_template` and :ref:`!needs_template_collapse` are no longer supported.

0.2.5
-----
* Bugfix: Fix for changes made in 0.2.5.

0.2.4
-----
* Bugfix: Fixed performance issue (:issue:`63`)

0.2.3
-----
* Improvement: Titles can now be made optional.  See :ref:`needs_title_optional`. (:issue:`49`)
* Improvement: Titles be auto-generated from the first sentence of a requirement.  See :ref:`needs_title_from_content` and :ref:`title_from_content`. (:issue:`49`)
* Improvement: Titles can have a maximum length.  See :ref:`needs_max_title_length`. (:issue:`49`)

0.2.2
-----
* Improvement: The sections, to which a need belongs, are now stored, filterable and exported in ``needs.json``. See updated :ref:`option_filter`. (:pr:`53` )
* Improvement: Project specific options for needs are supported now. See :ref:`needs_extra_options`. (:pr:`48` )
* Bugfix: Logging fixed (:issue:`50` )
* Bugfix: Tests for custom styles are now working when executed with all other tests (:pr:`47`)


0.2.1
-----
* Bugfix: Sphinx warnings fixed, if need-collapse was used. (:issue:`46`)
* Bugfix: dark.css, blank.css and common.css used wrong need-container selector. Fixed.

0.2.0
-----
* Deprecated: ``needfilter`` is replaced by :ref:`needlist`, :ref:`needtable` or :ref:`needflow`. Which support additional options for related layout.
* Improvement: Added :ref:`needtable` directive.
* Improvement: Added `DataTables <https://datatables.net/>`_ support for :ref:`needtable` (including table search, excel/pdf export and dynamic column selection).
* Improvement: Added :ref:`needs_id_regex`, which takes a regular expression and which is used to validate given IDs of needs.
* Improvement: Added meta information shields on documentation page
* Improvement: Added more examples to documentation
* Bugfix: Care about unneeded separator characters in tags (:issue:`36`)
* Bugfix: Avoiding multiple registration of resource files (js, css), if sphinx gets called several times (e.g. during tests)
* Bugfix: Needs with no status shows up on filters (:issue:`45`)
* Bugfix: Supporting Sphinx 1.7 (:issue:`41`)

0.1.49
------
* Bugfix: Supporting plantuml >= 0.9 (:issue:`38`)
* Bugfix: need_outgoing does not crash, if given need-id does not exist (:issue:`32`)

0.1.48
------
* Improvement: Added configuration option :ref:`needs_role_need_template`.
* Bugfix: Referencing not existing needs will result in build warnings instead of a build crash.
* Refactoring: needs development files are stored internally under *sphinxcontrib/needs*, which is in sync with
   most other sphinxcontrib-packages.

0.1.47
------
* Bugfix: dark.css was missing in MANIFEST.in.
* Improvement: Better output, if configured needs_css file can not be found during build.

0.1.46
------
* Bugfix: Added python2/3 compatibility for needs_import.

0.1.45
------
* Bugfix: needs with no status are handled the correct way now.

0.1.44
------
* Bugfix: Import statements are checked, if Python 2 or 3 is used.

0.1.43
------
* Improvement: Added "dark.css" as style
* Bugfix: Removed "," as as separator of links in need presentation.

0.1.42
------
* Improvement: Added config parameter :ref:`needs_css`, which allows to set a css file.
* Improvement: Most need-elements (title, id, tags, status, ...) got their own html class attribute to support custom styles.
* Improvement: Set default style "modern.css" for all projects without configured :ref:`needs_css` parameter.

0.1.41
------

* Improvement: Added config parameters :ref:`needs_statuses` and :ref:`needs_tags` to allow only configured statuses/tags inside documentation.
* Bugfix: Added LICENSE file (MIT)

0.1.40
------
* Bugfix: Removed jinja activation

0.1.39
------
* Bugfix: Added missing needimport_template.rst to package
* Bugfix: Corrected version param of needimport

0.1.38
------
* Improvement: **:links:**, **:tags:** and other list-based options can handle "," as delimiter
   (beside documented ";"). No spooky errors are thrown any more if "," is used accidentally.

0.1.37
------
* Bugfix: Implemented 0.1.36 bugfix also for ``needfilter`` and :ref:`needimport`.

0.1.36
------
* Bugfix: Empty **:links:** and **:tags:** options for :ref:`need` raise no error during build.

0.1.35
------
* Improvement/Bug: Updated default node_template to use less space for node parameter representation
* Improvement: Added **:filter:** option to :ref:`needimport` directive
* Bugfix: Set correct default value for **need_list** option. So no more warnings should be thrown during build.
* Bugfix: Imported needs gets sorted by id before adding them to the related document.

0.1.34
------
* Improvement: New option **tags** for :ref:`needimport` directive
* Bugfix: Handling of relative paths in needs builder

0.1.33
------
* New feature: Directive :ref:`needimport` implemented
* Improvement: needs-builder stores needs.json for all cases in the build directory (like _build/needs/needs.json) (See `issue <https://github.com/useblocks/sphinx-needs/issues/9>`_)
* Bugfix: Wrong version in needs.json, if an existing needs.json got imported
* Bugfix: Wrong need amount in initial needs.json fixed

0.1.32
------
* Bugfix: Setting correct working directory during conf.py import
* Bugfix: Better config handling, if Sphinx builds gets called multiple times during one single python process. (Configs from prio sphinx builds may still be active.)
* Bugifx: Some clean ups for using Sphinx >= 1.6

0.1.31
------

* Bugfix: Added missing dependency to setup.py: Sphinx>=1.6

0.1.30
------
* Improvement: Builder :ref:`needs_builder` added, which exports all needs to a json file.

0.1.29
------

* Bugfix: Build has crashed, if sphinx-needs was loaded but not a single need was defined.

0.1.28
------

* Bugfix: Added support for multiple sphinx projects initialisations/builds during a single python process call.
           (Reliable sphinx-needs configuration separation)

0.1.27
------

* New config: :ref:`needs_show_link_type`
* New config: :ref:`needs_show_link_title`

0.1.26
------

* Bugfix: Working placement of "," for links list produced by roles :ref:`role_need_outgoing`
   and :ref:`role_need_incoming`.

0.1.25
------

* Restructured code
* Restructured documentation
* Improvement: Role :ref:`role_need_outgoing` was added to print outgoing links from a given need
* Improvement: Role :ref:`role_need_incoming` was added to print incoming links to a given need

0.1.24
------

* Bugfix: Reactivated jinja execution for documentation.

0.1.23
------

* Improvement: :ref:`complex filter <filter>` for needfilter directive supports :ref:`regex searches <re_search>`.
* Improvement: :ref:`complex filter <filter>` has access to nearly all need variables (id, title, content, ...)`.
* Bugfix: If a duplicated ID is detected an error gets thrown.

0.1.22
------

* Improvement: needfilter directives supports complex filter-logic by using parameter :ref:`filter`.

0.1.21
------

* Improvement: Added word highlighting of need titles in linked pages of svg diagram boxes.

0.1.20
------

* Bugfix for custom needs_types: Parameter in conf.py was not taken into account.

0.1.19
------

* Added configuration parameter :ref:`needs_id_required`.
* Backwards compatibility changes:

* Reimplemented **needlist** as alias for ``needfilter``
* Added *need* directive/need as part of the default :ref:`needs_types` configuration.

0.1.18
------

**Initial start for the changelog**

* Free definable need types (Requirements, Bugs, Tests, Employees, ...)
* Allowing configuration of needs with a

* directive name
* meaningful title
* prefix for generated IDs
* color

* Added **needfilter** directive
* Added layouts for needfilter:

* list (default)
* table
* diagram (based on plantuml)

* Integrated interaction with the activated plantuml sphinx extension

* Added role **need** to create a reference to a need by giving the id


