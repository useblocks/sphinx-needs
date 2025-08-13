.. _configuration:

Configuration[Sphinx]
=====================

The configuration for ``CodeLinks`` takes place in the project's :external+sphinx:ref:`conf.py file <build-config>`.

Each source code project may have different configurations because of its programming language or its locations.
Therefore, based on such consideration, there are **global options** and **project-specific options** for ``CodeLinks``

All configuration options start with the prefix ``src_trace_`` for **Sphinx-CodeLinks**.

Global Options
--------------

Global options use the ``src_trace_`` prefix and are applied across the entire Sphinx documentation project.

src_trace_config_from_toml
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Specifies the path to a `TOML file <https://toml.io>`__ containing **Sphinx-CodeLinks** configuration options. This allows you to maintain configuration in a separate file for better organization.

**Type:** ``str`` (relative path to the directory where conf.py locates)
**Default:** Not set

.. code-block:: python

   # In conf.py
   src_trace_config_from_toml = "src_trace.toml"

When using a TOML configuration file:

- Configuration options are placed under a ``[src_trace]`` section
- The ``src_trace_`` prefix is omitted in the TOML file
- TOML configuration overrides settings in :file:`conf.py`

.. caution::
   Relative paths specified in the TOML file are resolved relative to the directory containing the TOML file, not the Sphinx project root.

.. _src_trace_set_local_url:

src_trace_set_local_url
~~~~~~~~~~~~~~~~~~~~~~~

Enables the generation of local file system links to source code locations. When enabled, **Sphinx-CodeLinks** will add a custom field, which contains the local path to the source file, to generated needs.

**Type:** ``bool``
**Default:** ``False``

.. tabs::

   .. code-tab:: python

      src_trace_set_local_url = True

   .. code-tab:: toml

      [src_trace]
      set_local_url = true

src_trace_local_url_field
~~~~~~~~~~~~~~~~~~~~~~~~~

Specifies the custom field name used for local source code links.

**Type:** ``str``
**Default:** ``"local-url"``
**Required when:** :ref:`src_trace_set_local_url` is ``True``

.. tabs::

   .. code-tab:: python

      src_trace_local_url_field = "local-url"

   .. code-tab:: toml

      [src_trace]
      local_url_field = "local-url"

.. _src_trace_set_remote_url:

src_trace_set_remote_url
~~~~~~~~~~~~~~~~~~~~~~~~

Enables the generation of remote repository links to source code locations. When enabled, **Sphinx-CodeLinks** will add a custom field, which contains the URL to the remote repository (e.g., GitHub, GitLab) where the source file is hosted, to needs.

**Type:** ``bool``
**Default:** ``False``

.. tabs::

   .. code-tab:: python

      src_trace_set_remote_url = True

   .. code-tab:: toml

      [src_trace]
      set_remote_url = true

src_trace_remote_url_field
~~~~~~~~~~~~~~~~~~~~~~~~~~

Specifies the custom field name used for remote source code links.

**Type:** ``str``
**Default:** ``"remote-url"``
**Required when:** :ref:`src_trace_set_remote_url` is ``True``

.. tabs::

   .. code-tab:: python

      src_trace_remote_url_field = "remote-url"

   .. code-tab:: toml

      [src_trace]
      remote_url_field = "remote-url"

Project-Specific Options
-------------------------

Project-specific options are configured within the ``src_trace_projects`` dictionary, allowing different settings for each source code project being analyzed.

src_trace_projects
~~~~~~~~~~~~~~~~~~

Defines configuration for individual source code projects. Each project is identified by a unique name (key) and contains its own set of configuration options (value).

**Type:** ``dict[str, dict]``
**Default:** ``{}``

.. tabs::

   .. code-tab:: python

      src_trace_projects = {
          "my_project": {
              # Project-specific options go here
          },
          "another_project": {
              # Different options for another project
          }
      }

   .. code-tab:: toml

      [src_trace.projects.my_project]
      # Configuration for "my_project"

      [src_trace.projects.another_project]
      # Configuration for "another_project"

remote_url_pattern
~~~~~~~~~~~~~~~~~~~

Defines the URL pattern for generating links to remote source code repositories (e.g., GitHub, GitLab). This pattern uses placeholders that are dynamically replaced with actual values.

**Type:** ``str``
**Default:** Not set
**Required when:** :ref:`src_trace_set_remote_url` is ``True``

**Available placeholders:**

- ``{commit}`` - Git commit hash
- ``{path}`` - Relative path to the source file
- ``{line}`` - Line number in the source file

.. tabs::

   .. code-tab:: python

      src_trace_projects = {
          "my_project": {
              "remote_url_pattern": "https://github.com/user/repo/blob/{commit}/{path}#L{line}"
          }
      }

   .. code-tab:: toml

      [src_trace.projects.my_project]
      remote_url_pattern = "https://github.com/user/repo/blob/{commit}/{path}#L{line}"

**Common patterns:**

- **GitHub:** ``https://github.com/user/repo/blob/{commit}/{path}#L{line}``
- **GitLab:** ``https://gitlab.com/user/repo/-/blob/{commit}/{path}#L{line}``
- **Bitbucket:** ``https://bitbucket.org/user/repo/src/{commit}/{path}#lines-{line}``

.. note::
   This option integrates with :external+needs:ref:`need_string_links<needs_string_links>` to automatically generate clickable links in the documentation.

source_discover
~~~~~~~~~~~~~~~

Configures how **Sphinx-CodeLinks** discovers and processes source files within a project. This option controls which files are analyzed for extracting documentation needs.

**Type:** ``dict``
**Default:** See below

.. tabs::

   .. code-tab:: python

      src_trace_projects = {
          "my_project": {
              "source_discover": {
                  "src_dir": "./",
                  "exclude": [],
                  "include": [],
                  "gitignore": True,
                  "comment_type": "cpp"
              }
          }
      }

   .. code-tab:: toml

      [src_trace.projects.my_project.source_discover]
      src_dir = "./"
      exclude = []
      include = []
      gitignore = true
      comment_type = "cpp"

**Configuration fields:**

- ``src_dir`` - Root directory for source file discovery (relative to Sphinx project root or the directory where TOML config file locates if given)
- ``exclude`` - List of glob patterns to exclude from processing
- ``include`` - List of glob patterns to include (if empty, includes all files)
- ``gitignore`` - Whether to respect ``.gitignore`` rules when discovering files (Nested .gitignore is NOT supported yet)
- ``comment_type`` - Comment style for the programming language ("cpp" and "python" are currently supported)

For detailed information about each field, see :ref:`source discover <discover>`.

.. _oneline_comment_style:

oneline_comment_style
~~~~~~~~~~~~~~~~~~~~~

Enables the use of simplified one-line comment patterns to represent **Sphinx-Needs** items directly in source code, eliminating the need for embedded RST syntax.

**Type:** ``dict``
**Location:** ``src_trace_projects[project_name]["analyse"]["oneline_comment_style"]``

.. tabs::

   .. code-tab:: python

      import os
      src_trace_projects = {
          "my_project": {
              "analyse": {
                  "oneline_comment_style": {
                      "start_sequence": "@",
                      "end_sequence": os.linesep,
                      "field_split_char": ",",
                      "needs_fields": [
                          {"name": "title"},
                          {"name": "id"},
                          {"name": "type", "default": "impl"},
                          {"name": "links", "type": "list[str]", "default": []},
                      ]
                  }
              }
          }
      }

   .. code-tab:: toml

      [src_trace.projects.my_project.analyse.oneline_comment_style]
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

.. important::
   The ``type`` and ``title`` fields must be configured in ``needs_fields`` as they are mandatory for **Sphinx-Needs**.

**Additional examples and use cases:**

For more comprehensive examples and advanced configurations, see the `test cases <https://github.com/useblocks/sphinx-codelinks/tree/main/tests>`__.
