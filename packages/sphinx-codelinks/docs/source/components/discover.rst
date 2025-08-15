.. _discover:

Source Discover
===============

SourceDiscover is one of the modules provided in ``Codelinks``. It discovers the source files from the given directory.
It provides users CLI and API to discover the source files.


.. _`default_discover`:

Configuration
~~~~~~~~~~~~~

When used as CLI, a TOML config file can be provided to configure the source discover module.
The default configuration is as follows:

.. code-block:: toml

      [source_discover]
      src_dir = "./",
      exclude = [],
      include = [],
      gitignore = true,
      comment_type = "cpp"

The details of each field are the followings

src_dir
~~~~~~~

Specifies the root directory for source file discovery. This path is resolved relative to the location of the TOML configuration file.

**Type:** ``str``
**Default:** ``"./"``

.. code-block:: toml

   [source_discover]
   src_dir = "../src"

**Examples:**

- ``"./"`` - Current directory (relative to config file)
- ``"../src"`` - Parent directory's src folder
- ``"./my_project/source"`` - Subdirectory within current directory

exclude
~~~~~~~

Defines a list of glob patterns for files and directories to exclude from discovery. This is useful for ignoring build artifacts, temporary files, or specific source files that shouldn't be processed.

**Type:** ``list[str]``
**Default:** ``[]``

.. code-block:: toml

   [source_discover]
   exclude = [
       "build/**",
       "*.tmp",
       "tests/fixtures/**",
       "vendor/third_party/**"
   ]

**Common exclusion patterns:**

- ``"build/**"`` - Exclude entire build directory
- ``"*.o"`` - Exclude object files
- ``"**/__pycache__/**"`` - Exclude Python cache directories
- ``"node_modules/**"`` - Exclude Node.js dependencies

include
~~~~~~~

Defines a list of glob patterns for files to explicitly include in discovery. When specified, only files matching these patterns will be processed, regardless of other filtering rules.

**Type:** ``list[str]``
**Default:** ``[]`` (include all files)

.. code-block:: toml

   [source_discover]
   include = [
       "src/**/*.cpp",
       "src/**/*.h",
       "include/**/*.hpp"
   ]

**Priority:** The ``include`` option has the highest priority and overrides both ``exclude`` and ``gitignore`` settings.

**Common inclusion patterns:**

- ``"**/*.cpp"`` - Include all C++ source files
- ``"**/*.py"`` - Include all Python files
- ``"src/**"`` - Include everything in src directory
- ``"*.{c,h}"`` - Include C source and header files

comment_type
~~~~~~~~~~~~

Specifies the comment syntax style used in the source code files. This determines what file types are discovered and how **Sphinx-CodeLinks** parses comments for documentation extraction.

**Type:** ``str``
**Default:** ``"cpp"``
**Supported values:** ``"cpp"``, ``"python"``

.. code-block:: toml

   [source_discover]
   comment_type = "python"

**Supported comment styles:**

.. list-table::
   :header-rows: 1
   :widths: 40 40 50

   * - Language
     - comment_type
     - Comment Syntax
     - discovered file types
   * - C/C++
     - ``"cpp"``
     - ``//`` (single-line), ``/* */`` (multi-line)
     - ``c``, ``h``, ``.cpp``, and ``.hpp``
   * - Python
     - ``"python"``
     - ``#`` (single-line), ``""" """`` (docstrings)
     - ``.py``

.. note::
   Future versions may support additional programming languages. Currently, only C/C++ and Python comment styles are supported.

gitignore
~~~~~~~~~

Controls whether to respect ``.gitignore`` files when discovering source files. When enabled, files and directories listed in ``.gitignore`` will be automatically excluded from processing.

**Type:** ``bool``
**Default:** ``true``

.. code-block:: toml

   [source_discover]
   gitignore = false

**Behavior:**

- ``true`` - Respect ``.gitignore`` rules (recommended)
- ``false`` - Ignore ``.gitignore`` files and process all matching files

.. important::
   **Current Limitation:** This option only supports the root-level ``.gitignore`` file. Nested ``.gitignore`` files in subdirectories or parent directories are not currently processed.

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
   comment_type = "cpp"

**Python Project:**

.. code-block:: toml

   [source_discover]
   src_dir = "./my_package"
   include = []
   exclude = ["tests/**", "setup.py"]
   comment_type = "python"
