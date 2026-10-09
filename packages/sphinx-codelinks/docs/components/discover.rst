.. _discover:

Source Discover
===============

SourceDiscover is one of the modules provided in ``Codelinks``. It discovers the source files from the given directory.
It provides users CLI and API to discover the source files.

Usage Examples
--------------

**Basic Configuration:**

.. code-block:: toml

   [source_discover]
   src_dir = "./src"
   comment_type = "cpp"

**Advanced Filtering:**

.. code-block:: toml

   [source_discover]
   src_dir = "./"
   include = []
   exclude = ["src/legacy/**", "**/*_test.cpp"]
   gitignore = true
   follow_links = false
   comment_type = "cpp"

**Python Project:**

.. code-block:: toml

   [source_discover]
   src_dir = "./my_package"
   include = []
   exclude = ["tests/**", "setup.py"]
   comment_type = "python"

**TypeScript Project:**

.. code-block:: toml

   [source_discover]
   src_dir = "./frontend"
   include = ["**/*.ts", "**/*.tsx"]
   comment_type = "ts"

``exclude`` is left out: it defaults to the build-output directories (``node_modules``, ``dist``, ``build``, ``out``, ``coverage``) for this comment type; an explicit list, ``[]`` included, replaces that default.
