.. _configuration:

Configuration
=============

The configuration for ``CodeLinks`` takes place in the project's :external+sphinx:ref:`conf.py file <build-config>`.

Each source code project may have different configurations because of its programming language or its locations.
Therefore, based on such considerations, there are **global options** and **project-specific options** for ``CodeLinks``.

.. attention:: It is highly recommended to set the configuration options in a TOML file, which can be used for both the Sphinx extension and the CLI application.

If the configurations are set in ``conf.py``,  the options start with the prefix ``src_trace_``.

Sphinx Configuration
--------------------

In ``conf.py``, a TOML file can be specified as the source of the configuration for Sphinx Directive ``src-trace``.

src_trace_config_from_toml
~~~~~~~~~~~~~~~~~~~~~~~~~~

Specifies the path to a `TOML file <https://toml.io>`__ containing **Sphinx-CodeLinks** configuration options. This allows you to maintain configuration in a separate file for better organization.

**Type:** ``str`` (relative path to the directory where conf.py is located)
**Default:** Not set

.. code-block:: python

   # In conf.py
   src_trace_config_from_toml = "codelinks.toml"

When using a TOML configuration file:

- Configuration options are placed under a ``[codelinks]`` section
- The ``src_trace_`` prefix is omitted in the TOML file
- TOML configuration overrides settings in :file:`conf.py`

.. caution:: Relative paths specified in the TOML file are resolved relative to the directory containing the TOML file, not the Sphinx project root.

.. _`set_local_url`:

Global Options
--------------

set_local_url
~~~~~~~~~~~~~

Enables the generation of local file system links to source code locations. When enabled, Sphinx Directive **src-trace** will add a custom field, which contains the local path to the source file, to generated needs.

**Type:** ``bool``
**Default:** ``False``

.. code-block:: toml

   [codelinks]
   set_local_url = true

local_url_field
~~~~~~~~~~~~~~~

Specifies the custom field name used for local source code links.

**Type:** ``str``
**Default:** ``"local-url"``
**Required when:** :ref:`set_local_url` is ``True``

.. code-block:: toml

   [codelinks]
   local_url_field = "local-url"

.. _`set_remote_url`:

set_remote_url
~~~~~~~~~~~~~~

Enables the generation of remote repository links to source code locations. When enabled, Sphinx Directive **src-trace** will add a custom field, which contains the URL to the remote repository (e.g., GitHub, GitLab) where the source file is hosted, to needs.

**Type:** ``bool``
**Default:** ``False``

.. code-block:: toml

   [codelinks]
   set_remote_url = true

remote_url_field
~~~~~~~~~~~~~~~~

Specifies the custom field name used for remote source code links.

**Type:** ``str``
**Default:** ``"remote-url"``
**Required when:** :ref:`set_remote_url` is ``True``

.. code-block:: toml

   [codelinks]
   remote_url_field = "remote-url"

outdir
~~~~~~

Specifies the output directory for generated artifacts such as extracted markers and warnings.

**Type:** ``str``
**Default:** ``"./output"``

.. code-block:: toml

   [codelinks]
   outdir = "output"

Project-Specific Options
------------------------

Project-specific options are configured within the ``projects`` section, allowing different settings for :ref:`SourceDiscover <discover>` and :ref:`SourceAnalyse <analyse>`.

projects
~~~~~~~~

Defines configuration for individual source code projects. Each project is identified by a unique name (key) and contains its own set of configuration options (value).

**Type:** ``dict[str, dict]``
**Default:** ``{}``

.. code-block:: toml

   [codelinks.projects.my_project]
   # Configuration for "my_project"

   [codelinks.projects.another_project]
   # Configuration for "another_project"

remote_url_pattern
~~~~~~~~~~~~~~~~~~

Defines the URL pattern for Sphinx Directive ``src-trace`` to generate links to remote source code repositories (e.g., GitHub, GitLab). This pattern uses placeholders that are dynamically replaced with actual values.

**Type:** ``str``
**Default:** Not set
**Required when:** :ref:`set_remote_url` is ``True``

**Available placeholders:**

- ``{commit}`` - Git commit hash
- ``{path}`` - Relative path to the source file
- ``{line}`` - Line number in the source file

.. code-block:: toml

   [codelinks.projects.my_project]
   remote_url_pattern = "https://github.com/user/repo/blob/{commit}/{path}#L{line}"

**Common patterns:**

- **GitHub:** ``https://github.com/user/repo/blob/{commit}/{path}#L{line}``
- **GitLab:** ``https://gitlab.com/user/repo/-/blob/{commit}/{path}#L{line}``
- **Bitbucket:** ``https://bitbucket.org/user/repo/src/{commit}/{path}#lines-{line}``

.. note:: This option integrates with :external+needs:ref:`need_string_links<needs_string_links>` to automatically generate clickable links in the documentation.

.. _`discover_config`:

source_discover
~~~~~~~~~~~~~~~

Configures how **Sphinx-CodeLinks** discovers and processes source files within a project. This option controls which files are analyzed for extracting documentation needs.

**Type:** ``dict``
**Default:** See below

.. code-block:: toml

   [codelinks.projects.my_project.source_discover]
   src_dir = "./"
   exclude = []
   include = []
   gitignore = true
   comment_type = "cpp"

**Configuration fields:**

- ``src_dir`` - Root directory for source file discovery (relative to Sphinx project root or the directory where the TOML config file is located if given)
- ``exclude`` - List of glob patterns to exclude from processing
- ``include`` - List of glob patterns to include (if empty, includes all files)
- ``gitignore`` - Whether to respect ``.gitignore`` rules when discovering files (Nested .gitignore is NOT supported yet)
- ``comment_type`` - Comment style for the programming language ("cpp" and "python" are currently supported)

.. _`source_dir`:

src_dir
^^^^^^^

Specifies the root directory for source file discovery. This path is resolved relative to the location of the TOML configuration file.

**Type:** ``str``
**Default:** ``"./"``

.. code-block:: toml

   [codelinks.projects.my_project.source_discover]
   src_dir = "../src"

**Examples:**

- ``"./"`` - Current directory (relative to config file)
- ``"../src"`` - Parent directory's src folder
- ``"./my_project/source"`` - Subdirectory within current directory

exclude
^^^^^^^

Defines a list of glob patterns for files and directories to exclude from discovery. This is useful for ignoring build artifacts, temporary files, or specific source files that shouldn't be processed.

**Type:** ``list[str]``
**Default:** ``[]``

.. code-block:: toml

   [codelinks.projects.my_project.source_discover]
   exclude = [
       "build/**"
       "*.tmp"
       "tests/fixtures/**"
       "vendor/third_party/**"
   ]

**Common exclusion patterns:**

- ``"build/**"`` - Exclude entire build directory
- ``"*.o"`` - Exclude object files
- ``"**/__pycache__/**"`` - Exclude Python cache directories
- ``"node_modules/**"`` - Exclude Node.js dependencies

include
^^^^^^^

Defines a list of glob patterns for files to explicitly include in discovery. When specified, only files matching these patterns will be processed, regardless of other filtering rules.

**Type:** ``list[str]``
**Default:** ``[]`` (include all files)

.. code-block:: toml

   [codelinks.projects.my_project.source_discover]
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
^^^^^^^^^^^^

Specifies the comment syntax style used in the source code files. This determines what file types are discovered and how **Sphinx-CodeLinks** parses comments for documentation extraction.

**Type:** ``str``
**Default:** ``"cpp"``
**Supported values:** ``"cpp"``, ``"python"``

.. code-block:: toml

   [codelinks.projects.my_project.source_discover]
   comment_type = "python"

**Supported comment styles:**

.. list-table:: Title
   :header-rows: 1
   :widths: 25, 25, 30, 50

   * - Language
     - comment_type
     - Comment Syntax
     - discovered file types
   * - C/C++
     - ``"cpp"``
     - ``//`` (single-line),
       ``/* */`` (multi-line)
     - ``c``, ``h``, ``.cpp``, and ``.hpp``
   * - Python
     - ``"python"``
     - ``#`` (single-line),
       ``""" """`` (docstrings)
     - ``.py``

.. note:: Future versions may support additional programming languages. Currently, only C/C++ and Python comment styles are supported.

gitignore
^^^^^^^^^

Controls whether to respect ``.gitignore`` files when discovering source files. When enabled, files and directories listed in ``.gitignore`` will be automatically excluded from processing.

**Type:** ``bool``
**Default:** ``true``

.. code-block:: toml

   [codelinks.projects.my_project.source_discover]
   gitignore = false

**Behavior:**

- ``true`` - Respect ``.gitignore`` rules (recommended)
- ``false`` - Ignore ``.gitignore`` files and process all matching files

.. important:: **Current Limitation:** This option only supports the root-level ``.gitignore`` file. Nested ``.gitignore`` files in subdirectories or parent directories are not currently processed.

For more information about the usage examples, see :ref:`source discover <discover>`.

.. _`analyse_config`:

analyse
~~~~~~~

Configures how **Sphinx-CodeLinks** analyse source files to extract markers from comments. This option defines how the markers in source code are parsed and extracted.

**Complete Configuration Example:**

.. code-block:: toml

   [codelinks]
   outdir = "output"

   [codelinks.projects.my_project.source_discover]
   src_dir = "./"
   exclude = []
   include = []
   gitignore = true
   comment_type = "cpp"

   [codelinks.projects.my_project.analyse]
   get_need_id_refs = true
   get_oneline_needs = true
   get_rst = true

   [codelinks.projects.my_project.analyse.oneline_comment_style]
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

   [codelinks.projects.my_project.analyse.need_id_refs]
   markers = ["@need-ids:"]

   [codelinks.projects.my_project.analyse.marked_rst]
   start_sequence = "@rst"
   end_sequence = "@endrst"

get_need_id_refs
^^^^^^^^^^^^^^^^

Enables the extraction of need IDs from source code comments. When enabled, **SourceAnalyse** will parse comments for specific markers that indicate need IDs, allowing them to be extracted for further usages.

**Type:** ``bool``
**Default:** ``False``

.. code-block:: toml

   [codelinks.projects.my_project.analyse]
   get_need_id_refs = true

get_oneline_needs
^^^^^^^^^^^^^^^^^

Enables the extraction of one-line needs directly from source code comments. When enabled, **SourceAnalyse** will parse comments for simplified :ref:`one-line patterns <oneline>` that represent needs, allowing them to be processed without requiring full RST syntax.

**Type:** ``bool``
**Default:** ``False``

.. code-block:: toml

   [codelinks.projects.my_project.analyse]
   get_oneline_needs = false

get_rst
^^^^^^^

Enables the extraction of marked RST text from source code comments. When enabled, **SourceAnalyse** will parse comments for specific markers that indicate RST blocks, allowing them to be extracted.

**Type:** ``bool``
**Default:** ``False``

.. code-block:: toml

   [codelinks.projects.my_project.analyse]
   get_rst = false

.. _`oneline_comment_style`:

analyse.oneline_comment_style
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Enables the use of simplified :ref:`one-line comment patterns <oneline>` to represent **Sphinx-Needs** items directly in source code, eliminating the need for embedded RST syntax.

**Type:** ``dict``
**Default:** See below

.. code-block:: toml

   [codelinks.projects.my_project.analyse.oneline_comment_style]
   start_sequence = "@"
   end_sequence = "\n"  # Platform-specific line ending
   field_split_char = ","
   needs_fields = [
         { name = "title", type = "str" },
         { name = "id", type = "str" },
         { name = "type", type = "str", default = "impl" },
         { name = "links", type = "list[str]", default = [] },
   ]

**Configuration fields:**

- ``start_sequence`` - Character(s) that begin a one-line comment pattern
- ``end_sequence`` - Character(s) that end a one-line comment pattern (typically line ending)
- ``field_split_char`` - Character used to separate fields within the comment
- ``needs_fields`` - List of field definitions for extracting need information

**Example usage:**

The following one-line comment in source code:

.. code-block:: cpp

   // @Function Bar, IMPL_4, impl, [SPEC_1, SPEC_2]

Is equivalent to this RST directive:

.. code-block:: rst

   .. impl:: Function Bar
      :id: IMPL_4
      :links: SPEC_1, SPEC_2

.. important:: The ``type`` and ``title`` fields must be configured in ``needs_fields`` as they are mandatory for **Sphinx-Needs**.

analyse.need_id_refs
^^^^^^^^^^^^^^^^^^^^

Configuration for Sphinx-Needs ID reference extraction.

**Type:** ``dict``
**Default:** See below

.. code-block:: toml

   [codelinks.projects.my_project.analyse.need_id_refs]
   markers = ["@need-ids:"]

**Configuration fields:**

- ``markers`` (``list[str]``) - List of marker strings that identify need ID references

analyse.marked_rst
^^^^^^^^^^^^^^^^^^

Configuration for marked RST block extraction.

**Type:** ``dict``
**Default:** See below

.. code-block:: toml

   [codelinks.projects.my_project.analyse.marked_rst]
   start_sequence = "@rst"
   end_sequence = "@endrst"

**Configuration fields:**

- ``start_sequence`` (``str``) - Marker that begins an RST block
- ``end_sequence`` (``str``) - Marker that ends an RST block
