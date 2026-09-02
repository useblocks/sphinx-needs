.. _directive:

Directive
=========

.. attention:: ``src-trace`` directive currently only supports :ref:`one-line need definition <oneline>`.

``CodeLinks`` provides ``src-trace`` directive and it can be used in the following ways:

.. code-block:: rst

   .. src-trace::
      :project: project_config
      :file: example.cpp

or

.. code-block:: rst

   .. src-trace::
      :project: project_config
      :directory: ./example

The ``src-trace`` directive has the following options:

* **project**: the project config specified in ``conf.py`` or TOML file to be used for source tracing.
* **file**: the source file to be traced.
* **directory**: the source files in the directory to be traced recursively.

Regarding the **file** and **directory** options:

- They are optional and mutually exclusive.
- The given paths are relative to ``src_dir`` defined in the source tracing configuration.
- If not given, the whole project will be examined.

Example
-------

With the following configuration for a demo source code project `dcdc <https://github.com/useblocks/sphinx-codelinks/tree/main/tests/data/dcdc>`_,

.. code-block:: toml
   :caption: ubproject.toml

   # Configuration for source tracing project "dcdc"
   [codelinks.projects.dcdc]
   remote_url_pattern = "https://github.com/useblocks/sphinx-codelinks/blob/{commit}/{path}#L{line}" # URL pattern for remote source code

   [codelinks.projects.dcdc.source_discover]
   src_dir = "../tests/data/dcdc" # Relative path from this TOML file to the source directory

   [codelinks.projects.dcdc.analyse]
   get_need_id_refs = false
   get_oneline_needs = true

   [codelinks.projects.dcdc.analyse.oneline_comment_style]
   # Configuration for oneline comment style
   start_sequence = "[["  # Start sequence for oneline comments
   end_sequence = "]]"    # End sequence for the online comments; default is newline character
   field_split_char = "," # Character to split fields in the comment
   # Fields that are defined in the oneline comment style
   needs_fields = [
     { "name" = "id", "type" = "str" },
     { "name" = "title", "type" = "str" },
     { "name" = "type", "type" = "str", "default" = "impl" },
     { "name" = "links", "type" = "list[str]", "default" = [
     ] },
   ]

The file is read by default, without any entry in :file:`conf.py` (see :ref:`src_trace_config_from_toml`).

The ``src-trace`` directive can be used with the **file** option:

.. code-block:: rst

   .. src-trace::
      :project: dcdc
      :file: ./charge/demo_1.cpp

The needs defined in source code are extracted and rendered to:

.. src-trace::
   :project: dcdc
   :file: ./charge/demo_1.cpp

The ``src-trace`` directive can be used with the **directory** option:

.. code-block:: rst

   .. src-trace::
      :project: dcdc
      :directory: ./discharge

The needs defined in source code are extracted and rendered to:

.. src-trace::
   :project: dcdc
   :directory: ./discharge

To have a more customized configuration of ``CodeLinks``, please refer to :ref:`configuration <configuration>`.
