Analyse
=======

The ``Analyse`` is a :ref:`CLI tool <cli>` that also provides an API for programmatic use. Its primary function is to extract specific, marked content from comments within source code files.

It can extract three types of content:

- Sphinx-Needs ID References
- Oneline needs (see :ref:`OneLineCommentStyle <oneline>`)
- Marked reStructuredText (RST) blocks

Configuration
-------------

The ``Analyse`` is configured using a ``toml`` file. The examples throughout this document are based on the following configuration:

.. literalinclude:: ./../../../tests/data/analyse/default_config.toml
   :caption: default_config.toml
   :language: toml

This configuration instructs the analyse to extract ``Sphinx-Needs ID Refs`` and ``Marked rst text`` using the defined markers.

Sphinx-Needs ID Refs
--------------------

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

Marked RST
----------

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

Limitations
-----------

Please be aware of the following limitations:

- **Supported Languages**: The analyse only supports comment styles for C/C++ (``//``, ``/*...*/``) and Python (``#``).
- **Single Comment Style**: An analysis run can only process a single comment style at a time.
- **Configuration Incompatibility**: The TOML configuration file cannot be shared with the ``CodeLink`` Sphinx extensions.
