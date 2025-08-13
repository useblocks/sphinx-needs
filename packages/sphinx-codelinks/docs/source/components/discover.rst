.. _discover:

Source Discover
===============

SourceDiscover is one of the modules provided in ``Codelinks``. It discovers the source files from the given directory.
It provides users CLI and API to discover the source files.

Configuration
~~~~~~~~~~~~~

When used as CLI, a TOML config file can be provided to configure the source discover module.
The config file contains the following fields:

comment_type
------------

This option defines the comment type used in the source code of the project.

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
-------

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

exclude
-------

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
-------

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
---------

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
