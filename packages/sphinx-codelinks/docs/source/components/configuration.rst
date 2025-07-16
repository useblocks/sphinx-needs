.. _configuration:

Configuration
=============

The configuration for ``CodeLinks`` take place in the project's :external+sphinx:ref:`conf.py file <build-config>`.

Each source code project may have different configurations because of its programming language or its locations.
Therefore, based on such consideration, there are **global options** and **project-specific options** for ``CodeLinks``

All configuration options starts with the prefix ``src_trace_`` for **Sphinx-CodeLinks**.

Global Options
--------------

The options starts with the prefix ``src_trace_`` are globally applied in the scope of Sphinx documentation.

src_trace_config_from_toml
~~~~~~~~~~~~~~~~~~~~~~~~~~

This configuration takes the (relative) path to a `toml file <https://toml.io>`__
which contains some or all of the ``CodeLinks`` configuration
(configuration in the toml will override that in the :file:`conf.py`).

.. code-block:: python

   # Specify the config path for source tracing in conf.py
   src_trace_config_from_toml = "src_trace.toml"

Configuration in the toml can contain any of the following options, under a ``[src_trace]`` section,
but with the ``src_trace_`` prefix removed.

.. caution:: Any configuration specifying relative paths in the toml file will be resolved relatively to the directory containing the ``toml`` file.

.. _`src_trace_set_local_url`:

src_trace_set_local_url
~~~~~~~~~~~~~~~~~~~~~~~

Set this option to ``True``, if the local link between a need to the local source code where it is defined is required.

Default: **False**

.. tabs::

   .. code-tab:: python

      src_trace_set_local_url = True

   .. code-tab:: toml

      [src_trace]
      set_local_url = true

src_trace_set_local_field
~~~~~~~~~~~~~~~~~~~~~~~~~

.. note:: This option is only required if :ref:`src_trace_set_local_url` is set to **True**.

Set the desired custom field name for the local link to the source code.

Default: **local-url**

.. tabs::

   .. code-tab:: python

      src_trace_local_url_field = "local-url"

   .. code-tab:: toml

      [src_trace]
      local_url_field = "local-url"

.. _`src_trace_set_remote_url`:

src_trace_set_remote_url
~~~~~~~~~~~~~~~~~~~~~~~~

Set this option to ``True``, if the remote link between a need to the remote source code
where it is defined is required.

The remote means where the source code is hosted such as GitHub.

Default: **False**

.. tabs::

   .. code-tab:: python

      src_trace_set_remote_url = True

   .. code-tab:: toml

      [src_trace]
      set_remote_url = true

src_trace_set_remote_field
~~~~~~~~~~~~~~~~~~~~~~~~~~

.. note:: This option is only required if :ref:`src_trace_set_remote_url` is set to **True**.

Set the desired custom field name for the remote link to the source code.

Default: **remote-url**

.. tabs::

   .. code-tab:: python

      src_trace_remote_url_field = "remote-url"

   .. code-tab:: toml

      [src_trace]
      remote_url_field = "remote-url"

Project Specific Options
------------------------

Options defined in **src_trace_projects** are project-specific.

src_trace_projects
~~~~~~~~~~~~~~~~~~

This option contains multiple sets of project-specific options. The project name is defined as the key in a dictionary
and its corresponding value is a dictionary containing the options specific to that project.

.. tabs::

   .. code-tab:: python

      project_options = dict()
      src_trace_projects = {
         "project_name": project_options
      }

   .. code-tab:: toml

      [src_trace.projects.project_name]
      # Project configuration for "project_name" shall be written here

comment_type
~~~~~~~~~~~~

The option defined the comment type used in source code of the project.

Default: **cpp**

.. note:: Currently, only C/C++ is supported

.. tabs::

   .. code-tab:: python

      src_trace_projects = {
         "project_name": {
            "comment_type": "c"
         }
      }

   .. code-tab:: toml

      [src_trace.projects.project_name]
      comment_type = "c"

.. _source_dir:

src_dir
~~~~~~~

The relative path from the ``conf.py`` or ``.toml`` file to the source code's root directory

Default: **./**

.. tabs::

   .. code-tab:: python

      src_trace_projects = {
         "project_name": {
            "src_dir": "./../src"
         }
      }

   .. code-tab:: toml

      [src_trace.projects.project_name]
      src_dir = "./../src"

remote_url_pattern
~~~~~~~~~~~~~~~~~~

This option only works with :ref:`src_trace_set_remote_url` set to **True**.
The pattern to access the source code to the remote repositories such as GitHub.

Default: **Not set**

.. tabs::

   .. code-tab:: python

      src_trace_projects = {
         "project_name": {
            "remote_url_pattern": "https://github.com/useblocks/sphinx-codelinks/blob/{commit}/{path}#L{line}"
         }
      }

   .. code-tab:: toml

      [src_trace.projects.project_name]
      remote_url_pattern = "https://github.com/useblocks/sphinx-codelinks/blob/{commit}/{path}#L{line}"

This option leverages the configuration of :external+needs:ref:`need_string_links<needs_string_links>`
with the following setup:

.. code-block:: python

   remote_url_pattern = remote_url_pattern.format(
      commit=commit_id,
      path=f"{remote_src_dir}/" + "{{value}}",
      line="{{lineno}}",
   )

   {
      "regex": r"^(?P<value>.+)#L(?P<lineno>.*)?",
      "link_url": remote_url_pattern,
      "link_name": "{{value}}#L{{lineno}}",
      "options": [remote_url_field],
   }

exclude
~~~~~~~

The option is a list of glob patterns to exclude the files which are not required to be addressed

Default: **[]**

.. tabs::

   .. code-tab:: python

      src_trace_projects = {
         "project_name": {
            "exclude": ["dcdc/src/ubt/ubt.cpp"]
         }
      }

   .. code-tab:: toml

      [src_trace.projects.project_name]
      exclude = ["dcdc/src/ubt/ubt.cpp"]

include
~~~~~~~

The option is a list of glob patterns to include the files which are required to be addressed

Default: **[]**

.. tabs::

   .. code-tab:: python

      src_trace_projects =
      {
         "project_name": {
            "include": ["dcdc/src/ubt/ubt.cpp"]
         }
      }

   .. code-tab:: toml

      [src_trace.projects.project_name]
      include = ["dcdc/src/ubt/ubt.cpp"]

.. note:: **include** option has the highest priority over **exclude** and **gitignore** options.

gitignore
~~~~~~~~~

The option to respect the .gitignore file.

Default: **True**

.. tabs::

   .. code-tab:: python

      src_trace_projects = {
         "project_name": {
            "gitignore": False
         }

   .. code-tab:: toml

      [src_trace.projects.project_name]
      gitignore = false

.. attention:: This option currently does NOT support nested .gitignore files

.. _`oneline_comment_style`:

oneline_comment_style
~~~~~~~~~~~~~~~~~~~~~

This option enables users to simply define a customized one-line-pattern comment to represent
``Sphinx-Needs`` need items instead of using RST.

Default:

.. tabs::

   .. code-tab:: python

      import os
      src_trace_projects = {
         "project_name": {
            "oneline_comment_style": {
               "start_sequence": "@",
               "end_sequence": os.linesep,
               "field_split_char": ",",
               needs_fields = [
                  {"name": "title"},
                  {"name": "id"},
                  {"name": "type", "default": "impl"},
                  {"name": "links", "type": "list[str]", "default": []},
               ]
            }
         }
      }

   .. code-tab:: toml

      [src_trace.projects.project_name.oneline_comment_style]
      start_sequence = "@"
      # end_sequence for the online comments; default is an os-dependant newline character
      field_split_char = ","
      needs_fields = [
         { "name" = "title", "type" = "str" },
         { "name" = "id", "type" = "str" },
         { "name" = "type", "type" = "str", "default" = "impl" },
         { "name" = "links", "type" = "list[str]", "default" = [] },
      ]

With the default, the following one-line comment will be extracted by ``CodeLinks`` and
it is equivalent to the following RST

.. tabs::

   .. code-tab:: c

      // @Function Bar, IMPL_4, impl, [SPEC_1, SPEC_2]

   .. code-tab:: RST

      .. impl:: Function Bar
         :id: IMPL_4
         :links: [SPEC_1, SPEC_2]

.. caution:: **type** and **title** must be configured in **needs_fields** as they are mandatory for Sphinx-Needs

More uses cases can be found in `tests <https://github.com/useblocks/sphinx-codelinks/tests>`__
