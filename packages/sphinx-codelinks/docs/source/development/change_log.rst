.. _changelog:

Changelog
=========

.. _`release:1.4.0`:

1.4.0
-----

:Released: 30.07.2026

New and Improved
................

- ✨ Added Bash language support for the ``analyse`` module.

  Comments in shell scripts are now parsed for need ID references and one-line need
  definitions. ``.sh``, ``.bash``, ``.zsh``, and ``.ksh`` files are discovered when
  ``comment_type = "bash"``. The supported comment style is ``#``. Fish shell is not
  supported (no ``tree-sitter-fish`` grammar is published for the Python package).

- ✨ Added an opt-in preprocessor-aware C/C++ extraction engine, powered by libclang.

  The default tree-sitter engine sees every comment in a file, regardless of conditional
  compilation. Configuring the new :ref:`analyse.preprocessor <preprocessor_config>` table
  switches C/C++ extraction to libclang, which evaluates the preprocessor and emits only
  the markers in **active** branches — a need behind an inactive ``#if`` / ``#else`` is
  dropped. Compiler flags are resolved per file from a ``compile_commands.json``
  compilation database, with an explicit ``defines`` list for headers, which are not
  listed in such a database. Active markers keep their original line numbers.

  The engine requires the optional ``libclang`` dependency
  (``pip install 'sphinx-codelinks[libclang]'``). Plain tree-sitter C/C++ extraction is
  unaffected when it is not installed. See :ref:`preprocessor_engine` for details.

- 📚 Traced the preprocessor-aware C/C++ engine in the feature documentation.

  ``features.rst`` now declares the engine as a feature with its fault children, and the
  implementation carries the one-line markers that link back to it. The engine is therefore
  covered by the project's own traceability report, like every supported language.

- 🧪 Added a declarative fixture and snapshot test layer for marker extraction.

  Extraction cases are now data (a YAML fixture plus a captured JSON snapshot) instead of
  bespoke test functions, covering the one-line, need-ID-reference and ``@rst`` block
  surfaces across all supported languages.

Fixes
.....

- 🐛 Anchor newline-terminated one-line markers to the start of the comment.

  A start sequence (default ``@``) that appeared in free-form prose was matched anywhere in
  a comment, so a line such as ``// See @author, check the example`` was parsed as a need
  definition and the bogus ID raised ``InvalidNeedException`` in Sphinx-Needs. Markers that
  run to the end of the line now only match when nothing but comment decoration (``//``,
  ``#``, ``*``, ``///``, ``//!``, …) and whitespace precedes the start sequence. Markers
  with an explicit ``end_sequence`` (e.g. ``[[ … ]]``) are self-delimiting and remain
  position-independent, so they may still follow prose.

- 🐛 Pinned ``typer`` and ``sphinxcontrib-typer`` to keep the documentation build working.

  ``typer 0.26.8`` removed ``rich_utils.STYLE_METAVAR`` and ``sphinxcontrib-typer 0.9.1``
  requires ``rich_utils.STYLE_TYPES``; either combination broke ``sphinx-build``. The
  dependencies are now capped at ``typer<0.26.8`` and ``sphinxcontrib-typer<0.9.1``.

.. _`release:1.3.0`:

1.3.0
-----

:Released: 20.06.2026

New and Improved
................

- ✨ Added Go parser for the ``analyse`` module.

  Need ID references and one-line need definitions can now be extracted from Go source files.
  The supported comment styles are ``//`` and ``/* */``.

- ✨ Added JSONC language support for the ``analyse`` module.

  Comments in JSONC files are now parsed for need ID references and one-line need definitions.
  ``.json`` files are also checked when they begin with a comment (see jsonc.org).

- 👌 Replaced ``gitignore-parser`` with ``ignore-python`` for source discovery.

  This adds native nested ``.gitignore`` support, improves performance, and brings behavioral
  parity with ubCode. A per-project ``follow_links`` configuration option was also added.

- ⬆️ Support and test Sphinx-Needs v5-8.
- ⬆️ Allow Sphinx 9.
- 📚 Documented C# language support in ``features.rst``.
- 🧪 Added a Sphinx integration test for C# source files.

Fixes
.....

- 🐛 Register Sphinx-Needs fields with a typed schema.

  The ``project``, ``file``, ``directory`` and URL fields are now registered with a typed
  (string) schema, so they no longer trigger schema violations on needs that do not set them
  when strict Sphinx-Needs schema validation is enabled.

- 🐛 Do not mutate the ``rebuild='env'`` ``src_trace_projects`` configuration during builds.

  Incremental Sphinx builds no longer re-read every document on each run.

- 🐛 Route ``analyse`` logging through the active environment instead of installing a stderr
  handler at import time.

  Routine INFO progress no longer goes to stderr unconditionally, and importing the package no
  longer forces a logging handler onto consumers.

- 🐛 Validate field default ordering in the oneline configuration.

  A required field defined after a field with a default is now reported as an error instead of
  being silently skipped.

.. _`release:1.2.0`:

1.2.0
-----

:Released: 18.02.2026

New and Improved
................

- ✨ Added Rust parser for the ``analyse`` module.

  Need ID references and one-line need definitions can now be extracted from Rust source files.

- 👌 Added explicit ``git_root`` configuration option.

  Users can now explicitly specify the Git root directory instead of relying on automatic detection.

- 👌 Enhanced warning logging in the oneline parser.

  Warning messages now include more context to help diagnose parsing issues.

- 📚 Added traceability page to the documentation.
- 📚 Added ``features.rst`` page documenting the full feature set with source tracing.

Fixes
.....

- 🐛 Fixed space handling in marker extraction.

  Leading and trailing spaces in extracted marker content are now correctly stripped.

.. _`release:1.1.0`:

1.1.0
-----

:Released: 02.10.2025

New and Improved
................

- ✨ Added C# parser for ``analyse`` module.

  Need ID references and marked RST blocks can be extracted from C# source files.
  The comments styles supported are:(``//``, ``/* */``, ``///``)

- ✨ Added YAML parser for ``analyse`` module.

  Need ID references can be extracted from YAML files.
  The supported comment style is ``#`` as well as inline comment style, e.g. ``key: value # comment``.

- 👌 Directive ``src-trace`` itself does not create need items anymore and only generate need items from the one-line need definition in the given source.

  The need item is removed because:

  - It has no use cases so far.
  - It creates extra need items users may not actually want in their documentation
  - It creates errors with some Sphinx-Needs configurations, e.g., when ``need_id_required`` or ``needs_statuses`` is defined.

Fixes
.....

- 🐛 Replace absolute path with relative path to fix ``local-url`` not working on the non-local environment
- 🐛 Add more file extensions of C/C++ for SourceDiscover

.. _`release:1.0.0`:

1.0.0
-----

:Released: 22.08.2025

New and Improved
................

- ✨ Added a new ``analyse`` CLI command and corresponding API.

  The ``analyse`` command parses source files (Python, C/C++) and extracts markers from comments.
  It can extract three types of markers, as documented in the :ref:`analyse <analyse>` section:

  - One-line need definitions
  - Need ID references
  - Marked RST blocks

  The extracted markers and their metadata are saved to a JSON file for further processing.

- ✨ Added a new ``write rst`` CLI command.

  The ``write rst`` command writes a reStructuredText file with :external+needs:ref:`needextend <needextend>` directive from the extracted markers generated by ``analyse``.
  The generated RST can be included in the Sphinx documentation to create the source code links in the existing needs

- 👌 Replaced ``virtual_docs`` with the new ``analyse`` module.

  The ``virtual_docs`` feature, which handled one-line need definitions (:ref:`OneLineCommentStyle <oneline>`),
  has been migrated into the new ``analyse`` module and removed from the core.
  The caching feature of ``virtual_docs`` is temporarily removed and may be reintroduced later.

- 👌 Updated the ``src-trace`` Sphinx directive.

  The ``src-trace`` directive now uses the new ``analyse`` API instead of the old ``virtual_docs`` one.

- 👌 Unified configuration in TOML

  The configuration for ``src-trace`` directive defined in TOML is now compatible with the new ``analyse`` module.

.. _`release:0.1.2`:

0.1.2
-----

:Released: 16.07.2025

Fixes
.....

- 🐛 Apply default configuration values when not given

  When a user does not specify certain configuration options, the extension will automatically use predefined default
  values, allowing users to get started quickly without needing to customize every option.
  Users can override these defaults by explicitly providing their own configuration values.

- 🐛 Fix local links for multi project configurations

  Local links between docs and one-line need definitions work correctly, when :ref:`src_dir <source_dir>` in multiple
  project configurations point at different locations.

.. _`release:0.1.1`:

0.1.1
-----

:Released: 11.07.2025

Initial release of ``Sphinx-CodeLinks``

This version features:

- ✨ Sphinx Directive ``src-trace``
- ✨ Virtual Docs and Source Discovery CLI
- ✨ One-line comment to define a ``Sphinx-Needs`` need item
