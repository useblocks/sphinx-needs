.. _analyse:

Source Analyse
==============

The **Source Analyse** module is a powerful component of **Sphinx-CodeLinks** that extracts documentation-related content from source code comments. It provides both CLI and API interfaces for flexible integration into documentation workflows.

**Key Capabilities:**

- Extract **Sphinx-Needs** ID references from source code comments
- Process custom one-line comment patterns for rapid documentation
- Extract marked reStructuredText (RST) blocks embedded in comments
- Generate structured JSON output for further processing
- Support for multiple programming language comment styles

Overview
--------

Source Analyse works by parsing source code files and identifying specially marked comments that contain documentation information. This enables developers to embed documentation directly in their source code while maintaining clean separation between code and documentation.

The module supports three primary extraction modes:

1. **Sphinx-Needs ID References** - Links between code and requirements/specifications
2. **One-line Needs** - Simplified syntax for creating documentation needs
3. **Marked RST Blocks** - Full reStructuredText content embedded in comments

Supported Content Types
-----------------------

Sphinx-Needs ID References
~~~~~~~~~~~~~~~~~~~~~~~~~~

Extract references to **Sphinx-Needs** items directly from source code comments, enabling traceability between code implementations and requirements.

One-line Needs
~~~~~~~~~~~~~~

Use simplified comment patterns to define **Sphinx-Needs** items without complex RST syntax. See :ref:`OneLineCommentStyle <oneline>` for detailed information.

Marked RST Blocks
~~~~~~~~~~~~~~~~~

Embed complete reStructuredText content within source code comments for rich documentation that can be extracted and processed.

Limitations
-----------

**Current Limitations:**

- **Language Support**: C/C++ (``//``, ``/* */``), C# (``//``, ``/* */``, ``///``), Python (``#``), YAML (``#``), Rust (``//``, ``/* */``, ``///``), Go (``//``, ``/* */``), JSONC (``//``, ``/* */``) and Bash (``#``) comment styles are supported
- **Single Comment Style**: Each analysis run processes only one comment style at a time

Extraction Examples
-------------------

The following examples are configured with :ref:`the analyse configuration <analyse_config>`,

Sphinx-Needs ID References
~~~~~~~~~~~~~~~~~~~~~~~~~~

Below is an example of a C++ source file containing need ID references and the corresponding JSON output from the analyse.

.. tabs::

   .. code-tab:: cpp

        #include <iostream>

        // @need-ids: need_001, need_002, need_003, need_004
        void dummy_func1(){
            //...
        }

        // @need-ids: need_003
        int main() {
            std::cout << "Starting demo_1..." << std::endl;
            dummy_func1();
            std::cout << "Demo_1 finished." << std::endl;
            return 0;
        }

   .. code-tab:: json

        [
            {
                "filepath": "tests/data/need_id_refs/dummy_1.cpp",
                "remote_url": "https://github.com/useblocks/sphinx-codelinks/blob/fa5a9129d60203355ae9fe4a725246a88522c60c/tests/data/need_id_refs/dummy_1.cpp#L3",
                "source_map": {
                    "start": { "row": 2, "column": 13 },
                    "end": { "row": 2, "column": 51 }
                },
                "tagged_scope": "void dummy_func1(){\n     //...\n }",
                "need_ids": ["need_001", "need_002", "need_003", "need_004"],
                "marker": "@need-ids:",
                "type": "need-id-refs"
            },
            {
                "filepath": "tests/data/need_id_refs/dummy_1.cpp",
                "remote_url": "https://github.com/useblocks/sphinx-codelinks/blob/fa5a9129d60203355ae9fe4a725246a88522c60c/tests/data/need_id_refs/dummy_1.cpp#L8",
                "source_map": {
                    "start": { "row": 7, "column": 13 },
                    "end": { "row": 7, "column": 21 }
                },
                "tagged_scope": "int main() {\n   std::cout << \"Starting demo_1...\" << std::endl;\n   dummy_func1();\n   std::cout << \"Demo_1 finished.\" << std::endl;\n   return 0;\n }",
                "need_ids": ["need_003"],
                "marker": "@need-ids:",
                "type": "need-id-refs"
            }
        ]

**Output Structure:**

- ``filepath`` - Path to the source file containing the reference
- ``remote_url`` - URL to the source code in the remote repository
- ``source_map`` - Location information (row/column) of the marker
- ``tagged_scope`` - The code scope associated with the marker
- ``need_ids`` - List of referenced need IDs
- ``marker`` - The marker string used for identification
- ``type`` - Type of extraction ("need-id-refs")

.. _need_id_refs_in_build:

Need ID references in the build
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The ``src-trace`` directive attaches the ``@need-ids:`` references in the files it analyses to the needs they name, during the build -- the need may be defined in any document, before or after the directive. Each referenced need gets a list in its project's :ref:`ref_url_field` (default ``code_url``), one entry per reference, in source order:

.. code-block:: json

   "REQ_001": {
       "code_url": [
           "https://github.com/org/repo/blob/<commit>/src/refs.cpp#L1",
           "https://github.com/org/repo/blob/<commit>/src/refs.cpp#L3"
       ]
   }

- **The entries** are the project's ``remote_url_pattern`` filled in for the marker's line when :ref:`set_remote_url` is on, else the local link (as ``local-url`` gives it: the source file copied into the build output, relative to the need's document). On the need's card a remote entry renders as a link named ``src/refs.cpp#L1``; a value of the local shape (``<file>.<ext>#L<line>``) links to the generated source page. Outside a git repository, or in one without a commit yet, there is no remote URL (#2045): the local link is used when local URLs are on, else nothing is attached. With local URLs only, a file referenced by ``@need-ids:`` is copied into the output and gets a source page, as a file with a one-line need is; under ``-j N`` that page is not generated yet (`#2044 <https://github.com/useblocks/sphinx-needs/issues/2044>`__).
- **A need nothing references** carries ``null``, which is removed before schema validation, so a schema with ``unevaluatedProperties: false`` never sees the field on it. A schema with ``unevaluatedProperties: false`` on a type that code references must declare ``code_url``, or every referenced need of that type fails validation.
- **An unknown id** warns at the source line: ``src/refs.cpp:5: WARNING: @need-ids reference to unknown need 'NOSUCH_ID' [codelinks.need_id_ref]``. ``suppress_warnings = ["codelinks.need_id_ref"]`` silences it. Each project with attached references also reports ``codelinks [<project>]: N references attached, M unknown``; one marker naming an unknown id warns once, even when two fields cover its file.
- **A comment that starts with a configured marker** is a reference and never a one-line need, even on the default one-line style, whose start sequence ``@`` would match ``// @need-ids: A, B`` too.
- **Precedence.** The references replace any value the need's own directive or a ``needs_global_options`` default gave the field (ubCode's rule); a user's :external+needs:ref:`needextend <needextend>` overrides them, as the references are attached after every need is read and before any ``needextend`` is applied. ``:+code_url:`` appends to the attached list, but on a need nothing references it fails the build until `sphinx-needs #2038 <https://github.com/useblocks/sphinx-needs/issues/2038>`__ is fixed -- set the field (``:code_url:``) instead. The need is not marked as modified.
- **Overlapping scans** attach each reference once: two directives over the same file, or two projects whose source directories overlap. When those two projects' patterns differ, the reference keeps the URL of the first project by name (ubCode keeps the last one written). Files under different roots are different files, each kept: ``src/main.cpp`` in two repositories gives two references. Two projects naming different fields fill each its own field.
- **Incremental builds.** A file added to, removed from or edited in a directive's scope re-reads the document hosting the directive on the next build, for its references as for the needs it defines; the cost is one directory walk per scope per build, with no parsing: roughly 0.1 s per 2,000 discovered files on an Apple M2 Pro laptop, whatever their size -- the walk is the directive's own discovery plus a ``stat`` per file -- while parsing them costs tens of times more (2,000 200-line C++ files: ~0.1 s of walk against ~9 s of analysis). The build directory is never traced -- the output and doctree directories and, when they sit inside the documentation source directory as ``_build/`` does, that directory, so sibling builders' output is skipped too; an output tree elsewhere inside ``src_dir`` needs an ignore rule (``.gitignore`` with ``gitignore = true``, or ``exclude``). The whole containing directory is skipped, so an output directory placed directly beside traced sources hides them: keep the output in a directory of its own, as ``_build/`` is. A need whose references changed has its card rewritten, whichever document it is in: that document is written again, not read again. A ``needtable`` (or any other filter) in a third document that selects on the field is not rewritten -- the cross-document class ``needextend`` has today.

**Migrating from** ``analyse`` **→** ``write rst`` **→** ``include``: remove the ``.. include::`` of the generated file (and the steps that generate it); the references now arrive by themselves, in ``code_url`` rather than in the ``remote-url`` (or ``remote_url``) field the generated ``needextend`` directives set, and as a list rather than one comma-joined string. A project that keeps including the generated file gets both. If you declared the field yourself for that route (``needs_fields``), remove the declaration: the extension registers it, and a declaration of your own warns -- the extension's ``codelinks.config`` warning names the cure -- and, as a string field, fails schema validation on every referenced need.

**Differences from ubCode**, which reads the same ``ref_url_field``: ubCode stores one string, the last reference written, where this is a list of every reference; and ubCode drops a reference to an unknown need silently, where this warns. ubCode currently drops every need whose ``code_url`` is a list when it imports a Sphinx-built ``needs.json``, in a project whose codelinks configuration registers the field (``useblocks/ubcode#3838``).

Projects without a src-trace directive
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

A project that no ``src-trace`` directive traces still has its ``@need-ids:`` references attached, as in ubCode: its whole source directory (``src_dir`` of :ref:`discover_config`) is discovered and analysed, and the references reach the needs they name exactly as a directive's do -- the same field, URLs, warnings and ``codelinks [<project>]: N references attached, M unknown`` line. The gate is the directive's own, and there is no switch of its own: local or remote URLs on, references extracted, at least one marker, and a :ref:`ref_url_field` that is not ``""``. A project that at least one directive traces is left to its directives.

- **No need is created.** One-line needs and RST blocks in such a project's files are not rendered -- there is no directive, and so no document, to hold them. The project's line counts them: ``codelinks [src]: 12 files, 30 references, 2 one-line needs not created (no src-trace directive)``.
- **When it is analysed.** Every build walks the project's source directory and compares the files, their modification times and sizes with the last analysis; it analyses the project again only when they differ or the configuration changed. The cost of an unchanged build is that walk, with no parsing (see *Incremental builds* above for what the walk costs). A build that analysed the project again rewrites the cards of the needs whose references changed -- or, when none did, writes the root document -- so that Sphinx keeps the result and the next build analyses nothing.
- **Errors do not stop the build.** A missing source directory, or a discovery or analysis failure, warns once per project and build (``codelinks.need_id_ref``), and that project's references are not attached.
- **Under** ``-j N`` the analysis runs in the main process, so with local URLs only its source pages are generated, unlike a directive's (`#2044 <https://github.com/useblocks/sphinx-needs/issues/2044>`__).

Marked RST Blocks
~~~~~~~~~~~~~~~~~

This example demonstrates how the analyse extracts RST blocks from comments.

.. tabs::

   .. code-tab:: cpp

       #include <iostream>

       /*
       @rst
       .. impl:: implement dummy function 1
       :id: IMPL_71
       @endrst
       */
       void dummy_func1(){
           //...
       }

       // @rst..impl:: implement main function @endrst
       int main() {
           std::cout << "Starting demo_1..." << std::endl;
           dummy_func1();
           std::cout << "Demo_1 finished." << std::endl;
           return 0;
       }

   .. code-tab:: json

       [
           {
               "filepath": "marked_rst/dummy_1.cpp",
               "remote_url": "https://github.com/useblocks/sphinx-codelinks/blob/26b301138eef25c5130518d96eaa7a29a9c6c9fe/marked_rst/dummy_1.cpp#L4",
               "source_map": {
                   "start": { "row": 3, "column": 8 },
                   "end": { "row": 3, "column": 61 }
               },
               "tagged_scope": "void dummy_func1(){\n     //...\n }",
               "rst": ".. impl:: implement dummy function 1\n   :id: IMPL_71\n",
               "type": "rst"
           },
           {
               "filepath": "marked_rst/dummy_1.cpp",
               "remote_url": "https://github.com/useblocks/sphinx-codelinks/blob/26b301138eef25c5130518d96eaa7a29a9c6c9fe/marked_rst/dummy_1.cpp#L14",
               "source_map": {
                   "start": { "row": 13, "column": 7 },
                   "end": { "row": 13, "column": 40 }
               },
               "tagged_scope": "int main() {\n   std::cout << \"Starting demo_1...\" << std::endl;\n   dummy_func1();\n   std::cout << \"Demo_1 finished.\" << std::endl;\n   return 0;\n }",
               "rst": "..impl:: implement main function ",
               "type": "rst"
           }
       ]

**Output Structure:**

- ``filepath`` - Path to the source file containing the RST block
- ``remote_url`` - URL to the source code in the remote repository
- ``source_map`` - Location information of the RST markers
- ``tagged_scope`` - The code scope associated with the RST block
- ``rst`` - The extracted reStructuredText content
- ``type`` - Type of extraction ("rst")

**RST Block Formats:**

The module supports both multi-line and single-line RST blocks:

- **Multi-line blocks**: Use ``@rst`` and ``@endrst`` on separate lines
- **Single-line blocks**: Use ``@rst content @endrst`` on the same line

One-line Needs
--------------

**One-line Needs** provide a simplified syntax for creating **Sphinx-Needs** items directly in source code comments without requiring full RST syntax.

For comprehensive information about one-line needs configuration and usage, see :ref:`OneLineCommentStyle <oneline>`.

**Basic Example:**

.. code-block:: c

   // @Function Implementation, IMPL_001, impl, [REQ_001, REQ_002]

This single comment line creates a complete **Sphinx-Needs** item equivalent to:

.. code-block:: rst

   .. impl:: Function Implementation
       :id: IMPL_001
       :links: REQ_001, REQ_002

.. _preprocessor_engine:

Preprocessor-Aware C/C++ Extraction (libclang)
----------------------------------------------

By default, **Source Analyse** uses a tree-sitter parser that extracts **every** comment,
regardless of the C preprocessor. For C/C++ projects that rely on conditional compilation
(``#ifdef VARIANT_A`` …), this means needs from *all* branches are extracted — even
branches that are never compiled.

The optional **libclang engine** addresses this. When an
:ref:`analyse.preprocessor <preprocessor_config>` table is configured and ``comment_type``
is ``"cpp"``, each file is parsed as a real translation unit and **comments inside inactive
preprocessor branches are dropped**. Active needs keep their original line numbers — no
source transformation is performed.

.. important:: The libclang engine requires an optional dependency:
   ``pip install 'sphinx-codelinks[libclang]'``. The wheel bundles the native library, so
   no compiler is required on the user's machine.

How files are selected and parsed
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

File **discovery** is unchanged — :ref:`SourceDiscover <discover>` still decides which
files are candidates. A ``compile_commands.json`` database only determines *how* each
discovered file is parsed:

.. list-table::
   :header-rows: 1
   :widths: 45 55

   * - File
     - How it is parsed
   * - Listed in ``compile_commands.json``
     - Parsed with the exact flags the compiler used for that translation unit.
   * - A compiled source (``.c``, ``.cpp``, ``.cc``, ``.cxx``) **not** listed
     - Skipped — assumed to be excluded from the build (e.g. another platform).
   * - A **header** (``.h``, ``.hpp``, …) — never listed in a database
     - Parsed **standalone** using ``defines`` and ``includes`` (see below).
   * - Any file, when **no** database is found
     - Parsed with ``defines`` and ``includes``.

Header files
~~~~~~~~~~~~~

A ``compile_commands.json`` only ever lists compiled translation units (``.cpp`` files);
headers are pulled in via ``#include`` and never appear as entries. **Sphinx-CodeLinks**
therefore parses each discovered header **standalone**, using the ``defines`` and
``includes`` you configure. Include guards resolve correctly, and ``#ifdef`` branches are
evaluated against your ``defines``.

.. note:: Because headers are parsed standalone, they see only the global ``defines`` —
   **not** the per-file ``-D`` flags from ``compile_commands.json``. To extract a
   particular variant's needs from headers, mirror that variant into ``defines``. Treat
   one analysis run as **one variant**: set ``defines`` to the variant you want, and both
   sources and headers evaluate their conditions consistently.

Example
~~~~~~~

.. code-block:: cpp

   // include/feature.hpp
   #ifndef FEATURE_HPP
   #define FEATURE_HPP

   // @Always available, IMPL_BASE, impl, [REQ_BASE]
   void base();

   #ifdef VARIANT_A
   // @Variant A only, IMPL_VAR_A, impl, [REQ_A]
   void variant_a();
   #endif

   #endif

With ``defines = ["VARIANT_A"]`` both ``IMPL_BASE`` and ``IMPL_VAR_A`` are extracted.
With ``defines = []`` only ``IMPL_BASE`` is extracted — the ``#ifdef VARIANT_A`` block is
inactive, so its need is dropped. The include guard (``#ifndef FEATURE_HPP``) is always
active when the header is parsed on its own, so ``IMPL_BASE`` is never suppressed by it.

Variant handling is the caller's job
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Which preprocessor branches are active — and therefore which need markers are in
scope — is decided entirely by the ``-D`` macros libclang sees (from
``compile_commands.json`` for a compiled source, or from ``defines`` for headers
and the standalone path). **Sphinx-CodeLinks** does not model, generate, or
reconcile build variants itself.

For the result to be meaningful, the macros fed to the extractor and the macros
that select the variant in the code must come from the **same source of truth** —
whatever drives your variant management (Kconfig, pure::variants, a home-grown
generator). Generate the ``compile_commands.json`` / ``defines`` for one variant
from that source, run the analysis once, and the extracted markers are exactly
the ones active in that variant. Keeping the inputs consistent is the caller's
responsibility.

Limitations
~~~~~~~~~~~

The command line of a ``compile_commands.json`` entry is parsed for Clang/GCC-style
flags (``-D``, ``-I``, ``-std=`` …). MSVC ``cl.exe`` slash-style flags (``/D``,
``/I``, ``/std:`` …) are **not** recognised, so a database generated for the MSVC
compiler driver yields no defines or include dirs. Generate the database with
``clang`` / ``clang-cl`` (which emit Clang-style flags) for use with this engine.
