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
