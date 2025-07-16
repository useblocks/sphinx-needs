.. _directive:

Directive
=========

``CodeLinks`` provides ``src-trace`` directive and it can be used in the following ways:

.. code-block:: rst

   .. src-trace:: example_with_file
      :project: project_config
      :file: example.cpp

or

.. code-block:: rst

   .. src-trace:: example_with_directory
      :project: project_config
      :directory: ./example

``src-trace`` directive has the following options:

* **project**: the project config specified in ``conf.py`` or ``toml`` file to be used for source tracing.
* **file**: the source file to be traced.
* **directory**: the source files in the directory to be traced recursively.

Regarding the **file** and **directory** options:

- they are optional and mutually exclusive.
- the given paths are relative to ``src_dir`` defined in the source tracing configuration
- if not given, the whole project will be examined.

Example
-------

With the following configuration for a demo source code project `dcdc <https://github.com/useblocks/sphinx-codelinks/tree/main/tests/data/dcdc>`_,

.. code-block:: python
   :caption: conf.py

   src_trace_config_from_toml = "src_trace.toml"

.. literalinclude:: ./../../src_trace.toml
   :caption: src_trace.toml
   :language: toml
   :lines: 1-25

``src-trace`` directive can be used with **file** option:

.. code-block:: rst

   .. src-trace:: dcdc demo_1
      :project: dcdc
      :file: ./charge/demo_1.cpp

The needs defined in source code are extracted and rendered to:

.. src-trace:: dcdc demo_1
   :project: dcdc
   :file: ./charge/demo_1.cpp

``src-trace`` directive can be used with **directory** option:

.. code-block:: rst

   .. src-trace:: dcdc charge
      :project: dcdc
      :directory: ./discharge

The needs defined in source code are extracted and rendered to:

.. src-trace:: dcdc charge
   :project: dcdc
   :directory: ./discharge

.. note:: **local-url** is not working on the website as it only supports local browse

To have a more customized configuration of ``CodeLinks``, please refer to :ref:`configuration <configuration>`.
