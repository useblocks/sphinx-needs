.. _changelog:

Changelog
=========

Unreleased
----------

New and Improved
................

- 🔧 Sphinx-CodeLinks now lives in the Sphinx-Needs repository, as
  `packages/sphinx-codelinks <https://github.com/useblocks/sphinx-needs/tree/master/packages/sphinx-codelinks>`__.

  The whole of ``useblocks/sphinx-codelinks``' history came with it, rewritten so that
  every historical commit already places its files under that directory: ``git log`` and
  ``git blame`` read the full history there with no ``--follow``, and
  ``packages/sphinx-codelinks/design/import-commit-map.txt`` maps every hash the old
  repository had to its hash in the new one.

  Some of the move is mechanical and already true; the rest is a checklist being worked
  through, and this bullet says which is which.

  - **The repository** (done): https://github.com/useblocks/sphinx-needs. Pull requests
    and branches are opened there, under ``packages/sphinx-codelinks/``.
  - **The issue tracker** (in progress): https://github.com/useblocks/sphinx-needs/issues.
    The open issues are being transferred, keeping their labels; the issue form has a
    *Package* dropdown with ``sphinx-codelinks`` among its options, and issues and pull
    requests concerning this package get a ``pkg: sphinx-codelinks`` label. Old issue URLs
    redirect.
  - **The documentation** (in progress): https://codelinks.useblocks.com stays the address.
    It is served by GitHub Pages from the old repository until the Read the Docs project
    and the DNS move are done, and by Read the Docs afterwards; nothing changes for a
    reader of that URL.
  - **The old repository** will be archived rather than deleted, so every permalink and
    every ``git+https://…/sphinx-codelinks.git@<sha>`` pin keeps resolving. Repositories
    pinning ``@main`` will stop receiving updates and should re-point at PyPI or at
    ``git+https://github.com/useblocks/sphinx-needs.git@…#subdirectory=packages/sphinx-codelinks``.
  - **Release tags** are prefixed: ``sphinx-codelinks-v1.4.0`` rather than ``1.4.0``. The
    bare namespace in that repository is Sphinx-Needs' own, and three of this project's
    seven released version numbers name existing Sphinx-Needs releases.
  - **An open pull request** can be moved across without losing its commits or their
    authorship: clone the old repository, fetch your branch, run the same
    ``git filter-repo --to-subdirectory-filter packages/sphinx-codelinks`` the import ran,
    and cherry-pick the range onto ``master`` in the monorepo. The import pull request's
    description carries the exact recipe.

- 🐛 ``sphinx_codelinks.__version__`` reported ``"0.1.0"``.

  It had said so since the first commit, through seven releases, while the distribution
  metadata said otherwise -- so ``import sphinx_codelinks; sphinx_codelinks.__version__``
  on an installed 1.4.0 returned the wrong string. It is exported in ``__all__``, so this
  is a public-API fix rather than a cosmetic one. From now on the two move together: the
  workspace's ``bump`` command writes both, and its ``check_workspace`` fence fails when
  they disagree.

- 🐛 ``locate_git_root`` found no git root in a linked git worktree, where ``.git`` is a
  file rather than a directory
  (`#106 <https://github.com/useblocks/sphinx-codelinks/issues/106>`__).

  ``locate_git_root`` required ``.git`` to be a directory, and ``get_remote_url`` and
  ``get_current_rev`` then read ``<root>/.git/config`` and ``<root>/.git/HEAD`` directly.
  In a linked worktree ``.git`` is a file holding ``gitdir: <path>``, the remotes live in
  the main repository's git directory named by ``commondir``, and only per-worktree state
  is local -- so every ``remote-url`` and every source link was missing, and a
  documentation build with ``-nW`` failed outright. Both shapes are now handled, with a
  regression test that builds a real worktree.

- 🔧 ``libclang`` is now genuinely optional for the test suite.

  It has always been an optional extra at runtime, and three test modules guarded it with
  ``pytest.importorskip``; a fourth imported ``sphinx_codelinks.analyse.preproc`` without
  a guard, and that package imports the libclang loader eagerly, so an environment without
  the wheel failed during collection rather than skipping. It now degrades honestly: the
  56 test cases that need the engine stop running, and the other 303 run -- the summary
  reads ``303 passed, 26 skipped``, because a module-level ``importorskip`` is one skip
  per module and never collects the tests inside it.

- 🔧 Lint and type checking now use the Sphinx-Needs workspace's configuration.

  The ``[tool.ruff]`` tables are the workspace root's, and the one per-file-ignore entry
  this package still needs went to the root with them, scoped to
  ``packages/sphinx-codelinks/tests/*`` (``E402``, ``SIM300`` -- 2 findings if it were
  dropped). It is scoped rather than ``**/tests/*`` because at the root that glob would
  silently loosen the other packages' suites too. Linting and formatting are now
  ``uv run poe lint``, which runs the whole workspace's hook set. Type checking moves from
  mypy to `ty <https://github.com/astral-sh/ty>`__ -- ``uv run poe typecheck`` -- the
  ``mypy`` dependency group becomes a ``typing`` one that pins the oldest supported Sphinx
  and docutils, and the 61 ``# type: ignore`` comments become 17 ``# ty: ignore`` ones. The dead ``pydantic.mypy`` plugin -- nothing in
  the package imports pydantic -- and the unused ``pytest-docker``, ``moto`` and ``psutil``
  test dependencies go with it. No behaviour changed; the whole diff is import order,
  suppressions and configuration.

- ‼️ Sphinx-Needs 8.5 or newer is now required (previously 5.0 or newer).

  Sphinx-CodeLinks is being imported into the Sphinx-Needs repository as a package of its
  uv workspace, where there is exactly one Sphinx-Needs and the manifest is required to
  track it tightly — ``sphinx-needs>=8.5.0,<9`` — so a wheel can never claim compatibility
  with a release it was not tested against. The per-Sphinx-Needs test factor is gone with
  it, and the two compatibility shims the old floor needed have been deleted: the
  ``add_field`` import fallback for Sphinx-Needs < 8, and the ``add_extra_option``
  signature probe that chose between a schema-aware and a schema-less registration. Both
  already took the modern branch on Sphinx-Needs 8.5, so behaviour there is unchanged.

- ✨ Python 3.11 is now supported; the floor moves down from 3.12.

  The full test suite passes on 3.11 unchanged, and the floor now equals the one the
  Sphinx-Needs workspace declares. The test matrix runs ``py{311,312,313,314}`` against
  ``sphinx{7,8,9}``, with one corner left out: ``py311-sphinx9`` is deliberately not a
  valid environment. Not because Sphinx 9 needs Python 3.12 -- Sphinx 9.0.x declares
  ``requires-python >=3.11`` and is exactly what a Python 3.11 user resolves by default,
  since 9.1 excludes itself for them -- but to align with the Sphinx-Needs workspace this
  package is being imported into, whose ``sphinx-9`` dependency group is
  ``sphinx~=9.1; python_version >= '3.12'`` and is therefore empty on 3.11. No package in
  that workspace is tested on 3.11 against Sphinx 9, and this matrix is replaced by that
  one at import, so the combination is left unexercised here too, deliberately.

- 📚 The documentation sources moved up beside ``conf.py``, so Read the Docs can build them.

  ``docs/source/*`` is now ``docs/*``, and the docs build no longer passes ``-c``:
  ``sphinx-build -nW --keep-going -b html docs docs/_build/html`` is what
  ``uv run poe docs-codelinks`` runs and what Read the Docs runs by itself. A ``.readthedocs.yaml`` comes with it, and the
  ``docs`` requirements move from a dependency group to a ``docs`` extra, which is the only
  form Read the Docs can install. The rendered site is unchanged; only the "edit this page"
  links point at the new paths.

- ✨ The default configuration file is now ``ubproject.toml``.

  :ref:`src_trace_config_from_toml` now defaults to ``"ubproject.toml"`` and the
  documentation recommends this file name throughout. ``ubproject.toml`` is the shared
  ubCode project file, which other useblocks tools — e.g. Sphinx-Needs via
  ``needs_from_toml`` or the ubCode checker in VS Code — read as well. Keeping the
  ``[codelinks]`` configuration in this single file makes all tools aware of the
  configured codelinks projects, which previously required a separate file per tool
  (e.g. ``src_trace.toml``) and left tools like the ubCode checker reporting
  ``Unknown codelinks project`` (ubcode-pub#75).

  A default file that does not exist or contains no ``[codelinks]`` table is silently
  ignored, so existing projects without ``ubproject.toml`` keep building without new
  warnings. Only a TOML file that was explicitly configured but cannot be loaded
  triggers a Sphinx warning, as before. The documentation project itself now stores
  its codelinks configuration in ``ubproject.toml``.

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
