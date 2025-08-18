.. _analyse:

Source Analyse
===============

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
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Extract references to **Sphinx-Needs** items directly from source code comments, enabling traceability between code implementations and requirements.

One-line Needs
~~~~~~~~~~~~~~~

Use simplified comment patterns to define **Sphinx-Needs** items without complex RST syntax. See :ref:`OneLineCommentStyle <oneline>` for detailed information.

Marked RST Blocks
~~~~~~~~~~~~~~~~~~

Embed complete reStructuredText content within source code comments for rich documentation that can be extracted and processed.

Limitations
-----------

**Current Limitations:**

- **Language Support**: Only C/C++ (``//``, ``/* */``) and Python (``#``) comment styles are supported
- **Single Comment Style**: Each analysis run processes only one comment style at a time

Configuration
-------------

The **Source Analyse** module is configured using TOML files and leverages the :ref:`Source Discovery <discover>` module to locate source files for processing.

**Complete Configuration Example:**

.. code-block:: toml

    [source_discover]
    src_dir = "./"
    exclude = []
    include = []
    gitignore = true
    comment_type = "cpp"

    [analyse]
    get_need_id_refs = true
    get_oneline_needs = false
    get_rst = false
    outdir = "./output"

    [analyse.oneline_comment_style]
    start_sequence = "@"
    # End sequences is newline by default. Whether it is "\n" or "\r\n" depending on the platform
    end_sequence = "\n"
    field_split_char = ","
    needs_fields = [
        { name = "title", type = "str" },
        { name = "id", type = "str" },
        { name = "type", type = "str", default = "impl" },
        { name = "links", type = "list[str]", default = [] },
    ]

    [analyse.need_id_refs]
    markers = ["@need-ids:"]

    [analyse.marked_rst]
    start_sequence = "@rst"
    end_sequence = "@endrst"

Configuration Sections
-----------------------

analyse
~~~~~~~

Main configuration section for the ``analyse`` module.

**Options:**

- ``get_need_id_refs`` (``bool``) - Enable extraction of Sphinx-Needs ID references
- ``get_oneline_needs`` (``bool``) - Enable extraction of one-line needs
- ``get_rst`` (``bool``) - Enable extraction of marked RST blocks
- ``outdir`` (``str``) - Output directory for generated files

analyse.need_id_refs
~~~~~~~~~~~~~~~~~~~~

Configuration for Sphinx-Needs ID reference extraction.

**Options:**

- ``markers`` (``list[str]``) - List of marker strings that identify need ID references

analyse.marked_rst
~~~~~~~~~~~~~~~~~~

Configuration for marked RST block extraction.

**Options:**

- ``start_sequence`` (``str``) - Marker that begins an RST block
- ``end_sequence`` (``str``) - Marker that ends an RST block

analyse.oneline_comment_style
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Configuration for one-line needs extraction. See :ref:`oneline_comment_style` for detailed information.

**Minimal Configuration Example:**

The following configuration demonstrates the minimum settings required for basic analysis:

.. literalinclude:: ./../../../tests/data/analyse/minimum_config.toml
   :caption: minimum_config.toml
   :language: toml

This configuration enables extraction of **Sphinx-Needs ID References** and **Marked RST blocks** using the specified markers.

Extraction Examples
-------------------

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
